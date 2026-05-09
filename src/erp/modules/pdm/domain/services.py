"""
PDM 领域服务模块 - 封装产品域的核心业务规则

本模块包含 PDM 域的所有领域服务，负责：
  - 状态机转换规则校验（SPU状态、项目阶段、选品状态）
  - 业务数据校验（SKU维度、IP记录、选品采集）
  - 业务计算逻辑（选品评分、项目完成度、风险评估）
  - 商标冲突检测

领域服务不依赖基础设施层，仅操作纯领域模型和基础类型。

包含的领域服务：
  - SPUDomainService: SPU状态机与审核校验
  - SKUDomainService: SKU维度校验与创建前置检查
  - ProductProjectDomainService: 产品项目阶段流转与完成度计算
  - ProductCollectionDomainService: 选品采集状态流转与评分算法
  - IPRecordDomainService: 知识产权记录校验与风险评估
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erp.modules.pdm.domain.models import SPU

SPU_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["pending_review", "cancelled"],
    "pending_review": ["approved", "rejected", "cancelled"],
    "rejected": ["draft", "cancelled"],
    "approved": ["listed", "cancelled"],
    "listed": ["delisted", "discontinued", "cancelled"],
    "delisted": ["listed", "discontinued", "cancelled"],
    "discontinued": [],
    "cancelled": [],
}

PROJECT_STAGE_TRANSITIONS: dict[str, list[str]] = {
    "proposing": ["researching", "cancelled"],
    "researching": ["designing", "proposing", "cancelled"],
    "designing": ["sourcing", "researching", "cancelled"],
    "sourcing": ["sampling", "designing", "cancelled"],
    "sampling": ["testing", "sourcing", "cancelled"],
    "testing": ["pre_production", "sampling", "cancelled"],
    "pre_production": ["mass_production", "testing", "cancelled"],
    "mass_production": ["launched", "pre_production", "cancelled"],
    "launched": ["completed", "cancelled"],
    "completed": [],
    "cancelled": [],
}

SKU_DIMENSION_LIMITS = {
    "weight_max": 50.0,
    "length_max": 200.0,
    "width_max": 200.0,
    "height_max": 200.0,
    "cost_price_max": 100000.0,
}


class SPUDomainService:
    """SPU领域服务 - 封装SPU状态机转换规则与审核前置校验

    SPU状态流转路径：
      draft → pending_review → approved → listed → delisted → discontinued
                                  ↓            ↓
                              rejected      cancelled

    每个状态转换都有前置条件校验：
      - pending_review: 必须有名称和分类
      - approved: 必须有分类和品牌
      - listed: 必须有主图
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """判断SPU是否可以从当前状态转换到目标状态

        Args:
            current_status: 当前SPU状态
            target_status: 目标SPU状态

        Returns:
            True表示允许转换，False表示不允许
        """
        return target_status in SPU_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_for_review(spu: SPU) -> list[str]:
        """校验SPU是否满足提交审核的前置条件

        提交审核前必须具备：名称、分类

        Args:
            spu: SPU领域模型实例

        Returns:
            校验错误列表，空列表表示校验通过
        """
        errors: list[str] = []
        if not spu.name:
            errors.append("SPU must have a name before submitting for review")
        if not spu.category_id:
            errors.append("SPU must have a category before review")
        return errors

    @staticmethod
    def validate_for_approval(spu: SPU) -> list[str]:
        """校验SPU是否满足审批通过的前置条件

        审批通过前必须具备：分类、品牌

        Args:
            spu: SPU领域模型实例

        Returns:
            校验错误列表，空列表表示校验通过
        """
        errors: list[str] = []
        if not spu.category_id:
            errors.append("SPU must have a category before approval")
        if not spu.brand_id:
            errors.append("SPU must have a brand before approval")
        return errors

    @staticmethod
    def validate_for_listing(spu: SPU) -> list[str]:
        """校验SPU是否满足上架的前置条件

        上架前必须具备：主图

        Args:
            spu: SPU领域模型实例

        Returns:
            校验错误列表，空列表表示校验通过
        """
        errors: list[str] = []
        if not spu.main_image:
            errors.append("SPU must have a main image before listing")
        return errors


class SKUDomainService:
    """SKU领域服务 - 封装SKU维度校验与创建前置检查

    SKU创建前需要校验：
      - 物理维度（重量、长宽高）在合理范围内
      - 成本价格在合理范围内
      - 所属SPU状态允许创建SKU
    """

    @staticmethod
    def validate_dimensions(weight: float, length: float, width: float, height: float, cost_price: float) -> list[str]:
        """校验SKU的物理维度和成本价格是否在合理范围内

        Args:
            weight: 重量(kg)，范围 [0, 50]
            length: 长度(cm)，范围 [0, 200]
            width: 宽度(cm)，范围 [0, 200]
            height: 高度(cm)，范围 [0, 200]
            cost_price: 成本价，范围 [0, 100000]

        Returns:
            校验错误列表，空列表表示校验通过
        """
        errors: list[str] = []
        if weight < 0 or weight > SKU_DIMENSION_LIMITS["weight_max"]:
            errors.append(f"Weight must be between 0 and {SKU_DIMENSION_LIMITS['weight_max']} kg")
        if length < 0 or length > SKU_DIMENSION_LIMITS["length_max"]:
            errors.append(f"Length must be between 0 and {SKU_DIMENSION_LIMITS['length_max']} cm")
        if width < 0 or width > SKU_DIMENSION_LIMITS["width_max"]:
            errors.append(f"Width must be between 0 and {SKU_DIMENSION_LIMITS['width_max']} cm")
        if height < 0 or height > SKU_DIMENSION_LIMITS["height_max"]:
            errors.append(f"Height must be between 0 and {SKU_DIMENSION_LIMITS['height_max']} cm")
        if cost_price < 0 or cost_price > SKU_DIMENSION_LIMITS["cost_price_max"]:
            errors.append(f"Cost price must be between 0 and {SKU_DIMENSION_LIMITS['cost_price_max']}")
        return errors

    @staticmethod
    def can_create_for_spu(spu: SPU) -> bool:
        """判断SPU状态是否允许创建SKU

        已取消(discontinued)和已停售(cancelled)的SPU不允许创建新SKU

        Args:
            spu: SPU领域模型实例

        Returns:
            True表示允许创建，False表示不允许
        """
        return spu.status not in ("cancelled", "discontinued")


class ProductProjectDomainService:
    """产品项目领域服务 - 封装项目阶段流转规则与完成度计算

    产品开发项目阶段流转路径：
      proposing → researching → designing → sourcing → sampling
      → testing → pre_production → mass_production → launched → completed

    任何阶段都可以回退到上一阶段或取消
    """

    @staticmethod
    def can_transition(current_stage: str, target_stage: str) -> bool:
        """判断项目是否可以从当前阶段转换到目标阶段

        Args:
            current_stage: 当前项目阶段
            target_stage: 目标项目阶段

        Returns:
            True表示允许转换，False表示不允许
        """
        return target_stage in PROJECT_STAGE_TRANSITIONS.get(current_stage, [])

    @staticmethod
    def calculate_completion_percentage(stage: str) -> float:
        """根据当前阶段计算项目完成度百分比

        完成度基于阶段在总流程中的位置线性计算：
          proposing=10%, researching=20%, ..., completed=100%

        Args:
            stage: 当前项目阶段

        Returns:
            完成度百分比，0.0~100.0
        """
        stages = [
            "proposing", "researching", "designing", "sourcing", "sampling",
            "testing", "pre_production", "mass_production", "launched", "completed",
        ]
        if stage == "cancelled":
            return 0.0
        idx = stages.index(stage) if stage in stages else 0
        return round(idx / len(stages) * 100, 1)


COLLECTION_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "collected": ["analyzing", "ignored"],
    "analyzing": ["selected", "ignored"],
    "selected": ["converting", "ignored"],
    "converting": ["converted", "failed"],
    "converted": [],
    "failed": ["converting"],
    "ignored": ["collected"],
}

IP_TYPES = {"trademark", "patent", "copyright"}
RISK_LEVELS = {"none", "low", "medium", "high", "critical"}
COLLECTION_TYPES = {"manual", "keyword", "category_url", "monitor"}


class ProductCollectionDomainService:
    """选品采集领域服务 - 封装选品状态流转与评分算法

    选品状态流转路径：
      collected → analyzing → selected → converting → converted
                    ↓            ↓           ↓
                 ignored      ignored      failed

    评分算法基于四个维度加权计算：
      - 月销量(30分): ≥1000→30, ≥500→20, ≥100→10
      - 平均评分(25分): ≥4.5→25, ≥4.0→15, ≥3.5→5
      - 评论数(20分): ≥500→20, ≥100→10, ≥20→5
      - 价格区间(25分): 10~50→25, 5~100→15, >0→5
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """判断选品记录是否可以从当前状态转换到目标状态

        Args:
            current_status: 当前选品状态
            target_status: 目标选品状态

        Returns:
            True表示允许转换，False表示不允许
        """
        return target_status in COLLECTION_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def calculate_selection_score(sales_data: dict, review_data: dict, price: float) -> float:
        """计算选品评分 - 基于销量、评分、评论数和价格四个维度

        评分维度及权重：
          1. 月销量(最高30分): 衡量市场需求热度
          2. 平均评分(最高25分): 衡量产品口碑质量
          3. 评论数(最高20分): 衡量市场活跃度
          4. 价格区间(最高25分): 跨境电商最优价格区间为$10~$50

        Args:
            sales_data: 销量数据，包含 monthly_sales 字段
            review_data: 评论数据，包含 avg_rating 和 review_count 字段
            price: 产品价格(USD)

        Returns:
            综合评分，0.0~100.0，保留1位小数
        """
        score = 0.0
        monthly_sales = sales_data.get("monthly_sales", 0)
        if monthly_sales >= 1000:
            score += 30
        elif monthly_sales >= 500:
            score += 20
        elif monthly_sales >= 100:
            score += 10
        avg_rating = review_data.get("avg_rating", 0)
        if avg_rating >= 4.5:
            score += 25
        elif avg_rating >= 4.0:
            score += 15
        elif avg_rating >= 3.5:
            score += 5
        review_count = review_data.get("review_count", 0)
        if review_count >= 500:
            score += 20
        elif review_count >= 100:
            score += 10
        elif review_count >= 20:
            score += 5
        if 10 <= price <= 50:
            score += 25
        elif 5 <= price <= 100:
            score += 15
        elif price > 0:
            score += 5
        return round(min(score, 100.0), 1)

    @staticmethod
    def validate_collection(source_platform: str, source_url: str) -> list[str]:
        """校验选品采集数据的基本完整性

        Args:
            source_platform: 来源平台标识（如amazon、aliexpress）
            source_url: 来源商品URL

        Returns:
            校验错误列表，空列表表示校验通过
        """
        errors: list[str] = []
        if not source_platform:
            errors.append("Source platform is required")
        if not source_url:
            errors.append("Source URL is required")
        return errors


class IPRecordDomainService:
    """知识产权记录领域服务 - 封装IP记录校验与风险评估

    支持的IP类型：trademark(商标)、patent(专利)、copyright(版权)
    风险等级：none → low → medium → high → critical

    商标冲突检测逻辑：产品名称包含已注册商标名称即视为冲突
    """

    @staticmethod
    def validate_ip_record(ip_type: str, risk_level: str) -> list[str]:
        """校验IP记录的类型和风险等级是否合法

        Args:
            ip_type: IP类型，必须为 trademark/patent/copyright 之一
            risk_level: 风险等级，必须为 none/low/medium/high/critical 之一

        Returns:
            校验错误列表，空列表表示校验通过
        """
        errors: list[str] = []
        if ip_type not in IP_TYPES:
            errors.append(f"Invalid IP type '{ip_type}', allowed: {', '.join(sorted(IP_TYPES))}")
        if risk_level not in RISK_LEVELS:
            errors.append(f"Invalid risk level '{risk_level}', allowed: {', '.join(sorted(RISK_LEVELS))}")
        return errors

    @staticmethod
    def assess_risk(ip_records: list[dict]) -> str:
        """评估一组IP记录的综合风险等级

        取所有记录中最高的风险等级作为综合风险等级

        Args:
            ip_records: IP记录列表，每条记录包含 risk_level 字段

        Returns:
            综合风险等级：none/low/medium/high/critical
        """
        if not ip_records:
            return "none"
        risk_order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}
        max_risk = "none"
        for r in ip_records:
            level = r.get("risk_level", "none")
            if risk_order.get(level, 0) > risk_order.get(max_risk, 0):
                max_risk = level
        return max_risk

    @staticmethod
    def check_trademark_conflict(product_name: str, trademarks: list[dict]) -> list[dict]:
        """检测产品名称是否与已注册商标存在冲突

        冲突判定规则：产品名称(小写)包含商标名称(小写)即视为冲突

        Args:
            product_name: 待检测的产品名称
            trademarks: 已注册商标列表，每条包含 ip_name、ip_number、risk_level 字段

        Returns:
            冲突的商标列表，空列表表示无冲突
        """
        conflicts = []
        name_lower = product_name.lower()
        for tm in trademarks:
            tm_name = tm.get("ip_name", "").lower()
            if tm_name and tm_name in name_lower:
                conflicts.append(tm)
        return conflicts


# ---------------------------------------------------------------------------
# 选品提报与审核 (P2-012)
# ---------------------------------------------------------------------------
# 提报流程: 提报 → 分配 → 认领 → 审核 → 生成SKU → 开发任务
# 支持来源: 人工提报/1688选品/出单产品/PMS AI建议/供应商推荐
# ---------------------------------------------------------------------------
SUBMISSION_SOURCES = {"manual", "1688", "selling", "pms_ai", "supplier"}
SUBMISSION_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "submitted": ["assigned", "rejected"],
    "assigned": ["claimed", "rejected"],
    "claimed": ["approved", "rejected"],
    "approved": ["sku_generated", "cancelled"],
    "sku_generated": ["project_created"],
    "project_created": [],
    "rejected": ["resubmitted"],
    "resubmitted": ["assigned", "rejected"],
    "cancelled": [],
}


class SelectionSubmissionService:
    """
    选品提报与审核领域服务 (P2-012)

    职责:
      - 提报来源校验: 验证提报来源是否合法
      - 提报状态机: 管理提报→分配→认领→审核→SKU生成全流程
      - 自动分配: 根据品类/市场自动推荐开发人员
      - 审核规则: 基于评分和风险自动判定审核结论
    """

    @staticmethod
    def is_valid_source(source: str) -> bool:
        return source in SUBMISSION_SOURCES

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        return target_status in SUBMISSION_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def should_auto_approve(selection_score: float, risk_level: str, source: str) -> dict:
        """
        自动审批判定规则

        自动通过条件:
          1. 选品评分 >= 70
          2. 风险等级为 none 或 low
          3. 来源为 PMS AI 建议(默认高可信)

        自动拒绝条件:
          1. 选品评分 < 30
          2. 风险等级为 high 或 critical
        """
        if source == "pms_ai" and selection_score >= 60 and risk_level in ("none", "low"):
            return {"auto_approve": True, "reason": "PMS AI 建议且评分达标"}
        if selection_score >= 70 and risk_level in ("none", "low"):
            return {"auto_approve": True, "reason": "选品评分优秀，风险可控"}
        if selection_score < 30 or risk_level in ("high", "critical"):
            return {"auto_approve": False, "auto_reject": True, "reason": "评分过低或风险过高"}
        return {"auto_approve": False, "auto_reject": False, "reason": "需人工审核"}

    @staticmethod
    def suggest_developer(category_id: str, target_market: str) -> list[str]:
        """
        根据品类和市场推荐开发人员(策略占位)

        实际实现应从人员能力矩阵中匹配:
          - 品类经验匹配
          - 目标市场经验匹配
          - 当前工作量均衡
        """
        return []


# ---------------------------------------------------------------------------
# 开发人员KPI (P2-020)
# ---------------------------------------------------------------------------
# KPI指标: 开发SKU数、出单率、销售利润、KPI提成
# ---------------------------------------------------------------------------


class DeveloperKPIService:
    """
    开发人员KPI领域服务 (P2-020)

    职责:
      - KPI指标计算: SKU开发数、出单率、利润率
      - 提成计算: 基于销售利润×提成比例
      - 绩效评级: 基于多维度综合评分
    """

    @staticmethod
    def calculate_sku_output(total_developed: int, period_days: int) -> dict:
        """计算SKU开发效率和产能"""
        monthly_rate = round(total_developed / max(period_days, 1) * 30, 1)
        return {
            "total_developed": total_developed,
            "period_days": period_days,
            "monthly_rate": monthly_rate,
            "efficiency": "high" if monthly_rate >= 10 else ("medium" if monthly_rate >= 5 else "low"),
        }

    @staticmethod
    def calculate_commission(total_profit: float, commission_rate: float = 0.05) -> dict:
        """
        计算KPI提成

        参数:
            total_profit:    销售总利润
            commission_rate: 提成比例(默认5%)
        """
        commission = round(total_profit * commission_rate, 2)
        return {
            "total_profit": round(total_profit, 2),
            "commission_rate": commission_rate,
            "commission": commission,
            "currency": "CNY",
        }

    @staticmethod
    def calculate_performance_score(sku_count: int, order_rate: float, profit: float) -> dict:
        """
        综合绩效评分

        评分维度:
          - SKU数量(30分): >=50→30, >=20→20, >=10→10
          - 出单率(40分): >=50%→40, >=30%→25, >=10%→10
          - 销售利润(30分): >=100万→30, >=50万→20, >=10万→10
        """
        score = 0
        if sku_count >= 50:
            score += 30
        elif sku_count >= 20:
            score += 20
        elif sku_count >= 10:
            score += 10
        if order_rate >= 50:
            score += 40
        elif order_rate >= 30:
            score += 25
        elif order_rate >= 10:
            score += 10
        if profit >= 1000000:
            score += 30
        elif profit >= 500000:
            score += 20
        elif profit >= 100000:
            score += 10
        grade = "A" if score >= 80 else ("B" if score >= 60 else ("C" if score >= 40 else "D"))
        return {"score": score, "grade": grade}


# ---------------------------------------------------------------------------
# 产品采集与资料导入 (P2-014)
# ---------------------------------------------------------------------------
# 支持多平台采集: Amazon/速卖通/Wish/eBay/Lazada/1688/淘宝/天猫/拼多多
# ---------------------------------------------------------------------------


class ProductImportService:
    """
    产品采集与资料导入领域服务

    职责: 平台字段映射、数据清洗(价格/重量/尺寸)、重复检测(URL/ProductID/名称三重重)
    """

    PLATFORM_MAPPINGS = {
        "amazon": {"title_key": "title", "price_key": "price", "image_key": "main_image", "currency": "USD"},
        "1688": {"title_key": "subject", "price_key": "price", "image_key": "image", "currency": "CNY"},
        "taobao": {"title_key": "title", "price_key": "price", "image_key": "pic_url", "currency": "CNY"},
        "aliexpress": {"title_key": "subject", "price_key": "price", "image_key": "image", "currency": "USD"},
        "ebay": {"title_key": "title", "price_key": "currentPrice", "image_key": "pictureURL", "currency": "USD"},
    }

    @staticmethod
    def normalize_raw_data(raw: dict, platform: str) -> dict:
        """将各平台原始数据映射为标准产品格式"""
        mapping = ProductImportService.PLATFORM_MAPPINGS.get(platform, {})
        return {
            "source_platform": platform,
            "source_url": raw.get("url", ""),
            "source_product_id": raw.get("product_id", "") or raw.get("id", ""),
            "title": raw.get(mapping.get("title_key", "title"), ""),
            "main_image": raw.get(mapping.get("image_key", "image"), ""),
            "images_json": raw.get("images_json", "[]") or raw.get("images", "[]"),
            "price": float(raw.get(mapping.get("price_key", "price"), 0)),
            "currency": mapping.get("currency", "USD"),
            "category_name": raw.get("category_name", "") or raw.get("category", ""),
            "attributes_json": raw.get("attributes_json", "{}"),
            "variants_json": raw.get("variants_json", "[]"),
            "seller_info_json": raw.get("seller_info_json", "{}"),
            "sales_data_json": raw.get("sales_data_json", "{}"),
        }

    @staticmethod
    def detect_duplicate(existing: list[dict], normalized: dict) -> dict:
        """多维度去重: URL/平台ProductID/标题(长文本)三重匹配"""
        url = normalized.get("source_url", "")
        pid = normalized.get("source_product_id", "")
        platform = normalized.get("source_platform", "")
        title = normalized.get("title", "").lower()
        for exist in existing:
            if url and exist.get("source_url") == url:
                return {"is_duplicate": True, "matched_by": "url", "existing_id": exist.get("id", "")}
            if pid and platform and exist.get("source_product_id") == pid and exist.get("source_platform") == platform:
                return {"is_duplicate": True, "matched_by": "product_id", "existing_id": exist.get("id", "")}
            if title and len(title) > 20 and exist.get("title", "").lower() == title:
                return {"is_duplicate": True, "matched_by": "title", "existing_id": exist.get("id", "")}
        return {"is_duplicate": False, "matched_by": "", "existing_id": ""}

    @staticmethod
    def clean_price(price: float, source_currency: str, target: str = "USD", rate: float = 1.0) -> dict:
        converted = round(price * rate, 2) if source_currency != target else round(price, 2)
        return {"original": price, "from": source_currency, "converted": converted, "to": target, "rate": rate}
