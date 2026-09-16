"""Alembic env.py — 同步迁移配置"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.database import Base
from app.config import get_settings

# 导入所有模型，确保 Base.metadata 包含所有表
from app.models import Event, User, Favorite, Registration  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 使用 .env 中的同步数据库 URL
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：使用同步引擎"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
