"""API 路由聚合"""
from fastapi import APIRouter

from app.api.v1 import events, favorites, registrations, users, pipeline, configs, rankings

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(events.router)
api_router.include_router(favorites.router)
api_router.include_router(registrations.router)
api_router.include_router(users.router)
api_router.include_router(pipeline.router)
api_router.include_router(configs.router)
api_router.include_router(rankings.router)
