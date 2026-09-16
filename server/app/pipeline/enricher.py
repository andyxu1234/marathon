"""enrich 流水线 — 列表卡片 raw_json → LLM 联网补全 enrich_json → 筛选 final_json → 落库

复用：
- LLM HTTP+payload 模式来自 parser._ai_parse_page（parser.py:108-131）
- 地点/日期/费用/规模/枚举工具来自 normalizer（_normalize_location/parse_date/_parse_fee/_parse_scale/_map_by_keywords + TYPE_MAP/LEVEL_MAP/STATUS_MAP）

无主项目概念：赛事类型/报名费/规模全部只存 mi_event.items_json。
"""
from __future__ import annotations

import json
from datetime import datetime, date, timedelta
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy import select, or_, null
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Event, EventSource
from app.pipeline.base import EventCandidate
from app.pipeline.normalizer import (
    _normalize_location, parse_date, _parse_fee, _parse_scale,
    _map_by_keywords, TYPE_MAP, LEVEL_MAP, STATUS_MAP,
)


# ============================================================
# Step A: EventCandidate → raw_json（纯 reshape，无 I/O）
# ============================================================
def build_raw_json(candidate: EventCandidate) -> dict:
    """把 parse_event_list 产出的 EventCandidate 转成 raw_json（存 mi_event_source.raw_json）。
    只搬字段，不调 LLM、不连网。"""
    return {
        "zuicool_event_id": (candidate.raw_extra or {}).get("event_id"),
        "event_name": candidate.event_name,
        "source_url": candidate.source_url,
        "start_date_raw": candidate.start_date_raw,
        "location_raw": candidate.location_raw,
        "reg_start_raw": candidate.reg_start_raw,
        "reg_end_raw": candidate.reg_end_raw,
        "status_raw": candidate.status_raw,         # 卡片按钮文本：点此报名/即将报名/已截止
        "reg_link": candidate.reg_link,
        "type_raw": candidate.type_raw,             # 卡片从名称猜的单类型
        "cover_image": candidate.cover_image,
        "parser_tag": candidate.parser_tag,
        "parse_confidence": candidate.parse_confidence,
    }


# 增量 hash：只对真正影响业务的关键卡片字段算 hash，cover_image/parse_confidence 不参与
_FIELDS_HASH_KEYS = (
    "event_name", "start_date_raw", "location_raw",
    "reg_start_raw", "reg_end_raw", "status_raw", "type_raw",
)


def compute_fields_hash(raw_json: dict) -> str:
    """对关键卡片字段算 sha1 hash（用于判断已存赛事是否有字段更新）。
    只关心会影响 enrich 结果的字段，cover_image 等不计。"""
    import hashlib
    fingerprint = {k: raw_json.get(k) for k in _FIELDS_HASH_KEYS}
    s = json.dumps(fingerprint, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


# ============================================================
# Step B: LLM 联网补全缺失字段
# ============================================================
# LLM 应返回的字段及类型（缺失返回 null，禁止编造）
_ENRICH_SCHEMA_FIELDS = [
    "event_year", "items", "certification", "level", "reg_start", "reg_end",
    "start_point", "end_point", "lottery_history", "registration_channels",
    "organizer", "contact_phone", "contact_email", "introduction",
]

_PROMPT_TMPL = """你是马拉松赛事资料补全助手。下面给出一项赛事从列表卡片中已解析出的基础信息（高可信度）。请你基于你对这场赛事的公开知识（含官网、过往年份公告、田协/世界田联赛事日历、媒体报道）补全 MISSING 字段。不要从给定基础信息中再抽取——那些字段已经填好；你只需返回 MISSING 部分。若你对某字段确实无可靠信息，必须返回 null，禁止编造。

【已知基础信息】
event_name: {event_name}
race_date: {race_date}
location: {location}
reg_end_raw: {reg_end_raw}
status_raw: {status_raw}

【需要你补全的字段（严格 JSON，键名固定）】
{{
  "event_year":        int | null,
  "items":             [{{"type":"马拉松","fee":160,"scale":20000}}] | null,
  "certification":     "A类"|"B类"|"C类"|null,
  "level":             "白金标"|"金标"|"精英标"|"标牌"|null,
  "reg_start":         "2026-09-01 10:00" | null,
  "reg_end":            "2026-09-30 23:59" | null,
  "start_point":        string | null,
  "end_point":          string | null,
  "lottery_history":    string | null,
  "registration_channels": string | null,
  "organizer":          string | null,
  "contact_phone":      string | null,
  "contact_email":      string | null,
  "introduction":       string | null
}}

只输出 JSON 对象，不要任何说明文字。
"""


async def enrich_with_llm(
    raw_json: dict,
    *,
    llm_api_base: str,
    llm_api_key: str,
    llm_model: str,
    timeout: int = 45,
) -> dict:
    """调 LLM 联网补全缺失字段。返回 enrich_json = {**raw_json, **llm_filled}。
    LLM_API_KEY 空时 raise RuntimeError，不静默返回 raw_json。"""
    if not llm_api_key:
        raise RuntimeError("LLM_API_KEY 未配置，无法跑 enrich 流程")

    base = (llm_api_base or "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/chat/completions"
    prompt = _PROMPT_TMPL.format(
        event_name=raw_json.get("event_name") or "",
        race_date=raw_json.get("start_date_raw") or "",
        location=raw_json.get("location_raw") or "",
        reg_end_raw=raw_json.get("reg_end_raw") or "",
        status_raw=raw_json.get("status_raw") or "",
    )
    headers = {
        "Authorization": f"Bearer {llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": llm_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are a helpful JSON-only extractor."},
            {"role": "user", "content": prompt},
        ],
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"LLM status={resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    # 去 ```json fences
    content = content.strip().strip("`")
    if content.startswith("json"):
        content = content[4:]
    obj = json.loads(content)
    # 兼容模型把结果塞到 "events" key 的情况
    if isinstance(obj, dict) and "events" in obj and isinstance(obj["events"], dict):
        obj = obj["events"]

    # 合并：raw_json 在前，LLM 补全字段在后（LLM 覆盖）
    enrich_json = dict(raw_json)
    for k in _ENRICH_SCHEMA_FIELDS:
        if k in obj:
            enrich_json[k] = obj[k]
    enrich_json["_enriched_at"] = datetime.now().isoformat(timespec="seconds")
    return enrich_json


# ============================================================
# Step C: 二轮筛选 → final_json + confidence
# ============================================================
_UNKNOWN_TOKENS = {"未知", "无", "暂无", "暂未公布", "不详", "n/a", "null"}


def _clean_val(v):
    """null/空串/未知词 → None；字符串去首尾空白"""
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s or s.lower() in _UNKNOWN_TOKENS:
            return None
        return s
    return v


def _normalize_certification(raw: Optional[str]) -> Optional[str]:
    s = _clean_val(raw)
    if not s:
        return None
    low = s.lower()
    # A1/A2/B1 等也归到对应主类，统一存 A类/B类/C类
    if low.startswith("a"):
        return "A类"
    if low.startswith("b"):
        return "B类"
    if low.startswith("c"):
        return "C类"
    return s


def filter_enriched(enrich_json: dict) -> tuple[dict, int]:
    """二轮筛选：null/未知词/空串剔除；枚举归一；算 confidence。
    返回 (final_json, confidence)。Phase 1 final_json 基本镜像 enrich_json。"""
    final = dict(enrich_json)
    # 清洗所有顶层标量字段
    for k in list(final.keys()):
        final[k] = _clean_val(final.get(k))

    # items 数组逐项清洗
    items = final.get("items")
    if isinstance(items, list):
        cleaned_items = []
        for it in items:
            if not isinstance(it, dict):
                continue
            t = _clean_val(it.get("type"))
            if not t:
                continue
            fee = it.get("fee")
            try:
                fee = float(fee) if fee not in (None, "", 0) else None
            except (TypeError, ValueError):
                fee = None
            scale = it.get("scale")
            try:
                scale = int(scale) if scale not in (None, "", 0) else None
            except (TypeError, ValueError):
                scale = None
            cleaned_items.append({"type": t, "fee": fee, "scale": scale})
        final["items"] = cleaned_items or None
    else:
        final["items"] = None

    final["certification"] = _normalize_certification(final.get("certification"))

    # confidence = 已填充的非空字段数 / 应填字段数
    filled = sum(1 for k in _ENRICH_SCHEMA_FIELDS if final.get(k) not in (None, [], ""))
    confidence = round(100 * filled / len(_ENRICH_SCHEMA_FIELDS))
    final["_confidence"] = confidence
    return final, confidence


# ============================================================
# Step D: persist_to_source — 写 mi_event_source
# ============================================================
async def persist_to_source(
    db: AsyncSession,
    *,
    source_name: str,
    source_url: str,
    source_weight: int,
    zuicool_event_id: str,
    raw_json: dict,
    enrich_json: dict,
    final_json: dict,
    parser_tag: str = "rule+llm",
    parse_confidence: int = 80,
) -> int:
    """upsert mi_event_source（按 source_name+zuicool_event_id 唯一索引）：
    - 不存在 → INSERT 新行
    - 存在 → UPDATE raw_json/enrich_json/final_json/raw_html_hash/fetched_at，审计链保留在原行（覆盖旧值）

    raw_html_hash 列复用为"卡片字段 hash"（compute_fields_hash），原意"HTML 内容哈希"在 enrich
    流水线里未使用，语义已扩展为"判断字段是否有更新"。
    返回 source_id。
    """
    fields_hash = compute_fields_hash(raw_json)

    # 查已存行（命中 ux_zuicool_source 唯一索引）
    q = await db.execute(
        select(EventSource).where(
            EventSource.source_name == source_name,
            EventSource.zuicool_event_id == zuicool_event_id,
        )
    )
    existing = q.scalars().first()

    if existing is not None:
        # UPDATE：覆盖 raw/enrich/final + 刷新 hash 和 fetched_at
        existing.event_name_raw = raw_json.get("event_name") or ""
        existing.start_date_raw = raw_json.get("start_date_raw")
        existing.location_raw = raw_json.get("location_raw")
        existing.source_url = source_url
        existing.raw_json = raw_json
        existing.enrich_json = enrich_json
        existing.final_json = final_json
        existing.raw_html_hash = fields_hash
        existing.parser_tag = parser_tag
        existing.parse_confidence = parse_confidence
        existing.fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # match_status 和 matched_event_id 保留（已 matched 的不重置）
        await db.flush()
        return existing.source_id

    # INSERT 新行
    src = EventSource(
        source_name=source_name,
        source_url=source_url,
        source_weight=source_weight,
        event_name_raw=raw_json.get("event_name") or "",
        start_date_raw=raw_json.get("start_date_raw"),
        location_raw=raw_json.get("location_raw"),
        zuicool_event_id=zuicool_event_id,
        raw_json=raw_json,
        enrich_json=enrich_json,
        final_json=final_json,
        raw_html_hash=fields_hash,
        parser_tag=parser_tag,
        parse_confidence=parse_confidence,
        match_status="pending",
    )
    db.add(src)
    await db.flush()
    return src.source_id


# ============================================================
# Step E: sync_to_event — final_json → upsert mi_event
# ============================================================
def _derive_event_type(items: Optional[list]) -> int:
    """从 items 派生 event_type 仅满足 NOT NULL 列（非主项目语义）。
    取最长距离项目：马拉松>半程>健康跑>越野。"""
    if not items:
        return 1
    priority = {"马拉松": 1, "半程马拉松": 2, "健康跑": 3, "欢乐跑": 3, "越野": 4}
    best = 5
    for it in items:
        if not isinstance(it, dict):
            continue
        t = (it.get("type") or "")
        for kw, code in priority.items():
            if kw in t and code < best:
                best = code
    return best if best <= 4 else 1


def _map_status(status_raw: Optional[str], reg_end: Optional[datetime], start_dt: Optional[datetime]) -> int:
    """卡片按钮文本 + reg_end + 比赛日期 → event_status。
    1未开始(即将报名) 2报名中 3报名结束 4比赛中 5已结束"""
    today = date.today()
    # 比赛日期优先
    if start_dt:
        sd = start_dt.date()
        if sd < today and (today - sd).days > 1:
            return 5  # 已结束
        if sd <= today <= sd + timedelta(days=1):
            return 4  # 比赛中
    # 按钮文本：即将报名 → 1，点此报名/立即报名/报名中 → 2，已截止/报名结束 → 3
    s = (status_raw or "").strip()
    if "即将" in s:
        return 1
    if "截止" in s or "结束" in s:
        return 3
    if "报名" in s or "点此" in s or "立即" in s:
        return 2
    # reg_end 兜底
    if reg_end:
        return 3 if reg_end.date() < today else 2
    return 1


async def _match_existing(db: AsyncSession, name: str, city: Optional[str],
                          start_dt: Optional[datetime]) -> Optional[int]:
    """复用 runner._match_existing_events 策略：同市+同天+名称LIKE。"""
    if not start_dt or not city:
        return None
    day_start = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start.replace(hour=23, minute=59, second=59)
    name_like = f"%{name.replace('马拉松', '')[:6]}%"
    q = await db.execute(
        select(Event).where(
            Event.deleted == 0,
            Event.city == city,
            Event.start_time >= day_start,
            Event.start_time <= day_end,
            or_(Event.event_name == name, Event.event_name.like(name_like)),
        )
    )
    e = q.scalars().first()
    return e.event_id if e else None


async def sync_to_event(db: AsyncSession, source_id: int,
                        final_json: dict) -> Optional[int]:
    """解析 final_json → upsert mi_event。返回 event_id（新增或更新）。
    多项目：items_json 是 type/fee/scale 唯一来源；event_type 从 items 派生；
    registration_fee/max_participants 不填（留 NULL/0）。"""
    name = (final_json.get("event_name") or "").strip()
    if len(name) < 2:
        return None

    start_dt = parse_date(final_json.get("start_date_raw") or final_json.get("race_date"))
    reg_start = parse_date(final_json.get("reg_start"))
    reg_end = parse_date(final_json.get("reg_end") or final_json.get("reg_end_raw"))

    province, city, loc_full = _normalize_location(final_json.get("location_raw"))
    items = final_json.get("items") if isinstance(final_json.get("items"), list) else None
    event_type = _derive_event_type(items)
    event_level = _map_by_keywords(final_json.get("level"), LEVEL_MAP, 5)
    event_status = _map_status(final_json.get("status_raw"), reg_end, start_dt)

    # 赛事年份：LLM 给的优先，否则从 start_dt 推
    event_year = final_json.get("event_year")
    if not event_year and start_dt:
        try:
            event_year = start_dt.year
        except Exception:
            event_year = None

    matched_id = None
    # 已 enrich 过的赛事：从 mi_event_source.matched_event_id 反查 mi_event
    # （比 _match_existing 的"同市+同天+名称LIKE"更可靠，避免字段变化时匹配错位）
    src_q = await db.execute(
        select(EventSource.matched_event_id).where(EventSource.source_id == source_id)
    )
    src_row = src_q.first()
    if src_row and src_row[0]:
        matched_id = src_row[0]
    if matched_id is None:
        matched_id = await _match_existing(db, name, city, start_dt)
    if matched_id is None:
        ev = Event(
            event_name=name,
            cover_image=final_json.get("cover_image"),
            event_type=event_type,
            event_status=event_status,
            event_level=event_level,
            start_time=start_dt,
            registration_start_time=reg_start,
            registration_end_time=reg_end,
            registration_link=final_json.get("reg_link"),
            location=loc_full,
            province=province,
            city=city,
            address=None,
            introduction=final_json.get("introduction"),
            organizer=final_json.get("organizer"),
            contact_phone=final_json.get("contact_phone"),
            contact_email=final_json.get("contact_email"),
            items_json=items if items else null(),  # [] / None → SQL NULL（避免 SQLAlchemy JSON 列把 None 序列化成 'null' 字面量）
            certification=final_json.get("certification"),
            lottery_history=final_json.get("lottery_history"),
            registration_channels=final_json.get("registration_channels"),
            start_point=final_json.get("start_point"),
            end_point=final_json.get("end_point"),
            event_year=event_year,
            create_by="pipeline-enrich",
        )
        db.add(ev)
        await db.flush()
        matched_id = ev.event_id
    else:
        ev = await db.get(Event, matched_id)
        if ev:
            changed = False
            for fname, new_val in (
                ("event_status", event_status), ("event_level", event_level),
                ("start_time", start_dt), ("registration_start_time", reg_start),
                ("registration_end_time", reg_end), ("registration_link", final_json.get("reg_link")),
                ("cover_image", final_json.get("cover_image")),
                ("introduction", final_json.get("introduction")),
                ("organizer", final_json.get("organizer")),
                ("contact_phone", final_json.get("contact_phone")),
                ("contact_email", final_json.get("contact_email")),
                ("items_json", items), ("certification", final_json.get("certification")),
                ("lottery_history", final_json.get("lottery_history")),
                ("registration_channels", final_json.get("registration_channels")),
                ("start_point", final_json.get("start_point")),
                ("end_point", final_json.get("end_point")),
                ("event_year", event_year), ("event_type", event_type),
                ("province", province), ("city", city),
            ):
                if new_val is None or new_val == 0:
                    continue
                if getattr(ev, fname) != new_val:
                    setattr(ev, fname, new_val)
                    changed = True
            ev.update_by = "pipeline-enrich"
            ev.update_time = datetime.now()
            if changed:
                logger.info(f"[Enricher] 更新 mi_event id={matched_id} {name}")
        else:
            return None

    # 回填 source 表匹配状态
    await db.execute(
        EventSource.__table__.update()
        .where(EventSource.source_id == source_id)
        .values(match_status="matched", matched_event_id=matched_id)
    )
    return matched_id
