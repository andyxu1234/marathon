"""用户相关路由 —— 登录 / 我的页 / 头像上传"""

import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from app.deps import DBSession, CurrentUser, OptionalUser, SettingsDep
from app.schemas.common import OkOut
from app.schemas.user import UserProfile, LoginOut, UserStats, AvatarUploadOut
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


class WeChatLoginRequest(BaseModel):
    code: str
    appid: Optional[str] = None   # wx.getAccountInfoSync().miniProgram.appId，精确配 secret
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class DouyinLoginRequest(BaseModel):
    """抖音小程序登录请求 —— 字段名与微信一致，复用前端登录适配器的传参格式"""
    code: str
    appid: Optional[str] = None   # 抖音小程序 appid，精确匹配 DOUYIN_APP_SECRET
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class PasswordLoginRequest(BaseModel):
    username: str
    password: str


class ProfileUpdate(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[int] = Field(default=None, ge=0, le=2, description="0未设置 1男 2女")
    age_group: Optional[int] = Field(
        default=None, ge=0, le=8,
        description="0未设置 1<=34 2:35-39 3:40-44 4:45-49 5:50-54 6:55-59 7:60-64 8>=65",
    )


@router.post("/login/wechat", response_model=LoginOut)
async def login_wechat(
    payload: WeChatLoginRequest,
    db: DBSession,
    settings: SettingsDep,
    current: OptionalUser = None,
):
    """微信小程序登录：code (+真实 appid) → openid → 找/建用户 → 发 token

    传 Authorization 头时的额外行为：
      若当前登录态是 dev_ 沙盒账号，且本次换到了真实 openid，则把该账号
      的 openid 就地升级为真实值（保留 user_id 与收藏/报名数据），而非新建账号。
    """
    return await user_service.login_by_wechat(
        db,
        settings,
        payload.code,
        app_id=payload.appid,
        nickname=payload.nickname,
        avatar=payload.avatar,
        current_user=current,
    )


@router.post("/login/douyin", response_model=LoginOut)
async def login_douyin(
    payload: DouyinLoginRequest,
    db: DBSession,
    settings: SettingsDep,
    current: OptionalUser = None,
):
    """抖音 / 字节跳动小程序登录：code (+真实 appid) → openid → 找/建用户 → 发 token

    接口结构与 /users/login/wechat 一致，后端走 DouyinClient
    调 jscode2session 换取 openid。
    """
    return await user_service.login_by_douyin(
        db,
        settings,
        payload.code,
        app_id=payload.appid,
        nickname=payload.nickname,
        avatar=payload.avatar,
        current_user=current,
    )


@router.post("/login/password", response_model=LoginOut)
async def login_password(
    payload: PasswordLoginRequest, db: DBSession, settings: SettingsDep
):
    """用户名密码登录（开发期/管理员用）"""
    return await user_service.login_by_password(
        db, settings, payload.username, payload.password
    )


@router.post("/avatar", response_model=AvatarUploadOut)
async def upload_avatar(
    user: CurrentUser,
    settings: SettingsDep,
    file: UploadFile = File(..., description="头像图片文件，最大 5MB，支持 jpg/png/webp/gif"),
):
    """上传用户头像，返回 /uploads/avatars/xxx.ext 相对 URL，前端可直接存 user.avatar"""
    # 1. 大小校验
    max_bytes = settings.AVATAR_MAX_MB * 1024 * 1024
    # UploadFile.size 可能为 None，保守在 read 时也限一次
    if file.size is not None and file.size > max_bytes:
        raise HTTPException(status_code=413, detail=f"头像超过 {settings.AVATAR_MAX_MB}MB")

    # 2. 扩展名 + Content-Type 双重校验
    ext = ""
    raw_name = (file.filename or "").strip().lower()
    for allow in settings.AVATAR_ALLOW_EXTS:
        if raw_name.endswith(allow):
            ext = allow
            break
    # 兜底：用 content-type 映射
    if not ext:
        ct = (file.content_type or "").lower()
        mapping = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
        ext = mapping.get(ct, "")
    if not ext:
        raise HTTPException(status_code=400, detail=f"仅支持 {settings.AVATAR_ALLOW_EXTS} 图片")

    # 3. 写文件
    save_dir = Path(settings.UPLOAD_DIR) / "avatars"
    save_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}{ext}"
    save_path = save_dir / file_name

    # 同步流式写入（FastAPI UploadFile.read 已经在后台线程处理即可）
    try:
        with open(save_path, "wb") as f:
            total_written = 0
            while True:
                chunk = await file.read(1024 * 256)  # 256KB
                if not chunk:
                    break
                total_written += len(chunk)
                if total_written > max_bytes:
                    # 超限：删除已写的临时文件
                    try:
                        save_path.unlink()
                    except OSError:
                        pass
                    raise HTTPException(status_code=413, detail=f"头像超过 {settings.AVATAR_MAX_MB}MB")
                f.write(chunk)
    finally:
        await file.close()

    url = f"{settings.UPLOAD_URL_PREFIX}/avatars/{file_name}"
    return AvatarUploadOut(url=url)


@router.get("/me", response_model=UserProfile)
async def get_me(db: DBSession, user: CurrentUser):
    """获取当前登录用户资料"""
    profile = await user_service.get_profile(db, user.user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="用户不存在")
    return profile


@router.put("/me", response_model=UserProfile)
async def update_me(payload: ProfileUpdate, db: DBSession, user: CurrentUser):
    """更新昵称/头像/性别/年龄段"""
    profile = await user_service.update_profile(
        db,
        user.user_id,
        nickname=payload.nickname,
        avatar=payload.avatar,
        gender=payload.gender,
        age_group=payload.age_group,
    )
    if not profile:
        raise HTTPException(status_code=404, detail="用户不存在")
    return profile


@router.get("/me/stats", response_model=UserStats)
async def get_my_stats(db: DBSession, user: CurrentUser):
    """我的页统计（场次数 / 累计花费 / 最近完赛）"""
    return await user_service.get_user_stats(db, user.user_id)


@router.post("/logout", response_model=OkOut)
async def logout():
    """退出登录（前端清 token 即可，后端无 session）"""
    return OkOut(ok=True, message="已退出")
