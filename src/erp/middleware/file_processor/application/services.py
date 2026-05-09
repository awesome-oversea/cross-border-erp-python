from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.file_processor.domain.engine import FileProcessorEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.file_processor")

_engine_instance = FileProcessorEngine()


class FileProcessorService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = _engine_instance

    async def upload(self, tenant_id: str, filename: str, content: bytes, domain: str = "general",
                      created_by: str = "") -> dict:
        meta = self._engine.upload(tenant_id, filename, content, domain, created_by)
        return self._meta_to_dict(meta)

    async def get_file(self, tenant_id: str, file_id: str) -> dict | None:
        meta = self._engine.get_file(file_id)
        if not meta or meta.tenant_id != tenant_id:
            return None
        return self._meta_to_dict(meta)

    async def delete_file(self, tenant_id: str, file_id: str) -> dict:
        return self._engine.delete_file(file_id)

    async def preview(self, tenant_id: str, file_id: str) -> dict:
        return self._engine.generate_preview(file_id)

    async def convert(self, tenant_id: str, file_id: str, target_format: str) -> dict:
        task = self._engine.convert(file_id, target_format)
        return {"task_id": task.task_id, "status": task.status, "result_file_id": task.result_file_id}

    async def list_files(self, tenant_id: str, domain: str = "", extension: str = "",
                          limit: int = 50, offset: int = 0) -> list[dict]:
        files = self._engine.list_files(tenant_id, domain, extension, limit, offset)
        return [self._meta_to_dict(f) for f in files]

    def _meta_to_dict(self, meta) -> dict:
        return {
            "file_id": meta.file_id, "filename": meta.filename,
            "original_filename": meta.original_filename, "extension": meta.extension,
            "mime_type": meta.mime_type, "size_bytes": meta.size_bytes,
            "content_hash": meta.content_hash, "storage_key": meta.storage_key,
            "domain": meta.domain, "is_image": meta.is_image,
            "is_document": meta.is_document, "status": meta.status,
            "preview_key": meta.preview_key, "thumbnail_key": meta.thumbnail_key,
            "created_at": meta.created_at,
        }
