from __future__ import annotations

from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, JSON, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EventSource(Base):
    """原始采集表 — 每条爬虫原始数据留痕，完整审计链

    match_status:
      - pending:   刚采集，尚未参与合并
      - matched:   已成功匹配到某条赛事并入库
      - conflict:  与其他来源冲突，已记录待审核
      - dropped:   无匹配/无效数据，已丢弃
    """

    __tablename__ = "mi_event_source"

    source_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="来源名称：最酷/中田协/芝华安方等")
    source_url: Mapped[str] = mapped_column(String(500), nullable=False, comment="来源页面URL")
    source_weight: Mapped[int] = mapped_column(Integer, default=60, comment="来源权威度权重 0~100")

    event_name_raw: Mapped[str] = mapped_column(String(200), comment="原始赛事名（未标准化）")
    start_date_raw: Mapped[Optional[str]] = mapped_column(String(100), comment="原始开赛日期字符串")
    location_raw: Mapped[Optional[str]] = mapped_column(String(200), comment="原始地点字符串")

    raw_html_hash: Mapped[Optional[str]] = mapped_column(
        String(64), comment="卡片字段 sha1 hash（enrich 增量检测用，原 HTML hash 列复用）"
    )

    # enrich 流水线三态 JSON + 增量 diff 键（见迁移 0002）
    zuicool_event_id: Mapped[Optional[str]] = mapped_column(String(50), comment="最酷赛事ID（/event/{id}），每日增量diff用")
    raw_json: Mapped[Optional[dict]] = mapped_column(JSON, comment="列表卡片原始抽取JSON")
    enrich_json: Mapped[Optional[dict]] = mapped_column(JSON, comment="LLM联网补全后的富化JSON")
    final_json: Mapped[Optional[dict]] = mapped_column(JSON, comment="二轮筛选后的最终JSON")

    parser_tag: Mapped[Optional[str]] = mapped_column(String(20), comment="解析方式：rule / ai")
    parse_confidence: Mapped[int] = mapped_column(Integer, default=0, comment="解析置信度 0~100")

    match_status: Mapped[str] = mapped_column(String(20), default="pending", comment="pending/matched/conflict/dropped")
    matched_event_id: Mapped[Optional[int]] = mapped_column(Integer, comment="匹配到的正式赛事ID")

    fetched_at: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="抓取时间"
    )
    create_time: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="创建时间"
    )

    __table_args__ = (
        Index("ix_source_name_fetch", "source_name", "fetched_at"),
        Index("ix_match_status", "match_status"),
        Index("ux_zuicool_source", "source_name", "zuicool_event_id", unique=True),
    )
