from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EventCustomize(Base):
    """用户自定义赛事表 mi_event_customize

    用户在"添加赛事"页手动创建的赛事，仅在该用户的关注页展示。
    报名/缴费/中签/比赛类型/费用等状态存放在 mi_registration 中
    （通过 custom_event_id 关联）。
    """

    __tablename__ = "mi_event_customize"

    customize_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mi_user.user_id"), nullable=False, comment="用户ID"
    )
    event_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="赛事名称")
    start_time: Mapped[Optional[str]] = mapped_column(DateTime, comment="开始时间")
    province: Mapped[Optional[str]] = mapped_column(String(50), comment="省份")
    city: Mapped[Optional[str]] = mapped_column(String(50), comment="城市")
    location: Mapped[Optional[str]] = mapped_column(String(100), comment="地点")
    event_level: Mapped[int] = mapped_column(
        Integer, default=0, comment="赛事等级 0未设置 1白金 2金标 3精英标 4标牌 5田协"
    )
    deleted: Mapped[int] = mapped_column(Integer, default=0, comment="删除标志")
    create_time: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="创建时间"
    )
    update_time: Mapped[Optional[str]] = mapped_column(
        DateTime, onupdate=func.current_timestamp(), comment="更新时间"
    )
