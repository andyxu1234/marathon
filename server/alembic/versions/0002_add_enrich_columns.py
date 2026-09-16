"""add enrich columns to mi_event_source

Revision ID: 0002_enrich_cols
Revises: 0001_add_reg
Create Date: 2026-09-03

说明：
- mi_event_source 追加 enrich 流水线所需的三态 JSON + zuicool_event_id
- raw_json      列表卡片直接抽取（无 LLM）
- enrich_json   LLM 联网补全后的富化 JSON
- final_json    二轮筛选后的最终 JSON（暂同 enrich_json）
- zuicool_event_id  最酷赛事 ID，每日增量 diff 用
- 保留旧 raw_payload 列不动（旧 run_pipeline 仍写它）
- 幂等：用 information_schema 检查列/索引是否存在
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_enrich_cols"
down_revision: Union[str, None] = "0001_add_reg"
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


def _index_exists(bind, table: str, index: str) -> bool:
    res = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = :t AND index_name = :i"
        ),
        {"t": table, "i": index},
    )
    return bool(res.scalar())


def upgrade() -> None:
    bind = op.get_bind()

    if not _column_exists(bind, "mi_event_source", "zuicool_event_id"):
        op.add_column(
            "mi_event_source",
            sa.Column("zuicool_event_id", sa.String(50), nullable=True,
                      comment="最酷赛事ID（/event/{id}），每日增量diff用"),
        )
    if not _column_exists(bind, "mi_event_source", "raw_json"):
        op.add_column(
            "mi_event_source",
            sa.Column("raw_json", sa.JSON, nullable=True, comment="列表卡片原始抽取JSON"),
        )
    if not _column_exists(bind, "mi_event_source", "enrich_json"):
        op.add_column(
            "mi_event_source",
            sa.Column("enrich_json", sa.JSON, nullable=True, comment="LLM联网补全后的富化JSON"),
        )
    if not _column_exists(bind, "mi_event_source", "final_json"):
        op.add_column(
            "mi_event_source",
            sa.Column("final_json", sa.JSON, nullable=True, comment="二轮筛选后的最终JSON"),
        )

    if not _index_exists(bind, "mi_event_source", "ux_zuicool_source"):
        op.create_index(
            "ux_zuicool_source", "mi_event_source",
            ["source_name", "zuicool_event_id"], unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, "mi_event_source", "ux_zuicool_source"):
        op.drop_index("ux_zuicool_source", table_name="mi_event_source")
    for col in ("final_json", "enrich_json", "raw_json", "zuicool_event_id"):
        if _column_exists(bind, "mi_event_source", col):
            op.drop_column("mi_event_source", col)
