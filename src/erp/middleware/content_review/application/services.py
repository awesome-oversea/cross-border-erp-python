from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from erp.middleware.content_review.domain.models import ContentReviewRule, ContentReviewTask
from erp.middleware.content_review.domain.reviewer import RuleBasedTextReviewer
from erp.shared.exceptions import NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.content_review")


class ContentReviewService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._reviewer = RuleBasedTextReviewer()

    async def submit_review(
        self,
        tenant_id: str,
        review_type: str,
        content_type: str,
        content_text: str = "",
        content_url: str = "",
        content_id: str = "",
        language: str = "en",
        source_domain: str = "",
        source_id: str = "",
    ) -> ContentReviewTask:
        rules = await self._get_active_rules(tenant_id, language)

        if content_type == "text" and content_text:
            auto_result = await self._reviewer.review_text(content_text, language, rules)
        elif content_type == "image" and content_url:
            auto_result = await self._reviewer.review_image(content_url, rules)
        else:
            auto_result = {"result": "pending", "detail": "Manual review required", "violations": []}

        needs_manual = auto_result["result"] in ("warning", "reject") or review_type == "manual"

        task = ContentReviewTask(
            tenant_id=tenant_id,
            review_type=review_type,
            content_type=content_type,
            content_id=content_id,
            content_text=content_text[:5000] if content_text else "",
            content_url=content_url,
            language=language,
            status="pending_manual" if needs_manual else "auto_passed",
            auto_result=auto_result["result"],
            auto_detail=json.dumps(auto_result, default=str),
            source_domain=source_domain,
            source_id=source_id,
        )
        self._session.add(task)
        await self._session.flush()

        logger.info("content_review_submitted", task_id=task.id, content_type=content_type, auto_result=auto_result["result"])
        return task

    async def manual_review(
        self,
        task_id: str,
        tenant_id: str,
        result: str,
        detail: str = "",
        reviewer_id: str = "",
    ) -> ContentReviewTask:
        stmt = select(ContentReviewTask).where(
            ContentReviewTask.id == task_id,
            ContentReviewTask.tenant_id == tenant_id,
        )
        res = await self._session.execute(stmt)
        task = res.scalar_one_or_none()
        if not task:
            raise NotFoundException(message=f"Review task '{task_id}' not found")
        if task.status not in ("pending_manual", "warning"):
            raise ValidationException(message=f"Task status '{task.status}' cannot be manually reviewed")

        task.manual_result = result
        task.manual_detail = detail
        task.reviewer_id = reviewer_id
        task.reviewed_at = datetime.now(UTC)
        task.status = "approved" if result == "pass" else "rejected"
        await self._session.flush()

        logger.info("content_review_completed", task_id=task_id, result=result, reviewer_id=reviewer_id)
        return task

    async def get_result(self, task_id: str, tenant_id: str) -> ContentReviewTask | None:
        stmt = select(ContentReviewTask).where(
            ContentReviewTask.id == task_id,
            ContentReviewTask.tenant_id == tenant_id,
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_tasks(
        self,
        tenant_id: str,
        status: str = "",
        content_type: str = "",
        review_type: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ContentReviewTask], int]:
        conditions = [ContentReviewTask.tenant_id == tenant_id]
        if status:
            conditions.append(ContentReviewTask.status == status)
        if content_type:
            conditions.append(ContentReviewTask.content_type == content_type)
        if review_type:
            conditions.append(ContentReviewTask.review_type == review_type)

        count_stmt = select(func.count()).select_from(ContentReviewTask).where(*conditions)
        total = (await self._session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(ContentReviewTask)
            .where(*conditions)
            .order_by(ContentReviewTask.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all()), total

    async def create_rule(
        self,
        tenant_id: str,
        rule_code: str,
        rule_name: str,
        rule_type: str,
        language: str = "*",
        keywords: list[str] | None = None,
        regex_patterns: list[str] | None = None,
        severity: str = "warning",
        is_active: bool = True,
    ) -> ContentReviewRule:
        existing = await self._get_rule_by_code(tenant_id, rule_code)
        if existing:
            raise ValidationException(message=f"Review rule '{rule_code}' already exists")

        rule = ContentReviewRule(
            tenant_id=tenant_id,
            rule_code=rule_code,
            rule_name=rule_name,
            rule_type=rule_type,
            language=language,
            keywords_json=json.dumps(keywords or [], default=str),
            regex_patterns_json=json.dumps(regex_patterns or [], default=str),
            severity=severity,
            is_active=is_active,
        )
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def get_rules(
        self,
        tenant_id: str,
        language: str = "",
        include_inactive: bool = False,
    ) -> Sequence[ContentReviewRule]:
        conditions = [ContentReviewRule.tenant_id == tenant_id]
        if not include_inactive:
            conditions.append(ContentReviewRule.is_active)
        if language:
            conditions.append(
                (ContentReviewRule.language == language) | (ContentReviewRule.language == "*")
            )
        stmt = select(ContentReviewRule).where(*conditions).order_by(ContentReviewRule.rule_type, ContentReviewRule.rule_code)
        res = await self._session.execute(stmt)
        return res.scalars().all()

    async def init_default_rules(self, tenant_id: str) -> list[ContentReviewRule]:
        defaults = [
            {
                "rule_code": "text_prohibited_keywords",
                "rule_name": "Prohibited Keyword Review",
                "rule_type": "text",
                "language": "*",
                "keywords": ["counterfeit", "fake", "prohibited", "replica", "banned"],
                "severity": "critical",
            },
            {
                "rule_code": "text_contact_privacy",
                "rule_name": "Sensitive Contact Review",
                "rule_type": "text",
                "language": "*",
                "regex_patterns": [r"\b\d{16}\b", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"],
                "severity": "critical",
            },
            {
                "rule_code": "text_marketing_warning",
                "rule_name": "Marketing Language Review",
                "rule_type": "text",
                "language": "*",
                "keywords": ["discount", "lowest price", "free gift", "flash sale", "best offer"],
                "severity": "warning",
            },
            {
                "rule_code": "image_sensitive_keywords",
                "rule_name": "Sensitive Image URL Review",
                "rule_type": "image",
                "language": "*",
                "keywords": ["adult", "weapon", "blood", "counterfeit", "infringement"],
                "severity": "critical",
            },
        ]

        created: list[ContentReviewRule] = []
        for item in defaults:
            try:
                created.append(
                    await self.create_rule(
                        tenant_id=tenant_id,
                        rule_code=item["rule_code"],
                        rule_name=item["rule_name"],
                        rule_type=item["rule_type"],
                        language=item.get("language", "*"),
                        keywords=item.get("keywords", []),
                        regex_patterns=item.get("regex_patterns", []),
                        severity=item.get("severity", "warning"),
                    )
                )
            except ValidationException:
                continue
        return created

    async def _get_active_rules(self, tenant_id: str, language: str) -> list[dict]:
        rules = await self.get_rules(tenant_id, language)
        result = []
        for r in rules:
            result.append({
                "rule_code": r.rule_code,
                "rule_name": r.rule_name,
                "rule_type": r.rule_type,
                "language": r.language,
                "keywords": json.loads(r.keywords_json) if r.keywords_json else [],
                "regex_patterns": json.loads(r.regex_patterns_json) if r.regex_patterns_json else [],
                "severity": r.severity,
                "is_active": r.is_active,
            })
        return result

    async def _get_rule_by_code(self, tenant_id: str, rule_code: str) -> ContentReviewRule | None:
        stmt = select(ContentReviewRule).where(
            ContentReviewRule.tenant_id == tenant_id,
            ContentReviewRule.rule_code == rule_code,
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()
