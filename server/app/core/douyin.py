"""抖音 / 字节跳动小程序登录客户端

官方文档：https://developer.open-douyin.com/docs/resource/zh-CN/mini-app/develop/server/basic-abilities/log-in/code-2-session

与微信 jscode2session 的关键差异：
  - HTTP Method：POST（不是 GET）
  - 请求格式：application/json body（不是 query string）
  - 响应结构：{ err_no, err_tips, data: { openid, session_key, unionid? } }
    （不是微信顶层直接返回 openid）
"""

import httpx
from loguru import logger


class DouyinClient:
    """抖音小程序登录客户端 —— jscode2session"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.client = httpx.AsyncClient(timeout=10.0)

    async def code_to_session(self, code: str) -> dict:
        """通过 code 换取 openid 和 session_key"""
        url = "https://developer.toutiao.com/api/apps/v2/jscode2session"
        payload = {
            "appid": self.app_id,
            "secret": self.app_secret,
            "code": code,
        }
        resp = await self.client.post(
            url,
            json=payload,
            headers={"content-type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

        # 抖音错误码：err_no=0 表示成功
        if data.get("err_no") != 0:
            logger.error(f"Douyin login error: {data}")
            raise ValueError(
                f"Douyin login failed: {data.get('err_tips', 'unknown error')} "
                f"(err_no={data.get('err_no')})"
            )

        logger.info(f"Douyin login success, openid: {data.get('data', {}).get('openid', '')[:8]}...")
        return data

    async def get_openid(self, code: str) -> str:
        """便捷方法：只获取 openid"""
        data = await self.code_to_session(code)
        return data["data"]["openid"]

    async def close(self):
        await self.client.aclose()
