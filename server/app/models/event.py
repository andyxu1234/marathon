from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, Numeric, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Event(Base):
    """赛事表 mi_event —— 与现有 DB schema 对齐

    event_type: 1马拉松 2半程马拉松 3健康跑 4越野跑 5其他
    event_status: 1未开始 2报名中 3报名结束 4比赛中 5已结束
    event_level: 1白金 2金标 3精英标 4标牌 5田协 （保留 DB 世界田联标准，前端按此展示）
    """

    __tablename__ = "mi_event"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="赛事名称")
    cover_image: Mapped[Optional[str]] = mapped_column(String(255), comment="封面图片")
    event_type: Mapped[int] = mapped_column(Integer, default=1, comment="赛事类型")
    event_status: Mapped[int] = mapped_column(Integer, default=1, comment="状态")
    event_level: Mapped[int] = mapped_column(Integer, default=1, comment="赛事级别")
    start_time: Mapped[Optional[str]] = mapped_column(DateTime, comment="开始时间")
    end_time: Mapped[Optional[str]] = mapped_column(DateTime, comment="结束时间")
    registration_start_time: Mapped[Optional[str]] = mapped_column(DateTime, comment="报名开始时间")
    registration_end_time: Mapped[Optional[str]] = mapped_column(DateTime, comment="报名结束时间")
    registration_link: Mapped[Optional[str]] = mapped_column(String(255), comment="报名链接")
    registration_qr_code: Mapped[Optional[str]] = mapped_column(String(255), comment="报名二维码")
    location: Mapped[Optional[str]] = mapped_column(String(100), comment="地点")
    province: Mapped[Optional[str]] = mapped_column(String(50), comment="省份")
    city: Mapped[Optional[str]] = mapped_column(String(50), comment="城市")
    address: Mapped[Optional[str]] = mapped_column(String(255), comment="详细地址")
    introduction: Mapped[Optional[str]] = mapped_column(String(500), comment="简介")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="详情")
    route_map: Mapped[Optional[str]] = mapped_column(String(255), comment="路线图")
    registration_guide: Mapped[Optional[str]] = mapped_column(Text, comment="报名须知")
    refund_policy: Mapped[Optional[str]] = mapped_column(Text, comment="退改政策")
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), comment="联系电话")
    contact_email: Mapped[Optional[str]] = mapped_column(String(100), comment="联系邮箱")
    organizer: Mapped[Optional[str]] = mapped_column(String(100), comment="组织者")
    max_participants: Mapped[int] = mapped_column(Integer, default=0, comment="最大参与人数")
    current_participants: Mapped[int] = mapped_column(Integer, default=0, comment="当前参与人数")
    is_recommended: Mapped[int] = mapped_column(Integer, default=0, comment="是否推荐")
    is_hot: Mapped[int] = mapped_column(Integer, default=0, comment="是否热门")
    view_count: Mapped[int] = mapped_column(Integer, default=0, comment="浏览量")
    favorite_count: Mapped[int] = mapped_column(Integer, default=0, comment="收藏量")
    registration_count: Mapped[int] = mapped_column(Integer, default=0, comment="报名量")
    # 新增字段（由 Alembic 迁移添加）
    registration_fee: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2), default=None, comment="默认报名费"
    )
    # enrich 流水线字段（见迁移 0003）
    items_json: Mapped[Optional[list]] = mapped_column(JSON, comment="多项目[{type,fee,scale}]，type/fee/scale唯一来源")
    certification: Mapped[Optional[str]] = mapped_column(String(50), comment="田协认证规格：A类/B类/C类")
    lottery_history: Mapped[Optional[str]] = mapped_column(Text, comment="往年中签率分析文本")
    registration_channels: Mapped[Optional[str]] = mapped_column(Text, comment="官方报名渠道")
    start_point: Mapped[Optional[str]] = mapped_column(String(255), comment="赛事起点")
    end_point: Mapped[Optional[str]] = mapped_column(String(255), comment="赛事终点")
    event_year: Mapped[Optional[int]] = mapped_column(Integer, comment="赛事年份")
    create_by: Mapped[Optional[str]] = mapped_column(String(50), comment="创建者")
    create_time: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="创建时间"
    )
    update_by: Mapped[Optional[str]] = mapped_column(String(50), comment="更新者")
    update_time: Mapped[Optional[str]] = mapped_column(
        DateTime, onupdate=func.current_timestamp(), comment="更新时间"
    )
    remark: Mapped[Optional[str]] = mapped_column(String(500), comment="备注")
    deleted: Mapped[int] = mapped_column(Integer, default=0, comment="删除标志")
    display: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", comment="是否展示（1展示 0隐藏）"
    )
