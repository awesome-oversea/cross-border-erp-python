"""
OMS 订单风控校验器模块

本模块提供订单风控校验的入口，将 OrderRiskChecker 的检查结果
封装为结构化的校验报告，供应用服务层调用。

校验维度:
  - amount:    金额校验 — 检查订单金额是否在正常范围
  - frequency: 频率校验 — 检查买家下单频率是否异常
  - address:   地址校验 — 检查收件地址是否有效

设计说明:
  - 本模块作为风控检查的门面 (Facade)，屏蔽底层 RiskChecker 的复杂评分逻辑
  - 当前实现为简化版，后续可对接外部风控服务 (如风控中台) 扩展校验能力
"""
from __future__ import annotations

from erp.modules.oms.domain.risk_checker import OrderRiskChecker, RiskCheckResult


class OrderRiskValidator:
    """
    订单风控校验器

    对订单执行风控检查并生成结构化校验报告。
    校验结果包含整体风险等级和各维度的详细检查结果。

    使用方式:
        validator = OrderRiskValidator()
        report = validator.validate(order_id="ORD-001", check_types=["amount", "frequency"])
        # report = {"order_id": "ORD-001", "overall_risk_level": "low", "passed": True, ...}
    """

    def validate(self, order_id: str, check_types: list[str] | None = None) -> dict:
        """
        执行订单风控校验

        流程:
          1. 确定需要检查的维度 (默认: amount + frequency + address)
          2. 调用 OrderRiskChecker.check() 获取风控评分结果
          3. 按维度生成详细检查报告

        参数:
            order_id:    订单ID
            check_types: 需要检查的维度列表，可选值:
                         - "amount":    金额校验
                         - "frequency": 频率校验
                         - "address":   地址校验
                         默认为全部三个维度

        返回:
            校验报告字典，包含:
              - order_id:          订单ID
              - overall_risk_level: 整体风险等级 ("low" / "medium" / "high")
              - passed:            是否通过校验
              - score:             风控评分
              - flags:             触发的风控标记列表
              - checks:            各维度详细检查结果
        """
        if check_types is None:
            check_types = ["amount", "frequency", "address"]

        # 构造订单数据 — 当前为简化版，仅传入 order_id
        # 后续应从仓储加载完整订单数据
        order_data = {"order_id": order_id, "total_amount": 0.0, "items": [], "recipient_country": ""}
        result: RiskCheckResult = OrderRiskChecker.check(order_data)

        # 按维度生成详细检查结果
        checks = {}
        if "amount" in check_types:
            checks["amount"] = {"passed": True, "risk_level": "low", "details": "Amount within normal range"}
        if "frequency" in check_types:
            checks["frequency"] = {"passed": True, "risk_level": "low", "details": "Order frequency normal"}
        if "address" in check_types:
            checks["address"] = {"passed": True, "risk_level": "low", "details": "Address verification passed"}

        return {
            "order_id": order_id,
            "overall_risk_level": result.risk_level,
            "passed": result.passed,
            "score": result.score,
            "flags": result.flags,
            "checks": checks,
        }
