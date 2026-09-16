from typing import Optional
from pydantic import BaseModel


class RegistrationBrief(BaseModel):
    """报名追踪简要 —— 嵌入关注卡片"""
    registration_status: int = 0  # 0未报名 1已报名
    payment_status: int = 0      # 0未缴费 1已缴费
    lottery_status: int = 0      # 0未中签 1已中签 2抽签中
    race_type: int = 0           # 0未设置 1全马 2半马 3健康跑
    fee: Optional[float] = None
    bib_number: Optional[str] = None
    finish_time: Optional[str] = None
    result_status: int = 0       # 0未完赛 1已完赛 2PB


class FavoriteItem(BaseModel):
    """关注页卡片 = 赛事简要 + 报名状态 + 倒计时"""
    event_id: Optional[int] = None
    custom_event_id: Optional[int] = None
    is_custom: bool = False
    event_name: str
    event_type: int
    event_type_label: str
    event_level: int
    event_level_label: str
    event_status: int = 1                  # 1未开始 2报名中 3报名结束 4比赛中 5已结束
    event_status_label: str = "未开始"
    start_time: Optional[str] = None
    start_date_label: Optional[str] = None
    location: Optional[str] = None
    cover_image: Optional[str] = None
    registration_fee: Optional[float] = None
    registration: RegistrationBrief = RegistrationBrief()
    days_to_race: Optional[int] = None
    create_time: Optional[str] = None  # 用于服务端排序，前端可不展示


class FavoriteStats(BaseModel):
    """关注页统计条"""
    favorite_count: int = 0
    registered_count: int = 0
    pending_lottery_count: int = 0
