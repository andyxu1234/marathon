"""微信小程序登录客户端（镜像 world-cup-prediction 模式）"""

import httpx
from loguru import logger


class WeChatClient:
    """微信小程序登录客户端"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.client = httpx.AsyncClient(timeout=10.0)

    async def code_to_session(self, code: str) -> dict:
        """通过 code 换取 openid 和 session_key"""
        url = "https://api.weixin.qq.com/sns/jscode2session"
        params = {
            "appid": self.app_id,
            "secret": self.app_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            logger.error(f"WeChat login error: {data}")
            raise ValueError(f"WeChat login failed: {data.get('errmsg', 'unknown error')}")

        logger.info(f"WeChat login success, openid: {data.get('openid', '')[:8]}...")
        return data

    async def get_openid(self, code: str) -> str:
        """便捷方法：只获取 openid"""
        data = await self.code_to_session(code)
        return data["openid"]

    async def close(self):
        await self.client.aclose()
