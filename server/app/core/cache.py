"""内存缓存（cachetools TTLCache，镜像参考项目轻量方案）"""

from typing import Any, Optional
from cachetools import TTLCache
from loguru import logger

# 默认 TTL 5 分钟，最多 512 条
_cache: TTLCache = TTLCache(maxsize=512, ttl=300)


def get_cache_stats() -> dict:
    return {"size": len(_cache), "maxsize": _cache.maxsize, "ttl": _cache.ttl}


def clear_all_caches() -> None:
    _cache.clear()
    logger.info("All caches cleared")


def cache_get(key: str) -> Optional[Any]:
    return _cache.get(key)


def cache_set(key: str, value: Any) -> None:
    _cache[key] = value
