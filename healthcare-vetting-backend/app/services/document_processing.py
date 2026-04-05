"""2.2 Document Processing — image compression, thumbnails, virus scanning, categorisation."""
import hashlib
import io
import os
import subprocess
from pathlib import Path
from typing import BinaryIO, Optional


# ---------------------------------------------------------------------------
# Document Category Detection
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "cv": ["cv", "curriculum vitae", "resume", "résumé"],
    "dbs_certificate": ["dbs", "disclosure", "barring", "criminal record"],
    "identity_document": ["passport", "driving licence", "driving license", "id card", "national insurance", "ni number"],
    "right_to_work": ["right to work", "biometric", "share code", "visa", "brp", "residence permit"],
    "training_cert": ["training", "certificate", "certification", "cpd", "mandatory training", "fire safety", "manual handling", "safeguarding"],
    "qualification": ["degree", "diploma", "qualification", "nursing", "nmc", "gmc", "hcpc", "registration"],
    "reference_letter": ["reference", "referee", "recommendation", "character reference", "employment reference"],
}


def detect_category(file_name: str, content_type: str = "") -> str:
    """Best-effort category detection from filename and content type."""
    name_lower = file_name.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return category
    # Fallback by extension/type
    if content_type.startswith("image/") and any(x in name_lower for x in ["selfie", "photo", "face"]):
        return "identity_document"
    return "other"


# ---------------------------------------------------------------------------
# Image Compression & Thumbnail Generation
# ---------------------------------------------------------------------------

_MAX_IMAGE_DIMENSION = 2048  # Max width or height for compressed images
_THUMBNAIL_SIZE = (200, 200)
_COMPRESSION_QUALITY = 85


def compress_image(file_data: BinaryIO, content_type: str) -> tuple[BinaryIO, int]:
    """Compress an image if it's too large. Returns (compressed_data, new_size).
    Falls back to original if Pillow is unavailable or image is not compressible."""
    if not content_type.startswith("image/"):
        data = file_data.read()
        return io.BytesIO(data), len(data)

    try:
        from PIL import Image

        img = Image.open(file_data)

        # Convert RGBA to RGB for JPEG compatibility
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize if too large
        w, h = img.size
        if w > _MAX_IMAGE_DIMENSION or h > _MAX_IMAGE_DIMENSION:
            ratio = min(_MAX_IMAGE_DIMENSION / w, _MAX_IMAGE_DIMENSION / h)
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        # Compress
        output = io.BytesIO()
        fmt = "JPEG" if content_type in ("image/jpeg", "image/jpg") else "PNG"
        if fmt == "JPEG":
            img.save(output, format=fmt, quality=_COMPRESSION_QUALITY, optimize=True)
        else:
            img.save(output, format=fmt, optimize=True)

        output.seek(0)
        size = output.getbuffer().nbytes
        return output, size

    except Exception:
        # Pillow not available or image processing failed — return original
        file_data.seek(0)
        data = file_data.read()
        return io.BytesIO(data), len(data)


def generate_thumbnail(file_data: BinaryIO, content_type: str) -> Optional[tuple[BinaryIO, str]]:
    """Generate a thumbnail for image files. Returns (thumb_data, thumb_content_type) or None."""
    if not content_type.startswith("image/"):
        return None

    try:
        from PIL import Image

        file_data.seek(0)
        img = Image.open(file_data)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img.thumbnail(_THUMBNAIL_SIZE, Image.LANCZOS)

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=75, optimize=True)
        output.seek(0)
        return output, "image/jpeg"

    except Exception:
        return None


# ---------------------------------------------------------------------------
# File Checksum
# ---------------------------------------------------------------------------

def compute_checksum(file_data: BinaryIO) -> str:
    """Compute SHA-256 checksum of file data. Resets file position after."""
    sha = hashlib.sha256()
    file_data.seek(0)
    while True:
        chunk = file_data.read(8192)
        if not chunk:
            break
        sha.update(chunk)
    file_data.seek(0)
    return sha.hexdigest()


# ---------------------------------------------------------------------------
# Virus Scanning (ClamAV)
# ---------------------------------------------------------------------------

def scan_for_viruses(file_path: str) -> dict:
    """Scan a file using ClamAV (clamscan). Gracefully skips if ClamAV is not installed.

    Returns:
        {"status": "clean|infected|skipped|error", "detail": "..."}
    """
    # Check if clamscan is available
    try:
        result = subprocess.run(["which", "clamscan"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return {"status": "skipped", "detail": "ClamAV not installed — virus scanning skipped"}
    except Exception:
        return {"status": "skipped", "detail": "Could not check for ClamAV"}

    try:
        result = subprocess.run(
            ["clamscan", "--no-summary", "--infected", file_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return {"status": "clean", "detail": "No threats detected"}
        elif result.returncode == 1:
            return {"status": "infected", "detail": result.stdout.strip() or "Threat detected"}
        else:
            return {"status": "error", "detail": result.stderr.strip() or "Scan failed"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "detail": "Virus scan timed out"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def scan_bytes_for_viruses(file_data: BinaryIO) -> dict:
    """Scan file data in memory via a temp file. Returns scan result dict."""
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".scan") as tmp:
            file_data.seek(0)
            tmp.write(file_data.read())
            tmp_path = tmp.name
            file_data.seek(0)

        result = scan_for_viruses(tmp_path)

        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        return result
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ---------------------------------------------------------------------------
# File Size Validation
# ---------------------------------------------------------------------------

_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
_ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain", "text/csv",
}


def validate_upload(file_size: int, content_type: str, file_name: str) -> Optional[str]:
    """Validate an upload. Returns error message or None if valid."""
    if file_size > _MAX_FILE_SIZE:
        return f"File too large ({file_size / 1024 / 1024:.1f} MB). Maximum is {_MAX_FILE_SIZE / 1024 / 1024:.0f} MB."
    if content_type not in _ALLOWED_CONTENT_TYPES:
        return f"File type '{content_type}' is not allowed. Allowed: PDF, images, Word documents, text files."
    # Check for suspicious extensions
    ext = Path(file_name).suffix.lower()
    dangerous = {".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs", ".js", ".msi", ".dll", ".com"}
    if ext in dangerous:
        return f"File extension '{ext}' is not allowed for security reasons."
    return None
