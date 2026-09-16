"""add platform + app_id to mi_user

Revision ID: 0007_user_platform
Revises: 0006_custom_event
Create Date: 2026-09-08

说明：
- mi_user 原 openid 字段注释为"微信openid"，现在微信/抖音通用
- 新增 platform 字段：1=weapp 2=douyin 9=h5沙盒，默认 1（兼容历史微信用户）
- 新增 app_id 字段：登录时使用的小程序 appid，精确匹配 secret 用
- 新增复合唯一约束 uk_platform_openid(platform, openid)：
  微信 openid 只在微信内部唯一，抖音 openid 只在抖音内部唯一
- 历史数据自动填充 platform=1（都是微信用户），openid 原值保留
- 幂等：用 information_schema 检查表/列/索引是否存在
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_user_platform"
down_revision: Union[str, None] = "0006_custom_event"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(bind, table: str, col: str) -> bool:
    res = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
        ),
        {"t": table, "c": col},
    )
    return res.scalar() > 0


def _idx_exists(bind, table: str, idx: str) -> bool:
    res = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND INDEX_NAME = :i"
        ),
        {"t": table, "i": idx},
    )
    return res.scalar() > 0


def upgrade() -> None:
    bind = op.get_bind()

    # 1. 加 platform 字段
    if not _col_exists(bind, "mi_user", "platform"):
        op.add_column(
            "mi_user",
            sa.Column(
                "platform",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("1"),
                comment="登录平台：1=weapp 2=douyin 9=h5沙盒",
            ),
        )

    # 2. 加 app_id 字段
    if not _col_exists(bind, "mi_user", "app_id"):
        op.add_column(
            "mi_user",
            sa.Column(
                "app_id",
                sa.String(50),
                nullable=True,
                comment="登录时使用的小程序appid（精确匹配secret用）",
            ),
        )

    # 3. 复合唯一约束
    if not _idx_exists(bind, "mi_user", "uk_platform_openid"):
        op.create_unique_constraint(
            "uk_platform_openid",
            "mi_user",
            ["platform", "openid"],
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _idx_exists(bind, "mi_user", "uk_platform_openid"):
        op.drop_constraint("uk_platform_openid", "mi_user", type_="unique")

    if _col_exists(bind, "mi_user", "app_id"):
        op.drop_column("mi_user", "app_id")

    if _col_exists(bind, "mi_user", "platform"):
        op.drop_column("mi_user", "platform")
