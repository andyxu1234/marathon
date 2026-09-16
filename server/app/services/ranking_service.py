"""跑者排行 service —— 4 个 metric 的实时聚合

数据来源：
  - 官方赛事：mi_registration JOIN mi_event，event_id 非空
  - 自定义赛事：mi_registration JOIN mi_event_customize，custom_event_id 非空
  - 项目类型优先取 registration.race_type（1全马 2半马 3健康跑），
    官方赛事的 race_type=0 时 fallback 到 event.event_type（1-5）。

距离推算（粗略）：
  race_type 1=全马 42.195 km；2=半马 21.0975 km；3=健康跑 5 km；
  event_type 4=越野 30 km（仅官方赛事有）；
  0/5=其他或未设置 → 不计入（避免歪数据）。
"""

from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.event_customize import EventCustomize
from app.models.registration import Registration
from app.models.user import User
from app.schemas.ranking import RankingItem, RankingListOut

METRIC_DISTANCE = "distance"
METRIC_HALF_PB = "half_marathon_pb"
METRIC_FULL_PB = "full_marathon_pb"
METRIC_SPENT = "spent"

ALL_METRICS = (METRIC_DISTANCE, METRIC_HALF_PB, METRIC_FULL_PB, METRIC_SPENT)

METRIC_LABELS = {
    METRIC_DISTANCE: "总跑量",
    METRIC_HALF_PB: "半马 PB",
    METRIC_FULL_PB: "全马 PB",
    METRIC_SPENT: "总花费",
}

DISTANCE_BY_RACE_TYPE: dict[int, float] = {
    1: 42.195,    # 全马
    2: 21.0975,   # 半马
    3: 5.0,       # 健康跑
}

DISTANCE_BY_EVENT_TYPE_FALLBACK: dict[int, float] = {
    1: 42.195,   # 马拉松
    2: 21.0975,  # 半程马拉松
    3: 5.0,      # 健康跑
    4: 30.0,     # 越野（官方赛事独有）
}

# 标准赛事距离的小数位数（保留精确值，不四舍五入）：
#   半马 = 21.0975（4 位），全马 = 42.195（3 位），健康跑 5.0 / 越野 30.0（1 位）
_DISTANCE_DECIMALS: dict[float, int] = {
    21.0975: 4,
    42.195: 3,
    5.0: 1,
    30.0: 1,
}


def _format_km(km: float) -> str:
    """根据累计距离的组成判断合适的小数位数，避免 21.0975 被截成 21.10

    规则：
    - 累计距离恰好是某标准距离的倍数（如 21.0975 * 1 = 21.0975）→ 用该标准的精度
    - 否则统一 2 位小数（如 21.0975 + 42.195 = 63.2925 → 63.29）
    """
    for std, decimals in _DISTANCE_DECIMALS.items():
        if abs(km % std) < 1e-6 or abs(km - std * round(km / std)) < 1e-6:
            # 是这个标准的整数倍 → 用标准精度
            return f"{km:.{decimals}f} km"
    return f"{km:.2f} km"

# finish_time "h:mm:ss" → 秒数
_PB_RE = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})$")


def _parse_pb(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    m = _PB_RE.match(s.strip())
    if not m:
        return None
    h, mn, sec = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return h * 3600 + mn * 60 + sec


def _format_pb(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h}:{m:02d}:{s:02d}"


def _format_value(metric: str, value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    if metric in (METRIC_HALF_PB, METRIC_FULL_PB):
        return _format_pb(int(value))
    if metric == METRIC_SPENT:
        return f"¥{int(value)}"
    return _format_km(value)


async def list_rankings(
    db: AsyncSession,
    *,
    metric: str,
    gender: int = 0,
    age_group: int = 0,
    current_user_id: Optional[int] = None,
    limit: int = 50,
) -> RankingListOut:
    if metric not in ALL_METRICS:
        metric = METRIC_DISTANCE

    # 1) 全部有效 user（deleted=0；不过滤 dev_ 沙盒——开发期让所有人上榜）
    u_stmt = select(
        User.user_id, User.nickname, User.username, User.avatar, User.gender, User.age_group
    ).where(User.deleted == 0)
    user_rows = (await db.execute(u_stmt)).all()
    users_by_id: dict[int, dict] = {}
    for u in user_rows:
        users_by_id[u.user_id] = {
            "nickname": u.nickname or u.username or f"跑友{u.user_id:05d}",
            "avatar": u.avatar,
            "gender": u.gender or 0,
            "age_group": u.age_group or 0,
        }

    # 2) 查询官方赛事 registration（join Event 拿 event_type 做 fallback）
    r_official_stmt = (
        select(
            Registration.user_id,
            Registration.finish_time,
            Registration.result_status,
            Registration.fee,
            Registration.payment_status,
            Registration.race_type,
            Event.event_type,
        )
        .join(Event, Event.event_id == Registration.event_id)
        .where(Registration.deleted == 0, Event.deleted == 0, Registration.event_id.isnot(None))
    )
    official_rows = (await db.execute(r_official_stmt)).all()

    # 2b) 查询自定义赛事 registration（无 event_type，只靠 race_type）
    r_custom_stmt = (
        select(
            Registration.user_id,
            Registration.finish_time,
            Registration.result_status,
            Registration.fee,
            Registration.payment_status,
            Registration.race_type,
        )
        .join(EventCustomize, EventCustomize.customize_id == Registration.custom_event_id)
        .where(
            Registration.deleted == 0,
            EventCustomize.deleted == 0,
            Registration.custom_event_id.isnot(None),
        )
    )
    custom_rows = (await db.execute(r_custom_stmt)).all()

    # 3) 聚合每个用户的 4 指标
    agg: dict[int, dict] = {}

    def _apply_row(user_id: int, race_type: int, event_type: Optional[int],
                   finish_time: Optional[str], result_status: Optional[int],
                   fee: Optional[float], payment_status: Optional[int]):
        a = agg.setdefault(
            user_id,
            {
                "distance_km": 0.0,
                "half_pb_seconds": None,
                "full_pb_seconds": None,
                "finished_count": 0,
                "registered_count": 0,
                "total_spent": 0.0,
            },
        )
        a["registered_count"] += 1
        if payment_status == 1 and fee is not None:
            a["total_spent"] += float(fee)

        # 确定项目类型（优先 race_type，fallback event_type）
        resolved_type = race_type if race_type and race_type in DISTANCE_BY_RACE_TYPE else None
        if resolved_type is None and event_type is not None:
            resolved_type = event_type if event_type in DISTANCE_BY_EVENT_TYPE_FALLBACK else None

        is_finished = result_status is not None and result_status >= 1
        if is_finished:
            a["finished_count"] += 1
            # 距离累加
            km = None
            if resolved_type is not None:
                if resolved_type in DISTANCE_BY_RACE_TYPE:
                    km = DISTANCE_BY_RACE_TYPE[resolved_type]
                elif event_type is not None and event_type in DISTANCE_BY_EVENT_TYPE_FALLBACK:
                    km = DISTANCE_BY_EVENT_TYPE_FALLBACK[event_type]
            if km:
                a["distance_km"] += km

            # PB 更新：race_type 1=全马 2=半马
            sec = _parse_pb(finish_time)
            if sec is not None and race_type in (1, 2):
                if race_type == 2:
                    if a["half_pb_seconds"] is None or sec < a["half_pb_seconds"]:
                        a["half_pb_seconds"] = sec
                elif race_type == 1:
                    if a["full_pb_seconds"] is None or sec < a["full_pb_seconds"]:
                        a["full_pb_seconds"] = sec
            # 官方赛事 fallback：race_type=0 时用 event_type
            elif sec is not None and race_type == 0 and event_type in (1, 2):
                if event_type == 2:
                    if a["half_pb_seconds"] is None or sec < a["half_pb_seconds"]:
                        a["half_pb_seconds"] = sec
                elif event_type == 1:
                    if a["full_pb_seconds"] is None or sec < a["full_pb_seconds"]:
                        a["full_pb_seconds"] = sec

    for r in official_rows:
        _apply_row(
            user_id=r.user_id,
            race_type=r.race_type or 0,
            event_type=r.event_type,
            finish_time=r.finish_time,
            result_status=r.result_status,
            fee=r.fee,
            payment_status=r.payment_status,
        )

    for r in custom_rows:
        _apply_row(
            user_id=r.user_id,
            race_type=r.race_type or 0,
            event_type=None,
            finish_time=r.finish_time,
            result_status=r.result_status,
            fee=r.fee,
            payment_status=r.payment_status,
        )

    # 4) 应用筛选 + 计算 metric value，构造候选列表
    candidates: list[tuple[int, dict, float]] = []
    for uid, meta in users_by_id.items():
        if gender not in (0, None) and meta["gender"] != gender:
            continue
        if age_group not in (0, None) and meta["age_group"] != age_group:
            continue
        a = agg.get(uid)
        if metric == METRIC_HALF_PB:
            sec = a["half_pb_seconds"] if a else None
            if sec is None:
                continue
            value = float(sec)
        elif metric == METRIC_FULL_PB:
            sec = a["full_pb_seconds"] if a else None
            if sec is None:
                continue
            value = float(sec)
        elif metric == METRIC_SPENT:
            value = float(a["total_spent"] if a else 0.0)
        else:  # distance
            value = float(a["distance_km"] if a else 0.0)
        candidates.append((uid, meta, value))

    # 5) 排序 + 取 top
    if metric in (METRIC_HALF_PB, METRIC_FULL_PB):
        candidates.sort(key=lambda x: x[2])
    else:
        candidates.sort(key=lambda x: x[2], reverse=True)

    top = candidates[:limit]
    items: list[RankingItem] = []
    for rank, (uid, meta, value) in enumerate(top, start=1):
        a = agg.get(uid, {})
        items.append(
            RankingItem(
                rank=rank,
                user_id=uid,
                nickname=meta["nickname"],
                avatar=meta["avatar"],
                gender=meta["gender"],
                age_group=meta["age_group"],
                value=value,
                value_label=_format_value(metric, value) or "—",
                finished_count=a.get("finished_count", 0),
                registered_count=a.get("registered_count", 0),
            )
        )

    # 6) 当前登录用户的"我的"视图
    my_rank: Optional[RankingItem] = None
    my_value: Optional[float] = None
    my_value_label: Optional[str] = None
    my_insight: Optional[str] = None

    if current_user_id is not None:
        in_top = next((it for it in items if it.user_id == current_user_id), None)
        if in_top:
            my_rank = in_top
            my_value = in_top.value
            my_value_label = in_top.value_label
        else:
            # 在完整候选里查
            full_idx = next(
                (
                    (idx, uid, meta, val)
                    for idx, (uid, meta, val) in enumerate(candidates, start=1)
                    if uid == current_user_id
                ),
                None,
            )
            if full_idx:
                idx, uid, meta, val = full_idx
                a = agg.get(uid, {})
                my_value = val
                my_value_label = _format_value(metric, val) or "—"
                my_rank = RankingItem(
                    rank=idx,
                    user_id=uid,
                    nickname=meta["nickname"],
                    avatar=meta["avatar"],
                    gender=meta["gender"],
                    age_group=meta["age_group"],
                    value=val,
                    value_label=my_value_label,
                    finished_count=a.get("finished_count", 0),
                    registered_count=a.get("registered_count", 0),
                )
                my_insight = "当前筛选下未上榜"
            else:
                # 不在候选里：可能是沙盒账号，或 metric=PB 时无完赛记录
                if metric in (METRIC_HALF_PB, METRIC_FULL_PB):
                    my_value_label = "—"
                    my_insight = "完成一场半马/全马后即可上榜"
                else:
                    my_value_label = "0 km" if metric == METRIC_DISTANCE else "¥0"
                    my_insight = "去关注或添加赛事，开始你的跑步旅程"

    return RankingListOut(
        metric=metric,
        gender=gender,
        age_group=age_group,
        items=items,
        my_rank=my_rank,
        my_value=my_value,
        my_value_label=my_value_label,
        my_insight=my_insight,
        total_users=len(candidates),
    )