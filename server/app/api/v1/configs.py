"""系统配置字典路由 —— 前台下拉框数据源（公开读，无需登录）"""

from fastapi import APIRouter

from app.deps import DBSession
from app.schemas.config import ConfigItem
from app.services import config_service

router = APIRouter(prefix="/configs", tags=["configs"])


@router.get("", response_model=dict[str, list[ConfigItem]])
async def list_configs(db: DBSession):
    """全量字典：{config_type: [{code, name, sort_order}...]}，前端一次拉齐缓存"""
    return await config_service.list_all_groups(db)


@router.get("/{config_type}", response_model=list[ConfigItem])
async def get_config_type(config_type: str, db: DBSession):
    """按类别取字典，如 GET /configs/age_group → [{code:'1', name:'34岁以下'}, ...]

    未知 config_type 返回空数组（不 404，前端按空处理更稳）。
    """
    return await config_service.list_by_type(db, config_type)
