from __future__ import annotations

import io
import mimetypes
import tempfile
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Iterator
from uuid import uuid4

try:
    from minio import Minio
    from minio.error import S3Error
    _MINIO_IMPORT_ERROR = None
except ModuleNotFoundError as exc:
    Minio = None  # type: ignore[assignment]
    S3Error = Exception  # type: ignore[assignment]
    _MINIO_IMPORT_ERROR = exc

from core.config import settings


class StorageService:
    def __init__(self) -> None:
        if Minio is None:
            raise RuntimeError(
                "MinIO Python SDK 未安装，请先执行 `pip install -r requirements.txt`"
            ) from _MINIO_IMPORT_ERROR

        endpoint = str(settings.MINIO_ENDPOINT or "").strip()
        access_key = str(settings.MINIO_ACCESS_KEY or "").strip()
        secret_key = str(settings.MINIO_SECRET_KEY or "").strip()
        if not endpoint or not access_key or not secret_key:
            raise RuntimeError("MinIO 配置未完成，请检查 MINIO_ENDPOINT / MINIO_ACCESS_KEY / MINIO_SECRET_KEY")

        self.bucket = settings.MINIO_BUCKET
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=bool(settings.MINIO_SECURE),
            region=settings.MINIO_REGION or None,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        found = self.client.bucket_exists(self.bucket)
        if not found:
            self.client.make_bucket(self.bucket)

    def build_object_key(self, category: str, filename: str) -> str:
        safe_name = Path(filename).name or "file"
        ext = Path(safe_name).suffix
        stem = Path(safe_name).stem or "file"
        object_name = f"{stem}_{uuid4().hex[:12]}{ext}"
        return f"{category.strip('/').replace(' ', '_')}/{object_name}"

    def upload_bytes(self, object_key: str, content: bytes, content_type: str | None = None) -> str:
        guessed_type = content_type or mimetypes.guess_type(object_key)[0] or "application/octet-stream"
        self.client.put_object(
            self.bucket,
            object_key,
            io.BytesIO(content),
            length=len(content),
            content_type=guessed_type,
        )
        return object_key

    def remove_object(self, object_key: str) -> None:
        if not object_key or object_key.startswith(("http://", "https://", "data:")):
            return
        try:
            self.client.remove_object(self.bucket, object_key)
        except S3Error:
            return

    def get_download_url(self, object_key: str, expires: timedelta | None = None) -> str:
        if not object_key:
            return ""
        if object_key.startswith(("http://", "https://", "data:")):
            return object_key

        public_base = str(settings.MINIO_PUBLIC_BASE_URL or "").strip().rstrip("/")
        if public_base:
            return f"{public_base}/{self.bucket}/{object_key}"

        return self.client.presigned_get_object(
            self.bucket,
            object_key,
            expires=expires or timedelta(days=7),
        )

    @contextmanager
    def download_to_tempfile(self, object_key: str, suffix: str = "") -> Iterator[Path]:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)
        try:
            self.client.fget_object(self.bucket, object_key, str(temp_path))
            yield temp_path
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def download_persistent_tempfile(self, object_key: str, suffix: str = "") -> Path:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)
        self.client.fget_object(self.bucket, object_key, str(temp_path))
        return temp_path


_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
