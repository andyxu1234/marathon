from typing import Optional
from pydantic import BaseModel


class ConfigItem(BaseModel):
    """单个字典项（code 为字符串；业务列存 int，取用时 int(item.code)）"""
    code: str
    name: str
    sort_order: int = 0
    remark: Optional[str] = None


class ConfigGroup(BaseModel):
    """单类别字典"""
    config_type: str
    items: list[ConfigItem] = []
