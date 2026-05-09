from __future__ import annotations

from erp.shared.observability.logging import get_logger

logger = get_logger("erp.translation")


class TranslationService:
    _term_db: dict[str, dict[str, str]] = {}
    _translation_memory: dict[str, dict[str, str]] = {}

    @classmethod
    def register_terms(cls, domain: str, terms: dict[str, dict[str, str]]) -> None:
        for term_key, translations in terms.items():
            full_key = f"{domain}.{term_key}"
            cls._term_db[full_key] = translations

    @classmethod
    def get_term(cls, key: str, lang: str = "zh") -> str | None:
        entry = cls._term_db.get(key)
        if not entry:
            return None
        return entry.get(lang, entry.get("zh", key))

    @classmethod
    def translate(cls, text: str, source_lang: str, target_lang: str, domain: str = "general") -> str:
        cache_key = f"{source_lang}:{target_lang}:{domain}:{text}"
        cached = cls._translation_memory.get(cache_key, {}).get(target_lang)
        if cached:
            return cached

        term_key = f"{domain}.{text}"
        term_result = cls.get_term(term_key, target_lang)
        if term_result and term_result != term_key:
            if cache_key not in cls._translation_memory:
                cls._translation_memory[cache_key] = {}
            cls._translation_memory[cache_key][target_lang] = term_result
            return term_result

        return text

    @classmethod
    def batch_translate(cls, texts: list[str], source_lang: str, target_lang: str, domain: str = "general") -> list[str]:
        return [cls.translate(t, source_lang, target_lang, domain) for t in texts]


TranslationService.register_terms("pdm", {
    "spu": {"zh": "标准产品单元", "en": "Standard Product Unit"},
    "sku": {"zh": "库存量单位", "en": "Stock Keeping Unit"},
    "variant": {"zh": "变体", "en": "Variant"},
    "category": {"zh": "分类", "en": "Category"},
    "brand": {"zh": "品牌", "en": "Brand"},
    "listing": {"zh": "刊登", "en": "Listing"},
})

TranslationService.register_terms("oms", {
    "sales_order": {"zh": "销售订单", "en": "Sales Order"},
    "order_item": {"zh": "订单明细", "en": "Order Item"},
    "fulfillment": {"zh": "履约", "en": "Fulfillment"},
    "shipment": {"zh": "发货", "en": "Shipment"},
    "refund": {"zh": "退款", "en": "Refund"},
})

TranslationService.register_terms("wms", {
    "warehouse": {"zh": "仓库", "en": "Warehouse"},
    "inventory": {"zh": "库存", "en": "Inventory"},
    "inbound": {"zh": "入库", "en": "Inbound"},
    "outbound": {"zh": "出库", "en": "Outbound"},
    "stock_transfer": {"zh": "调拨", "en": "Stock Transfer"},
})

TranslationService.register_terms("fms", {
    "cost_event": {"zh": "成本事件", "en": "Cost Event"},
    "profit": {"zh": "利润", "en": "Profit"},
    "payment": {"zh": "付款", "en": "Payment"},
    "settlement": {"zh": "结算", "en": "Settlement"},
    "exchange_rate": {"zh": "汇率", "en": "Exchange Rate"},
})

TranslationService.register_terms("scm", {
    "purchase_order": {"zh": "采购单", "en": "Purchase Order"},
    "supplier": {"zh": "供应商", "en": "Supplier"},
    "replenishment": {"zh": "补货", "en": "Replenishment"},
})

TranslationService.register_terms("tms", {
    "logistics": {"zh": "物流", "en": "Logistics"},
    "tracking": {"zh": "物流追踪", "en": "Tracking"},
    "shipping_label": {"zh": "面单", "en": "Shipping Label"},
    "freight": {"zh": "运费", "en": "Freight"},
})

TranslationService.register_terms("common", {
    "tenant": {"zh": "租户", "en": "Tenant"},
    "status": {"zh": "状态", "en": "Status"},
    "create": {"zh": "创建", "en": "Create"},
    "update": {"zh": "更新", "en": "Update"},
    "delete": {"zh": "删除", "en": "Delete"},
    "approve": {"zh": "审批", "en": "Approve"},
    "reject": {"zh": "驳回", "en": "Reject"},
    "submit": {"zh": "提交", "en": "Submit"},
    "export": {"zh": "导出", "en": "Export"},
    "import": {"zh": "导入", "en": "Import"},
})
