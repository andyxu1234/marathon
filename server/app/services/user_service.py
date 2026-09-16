"""用户业务服务"""

from __future__ import annotations

from typing import Optional
from datetime import datetime

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.auth import create_token
from app.core.wechat import WeChatClient
from app.core.douyin import DouyinClient
from app.models.user import User
from app.models.favorite import Favorite
from app.models.registration import Registration
from app.models.event import Event
from app.models.event_customize import EventCustomize
from app.schemas.user import (
    UserProfile,
    LoginOut,
    UserStats,
    RecentFinishedItem,
    NextRaceItem,
    MyRankItem,
)


# ---- 平台常量 ----
PLATFORM_WEAPP = 1
PLATFORM_DOUYIN = 2
PLATFORM_H5_SANDBOX = 9

_PLATFORM_PREFIX = {
    PLATFORM_WEAPP: "wx",
    PLATFORM_DOUYIN: "tt",
    PLATFORM_H5_SANDBOX: "h5",
}

_SANDBOX_OPENID_PREFIX = "dev_"


def _runner_level(total: int) -> str:
    """根据完赛场次给出跑者等级（v1 简版）"""
    if total >= 10:
        return "金标跑者"
    if total >= 5:
        return "精英跑者"
    if total >= 1:
        return "跑者"
    return "新手"


def to_profile(u: User, registered_count: int = 0) -> UserProfile:
    return UserProfile(
        user_id=u.user_id,
        nickname=u.nickname or u.username,
        avatar=u.avatar,
        username=u.username,
        runner_level=_runner_level(registered_count),
        runner_no=f"R{u.user_id:06d}",
        gender=u.gender or 0,
        age_group=u.age_group or 0,
        is_sandbox=(u.openid or "").startswith(_SANDBOX_OPENID_PREFIX),
    )


def _sandbox_openid(platform: int, code: str, use_app_id: Optional[str]) -> str:
    """沙盒 openid：基于 (platform + appid + code) 做稳定哈希"""
    import hashlib

    base = f"{platform}|{use_app_id or 'local'}|{code}"
    digest = hashlib.md5(base.encode("utf-8")).hexdigest()
    return f"{_SANDBOX_OPENID_PREFIX}{digest[:16]}"


async def login_by_platform(
    db: AsyncSession,
    settings: Settings,
    code: str,
    *,
    platform: int,
    app_id: Optional[str] = None,
    nickname: Optional[str] = None,
    avatar: Optional[str] = None,
    current_user: Optional[User] = None,
) -> LoginOut:
    """通用平台登录：code → openid → 找/建用户 → 发 token

    platform: 1=weapp 2=douyin 9=h5沙盒

    经验修正：
      - 必须按请求里的真实 appid（getAccountInfoSync 取得）精确匹配 appsecret，
        避免 A 小程序 appid 配了 B 小程序 secret 导致 invalid appsecret。
      - openid 查找从单字段改成 (platform, openid) 复合，避免跨平台撞 openid。

    openid 升级机制（保留）：
      - 历史 dev_ 沙盒账号 → 拿到真实 openid 后就地升级，
        保留 user_id → 收藏 / 报名 / 统计数据全部不丢。
      - 旧账号的 platform 也一并更新（从 9 改成 1 或 2）。
    """
    from loguru import logger

    # ---- 1. 判定用哪套 appid/secret ----
    use_app_id = app_id or _default_app_id(settings, platform)
    use_app_secret: Optional[str] = None

    if platform == PLATFORM_WEAPP:
        if not settings.WECHAT_APP_SECRET:
            logger.error(
                "[login-wechat] WECHAT_APP_SECRET 未配置！无法换取真实 openid，"
                "本次登录将写入 dev_ 沙盒值。"
                "请到微信公众平台 mp.weixin.qq.com → 开发管理 → 开发设置 获取 AppSecret，"
                "填入 server/.env 的 WECHAT_APP_SECRET。"
            )
        elif use_app_id and use_app_id != settings.WECHAT_APP_ID and settings.WECHAT_APP_ID:
            logger.warning(
                f"[login-wechat] 请求 appid={use_app_id!r} 与配置 "
                f"WECHAT_APP_ID={settings.WECHAT_APP_ID!r} 不匹配，回退沙盒 openid。"
            )
        else:
            use_app_secret = settings.WECHAT_APP_SECRET

    elif platform == PLATFORM_DOUYIN:
        if not settings.DOUYIN_APP_SECRET:
            logger.error(
                "[login-douyin] DOUYIN_APP_SECRET 未配置！无法换取真实 openid，"
                "本次登录将写入 dev_ 沙盒值。"
                "请到抖音开放平台 developer.open-douyin.com → 开发设置 获取 AppSecret，"
                "填入 server/.env 的 DOUYIN_APP_SECRET。"
            )
        elif use_app_id and use_app_id != settings.DOUYIN_APP_ID and settings.DOUYIN_APP_ID:
            logger.warning(
                f"[login-douyin] 请求 appid={use_app_id!r} 与配置 "
                f"DOUYIN_APP_ID={settings.DOUYIN_APP_ID!r} 不匹配，回退沙盒 openid。"
            )
        else:
            use_app_secret = settings.DOUYIN_APP_SECRET

    if not use_app_id:
        logger.warning(
            f"[login-{platform}] 前端未传 appid（建议用 getAccountInfoSync 取真实值）。"
        )

    # ---- 2. code 换 openid ----
    openid: Optional[str] = None
    if platform in (PLATFORM_WEAPP, PLATFORM_DOUYIN) and use_app_id and use_app_secret:
        if platform == PLATFORM_WEAPP:
            client = WeChatClient(use_app_id, use_app_secret)
        else:
            client = DouyinClient(use_app_id, use_app_secret)
        try:
            openid = await client.get_openid(code)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[login-{platform}] 平台接口失败，回退沙盒 openid: {exc}")
            openid = None
        finally:
            await client.close()

    is_real_openid = bool(openid)
    if not openid:
        openid = _sandbox_openid(platform, code, use_app_id)

    # ---- 3. 找 / 升级 / 建 用户 ----
    q = await db.execute(
        select(User).where(User.platform == platform, User.openid == openid)
    )
    user = q.scalar_one_or_none()
    is_new = False

    if user:
        # 已存在：直接复用
        pass
    elif (
        is_real_openid
        and current_user is not None
        and (current_user.openid or "").startswith(_SANDBOX_OPENID_PREFIX)
    ):
        # openid 升级：把 dev_ 沙盒账号就地改写成真实 openid，
        # 保留 user_id → 收藏 / 报名 / 统计数据全部不丢。
        logger.info(
            f"[login-{platform}] openid 升级：user_id={current_user.user_id} "
            f"platform={current_user.platform}→{platform} "
            f"{current_user.openid} → {openid}"
        )
        current_user.openid = openid
        current_user.platform = platform
        current_user.app_id = use_app_id
        if not current_user.username or current_user.username.startswith(("wx_", "tt_", "h5_")):
            prefix = _PLATFORM_PREFIX.get(platform, "mp")
            current_user.username = f"{prefix}_{openid[-8:]}"
        user = current_user
    else:
        # 新用户：按"当前平台的有效用户数"算下一个序号（排除已软删）。
        # 不排除 dev_ 沙盒：沙盒账号在各自平台内也占序号，
        # 否则每次新用户（secret未配时都是 dev_）count 永远是 0，序号卡死。
        cnt_q = await db.execute(
            select(func.count(User.user_id)).where(
                and_(
                    User.deleted == 0,
                    User.platform == platform,
                )
            )
        )
        next_seq = (cnt_q.scalar() or 0) + 1
        prefix = _PLATFORM_PREFIX.get(platform, "mp")
        username = f"{prefix}_{openid[-8:]}"
        user = User(
            username=username,
            password="",  # 小程序登录无密码
            nickname=None,  # flush 后按 next_seq 生成
            avatar=avatar,
            openid=openid,
            platform=platform,
            app_id=use_app_id,
            user_type=0,
            status=0,
        )
        db.add(user)
        await db.flush()
        user.nickname = nickname or f"跑友{next_seq:05d}"
        is_new = True

    # 已存在用户：如果传了昵称/头像（比如 my 页「完善资料」后再登录），就更新
    if not is_new:
        if nickname and user.nickname != nickname:
            user.nickname = nickname
        if avatar and user.avatar != avatar:
            user.avatar = avatar

    await db.flush()

    # 更新最后登录时间
    user.login_date = datetime.utcnow()
    await db.flush()

    token = create_token(user.user_id, settings.SECRET_KEY, settings.TOKEN_EXPIRE_HOURS)
    reg_cnt = await _count_registered(db, user.user_id)
    return LoginOut(token=token, user=to_profile(user, reg_cnt), is_new_user=is_new)


def _default_app_id(settings: Settings, platform: int) -> str:
    """按 platform 取默认 app_id 兜底"""
    if platform == PLATFORM_WEAPP:
        return settings.WECHAT_APP_ID
    if platform == PLATFORM_DOUYIN:
        return settings.DOUYIN_APP_ID
    return ""


# ---- 向后兼容：保留原函数名，内部转调 login_by_platform ----
async def login_by_wechat(
    db: AsyncSession,
    settings: Settings,
    code: str,
    *,
    app_id: Optional[str] = None,
    nickname: Optional[str] = None,
    avatar: Optional[str] = None,
    current_user: Optional[User] = None,
) -> LoginOut:
    """微信小程序登录（向后兼容的薄包装，内部转调 login_by_platform）"""
    return await login_by_platform(
        db, settings, code,
        platform=PLATFORM_WEAPP,
        app_id=app_id,
        nickname=nickname,
        avatar=avatar,
        current_user=current_user,
    )


async def login_by_douyin(
    db: AsyncSession,
    settings: Settings,
    code: str,
    *,
    app_id: Optional[str] = None,
    nickname: Optional[str] = None,
    avatar: Optional[str] = None,
    current_user: Optional[User] = None,
) -> LoginOut:
    """抖音小程序登录"""
    return await login_by_platform(
        db, settings, code,
        platform=PLATFORM_DOUYIN,
        app_id=app_id,
        nickname=nickname,
        avatar=avatar,
        current_user=current_user,
    )


async def login_by_password(
    db: AsyncSession,
    settings: Settings,
    username: str,
    password: str,
) -> LoginOut:
    """用户名 + 密码登录（开发期/管理员用）"""
    q = await db.execute(
        select(User).where(User.username == username, User.deleted == 0)
    )
    user = q.scalar_one_or_none()
    # v1 简版：明文比对（DB 中 password 字段在小程序用户为空）
    if not user or (user.password and user.password != password):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user.login_date = datetime.utcnow()
    await db.flush()
    token = create_token(user.user_id, settings.SECRET_KEY, settings.TOKEN_EXPIRE_HOURS)
    reg_cnt = await _count_registered(db, user.user_id)
    return LoginOut(token=token, user=to_profile(user, reg_cnt), is_new_user=False)


async def get_profile(db: AsyncSession, user_id: int) -> Optional[UserProfile]:
    u = await db.get(User, user_id)
    if not u or u.deleted == 1:
        return None
    reg_cnt = await _count_registered(db, user_id)
    return to_profile(u, reg_cnt)


async def update_profile(
    db: AsyncSession,
    user_id: int,
    *,
    nickname: Optional[str] = None,
    avatar: Optional[str] = None,
    gender: Optional[int] = None,
    age_group: Optional[int] = None,
) -> Optional[UserProfile]:
    u = await db.get(User, user_id)
    if not u or u.deleted == 1:
        return None
    if nickname:
        u.nickname = nickname
    if avatar:
        u.avatar = avatar
    if gender is not None:
        # 0未设置 1男 2女；越界值防御性拒绝（不写库）
        if gender not in (0, 1, 2):
            raise ValueError("gender 必须是 0/1/2（0未设置 1男 2女）")
        u.gender = gender
    if age_group is not None:
        # 0未设置 1<=34 2:35-39 3:40-44 4:45-49 5:50-54 6:55-59 7:60-64 8>=65
        if age_group not in (0, 1, 2, 3, 4, 5, 6, 7, 8):
            raise ValueError("age_group 必须是 0-8（0未设置 1<=34 ... 8>=65）")
        u.age_group = age_group
    await db.flush()
    reg_cnt = await _count_registered(db, user_id)
    return to_profile(u, reg_cnt)


async def _count_registered(db: AsyncSession, user_id: int) -> int:
    q = await db.execute(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.user_id == user_id,
            Registration.registration_status == 1,
            Registration.deleted == 0,
        )
    )
    return int(q.scalar() or 0)


async def get_user_stats(db: AsyncSession, user_id: int) -> UserStats:
    """我的页统计 —— 真实计算，不再 mock

    数据源：
      - mi_registration + mi_event → 完赛数 / 里程 / PB / 花费
      - mi_favorite → 关注数 + 下一场比赛
      - ranking_service → 我的排名（复用其聚合逻辑）
    """
    from datetime import date

    from app.services import ranking_service as rs
    from app.services.favorite_service import _status_from_start_time  # noqa: F401

    u = await db.get(User, user_id)
    if not u:
        return UserStats(user_id=user_id)

    # === 1. Registration 聚合 ===
    # 1a. 报名中 / 完赛数
    reg_cnt_q = await db.execute(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.user_id == user_id,
            Registration.registration_status == 1,
            Registration.deleted == 0,
        )
    )
    registered_count = int(reg_cnt_q.scalar() or 0)

    finish_cnt_q = await db.execute(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.user_id == user_id,
            Registration.result_status >= 1,
            Registration.deleted == 0,
        )
    )
    finished_count = int(finish_cnt_q.scalar() or 0)

    # 1b. 累计花费（已缴费的 fee）
    spent_q = await db.execute(
        select(func.coalesce(func.sum(Registration.fee), 0))
        .where(
            Registration.user_id == user_id,
            Registration.payment_status == 1,
            Registration.deleted == 0,
        )
    )
    total_spent = float(spent_q.scalar() or 0)

    # 1c. 里程 + PB：复用 ranking_service 的聚合口径
    reg_stmt = (
        select(
            Registration.user_id,
            Registration.event_id,
            Registration.finish_time,
            Registration.result_status,
            Registration.fee,
            Registration.payment_status,
            Event.event_type,
            Event.start_time,
        )
        .join(Event, Event.event_id == Registration.event_id)
        .where(
            Registration.user_id == user_id,
            Registration.deleted == 0,
            Event.deleted == 0,
        )
    )
    reg_rows = (await db.execute(reg_stmt)).all()

    total_distance = 0.0
    half_pb_seconds: Optional[int] = None
    full_pb_seconds: Optional[int] = None
    for r in reg_rows:
        if r.result_status >= 1:
            km = rs.DISTANCE_BY_EVENT_TYPE.get(r.event_type)
            if km:
                total_distance += km
            sec = rs._parse_pb(r.finish_time)
            if sec is not None:
                if r.event_type == 2:
                    if half_pb_seconds is None or sec < half_pb_seconds:
                        half_pb_seconds = sec
                elif r.event_type == 1:
                    if full_pb_seconds is None or sec < full_pb_seconds:
                        full_pb_seconds = sec

    # 1d. 最近 3 场完赛
    recent_q = await db.execute(
        select(Event, Registration)
        .join(Registration, Registration.event_id == Event.event_id)
        .where(
            Registration.user_id == user_id,
            Registration.result_status >= 1,
            Registration.deleted == 0,
            Event.deleted == 0,
        )
        .order_by(Registration.update_time.desc())
        .limit(3)
    )
    recent: list[RecentFinishedItem] = []
    for e, r in recent_q:
        recent.append(
            RecentFinishedItem(
                event_id=e.event_id,
                event_name=e.event_name,
                start_time=e.start_time.strftime("%Y-%m-%d") if e.start_time else None,
                finish_time=r.finish_time,
                result_status=r.result_status or 0,
                is_pb=(r.result_status == 2),
            )
        )

    # === 2. 关注数 ===
    fav_cnt_q = await db.execute(
        select(func.count())
        .select_from(Favorite)
        .where(Favorite.user_id == user_id, Favorite.deleted == 0)
    )
    favorited_count = int(fav_cnt_q.scalar() or 0)

    # === 3. 下一场比赛（从 Favorites 找最近的 start_time） ===
    next_race: Optional["NextRaceItem"] = None
    today = date.today()

    # 官方赛事
    reg_soon_q = await db.execute(
        select(Event, Registration)
        .join(Favorite, Favorite.event_id == Event.event_id)
        .outerjoin(Registration, Registration.event_id == Favorite.event_id)
        .where(
            Favorite.user_id == user_id,
            Favorite.deleted == 0,
            Event.deleted == 0,
            Event.start_time.isnot(None),
        )
        .order_by(Event.start_time.asc())
        .limit(50)
    )
    soon_rows = reg_soon_q.all()

    # 自定义赛事
    custom_soon_q = await db.execute(
        select(EventCustomize, Registration)
        .join(Favorite, Favorite.custom_event_id == EventCustomize.customize_id)
        .outerjoin(
            Registration,
            Registration.custom_event_id == Favorite.custom_event_id,
        )
        .where(
            Favorite.user_id == user_id,
            Favorite.deleted == 0,
            EventCustomize.deleted == 0,
            EventCustomize.start_time.isnot(None),
        )
        .order_by(EventCustomize.start_time.asc())
        .limit(50)
    )
    custom_soon_rows = custom_soon_q.all()

    # 合并排序取最近一场
    all_soon: list[tuple[date, dict]] = []

    TYPE_LABELS = {1: "全马", 2: "半马", 3: "健康跑", 4: "越野", 5: "其他", 0: "自定义"}

    for ev, _reg in soon_rows:
        d = ev.start_time.date() if ev.start_time else None
        if d is None:
            continue
        days = (d - today).days
        if days >= -14:  # 只取未来14天内或已开赛的
            all_soon.append((
                d,
                {
                    "event_id": ev.event_id,
                    "custom_event_id": None,
                    "event_name": ev.event_name,
                    "event_type": ev.event_type or 0,
                    "event_type_label": TYPE_LABELS.get(ev.event_type or 0, "全马"),
                    "start_date": d.strftime("%Y-%m-%d"),
                    "days_away": days,
                    "is_custom": False,
                },
            ))

    for ec, _reg in custom_soon_rows:
        d = ec.start_time.date() if ec.start_time else None
        if d is None:
            continue
        days = (d - today).days
        if days >= -14:
            all_soon.append((
                d,
                {
                    "event_id": None,
                    "custom_event_id": ec.customize_id,
                    "event_name": ec.event_name,
                    "event_type": 0,
                    "event_type_label": "自定义",
                    "start_date": d.strftime("%Y-%m-%d"),
                    "days_away": days,
                    "is_custom": True,
                },
            ))

    if all_soon:
        all_soon.sort(key=lambda x: x[0])
        next_race = NextRaceItem(**all_soon[0][1])

    # === 4. 我的排名（取 distance / full_pb / half_pb 三者中最好的） ===
    my_rank: Optional["MyRankItem"] = None
    if finished_count > 0 or total_spent > 0:
        best_rank: Optional[int] = None
        best_metric: Optional[str] = None
        best_value_label: Optional[str] = None
        best_total: int = 0

        for metric in (rs.METRIC_DISTANCE, rs.METRIC_FULL_PB, rs.METRIC_HALF_PB, rs.METRIC_SPENT):
            rl = await rs.list_rankings(db, metric=metric, current_user_id=user_id, limit=50)
            if rl.my_rank is None or rl.my_rank.rank == 0:
                continue
            rank = rl.my_rank.rank
            if best_rank is None or rank < best_rank:
                best_rank = rank
                best_metric = metric
                best_value_label = rl.my_value_label or "—"
                best_total = rl.total_users

        # 至少需要 2 个用户才显示排名
        if best_rank and best_metric and best_total >= 2:
            pct = max(0, min(100, int((best_rank / max(best_total, 1)) * 100)))
            metric_label = rs.METRIC_LABELS.get(best_metric, best_metric.replace("_", " "))
            insight = f"你比全国 {100 - pct}% 的跑者{metric_label}"
            my_rank = MyRankItem(
                metric=best_metric,
                rank=best_rank,
                total_users=best_total,
                value_label=best_value_label or "—",
                insight=insight,
            )

    return UserStats(
        user_id=user_id,
        nickname=u.nickname or u.username,
        avatar=u.avatar,
        runner_level=_runner_level(finished_count),
        runner_no=f"R{user_id:06d}",
        gender=u.gender or 0,
        age_group=u.age_group or 0,
        registered_count=registered_count,
        finished_count=finished_count,
        total_spent=total_spent,
        total_distance=round(total_distance, 2),
        half_pb=rs._format_pb(half_pb_seconds) if half_pb_seconds else None,
        full_pb=rs._format_pb(full_pb_seconds) if full_pb_seconds else None,
        favorited_count=favorited_count,
        next_race=next_race,
        my_rank=my_rank,
        recent_finished=recent,
    )
