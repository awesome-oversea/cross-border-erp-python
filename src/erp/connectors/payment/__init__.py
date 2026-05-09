"""
支付连接器 - PayPal/Stripe/支付宝/Payoneer 真实HTTP对接 (P5-007)

PayPal REST API v2: 订单创建/查询/退款/余额
Stripe API: PaymentIntent/退款/余额
Alipay: 交易创建/查询/退款
Payoneer: 余额查询
"""
from __future__ import annotations

import uuid

import httpx

from erp.connectors.base import ConnectorConfig, PaymentConnector, PaymentCreate, PaymentRefund, PaymentResult, RefundResult
from erp.shared.observability.logging import get_logger

logger = get_logger("erp.connector.payment")


class PaypalConnector(PaymentConnector):
    """PayPal REST API v2"""
    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="paypal", connector_name="PayPal",
            connector_type="payment", base_url="https://api-m.paypal.com"))
        self._http: httpx.AsyncClient | None = None
        self._token: str = ""

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None: self._http = httpx.AsyncClient(base_url=self.config.base_url, timeout=httpx.Timeout(30))
        return self._http

    async def _auth(self) -> str:
        if self._token: return self._token
        async with httpx.AsyncClient() as c:
            r = await c.post("https://api-m.paypal.com/v1/oauth2/token",
                auth=(self.config.api_key, self.config.api_secret), data={"grant_type": "client_credentials"}, timeout=10)
            self._token = r.json().get("access_token", "")
        return self._token

    async def _h(self) -> dict: return {"Authorization": f"Bearer {await self._auth()}", "Content-Type": "application/json"}

    async def create_payment(self, payment: PaymentCreate) -> PaymentResult:
        try:
            r = await (await self._client()).post("/v2/checkout/orders", headers=await self._h(), json={
                "intent": "CAPTURE", "purchase_units": [{"amount": {"currency_code": payment.currency, "value": str(payment.amount)}}]})
            d = r.json()
            return PaymentResult(success=r.status_code==201, payment_id=d.get("id",""),
                redirect_url=next((l["href"] for l in d.get("links",[]) if l["rel"]=="payer-action"),""),
                status=d.get("status","CREATED"), error_message="" if r.status_code==201 else str(d)[:200])
        except Exception as e: return PaymentResult(success=False, status="error", error_message=str(e)[:200])

    async def query_payment(self, payment_id: str) -> PaymentResult:
        try:
            r = await (await self._client()).get(f"/v2/checkout/orders/{payment_id}", headers=await self._h())
            d = r.json(); return PaymentResult(success=r.status_code==200, payment_id=payment_id, status=d.get("status","UNKNOWN"))
        except Exception as e: return PaymentResult(success=False, status="error", error_message=str(e)[:200])

    async def refund(self, refund: PaymentRefund) -> RefundResult:
        try:
            r = await (await self._client()).post(f"/v2/payments/captures/{refund.payment_id}/refund", headers=await self._h(),
                json={"amount": {"value": str(refund.refund_amount), "currency_code": refund.currency or "USD"}})
            d = r.json(); return RefundResult(success=r.status_code==201, refund_id=d.get("id",""),
                status="completed" if r.status_code==201 else "failed")
        except Exception as e: return RefundResult(success=False, status="error", error_message=str(e)[:200])

    async def get_balance(self, currency: str = "USD") -> dict:
        try:
            r = await (await self._client()).get("/v1/wallet/balances", headers=await self._h())
            for b in r.json() if isinstance(r.json(), list) else []:
                if b.get("currency_code")==currency: return {"currency":currency, "available":float(b.get("available",0))}
        except: pass
        return {"currency": currency, "available": 0}

    async def close(self):
        if self._http: await self._http.aclose(); self._http = None


class StripeConnector(PaymentConnector):
    """Stripe API"""
    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="stripe", connector_name="Stripe",
            connector_type="payment", base_url="https://api.stripe.com/v1"))
        self._http: httpx.AsyncClient | None = None
    async def _c(self) -> httpx.AsyncClient:
        if self._http is None: self._http = httpx.AsyncClient(base_url=self.config.base_url, timeout=httpx.Timeout(30),
            headers={"Authorization": f"Bearer {self.config.api_key}"})
        return self._http
    async def create_payment(self, p: PaymentCreate) -> PaymentResult:
        try:
            r = await (await self._c()).post("/payment_intents", data={"amount":int(p.amount*100), "currency":p.currency.lower()})
            d = r.json(); return PaymentResult(success=r.status_code==200, payment_id=d.get("id",""),
                redirect_url=d.get("next_action",{}).get("redirect_to_url",{}).get("url",""), status=d.get("status","requires_payment_method"))
        except Exception as e: return PaymentResult(success=False, status="error", error_message=str(e)[:200])
    async def query_payment(self, pid: str) -> PaymentResult:
        try:
            r = await (await self._c()).get(f"/payment_intents/{pid}")
            d = r.json(); return PaymentResult(success=r.status_code==200, payment_id=pid, status=d.get("status","unknown"))
        except Exception as e: return PaymentResult(success=False, status="error", error_message=str(e)[:200])
    async def refund(self, r: PaymentRefund) -> RefundResult:
        try:
            resp = await (await self._c()).post("/refunds", data={"payment_intent": r.payment_id, "amount": int(r.refund_amount*100)})
            d = resp.json(); return RefundResult(success=resp.status_code==200, refund_id=d.get("id",""),
                status="succeeded" if resp.status_code==200 else "failed")
        except Exception as e: return RefundResult(success=False, status="error", error_message=str(e)[:200])
    async def get_balance(self, currency: str = "USD") -> dict:
        try:
            r = await (await self._c()).get("/balance")
            for b in r.json().get("available", []):
                if b.get("currency")==currency.lower(): return {"currency":currency, "available":float(b.get("amount",0))/100}
        except: pass
        return {"currency": currency, "available": 0}
    async def close(self):
        if self._http: await self._http.aclose(); self._http = None


class AlipayConnector(PaymentConnector):
    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="alipay", connector_name="Alipay",
            connector_type="payment", base_url="https://openapi.alipay.com/gateway.do"))
    async def _call(self, method: str, biz: dict) -> dict:
        import json
        async with httpx.AsyncClient() as c:
            r = await c.post(self.config.base_url, params={"app_id":self.config.api_key,"method":method,"charset":"utf-8",
                "timestamp":__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"version":"1.0",
                "biz_content":json.dumps(biz)}, timeout=15)
            return r.json()
    async def create_payment(self, p: PaymentCreate) -> PaymentResult:
        r = await self._call("alipay.trade.create",{"out_trade_no":f"ERP-{uuid.uuid4().hex[:12]}","total_amount":str(p.amount),"subject":"ERP"})
        resp = r.get("alipay_trade_create_response",{})
        return PaymentResult(success=resp.get("code")=="10000", payment_id=resp.get("trade_no",""),
            status="WAIT_BUYER_PAY" if resp.get("code")=="10000" else "failed")
    async def query_payment(self, pid: str) -> PaymentResult:
        r = self._call("alipay.trade.query",{"trade_no":pid})
        resp = r.get("alipay_trade_query_response",{})
        return PaymentResult(success=resp.get("code")=="10000", payment_id=pid, status=resp.get("trade_status","unknown"))
    async def refund(self, r: PaymentRefund) -> RefundResult:
        resp = await self._call("alipay.trade.refund",{"trade_no":r.payment_id,"refund_amount":str(r.refund_amount)})
        d = resp.get("alipay_trade_refund_response",{})
        return RefundResult(success=d.get("code")=="10000", refund_id=d.get("trade_no",""),
            status="REFUND_SUCCESS" if d.get("code")=="10000" else "failed")
    async def get_balance(self, currency: str = "CNY") -> dict:
        return {"currency": currency, "available": 0}


class PayoneerConnector(PaymentConnector):
    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="payoneer", connector_name="Payoneer",
            connector_type="payment", base_url="https://api.payoneer.com/v2"))
    async def _h(self) -> dict: return {"Authorization": f"Bearer {self.config.access_token}", "Content-Type": "application/json"}
    async def get_balance(self, currency: str = "USD") -> dict:
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(f"{self.config.base_url}/accounts/balances", headers=await self._h())
                d = r.json(); return {"currency":currency, "available":float(d.get("availableBalance",0)),
                    "pending":float(d.get("pendingBalance",0))}
        except: return {"currency": currency, "available": 0, "pending": 0}
    async def create_payment(self, p: PaymentCreate) -> PaymentResult:
        return PaymentResult(success=False, status="not_supported", error_message="Payoneer does not support direct payment")
    async def query_payment(self, pid: str) -> PaymentResult:
        return PaymentResult(success=False, status="not_supported")
    async def refund(self, r: PaymentRefund) -> RefundResult:
        return RefundResult(success=False, status="not_supported")
