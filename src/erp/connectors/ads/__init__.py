"""
Amazon Ads API 连接器 (P5-005)

对接Amazon Advertising API:
  - Campaign管理: SP/SB/SD  campaigns
  - AdGroup管理
  - Keyword管理
  - 报告: 搜索词报告、活动报告、关键词报告

认证: OAuth2 refresh_token (与Amazon SP-API相同)
端点: https://advertising-api-{region}.amazon.com
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx

from erp.connectors.base import ConnectorConfig
from erp.shared.observability.logging import get_logger

logger = get_logger("erp.connector.ads")

ADS_ENDPOINTS = {
    "NA": "https://advertising-api-na.amazon.com",
    "EU": "https://advertising-api-eu.amazon.com",
    "FE": "https://advertising-api-fe.amazon.com",
}


class AmazonAdsConnector:
    """
    Amazon Ads API连接器

    支持SP/SB/SD三种广告类型的Campaign/AdGroup/Keyword管理，
    以及报告生成与下载。
    """

    def __init__(self, config: ConnectorConfig | None = None):
        self.config = config or ConnectorConfig(
            connector_id="amazon_ads", connector_name="Amazon Ads",
            connector_type="advertising",
            base_url="https://advertising-api-na.amazon.com",
        )
        self._http: httpx.AsyncClient | None = None
        self._token: str = ""
        self._token_expires: float = 0
        self._profile_id: str = ""

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            region = "EU" if (self.config.marketplace_id or "").startswith(("A2Q", "A2E")) else \
                     "FE" if (self.config.marketplace_id or "").startswith(("A1V", "A2I")) else "NA"
            self._http = httpx.AsyncClient(
                base_url=ADS_ENDPOINTS[region],
                timeout=httpx.Timeout(60, connect=10),
            )
        return self._http

    async def _get_token(self) -> str:
        if self._token and self._token_expires > datetime.now(UTC).timestamp():
            return self._token
        async with httpx.AsyncClient() as c:
            r = await c.post("https://api.amazon.com/auth/o2/token", json={
                "grant_type": "refresh_token", "refresh_token": self.config.refresh_token,
                "client_id": self.config.api_key, "client_secret": self.config.api_secret,
            }, timeout=10)
            d = r.json()
            self._token = d.get("access_token", "")
            self._token_expires = datetime.now(UTC).timestamp() + d.get("expires_in", 3600) - 60
        return self._token

    async def _headers(self) -> dict:
        if not self._profile_id:
            await self._resolve_profile()
        return {"Authorization": f"Bearer {await self._get_token()}",
                "Amazon-Advertising-API-ClientId": self.config.api_key,
                "Amazon-Advertising-API-Scope": self._profile_id,
                "Content-Type": "application/json"}

    async def _resolve_profile(self) -> str:
        """获取Amazon Ads Profile ID"""
        try:
            c = await self._client()
            r = await c.get("/v2/profiles", headers={
                "Authorization": f"Bearer {await self._get_token()}",
                "Amazon-Advertising-API-ClientId": self.config.api_key,
            })
            profiles = r.json()
            for p in profiles:
                if str(p.get("marketplaceId", "")) == self.config.marketplace_id:
                    self._profile_id = str(p.get("profileId", ""))
                    break
            if not self._profile_id and profiles:
                self._profile_id = str(profiles[0].get("profileId", ""))
        except Exception as e:
            logger.error("ads_resolve_profile_failed", error=str(e)[:200])

    async def list_campaigns(self, campaign_type: str = "sp") -> list[dict]:
        """获取广告活动列表"""
        c = await self._client(); h = await self._headers()
        endpoint = f"/v2/{campaign_type}/campaigns"
        try:
            r = await c.get(endpoint, headers=h, params={"pageSize": 100})
            r.raise_for_status(); return r.json()
        except Exception as e:
            logger.error("ads_list_campaigns_failed", error=str(e)[:200])
            return []

    async def list_ad_groups(self, campaign_id: str, campaign_type: str = "sp") -> list[dict]:
        """获取广告组列表"""
        c = await self._client(); h = await self._headers()
        try:
            r = await c.get(f"/v2/{campaign_type}/adGroups", headers=h,
                          params={"campaignIdFilter": campaign_id, "pageSize": 100})
            r.raise_for_status(); return r.json()
        except Exception as e:
            logger.error("ads_list_adgroups_failed", error=str(e)[:200])
            return []

    async def list_keywords(self, ad_group_id: str, campaign_type: str = "sp") -> list[dict]:
        """获取关键词列表"""
        c = await self._client(); h = await self._headers()
        try:
            r = await c.get(f"/v2/{campaign_type}/keywords", headers=h,
                          params={"adGroupIdFilter": ad_group_id, "pageSize": 100})
            r.raise_for_status(); return r.json()
        except Exception as e:
            logger.error("ads_list_keywords_failed", error=str(e)[:200])
            return []

    async def request_report(self, report_type: str, segment: str = "", metrics: list[str] | None = None) -> str:
        """请求生成广告报告"""
        c = await self._client(); h = await self._headers()
        payload = {
            "reportDate": datetime.now(UTC).strftime("%Y%m%d"),
            "metrics": ",".join(metrics or ["impressions", "clicks", "cost", "purchases", "sales"]),
        }
        if segment: payload["segment"] = segment
        try:
            r = await c.post(f"/v2/{report_type}/report", headers=h, json=payload)
            r.raise_for_status()
            return r.json().get("reportId", "")
        except Exception as e:
            logger.error("ads_request_report_failed", error=str(e)[:200])
            return ""

    async def get_report(self, report_id: str) -> dict:
        """获取已生成的报告"""
        c = await self._client(); h = await self._headers()
        try:
            r = await c.get(f"/v2/reports/{report_id}", headers=h)
            if r.status_code == 200:
                return r.json()
            return {"status": r.json().get("status", "in_progress")}
        except Exception as e:
            logger.error("ads_get_report_failed", error=str(e)[:200])
            return {"error": str(e)}

    async def download_report(self, report_id: str) -> list[dict]:
        """下载已完成的报告"""
        c = await self._client(); h = await self._headers()
        try:
            r = await c.get(f"/v2/reports/{report_id}/download", headers=h)
            r.raise_for_status(); return r.json()
        except Exception as e:
            logger.error("ads_download_report_failed", error=str(e)[:200])
            return []

    async def update_campaign_bid(self, campaign_id: str, bid: float, campaign_type: str = "sp") -> bool:
        """更新广告活动竞价"""
        c = await self._client(); h = await self._headers()
        try:
            r = await c.put(f"/v2/{campaign_type}/campaigns", headers=h, json=[{
                "campaignId": int(campaign_id), "bid": bid,
            }])
            r.raise_for_status(); return True
        except Exception as e:
            logger.error("ads_update_bid_failed", error=str(e)[:200])
            return False

    async def close(self):
        if self._http: await self._http.aclose(); self._http = None
