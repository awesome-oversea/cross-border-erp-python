"""
BI 领域服务 - 商业智能域的纯业务规则

本模块定义了指标、告警、报表三个核心领域服务，
所有方法均为无状态纯函数，不依赖数据库或外部 IO，
仅对输入进行校验和计算，确保业务规则的可测试性。
"""

# ──── 常量定义 ────

VALID_PERIOD_TYPES = {"hourly", "daily", "weekly", "monthly", "quarterly", "yearly"}
"""合法的周期类型集合，用于指标值录入时的校验"""

VALID_METRIC_CATEGORIES = {"sales", "inventory", "finance", "logistics", "customer", "advertising", "general"}
"""合法的指标分类集合"""

VALID_COMPARE_OPERATORS = {"gt", "gte", "lt", "lte", "eq", "neq"}
"""合法的比较运算符集合，用于告警阈值比较"""


class MetricDomainService:
    """
    指标领域服务 - 指标元数据的校验与数值计算

    职责:
    1. 校验指标编码、分类、刷新频率是否合法
    2. 计算环比变化率
    3. 计算移动平均线
    """

    @staticmethod
    def validate_metric(metric_code: str, metric_category: str, refresh_frequency: str) -> list[str]:
        """
        校验指标元数据是否合法

        Args:
            metric_code: 指标编码，至少 2 个字符
            metric_category: 指标分类，必须在 VALID_METRIC_CATEGORIES 中
            refresh_frequency: 刷新频率，必须在 VALID_PERIOD_TYPES 中

        Returns:
            校验错误列表，为空表示校验通过
        """
        errors: list[str] = []
        if not metric_code or len(metric_code) < 2:
            errors.append("Metric code must be at least 2 characters")
        if metric_category not in VALID_METRIC_CATEGORIES:
            errors.append(f"Invalid metric category: {metric_category}")
        if refresh_frequency not in VALID_PERIOD_TYPES:
            errors.append(f"Invalid refresh frequency: {refresh_frequency}")
        return errors

    @staticmethod
    def calculate_change_rate(current_value: float, previous_value: float) -> float:
        """
        计算环比变化率

        公式: (current - previous) / |previous| * 100

        特殊处理:
        - previous 为 0 且 current 也为 0 → 返回 0.0
        - previous 为 0 但 current 不为 0 → 返回 100.0（表示无限增长）
        """
        if previous_value == 0:
            return 0.0 if current_value == 0 else 100.0
        return round((current_value - previous_value) / abs(previous_value) * 100, 2)

    @staticmethod
    def calculate_moving_average(values: list[float], window: int = 7) -> list[float]:
        """
        计算移动平均线

        对每个数据点，取其前 window-1 个点到当前点的平均值。
        不足 window 个点时，使用实际可用点数计算。

        Args:
            values: 数值序列
            window: 移动窗口大小，默认 7（周维度）

        Returns:
            与输入等长的移动平均序列
        """
        if not values or window <= 0:
            return []
        result = []
        for i in range(len(values)):
            start = max(0, i - window + 1)
            window_values = values[start:i + 1]
            result.append(round(sum(window_values) / len(window_values), 2))
        return result


class AlertDomainService:
    """
    告警领域服务 - 阈值比较与告警规则校验

    职责:
    1. 根据比较运算符判断当前值是否触发告警
    2. 校验告警规则的运算符和阈值是否合法
    """

    _OPERATORS: dict[str, callable] = {
        "gt": lambda v, t: v > t,
        "gte": lambda v, t: v >= t,
        "lt": lambda v, t: v < t,
        "lte": lambda v, t: v <= t,
        "eq": lambda v, t: v == t,
        "neq": lambda v, t: v != t,
    }
    """运算符到比较函数的映射表"""

    @staticmethod
    def evaluate_threshold(current_value: float, operator: str, threshold: float) -> bool:
        """
        评估当前值是否满足告警阈值条件

        Args:
            current_value: 当前实际值
            operator: 比较运算符 (gt/gte/lt/lte/eq/neq)
            threshold: 阈值

        Returns:
            True 表示触发告警，False 表示未触发
        """
        op_func = AlertDomainService._OPERATORS.get(operator)
        return op_func(current_value, threshold) if op_func else False

    @staticmethod
    def validate_alert_rule(operator: str, threshold: float) -> list[str]:
        """
        校验告警规则参数是否合法

        Args:
            operator: 比较运算符，必须在 VALID_COMPARE_OPERATORS 中
            threshold: 阈值（当前仅校验运算符）

        Returns:
            校验错误列表，为空表示校验通过
        """
        errors: list[str] = []
        if operator not in VALID_COMPARE_OPERATORS:
            errors.append(f"Invalid operator: {operator}")
        return errors


class ReportDomainService:
    """
    报表领域服务 - 报表配置校验与数值聚合

    职责:
    1. 校验报表的周期类型和维度配置
    2. 对数值序列执行聚合计算（sum/avg/max/min/count）
    """

    @staticmethod
    def validate_report_config(period_type: str, dimensions: list[str]) -> list[str]:
        """
        校验报表配置是否合法

        Args:
            period_type: 周期类型，必须在 VALID_PERIOD_TYPES 中
            dimensions: 维度列表，至少包含一个维度

        Returns:
            校验错误列表，为空表示校验通过
        """
        errors: list[str] = []
        if period_type not in VALID_PERIOD_TYPES:
            errors.append(f"Invalid period type: {period_type}")
        if not dimensions:
            errors.append("At least one dimension is required")
        return errors

    @staticmethod
    def aggregate_values(values: list[float], aggregation: str = "sum") -> float:
        """
        对数值序列执行聚合计算

        Args:
            values: 数值序列
            aggregation: 聚合方式，支持 sum/avg/max/min/count

        Returns:
            聚合结果，空序列返回 0.0
        """
        if not values:
            return 0.0
        if aggregation == "sum":
            return round(sum(values), 2)
        elif aggregation == "avg":
            return round(sum(values) / len(values), 2)
        elif aggregation == "max":
            return round(max(values), 2)
        elif aggregation == "min":
            return round(min(values), 2)
        elif aggregation == "count":
            return float(len(values))
        return 0.0


class RealTimeSalesService:
    @staticmethod
    def rank(sales_data: list[dict], by: str = "sku", top: int = 10) -> list[dict]:
        ranked = sorted(sales_data, key=lambda x: x.get("sales", 0), reverse=True)
        return [{"rank": i+1, by: r.get(by), "sales": r.get("sales", 0),
                 "qty": r.get("qty", 0), "change": r.get("change", 0)} for i, r in enumerate(ranked[:top])]

    @staticmethod
    def mom(periods: list[dict]) -> list[dict]:
        return [{"period": p.get("period"), "value": p.get("value", 0),
                 "mom": round((p.get("value",0)-periods[i-1].get("value",0))/max(periods[i-1].get("value",0),1)*100,2)
                 if i > 0 and periods[i-1].get("value",0) > 0 else 0} for i, p in enumerate(periods)]


class BusinessAlertCategorizer:
    CATEGORIES = {"inventory": "库存预警", "profit": "利润预警", "logistics": "物流预警",
                  "ad": "广告预警", "order": "订单预警"}
    @staticmethod
    def categorize(t: str) -> str: return BusinessAlertCategorizer.CATEGORIES.get(t, "其他")
    @staticmethod
    def sort(alerts: list[dict]) -> list[dict]:
        levels = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return sorted(alerts, key=lambda a: levels.get(a.get("level", "low"), 99))


class KpiEvaluationService:
    """KPI目标与考核 (P6-010): 评分、趋势、达成率"""
    @staticmethod
    def achievement(actual: float, target: float, direction: str = "up") -> dict:
        rate = round(actual / target * 100, 2) if target > 0 else 0
        met = (actual >= target) if direction == "up" else (actual <= target)
        return {"actual": actual, "target": target, "rate": rate, "met": met,
                "status": "exceeded" if rate >= 120 else ("achieved" if met else "missed")}

    @staticmethod
    def scorecard(kpis: list[dict]) -> dict:
        total = len(kpis)
        met = sum(1 for k in kpis if k.get("met"))
        return {"total_kpis": total, "met": met, "rate": round(met/max(total,1)*100, 2),
                "grade": "A" if met/total >= 0.9 else ("B" if met/total >= 0.7 else "C") if total > 0 else "N/A"}


class ProductDeepIndicatorService:
    """产品表现11项深度指标 (P6-016): 销售分布/退款/广告/排名/库存/转化"""
    @staticmethod
    def calculate(sales: list[dict], refunds: list[dict], ads: list[dict]) -> dict:
        total_sales = sum(s.get("amount", 0) for s in sales)
        total_qty = sum(s.get("qty", 0) for s in sales)
        total_refund = sum(r.get("amount", 0) for r in refunds)
        ad_cost = sum(a.get("cost", 0) for a in ads)
        ad_sales = sum(a.get("sales", 0) for a in ads)
        return {"total_sales": round(total_sales, 2), "total_qty": total_qty,
                "refund_rate": round(total_refund/total_sales*100, 2) if total_sales > 0 else 0,
                "ad_ratio": round(ad_cost/total_sales*100, 2) if total_sales > 0 else 0,
                "acos": round(ad_cost/max(ad_sales,1)*100, 2) if ad_sales > 0 else 0,
                "net_profit": round(total_sales - total_refund - ad_cost, 2)}


class DataQualityService:
    """数据质量校验 (P6-004): 完整性/一致性/延迟/重复"""
    @staticmethod
    def completeness(expected: int, actual: int) -> dict:
        rate = round(actual / expected * 100, 2) if expected > 0 else 0
        return {"expected": expected, "actual": actual, "rate": rate, "passed": rate >= 95}

    @staticmethod
    def duplicates(ids: list[str]) -> dict:
        dupes = len(ids) - len(set(ids))
        return {"total": len(ids), "duplicates": dupes, "passed": dupes == 0}

    @staticmethod
    def lag(seconds: float, threshold: float = 300) -> dict:
        return {"lag_s": seconds, "threshold": threshold, "passed": seconds <= threshold}

    @staticmethod
    def score(checks: list[dict]) -> dict:
        total = len(checks)
        passed = sum(1 for c in checks if c.get("passed"))
        return {"total": total, "passed": passed, "failed": total - passed,
                "score": round(passed / total * 100, 2) if total > 0 else 0}


class CustomReportService:
    """自定义报告 (P6-008): 维度/指标/筛选自定义"""
    @staticmethod
    def validate(cfg: dict) -> list[str]:
        e = []
        if not cfg.get("metrics"): e.append("至少选择一个指标")
        if not cfg.get("dimensions"): e.append("至少选择一个维度")
        if cfg.get("page_size", 20) > 1000: e.append("每页最多1000条")
        return e

    @staticmethod
    def summarize(data: list[dict], metrics: list[str]) -> dict:
        s = {}
        for m in metrics:
            vals = [d.get(m, 0) for d in data if d.get(m) is not None]
            s[m] = {"sum": round(sum(vals), 2), "avg": round(sum(vals)/max(len(vals),1), 2),
                    "min": min(vals) if vals else 0, "max": max(vals) if vals else 0,
                    "count": len(vals)} if vals else {"sum": 0, "avg": 0, "min": 0, "max": 0, "count": 0}
        return s
