"""2.2 Document Upload & Storage — API routes."""
import io
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from typing import Optional

from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Query("other"),
    candidate_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Upload a document (multipart file upload)."""
    from app.services.document_processing import (
        validate_upload, detect_category, compress_image,
        generate_thumbnail, compute_checksum, scan_bytes_for_viruses,
    )
    from app.services.document_storage import (
        get_storage_backend, store_document_record, update_virus_scan,
    )

    # Read file
    file_data = await file.read()
    file_size = len(file_data)
    content_type = file.content_type or "application/octet-stream"
    file_name = file.filename or "unnamed"

    # Validate
    err = validate_upload(file_size, content_type, file_name)
    if err:
        raise HTTPException(status_code=400, detail=err)

    # Auto-detect category if not provided
    if category == "other" or category == "auto":
        category = detect_category(file_name, content_type)

    # Determine ownership
    user_type = current_user.get("type", "candidate")
    owner_id = current_user.get("sub", "")
    agency_id = None
    cand_id = candidate_id

    if user_type == "candidate":
        cand_id = owner_id
    elif user_type == "agency":
        agency_id = owner_id
    elif user_type == "admin":
        agency_id = None  # Admin uploads are not agency-scoped

    # Compute checksum
    file_stream = io.BytesIO(file_data)
    checksum = compute_checksum(file_stream)

    # Compress images
    file_stream.seek(0)
    compressed, compressed_size = compress_image(file_stream, content_type)

    # Generate thumbnail for images
    compressed.seek(0)
    thumb_result = generate_thumbnail(compressed, content_type)

    # Upload main file
    storage = get_storage_backend()
    compressed.seek(0)
    storage_key = storage.upload(
        compressed, file_name, content_type,
        {"owner_id": owner_id, "category": category, "candidate_id": cand_id or ""},
    )

    # Upload thumbnail if generated
    thumbnail_key = None
    if thumb_result:
        thumb_data, thumb_ct = thumb_result
        thumb_name = f"thumb_{file_name}"
        thumbnail_key = storage.upload(thumb_data, thumb_name, thumb_ct, {"type": "thumbnail"})

    # Store metadata in DB
    doc = store_document_record(
        owner_id=owner_id,
        owner_type=user_type,
        file_name=file_name,
        content_type=content_type,
        file_size=compressed_size,
        storage_key=storage_key,
        category=category,
        thumbnail_key=thumbnail_key,
        checksum=checksum,
        agency_id=agency_id,
        candidate_id=cand_id,
    )

    # Virus scan (async-ish — scan in-process but don't block response if slow)
    try:
        compressed.seek(0)
        scan_result = scan_bytes_for_viruses(compressed)
        update_virus_scan(doc["id"], scan_result["status"])
        doc["virus_scan_status"] = scan_result["status"]
        doc["virus_scan_detail"] = scan_result.get("detail", "")
        if scan_result["status"] == "infected":
            # Delete infected file immediately
            from app.services.document_storage import delete_document
            delete_document(doc["id"])
            raise HTTPException(status_code=400, detail=f"File rejected: {scan_result['detail']}")
    except HTTPException:
        raise
    except Exception:
        doc["virus_scan_status"] = "skipped"

    return doc


@router.get("")
async def list_documents(
    candidate_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """List documents for the authenticated user."""
    from app.services.document_storage import list_documents as _list

    user_type = current_user.get("type", "candidate")
    owner_id = current_user.get("sub", "")

    if user_type == "candidate":
        docs = _list(owner_id=owner_id, category=category)
    elif user_type == "agency":
        docs = _list(agency_id=owner_id, candidate_id=candidate_id, category=category)
    elif user_type == "admin":
        docs = _list(candidate_id=candidate_id, category=category)
    else:
        docs = []

    return {"documents": docs}


@router.get("/{doc_id}")
async def download_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    """Download a document by ID."""
    from app.services.document_storage import get_document, get_storage_backend

    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Access control
    user_type = current_user.get("type", "candidate")
    owner_id = current_user.get("sub", "")
    if user_type == "candidate" and doc["owner_id"] != owner_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if user_type == "agency" and doc.get("agency_id") != owner_id and doc["owner_id"] != owner_id:
        raise HTTPException(status_code=403, detail="Access denied")

    storage = get_storage_backend()
    try:
        data_stream, filename, content_type = storage.download(doc["storage_key"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found in storage")

    return StreamingResponse(
        data_stream,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{doc_id}/signed-url")
async def get_signed_url(doc_id: str, current_user: dict = Depends(get_current_user)):
    """Get a time-limited signed URL for a document."""
    from app.services.document_storage import get_document, get_storage_backend

    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Access control
    user_type = current_user.get("type", "candidate")
    owner_id = current_user.get("sub", "")
    if user_type == "candidate" and doc["owner_id"] != owner_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if user_type == "agency" and doc.get("agency_id") != owner_id and doc["owner_id"] != owner_id:
        raise HTTPException(status_code=403, detail="Access denied")

    storage = get_storage_backend()
    url = storage.get_signed_url(doc["storage_key"], expires_seconds=3600)

    return {"signed_url": url, "expires_in": 3600}


@router.get("/signed-download")
async def signed_download(key: str, expires: int, sig: str):
    """Download a file via a signed URL (no auth required — signature is the auth)."""
    from app.services.document_storage import verify_signed_url, get_storage_backend

    if not verify_signed_url(key, expires, sig):
        raise HTTPException(status_code=403, detail="Invalid or expired signed URL")

    storage = get_storage_backend()
    try:
        data_stream, filename, content_type = storage.download(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

    return StreamingResponse(
        data_stream,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.delete("/{doc_id}")
async def delete_doc(doc_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a document."""
    from app.services.document_storage import get_document, delete_document

    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Access control
    user_type = current_user.get("type", "candidate")
    owner_id = current_user.get("sub", "")
    if user_type == "candidate" and doc["owner_id"] != owner_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if user_type not in ("admin", "agency") and doc["owner_id"] != owner_id:
        raise HTTPException(status_code=403, detail="Access denied")

    delete_document(doc_id)
    return {"message": "Document deleted", "id": doc_id}


@router.post("/retention-cleanup")
async def run_retention_cleanup(current_user: dict = Depends(get_current_user)):
    """Run retention policy enforcement — admin only."""
    if current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    from app.services.document_storage import enforce_retention_policy
    count = enforce_retention_policy()
    return {"message": f"Retention cleanup complete", "documents_deleted": count}
