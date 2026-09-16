"""add registration_fee to mi_event and create mi_registration

Revision ID: 0001_add_reg
Revises:
Create Date: 2026-08-27

说明：
- 现有库 mi_event / mi_user / mi_favorite 已存在并有数据，不由 Alembic 创建
- 本迁移只做增量：
  1) 给 mi_event 追加 registration_fee 字段（默认报名费，对应首页卡片 ¥220）
  2) 新建 mi_registration 表（用户报名追踪，承载关注页 4 行状态 + 我的页统计）
- 幂等：用 information_schema 检查列是否存在、CREATE TABLE IF NOT EXISTS，可重复执行
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_add_reg"
down_revision: Union[str, None] = None
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

    # 1) mi_event 追加 registration_fee（若不存在）
    if not _column_exists(bind, "mi_event", "registration_fee"):
        op.add_column(
            "mi_event",
            sa.Column(
                "registration_fee",
                sa.Numeric(10, 2),
                nullable=True,
                comment="默认报名费",
            ),
        )

    # 2) 新建 mi_registration（若不存在）
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `mi_registration` (
          `registration_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '报名ID',
          `user_id` BIGINT NOT NULL COMMENT '用户ID',
          `event_id` BIGINT NOT NULL COMMENT '赛事ID',
          `registration_status` TINYINT NOT NULL DEFAULT 0 COMMENT '报名状态（0未报名 1已报名）',
          `payment_status` TINYINT NOT NULL DEFAULT 0 COMMENT '缴费状态（0未缴费 1已缴费）',
          `lottery_status` TINYINT NOT NULL DEFAULT 0 COMMENT '中签状态（0未中签 1已中签 2抽签中）',
          `fee` DECIMAL(10,2) DEFAULT 0 COMMENT '报名费用',
          `bib_number` VARCHAR(20) DEFAULT NULL COMMENT '参赛号码',
          `finish_time` VARCHAR(20) DEFAULT NULL COMMENT '完赛成绩',
          `result_status` TINYINT NOT NULL DEFAULT 0 COMMENT '完赛状态（0未完赛 1已完赛 2PB）',
          `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
          `update_time` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
          `deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '删除标志（0存在 1删除）',
          PRIMARY KEY (`registration_id`),
          UNIQUE KEY `uk_user_event` (`user_id`, `event_id`),
          KEY `idx_user_id` (`user_id`),
          KEY `idx_event_id` (`event_id`),
          CONSTRAINT `fk_reg_user` FOREIGN KEY (`user_id`) REFERENCES `mi_user` (`user_id`),
          CONSTRAINT `fk_reg_event` FOREIGN KEY (`event_id`) REFERENCES `mi_event` (`event_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户报名记录表'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS `mi_registration`")
    # 谨慎起见，downgrade 不自动删 registration_fee 列（避免丢数据）
