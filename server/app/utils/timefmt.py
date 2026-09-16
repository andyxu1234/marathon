"""日期/时间格式化工具"""

from datetime import datetime, date
from typing import Optional


def fmt_dt(value, fmt: str = "%Y-%m-%d %H:%M") -> Optional[str]:
    """格式化 datetime/str → 'YYYY-MM-DD HH:MM'，失败返回 None"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.strftime(fmt)
    if isinstance(value, date):
        return value.strftime(fmt[:10] if fmt == "%Y-%m-%d %H:%M" else fmt)
    try:
        # 兼容字符串
        if "T" in str(value):
            return datetime.fromisoformat(str(value).replace("Z", "")).strftime(fmt)
        return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").strftime(fmt)
    except Exception:
        return str(value) if value else None


def fmt_date(value, fmt: str = "%Y-%m-%d") -> Optional[str]:
    """仅日期"""
    return fmt_dt(value, fmt)


def days_until(value) -> Optional[int]:
    """距离目标日期还有多少天（负数表示已过）"""
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            target = value.date()
        elif isinstance(value, date):
            target = value
        else:
            s = str(value)[:10]
            target = datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None
    return (target - date.today()).days


def month_key(value) -> Optional[str]:
    """'YYYY-MM' 用于按月分组"""
    formatted = fmt_date(value, "%Y-%m")
    return formatted
