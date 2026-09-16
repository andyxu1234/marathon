"""赛事业务服务"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.favorite import Favorite
from app.models.registration import Registration
from app.schemas.event import EventBrief, EventDetail, EventFilters, EventStats
from app.schemas.common import Page
from app.utils.labels import (
    event_type_label,
    event_status_label,
    event_level_label,
    EVENT_TYPE_OPTIONS,
    EVENT_LEVEL_OPTIONS,
    EVENT_STATUS_OPTIONS,
)
from app.utils.timefmt import fmt_dt, fmt_date, month_key


def _to_brief(e: Event) -> EventBrief:
    return EventBrief(
        event_id=e.event_id,
        event_name=e.event_name,
        cover_image=e.cover_image,
        event_type=e.event_type,
        event_type_label=event_type_label(e.event_type),
        event_status=e.event_status,
        event_status_label=event_status_label(e.event_status),
        event_level=e.event_level,
        event_level_label=event_level_label(e.event_level),
        start_time=fmt_dt(e.start_time),
        start_date_label=fmt_date(e.start_time),
        location=e.location,
        province=e.province,
        city=e.city,
        registration_fee=float(e.registration_fee) if e.registration_fee is not None else None,
        is_hot=e.is_hot,
        is_recommended=e.is_recommended,
        favorite_count=e.favorite_count,
        registration_count=e.registration_count,
    )


def _to_detail(e: Event, is_favorite: bool = False) -> EventDetail:
    brief = _to_brief(e)
    return EventDetail(
        **brief.model_dump(),
        end_time=fmt_dt(e.end_time),
        registration_start_time=fmt_dt(e.registration_start_time),
        registration_end_time=fmt_dt(e.registration_end_time),
        registration_link=e.registration_link,
        registration_qr_code=e.registration_qr_code,
        address=e.address,
        introduction=e.introduction,
        description=e.description,
        route_map=e.route_map,
        registration_guide=e.registration_guide,
        refund_policy=e.refund_policy,
        contact_phone=e.contact_phone,
        contact_email=e.contact_email,
        organizer=e.organizer,
        max_participants=e.max_participants,
        current_participants=e.current_participants,
        is_favorite=is_favorite,
        items_json=e.items_json,
        certification=e.certification,
        lottery_history=e.lottery_history,
        registration_channels=e.registration_channels,
        start_point=e.start_point,
        end_point=e.end_point,
        event_year=e.event_year,
    )


def _location_eq(field, q: str):
    """
    省/市字段等值匹配 + 去掉省/市/自治区后缀的宽松匹配 OR。
    原因：
      - 前端 province-city-china 数据一般是"江苏"（matchName 去了省后缀）
      - pipeline 归一化到 Event.province 的值可能是"江苏省"或"江苏"两种
    """
    return or_(field == q, field == f"{q}省", field == f"{q}市",
               field == f"{q}自治区", field == f"{q}特别行政区")


async def list_events(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 10,
    keyword: Optional[str] = None,
    event_type: Optional[int] = None,
    event_status: Optional[int] = None,
    event_level: Optional[int] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    month: Optional[int] = None,
    event_year: Optional[int] = None,
    is_hot: Optional[bool] = None,
    is_recommended: Optional[bool] = None,
) -> Page[EventBrief]:
    """分页查询赛事列表（首页用）"""
    filters = [Event.deleted == 0]
    if keyword:
        kw = f"%{keyword}%"
        filters.append(Event.event_name.like(kw))
    if event_type:
        filters.append(Event.event_type == event_type)
    if event_status:
        filters.append(Event.event_status == event_status)
    if event_level:
        filters.append(Event.event_level == event_level)
    if province:
        filters.append(_location_eq(Event.province, province))
    if city:
        filters.append(_location_eq(Event.city, city))
    if month:
        # 按 start_time 的 YYYY-MM 过滤
        filters.append(func.extract("month", Event.start_time) == month)
    if event_year:
        # 按开始时间的年份过滤
        filters.append(func.extract("year", Event.start_time) == event_year)

    if is_hot is not None:
        filters.append(Event.is_hot == (1 if is_hot else 0))
    if is_recommended is not None:
        filters.append(Event.is_recommended == (1 if is_recommended else 0))

    where = and_(*filters)

    # 总数
    total_q = await db.execute(select(func.count()).select_from(Event).where(where))
    total = int(total_q.scalar() or 0)

    # 分页数据：推荐在前、热门其次、最近开赛
    order = (
        Event.is_recommended.desc(),
        Event.is_hot.desc(),
        Event.start_time.asc(),
    )
    rows_q = await db.execute(
        select(Event)
        .where(where)
        .order_by(*order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = rows_q.scalars().all()

    return Page[EventBrief](
        items=[_to_brief(e) for e in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_event_detail(
    db: AsyncSession,
    event_id: int,
    user_id: Optional[int] = None,
) -> Optional[EventDetail]:
    """获取赛事详情，并增量浏览量"""
    e = await db.get(Event, event_id)
    if not e or e.deleted == 1:
        return None
    # 增量浏览
    e.view_count = (e.view_count or 0) + 1
    await db.flush()

    is_fav = False
    if user_id:
        fav_q = await db.execute(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.event_id == event_id,
                Favorite.deleted == 0,
            )
        )
        is_fav = fav_q.scalar_one_or_none() is not None

    return _to_detail(e, is_favorite=is_fav)


async def get_event_stats(db: AsyncSession) -> EventStats:
    """首页统计：总数 / 报名中 / 未开始 / 已结束（event_status 语义见 Event 模型）"""
    async def _count(*extra) -> int:
        stmt = select(func.count()).select_from(Event).where(Event.deleted == 0, *extra)
        return int((await db.execute(stmt)).scalar() or 0)

    return EventStats(
        total=await _count(),
        registering=await _count(Event.event_status == 2),
        upcoming=await _count(Event.event_status == 1),
        finished=await _count(Event.event_status == 5),
    )


async def get_event_filters(db: AsyncSession) -> EventFilters:
    """获取筛选项的可选值（含从 DB distinct 出来的月份/省份）"""
    # 月份
    month_q = await db.execute(
        select(func.distinct(func.date_format(Event.start_time, "%Y-%m")))
        .where(Event.deleted == 0, Event.start_time.isnot(None))
        .order_by(func.date_format(Event.start_time, "%Y-%m"))
    )
    months = [r[0] for r in month_q if r[0]]

    # 省份
    prov_q = await db.execute(
        select(func.distinct(Event.province))
        .where(Event.deleted == 0, Event.province.isnot(None))
        .order_by(Event.province)
    )
    provinces = [r[0] for r in prov_q if r[0]]

    return EventFilters(
        types=EVENT_TYPE_OPTIONS,
        levels=EVENT_LEVEL_OPTIONS,
        statuses=EVENT_STATUS_OPTIONS,
        months=months,
        provinces=provinces,
    )


async def toggle_favorite(
    db: AsyncSession,
    user_id: int,
    event_id: int,
    *,
    favorite: bool = True,
) -> bool:
    """切换收藏状态，返回最终是否收藏

    取消关注时同步软删除 Registration 记录，保持数据一致性。
    """
    e = await db.get(Event, event_id)
    if not e or e.deleted == 1:
        return False

    fav_q = await db.execute(
        select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.event_id == event_id,
        )
    )
    fav = fav_q.scalar_one_or_none()

    if favorite:
        if not fav:
            fav = Favorite(user_id=user_id, event_id=event_id, deleted=0)
            db.add(fav)
        elif fav.deleted == 1:
            fav.deleted = 0
        else:
            return True  # 已收藏
        e.favorite_count = (e.favorite_count or 0) + 1
    else:
        if fav and fav.deleted == 0:
            fav.deleted = 1
            e.favorite_count = max(0, (e.favorite_count or 0) - 1)
            # 同步软删除 Registration 记录
            reg_q = await db.execute(
                select(Registration).where(
                    Registration.user_id == user_id,
                    Registration.event_id == event_id,
                    Registration.deleted == 0,
                )
            )
            reg = reg_q.scalar_one_or_none()
            if reg:
                reg.deleted = 1
        return False

    await db.flush()
    return True


async def create_custom_event(
    db: AsyncSession,
    *,
    event_name: str,
    event_type: int = 1,
    start_time: Optional[str] = None,
    location: Optional[str] = None,
    event_level: int = 1,
    registration_fee: Optional[float] = None,
) -> Event:
    """用户在"添加赛事"页创建一条自定义赛事（不走管理后台）"""
    e = Event(
        event_name=event_name,
        event_type=event_type,
        event_level=event_level,
        start_time=start_time,
        location=location,
        registration_fee=registration_fee,
        event_status=1,  # 未开始
        is_recommended=0,
        is_hot=0,
    )
    db.add(e)
    await db.flush()
    return e
