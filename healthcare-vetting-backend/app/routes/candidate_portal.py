"""2.1 Candidate Self-Service Portal: compliance dashboard, document upload, check timeline, SSE."""
import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from app.database import get_db
from app.utils.auth import get_current_user, generate_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/candidates/portal", tags=["Candidate Portal"])

UPLOAD_DIR = os.environ.get("CANDIDATE_UPLOAD_DIR", "/tmp/candidate_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/dashboard")
async def candidate_dashboard(request: Request, current_user: dict = Depends(get_current_user)):
    """Return the candidate's full compliance dashboard with status per check type."""
    if current_user.get("type") != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access only")

    candidate_id = current_user["sub"]
    with get_db() as db:
        candidate = db.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,)).fetchone()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        candidate = dict(candidate)

        # Gather compliance data across all check types
        checks = {}

        # 1. Identity verification
        id_check = db.execute(
            "SELECT status, created_at, updated_at FROM compliance_checks WHERE candidate_id=%s AND check_type='identity' ORDER BY created_at DESC LIMIT 1",
            (candidate_id,),
        ).fetchone()
        checks["identity"] = _format_check(id_check, "Identity Verification")

        # 2. DBS check
        dbs_check = db.execute(
            "SELECT status, created_at, updated_at FROM compliance_checks WHERE candidate_id=%s AND check_type='dbs' ORDER BY created_at DESC LIMIT 1",
            (candidate_id,),
        ).fetchone()
        checks["dbs"] = _format_check(dbs_check, "DBS Check")

        # 3. Right to Work
        rtw_check = db.execute(
            "SELECT status, created_at, updated_at FROM compliance_checks WHERE candidate_id=%s AND check_type='right_to_work' ORDER BY created_at DESC LIMIT 1",
            (candidate_id,),
        ).fetchone()
        checks["right_to_work"] = _format_check(rtw_check, "Right to Work")

        # 4. Professional Registration
        reg_check = db.execute(
            "SELECT status, created_at, updated_at FROM compliance_checks WHERE candidate_id=%s AND check_type='professional_registration' ORDER BY created_at DESC LIMIT 1",
            (candidate_id,),
        ).fetchone()
        checks["professional_registration"] = _format_check(reg_check, "Professional Registration")

        # 5. References
        refs = db.execute(
            "SELECT * FROM references_ WHERE candidate_id=%s ORDER BY created_at DESC",
            (candidate_id,),
        ).fetchall()
        ref_statuses = [dict(r) for r in refs] if refs else []
        completed_refs = sum(1 for r in ref_statuses if r.get("status") == "completed")
        checks["references"] = {
            "label": "References",
            "status": "completed" if completed_refs >= 2 else ("in_progress" if ref_statuses else "not_started"),
            "detail": f"{completed_refs}/{max(len(ref_statuses), 2)} references completed",
            "items": ref_statuses,
        }

        # 6. Employment verification
        emp_vers = db.execute(
            "SELECT * FROM employment_verifications WHERE candidate_id=%s ORDER BY created_at DESC",
            (candidate_id,),
        ).fetchall()
        emp_list = [dict(e) for e in emp_vers] if emp_vers else []
        completed_emp = sum(1 for e in emp_list if e.get("status") == "completed")
        checks["employment"] = {
            "label": "Employment History",
            "status": "completed" if emp_list and completed_emp == len(emp_list) else ("in_progress" if emp_list else "not_started"),
            "detail": f"{completed_emp}/{len(emp_list)} verifications completed",
            "items": emp_list,
        }

        # 7. Training & qualifications
        training_check = db.execute(
            "SELECT status, created_at, updated_at FROM compliance_checks WHERE candidate_id=%s AND check_type='training' ORDER BY created_at DESC LIMIT 1",
            (candidate_id,),
        ).fetchone()
        checks["training"] = _format_check(training_check, "Training & Qualifications")

        # 8. Documents uploaded
        docs = db.execute(
            "SELECT * FROM candidate_documents WHERE candidate_id=%s ORDER BY uploaded_at DESC",
            (candidate_id,),
        ).fetchall()
        doc_list = [dict(d) for d in docs] if docs else []

        # Overall compliance score
        total = len(checks)
        completed = sum(1 for c in checks.values() if c["status"] == "completed")
        in_progress = sum(1 for c in checks.values() if c["status"] == "in_progress")

        # Pre-notifications pending
        notifications = db.execute(
            "SELECT * FROM candidate_pre_notifications WHERE candidate_id=%s AND status='pending' ORDER BY created_at DESC",
            (candidate_id,),
        ).fetchall()
        pending_notifications = [dict(n) for n in notifications] if notifications else []

    return {
        "candidate": {
            "id": candidate["id"],
            "email": candidate["email"],
            "first_name": candidate.get("first_name", ""),
            "last_name": candidate.get("last_name", ""),
        },
        "compliance_score": round((completed / total) * 100, 1) if total else 0,
        "summary": {"total": total, "completed": completed, "in_progress": in_progress, "not_started": total - completed - in_progress},
        "checks": checks,
        "documents": doc_list,
        "pending_notifications": pending_notifications,
    }


@router.get("/timeline")
async def candidate_timeline(request: Request, current_user: dict = Depends(get_current_user)):
    """Return a chronological timeline of all compliance events for a candidate."""
    if current_user.get("type") != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access only")

    candidate_id = current_user["sub"]
    events = []

    with get_db() as db:
        # Compliance checks
        rows = db.execute(
            "SELECT check_type, status, created_at, updated_at FROM compliance_checks WHERE candidate_id=%s ORDER BY created_at DESC",
            (candidate_id,),
        ).fetchall()
        for r in rows:
            r = dict(r)
            events.append({
                "type": "compliance_check",
                "check_type": r["check_type"],
                "status": r["status"],
                "date": r.get("updated_at") or r["created_at"],
                "description": f"{r['check_type'].replace('_', ' ').title()} — {r['status']}",
            })

        # References
        refs = db.execute(
            "SELECT referee_name, status, created_at FROM references_ WHERE candidate_id=%s ORDER BY created_at DESC",
            (candidate_id,),
        ).fetchall()
        for r in refs:
            r = dict(r)
            events.append({
                "type": "reference",
                "status": r["status"],
                "date": r["created_at"],
                "description": f"Reference from {r.get('referee_name', 'Unknown')} — {r['status']}",
            })

        # Employment verifications
        emps = db.execute(
            "SELECT employer_name, status, created_at FROM employment_verifications WHERE candidate_id=%s ORDER BY created_at DESC",
            (candidate_id,),
        ).fetchall()
        for e in emps:
            e = dict(e)
            events.append({
                "type": "employment_verification",
                "status": e["status"],
                "date": e["created_at"],
                "description": f"Employment at {e.get('employer_name', 'Unknown')} — {e['status']}",
            })

        # Documents
        docs = db.execute(
            "SELECT document_type, uploaded_at FROM candidate_documents WHERE candidate_id=%s ORDER BY uploaded_at DESC",
            (candidate_id,),
        ).fetchall()
        for d in docs:
            d = dict(d)
            events.append({
                "type": "document_upload",
                "status": "uploaded",
                "date": d["uploaded_at"],
                "description": f"Document uploaded: {d.get('document_type', 'Unknown')}",
            })

    # Sort by date descending
    events.sort(key=lambda x: x.get("date") or "", reverse=True)
    return {"timeline": events}


@router.post("/documents")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    document_type: str = Form("other"),
    description: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    """Upload a document (stored on local disk)."""
    if current_user.get("type") != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access only")

    candidate_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()
    doc_id = generate_id()

    # Save file to disk
    candidate_dir = os.path.join(UPLOAD_DIR, candidate_id)
    os.makedirs(candidate_dir, exist_ok=True)
    safe_name = f"{doc_id}_{file.filename}"
    file_path = os.path.join(candidate_dir, safe_name)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    file_size = os.path.getsize(file_path)

    with get_db() as db:
        # Ensure candidate_documents table exists
        db.execute("""CREATE TABLE IF NOT EXISTS candidate_documents (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            document_type TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            description TEXT,
            uploaded_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        )""")
        db.execute(
            "INSERT INTO candidate_documents (id, candidate_id, document_type, file_name, file_path, file_size, description, uploaded_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (doc_id, candidate_id, document_type, file.filename, file_path, file_size, description, now),
        )

    return {
        "id": doc_id,
        "document_type": document_type,
        "file_name": file.filename,
        "file_size": file_size,
        "uploaded_at": now,
    }


@router.get("/documents")
async def list_documents(request: Request, current_user: dict = Depends(get_current_user)):
    """List all documents uploaded by the candidate."""
    if current_user.get("type") != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access only")

    candidate_id = current_user["sub"]
    with get_db() as db:
        try:
            docs = db.execute(
                "SELECT id, document_type, file_name, file_size, description, uploaded_at FROM candidate_documents WHERE candidate_id=%s ORDER BY uploaded_at DESC",
                (candidate_id,),
            ).fetchall()
            return {"documents": [dict(d) for d in docs]}
        except Exception:
            return {"documents": []}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Delete a document."""
    if current_user.get("type") != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access only")

    candidate_id = current_user["sub"]
    with get_db() as db:
        doc = db.execute(
            "SELECT * FROM candidate_documents WHERE id=%s AND candidate_id=%s",
            (doc_id, candidate_id),
        ).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        doc = dict(doc)
        # Delete from disk
        if os.path.exists(doc["file_path"]):
            os.remove(doc["file_path"])
        db.execute("DELETE FROM candidate_documents WHERE id=%s", (doc_id,))

    return {"deleted": True}


@router.post("/notifications/{notification_id}/confirm")
async def confirm_pre_notification(notification_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Candidate confirms a pre-notification (allowing the verification request to proceed)."""
    if current_user.get("type") != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access only")

    candidate_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        notif = db.execute(
            "SELECT * FROM candidate_pre_notifications WHERE id=%s AND candidate_id=%s",
            (notification_id, candidate_id),
        ).fetchone()
        if not notif:
            raise HTTPException(status_code=404, detail="Notification not found")

        db.execute(
            "UPDATE candidate_pre_notifications SET status='confirmed', candidate_confirmed_at=%s WHERE id=%s",
            (now, notification_id),
        )

    return {"confirmed": True, "notification_id": notification_id}


@router.post("/documents/bulk")
async def bulk_upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    document_types: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    """Bulk upload multiple documents (CV, passport, DBS certificate, training certs).
    document_types is a comma-separated list matching the files order, e.g. 'cv,passport,dbs,training_cert'."""
    if current_user.get("type") != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access only")

    candidate_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()
    type_list = [t.strip() for t in document_types.split(",")] if document_types else []
    results = []

    candidate_dir = os.path.join(UPLOAD_DIR, candidate_id)
    os.makedirs(candidate_dir, exist_ok=True)

    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS candidate_documents (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            document_type TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            description TEXT,
            uploaded_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        )""")

        for idx, file in enumerate(files):
            doc_id = generate_id()
            doc_type = type_list[idx] if idx < len(type_list) else "other"
            safe_name = f"{doc_id}_{file.filename}"
            file_path = os.path.join(candidate_dir, safe_name)

            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

            file_size = os.path.getsize(file_path)
            db.execute(
                "INSERT INTO candidate_documents (id, candidate_id, document_type, file_name, file_path, file_size, description, uploaded_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (doc_id, candidate_id, doc_type, file.filename, file_path, file_size, "", now),
            )
            results.append({
                "id": doc_id,
                "document_type": doc_type,
                "file_name": file.filename,
                "file_size": file_size,
                "uploaded_at": now,
            })

    return {"uploaded": len(results), "documents": results}


# ── SSE: Real-time candidate check status updates ──────────────────────────

@router.get("/status-stream")
async def candidate_status_stream(request: Request, current_user: dict = Depends(get_current_user)):
    """Server-Sent Events (SSE) endpoint for real-time candidate check status updates.
    The client connects and receives JSON events whenever check statuses change."""
    if current_user.get("type") != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access only")

    candidate_id = current_user["sub"]

    async def event_generator():
        """Poll DB for status changes and yield SSE events."""
        last_snapshot: dict = {}
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                current_snapshot = _get_check_snapshot(candidate_id)

                # On first iteration, send full snapshot
                if not last_snapshot:
                    yield f"event: snapshot\ndata: {json.dumps(current_snapshot)}\n\n"
                    last_snapshot = current_snapshot
                else:
                    # Detect changes
                    changes = {}
                    for check_type, status in current_snapshot.items():
                        if last_snapshot.get(check_type) != status:
                            changes[check_type] = {"old": last_snapshot.get(check_type), "new": status}
                    if changes:
                        yield f"event: update\ndata: {json.dumps({'changes': changes, 'snapshot': current_snapshot})}\n\n"
                        last_snapshot = current_snapshot

                # Send heartbeat every cycle to keep connection alive
                yield f"event: heartbeat\ndata: {json.dumps({'ts': datetime.now(timezone.utc).isoformat()})}\n\n"

                await asyncio.sleep(5)  # Poll every 5 seconds
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _get_check_snapshot(candidate_id: str) -> dict:
    """Get current status of all check types for a candidate."""
    snapshot = {}
    with get_db() as db:
        for check_type in ["identity", "dbs", "right_to_work", "professional_registration", "training"]:
            row = db.execute(
                "SELECT status FROM compliance_checks WHERE candidate_id=%s AND check_type=%s ORDER BY created_at DESC LIMIT 1",
                (candidate_id, check_type),
            ).fetchone()
            snapshot[check_type] = dict(row)["status"] if row else "not_started"

        # References
        refs = db.execute(
            "SELECT status FROM references_ WHERE candidate_id=%s",
            (candidate_id,),
        ).fetchall()
        if refs:
            completed = sum(1 for r in refs if dict(r)["status"] == "completed")
            snapshot["references"] = f"{completed}/{len(refs)}_completed"
        else:
            snapshot["references"] = "not_started"

        # Employment
        emps = db.execute(
            "SELECT status FROM employment_verifications WHERE candidate_id=%s",
            (candidate_id,),
        ).fetchall()
        if emps:
            completed = sum(1 for e in emps if dict(e)["status"] == "completed")
            snapshot["employment"] = f"{completed}/{len(emps)}_completed"
        else:
            snapshot["employment"] = "not_started"

    return snapshot


def _format_check(row, label: str) -> dict:
    if not row:
        return {"label": label, "status": "not_started", "detail": "Not yet initiated"}
    r = dict(row)
    return {
        "label": label,
        "status": r["status"],
        "detail": f"Status: {r['status']}",
        "started_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
    }
