"""2.2 Document Upload & Storage — abstraction layer (local disk now, S3/R2 ready).

Storage backends:
  - LocalStorage: stores files on disk under /data/documents/
  - S3Storage: ready for AWS S3 or Cloudflare R2 (just add credentials)

All backends implement the same interface so they are swappable via config.
"""
import hashlib
import hmac
import io
import json
import mimetypes
import os
import shutil
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO, Optional

from app.database import get_db
from app.utils.auth import generate_id


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class StorageBackend(ABC):
    """Interface every storage backend must implement."""

    @abstractmethod
    def upload(self, file_data: BinaryIO, file_name: str, content_type: str, metadata: dict) -> str:
        """Upload a file. Returns the storage key (path/key)."""

    @abstractmethod
    def download(self, storage_key: str) -> tuple[BinaryIO, str, str]:
        """Download a file. Returns (data stream, filename, content_type)."""

    @abstractmethod
    def delete(self, storage_key: str) -> bool:
        """Delete a file. Returns True if deleted."""

    @abstractmethod
    def get_signed_url(self, storage_key: str, expires_seconds: int = 3600) -> str:
        """Generate a time-limited signed URL for direct browser access."""

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        """Check whether a file exists."""


# ---------------------------------------------------------------------------
# Local Disk Storage
# ---------------------------------------------------------------------------

_LOCAL_ROOT = Path(os.environ.get("DOCUMENT_STORAGE_PATH", "/data/documents"))
_SIGNED_URL_SECRET = os.environ.get("SIGNED_URL_SECRET", "healthvet-local-dev-secret-change-in-prod")


class LocalStorage(StorageBackend):
    """Stores files on the local filesystem."""

    def __init__(self, root: Path | None = None):
        self.root = root or _LOCAL_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    def _key_path(self, key: str) -> Path:
        return self.root / key

    def upload(self, file_data: BinaryIO, file_name: str, content_type: str, metadata: dict) -> str:
        # Organise by date + random prefix for uniqueness
        today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        ext = Path(file_name).suffix or ""
        unique = uuid.uuid4().hex[:12]
        safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in Path(file_name).stem)[:80]
        key = f"{today}/{unique}_{safe_name}{ext}"

        dest = self._key_path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)

        with open(dest, "wb") as f:
            shutil.copyfileobj(file_data, f)

        # Store metadata alongside
        meta_path = dest.with_suffix(dest.suffix + ".meta.json")
        with open(meta_path, "w") as f:
            json.dump({**metadata, "content_type": content_type, "original_name": file_name, "uploaded_at": datetime.now(timezone.utc).isoformat()}, f)

        return key

    def download(self, storage_key: str) -> tuple[BinaryIO, str, str]:
        path = self._key_path(storage_key)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {storage_key}")

        # Read metadata
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        content_type = "application/octet-stream"
        original_name = path.name
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
                content_type = meta.get("content_type", content_type)
                original_name = meta.get("original_name", original_name)

        return open(path, "rb"), original_name, content_type

    def delete(self, storage_key: str) -> bool:
        path = self._key_path(storage_key)
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        thumb_path = path.parent / f"thumb_{path.name}"
        deleted = False
        for p in (path, meta_path, thumb_path):
            if p.exists():
                p.unlink()
                deleted = True
        return deleted

    def get_signed_url(self, storage_key: str, expires_seconds: int = 3600) -> str:
        """Generate an HMAC-signed URL that the download endpoint can verify."""
        expires_at = int(time.time()) + expires_seconds
        payload = f"{storage_key}:{expires_at}"
        signature = hmac.new(_SIGNED_URL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        # The frontend calls /api/documents/signed-download?key=...&expires=...&sig=...
        return f"/api/documents/signed-download?key={storage_key}&expires={expires_at}&sig={signature}"

    def exists(self, storage_key: str) -> bool:
        return self._key_path(storage_key).exists()


# ---------------------------------------------------------------------------
# S3/R2 Storage (stub — ready for credentials)
# ---------------------------------------------------------------------------

class S3Storage(StorageBackend):
    """AWS S3 / Cloudflare R2 storage backend. Requires boto3 and credentials."""

    def __init__(self, bucket: str, region: str = "eu-west-2", endpoint_url: str | None = None):
        self.bucket = bucket
        self.region = region
        self.endpoint_url = endpoint_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3
            kwargs: dict = {"region_name": self.region}
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            self._client = boto3.client("s3", **kwargs)
        return self._client

    def upload(self, file_data: BinaryIO, file_name: str, content_type: str, metadata: dict) -> str:
        today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        ext = Path(file_name).suffix or ""
        unique = uuid.uuid4().hex[:12]
        safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in Path(file_name).stem)[:80]
        key = f"{today}/{unique}_{safe_name}{ext}"

        s3 = self._get_client()
        s3.upload_fileobj(
            file_data, self.bucket, key,
            ExtraArgs={"ContentType": content_type, "Metadata": {k: str(v) for k, v in metadata.items()}},
        )
        return key

    def download(self, storage_key: str) -> tuple[BinaryIO, str, str]:
        s3 = self._get_client()
        response = s3.get_object(Bucket=self.bucket, Key=storage_key)
        content_type = response.get("ContentType", "application/octet-stream")
        original_name = response.get("Metadata", {}).get("original_name", storage_key.split("/")[-1])
        return response["Body"], original_name, content_type

    def delete(self, storage_key: str) -> bool:
        s3 = self._get_client()
        s3.delete_object(Bucket=self.bucket, Key=storage_key)
        return True

    def get_signed_url(self, storage_key: str, expires_seconds: int = 3600) -> str:
        s3 = self._get_client()
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": storage_key},
            ExpiresIn=expires_seconds,
        )

    def exists(self, storage_key: str) -> bool:
        s3 = self._get_client()
        try:
            s3.head_object(Bucket=self.bucket, Key=storage_key)
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Factory — pick backend based on environment
# ---------------------------------------------------------------------------

def get_storage_backend() -> StorageBackend:
    """Return the configured storage backend."""
    backend = os.environ.get("DOCUMENT_STORAGE_BACKEND", "local")
    if backend == "s3":
        bucket = os.environ.get("S3_BUCKET", "healthvet-documents")
        region = os.environ.get("S3_REGION", "eu-west-2")
        endpoint = os.environ.get("S3_ENDPOINT_URL")  # For Cloudflare R2
        return S3Storage(bucket=bucket, region=region, endpoint_url=endpoint)
    return LocalStorage()


def verify_signed_url(storage_key: str, expires: int, signature: str) -> bool:
    """Verify an HMAC-signed URL is valid and not expired."""
    if int(time.time()) > expires:
        return False
    payload = f"{storage_key}:{expires}"
    expected = hmac.new(_SIGNED_URL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Document metadata DB operations
# ---------------------------------------------------------------------------

_DOCUMENT_CATEGORIES = {
    "identity_document", "dbs_certificate", "training_cert", "cv",
    "right_to_work", "reference_letter", "qualification", "other",
}

# UK healthcare retention: 6 years from last activity (or longer for specific records)
_RETENTION_YEARS = 6


def _ensure_table():
    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            owner_type TEXT NOT NULL DEFAULT 'candidate',
            agency_id TEXT,
            candidate_id TEXT,
            file_name TEXT NOT NULL,
            content_type TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            storage_key TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'other',
            thumbnail_key TEXT,
            checksum_sha256 TEXT,
            virus_scan_status TEXT DEFAULT 'pending',
            virus_scan_at TEXT,
            retention_expires_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")


def store_document_record(
    owner_id: str,
    owner_type: str,
    file_name: str,
    content_type: str,
    file_size: int,
    storage_key: str,
    category: str = "other",
    thumbnail_key: str | None = None,
    checksum: str | None = None,
    agency_id: str | None = None,
    candidate_id: str | None = None,
) -> dict:
    """Insert a document metadata record into the DB."""
    _ensure_table()
    doc_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()
    retention = (datetime.now(timezone.utc) + timedelta(days=_RETENTION_YEARS * 365)).isoformat()
    cat = category if category in _DOCUMENT_CATEGORIES else "other"

    with get_db() as db:
        db.execute(
            """INSERT INTO documents
               (id, owner_id, owner_type, agency_id, candidate_id, file_name, content_type,
                file_size, storage_key, category, thumbnail_key, checksum_sha256,
                virus_scan_status, retention_expires_at, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (doc_id, owner_id, owner_type, agency_id, candidate_id, file_name,
             content_type, file_size, storage_key, cat, thumbnail_key, checksum,
             "pending", retention, now, now),
        )

    return {
        "id": doc_id, "owner_id": owner_id, "owner_type": owner_type,
        "file_name": file_name, "content_type": content_type, "file_size": file_size,
        "storage_key": storage_key, "category": cat, "thumbnail_key": thumbnail_key,
        "created_at": now, "retention_expires_at": retention,
    }


def get_document(doc_id: str) -> dict | None:
    _ensure_table()
    with get_db() as db:
        row = db.execute("SELECT * FROM documents WHERE id=%s", (doc_id,)).fetchone()
        return dict(row) if row else None


def list_documents(owner_id: str | None = None, candidate_id: str | None = None,
                   agency_id: str | None = None, category: str | None = None,
                   limit: int = 100) -> list[dict]:
    _ensure_table()
    with get_db() as db:
        clauses = []
        params: list = []
        if owner_id:
            clauses.append("owner_id=%s"); params.append(owner_id)
        if candidate_id:
            clauses.append("candidate_id=%s"); params.append(candidate_id)
        if agency_id:
            clauses.append("agency_id=%s"); params.append(agency_id)
        if category:
            clauses.append("category=%s"); params.append(category)
        where = " AND ".join(clauses) if clauses else "1=1"
        rows = db.execute(f"SELECT * FROM documents WHERE {where} ORDER BY created_at DESC LIMIT %s", (*params, limit)).fetchall()
        return [dict(r) for r in rows]


def delete_document(doc_id: str) -> bool:
    _ensure_table()
    doc = get_document(doc_id)
    if not doc:
        return False
    storage = get_storage_backend()
    storage.delete(doc["storage_key"])
    if doc.get("thumbnail_key"):
        storage.delete(doc["thumbnail_key"])
    with get_db() as db:
        db.execute("DELETE FROM documents WHERE id=%s", (doc_id,))
    return True


def update_virus_scan(doc_id: str, status: str):
    _ensure_table()
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute("UPDATE documents SET virus_scan_status=%s, virus_scan_at=%s, updated_at=%s WHERE id=%s",
                    (status, now, now, doc_id))


def enforce_retention_policy() -> int:
    """Delete documents past their retention date. Returns count deleted."""
    _ensure_table()
    now = datetime.now(timezone.utc).isoformat()
    storage = get_storage_backend()
    with get_db() as db:
        expired = db.execute(
            "SELECT id, storage_key, thumbnail_key FROM documents WHERE retention_expires_at < %s", (now,)
        ).fetchall()
        count = 0
        for row in expired:
            try:
                storage.delete(row["storage_key"])
                if row["thumbnail_key"]:
                    storage.delete(row["thumbnail_key"])
                db.execute("DELETE FROM documents WHERE id=%s", (row["id"],))
                count += 1
            except Exception:
                pass
    return count
