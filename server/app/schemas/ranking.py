from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class RankingItem(BaseModel):
    """榜单单条"""
    rank: int
    user_id: int
    nickname: str
    avatar: Optional[str] = None
    gender: int = 0  # 0未设置 1男 2女
    age_group: int = 0
    # 排名依据：distance→km / half_pb/full_pb→秒 / spent→元
    value: float
    value_label: str  # "421.95 km" / "3:25:18" / "¥1280"
    finished_count: int = 0
    registered_count: int = 0


class RankingListOut(BaseModel):
    """榜单响应"""
    metric: str
    gender: int
    age_group: int
    items: list[RankingItem] = []
    # 当前登录用户的"我的"视图：
    # - 在榜内：my_rank 就是 items 中的一项；my_value / my_value_label 与 my_rank 一致
    # - 不在榜但有数据：my_rank 仍给出，rank 是其在完整候选里的位次，my_insight 提示"未上榜"
    # - 无数据：my_rank=None，my_value_label="—"
    my_rank: Optional[RankingItem] = None
    my_value: Optional[float] = None
    my_value_label: Optional[str] = None
    my_insight: Optional[str] = None
    total_users: int = 0