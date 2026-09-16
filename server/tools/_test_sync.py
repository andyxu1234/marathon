"""端到端 DB 写入测试（不依赖 LLM）：构造假 final_json → persist_to_source + sync_to_event → 查 mi_event 断言 → 清理。
验证 mi_event_source 三态 JSON + mi_event 新列（items_json/certification/...）真实可写可读。"""
import asyncio
from app.database import async_session_factory
from app.pipeline import enricher
from app.pipeline.base import EventCandidate
from sqlalchemy import text


async def main():
    cand = EventCandidate(
        event_name="测试马拉松_dryrun",
        source_name="最酷",
        source_url="https://zuicool.com/event/999999",
        source_weight=80,
        start_date_raw="2026.11.15",
        location_raw="江苏 南京市 玄武区",
        status_raw="点此报名",
        reg_end_raw="2026-10-20 23:59",
        reg_link="https://zuicool.com/event/999999",
        type_raw="马拉松",
        raw_extra={"event_id": "999999"},
    )
    raw_json = enricher.build_raw_json(cand)
    # 假 LLM 输出（绕过 enrich_with_llm）
    enrich_json = {
        **raw_json,
        "event_year": 2026,
        "items": [
            {"type": "马拉松", "fee": 200, "scale": 15000},
            {"type": "半程马拉松", "fee": 120, "scale": 8000},
            {"type": "欢乐跑", "fee": 60, "scale": 3000},
        ],
        "certification": "A类",
        "level": "金标",
        "reg_start": "2025-09-01 10:00",
        "reg_end": "2026-10-20 23:59",
        "start_point": "南京奥体中心",
        "end_point": "青奥体育公园",
        "lottery_history": "2024 全马中签率 12%，半马 25%",
        "registration_channels": "数字心动APP、官方公众号",
        "organizer": "南京市体育局",
        "contact_phone": "025-12345678",
        "introduction": "测试赛事简介",
    }
    final_json, conf = enricher.filter_enriched(enrich_json)
    print(f"confidence={conf}")

    async with async_session_factory() as db:
        # 写 source
        src_id = await enricher.persist_to_source(
            db,
            source_name="最酷",
            source_url="https://zuicool.com/event/999999",
            source_weight=80,
            zuicool_event_id="999999",
            raw_json=raw_json,
            enrich_json=enrich_json,
            final_json=final_json,
            parse_confidence=conf,
        )
        # 写 mi_event
        event_id = await enricher.sync_to_event(db, src_id, final_json)
        await db.commit()
        print(f"source_id={src_id} event_id={event_id}")

        # 查 mi_event 断言新列
        r = await db.execute(text(
            "SELECT event_name, event_type, event_status, event_level, "
            "JSON_LENGTH(items_json) AS n_items, certification, event_year, "
            "start_point, end_point, lottery_history, registration_channels "
            "FROM mi_event WHERE event_id=:id"), {"id": event_id})
        row = r.first()
        print("mi_event row:", row)
        assert row and row[0] == "测试马拉松_dryrun"
        assert row[1] == 1, "event_type should be 1 (马拉松 derived)"
        assert row[2] == 2, "status should be 2 (报名中)"
        assert row[3] == 2, "level should be 2 (金标)"
        assert row[4] == 3, "items_json should have 3 items"
        assert row[5] == "A类"
        assert row[6] == 2026
        assert row[7] == "南京奥体中心"
        print("✓ mi_event 所有新列断言通过")

        # 再跑一次 sync_to_event，应走 UPDATE 不重复 INSERT
        event_id2 = await enricher.sync_to_event(db, src_id, final_json)
        await db.commit()
        assert event_id2 == event_id, f"应复用同一 event_id，got {event_id2}"
        r2 = await db.execute(text("SELECT COUNT(*) FROM mi_event WHERE event_id=:id"), {"id": event_id})
        assert r2.scalar() == 1
        print(f"✓ 重复 sync 走 UPDATE（event_id 复用 {event_id}，无重复行）")

        # 清理（dev 库不留测试数据）
        await db.execute(text("DELETE FROM mi_event WHERE event_id=:id"), {"id": event_id})
        await db.execute(text("DELETE FROM mi_event_source WHERE source_id=:id"), {"id": src_id})
        await db.commit()
        print("✓ 已清理测试数据")


asyncio.run(main())
