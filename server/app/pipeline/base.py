"""数据管道基础数据类

enrich 流水线（discover_events → LLM 补全 → mi_event）只需 EventCandidate。
旧 pipeline 的 RawPage / NormalizedEvent / MergedEvent / MergeReport / BaseSourceAdapter
已随迁移 0004 + 删旧 pipeline 一并清除。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class EventCandidate:
    """解析出的候选赛事（尚未标准化）"""
    # 基础信息
    event_name: str
    source_name: str
    source_url: str
    source_weight: int = 60

    # 原始字段（格式未统一，可能是"2026北京马拉松"这种字符串）
    start_date_raw: Optional[str] = None
    end_date_raw: Optional[str] = None
    reg_start_raw: Optional[str] = None
    reg_end_raw: Optional[str] = None
    location_raw: Optional[str] = None
    fee_raw: Optional[str] = None
    scale_raw: Optional[str] = None
    type_raw: Optional[str] = None      # 全马/半马/健康跑...
    level_raw: Optional[str] = None     # 白金标/金标...
    status_raw: Optional[str] = None    # 报名中/抽签中/...
    reg_link: Optional[str] = None
    cover_image: Optional[str] = None
    organizer: Optional[str] = None
    introduction: Optional[str] = None

    # 解析元信息
    parser_tag: str = "rule"            # rule / ai
    parse_confidence: int = 100         # 0~100
    raw_extra: dict[str, Any] = field(default_factory=dict)
