from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.translation_center.domain.engine import TranslationCenterEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.translation_center")

_engine_instance = TranslationCenterEngine()


class TranslationCenterService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = _engine_instance

    async def translate(self, tenant_id: str, text: str, source_lang: str,
                         target_lang: str, domain: str = "general") -> dict:
        result = self._engine.translate(text, source_lang, target_lang, domain)
        return {"source_text": text, "source_lang": source_lang,
                "target_lang": target_lang, "translated_text": result, "domain": domain}

    async def batch_translate(self, tenant_id: str, texts: list[str], source_lang: str,
                               target_lang: str, domain: str = "general") -> list[dict]:
        results = self._engine.batch_translate(texts, source_lang, target_lang, domain)
        return [{"source_text": s, "translated_text": t} for s, t in zip(texts, results, strict=False)]

    async def get_languages(self, tenant_id: str) -> list[dict]:
        return self._engine.get_languages()

    async def get_glossary(self, tenant_id: str, domain: str = "") -> list[dict]:
        return self._engine.get_glossary(domain)

    async def add_glossary(self, tenant_id: str, domain: str, key: str,
                            translations: dict[str, str]) -> dict:
        return self._engine.add_glossary(domain, key, translations)
