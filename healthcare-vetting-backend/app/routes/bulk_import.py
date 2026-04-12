"""Bulk candidate import via CSV for agencies."""
import csv
import io
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_db
from app.utils.auth import get_current_user, generate_id, hash_password

router = APIRouter(prefix="/api/agencies", tags=["Bulk Import"])


class BulkImportRequest(BaseModel):
    csv_data: str  # Raw CSV string
    send_invites: bool = True


@router.post("/bulk-import")
async def bulk_import_candidates(data: BulkImportRequest, current_user: dict = Depends(get_current_user)):
    """Import multiple candidates from CSV data.
    Expected CSV columns: email, first_name, last_name, phone (optional), profession (optional)
    """
    if current_user["type"] not in ("agency", "admin"):
        raise HTTPException(status_code=403, detail="Agencies and admins only")

    agency_id = current_user["sub"] if current_user["type"] == "agency" else None
    now = datetime.now(timezone.utc).isoformat()

    try:
        reader = csv.DictReader(io.StringIO(data.csv_data.strip()))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid CSV format")

    # Normalize headers (strip whitespace, lowercase)
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no headers")

    fieldnames_map = {f.strip().lower().replace(" ", "_"): f for f in reader.fieldnames}

    required = ["email", "first_name", "last_name"]
    for req in required:
        if req not in fieldnames_map:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required column: {req}. Required columns: email, first_name, last_name",
            )

    results = {"imported": 0, "skipped": 0, "errors": [], "candidates": []}
    import secrets

    with get_db() as db:
        for row_num, row in enumerate(reader, start=2):
            # Normalize row keys
            normalized = {}
            for key, orig_key in fieldnames_map.items():
                normalized[key] = (row.get(orig_key) or "").strip()

            email = normalized.get("email", "").lower()
            first_name = normalized.get("first_name", "")
            last_name = normalized.get("last_name", "")
            phone = normalized.get("phone", "")
            profession = normalized.get("profession", "")

            if not email or not first_name or not last_name:
                results["errors"].append({"row": row_num, "error": "Missing required field (email, first_name, or last_name)"})
                results["skipped"] += 1
                continue

            # Check if email format is valid (basic check)
            if "@" not in email or "." not in email:
                results["errors"].append({"row": row_num, "email": email, "error": "Invalid email format"})
                results["skipped"] += 1
                continue

            # Check if candidate already exists
            db.execute("SELECT id FROM candidates WHERE email=%s", (email,))
            existing = db.fetchone()

            if existing:
                candidate_id = dict(existing)["id"]
                # If agency, link if not already linked
                if agency_id:
                    linked = db.execute(
                        "SELECT 1 FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
                        (agency_id, candidate_id),
                    )
                    linked = db.fetchone()
                    if not linked:
                        db.execute(
                            "INSERT INTO agency_candidates (agency_id, candidate_id, assigned_at) VALUES (%s, %s, %s)",
                            (agency_id, candidate_id, now),
                        )
                results["candidates"].append({"email": email, "status": "already_exists", "candidate_id": candidate_id})
                results["skipped"] += 1
                continue

            # Create new candidate with a temporary password
            candidate_id = generate_id()
            temp_password = secrets.token_urlsafe(12)
            db.execute(
                """INSERT INTO candidates (id, email, password_hash, first_name, last_name, phone, profession, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (candidate_id, email, hash_password(temp_password), first_name, last_name,
                 phone or None, profession or None, now, now),
            )

            # Link to agency
            if agency_id:
                db.execute(
                    "INSERT INTO agency_candidates (agency_id, candidate_id, assigned_at) VALUES (%s, %s, %s)",
                    (agency_id, candidate_id, now),
                )

                # Create invite if requested
                if data.send_invites:
                    invite_id = generate_id()
                    invite_code = secrets.token_urlsafe(16)
                    db.execute(
                        """INSERT INTO agency_invites (id, agency_id, candidate_email, invite_code, status, created_at)
                           VALUES (%s, %s, %s, %s, 'pending', %s)""",
                        (invite_id, agency_id, email, invite_code, now),
                    )

            results["imported"] += 1
            results["candidates"].append({
                "email": email,
                "name": f"{first_name} {last_name}",
                "status": "created",
                "candidate_id": candidate_id,
            })

        # Log the bulk import
        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, "bulk_import", agency_id or "admin", "bulk_candidate_import",
             current_user["sub"], f"Imported {results['imported']}, skipped {results['skipped']}", now),
        )

    return results


@router.get("/bulk-import/template")
async def get_csv_template(current_user: dict = Depends(get_current_user)):
    """Return a CSV template string for bulk import."""
    if current_user["type"] not in ("agency", "admin"):
        raise HTTPException(status_code=403, detail="Agencies and admins only")

    return {
        "template": "email,first_name,last_name,phone,profession\njane.doe@example.com,Jane,Doe,07700900001,Nurse\njohn.smith@example.com,John,Smith,07700900002,Healthcare Assistant",
        "columns": [
            {"name": "email", "required": True, "description": "Candidate email address"},
            {"name": "first_name", "required": True, "description": "First name"},
            {"name": "last_name", "required": True, "description": "Last name"},
            {"name": "phone", "required": False, "description": "Phone number"},
            {"name": "profession", "required": False, "description": "Job role / profession"},
        ],
    }
