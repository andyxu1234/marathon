from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Integer, ForeignKey, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Favorite(Base):
    """收藏表 mi_favorite

    支持两种关联：
      - event_id：官方赛事（mi_event）
      - custom_event_id：用户自定义赛事（mi_event_customize）
    二者互斥，分别通过联合唯一约束防止重复关注。
    """

    __tablename__ = "mi_favorite"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="idx_user_event"),
        UniqueConstraint("user_id", "custom_event_id", name="idx_user_custom_event"),
    )

    favorite_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("mi_user.user_id"), nullable=False, comment="用户ID")
    event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("mi_event.event_id"), nullable=True, comment="赛事ID"
    )
    custom_event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("mi_event_customize.customize_id"), nullable=True, comment="自定义赛事ID"
    )
    create_time: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="创建时间"
    )
    update_time: Mapped[Optional[str]] = mapped_column(
        DateTime, onupdate=func.current_timestamp(), comment="更新时间"
    )
    deleted: Mapped[int] = mapped_column(Integer, default=0, comment="删除标志")
