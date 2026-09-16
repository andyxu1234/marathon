"""drop legacy pipeline schema

Revision ID: 0004_drop_legacy
Revises: 0003_add_event_enrich_fields
Create Date: 2026-09-03

说明：
- 删除旧 pipeline（parser+normalizer+dedupe+run_pipeline）遗留的 schema
- DROP TABLE mi_event_pending（enrich 流水线无"待审核"分流概念，所有数据直接落 mi_event）
- DROP COLUMN mi_event_source.raw_payload（旧 pipeline 字段快照列，enrich 用 raw_json 三态 JSON 替代）
- mi_event 表字段全保留：registration_fee / max_participants / address / description / route_map /
  registration_qr_code / registration_guide / refund_policy / current_participants / is_recommended /
  is_hot / view_count / favorite_count / registration_count / remark 等是小程序展示/运营手工字段，
  enrich 流水线不写但也不删，避免破坏小程序代码
- 幂等：用 information_schema 检查表/列是否存在
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_drop_legacy"
down_revision: Union[str, None] = "0003_event_enrich"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table: str) -> bool:
    res = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = :t"
        ),
        {"t": table},
    )
    return bool(res.scalar())


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

    # 1. DROP TABLE mi_event_pending（整表）
    if _table_exists(bind, "mi_event_pending"):
        op.drop_table("mi_event_pending")
        print("[0004] DROPPED TABLE mi_event_pending")

    # 2. DROP COLUMN mi_event_source.raw_payload
    if _column_exists(bind, "mi_event_source", "raw_payload"):
        op.drop_column("mi_event_source", "raw_payload")
        print("[0004] DROPPED COLUMN mi_event_source.raw_payload")


def downgrade() -> None:
    bind = op.get_bind()

    # 恢复 raw_payload 列（数据无法恢复，仅恢复 schema）
    if not _column_exists(bind, "mi_event_source", "raw_payload"):
        op.add_column(
            "mi_event_source",
            sa.Column("raw_payload", sa.JSON, nullable=True,
                      comment="原始字段快照（旧 pipeline 用，已废弃）"),
        )

    # 恢复 mi_event_pending 表（仅 schema，无数据）
    if not _table_exists(bind, "mi_event_pending"):
        op.create_table(
            "mi_event_pending",
            sa.Column("pending_id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("merge_type", sa.String(20), nullable=False, server_default="new"),
            sa.Column("confidence_score", sa.Integer, server_default="0"),
            sa.Column("event_name", sa.String(100), nullable=False),
            sa.Column("cover_image", sa.String(255)),
            sa.Column("event_type", sa.Integer, server_default="1"),
            sa.Column("event_status", sa.Integer, server_default="1"),
            sa.Column("event_level", sa.Integer, server_default="5"),
            sa.Column("start_time", sa.DateTime),
            sa.Column("end_time", sa.DateTime),
            sa.Column("registration_start_time", sa.DateTime),
            sa.Column("registration_end_time", sa.DateTime),
            sa.Column("registration_link", sa.String(255)),
            sa.Column("registration_fee", sa.Numeric(10, 2)),
            sa.Column("location", sa.String(100)),
            sa.Column("province", sa.String(50)),
            sa.Column("city", sa.String(50)),
            sa.Column("address", sa.String(255)),
            sa.Column("introduction", sa.String(500)),
            sa.Column("organizer", sa.String(100)),
            sa.Column("max_participants", sa.Integer, server_default="0"),
            sa.Column("conflict_details", sa.JSON),
            sa.Column("source_ids", sa.JSON),
            sa.Column("reviewed_status", sa.String(20), server_default="pending"),
            sa.Column("reviewed_by", sa.String(50)),
            sa.Column("reviewed_at", sa.DateTime),
            sa.Column("review_note", sa.String(500)),
            sa.Column("create_time", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("update_time", sa.DateTime, onupdate=sa.text("CURRENT_TIMESTAMP")),
        )
