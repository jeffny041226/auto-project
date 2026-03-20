"""MinIO client for file storage."""
import io
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.config import settings


class MinIOClient:
    """MinIO client wrapper for object storage."""

    def __init__(self):
        self._client: Optional[Minio] = None
        self._bucket: str = settings.MINIO_BUCKET

    def connect(self) -> None:
        """Initialize MinIO client."""
        self._client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Ensure the bucket exists."""
        if not self._client:
            raise RuntimeError("MinIO not connected")
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
        except S3Error as e:
            if "BucketAlreadyOwnedByYou" not in str(e):
                raise

    @property
    def client(self) -> Minio:
        """Get MinIO client."""
        if not self._client:
            raise RuntimeError("MinIO not connected. Call connect() first.")
        return self._client

    def upload_file(
        self,
        object_name: str,
        data: bytes | io.IOBase,
        length: Optional[int] = None,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload file to MinIO.

        Returns the object URL.
        """
        if isinstance(data, bytes):
            data = io.BytesIO(data)
            length = len(data.getvalue()) if length is None else length

        self.client.put_object(
            self._bucket,
            object_name,
            data,
            length or -1,
            content_type=content_type,
        )
        return f"{settings.MINIO_ENDPOINT}/{self._bucket}/{object_name}"

    def download_file(self, object_name: str) -> bytes:
        """Download file from MinIO."""
        response = self.client.get_object(self._bucket, object_name)
        data = response.read()
        response.close()
        response.release_conn()
        return data

    def delete_file(self, object_name: str) -> None:
        """Delete file from MinIO."""
        self.client.remove_object(self._bucket, object_name)

    def get_presigned_url(
        self,
        object_name: str,
        expires_seconds: int = 3600,
    ) -> str:
        """Get presigned URL for download."""
        return self.client.presigned_get_object(
            self._bucket,
            object_name,
            expires=expires_seconds,
        )

    def list_objects(self, prefix: str = "") -> list[str]:
        """List objects with prefix."""
        objects = self.client.list_objects(self._bucket, prefix=prefix)
        return [obj.object_name for obj in objects]


# Global MinIO client instance
minio_client = MinIOClient()


def get_minio() -> MinIOClient:
    """Dependency to get MinIO client."""
    return minio_client
