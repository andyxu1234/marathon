"""Pipeline Runner — enrich 流水线主入口

旧 run_pipeline（采集 → 解析 → 归一化 → 去重 → 分流入库）已随迁移 0004 + 删旧 pipeline
一并清除。当前 runner.py 只保留 run_enrich_pipeline + PipelineReport。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_factory
from app.models.event import Event
from app.models.event_source import EventSource
from app.pipeline.sources.zuicool import ZuicoolAdapter


@dataclass
class PipelineReport:
    success: bool = True
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    sources: list[dict] = field(default_factory=list)
    total_raw_pages: int = 0
    total_candidates: int = 0
    total_normalized: int = 0
    dedup_groups: int = 0
    merged_events: int = 0
    auto_inserted: int = 0
    auto_updated: int = 0
    pending_review: int = 0
    duplicates_skipped: int = 0
    conflict_fields: list[dict] = field(default_factory=list)
    require_review: bool = True
    message: str = ""


# ============================================================
# ENRICH 流水线 — 列表卡片 → LLM 联网补全 → mi_event
# ============================================================
async def _load_existing_zuicool_state(db: AsyncSession) -> dict[str, dict]:
    """一次 SELECT 拿已存最酷 source 行的 {zuicool_event_id: {source_id, fields_hash}}。
    fields_hash 即 raw_html_hash 列（enricher.persist_to_source 写入的卡片字段 sha1），
    用于方案 B 增量：对比今日抓回的卡片 hash，不一致 → 重新 enrich + update mi_event。
    """
    q = await db.execute(
        select(
            EventSource.zuicool_event_id,
            EventSource.source_id,
            EventSource.raw_html_hash,
        )
        .where(EventSource.source_name == "最酷")
        .where(EventSource.zuicool_event_id.is_not(None))
    )
    return {
        row[0]: {"source_id": row[1], "fields_hash": row[2] or ""}
        for row in q if row[0]
    }


async def run_enrich_pipeline(source_filter: Optional[str] = None) -> PipelineReport:
    """enrich 流水线主入口：
    1) discover_events(min_date=today) 抓列表卡片全量（仅未来日期）
    2) 与 DB 已存 zuicool_event_id diff（方案 B：新增 + 字段 hash 变化检测）
    3) 对每个新增/变化：build_raw_json → enrich_with_llm → filter_enriched →
       persist_to_source(upsert) → sync_to_event(upsert mi_event)
    """
    from app.pipeline import enricher

    settings = get_settings()
    report = PipelineReport()
    report.require_review = False
    t0 = datetime.now()
    try:
        if not settings.LLM_API_KEY:
            raise RuntimeError("LLM_API_KEY 未配置，enrich 流程无法运行")

        # enrich 流水线目前只支持最酷，source_filter 仅做兼容校验
        if source_filter and source_filter != "最酷":
            report.message = f"enrich 流水线不支持数据源 {source_filter}（仅最酷）"
            report.success = False
            return report
        zuicool = ZuicoolAdapter()

        # ============= Step 1: discover_events（列表卡片全量，仅未来日期）=============
        # min_date=today：最酷列表按比赛日期倒序，第 N 页全部过期时会提前 break
        discovered = await zuicool.discover_events(
            timeout=settings.PIPELINE_FETCH_TIMEOUT,
            min_date=date.today(),
        )
        report.total_candidates = len(discovered)
        logger.info(f"[Enrich] discover_events 返回 {len(discovered)} 条（min_date={date.today()}）")

        async with async_session_factory() as db:
            # ============= Step 2: diff（方案 B：新增 + 字段 hash 变化检测）=============
            # existing_state: {zuicool_event_id: {source_id, fields_hash}}
            existing_state = await _load_existing_zuicool_state(db)
            new_items: list[dict] = []
            changed_items: list[dict] = []
            skipped_unchanged = 0
            for d in discovered:
                eid = d.get("event_id")
                if not eid:
                    continue
                candidate = d.get("candidate")
                if candidate is None:
                    continue
                # 算今日抓回卡片的 hash
                today_raw = enricher.build_raw_json(candidate)
                today_hash = enricher.compute_fields_hash(today_raw)
                st = existing_state.get(eid)
                if st is None:
                    # 新赛事
                    new_items.append(d)
                elif (st.get("fields_hash") or "") != today_hash:
                    # 字段变化（status/reg_end/start_date 等变了）→ 重新 enrich + update
                    d["_today_raw"] = today_raw   # 避免下面重复 build_raw_json
                    changed_items.append(d)
                else:
                    skipped_unchanged += 1
            report.total_raw_pages = len(new_items) + len(changed_items)
            logger.info(
                f"[Enrich] diff: 已存 {len(existing_state)}，"
                f"新增 {len(new_items)}，字段变化 {len(changed_items)}，"
                f"无变化跳过 {skipped_unchanged}"
            )

            ins = upd = 0
            # 处理顺序：先新增，再变化（同一 DB session，flush 后再处理变化项避免唯一索引冲突）
            for item in new_items + changed_items:
                eid = item["event_id"]
                # 变化项已预 build_raw_json，复用；新项现场 build
                raw_json = item.pop("_today_raw", None) or enricher.build_raw_json(item["candidate"])
                try:
                    # ============= Step 4: enrich_with_llm =============
                    enrich_json = await enricher.enrich_with_llm(
                        raw_json,
                        llm_api_base=settings.LLM_API_BASE,
                        llm_api_key=settings.LLM_API_KEY,
                        llm_model=settings.LLM_MODEL,
                    )
                    # ============= Step 5: filter_enriched =============
                    final_json, conf = enricher.filter_enriched(enrich_json)
                    # ============= Step 6: persist_to_source（upsert 语义）=============
                    source_id = await enricher.persist_to_source(
                        db,
                        source_name=zuicool.source_name,
                        source_url=item.get("url") or item["candidate"].source_url,
                        source_weight=zuicool.source_weight,
                        zuicool_event_id=eid,
                        raw_json=raw_json,
                        enrich_json=enrich_json,
                        final_json=final_json,
                        parse_confidence=conf,
                    )
                    # ============= Step 7: sync_to_event =============
                    event_id = await enricher.sync_to_event(db, source_id, final_json)
                    if event_id is not None:
                        # 区分新增/变化：是否在 existing_state 里
                        if eid in existing_state:
                            upd += 1
                        else:
                            ins += 1
                except Exception as e:
                    logger.warning(f"[Enrich] event_id={eid} {item.get('name')} 失败: {e!r}")
                    continue

            report.auto_inserted = ins
            report.auto_updated = upd
            await db.commit()
            report.message = (
                f"enrich 完成：列表 {len(discovered)} 条，已存 {len(existing_state)}，"
                f"新增 {len(new_items)} 条，字段变化 {len(changed_items)} 条，"
                f"落 mi_event insert {ins} / update {upd}"
            )
    except Exception as e:
        logger.exception(f"[Enrich] enrich pipeline 异常: {e!r}")
        report.success = False
        report.message = f"enrich 执行异常: {e!r}"
    finally:
        report.finished_at = datetime.now()
        report.duration_seconds = round((datetime.now() - t0).total_seconds(), 2)

    return report
