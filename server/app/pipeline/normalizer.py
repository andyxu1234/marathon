"""清洗与归一化工具函数

enricher.py 复用本模块的字段归一化工具（_normalize_location / parse_date /
_map_by_keywords / _parse_fee / _parse_scale）和数据字典（TYPE_MAP / LEVEL_MAP /
STATUS_MAP / PROVINCE_ALIAS）。
旧 pipeline 的 normalize_candidate / normalize_all 入口已随删旧 pipeline 一并清除。
"""
from __future__ import annotations

import re
from datetime import datetime, date
from typing import Optional

# ============================================================
# 数据字典
# ============================================================

# 省-直辖市级别名（简化版，覆盖大部分马拉松举办地）
PROVINCE_ALIAS: dict[str, str] = {
    "北京": "北京市", "上海": "上海市", "天津": "天津市", "重庆": "重庆市",
    "广州": "广东省", "深圳": "广东省", "珠海": "广东省", "东莞": "广东省",
    "杭州": "浙江省", "宁波": "浙江省", "温州": "浙江省", "绍兴": "浙江省",
    "金华": "浙江省", "无锡": "江苏省", "南京": "江苏省", "苏州": "江苏省",
    "徐州": "江苏省", "扬州": "江苏省", "常州": "江苏省", "南通": "江苏省",
    "成都": "四川省", "武汉": "湖北省", "西安": "陕西省", "长沙": "湖南省",
    "郑州": "河南省", "济南": "山东省", "青岛": "山东省", "厦门": "福建省",
    "福州": "福建省", "大连": "辽宁省", "沈阳": "辽宁省", "哈尔滨": "黑龙江省",
    "昆明": "云南省", "贵阳": "贵州省", "合肥": "安徽省", "南昌": "江西省",
    "石家庄": "河北省", "太原": "山西省", "呼和浩特": "内蒙古自治区",
    "乌鲁木齐": "新疆维吾尔自治区", "兰州": "甘肃省", "银川": "宁夏回族自治区",
    "西宁": "青海省", "拉萨": "西藏自治区", "海口": "海南省", "三亚": "海南省",
    "南宁": "广西壮族自治区",
}

# 直辖市/单列直接 city == province
DIRECT_CITY = {"北京", "上海", "天津", "重庆"}

# 赛事类型映射
TYPE_MAP: dict[tuple[str, ...], int] = {
    ("全马", "全程", "全程马拉松", "马拉松"): 1,
    ("半马", "半程", "半程马拉松"): 2,
    ("健康跑", "欢乐跑", "迷你跑", "迷你马", "5K", "5公里", "10K", "10公里", "家庭跑"): 3,
    ("越野", "越野跑", "山地"): 4,
}

# 赛事级别映射
LEVEL_MAP: dict[tuple[str, ...], int] = {
    ("白金", "白金标", "platinum", "WMM"): 1,
    ("金标", "金"): 2,
    ("精英标", "精英"): 3,
    ("标牌", "铜标", "银标"): 4,
    ("田协", "A1", "A2", "认证"): 5,
}

# 状态映射
STATUS_MAP: dict[tuple[str, ...], int] = {
    ("报名中", "报名开启", "开放报名", "正在报名"): 2,
    ("报名结束", "报名截止", "关闭报名"): 3,
    ("比赛中", "进行中"): 4,
    ("已结束", "已完赛"): 5,
    ("抽签中", "公布抽签", "待抽签"): 2,  # 归入报名中
}

# ============================================================
# 日期解析（支持多种格式）
# ============================================================
_DATE_PATTERNS = [
    # 2026-09-20, 2026/09/20, 2026.09.20
    re.compile(r"(?P<y>20\d{2})[\-/.年](?P<m>\d{1,2})[\-/.月](?P<d>\d{1,2})"),
    # 2026年9月20日(周日)
    re.compile(r"(?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日"),
    # 09月20日 → 当年
    re.compile(r"(?P<m>\d{1,2})月(?P<d>\d{1,2})日"),
]


def parse_date(raw: Optional[str]) -> Optional[datetime]:
    """多种格式 → datetime；解析失败返回 None"""
    if not raw:
        return None
    raw = raw.strip()
    this_year = date.today().year
    for pat in _DATE_PATTERNS:
        m = pat.search(raw)
        if not m:
            continue
        try:
            y = int(m.group("y")) if "y" in m.groupdict() and m.group("y") else this_year
            mo = int(m.group("m"))
            d = int(m.group("d"))
            if not (1 <= mo <= 12 and 1 <= d <= 31):
                continue
            dt = datetime(y, mo, d, 7, 30)  # 默认早上 7:30 开赛
            # 如果只识别到 10 月 20 日这种没年份的，并且已经过了，推到明年
            if "y" not in m.groupdict() or not m.group("y"):
                if dt.date() < date.today():
                    dt = dt.replace(year=this_year + 1)
            return dt
        except (ValueError, OverflowError):
            continue
    return None


# ============================================================
# 单个字段归一化工具
# ============================================================
def _map_by_keywords(raw: Optional[str], mapping: dict[tuple[str, ...], int], default: int) -> int:
    if not raw:
        return default
    s = raw.strip().lower()
    for keywords, value in mapping.items():
        if any(kw.lower() in s for kw in keywords):
            return value
    return default


def _normalize_location(raw_loc: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """返回 (province, city, full_location_display)"""
    if not raw_loc:
        return None, None, None
    s = raw_loc.strip()
    # 去除常见后缀
    s = re.sub(r"(市|省|自治区|特别行政区)$", "", s)
    city = None
    province = PROVINCE_ALIAS.get(s)
    if s in DIRECT_CITY:
        city = s + "市"
        province = s + "市"
    elif province:
        city = s + "市"
    else:
        # 尝试包含匹配：如"杭州萧山"→杭州
        for alias, prov in PROVINCE_ALIAS.items():
            if alias in s:
                city = alias + ("" if alias in DIRECT_CITY else "市")
                province = prov
                break
    if city and not province:
        province = city
    return province, city, raw_loc


def _parse_fee(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", str(raw))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _parse_scale(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    m = re.search(r"(\d+)", str(raw))
    if not m:
        return None
    try:
        v = int(m.group(1))
        return v if 100 <= v <= 100000 else None
    except ValueError:
        return None

