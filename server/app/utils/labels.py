"""赛事枚举 → 中文标签映射（与设计稿对齐）"""

EVENT_TYPE_LABELS = {
    1: "全程马拉松",
    2: "半程马拉松",
    3: "健康跑",
    4: "越野跑",
    5: "其他",
}

EVENT_STATUS_LABELS = {
    1: "未开始",
    2: "报名中",
    3: "报名结束",
    4: "比赛中",
    5: "已结束",
}

EVENT_LEVEL_LABELS = {
    0: "未设置",
    1: "白金标",
    2: "金标",
    3: "精英标",
    4: "标牌",
    5: "田协",
}


def event_type_label(t: int) -> str:
    return EVENT_TYPE_LABELS.get(t, "其他")


def event_status_label(s: int) -> str:
    return EVENT_STATUS_LABELS.get(s, "未开始")


def event_level_label(l: int) -> str:
    return EVENT_LEVEL_LABELS.get(l, "未设置")


# 筛选项的可选值（前端下拉/标签使用）
EVENT_TYPE_OPTIONS = [{"value": k, "label": v} for k, v in EVENT_TYPE_LABELS.items()]
EVENT_LEVEL_OPTIONS = [{"value": k, "label": v} for k, v in EVENT_LEVEL_LABELS.items()]
EVENT_STATUS_OPTIONS = [{"value": k, "label": v} for k, v in EVENT_STATUS_LABELS.items()]
