"""enrich 流水线 dry-run：取一个 event_id，跑 build_raw_json→enrich_with_llm→filter_enriched，
打印三段 JSON + confidence，不碰 DB。

用法：
  cd server
  python -m tools.enrich_dryrun --event-id 58557
  python -m tools.enrich_dryrun              # 不传 id 则取列表页第一张卡片
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 让 server 目录可 import（脚本从 server/ 根运行）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.pipeline import enricher
from app.pipeline.sources.zuicool import ZuicoolAdapter


async def _fetch_card_by_id(adapter: ZuicoolAdapter, event_id: str):
    """从列表页翻页找到指定 event_id 的卡片 candidate；找不到返回 None。"""
    discovered = await adapter.discover_events(timeout=20, max_pages=5)
    for d in discovered:
        if d.get("event_id") == str(event_id):
            return d.get("candidate"), d
    return None, None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--event-id", default=None, help="最酷 event_id；不传取列表页第一张")
    ap.add_argument("--max-pages", type=int, default=2, help="不传 event-id 时翻几页找首个")
    args = ap.parse_args()

    settings = get_settings()
    if not settings.LLM_API_KEY:
        print("⚠️  LLM_API_KEY 未配置（.env），enrich_with_llm 会报错。"
              "只能跑 build_raw_json，不能跑 LLM 补全。", file=sys.stderr)

    adapter = ZuicoolAdapter()
    candidate = None
    if args.event_id:
        candidate, meta = await _fetch_card_by_id(adapter, args.event_id)
        if candidate is None:
            # 列表页没有该 id（可能是已截止/历史赛事，不在列表里）→ 构造一个最小 candidate
            from app.pipeline.base import EventCandidate
            candidate = EventCandidate(
                event_name=f"event_id={args.event_id}（不在列表页，可能已截止）",
                source_name="最酷",
                source_url=f"https://zuicool.com/event/{args.event_id}",
                raw_extra={"event_id": args.event_id},
            )
            meta = {"event_id": args.event_id, "name": candidate.event_name}
    else:
        discovered = await adapter.discover_events(timeout=20, max_pages=args.max_pages)
        if not discovered:
            print("列表页未抓到任何卡片", file=sys.stderr)
            return
        meta = discovered[0]
        candidate = meta.get("candidate")

    print(f"\n=== 选中赛事 ===\n  event_id: {meta.get('event_id')}\n  name: {meta.get('name')}\n")

    # Step 1: build_raw_json
    raw_json = enricher.build_raw_json(candidate)
    print("=== [1] raw_json（卡片抽取）===")
    print(json.dumps(raw_json, ensure_ascii=False, indent=2))

    if not settings.LLM_API_KEY:
        print("\n（LLM_API_KEY 未配置，跳过 enrich/filter）")
        return

    # Step 2: enrich_with_llm
    print("\n=== [2] enrich_with_llm（LLM 联网补全，可能耗时 5-30s）===")
    enrich_json = await enricher.enrich_with_llm(
        raw_json,
        llm_api_base=settings.LLM_API_BASE,
        llm_api_key=settings.LLM_API_KEY,
        llm_model=settings.LLM_MODEL,
    )
    print(json.dumps(enrich_json, ensure_ascii=False, indent=2))

    # Step 3: filter_enriched
    final_json, conf = enricher.filter_enriched(enrich_json)
    print(f"\n=== [3] final_json（二轮筛选后）  confidence={conf} ===")
    print(json.dumps(final_json, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
