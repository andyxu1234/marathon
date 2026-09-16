from typing import Optional, Generic, TypeVar, List, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """通用分页响应"""
    items: List[T]
    total: int
    page: int
    page_size: int


class OkOut(BaseModel):
    ok: bool = True
    message: Optional[str] = None
    data: Optional[Any] = Field(default=None, description="可选的附加返回数据")
