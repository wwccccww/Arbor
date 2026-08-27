from __future__ import annotations

import os
import re

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - optional s3 extra
    ClientError = None

from arbor.domain.errors import DomainError
from arbor.env import load_dotenv


def s3_configured() -> bool:
    load_dotenv()
    bucket = (os.environ.get("ARBOR_S3_BUCKET") or "").strip()
    endpoint = (os.environ.get("ARBOR_S3_ENDPOINT") or os.environ.get("S3_ENDPOINT") or "").strip()
    access = (
        os.environ.get("ARBOR_S3_ACCESS_KEY")
        or os.environ.get("AWS_ACCESS_KEY_ID")
        or ""
    ).strip()
    secret = (
        os.environ.get("ARBOR_S3_SECRET_KEY")
        or os.environ.get("AWS_SECRET_ACCESS_KEY")
        or ""
    ).strip()
    return bool(bucket and endpoint and access and secret)


class S3ObjectStorage:
    """S3-compatible object storage (AWS S3, MinIO, etc.)."""

    def __init__(
        self,
        *,
        bucket: str,
        client,
        prefix: str = "",
    ) -> None:
        self.bucket = bucket
        self.client = client
        self.prefix = prefix.strip("/")

    @classmethod
    def from_env(cls) -> S3ObjectStorage:
        load_dotenv()
        bucket = (os.environ.get("ARBOR_S3_BUCKET") or "").strip()
        endpoint = (os.environ.get("ARBOR_S3_ENDPOINT") or os.environ.get("S3_ENDPOINT") or "").strip()
        access = (
            os.environ.get("ARBOR_S3_ACCESS_KEY")
            or os.environ.get("AWS_ACCESS_KEY_ID")
            or ""
        ).strip()
        secret = (
            os.environ.get("ARBOR_S3_SECRET_KEY")
            or os.environ.get("AWS_SECRET_ACCESS_KEY")
            or ""
        ).strip()
        region = (os.environ.get("ARBOR_S3_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1").strip()
        prefix = (os.environ.get("ARBOR_S3_PREFIX") or "arbor/").strip()
        if not bucket or not endpoint or not access or not secret:
            raise DomainError(
                "VALIDATION_ERROR",
                "S3 requires ARBOR_S3_BUCKET, ARBOR_S3_ENDPOINT, ARBOR_S3_ACCESS_KEY, ARBOR_S3_SECRET_KEY",
            )
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise DomainError(
                "VALIDATION_ERROR",
                "S3 backend requires boto3; pip install -e '.[s3]'",
            ) from exc
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )
        return cls(bucket=bucket, client=client, prefix=prefix)

    def _key(self, name: str) -> str:
        safe = re.sub(r"/+", "/", (name or "").replace("\\", "/").lstrip("/"))
        if self.prefix:
            return f"{self.prefix}/{safe}".strip("/")
        return safe

    def put(self, name: str, data: bytes) -> str:
        key = self._key(name)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return key

    def get(self, name: str) -> bytes | None:
        raw = (name or "").replace("\\", "/").lstrip("/")
        candidates = [raw]
        keyed = self._key(name)
        if keyed not in candidates:
            candidates.append(keyed)
        for key in candidates:
            try:
                response = self.client.get_object(Bucket=self.bucket, Key=key)
            except Exception as exc:
                if ClientError is not None and isinstance(exc, ClientError):
                    code = exc.response.get("Error", {}).get("Code", "")
                    if code in {"NoSuchKey", "404", "NotFound"}:
                        continue
                raise
            body = response["Body"].read()
            return bytes(body) if body is not None else None
        return None

    def delete(self, name: str) -> bool:
        raw = (name or "").replace("\\", "/").lstrip("/")
        candidates = [raw]
        keyed = self._key(name)
        if keyed not in candidates:
            candidates.append(keyed)
        deleted = False
        for key in candidates:
            try:
                self.client.delete_object(Bucket=self.bucket, Key=key)
                deleted = True
            except Exception as exc:
                if ClientError is not None and isinstance(exc, ClientError):
                    code = exc.response.get("Error", {}).get("Code", "")
                    if code in {"NoSuchKey", "404", "NotFound"}:
                        continue
                raise
        return deleted

    def count(self) -> int:
        total = 0
        prefix = self.prefix or ""
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            total += len(page.get("Contents") or [])
        return total

    def list_keys(self, prefix: str = "") -> list[str]:
        search_prefix = self._key(prefix) if prefix else (self.prefix or "")
        keys: list[str] = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=search_prefix):
            for item in page.get("Contents") or []:
                key = str(item.get("Key") or "")
                if key:
                    keys.append(key)
        return sorted(keys)
