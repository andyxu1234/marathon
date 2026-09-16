"""add enrich fields to mi_event

Revision ID: 0003_event_enrich
Revises: 0002_enrich_cols
Create Date: 2026-09-03

说明：
- mi_event 追加 enrich 流水线所需字段：
  items_json            多项目 [{type,fee,scale}]，type/fee/scale 唯一来源
  certification          田协认证规格 A类/B类/C类（与 event_level 分离）
  lottery_history        往年中签率分析文本
  registration_channels  官方报名渠道
  start_point / end_point 赛事起点/终点
  event_year             赛事年份
- event_level 语义收窄为 1白金/2金标/3精英标/4标牌（田协维度让给 certification）
- 无主项目概念：registration_fee / max_participants 不再由 enrich 流程填充
- 幂等：information_schema 检查列是否存在
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_event_enrich"
down_revision: Union[str, None] = "0002_enrich_cols"
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
    cols = [
        ("items_json", sa.JSON, "多项目[{type,fee,scale}]，type/fee/scale唯一来源"),
        ("certification", sa.String(50), "田协认证规格：A类/B类/C类"),
        ("lottery_history", sa.Text, "往年中签率分析文本"),
        ("registration_channels", sa.Text, "官方报名渠道"),
        ("start_point", sa.String(255), "赛事起点"),
        ("end_point", sa.String(255), "赛事终点"),
        ("event_year", sa.Integer, "赛事年份"),
    ]
    for name, typ, comment in cols:
        if not _column_exists(bind, "mi_event", name):
            op.add_column("mi_event", sa.Column(name, typ, nullable=True, comment=comment))


def downgrade() -> None:
    bind = op.get_bind()
    for col in ("event_year", "end_point", "start_point",
                "registration_channels", "lottery_history", "certification", "items_json"):
        if _column_exists(bind, "mi_event", col):
            op.drop_column("mi_event", col)
