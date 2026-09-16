"""报名状态业务服务"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.event_customize import EventCustomize
from app.models.favorite import Favorite
from app.models.registration import Registration
from app.schemas.registration import RegistrationUpdate
from app.services.favorite_service import ensure_favorite


async def get_registration(
    db: AsyncSession, user_id: int, event_id: int
) -> Optional[Registration]:
    q = await db.execute(
        select(Registration).where(
            Registration.user_id == user_id,
            Registration.event_id == event_id,
        )
    )
    return q.scalar_one_or_none()


async def get_custom_registration(
    db: AsyncSession, user_id: int, custom_event_id: int
) -> Optional[Registration]:
    q = await db.execute(
        select(Registration).where(
            Registration.user_id == user_id,
            Registration.custom_event_id == custom_event_id,
        )
    )
    return q.scalar_one_or_none()


def _parse_start_time(start_time: Optional[str]) -> Optional[datetime]:
    if not start_time:
        return None
    try:
        return datetime.strptime(start_time, "%Y-%m-%d")
    except ValueError:
        return None


async def update_registration(
    db: AsyncSession,
    user_id: int,
    event_id: int,
    payload: RegistrationUpdate,
) -> Optional[Registration]:
    # 必须先关注了，才能更新报名状态
    await ensure_favorite(db, user_id, event_id)
    reg = await get_registration(db, user_id, event_id)
    if not reg:
        return None

    data = payload.model_dump(exclude_none=True)
    for k, v in data.items():
        setattr(reg, k, v)
    await db.flush()
    return reg


async def update_custom_registration(
    db: AsyncSession,
    user_id: int,
    custom_event_id: int,
    payload: RegistrationUpdate,
) -> Optional[Registration]:
    """更新自定义赛事的报名状态"""
    # 确保收藏关系存在
    fav_q = await db.execute(
        select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.custom_event_id == custom_event_id,
            Favorite.deleted == 0,
        )
    )
    if not fav_q.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="未关注该自定义赛事")

    reg = await get_custom_registration(db, user_id, custom_event_id)
    if not reg:
        return None

    data = payload.model_dump(exclude_none=True)
    for k, v in data.items():
        setattr(reg, k, v)
    await db.flush()
    return reg


async def add_race(
    db: AsyncSession,
    user_id: int,
    *,
    event_id: Optional[int] = None,
    event_name: Optional[str] = None,
    start_time: Optional[str] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    location: Optional[str] = None,
    event_level: int = 0,
    registration_status: int = 0,
    payment_status: int = 0,
    lottery_status: int = 0,
    race_type: int = 0,
    fee: Optional[float] = None,
) -> tuple[Optional[Event], Optional[EventCustomize], Favorite, Registration]:
    """添加赛事：数据库已有赛事走收藏+报名记录；否则新建自定义赛事"""
    if event_id:
        # 1) 选择数据库已有赛事
        e = await db.get(Event, event_id)
        if not e or e.deleted == 1:
            raise HTTPException(status_code=404, detail="赛事不存在")

        # 检查是否新收藏，避免重复计数
        fav_q = await db.execute(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.event_id == event_id,
            )
        )
        existing_fav = fav_q.scalar_one_or_none()
        is_new_favorite = not existing_fav or existing_fav.deleted == 1

        fav = await ensure_favorite(db, user_id, event_id)

        # 获取或创建报名记录，并写入用户提交的状态
        reg = await get_registration(db, user_id, event_id)
        old_reg_status = reg.registration_status if reg else 0
        if not reg:
            reg = Registration(
                user_id=user_id,
                event_id=event_id,
                fee=fee if fee is not None else 0,
            )
            db.add(reg)
            await db.flush()

        reg.registration_status = registration_status
        reg.payment_status = payment_status
        reg.lottery_status = lottery_status
        reg.race_type = race_type if race_type in (1, 2, 3) else 0
        if fee is not None:
            reg.fee = fee
        await db.flush()

        # 同步赛事冗余计数
        if is_new_favorite:
            e.favorite_count = (e.favorite_count or 0) + 1
        if registration_status == 1 and old_reg_status != 1:
            e.registration_count = (e.registration_count or 0) + 1
        await db.flush()

        return e, None, fav, reg

    # 2) 自定义赛事分支
    if not event_name or not event_name.strip():
        raise HTTPException(status_code=400, detail="请填写赛事名称")

    location_str = location or f"{province or ''}{city or ''}".strip()
    ec = EventCustomize(
        user_id=user_id,
        event_name=event_name.strip(),
        start_time=_parse_start_time(start_time),
        province=province,
        city=city,
        location=location_str,
        event_level=event_level,
    )
    db.add(ec)
    await db.flush()  # 拿 customize_id

    fav = Favorite(user_id=user_id, custom_event_id=ec.customize_id)
    db.add(fav)
    await db.flush()

    reg = Registration(
        user_id=user_id,
        custom_event_id=ec.customize_id,
        registration_status=registration_status,
        payment_status=payment_status,
        lottery_status=lottery_status,
        race_type=race_type if race_type in (1, 2, 3) else 0,
        fee=fee if fee is not None else 0,
    )
    db.add(reg)
    await db.flush()

    return None, ec, fav, reg


async def delete_custom_race(
    db: AsyncSession,
    user_id: int,
    custom_event_id: int,
) -> bool:
    """删除自定义赛事：软删除 mi_event_customize + mi_favorite + mi_registration

    三者必须同时存在且 user_id 匹配，返回是否成功删除。
    """
    # 验证归属
    ec_q = await db.execute(
        select(EventCustomize).where(
            EventCustomize.customize_id == custom_event_id,
            EventCustomize.user_id == user_id,
            EventCustomize.deleted == 0,
        )
    )
    ec = ec_q.scalar_one_or_none()
    if not ec:
        return False

    ec.deleted = 1

    fav_q = await db.execute(
        select(Favorite).where(
            Favorite.custom_event_id == custom_event_id,
            Favorite.user_id == user_id,
        )
    )
    fav = fav_q.scalar_one_or_none()
    if fav:
        fav.deleted = 1

    reg_q = await db.execute(
        select(Registration).where(
            Registration.custom_event_id == custom_event_id,
            Registration.user_id == user_id,
        )
    )
    reg = reg_q.scalar_one_or_none()
    if reg:
        reg.deleted = 1

    await db.flush()
    return True
