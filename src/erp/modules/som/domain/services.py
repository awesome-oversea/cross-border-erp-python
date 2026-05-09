"""
SOM 域服务 - 纯业务规则与状态机，不依赖基础设施层

本模块包含销售运营域的核心业务规则：
- Listing 状态机与校验
- 店铺授权状态机与校验
- 价格规则计算引擎
- Listing 优化评分引擎
- 告警规则评估与状态机

所有方法均为无副作用的纯函数/静态方法，仅依赖传入参数和常量定义。
"""
from __future__ import annotations

# ──── Listing 状态机 ────

LISTING_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["pending_review", "cancelled"],
    "pending_review": ["approved", "rejected", "cancelled"],
    "approved": ["publishing", "cancelled"],
    "publishing": ["published", "publish_failed"],
    "publish_failed": ["publishing", "cancelled"],
    "published": ["unpublished", "archived"],
    "unpublished": ["publishing", "archived"],
    "archived": [],
    "rejected": ["draft"],
    "cancelled": [],
}
"""Listing 内部状态流转表 - 控制审核→发布→下架全生命周期"""

LISTING_STATUS_ON_PLATFORM: dict[str, list[str]] = {
    "not_listed": ["active", "inactive"],
    "active": ["inactive", "closed"],
    "inactive": ["active", "closed"],
    "closed": [],
}
"""Listing 平台侧状态流转表 - 反映平台上的实际上架状态"""

# ──── 店铺授权状态机 ────

STORE_AUTH_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "unauthorized": ["authorizing", "expired"],
    "authorizing": ["authorized", "unauthorized"],
    "authorized": ["expired", "revoked", "unauthorized"],
    "expired": ["authorizing", "unauthorized"],
    "revoked": ["unauthorized"],
}
"""店铺授权状态流转表 - 控制授权→过期→吊销流程"""

# ──── 平台与规则类型常量 ────

VALID_PLATFORMS = {
    "amazon", "shopify", "tiktok_shop", "shopee", "lazada",
    "walmart", "ebay", "aliexpress", "temu", "shein",
}
"""支持的电商平台集合"""

PRICE_RULE_TYPES = {
    "markup", "markdown", "fixed", "competitive",
}
"""价格规则类型: 加价/降价/固定/竞争性定价"""


class ListingDomainService:
    """Listing 领域服务 - 封装 Listing 相关的业务规则"""

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """判断 Listing 内部状态是否可以从 current 转换到 target"""
        return target_status in LISTING_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def can_transition_platform_status(current_status: str, target_status: str) -> bool:
        """判断 Listing 平台侧状态是否可以从 current 转换到 target"""
        return target_status in LISTING_STATUS_ON_PLATFORM.get(current_status, [])

    @staticmethod
    def validate_listing_price(price: float, sale_price: float, msrp: float) -> list[str]:
        """校验 Listing 价格合理性，返回错误列表（空列表表示通过）"""
        errors: list[str] = []
        if price < 0:
            errors.append("Price cannot be negative")
        if sale_price < 0:
            errors.append("Sale price cannot be negative")
        if msrp < 0:
            errors.append("MSRP cannot be negative")
        if sale_price > 0 and sale_price > price:
            errors.append("Sale price cannot exceed regular price")
        if msrp > 0 and price > msrp:
            errors.append("Regular price exceeds MSRP")
        return errors

    @staticmethod
    def is_publishable(status: str, listing_status: str) -> bool:
        """判断 Listing 是否满足发布条件（内部状态已审核 + 平台未上架）"""
        return status in ("approved", "publish_failed") and listing_status in ("not_listed", "inactive")

    @staticmethod
    def is_editable(status: str) -> bool:
        """判断 Listing 是否处于可编辑状态"""
        return status in ("draft", "rejected", "pending_review")


class StoreDomainService:
    """店铺领域服务 - 封装店铺相关的业务规则"""

    @staticmethod
    def can_transition_auth(current_status: str, target_status: str) -> bool:
        """判断店铺授权状态是否可以从 current 转换到 target"""
        return target_status in STORE_AUTH_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_platform(platform: str) -> bool:
        """校验平台是否在支持列表中"""
        return platform.lower() in VALID_PLATFORMS

    @staticmethod
    def is_operational(status: str, auth_status: str) -> bool:
        """判断店铺是否处于可运营状态（活跃 + 已授权）"""
        return status == "active" and auth_status == "authorized"


class PriceRuleDomainService:
    """价格规则领域服务 - 封装价格规则的校验与计算逻辑"""

    @staticmethod
    def validate_rule(rule_type: str, formula: dict, min_price: float, max_price: float) -> list[str]:
        """校验价格规则参数合理性，返回错误列表"""
        errors: list[str] = []
        if rule_type not in PRICE_RULE_TYPES:
            errors.append(f"Invalid rule type: {rule_type}")
        if min_price < 0:
            errors.append("Min price cannot be negative")
        if max_price > 0 and max_price < min_price:
            errors.append("Max price cannot be less than min price")
        if rule_type == "markup" and "percentage" not in formula:
            errors.append("Markup rule requires 'percentage' in formula")
        if rule_type == "markdown" and "percentage" not in formula:
            errors.append("Markdown rule requires 'percentage' in formula")
        if rule_type == "fixed" and "amount" not in formula:
            errors.append("Fixed rule requires 'amount' in formula")
        return errors

    @staticmethod
    def calculate_price(rule_type: str, formula: dict, cost_price: float, min_price: float = 0, max_price: float = 0) -> float:
        """根据规则类型和公式计算定价，并应用价格上下限约束"""
        if rule_type == "markup":
            percentage = formula.get("percentage", 0)
            result = cost_price * (1 + percentage / 100)
        elif rule_type == "markdown":
            percentage = formula.get("percentage", 0)
            result = cost_price * (1 - percentage / 100)
        elif rule_type == "fixed":
            result = formula.get("amount", cost_price)
        elif rule_type == "competitive":
            base = formula.get("base_price", cost_price)
            adjustment = formula.get("adjustment", 0)
            result = base + adjustment
        else:
            result = cost_price

        if min_price > 0 and result < min_price:
            result = min_price
        if max_price > 0 and result > max_price:
            result = max_price
        return round(result, 2)


# ──── Listing 优化评分引擎 ────

VALID_OPT_TYPES = {"title", "keyword", "image", "bullet_point", "description", "full"}
"""支持的优化类型集合"""

OPTIMIZATION_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["analyzing", "cancelled"],
    "analyzing": ["suggested", "failed"],
    "suggested": ["applying", "cancelled"],
    "applying": ["applied", "partial_applied", "failed"],
    "applied": [],
    "partial_applied": ["applying", "cancelled"],
    "failed": ["analyzing"],
    "cancelled": [],
}
"""优化任务状态流转表"""

# ──── 平台内容规范常量 ────

AMAZON_TITLE_MAX_LENGTH = 200
"""Amazon 标题最大字符数"""
SHOPEE_TITLE_MAX_LENGTH = 120
"""Shopee 标题最大字符数"""
AMAZON_BULLET_POINT_MAX_COUNT = 5
"""Amazon 五点描述最大条数"""
AMAZON_SEARCH_TERMS_MAX_LENGTH = 250
"""Amazon 后台搜索词最大字节长度"""
AMAZON_IMAGE_MIN_COUNT = 5
"""Amazon 推荐最少图片数"""
AMAZON_MAIN_IMAGE_MIN_WIDTH = 1000
"""Amazon 主图最小宽度(px)"""


class ListingOptimizationDomainService:
    """Listing 优化领域服务 - 封装 Listing 内容质量评分与优化建议生成逻辑"""

    @staticmethod
    def validate_opt_type(opt_type: str) -> bool:
        """校验优化类型是否合法"""
        return opt_type in VALID_OPT_TYPES

    @staticmethod
    def can_transition_opt_status(current: str, target: str) -> bool:
        """判断优化任务状态是否可以从 current 转换到 target"""
        return target in OPTIMIZATION_STATUS_TRANSITIONS.get(current, [])

    @staticmethod
    def score_title(title: str, platform: str = "amazon") -> dict:
        """对 Listing 标题进行质量评分

        评分维度: 长度利用(25) + 关键词密度(25) + 大小写规范(15) + 特殊字符(10) + 排版(15) + 合规性(10)
        返回: {"score": float, "issues": [...], "suggestions": [...]}
        """
        score = 0.0
        issues: list[str] = []
        suggestions: list[str] = []

        if not title or not title.strip():
            return {"score": 0.0, "issues": ["Title is empty"], "suggestions": ["Add a product title"]}

        max_length = AMAZON_TITLE_MAX_LENGTH if platform == "amazon" else SHOPEE_TITLE_MAX_LENGTH
        word_count = len(title.split())

        if len(title) > max_length:
            issues.append(f"Title exceeds {max_length} characters")
            suggestions.append(f"Shorten title to under {max_length} characters")
        elif len(title) < max_length * 0.5:
            issues.append("Title is too short, not utilizing available space")
            suggestions.append(f"Expand title to use more of the {max_length} character limit")
        else:
            score += 25.0

        if word_count < 3:
            issues.append("Title has too few words for effective search")
            suggestions.append("Include more descriptive keywords")
        elif word_count >= 5:
            score += 25.0
        else:
            score += 15.0

        if title.isupper():
            issues.append("Title is all uppercase, which may reduce readability")
            suggestions.append("Use title case or sentence case")
        elif title.islower():
            issues.append("Title is all lowercase")
            suggestions.append("Capitalize the first letter of each major word")
        else:
            score += 15.0

        if any(c in title for c in "!@#$%^*"):
            issues.append("Title contains special characters that may not display correctly")
            suggestions.append("Remove unnecessary special characters")
        else:
            score += 10.0

        if len(title) > 10 and title[:10].count(" ") == 0:
            issues.append("First 10 characters contain no spaces; front-loading keywords too densely")
            suggestions.append("Ensure brand or key identifier is at the start, followed by a space")
        else:
            score += 15.0

        if any(kw in title.lower() for kw in ["best", "free", "guarantee"]):
            issues.append("Title may contain prohibited promotional terms")
            suggestions.append("Remove promotional language per platform policy")
        else:
            score += 10.0

        return {"score": round(score, 1), "issues": issues, "suggestions": suggestions}

    @staticmethod
    def score_keywords(search_terms: str, title: str = "", bullet_points_json: str = "[]") -> dict:
        """对后台搜索词进行质量评分

        评分维度: 长度利用(30) + 关键词数量(25) + 与标题去重(20) + 与五点去重(15) + 大小写(10)
        """
        score = 0.0
        issues: list[str] = []
        suggestions: list[str] = []

        if not search_terms or not search_terms.strip():
            return {"score": 0.0, "issues": ["No search terms provided"], "suggestions": ["Add backend search terms"]}

        keywords = [kw.strip() for kw in search_terms.split(",") if kw.strip()]
        total_length = len(search_terms.replace(",", " ").strip())

        if total_length > AMAZON_SEARCH_TERMS_MAX_LENGTH:
            issues.append(f"Search terms exceed {AMAZON_SEARCH_TERMS_MAX_LENGTH} byte limit")
            suggestions.append("Remove duplicate or redundant keywords")
        elif total_length < AMAZON_SEARCH_TERMS_MAX_LENGTH * 0.3:
            issues.append("Search terms are under-utilized")
            suggestions.append("Add more relevant keywords to approach the byte limit")
        else:
            score += 30.0

        if len(keywords) < 3:
            issues.append("Too few keywords")
            suggestions.append("Add at least 5-10 relevant keywords")
        elif len(keywords) >= 5:
            score += 25.0
        else:
            score += 15.0

        title_words = set(title.lower().split()) if title else set()
        duplicate_in_title = [kw for kw in keywords if kw.lower() in title_words]
        if duplicate_in_title:
            issues.append(f"Keywords duplicate title words: {duplicate_in_title[:3]}")
            suggestions.append("Remove keywords already in the title to save space")
        else:
            score += 20.0

        import json
        try:
            bullets = json.loads(bullet_points_json) if bullet_points_json else []
        except (json.JSONDecodeError, TypeError):
            bullets = []
        bullet_text = " ".join(bullets).lower() if bullets else ""
        duplicate_in_bullets = [kw for kw in keywords if kw.lower() in bullet_text]
        if duplicate_in_bullets:
            issues.append(f"Keywords duplicate bullet point content: {duplicate_in_bullets[:3]}")
            suggestions.append("Replace duplicated keywords with alternative search terms")
        else:
            score += 15.0

        if any(kw.isupper() and len(kw) > 2 for kw in keywords):
            issues.append("Some keywords are all uppercase")
            suggestions.append("Use lowercase for search terms as they are case-insensitive")
        else:
            score += 10.0

        return {"score": round(score, 1), "issues": issues, "suggestions": suggestions}

    @staticmethod
    def score_images(images_json: str, main_image: str = "") -> dict:
        """对 Listing 图片进行质量评分

        评分维度: 数量(35) + 主图(25) + 去重(15) + 场景图(15) + 信息图(10)
        """
        score = 0.0
        issues: list[str] = []
        suggestions: list[str] = []

        import json
        try:
            images = json.loads(images_json) if images_json else []
        except (json.JSONDecodeError, TypeError):
            images = []

        if not images and not main_image:
            return {"score": 0.0, "issues": ["No images provided"], "suggestions": ["Add at least one product image"]}

        all_images = []
        if main_image:
            all_images.append(main_image)
        all_images.extend(images)
        image_count = len(all_images)

        if image_count < 3:
            issues.append(f"Only {image_count} image(s), which is below best practice")
            suggestions.append(f"Add at least {AMAZON_IMAGE_MIN_COUNT} images for better conversion")
        elif image_count < AMAZON_IMAGE_MIN_COUNT:
            score += 20.0
            suggestions.append(f"Consider adding more images to reach {AMAZON_IMAGE_MIN_COUNT}")
        else:
            score += 35.0

        if not main_image:
            issues.append("No main image specified")
            suggestions.append("Set a high-quality main image")
        else:
            score += 25.0

        if image_count > 0:
            unique_images = set(all_images)
            if len(unique_images) < image_count:
                issues.append("Duplicate images detected")
                suggestions.append("Replace duplicate images with different angles or lifestyle shots")
            else:
                score += 15.0

        if image_count >= 5:
            has_lifestyle = any("lifestyle" in img.lower() or "scene" in img.lower() for img in all_images)
            if not has_lifestyle:
                suggestions.append("Consider adding lifestyle/scene images for better engagement")
            else:
                score += 15.0

        if image_count >= 2:
            has_infographic = any("info" in img.lower() or "chart" in img.lower() for img in all_images)
            if not has_infographic:
                suggestions.append("Consider adding infographic images to highlight features")
            else:
                score += 10.0

        return {"score": round(score, 1), "issues": issues, "suggestions": suggestions}

    @staticmethod
    def score_bullet_points(bullet_points_json: str) -> dict:
        """对五点描述进行质量评分

        评分维度: 数量(25) + 短描述(20) + 长描述(20) + 大小写(15) + 合规性(20)
        """
        score = 0.0
        issues: list[str] = []
        suggestions: list[str] = []

        import json
        try:
            bullets = json.loads(bullet_points_json) if bullet_points_json else []
        except (json.JSONDecodeError, TypeError):
            bullets = []

        if not bullets:
            return {"score": 0.0, "issues": ["No bullet points provided"], "suggestions": ["Add bullet points to highlight key features"]}

        if len(bullets) < AMAZON_BULLET_POINT_MAX_COUNT:
            issues.append(f"Only {len(bullets)} bullet point(s), recommended {AMAZON_BULLET_POINT_MAX_COUNT}")
            suggestions.append(f"Add more bullet points to fill all {AMAZON_BULLET_POINT_MAX_COUNT} slots")
        else:
            score += 25.0

        short_bullets = [b for b in bullets if len(b) < 30]
        if short_bullets:
            issues.append(f"{len(short_bullets)} bullet point(s) are too short (under 30 chars)")
            suggestions.append("Expand short bullet points with more detail")
        else:
            score += 20.0

        long_bullets = [b for b in bullets if len(b) > 500]
        if long_bullets:
            issues.append(f"{len(long_bullets)} bullet point(s) are too long (over 500 chars)")
            suggestions.append("Shorten verbose bullet points for better readability")
        else:
            score += 20.0

        if any(b.isupper() for b in bullets if len(b) > 10):
            issues.append("Some bullet points are all uppercase")
            suggestions.append("Use sentence case for bullet points")
        else:
            score += 15.0

        if any(kw in " ".join(bullets).lower() for kw in ["best", "#1", "free shipping"]):
            issues.append("Bullet points may contain prohibited claims")
            suggestions.append("Remove subjective claims per platform policy")
        else:
            score += 20.0

        return {"score": round(score, 1), "issues": issues, "suggestions": suggestions}

    @staticmethod
    def compute_overall_score(scores: dict[str, float]) -> float:
        """根据各维度评分计算加权总分

        权重: 标题(0.30) + 关键词(0.25) + 图片(0.25) + 五点(0.20)
        """
        weights = {"title": 0.30, "keyword": 0.25, "image": 0.25, "bullet_point": 0.20}
        total = 0.0
        for key, weight in weights.items():
            total += scores.get(key, 0.0) * weight
        return round(total, 1)


# ──── 告警规则域 ────

VALID_METRIC_TYPES = {"sales", "traffic", "conversion", "ads_spend", "inventory", "listing"}
"""支持的告警指标类型"""
VALID_CONDITION_TYPES = {"gt", "lt", "eq", "gte", "lte", "between", "change_rate"}
"""支持的告警条件类型"""
VALID_SEVERITY_LEVELS = {"info", "warning", "critical"}
"""告警严重级别"""
VALID_NOTIFY_CHANNELS = {"email", "sms", "feishu", "dingtalk", "wechat"}
"""支持的告警通知渠道"""

ALERT_RECORD_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "firing": ["acknowledged", "resolved"],
    "acknowledged": ["resolved"],
    "resolved": [],
}
"""告警记录状态流转表: 触发→确认→解决"""


class AlertRuleDomainService:
    """告警规则领域服务 - 封装告警规则的校验、评估与状态机"""

    @staticmethod
    def validate_rule(metric_type: str, condition_type: str, severity: str, notify_channels: str) -> list[str]:
        """校验告警规则参数合法性，返回错误列表"""
        errors: list[str] = []
        if metric_type not in VALID_METRIC_TYPES:
            errors.append(f"Invalid metric_type: {metric_type}")
        if condition_type not in VALID_CONDITION_TYPES:
            errors.append(f"Invalid condition_type: {condition_type}")
        if severity not in VALID_SEVERITY_LEVELS:
            errors.append(f"Invalid severity: {severity}")
        channels = set(notify_channels.split(",")) if notify_channels else set()
        invalid_channels = channels - VALID_NOTIFY_CHANNELS
        if invalid_channels:
            errors.append(f"Invalid notify channels: {invalid_channels}")
        return errors

    @staticmethod
    def evaluate_condition(actual_value: float, condition_type: str, threshold: float, threshold_max: float = 0.0) -> bool:
        """评估实际值是否满足告警条件

        支持条件: gt(大于)/lt(小于)/eq(等于)/gte(大于等于)/lte(小于等于)/between(区间)/change_rate(变化率)
        """
        if condition_type == "gt":
            return actual_value > threshold
        elif condition_type == "lt":
            return actual_value < threshold
        elif condition_type == "eq":
            return abs(actual_value - threshold) < 0.001
        elif condition_type == "gte":
            return actual_value >= threshold
        elif condition_type == "lte":
            return actual_value <= threshold
        elif condition_type == "between":
            return threshold <= actual_value <= threshold_max
        elif condition_type == "change_rate":
            return abs(actual_value) > threshold
        return False

    @staticmethod
    def can_transition_alert_status(current: str, target: str) -> bool:
        """判断告警记录状态是否可以从 current 转换到 target"""
        return target in ALERT_RECORD_STATUS_TRANSITIONS.get(current, [])

    @staticmethod
    def build_alert_message(rule_name: str, metric_type: str, condition_type: str, actual_value: float, threshold: float) -> str:
        """根据规则名、指标类型和条件生成告警消息文本"""
        condition_map = {
            "gt": "exceeded", "lt": "fell below", "eq": "equals",
            "gte": "reached or exceeded", "lte": "reached or fell below",
            "between": "is outside range of", "change_rate": "change rate exceeded",
        }
        desc = condition_map.get(condition_type, "triggered")
        return f"[{rule_name}] {metric_type} {desc} threshold: actual={actual_value}, threshold={threshold}"


# ---------------------------------------------------------------------------
# 批量刊登服务 (P2-022)
# ---------------------------------------------------------------------------
SUPPORTED_BATCH_OPERATIONS = {
    "publish", "unpublish", "update_price", "update_quantity",
    "update_title", "update_description", "translate", "delete",
}
"""支持的批量刊登操作类型"""


class BatchListingService:
    """
    批量刊登领域服务

    职责:
      - 批量操作校验: 校验批量操作参数合法性
      - 批量操作拆分: 将大批量操作拆分为小批次
      - 操作结果汇总: 统计成功/失败/跳过数量
      - 多语种翻译: 支持批量翻译文案
    """

# ---------------------------------------------------------------------------
# 平台产品限价 (P2-024)
# ---------------------------------------------------------------------------
# 防止多店铺同站点内部价格战
# 支持按平台/店铺/SKU维度设置最低/最高限价
# ---------------------------------------------------------------------------


class PriceLimitService:
    """平台产品限价领域服务"""
    @staticmethod
    def validate_price_against_limits(price: float, min_price: float = 0, max_price: float = 0) -> list[str]:
        errors = []
        if min_price > 0 and price < min_price:
            errors.append(f"售价{price}低于最低限价{min_price}")
        if max_price > 0 and price > max_price:
            errors.append(f"售价{price}超过最高限价{max_price}")
        return errors

    @staticmethod
    def check_cross_store_conflict(sku_id: str, price: float, same_sku_prices: list[float], max_diff_pct: float = 10) -> list[str]:
        """检查同SKU在多店铺间的价格冲突"""
        if not same_sku_prices:
            return []
        others_min = min(same_sku_prices)
        diff_pct = abs(price - others_min) / others_min * 100 if others_min > 0 else 0
        if diff_pct > max_diff_pct:
            return [f"该SKU在各店铺间价差{diff_pct:.1f}%超过限制{max_diff_pct}%，可能导致内部价格战"]
        return []


# ---------------------------------------------------------------------------
# 滞销品清库计划 (P2-026)
# ---------------------------------------------------------------------------


class SlowMovingService:
    """滞销品清库计划领域服务"""
    @staticmethod
    def classify_movement(sales_qty_30d: int, current_stock: int) -> dict:
        """根据30天销量和当前库存判断动销状态"""
        if current_stock <= 0:
            return {"status": "out_of_stock", "label": "无库存", "action": ""}
        sell_rate = sales_qty_30d / 30 if sales_qty_30d > 0 else 0
        if sell_rate == 0:
            stock_days = 999
        else:
            stock_days = round(current_stock / sell_rate)
        if stock_days >= 180 or (sales_qty_30d == 0 and current_stock > 0):
            return {"status": "slow_moving", "label": "滞销品", "action": "建议降价清库", "stock_days": stock_days}
        elif stock_days >= 90:
            return {"status": "warning", "label": "缓慢动销", "action": "关注库存周转", "stock_days": stock_days}
        else:
            return {"status": "normal", "label": "正常动销", "action": "", "stock_days": stock_days}

    @staticmethod
    def suggest_clearance_price(cost_price: float, original_price: float, stock_qty: int) -> dict:
        """建议清库价格: 按阶梯降价策略"""
        if stock_qty <= 0:
            return {"suggested_price": 0, "discount_pct": 0, "strategy": ""}
        if stock_qty <= 10:
            discount = 0.3
        elif stock_qty <= 50:
            discount = 0.4
        else:
            discount = 0.5
        suggested = round(original_price * (1 - discount), 2)
        return {
            "suggested_price": max(suggested, round(cost_price * 0.8, 2)),
            "discount_pct": round(discount * 100),
            "strategy": f"建议打{int((1-discount)*100)}折清库",
            "is_above_cost": suggested > cost_price,
        }


# ---------------------------------------------------------------------------
# 销售小组与运营绩效 (P2-028)
# ---------------------------------------------------------------------------


class SalesTeamService:
    """销售小组领域服务"""
    @staticmethod
    def calculate_team_performance(members: list[dict]) -> dict:
        total_sales = sum(m.get("sales", 0) for m in members)
        total_orders = sum(m.get("orders", 0) for m in members)
        avg_target = sum(m.get("target", 0) for m in members) / max(len(members), 1)
        achievement = round(total_sales / avg_target * 100, 2) if avg_target > 0 else 0
        return {
            "total_sales": total_sales, "total_orders": total_orders,
            "member_count": len(members), "achievement_pct": achievement,
            "top_performer": max(members, key=lambda x: x.get("sales", 0)) if members else None,
        }


    @staticmethod
    def is_valid_batch_operation(operation: str) -> bool:
        return operation in SUPPORTED_BATCH_OPERATIONS

    @staticmethod
    def split_batch(items: list[str], batch_size: int = 20) -> list[list[str]]:
        """
        将大批量操作拆分为小批次

        参数:
            items:     待操作项列表(Listing ID列表)
            batch_size: 每批数量(默认20，平台API通常限制)

        返回:
            拆分后的批次列表
        """
        return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

    @staticmethod
    def aggregate_batch_results(results: list[dict]) -> dict:
        """
        汇总批量操作结果

        参数:
            results: 操作结果列表 [{listing_id, status, error?}, ...]

        返回:
            汇总统计 {total, success, failed, skipped, errors}
        """
        total = len(results)
        success = sum(1 for r in results if r.get("status") == "success")
        failed = sum(1 for r in results if r.get("status") == "failed")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        errors = [r.get("error", "") for r in results if r.get("error")]
        return {
            "total": total, "success": success, "failed": failed,
            "skipped": skipped, "errors": errors[:10],
            "success_rate": round(success / total * 100, 2) if total > 0 else 0,
        }

    @staticmethod
    def estimate_batch_time(item_count: int, per_item_seconds: float = 2.0) -> str:
        """估算批量操作耗时"""
        total_seconds = item_count * per_item_seconds
        if total_seconds < 60:
            return f"{int(total_seconds)}秒"
        elif total_seconds < 3600:
            return f"{int(total_seconds / 60)}分钟"
        else:
            return f"{round(total_seconds / 3600, 1)}小时"


# ---------------------------------------------------------------------------
# Reviews同步与质量问题联动 (P2-027)
# ---------------------------------------------------------------------------
REVIEW_SENTIMENT_TYPES = {"positive", "neutral", "negative"}
"""评论情感类型"""


class ReviewDomainService:
    """
    Reviews领域服务

    职责:
      - 评论情感分类: 根据评分判定情感倾向
      - 质量问题提取: 从差评中提取质量相关关键词
      - 质量问题联动: 将质量问题与PDM产品问题记录关联
    """

    @staticmethod
    def classify_sentiment(rating: int) -> str:
        """
        根据评分分类评论情感

        规则:
          - 4-5星: positive
          - 3星:   neutral
          - 1-2星: negative
        """
        if rating >= 4:
            return "positive"
        elif rating >= 3:
            return "neutral"
        return "negative"

    @staticmethod
    def extract_quality_keywords(review_text: str) -> list[str]:
        """
        从评论中提取潜在的质量问题关键词

        常用质量相关关键词列表:
          破损/损坏/坏了/断裂/失灵/不工作/褪色/掉色/开线/变形
        """
        quality_keywords = [
            "破损", "损坏", "坏了", "断裂", "失灵", "不工作",
            "褪色", "掉色", "开线", "变形", "生锈", "漏水",
            "broken", "damaged", "defective", "cracked", "faded",
            "ripped", "malfunction", "stopped working",
        ]
        found = []
        text_lower = review_text.lower()
        for keyword in quality_keywords:
            if keyword.lower() in text_lower:
                found.append(keyword)
        return found

    @staticmethod
    def should_link_to_product_issue(review_text: str, rating: int) -> dict:
        """
        判断评论是否需要创建产品问题记录

        判定条件:
          1. 差评(1-2星)
          2. 且包含质量问题关键词
          3. 或明确描述产品缺陷

        返回:
            {"should_link": bool, "keywords": [...], "severity": str}
        """
        if rating >= 3:
            return {"should_link": False, "keywords": [], "severity": "low"}
        keywords = ReviewDomainService.extract_quality_keywords(review_text)
        if keywords:
            severity = "high" if rating == 1 else "medium"
            return {"should_link": True, "keywords": keywords, "severity": severity}
        return {"should_link": False, "keywords": [], "severity": "low"}


class DistributionService:
    @staticmethod
    def calc_dist_price(base: float, discount: float, min_margin: float = 0.05) -> dict:
        price = round(base * (1 - discount / 100), 2)
        margin = round((base - price) / base, 4) if base > 0 else 0
        if margin < min_margin: price = round(base * (1 - min_margin), 2)
        return {"base": base, "dist_price": price, "discount": discount, "margin": margin}


class SalesEstimationService:
    @staticmethod
    def estimate(history: list[dict], exclude_promo: bool = True, days: int = 30) -> dict:
        if not history: return {"daily_sales": 0, "samples": 0}
        if exclude_promo: history = [d for d in history if not d.get("is_promotion")]
        if not history: return {"daily_sales": 0, "samples": 0}
        recent = history[-days:]
        avg = round(sum(d.get("qty", 0) for d in recent) / max(len(recent), 1), 2)
        return {"daily_sales": avg, "samples": len(recent)}


class OperationsCalendarService:
    EVENT_TYPES = {"promotion", "listing", "restock", "clearance", "incident"}
    @staticmethod
    def validate(etype: str, title: str) -> list[str]:
        e = []
        if etype not in OperationsCalendarService.EVENT_TYPES: e.append(f"类型不合法: {etype}")
        if not title: e.append("标题不能为空")
        return e
