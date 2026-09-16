"""add display column to mi_event

Revision ID: 0005_event_display
Revises: 0004_drop_legacy
Create Date: 2026-09-03

说明：
- mi_event 新增 display 列，控制 UI 展示
- 默认 1（展示），运营可手动改 0 隐藏
- server_default='1' 确保已有 255 行数据自动填充 1
- 幂等：information_schema 检查列是否存在
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_event_display"
down_revision: Union[str, None] = "0004_drop_legacy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    res = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return bool(res.scalar())


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "mi_event", "display"):
        op.add_column(
            "mi_event",
            sa.Column(
                "display",
                sa.Integer(),
                nullable=False,
                server_default="1",
                comment="是否展示（1展示 0隐藏）",
            ),
        )
        print("[0005] ADDED COLUMN mi_event.display (default=1)")


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "mi_event", "display"):
        op.drop_column("mi_event", "display")
        print("[0005] DROPPED COLUMN mi_event.display")
