from __future__ import annotations

from dataclasses import dataclass, field

SUPPORTED_LANGUAGES = {
    "zh": "中文", "en": "English", "ja": "日本語", "de": "Deutsch",
    "fr": "Français", "es": "Español", "it": "Italiano", "pt": "Português",
    "ko": "한국어", "ru": "Русский", "ar": "العربية", "th": "ไทย",
    "vi": "Tiếng Việt", "id": "Bahasa Indonesia", "ms": "Bahasa Melayu",
}


@dataclass
class GlossaryEntry:
    entry_id: str = ""
    domain: str = ""
    key: str = ""
    translations: dict[str, str] = field(default_factory=dict)
    is_active: bool = True


@dataclass
class TranslationMemoryEntry:
    source_text: str = ""
    source_lang: str = ""
    target_lang: str = ""
    translated_text: str = ""
    domain: str = ""
    quality_score: float = 1.0


class TranslationCenterEngine:
    def __init__(self):
        self._glossary: dict[str, GlossaryEntry] = {}
        self._memory: dict[str, TranslationMemoryEntry] = {}
        self._register_default_glossary()

    def _register_default_glossary(self):
        defaults = [
            ("pdm", "spu", {"zh": "标准产品单元", "en": "Standard Product Unit", "ja": "標準製品ユニット"}),
            ("pdm", "sku", {"zh": "库存量单位", "en": "Stock Keeping Unit", "ja": "在庫管理単位"}),
            ("oms", "sales_order", {"zh": "销售订单", "en": "Sales Order", "ja": "販売注文"}),
            ("wms", "inventory", {"zh": "库存", "en": "Inventory", "ja": "在庫"}),
            ("scm", "purchase_order", {"zh": "采购订单", "en": "Purchase Order", "ja": "発注書"}),
            ("fms", "invoice", {"zh": "发票", "en": "Invoice", "ja": "請求書"}),
            ("tms", "shipment", {"zh": "货件", "en": "Shipment", "ja": "出荷"}),
            ("ads", "campaign", {"zh": "广告活动", "en": "Campaign", "ja": "キャンペーン"}),
        ]
        for domain, key, translations in defaults:
            entry_id = f"{domain}.{key}"
            self._glossary[entry_id] = GlossaryEntry(entry_id=entry_id, domain=domain,
                                                       key=key, translations=translations)

    def translate(self, text: str, source_lang: str, target_lang: str,
                   domain: str = "general") -> str:
        if source_lang == target_lang:
            return text

        cache_key = f"{source_lang}:{target_lang}:{domain}:{text}"
        cached = self._memory.get(cache_key)
        if cached:
            return cached.translated_text

        glossary_key = f"{domain}.{text}"
        entry = self._glossary.get(glossary_key)
        if entry and target_lang in entry.translations:
            result = entry.translations[target_lang]
            self._memory[cache_key] = TranslationMemoryEntry(
                source_text=text, source_lang=source_lang, target_lang=target_lang,
                translated_text=result, domain=domain,
            )
            return result

        return text

    def batch_translate(self, texts: list[str], source_lang: str, target_lang: str,
                         domain: str = "general") -> list[str]:
        return [self.translate(t, source_lang, target_lang, domain) for t in texts]

    def get_languages(self) -> list[dict]:
        return [{"code": k, "name": v} for k, v in SUPPORTED_LANGUAGES.items()]

    def get_glossary(self, domain: str = "") -> list[dict]:
        entries = list(self._glossary.values())
        if domain:
            entries = [e for e in entries if e.domain == domain]
        return [{"entry_id": e.entry_id, "domain": e.domain, "key": e.key,
                 "translations": e.translations} for e in entries]

    def add_glossary(self, domain: str, key: str, translations: dict[str, str]) -> dict:
        entry_id = f"{domain}.{key}"
        entry = GlossaryEntry(entry_id=entry_id, domain=domain, key=key, translations=translations)
        self._glossary[entry_id] = entry
        return {"entry_id": entry_id, "domain": domain, "key": key, "translations": translations}


class ProofreadService:
    """人工校对(V4 11.8): 翻译结果校对流程"""

    @staticmethod
    def submit_for_review(translation: dict, reviewer: str) -> dict:
        return {"translation_id": translation.get("id", ""), "reviewer": reviewer,
                "status": "pending_review", "original_text": translation.get("original", ""),
                "translated_text": translation.get("translated", "")}

    @staticmethod
    def approve(translation_id: str, score: int = 5) -> dict:
        return {"translation_id": translation_id, "score": min(max(score, 1), 5), "status": "approved"}

    @staticmethod
    def reject(translation_id: str, feedback: str) -> dict:
        return {"translation_id": translation_id, "feedback": feedback, "status": "rejected"}
