from __future__ import annotations

import re
from abc import ABC, abstractmethod


class ContentReviewer(ABC):
    @abstractmethod
    async def review_text(self, text: str, language: str, rules: list[dict]) -> dict:
        pass

    @abstractmethod
    async def review_image(self, image_url: str, rules: list[dict]) -> dict:
        pass


class RuleBasedTextReviewer(ContentReviewer):
    def __init__(self):
        self._keyword_cache: dict[str, list[str]] = {}

    async def review_text(self, text: str, language: str, rules: list[dict]) -> dict:
        violations: list[dict] = []
        text_lower = text.lower()
        for rule in rules:
            if not rule.get("is_active", True):
                continue
            rule_lang = rule.get("language", "*")
            if rule_lang != "*" and rule_lang != language:
                continue
            rule_type = rule.get("rule_type", "")
            if rule_type.startswith("image"):
                continue
            keywords = rule.get("keywords", [])
            for kw in keywords:
                if kw.lower() in text_lower:
                    violations.append({
                        "rule_code": rule.get("rule_code", ""),
                        "rule_name": rule.get("rule_name", ""),
                        "keyword": kw,
                        "severity": rule.get("severity", "warning"),
                    })
            patterns = rule.get("regex_patterns", [])
            for pattern in patterns:
                try:
                    if re.search(pattern, text, re.IGNORECASE):
                        violations.append({
                            "rule_code": rule.get("rule_code", ""),
                            "rule_name": rule.get("rule_name", ""),
                            "pattern": pattern,
                            "severity": rule.get("severity", "warning"),
                        })
                except re.error:
                    pass

        if not violations:
            return {"result": "pass", "detail": "No violations found", "violations": []}

        has_critical = any(v["severity"] == "critical" for v in violations)
        result = "reject" if has_critical else "warning"
        return {"result": result, "detail": f"Found {len(violations)} violation(s)", "violations": violations}

    async def review_image(self, image_url: str, rules: list[dict]) -> dict:
        violations: list[dict] = []
        normalized_url = image_url.lower()
        for rule in rules:
            if not rule.get("is_active", True):
                continue
            rule_type = rule.get("rule_type", "")
            if rule_type.startswith("text"):
                continue

            for kw in rule.get("keywords", []):
                if kw.lower() in normalized_url:
                    violations.append({
                        "rule_code": rule.get("rule_code", ""),
                        "rule_name": rule.get("rule_name", ""),
                        "keyword": kw,
                        "severity": rule.get("severity", "warning"),
                    })

            for pattern in rule.get("regex_patterns", []):
                try:
                    if re.search(pattern, image_url, re.IGNORECASE):
                        violations.append({
                            "rule_code": rule.get("rule_code", ""),
                            "rule_name": rule.get("rule_name", ""),
                            "pattern": pattern,
                            "severity": rule.get("severity", "warning"),
                        })
                except re.error:
                    continue

        if not violations:
            return {"result": "pass", "detail": "No violations found", "violations": []}

        has_critical = any(v["severity"] == "critical" for v in violations)
        result = "reject" if has_critical else "warning"
        return {"result": result, "detail": f"Found {len(violations)} violation(s)", "violations": violations}
