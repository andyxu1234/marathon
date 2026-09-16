from typing import Optional
from pydantic import BaseModel


class EventBrief(BaseModel):
    """赛事简要 —— 首页卡片 / 关注列表用"""
    event_id: int
    event_name: str
    cover_image: Optional[str] = None
    event_type: int
    event_type_label: str
    event_status: int
    event_status_label: str
    event_level: int
    event_level_label: str
    start_time: Optional[str] = None
    start_date_label: Optional[str] = None
    location: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    registration_fee: Optional[float] = None
    is_hot: int = 0
    is_recommended: int = 0
    favorite_count: int = 0
    registration_count: int = 0


class EventDetail(EventBrief):
    """赛事详情 —— 比赛详情页"""
    end_time: Optional[str] = None
    registration_start_time: Optional[str] = None
    registration_end_time: Optional[str] = None
    registration_link: Optional[str] = None
    registration_qr_code: Optional[str] = None
    address: Optional[str] = None
    introduction: Optional[str] = None
    description: Optional[str] = None
    route_map: Optional[str] = None
    registration_guide: Optional[str] = None
    refund_policy: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    organizer: Optional[str] = None
    max_participants: int = 0
    current_participants: int = 0
    is_favorite: bool = False
    # enrich 流水线富字段（见迁移 0003）
    items_json: Optional[list] = None
    certification: Optional[str] = None
    lottery_history: Optional[str] = None
    registration_channels: Optional[str] = None
    start_point: Optional[str] = None
    end_point: Optional[str] = None
    event_year: Optional[int] = None


class EventFilters(BaseModel):
    """筛选项可选值"""
    types: list[dict] = []
    levels: list[dict] = []
    statuses: list[dict] = []
    months: list[str] = []
    provinces: list[str] = []


class EventStats(BaseModel):
    """首页数据统计（Hero 卡片）"""
    total: int = 0
    registering: int = 0
    upcoming: int = 0
    finished: int = 0
