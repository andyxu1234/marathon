"""关注页路由"""

from fastapi import APIRouter, Query

from app.deps import DBSession, CurrentUser
from app.schemas.common import Page
from app.schemas.favorite import FavoriteItem, FavoriteStats
from app.services import favorite_service

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=Page[FavoriteItem])
async def list_favorites(
    db: DBSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    """关注页列表（卡片 + 报名状态 + 倒计时）"""
    items, total = await favorite_service.list_favorites(
        db, user.user_id, page=page, page_size=page_size
    )
    return Page[FavoriteItem](
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/stats", response_model=FavoriteStats)
async def get_stats(db: DBSession, user: CurrentUser):
    """关注页顶部统计条"""
    return await favorite_service.get_favorite_stats(db, user.user_id)
