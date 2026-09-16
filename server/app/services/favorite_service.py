"""收藏/关注页业务服务"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.event_customize import EventCustomize
from app.models.favorite import Favorite
from app.models.registration import Registration
from app.schemas.favorite import (
    FavoriteItem,
    FavoriteStats,
    RegistrationBrief,
)
from app.utils.labels import (
    event_type_label,
    event_level_label,
    event_status_label,
)
from app.utils.timefmt import fmt_dt, fmt_date, days_until


async def _get_or_create_registration(
    db: AsyncSession, user_id: int, event_id: int
) -> Registration:
    """获取或创建一条报名记录（首次关注时建空壳，费用/项目继承赛事）"""
    q = await db.execute(
        select(Registration).where(
            Registration.user_id == user_id,
            Registration.event_id == event_id,
        )
    )
    reg = q.scalar_one_or_none()
    if not reg:
        # 建空壳时：费用自动带出赛事报名费（无则 0），报名项目继承赛事类型
        ev_q = await db.execute(select(Event).where(Event.event_id == event_id))
        ev = ev_q.scalar_one_or_none()
        inherit_type = ev.event_type if ev and ev.event_type in (1, 2, 3) else 0
        reg = Registration(
            user_id=user_id,
            event_id=event_id,
            fee=float(ev.registration_fee) if ev and ev.registration_fee is not None else 0,
            race_type=inherit_type,
        )
        db.add(reg)
        await db.flush()
    return reg


def _brief_from_registration(r: Optional[Registration]) -> RegistrationBrief:
    if not r:
        return RegistrationBrief()
    return RegistrationBrief(
        registration_status=r.registration_status or 0,
        payment_status=r.payment_status or 0,
        lottery_status=r.lottery_status or 0,
        race_type=r.race_type or 0,
        fee=float(r.fee) if r.fee is not None else None,
        bib_number=r.bib_number,
        finish_time=r.finish_time,
        result_status=r.result_status or 0,
    )


def _status_from_start_time(start_time: Optional[datetime]) -> tuple[int, str]:
    """自定义赛事没有 event_status 字段，根据比赛日期推算"""
    if not start_time:
        return 1, event_status_label(1)
    days = days_until(start_time)
    if days is None:
        return 1, event_status_label(1)
    if days < 0:
        return 5, event_status_label(5)
    if days == 0:
        return 4, event_status_label(4)
    return 1, event_status_label(1)


def _custom_location(ec: EventCustomize) -> str:
    if ec.location:
        return ec.location
    return f"{ec.province or ''}{ec.city or ''}".strip()


async def _list_regular_favorites(
    db: AsyncSession,
    user_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[FavoriteItem], int]:
    """已有赛事的关注列表"""
    cnt_q = await db.execute(
        select(func.count())
        .select_from(Favorite)
        .join(Event, Event.event_id == Favorite.event_id)
        .where(Favorite.user_id == user_id, Favorite.deleted == 0, Event.deleted == 0)
    )
    total = int(cnt_q.scalar() or 0)

    rows_q = await db.execute(
        select(Favorite, Event, Registration)
        .join(Event, Event.event_id == Favorite.event_id)
        .outerjoin(
            Registration,
            and_(
                Registration.user_id == user_id,
                Registration.event_id == Favorite.event_id,
            ),
        )
        .where(Favorite.user_id == user_id, Favorite.deleted == 0, Event.deleted == 0)
        .order_by(Favorite.create_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items: list[FavoriteItem] = []
    for fav, e, reg in rows_q:
        items.append(
            FavoriteItem(
                event_id=e.event_id,
                custom_event_id=None,
                is_custom=False,
                event_name=e.event_name,
                event_type=e.event_type,
                event_type_label=event_type_label(e.event_type),
                event_level=e.event_level,
                event_level_label=event_level_label(e.event_level),
                event_status=int(e.event_status or 1),
                event_status_label=event_status_label(int(e.event_status or 1)),
                start_time=fmt_dt(e.start_time),
                start_date_label=fmt_date(e.start_time),
                location=e.location,
                cover_image=e.cover_image,
                registration_fee=float(e.registration_fee) if e.registration_fee is not None else None,
                registration=_brief_from_registration(reg),
                days_to_race=days_until(e.start_time),
                create_time=fmt_dt(fav.create_time),
            )
        )
    return items, total


async def _list_custom_favorites(
    db: AsyncSession,
    user_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[FavoriteItem], int]:
    """自定义赛事的关注列表"""
    cnt_q = await db.execute(
        select(func.count())
        .select_from(Favorite)
        .join(EventCustomize, EventCustomize.customize_id == Favorite.custom_event_id)
        .where(
            Favorite.user_id == user_id,
            Favorite.deleted == 0,
            EventCustomize.deleted == 0,
        )
    )
    total = int(cnt_q.scalar() or 0)

    rows_q = await db.execute(
        select(Favorite, EventCustomize, Registration)
        .join(EventCustomize, EventCustomize.customize_id == Favorite.custom_event_id)
        .outerjoin(
            Registration,
            and_(
                Registration.user_id == user_id,
                Registration.custom_event_id == Favorite.custom_event_id,
            ),
        )
        .where(
            Favorite.user_id == user_id,
            Favorite.deleted == 0,
            EventCustomize.deleted == 0,
        )
        .order_by(Favorite.create_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items: list[FavoriteItem] = []
    for fav, ec, reg in rows_q:
        status, status_label = _status_from_start_time(ec.start_time)
        race_type = reg.race_type if reg and reg.race_type in (1, 2, 3) else 5
        items.append(
            FavoriteItem(
                event_id=None,
                custom_event_id=ec.customize_id,
                is_custom=True,
                event_name=ec.event_name,
                event_type=race_type,
                event_type_label=event_type_label(race_type),
                event_level=ec.event_level or 0,
                event_level_label=event_level_label(ec.event_level or 0),
                event_status=status,
                event_status_label=status_label,
                start_time=fmt_dt(ec.start_time),
                start_date_label=fmt_date(ec.start_time),
                location=_custom_location(ec),
                cover_image=None,
                registration_fee=None,
                registration=_brief_from_registration(reg),
                days_to_race=days_until(ec.start_time),
                create_time=fmt_dt(fav.create_time),
            )
        )
    return items, total


async def list_favorites(
    db: AsyncSession,
    user_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[FavoriteItem], int]:
    """关注页列表（卡片 + 报名状态 + 倒计时）

    合并官方赛事收藏与用户自定义赛事，按收藏时间倒序。
    """
    regular_items, regular_total = await _list_regular_favorites(
        db, user_id, page=page, page_size=page_size
    )
    custom_items, custom_total = await _list_custom_favorites(
        db, user_id, page=page, page_size=page_size
    )

    # 按收藏时间倒序合并
    merged = sorted(
        regular_items + custom_items,
        key=lambda x: (x.create_time or ""),
        reverse=True,
    )
    return merged, regular_total + custom_total


async def get_favorite_stats(db: AsyncSession, user_id: int) -> FavoriteStats:
    """关注页顶部统计条"""
    # 收藏总数：官方 + 自定义
    fav_cnt_q = await db.execute(
        select(func.count())
        .select_from(Favorite)
        .where(Favorite.user_id == user_id, Favorite.deleted == 0)
    )
    favorite_count = int(fav_cnt_q.scalar() or 0)

    # 已报名数：以 Registration 表为基准
    reg_q = await db.execute(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.user_id == user_id,
            Registration.registration_status == 1,
            Registration.deleted == 0,
        )
    )
    registered_count = int(reg_q.scalar() or 0)

    # 抽签中
    lottery_q = await db.execute(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.user_id == user_id,
            Registration.lottery_status == 2,
            Registration.deleted == 0,
        )
    )
    pending_lottery_count = int(lottery_q.scalar() or 0)

    return FavoriteStats(
        favorite_count=favorite_count,
        registered_count=registered_count,
        pending_lottery_count=pending_lottery_count,
    )


async def ensure_favorite(
    db: AsyncSession, user_id: int, event_id: int
) -> Favorite:
    """首次关注时建收藏 + 空壳 Registration"""
    q = await db.execute(
        select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.event_id == event_id,
        )
    )
    fav = q.scalar_one_or_none()
    if not fav:
        fav = Favorite(user_id=user_id, event_id=event_id)
        db.add(fav)
        await db.flush()
    elif fav.deleted == 1:
        fav.deleted = 0
        await db.flush()
    await _get_or_create_registration(db, user_id, event_id)
    return fav
