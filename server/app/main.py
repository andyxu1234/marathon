"""FastAPI 应用入口"""

import sys
import asyncio

# Windows 默认 ProactorEventLoop 与 aiomysql 不兼容，必须切到 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config import get_settings
from app.api import api_router
from app.database import engine, Base
from app import models  # noqa: F401  — 让 SQLAlchemy 注册所有 model
from app.pipeline.scheduler import scheduler as pipeline_scheduler


async def _auto_create_tables():
    """启动时自动建表（仅处理不存在的表，不影响已有数据）。
    跳过 Alembic 迁移，开发期快速体验用。"""
    from sqlalchemy import inspect, create_engine
    from app.config import get_settings

    # 用同步 engine 建表（异步 run_sync 访问 inspect 在不同 SQLAlchemy 版本上有差异）
    sync_url = get_settings().DATABASE_URL_SYNC
    sync_engine = create_engine(sync_url, pool_pre_ping=True)
    try:
        with sync_engine.begin() as conn:
            insp = inspect(conn)
            existing = set(insp.get_table_names())
            all_tables = Base.metadata.tables
            to_create = [tbl for name, tbl in all_tables.items() if name not in existing]
            if to_create:
                logger.info(f"[Bootstrap] 自动建表: {[t.name for t in to_create]}")
                Base.metadata.create_all(bind=conn, tables=to_create)
            else:
                logger.info("[Bootstrap] 数据库表完整，无需新建")
    finally:
        sync_engine.dispose()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：建表 → 启调度器 → 运行 → 关闭调度器"""
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME}...")

    # 1. 自动建表（新增的 source/pending 表首次启动自动创建）
    try:
        await _auto_create_tables()
    except Exception as e:
        logger.warning(f"[Bootstrap] 自动建表跳过: {e!r}")

    # 2. 配置字典 seed（mi_config 幂等补种：仅补缺失行，不覆盖已有/软删项）
    try:
        from app.database import async_session_factory
        from app.services.config_service import seed_defaults

        async with async_session_factory() as sess:
            added = await seed_defaults(sess)
            await sess.commit()
        if added:
            logger.info(f"[Bootstrap] mi_config 字典 seed 新增 {added} 行")
    except Exception as e:
        logger.warning(f"[Bootstrap] 配置字典 seed 跳过: {e!r}")

    # 3. 启动 APScheduler（数据管道定时任务）
    try:
        pipeline_scheduler.start()
    except Exception as e:
        logger.warning(f"[Bootstrap] 调度器启动失败: {e!r}")

    yield

    # 4. 优雅关闭
    pipeline_scheduler.shutdown()
    logger.info("Shutting down...")


settings = get_settings()

app = FastAPI(
    title="Marathon Mini-Program API",
    description="马拉松赛事小程序后端 API — 含多源数据采集管道",
    version="1.1.0",
    lifespan=lifespan,
)

# 注册路由
app.include_router(api_router)

# 用户上传头像静态目录（URL: /uploads/avatars/xxx.png → server/uploads/avatars/xxx.png）
# 注：先 mkdir 防止 StaticFiles(directory=...) 在目录不存在时启动失败
from pathlib import Path

Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
try:
    app.mount(
        settings.UPLOAD_URL_PREFIX,
        StaticFiles(directory=settings.UPLOAD_DIR),
        name="uploads",
    )
except RuntimeError:
    # 重复 mount（例如 reload 模式）忽略
    pass

# CORS 跨域配置（全开，开发期方便）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "1.1.0",
        "pipeline": pipeline_scheduler.status()["scheduler_active"],
    }


@app.get("/cache-stats")
async def cache_stats():
    from app.core.cache import get_cache_stats
    return get_cache_stats()


@app.get("/pipeline-status")
async def quick_pipeline_status():
    """短路径：快速查看管道状态（不需要 /api/v1 前缀）"""
    return pipeline_scheduler.status()
