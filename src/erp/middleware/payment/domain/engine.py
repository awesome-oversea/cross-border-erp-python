"""
支付聚合中台引擎

职责:
  - 统一支付接口: 屏蔽PayPal/Stripe/支付宝等渠道差异
  - 退款处理: 统一退款流程
  - 对账: 支付流水与银行对账
  - 结汇提现: 一站式管理收款/结汇

被调用方: OMS(订单支付), CRM(退款), FMS(对账)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PaymentChannel(StrEnum):
    PAYPAL = "paypal"
    STRIPE = "stripe"
    ALIPAY = "alipay"
    WECHAT = "wechat"
    PAYONEER = "payoneer"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass
class PaymentRequest:
    channel: str = ""
    amount: float = 0.0
    currency: str = "USD"
    order_id: str = ""
    description: str = ""


@dataclass
class PaymentResult:
    success: bool = False
    payment_id: str = ""
    status: str = ""
    error: str = ""


class PaymentEngine:
    """支付聚合引擎 - 统一支付/退款/对账/结汇"""

    SUPPORTED_CHANNELS = {"paypal", "stripe", "alipay", "wechat", "payoneer"}

    @staticmethod
    def validate_payment(req: PaymentRequest) -> list[str]:
        """校验支付请求参数"""
        errors = []
        if req.amount <= 0:
            errors.append("支付金额必须大于0")
        if req.channel not in PaymentEngine.SUPPORTED_CHANNELS:
            errors.append(f"不支持的支付渠道: {req.channel}")
        if not req.order_id:
            errors.append("订单ID不能为空")
        return errors

    @staticmethod
    def validate_refund(amount: float, original_amount: float) -> list[str]:
        """校验退款金额"""
        errors = []
        if amount <= 0:
            errors.append("退款金额必须大于0")
        if amount > original_amount:
            errors.append("退款金额不能超过原支付金额")
        return errors

    @staticmethod
    def calc_fee(amount: float, channel: str) -> float:
        """计算支付手续费"""
        fee_rates = {"paypal": 0.029, "stripe": 0.028, "alipay": 0.006,
                     "wechat": 0.006, "payoneer": 0.01}
        rate = fee_rates.get(channel, 0.03)
        return round(amount * rate, 2)

    @staticmethod
    def calc_settlement_amount(channel: str, total: float, fx_rate: float = 1.0) -> dict:
        """计算结汇金额(扣除手续费后)"""
        fee = PaymentEngine.calc_fee(total, channel)
        net = round((total - fee) * fx_rate, 2)
        return {"total": total, "fee": fee, "fx_rate": fx_rate, "net": net}


class PaymentEnhancedService:
    """批量付款+自动对账+追款(V4 10.3)"""

    @staticmethod
    def batch_pay(payments: list[dict]) -> dict:
        total = len(payments)
        processed = sum(1 for p in payments if p.get("amount", 0) > 0)
        return {"total": total, "processed": processed, "amount": round(sum(p.get("amount",0) for p in payments), 2)}

    @staticmethod
    def auto_reconcile(bank_stmts: list[dict], payment_logs: list[dict]) -> list[dict]:
        diffs = []
        for bs in bank_stmts:
            match = [p for p in payment_logs if p.get("id") == bs.get("ref_id") and abs(p.get("amount",0) - bs.get("amount",0)) < 0.01]
            if not match:
                diffs.append({"ref": bs.get("ref_id"), "bank_amt": bs.get("amount"), "status": "unmatched"})
        return diffs

    @staticmethod
    def amazon_collection(transactions: list[dict]) -> dict:
        pending = [t for t in transactions if t.get("status") == "pending"]
        return {"total": len(transactions), "pending": len(pending), "amount_pending": round(sum(t.get("amount",0) for t in pending), 2)}
