"""APScheduler 定时调度集成（enrich 流水线专用）

旧 pipeline 的 adapter cron 任务（遍历 REGISTRY 注册）已随迁移 0004 + 删旧 pipeline 一并清除。
当前只保留 enrich 任务：每天 06:30 抓最酷列表卡片 → LLM 联网补全 → upsert mi_event。
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from app.pipeline.runner import run_enrich_pipeline, PipelineReport
from app.config import get_settings


class PipelineScheduler:
    """轻量单例封装，避免全局 scheduler 难管理"""

    def __init__(self) -> None:
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._enrich_running: bool = False
        self._last_enrich_report: Optional[PipelineReport] = None
        self._run_history: list[dict] = []

    # ---------- 生命周期 ----------
    def start(self) -> None:
        if self._scheduler and self._scheduler.running:
            logger.info("[Scheduler] 已在运行，跳过启动")
            return
        self._scheduler = AsyncIOScheduler(
            timezone="Asia/Shanghai",
            job_defaults={
                "coalesce": True,      # 错过执行时间后只补跑 1 次
                "max_instances": 1,    # 同一 job 并发数 1（防重叠）
                "misfire_grace_time": 600,
            },
        )
        self._scheduler.start()
        logger.info("[Scheduler] 已启动")

        # enrich 流水线：每天 06:30 跑一次
        settings = get_settings()
        if settings.PIPELINE_ENRICH_ENABLED:
            self._scheduler.add_job(
                self._run_enrich_safe,
                trigger=CronTrigger.from_crontab(settings.PIPELINE_ENRICH_CRON),
                id="pipeline-enrich-zuicool",
                name="增量富化-最酷",
                replace_existing=True,
            )
            logger.info(
                f"[Scheduler] 注册 enrich 任务: cron={settings.PIPELINE_ENRICH_CRON}"
            )

    def shutdown(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("[Scheduler] 已停止")

    # ---------- enrich 流水线运行入口 ----------
    async def _run_enrich_safe(self) -> PipelineReport:
        if self._enrich_running:
            logger.warning("[Scheduler] enrich 正在运行中，跳过")
            return self._last_enrich_report or PipelineReport(
                success=False, message="enrich 正在运行中")
        self._enrich_running = True
        try:
            report = await run_enrich_pipeline()
        finally:
            self._enrich_running = False
        self._last_enrich_report = report
        self._run_history.insert(0, {
            "time": datetime.now().isoformat(timespec="seconds"),
            "mode": "enrich",
            "success": report.success,
            "duration": report.duration_seconds,
            "auto_inserted": report.auto_inserted,
            "auto_updated": report.auto_updated,
            "message": report.message,
        })
        self._run_history = self._run_history[:20]
        logger.info(
            f"[Scheduler] enrich 完成: 新增 {report.auto_inserted} 更新 {report.auto_updated} "
            f"耗时 {report.duration_seconds}s"
        )
        return report

    async def trigger_manual_enrich(self) -> PipelineReport:
        """手动触发 enrich（API 调用）。"""
        if self._enrich_running:
            report = PipelineReport(success=False)
            report.message = "enrich 正在运行中，请稍后重试"
            return report
        return await self._run_enrich_safe()

    # ---------- 状态查询 ----------
    def status(self) -> dict:
        jobs = []
        if self._scheduler:
            for job in self._scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat(timespec="seconds") if job.next_run_time else None,
                })
        return {
            "enrich_running": self._enrich_running,
            "scheduler_active": bool(self._scheduler and self._scheduler.running),
            "jobs": jobs,
            "last_enrich_report": self._last_enrich_report and {
                "success": self._last_enrich_report.success,
                "started_at": self._last_enrich_report.started_at.isoformat(timespec="seconds"),
                "duration": self._last_enrich_report.duration_seconds,
                "auto_inserted": self._last_enrich_report.auto_inserted,
                "auto_updated": self._last_enrich_report.auto_updated,
                "message": self._last_enrich_report.message,
            },
            "history": self._run_history,
        }


# 全局单例
scheduler = PipelineScheduler()


@asynccontextmanager
async def pipeline_lifespan():
    """把此 lifespan 叠加到 FastAPI lifespan 中使用"""
    scheduler.start()
    try:
        yield scheduler
    finally:
        scheduler.shutdown()
