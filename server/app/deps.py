from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings, Settings
from app.core.auth import verify_token
from app.models.user import User

DBSession = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_current_user(
    db: DBSession,
    settings: SettingsDep,
    authorization: Optional[str] = Header(default=None),
) -> User:
    """从 Authorization: Bearer <token> 解析当前用户"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未携带登录凭证")
    token = authorization.split(" ", 1)[1].strip()
    user_id = verify_token(token, settings.SECRET_KEY)
    if not user_id:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    user = await db.get(User, user_id)
    if not user or user.deleted == 1 or user.status != 0:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    db: DBSession,
    settings: SettingsDep,
    authorization: Optional[str] = Header(default=None),
) -> Optional[User]:
    """可选登录态：未登录返回 None，不抛 401（用于首页等公开页）"""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    user_id = verify_token(token, settings.SECRET_KEY)
    if not user_id:
        return None
    user = await db.get(User, user_id)
    if not user or user.deleted == 1 or user.status != 0:
        return None
    return user


OptionalUser = Annotated[Optional[User], Depends(get_optional_user)]
