from typing import Optional
from pydantic import BaseModel


class RegistrationUpdate(BaseModel):
    """更新报名状态 —— 关注页 chips 切换"""
    registration_status: Optional[int] = None  # 0未报名 1已报名
    payment_status: Optional[int] = None        # 0未缴费 1已缴费
    lottery_status: Optional[int] = None       # 0未中签 1已中签 2抽签中
    race_type: Optional[int] = None            # 0未设置 1全马 2半马 3健康跑
    fee: Optional[float] = None
    bib_number: Optional[str] = None
    finish_time: Optional[str] = None
    result_status: Optional[int] = None        # 0未完赛 1已完赛 2PB


class AddRaceRequest(BaseModel):
    """添加赛事表单

    分支：
      - event_id 有值：选择数据库已有赛事，只需提交报名状态类字段
      - 否则：创建自定义赛事，必须提供 event_name，可选比赛日期/地点/等级
    """
    event_id: Optional[int] = None                    # 数据库已有赛事 ID
    event_name: Optional[str] = None                # 自定义赛事名称
    start_time: Optional[str] = None                 # 比赛日期 YYYY-MM-DD
    province: Optional[str] = None                   # 省份
    city: Optional[str] = None                       # 城市
    location: Optional[str] = None                   # 合并展示地点（兼容旧字段）
    event_level: int = 0                             # 0未设置 1白金 2金标 3精英标 4标牌 5田协
    registration_status: int = 0                     # 0未报名 1已报名
    payment_status: int = 0                          # 0未缴费 1已缴费
    lottery_status: int = 0                          # 0未中签 1已中签 2抽签中
    race_type: int = 0                               # 0未设置 1全马 2半马 3健康跑
    fee: Optional[float] = None


class AddRaceOut(BaseModel):
    event_id: Optional[int] = None
    custom_event_id: Optional[int] = None
    favorite_id: int
    registration_id: int
