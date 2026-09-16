"""add custom event support (mi_event_customize + custom_event_id)

Revision ID: 0006_custom_event
Revises: 0005_event_display
Create Date: 2026-09-04

说明：
- 支持用户在「添加赛事」页手动创建自定义赛事
- 新建 mi_event_customize 表（用户自建赛事，仅在该用户关注页展示）
- mi_favorite 增加 custom_event_id 列（与 event_id 互斥），event_id 改为可空
  · 追加 (user_id, custom_event_id) 唯一约束
- mi_registration 增加 custom_event_id 列，event_id 改为可空（官方/自定义互斥）
  · 历史 mi_registration.event_id 全部非空，ALTER 为 nullable 不破坏现有数据
  · 旧 uk_user_event 仍保留，新增 uk_user_custom_event
- 列类型统一用 BIGINT 与 mi_user.user_id / mi_event.event_id 对齐，避免 FK 类型不匹配
- 幂等：用 information_schema 检查表/列/索引是否存在
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_custom_event"
down_revision: Union[str, None] = "0005_event_display"
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

    # 1. 创建 mi_event_customize 表（BIGINT 与 mi_user 对齐）
    if not _table_exists(bind, "mi_event_customize"):
        op.execute(
            """
            CREATE TABLE `mi_event_customize` (
              `customize_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '自定义赛事ID',
              `user_id` BIGINT NOT NULL COMMENT '用户ID',
              `event_name` VARCHAR(100) NOT NULL COMMENT '赛事名称',
              `start_time` DATETIME DEFAULT NULL COMMENT '开始时间',
              `province` VARCHAR(50) DEFAULT NULL COMMENT '省份',
              `city` VARCHAR(50) DEFAULT NULL COMMENT '城市',
              `location` VARCHAR(100) DEFAULT NULL COMMENT '地点',
              `event_level` INT DEFAULT 0 COMMENT '赛事等级 0未设置 1白金 2金标 3精英标 4标牌 5田协',
              `deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '删除标志（0存在 1删除）',
              `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
              `update_time` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
              PRIMARY KEY (`customize_id`),
              KEY `idx_customize_user` (`user_id`),
              CONSTRAINT `fk_customize_user` FOREIGN KEY (`user_id`) REFERENCES `mi_user` (`user_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户自定义赛事表'
            """
        )
        print("[0006] CREATED TABLE mi_event_customize")

    # 2. mi_favorite 增加 custom_event_id 列 + event_id 改可空 + 唯一约束
    if not _column_exists(bind, "mi_favorite", "custom_event_id"):
        op.execute(
            "ALTER TABLE `mi_favorite` "
            "ADD COLUMN `custom_event_id` BIGINT DEFAULT NULL COMMENT '自定义赛事ID（与 event_id 互斥）' "
            "AFTER `event_id`"
        )
        print("[0006] ADDED COLUMN mi_favorite.custom_event_id")

    # event_id 改为可空（model 声明 Optional，DB 当前 NOT NULL，需要放宽以支持 custom_event_id 互斥场景）
    op.execute(
        "ALTER TABLE `mi_favorite` "
        "MODIFY COLUMN `event_id` BIGINT NULL COMMENT '赛事ID（官方/自定义互斥，自定义时为 NULL）'"
    )
    print("[0006] ALTER mi_favorite.event_id -> NULLABLE")

    # FK + 唯一约束
    if not _index_exists(bind, "mi_favorite", "fk_favorite_custom_event"):
        op.execute(
            "ALTER TABLE `mi_favorite` "
            "ADD CONSTRAINT `fk_favorite_custom_event` "
            "FOREIGN KEY (`custom_event_id`) REFERENCES `mi_event_customize` (`customize_id`)"
        )

    if not _index_exists(bind, "mi_favorite", "idx_user_custom_event"):
        op.execute(
            "ALTER TABLE `mi_favorite` "
            "ADD UNIQUE KEY `idx_user_custom_event` (`user_id`, `custom_event_id`)"
        )
        print("[0006] ADDED CONSTRAINT mi_favorite.idx_user_custom_event")

    # 3. mi_registration 增加 custom_event_id 列 + event_id 改可空 + 唯一约束
    if not _column_exists(bind, "mi_registration", "custom_event_id"):
        op.execute(
            "ALTER TABLE `mi_registration` "
            "ADD COLUMN `custom_event_id` BIGINT DEFAULT NULL COMMENT '自定义赛事ID（与 event_id 互斥）' "
            "AFTER `event_id`"
        )
        print("[0006] ADDED COLUMN mi_registration.custom_event_id")

    # event_id 改为可空
    op.execute(
        "ALTER TABLE `mi_registration` "
        "MODIFY COLUMN `event_id` BIGINT NULL COMMENT '赛事ID（官方/自定义互斥，自定义时为 NULL）'"
    )
    print("[0006] ALTER mi_registration.event_id -> NULLABLE")

    if not _index_exists(bind, "mi_registration", "fk_reg_custom_event"):
        op.execute(
            "ALTER TABLE `mi_registration` "
            "ADD CONSTRAINT `fk_reg_custom_event` "
            "FOREIGN KEY (`custom_event_id`) REFERENCES `mi_event_customize` (`customize_id`)"
        )

    if not _index_exists(bind, "mi_registration", "uk_user_custom_event"):
        op.execute(
            "ALTER TABLE `mi_registration` "
            "ADD UNIQUE KEY `uk_user_custom_event` (`user_id`, `custom_event_id`)"
        )
        print("[0006] ADDED CONSTRAINT mi_registration.uk_user_custom_event")


def downgrade() -> None:
    bind = op.get_bind()

    # 恢复 mi_registration
    if _index_exists(bind, "mi_registration", "uk_user_custom_event"):
        op.execute("ALTER TABLE `mi_registration` DROP INDEX `uk_user_custom_event`")
    if _index_exists(bind, "mi_registration", "fk_reg_custom_event"):
        op.execute("ALTER TABLE `mi_registration` DROP FOREIGN KEY `fk_reg_custom_event`")
    if _column_exists(bind, "mi_registration", "custom_event_id"):
        op.execute("ALTER TABLE `mi_registration` DROP COLUMN `custom_event_id`")
    # 恢复 event_id NOT NULL（若有 NULL 用 0 兜底）
    op.execute(
        "UPDATE `mi_registration` SET `event_id` = 0 WHERE `event_id` IS NULL"
    )
    op.execute(
        "ALTER TABLE `mi_registration` "
        "MODIFY COLUMN `event_id` BIGINT NOT NULL COMMENT '赛事ID'"
    )

    # 恢复 mi_favorite
    if _index_exists(bind, "mi_favorite", "idx_user_custom_event"):
        op.execute("ALTER TABLE `mi_favorite` DROP INDEX `idx_user_custom_event`")
    if _index_exists(bind, "mi_favorite", "fk_favorite_custom_event"):
        op.execute("ALTER TABLE `mi_favorite` DROP FOREIGN KEY `fk_favorite_custom_event`")
    if _column_exists(bind, "mi_favorite", "custom_event_id"):
        op.execute("ALTER TABLE `mi_favorite` DROP COLUMN `custom_event_id`")
    op.execute(
        "UPDATE `mi_favorite` SET `event_id` = 0 WHERE `event_id` IS NULL"
    )
    op.execute(
        "ALTER TABLE `mi_favorite` "
        "MODIFY COLUMN `event_id` BIGINT NOT NULL COMMENT '赛事ID'"
    )

    # 删除 mi_event_customize
    if _table_exists(bind, "mi_event_customize"):
        op.execute("DROP TABLE `mi_event_customize`")
