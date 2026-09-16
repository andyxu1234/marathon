from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Integer, ForeignKey, DateTime, Numeric, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Registration(Base):
    """用户报名记录表 mi_registration

    承载"关注页" 4 行状态、"我的页" 统计、"添加赛事"表单的用户字段。
    支持关联官方赛事（event_id）或自定义赛事（custom_event_id），二者互斥。

    registration_status: 0未报名 1已报名
    payment_status: 0未缴费 1已缴费
    lottery_status: 0未中签 1已中签 2抽签中
    result_status: 0未完赛 1已完赛 2PB（个人最好成绩）
    """

    __tablename__ = "mi_registration"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uk_user_event"),
        UniqueConstraint("user_id", "custom_event_id", name="uk_user_custom_event"),
    )

    registration_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("mi_user.user_id"), nullable=False, comment="用户ID")
    event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("mi_event.event_id"), nullable=True, comment="赛事ID"
    )
    custom_event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("mi_event_customize.customize_id"), nullable=True, comment="自定义赛事ID"
    )
    registration_status: Mapped[int] = mapped_column(Integer, default=0, comment="报名状态")
    payment_status: Mapped[int] = mapped_column(Integer, default=0, comment="缴费状态")
    lottery_status: Mapped[int] = mapped_column(Integer, default=0, comment="中签状态")
    race_type: Mapped[int] = mapped_column(Integer, default=0, comment="报名项目 0未设置 1全马 2半马 3健康跑")
    fee: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), default=0, comment="报名费用")
    bib_number: Mapped[Optional[str]] = mapped_column(String(20), comment="参赛号码")
    finish_time: Mapped[Optional[str]] = mapped_column(String(20), comment="完赛成绩")
    result_status: Mapped[int] = mapped_column(Integer, default=0, comment="完赛状态")
    create_time: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="创建时间"
    )
    update_time: Mapped[Optional[str]] = mapped_column(
        DateTime, onupdate=func.current_timestamp(), comment="更新时间"
    )
    deleted: Mapped[int] = mapped_column(Integer, default=0, comment="删除标志")
