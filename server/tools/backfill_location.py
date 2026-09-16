"""按空格拆分 location 回填 mi_event.province / city / address

约定（与已成功解析样本对齐）：
- 4 段: [省份] [城市] [区/县] [详细地址]
- 3 段: [省份] [城市] [详细地址]
- 2 段: [省份] [城市]
- 1 段 / 含 "不限/待定/未知": 跳过
- 海外省份名（马来西亚/新加坡/日本/...）: 跳过

省份短名 → 全称映射（与现有库中已成功解析的值完全一致）：
- 北京/上海/天津/重庆 → 北京市/上海市/天津市/重庆市，city 取短名（北京/上海/...）
- 内蒙古/新疆/宁夏/广西/西藏 → xxx自治区
- 其他 → xxx省

用法：
    python tools/backfill_location.py            # 预览（dry-run）
    python tools/backfill_location.py --apply   # 真正写库
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import get_settings

import pymysql

# ===== 省份短名 → 库内已存全称 =====
PROVINCE_MAP = {
    # 直辖市
    '北京': '北京市', '上海': '上海市', '天津': '天津市', '重庆': '重庆市',
    # 省
    '河北': '河北省', '山西': '山西省', '辽宁': '辽宁省', '吉林': '吉林省',
    '黑龙江': '黑龙江省', '江苏': '江苏省', '浙江': '浙江省', '安徽': '安徽省',
    '福建': '福建省', '江西': '江西省', '山东': '山东省', '河南': '河南省',
    '湖北': '湖北省', '湖南': '湖南省', '广东': '广东省', '海南': '海南省',
    '四川': '四川省', '贵州': '贵州省', '云南': '云南省', '陕西': '陕西省',
    '甘肃': '甘肃省', '青海': '青海省', '台湾': '台湾省',
    # 自治区
    '内蒙古': '内蒙古自治区', '广西': '广西壮族自治区', '西藏': '西藏自治区',
    '宁夏': '宁夏回族自治区', '新疆': '新疆维吾尔自治区',
    # 特别行政区
    '香港': '香港特别行政区', '澳门': '澳门特别行政区',
}

# 直辖市的 city 短名（库内既有数据的约定：province=北京市, city=北京）
MUNICIPALITY_SHORT = {'北京': '北京', '上海': '上海', '天津': '天津', '重庆': '重庆'}

# 海外/港澳台非大陆省级行政（按用户口径跳过）
FOREIGN_PREFIXES = ('马来西亚', '新加坡', '日本', '韩国', '泰国', '越南',
                    '美国', '加拿大', '英国', '法国', '德国', '意大利',
                    '澳大利亚', '中国香港', '中国澳门', '中国台湾')

NO_INFO_KEYWORDS = ('不限地点', '不限', '待定', '未知', 'TBD', 'tbd')

# 已经是带后缀的省份名（"湖南省"/"新疆维吾尔自治区"），不要再加省份后缀
HAS_SUFFIX_PATTERN = re.compile(
    r'(省|自治区|特别行政区|生产建设兵团)$'
)


def parse_location(loc: str) -> tuple[str | None, str | None, str | None]:
    """返回 (province, city, address)；任一字段无法解析则对应返回 None"""
    if not loc:
        return None, None, None

    s = loc.strip()

    # 跳过无具体地点
    if any(kw in s for kw in NO_INFO_KEYWORDS):
        return None, None, None

    # 跳过海外
    if any(s.startswith(pre) for pre in FOREIGN_PREFIXES):
        return None, None, None

    parts = s.split()
    if len(parts) < 2:
        return None, None, None

    p1, p2 = parts[0], parts[1]

    # ---- province ----
    if p1 in PROVINCE_MAP:
        province = PROVINCE_MAP[p1]
    elif HAS_SUFFIX_PATTERN.search(p1):
        province = p1  # 已是全称（防御性兜底）
    else:
        # 不认识的省份前缀 → 安全起见跳过
        return None, None, None

    # ---- city ----
    if p1 in MUNICIPALITY_SHORT:
        # 直辖市：city 用短名（库内约定）
        city = MUNICIPALITY_SHORT[p1]
    else:
        city = p2  # 一般省份：原样保留（含 市/自治州/地区 等）

    # ---- address ----
    if len(parts) >= 4:
        address = ' '.join(parts[2:])
    elif len(parts) == 3:
        address = parts[2]
    else:
        address = None

    return province, city, address


def main():
    parser = argparse.ArgumentParser(description='回填 mi_event 的 province/city/address')
    parser.add_argument('--apply', action='store_true', help='真正写库（默认仅预览）')
    parser.add_argument('--limit', type=int, default=0, help='只处理前 N 行（默认全部）')
    args = parser.parse_args()

    settings = get_settings()
    conn = pymysql.connect(
        host=settings.DB_HOST, port=settings.DB_PORT,
        user=settings.DB_USER, password=settings.DB_PASSWORD,
        database=settings.DB_NAME, charset='utf8mb4',
    )

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT event_id, location FROM mi_event
                WHERE (province IS NULL OR province = '')
                  AND (city IS NULL OR city = '')
                  AND location IS NOT NULL AND location != ''
                ORDER BY event_id
            """)
            rows = cur.fetchall()

        if args.limit:
            rows = rows[: args.limit]

        updates = []  # (event_id, province, city, address, original_location)
        skips = []    # (event_id, location, reason)

        for event_id, loc in rows:
            province, city, address = parse_location(loc)
            if province is None and city is None:
                skips.append((event_id, loc, '无法解析（海外/无地点/省份未识别）'))
                continue
            updates.append((event_id, province, city, address, loc))

        print(f"扫描 {len(rows)} 行，可解析 {len(updates)} 行，跳过 {len(skips)} 行\n")

        print("== 待更新预览（前 20 条）==")
        for eid, p, c, a, loc in updates[:20]:
            addr_repr = a if a else '(空)'
            print(f"  [{eid:>4}] {loc}")
            print(f"        → province={p!r}  city={c!r}  address={addr_repr!r}")
        if len(updates) > 20:
            print(f"  ... 还有 {len(updates) - 20} 条\n")

        if skips:
            print("\n== 跳过的行 ==")
            for eid, loc, reason in skips:
                print(f"  [{eid:>4}] {loc!r}  —— {reason}")

        if not args.apply:
            print("\n[DRY-RUN] 未写库。带上 --apply 真正执行更新。")
            return

        # 真正写库
        print("\n[APPLY] 写入数据库...")
        with conn.cursor() as cur:
            sql = (
                "UPDATE mi_event "
                "SET province=%s, city=%s, address=COALESCE(address, %s) "
                "WHERE event_id=%s "
                "  AND (province IS NULL OR province = '') "
                "  AND (city IS NULL OR city = '')"
            )
            affected = 0
            for event_id, province, city, address, _loc in updates:
                cur.execute(sql, (province, city, address, event_id))
                affected += cur.rowcount
            conn.commit()
            print(f"  实际更新行数: {affected}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()