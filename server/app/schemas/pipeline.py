from pydantic import BaseModel


class PipelineReportOut(BaseModel):
    """enrich 流水线执行报告（返回给 API）"""
    success: bool = True
    started_at: str
    finished_at: str
    duration_seconds: float
    total_candidates: int = 0       # 列表卡片总数
    auto_inserted: int = 0          # 新增 mi_event 行数
    auto_updated: int = 0           # 更新 mi_event 行数（字段 hash 变化）
    message: str = ""
