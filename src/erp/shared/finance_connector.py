"""
外部财务系统连接器适配层 (P5-010)

支持推送凭证到:
  - 金蝶云星空 (Kingdee)
  - 用友U8+/U8Cloud (Yonyou)

通过统一接口 push_voucher() 屏蔽各系统差异。
"""
from __future__ import annotations

import httpx

from erp.shared.observability.logging import get_logger

logger = get_logger("erp.finance_connector")


class KingdeeClient:
    """金蝶云星空API客户端: 凭证推送,需配置api_key/api_secret"""
    """金蝶云星空API客户端"""
    def __init__(self, api_key: str = "", api_secret: str = "", base_url: str = "https://api.kingdee.com/api"):
        self._base = base_url
        self._auth = (api_key, api_secret)
        self._token: str = ""

    async def _login(self) -> str:
        if self._token: return self._token
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self._base}/auth", json={"appId": self._auth[0], "appSecret": self._auth[1]}, timeout=10)
            self._token = r.json().get("access_token", "")
        return self._token

    async def push_voucher(self, entries: list[dict], date: str = "", desc: str = "") -> dict:
        try:
            r = await httpx.AsyncClient().post(f"{self._base}/v1/voucher/push", headers={
                "Authorization": f"Bearer {await self._login()}", "Content-Type": "application/json",
            }, json={"date": date, "entries": entries, "description": desc}, timeout=15)
            d = r.json()
            return {"success": r.status_code == 200, "id": d.get("id", ""),
                    "status": "pushed" if r.status_code == 200 else "failed"}
        except Exception as e: return {"success": False, "error": str(e)[:200]}


class YonyouClient:
    """用友U8+API客户端: 凭证推送,需配置accId/token"""
    """用友U8+API客户端"""
    def __init__(self, api_key: str = "", api_secret: str = "", base_url: str = "https://api.yonyou.com/api"):
        self._base = base_url
        self._auth = (api_key, api_secret)

    async def push_voucher(self, entries: list[dict], date: str = "", desc: str = "") -> dict:
        try:
            r = await httpx.AsyncClient().post(f"{self._base}/voucher/save", json={
                "accId": self._auth[0], "token": self._auth[1],
                "date": date, "entries": entries, "desc": desc,
            }, timeout=15)
            d = r.json()
            return {"success": d.get("code") == "200", "id": d.get("data", {}).get("id", ""),
                    "status": "pushed" if d.get("code") == "200" else "failed"}
        except Exception as e: return {"success": False, "error": str(e)[:200]}
