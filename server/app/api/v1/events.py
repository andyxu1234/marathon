"""赛事相关路由 —— 首页 / 比赛详情页"""

from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from app.deps import DBSession, OptionalUser, CurrentUser
from app.schemas.common import Page, OkOut
from app.schemas.event import EventBrief, EventDetail, EventFilters, EventStats
from app.services import event_service

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=Page[EventBrief])
async def list_events(
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    keyword: Optional[str] = None,
    event_type: Optional[int] = Query(None, description="1全马 2半马 3健康跑 4越野跑 5其他"),
    event_status: Optional[int] = None,
    event_level: Optional[int] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    month: Optional[int] = Query(None, description="月份 1-12"),
    event_year: Optional[int] = Query(None, description="年份 如 2026"),
    is_hot: Optional[bool] = None,
    is_recommended: Optional[bool] = None,
):
    """分页查询赛事列表（首页卡片用）"""
    return await event_service.list_events(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        event_type=event_type,
        event_status=event_status,
        event_level=event_level,
        province=province,
        city=city,
        month=month,
        event_year=event_year,
        is_hot=is_hot,
        is_recommended=is_recommended,
    )


@router.get("/filters", response_model=EventFilters)
async def get_filters(db: DBSession):
    """获取筛选项可选值（类型 / 级别 / 状态 / 月份 / 省份）"""
    return await event_service.get_event_filters(db)


@router.get("/stats", response_model=EventStats)
async def get_stats(db: DBSession):
    """首页数据统计（总赛事 / 报名中 / 未开始 / 已结束）"""
    return await event_service.get_event_stats(db)


@router.get("/{event_id}", response_model=EventDetail)
async def get_event(event_id: int, db: DBSession, user: OptionalUser):
    """获取赛事详情（增量浏览），并返回当前登录态是否已收藏"""
    detail = await event_service.get_event_detail(
        db, event_id, user_id=user.user_id if user else None
    )
    if not detail:
        raise HTTPException(status_code=404, detail="赛事不存在")
    return detail


@router.post("/{event_id}/favorite", response_model=OkOut)
async def favorite_event(event_id: int, db: DBSession, user: CurrentUser):
    """收藏赛事"""
    ok = await event_service.toggle_favorite(db, user.user_id, event_id, favorite=True)
    if not ok:
        raise HTTPException(status_code=404, detail="赛事不存在")
    return OkOut(ok=True, message="已收藏")


@router.delete("/{event_id}/favorite", response_model=OkOut)
async def unfavorite_event(event_id: int, db: DBSession, user: CurrentUser):
    """取消收藏"""
    await event_service.toggle_favorite(db, user.user_id, event_id, favorite=False)
    return OkOut(ok=True, message="已取消收藏")
