"""报名状态路由 + 添加赛事"""

from fastapi import APIRouter, HTTPException

from app.deps import DBSession, CurrentUser
from app.schemas.common import OkOut
from app.schemas.registration import RegistrationUpdate, AddRaceRequest, AddRaceOut
from app.services import registration_service

router = APIRouter(tags=["registrations"])


@router.put("/events/{event_id}/registration", response_model=OkOut)
async def update_registration(
    event_id: int,
    payload: RegistrationUpdate,
    db: DBSession,
    user: CurrentUser,
):
    """更新某赛事的报名状态（关注页 chips 切换）"""
    reg = await registration_service.update_registration(
        db, user.user_id, event_id, payload
    )
    if not reg:
        raise HTTPException(status_code=404, detail="赛事不存在")
    return OkOut(ok=True, message="已更新")


@router.put("/custom-events/{custom_event_id}/registration", response_model=OkOut)
async def update_custom_registration(
    custom_event_id: int,
    payload: RegistrationUpdate,
    db: DBSession,
    user: CurrentUser,
):
    """更新自定义赛事的报名状态"""
    reg = await registration_service.update_custom_registration(
        db, user.user_id, custom_event_id, payload
    )
    if not reg:
        raise HTTPException(status_code=404, detail="自定义赛事不存在")
    return OkOut(ok=True, message="已更新")


@router.post("/races", response_model=AddRaceOut)
async def add_race(
    payload: AddRaceRequest,
    db: DBSession,
    user: CurrentUser,
):
    """添加赛事：数据库已有赛事直接收藏；否则新建自定义赛事"""
    e, ec, fav, reg = await registration_service.add_race(
        db,
        user.user_id,
        event_id=payload.event_id,
        event_name=payload.event_name,
        start_time=payload.start_time,
        province=payload.province,
        city=payload.city,
        location=payload.location,
        event_level=payload.event_level,
        registration_status=payload.registration_status,
        payment_status=payload.payment_status,
        lottery_status=payload.lottery_status,
        race_type=payload.race_type,
        fee=payload.fee,
    )
    return AddRaceOut(
        event_id=e.event_id if e else None,
        custom_event_id=ec.customize_id if ec else None,
        favorite_id=fav.favorite_id,
        registration_id=reg.registration_id,
    )


@router.delete("/races/{custom_event_id}", response_model=OkOut)
async def delete_custom_race(
    custom_event_id: int,
    db: DBSession,
    user: CurrentUser,
):
    """删除自定义赛事（软删除自定义赛事 + 收藏 + 报名记录）"""
    ok = await registration_service.delete_custom_race(db, user.user_id, custom_event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="自定义赛事不存在")
    return OkOut(ok=True, message="已删除")
