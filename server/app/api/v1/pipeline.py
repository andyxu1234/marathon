"""enrich 流水线相关 API
- GET    /api/v1/pipeline/status   调度状态 + 最近 enrich 报告
- POST   /api/v1/pipeline/run      手动触发一次 enrich（每天 06:30 自动跑）
- GET    /api/v1/pipeline/sources  数据源列表（enrich 流水线当前只支持最酷）
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.pipeline.scheduler import scheduler
from app.pipeline.sources.zuicool import ZuicoolAdapter
from app.schemas.common import OkOut
from app.schemas.pipeline import PipelineReportOut

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# ============================================================
# 调度状态 + 手动触发
# ============================================================
@router.get("/status")
async def pipeline_status():
    """调度器状态 + 最近 1 次 enrich 报告 + 最近 20 次历史"""
    return scheduler.status()


@router.post("/run", response_model=PipelineReportOut)
async def pipeline_run(
    source: Optional[str] = Query(
        None, description="enrich 流水线目前只支持'最酷'，传别的会拒绝"
    ),
):
    """手动触发一次 enrich 流水线（列表卡片 → LLM 补全 → upsert mi_event）。
    会阻塞等待跑完，通常 10-60 秒（取决于新增/变化项数量）。
    """
    report = await scheduler.trigger_manual_enrich()
    return PipelineReportOut(
        success=report.success,
        started_at=report.started_at.isoformat(timespec="seconds"),
        finished_at=(report.finished_at or report.started_at).isoformat(timespec="seconds"),
        duration_seconds=report.duration_seconds,
        total_candidates=report.total_candidates,
        auto_inserted=report.auto_inserted,
        auto_updated=report.auto_updated,
        message=report.message,
    )


@router.get("/sources")
async def list_sources():
    """enrich 流水线当前支持的数据源"""
    a = ZuicoolAdapter()
    return {
        "items": [{
            "source_name": a.source_name,
            "source_weight": a.source_weight,
            "type_filter": a.EVENTS_TYPE_FILTER,
            "where_filter": a.EVENTS_WHERE_FILTER,
            "max_pages": a.EVENTS_MAX_PAGES,
            "page_size": a.EVENTS_PAGE_SIZE,
            "adapter_class": type(a).__name__,
        }],
        "total": 1,
    }


__all__ = ["OkOut"]
