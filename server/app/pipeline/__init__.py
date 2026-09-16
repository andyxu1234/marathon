"""马拉松赛事数据 enrich 流水线

列表卡片抓取 → LLM 联网补全 → 三态 JSON 存储 → upsert mi_event
（旧 run_pipeline 已随迁移 0004 + 删旧 pipeline 一并清除）
"""
from app.pipeline.runner import run_enrich_pipeline, PipelineReport

__all__ = ["run_enrich_pipeline", "PipelineReport"]
