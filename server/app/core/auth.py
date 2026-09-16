"""JWT 认证工具（镜像 world-cup-prediction 模式）"""

from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError


def create_token(user_id: int, secret_key: str, expire_hours: int = 720) -> str:
    """生成 JWT token"""
    expire = datetime.utcnow() + timedelta(hours=expire_hours)
    payload = {"user_id": user_id, "exp": expire}
    return jwt.encode(payload, secret_key, algorithm="HS256")


def verify_token(token: str, secret_key: str) -> Optional[int]:
    """验证 token，返回 user_id 或 None"""
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return payload.get("user_id")
    except (JWTError, ValueError):
        return None
