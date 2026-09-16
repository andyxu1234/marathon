"""小批量真实入库验证：取前 N 个 event 走完整 enrich 链路（real LLM → real DB write）。
用法：python -m tools.enrich_batch_run --limit 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.config import get_settings
from app.database import async_session_factory
from app.pipeline import enricher
from app.pipeline.runner import _load_existing_zuicool_state
from app.pipeline.sources.zuicool import ZuicoolAdapter


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5, help="处理前 N 个新增/变化 event")
    ap.add_argument("--max-pages", type=int, default=2, help="discover 翻几页找 event")
    args = ap.parse_args()

    settings = get_settings()
    if not settings.LLM_API_KEY:
        print("LLM_API_KEY 未配置，无法跑", file=sys.stderr)
        return

    adapter = ZuicoolAdapter()
    print(f"[1] discover_events (max_pages={args.max_pages})...")
    discovered = await adapter.discover_events(timeout=settings.PIPELINE_FETCH_TIMEOUT,
                                              max_pages=args.max_pages)
    print(f"    列表共 {len(discovered)} 条")

    async with async_session_factory() as db:
        # 方案 B diff：新 event_id → 新增；已存但 fields_hash 变了 → 更新；否则跳过
        existing_state = await _load_existing_zuicool_state(db)
        todo: list[dict] = []
        skipped = 0
        for d in discovered:
            eid = d.get("event_id")
            cand = d.get("candidate")
            if not eid or cand is None:
                continue
            today_raw = enricher.build_raw_json(cand)
            today_hash = enricher.compute_fields_hash(today_raw)
            st = existing_state.get(eid)
            if st is None:
                d["_kind"] = "new"
                d["_today_raw"] = today_raw
                todo.append(d)
            elif (st.get("fields_hash") or "") != today_hash:
                d["_kind"] = "update"
                d["_today_raw"] = today_raw
                todo.append(d)
            else:
                skipped += 1
        todo = todo[: args.limit]
        print(f"[2] diff: 已存 {len(existing_state)}，"
              f"待处理 {len(todo)}（新增+变化），无变化跳过 {skipped}\n")

        results = []
        for i, item in enumerate(todo, 1):
            eid = item["event_id"]
            cand = item.get("candidate")
            name = item.get("name")
            kind = item.get("_kind", "new")
            print(f"  [{i}/{len(todo)}] ({kind}) id={eid} {name}")
            try:
                raw_json = item.pop("_today_raw", None) or enricher.build_raw_json(cand)
                enrich_json = await enricher.enrich_with_llm(
                    raw_json,
                    llm_api_base=settings.LLM_API_BASE,
                    llm_api_key=settings.LLM_API_KEY,
                    llm_model=settings.LLM_MODEL,
                )
                final_json, conf = enricher.filter_enriched(enrich_json)
                src_id = await enricher.persist_to_source(
                    db,
                    source_name=adapter.source_name,
                    source_url=item.get("url") or cand.source_url,
                    source_weight=adapter.source_weight,
                    zuicool_event_id=eid,
                    raw_json=raw_json,
                    enrich_json=enrich_json,
                    final_json=final_json,
                    parse_confidence=conf,
                )
                ev_id = await enricher.sync_to_event(db, src_id, final_json)
                results.append({
                    "eid": eid, "name": name, "src_id": src_id, "event_id": ev_id,
                    "conf": conf,
                    "items": final_json.get("items"),
                    "cert": final_json.get("certification"),
                    "level": final_json.get("level"),
                    "lottery": bool(final_json.get("lottery_history")),
                    "channels": bool(final_json.get("registration_channels")),
                })
                print(f"      → source_id={src_id} event_id={ev_id} conf={conf}")
            except Exception as e:
                print(f"      ✗ 失败: {e!r}")
                await db.rollback()
                continue
            await db.commit()

        # 汇总查询：从 DB 读回来确认真实落库
        print("\n[3] DB 回查确认：")
        for r in results:
            if not r["event_id"]:
                continue
            q = await db.execute(text(
                "SELECT event_name, event_type, event_status, event_level, "
                "certification, event_year, JSON_LENGTH(items_json) AS n_items, "
                "start_point, lottery_history IS NOT NULL AS has_lottery, "
                "registration_channels IS NOT NULL AS has_channels "
                "FROM mi_event WHERE event_id=:id"), {"id": r["event_id"]})
            row = q.first()
            print(f"  event_id={r['event_id']} {row[0]}")
            print(f"    type={row[1]} status={row[2]} level={row[3]} cert={row[4]} year={row[5]} n_items={row[6]}")
            print(f"    start_point={row[7]} has_lottery={row[8]} has_channels={row[9]}")

        print("\n[4] 字段命中统计：")
        total = len(results)
        for f in ["items", "cert", "level", "lottery", "channels"]:
            n = sum(1 for r in results if r.get(f))
            print(f"    {f}: {n}/{total}")


asyncio.run(main())
