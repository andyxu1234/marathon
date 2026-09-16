from __future__ import annotations

import ssl
import sys

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# 远程阿里云 MySQL 可要求 SSL。Windows 的 asyncio + aiomysql 自定义 SSLContext
# 在握手阶段易出 SSLWantReadError；alembic 走 pymysql 不带 SSL 也能连上，
# 说明该实例接受明文连接。故默认关闭 SSL，仅当 DB_SSL=1 时开启。
_db_ssl: ssl.SSLContext | None = None
if str(getattr(settings, "DB_SSL", "0")) == "1":
    _db_ssl = ssl.create_default_context()
    _db_ssl.check_hostname = False
    _db_ssl.verify_mode = ssl.CERT_NONE

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    # 取出连接前 SELECT 1 探活，避免复用到被回收的死连接
    pool_pre_ping=True,
    connect_args=({"ssl": _db_ssl} if _db_ssl else {}),
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取异步数据库 session"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
