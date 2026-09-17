from __future__ import annotations

import sys
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# .env 绝对路径，不受工作目录影响
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # 数据库
    DB_PASSWORD: str = ""
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_NAME: str = "marathon"
    DB_USER: str = "root"

    @property
    def DATABASE_URL(self) -> str:
        # Windows 下 asyncmy 连远程 MySQL 会报 WinError 87，开发用 aiomysql；
        # Linux/Docker 部署仍走 asyncmy。
        driver = "mysql+aiomysql" if sys.platform == "win32" else "mysql+asyncmy"
        return (
            f"{driver}://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Alembic 迁移用的同步连接"""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # 微信小程序（支持多套 appid/secret，以 appid 为 key 精确匹配；默认 WECHAT_APP_* 兜底）
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""

    # 抖音 / 字节跳动小程序
    DOUYIN_APP_ID: str = ""
    DOUYIN_APP_SECRET: str = ""

    # JWT 认证
    SECRET_KEY: str = "marathon-2026-secret-key-change-in-production"
    TOKEN_EXPIRE_HOURS: int = 720  # 30 天

    # 应用
    APP_NAME: str = "Marathon Mini-Program API"
    DEBUG: bool = False

    # ===== 用户上传（头像） =====
    # 上传目录：server/uploads/avatars，前端通过 /m-uploads/avatars/xxx.png 访问
    # 前缀用 /m-uploads 而非 /uploads，避免与同服务器上 world-cup-prediction
    # 项目的静态资源路径冲突（Nginx 按前缀分发，两项目共用同一域名）。
    UPLOAD_DIR: str = str(Path(__file__).resolve().parent.parent / "uploads")
    UPLOAD_URL_PREFIX: str = "/m-uploads"
    AVATAR_MAX_MB: int = 5
    AVATAR_ALLOW_EXTS: tuple = (".jpg", ".jpeg", ".png", ".webp", ".gif")

    # ===== 数据管道（Pipeline）配置 =====
    # 人工审核总开关：True = 低置信度进入待审核队列；False = 全部自动入库（有日志留痕）
    PIPELINE_REQUIRE_REVIEW: bool = True
    # 自动入库阈值：综合置信度 ≥ 此值，即使开启审核也直接入库
    PIPELINE_CONFIDENCE_THRESHOLD: int = 75
    # 模糊匹配相似度阈值（0-100）：名称相似度 ≥ 此值 + 日期城市匹配 → 视为同一赛事
    PIPELINE_FUZZY_THRESHOLD: int = 90
    # 抓取超时
    PIPELINE_FETCH_TIMEOUT: int = 20
    # AI 兜底解析开关（没配置 LLM 时自动关掉，只用规则解析）
    PIPELINE_AI_FALLBACK: bool = False
    # LLM 接口（可选，AI 兜底用；留空则跳过 AI 解析）
    LLM_API_BASE: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"

    # ===== enrich 流水线（列表卡片 → LLM 联网补全 → mi_event）=====
    PIPELINE_ENRICH_ENABLED: bool = True
    PIPELINE_ENRICH_CRON: str = "30 6 * * *"      # 每天 06:30 北京
    ENRICH_USE_DETAIL_PAGE: bool = False           # True 时改走详情页填 enrich_json（备选）
    ENRICH_USE_WEB_GROUNDING: bool = False         # True 时喂 Bing 片段给 LLM 降 hallucination（Phase2）

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
