"""跑者排行路由 —— 4 个 metric + 性别/年龄段筛选"""

from fastapi import APIRouter, Query

from app.deps import DBSession, OptionalUser
from app.schemas.ranking import RankingListOut
from app.services import ranking_service

router = APIRouter(prefix="/rankings", tags=["rankings"])


@router.get("", response_model=RankingListOut)
async def get_rankings(
    db: DBSession,
    current: OptionalUser = None,
    metric: str = Query(
        "distance",
        pattern="^(distance|half_marathon_pb|full_marathon_pb|spent)$",
        description="distance=总跑量 / half_marathon_pb=半马PB / full_marathon_pb=全马PB / spent=总花费",
    ),
    gender: int = Query(0, ge=0, le=2, description="0全部 1男 2女"),
    age_group: int = Query(0, ge=0, le=8, description="0全部 1<=34 ... 8>=65"),
    limit: int = Query(50, ge=1, le=200),
):
    """跑者排行（公开读；登录后额外回传 my_rank 我的排名）

    PB 类榜单只列出有完赛记录的用户；其他 metric 任何人参与排序。
    """
    return await ranking_service.list_rankings(
        db,
        metric=metric,
        gender=gender,
        age_group=age_group,
        current_user_id=current.user_id if current else None,
        limit=limit,
    )