from io import BytesIO
from typing import Protocol

from app.core.config import Settings, get_settings


class StorageError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class ObjectStore(Protocol):
    def put_object(self, key: str, data: bytes, content_type: str) -> None: ...

    def get_object(self, key: str) -> bytes: ...

    def delete_object(self, key: str) -> None: ...


class MemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put_object(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def get_object(self, key: str) -> bytes:
        try:
            return self.objects[key][0]
        except KeyError as exc:
            raise StorageError("Stored file was not found") from exc

    def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)


class MinioObjectStore:
    def __init__(self, settings: Settings | None = None) -> None:
        from minio import Minio

        settings = settings or get_settings()
        self.bucket = settings.minio_bucket
        region = settings.minio_region.strip()
        if not region and "r2.cloudflarestorage.com" in settings.minio_endpoint:
            region = "auto"
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            region=region or None,
        )

    def put_object(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self.client.put_object(
                self.bucket,
                key,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        except Exception as exc:
            raise StorageError("Could not store the document") from exc

    def get_object(self, key: str) -> bytes:
        try:
            response = self.client.get_object(self.bucket, key)
        except Exception as exc:
            raise StorageError("Could not read the document") from exc
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete_object(self, key: str) -> None:
        try:
            self.client.remove_object(self.bucket, key)
        except Exception as exc:
            raise StorageError("Could not delete the stored document") from exc


def get_object_store() -> ObjectStore:
    return MinioObjectStore()
