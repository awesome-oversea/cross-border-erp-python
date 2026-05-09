"""
内容审核中心引擎

职责:
  - 敏感词检测: 匹配敏感词库,支持多语言
  - 图片审核: 合规检查/水印检测
  - 商标侵权检查: 与商标库比对
  - 审核流程: 自动审核+人工复审

被调用方: PDM(产品描述), SOM(Listing文案), 所有域(内容发布)
"""
from __future__ import annotations

import re


class ContentReviewEngine:
    """内容审核引擎 - 敏感词/图片/商标合规检测"""

    @staticmethod
    def check_sensitive_words(text: str, sensitive_words: list[str]) -> list[dict]:
        """检测文本中的敏感词"""
        if not text:
            return []
        text_lower = text.lower()
        hits = []
        for word in sensitive_words:
            if word.lower() in text_lower:
                hits.append({"word": word, "position": text_lower.index(word.lower())})
        return hits

    @staticmethod
    def check_trademark(text: str, trademarks: list[str]) -> list[dict]:
        """检测文本是否包含注册商标"""
        hits = []
        text_lower = text.lower()
        for tm in trademarks:
            if tm.lower() in text_lower:
                hits.append({"trademark": tm, "matched": True})
        return hits

    @staticmethod
    def check_image_compliance(image_url: str, rules: dict | None = None) -> list[str]:
        """图片合规检查(占位,实际由图像识别服务实现)"""
        warnings = []
        if not image_url:
            warnings.append("图片URL为空")
        return warnings

    @staticmethod
    def auto_pass(hits: list[dict], threshold: int = 0) -> bool:
        """自动审核判定: 命中数为0时自动通过"""
        return len(hits) <= threshold


class MultiLangReviewService:
    """多语言审核(V4 10.1): 翻译质量+文化禁忌"""

    @staticmethod
    def check_translation_quality(original: str, translated: str, lang: str) -> list[str]:
        issues = []
        if not translated: issues.append("翻译结果为空")
        if len(translated) < len(original) * 0.3: issues.append("翻译长度异常,可能内容丢失")
        if len(translated) > len(original) * 3: issues.append("翻译长度异常,可能冗余")
        return issues

    @staticmethod
    def check_cultural_taboo(text: str, target_lang: str) -> list[str]:
        taboos = {"de": ["nazi", "ss"], "ar": ["pig", "alcohol"], "ja": ["fujin"], "fr": ["con"]}
        text_lower = text.lower()
        hits = [w for w in taboos.get(target_lang, []) if w in text_lower]
        return [f"文化禁忌词: {w}" for w in hits]
