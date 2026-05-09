from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from erp.shared.observability.logging import get_logger

logger = get_logger("erp.storage")

_minio_client = None


def init_minio(endpoint: str, access_key: str, secret_key: str, bucket: str, region: str = "us-east-1") -> None:
    global _minio_client
    try:
        from minio import Minio

        _minio_client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False,
            region=region,
        )
        _minio_client._bucket = bucket
        _minio_client._region = region
        if not _minio_client.bucket_exists(bucket):
            _minio_client.make_bucket(bucket)
            logger.info("minio_bucket_created", bucket=bucket)
    except ImportError:
        logger.warning("minio_package_not_installed", hint="pip install minio")
    except Exception as e:
        logger.error("minio_init_failed", error=str(e))


def get_minio():
    return _minio_client


class FileStorageService:
    ALLOWED_EXTENSIONS = {
        "jpg", "jpeg", "png", "gif", "webp", "bmp", "svg",
        "pdf", "doc", "docx", "xls", "xlsx", "csv", "txt",
        "zip", "rar", "7z",
    }
    MAX_FILE_SIZE = 50 * 1024 * 1024

    def __init__(self, client=None):
        self._client = client or get_minio()
        self._bucket = getattr(self._client, "_bucket", "erp-assets") if self._client else "erp-assets"

    def _generate_object_key(self, tenant_id: str, domain: str, filename: str) -> str:
        filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        date_prefix = datetime.now(UTC).strftime("%Y/%m/%d")
        unique_id = str(uuid.uuid4())[:8]
        return f"{tenant_id}/{domain}/{date_prefix}/{unique_id}/{filename}"

    async def upload(
        self,
        tenant_id: str,
        domain: str,
        filename: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("MinIO not initialized")

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext and ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(f"File extension '{ext}' is not allowed")

        if len(data) > self.MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum allowed size ({self.MAX_FILE_SIZE // 1024 // 1024}MB)")

        object_key = self._generate_object_key(tenant_id, domain, filename)
        file_hash = hashlib.sha256(data).hexdigest()

        from io import BytesIO
        stream = BytesIO(data)
        self._client.put_object(
            self._bucket,
            object_key,
            stream,
            length=len(data),
            content_type=content_type,
            metadata=metadata or {},
        )

        return {
            "object_key": object_key,
            "bucket": self._bucket,
            "filename": filename,
            "size": len(data),
            "content_type": content_type,
            "file_hash": file_hash,
            "tenant_id": tenant_id,
            "domain": domain,
        }

    async def get_presigned_url(self, object_key: str, expires_seconds: int = 3600) -> str:
        if not self._client:
            raise RuntimeError("MinIO not initialized")
        from datetime import timedelta
        url = self._client.presigned_get_object(
            self._bucket,
            object_key,
            expires=timedelta(seconds=expires_seconds),
        )
        return url

    async def get_presigned_put_url(self, object_key: str, expires_seconds: int = 3600) -> str:
        if not self._client:
            raise RuntimeError("MinIO not initialized")
        from datetime import timedelta
        url = self._client.presigned_put_object(
            self._bucket,
            object_key,
            expires=timedelta(seconds=expires_seconds),
        )
        return url

    async def delete(self, object_key: str) -> bool:
        if not self._client:
            raise RuntimeError("MinIO not initialized")
        self._client.remove_object(self._bucket, object_key)
        return True

    async def get_info(self, object_key: str) -> dict[str, Any] | None:
        if not self._client:
            raise RuntimeError("MinIO not initialized")
        try:
            stat = self._client.stat_object(self._bucket, object_key)
            return {
                "object_key": object_key,
                "size": stat.size,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
                "etag": stat.etag,
            }
        except Exception:
            return None


_storage_service: FileStorageService | None = None


def get_storage_service() -> FileStorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = FileStorageService()
    return _storage_service
