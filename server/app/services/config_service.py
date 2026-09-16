"""配置字典 service —— mi_config 查询 + 幂等 seed

seed 原则（见 seed_defaults 注释）：
  · 只补缺失行，绝不覆盖已有（用户改过 config_name 的重启不会被还原）
  · 软删（deleted=1）过的键视为"已存在"，不会复活重插
"""

from typing import Optional

from sqlalchemy import select

from app.models.config import Config
from app.schemas.config import ConfigItem

# 预置字典：config_type -> [(config_code, config_name, sort_order)]
# name 与各业务 model 注释 / 前端常量逐字对齐（改这里只影响"首次建库后新装环境"）。
SEED_CONFIGS: dict[str, list[tuple[str, str, int]]] = {
    "gender": [
        ("0", "未设置", 0),
        ("1", "男", 1),
        ("2", "女", 2),
    ],
    "age_group": [
        ("0", "未设置", 0),
        ("1", "34岁以下", 1),
        ("2", "35-39岁", 2),
        ("3", "40-44岁", 3),
        ("4", "45-49岁", 4),
        ("5", "50-54岁", 5),
        ("6", "55-59岁", 6),
        ("7", "60-64岁", 7),
        ("8", "65岁以上", 8),
    ],
    "reg_status": [
        ("0", "未报名", 0),
        ("1", "已报名", 1),
    ],
    "pay_status": [
        ("0", "未缴费", 0),
        ("1", "已缴费", 1),
    ],
    "lottery_status": [
        ("0", "未中签", 0),
        ("1", "已中签", 1),
        ("2", "抽签中", 2),
    ],
    "result_status": [
        ("0", "未完赛", 0),
        ("1", "已完赛", 1),
        ("2", "PB", 2),
    ],
    "event_type": [
        ("1", "马拉松", 1),
        ("2", "半程马拉松", 2),
        ("3", "健康跑", 3),
        ("4", "越野跑", 4),
        ("5", "其他", 5),
    ],
    "event_status": [
        ("1", "未开始", 1),
        ("2", "报名中", 2),
        ("3", "报名结束", 3),
        ("4", "比赛中", 4),
        ("5", "已结束", 5),
    ],
    "event_level": [
        ("1", "白金", 1),
        ("2", "金标", 2),
        ("3", "精英标", 3),
        ("4", "标牌", 4),
        ("5", "田协", 5),
    ],
}

# 白名单校验：config_type 不在其中时 list_by_type 直接返回空（防止拼非法 type 打 DB）
KNOWN_TYPES: set[str] = set(SEED_CONFIGS.keys())


def _to_item(c: Config) -> ConfigItem:
    return ConfigItem(
        code=c.config_code,
        name=c.config_name,
        sort_order=c.sort_order,
        remark=c.remark,
    )


async def list_by_type(db, config_type: str) -> list[ConfigItem]:
    """单类别启用字典项（未登录可访问；未知 type 返回空列表）"""
    if config_type not in KNOWN_TYPES:
        return []
    stmt = (
        select(Config)
        .where(
            Config.config_type == config_type,
            Config.status == 1,
            Config.deleted == 0,
        )
        .order_by(Config.sort_order.asc(), Config.config_id.asc())
    )
    res = await db.execute(stmt)
    rows = list(res.scalars().all())
    return [_to_item(r) for r in rows]


async def list_all_groups(db) -> dict[str, list[ConfigItem]]:
    """全量启用字典：{config_type: [items]}，前端可一次拉齐缓存"""
    stmt = (
        select(Config)
        .where(Config.status == 1, Config.deleted == 0)
        .order_by(Config.sort_order.asc(), Config.config_id.asc())
    )
    res = await db.execute(stmt)
    grouped: dict[str, list[ConfigItem]] = {}
    for row in res.scalars().all():
        grouped.setdefault(row.config_type, []).append(_to_item(row))
    return grouped


async def seed_defaults(db) -> int:
    """幂等补种缺失字典行。

    存在性判定包含软删行：只要 (config_type, config_code) 在库里出现过就不再插，
    保证：
      1. 用户改过的 config_name 不会被还原（只 INSERT 不 UPDATE）
      2. 用户软删的选项不会在下次启动时"复活"
    返回本次新增行数。
    """
    res = await db.execute(select(Config.config_type, Config.config_code))
    existing = {(t, c) for t, c in res.all()}

    to_add: list[Config] = []
    for ctype, items in SEED_CONFIGS.items():
        for code, name, sort_order in items:
            if (ctype, code) in existing:
                continue
            to_add.append(
                Config(
                    config_type=ctype,
                    config_code=code,
                    config_name=name,
                    sort_order=sort_order,
                    remark=f"seed: {ctype}",
                )
            )

    if to_add:
        db.add_all(to_add)
        await db.flush()
    return len(to_add)
