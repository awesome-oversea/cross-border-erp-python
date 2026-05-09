from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp", "bmp", "svg",
    "pdf", "doc", "docx", "xls", "xlsx", "csv", "txt",
    "zip", "rar", "7z",
}

MAX_FILE_SIZE = 50 * 1024 * 1024

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"}
DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "csv", "txt"}


@dataclass
class FileMetadata:
    file_id: str = ""
    tenant_id: str = ""
    filename: str = ""
    original_filename: str = ""
    extension: str = ""
    mime_type: str = ""
    size_bytes: int = 0
    content_hash: str = ""
    storage_key: str = ""
    domain: str = ""
    is_image: bool = False
    is_document: bool = False
    status: str = "uploaded"
    thumbnail_key: str = ""
    preview_key: str = ""
    created_at: str = ""
    created_by: str = ""


@dataclass
class ConversionTask:
    task_id: str = ""
    source_file_id: str = ""
    target_format: str = ""
    status: str = "pending"
    result_file_id: str = ""
    error_message: str = ""
    created_at: str = ""


class FileProcessorEngine:
    def __init__(self):
        self._files: dict[str, FileMetadata] = {}
        self._conversions: list[ConversionTask] = []

    def upload(self, tenant_id: str, filename: str, content: bytes, domain: str = "general",
               created_by: str = "") -> FileMetadata:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"File extension '{ext}' is not allowed")
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum allowed ({MAX_FILE_SIZE // (1024*1024)}MB)")

        content_hash = hashlib.sha256(content).hexdigest()
        file_id = str(uuid.uuid4())
        date_prefix = datetime.now(UTC).strftime("%Y/%m/%d")
        storage_key = f"{tenant_id}/{domain}/{date_prefix}/{file_id[:8]}/{filename}"

        meta = FileMetadata(
            file_id=file_id, tenant_id=tenant_id, filename=filename,
            original_filename=filename, extension=ext,
            mime_type=self._guess_mime(ext), size_bytes=len(content),
            content_hash=content_hash, storage_key=storage_key, domain=domain,
            is_image=ext in IMAGE_EXTENSIONS, is_document=ext in DOCUMENT_EXTENSIONS,
            status="uploaded",
            created_at=datetime.now(UTC).isoformat(), created_by=created_by,
        )
        self._files[file_id] = meta
        return meta

    def get_file(self, file_id: str) -> FileMetadata | None:
        return self._files.get(file_id)

    def delete_file(self, file_id: str) -> dict:
        meta = self._files.pop(file_id, None)
        if not meta:
            return {"success": False, "error": "File not found"}
        return {"success": True, "file_id": file_id, "filename": meta.filename}

    def generate_preview(self, file_id: str) -> dict:
        meta = self._files.get(file_id)
        if not meta:
            return {"success": False, "error": "File not found"}
        if meta.is_image:
            preview_key = f"preview/{meta.storage_key}"
            meta.preview_key = preview_key
            meta.thumbnail_key = f"thumb/{meta.storage_key}"
            return {"success": True, "file_id": file_id, "preview_key": preview_key, "type": "image"}
        if meta.extension == "pdf":
            preview_key = f"preview/{meta.storage_key}"
            meta.preview_key = preview_key
            return {"success": True, "file_id": file_id, "preview_key": preview_key, "type": "pdf"}
        return {"success": False, "error": f"Preview not supported for '{meta.extension}' files"}

    def convert(self, file_id: str, target_format: str) -> ConversionTask:
        meta = self._files.get(file_id)
        if not meta:
            raise ValueError("File not found")
        task = ConversionTask(
            task_id=str(uuid.uuid4()), source_file_id=file_id,
            target_format=target_format, status="completed",
            result_file_id=str(uuid.uuid4()),
            created_at=datetime.now(UTC).isoformat(),
        )
        self._conversions.append(task)
        return task

    def list_files(self, tenant_id: str, domain: str = "", extension: str = "",
                    limit: int = 50, offset: int = 0) -> list[FileMetadata]:
        results = [f for f in self._files.values() if f.tenant_id == tenant_id]
        if domain:
            results = [f for f in results if f.domain == domain]
        if extension:
            results = [f for f in results if f.extension == extension]
        return results[offset:offset + limit]

    def _guess_mime(self, ext: str) -> str:
        mime_map = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml",
            "pdf": "application/pdf", "csv": "text/csv", "txt": "text/plain",
            "xls": "application/vnd.ms-excel", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "doc": "application/msword", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "zip": "application/zip", "rar": "application/x-rar-compressed",
        }
        return mime_map.get(ext, "application/octet-stream")


class ChunkedUploadService:
    """分片上传+断点续传(V4 11.2)"""

    CHUNK_SIZE = 5 * 1024 * 1024  # 5MB

    @staticmethod
    def init_upload(filename: str, file_size: int) -> dict:
        chunks = (file_size + ChunkedUploadService.CHUNK_SIZE - 1) // ChunkedUploadService.CHUNK_SIZE
        return {"upload_id": __import__("uuid").uuid4().hex[:16], "filename": filename, "total_size": file_size,
                "chunk_size": ChunkedUploadService.CHUNK_SIZE, "total_chunks": chunks}

    @staticmethod
    def validate_chunk(chunk_index: int, total_chunks: int) -> bool:
        return 0 <= chunk_index < total_chunks

    @staticmethod
    def merge_check(received: list[int], total: int) -> bool:
        return len(received) == total and sorted(received) == list(range(total))
