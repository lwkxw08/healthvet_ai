"""
Lead Generation API Routes
Manage scrape jobs, view leads, trigger scraping from multiple sources.
Also includes professional registration scraping endpoints.
"""
import io
import json
import threading
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from app.database import get_db
from app.utils.auth import get_current_user, generate_id
from app.middleware.rate_limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lead-generation", tags=["Lead Generation"])


# ── Schemas ──────────────────────────────────────────────────────────

class ScrapeJobRequest(BaseModel):
    source: str  # agencycentral, indeed, cqc, nhs_jobs
    industry: Optional[str] = None
    industry_slug: Optional[str] = None
    config: Optional[dict] = None


class LeadUpdateRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class RegistrationScrapeRequest(BaseModel):
    candidate_id: str
    body: str  # NMC, GMC, HCPC, GPhC
    registration_number: str


class BulkDeleteRequest(BaseModel):
    lead_ids: List[str]


# ── Startup recovery ─────────────────────────────────────────────────

def recover_stale_scrape_jobs():
    """Mark orphaned pending/running scrape jobs as failed on server startup.
    Daemon threads die on restart, so any job still pending/running is stale."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_db() as db:
            db.execute(
                "SELECT id, status FROM scrape_jobs WHERE status IN ('pending', 'running')"
            )
            stale = db.fetchall()
            for row in stale:
                db.execute(
                    "UPDATE scrape_jobs SET status='failed', error_message=%s, completed_at=%s WHERE id=%s",
                    ("Server restarted — job did not complete. Please retry.", now, row["id"]),
                )
            if stale:
                logger.info(f"Recovered {len(stale)} stale scrape jobs on startup")
    except Exception as e:
        logger.error(f"Error recovering stale scrape jobs: {e}")


# ── Background scrape runner ─────────────────────────────────────────

def _run_scrape_in_background(job_id: str, source: str, config: dict, industry: str, industry_slug: str):
    """Run a scrape job in a background thread."""
    now = datetime.now(timezone.utc).isoformat()

    # Mark job as running immediately so stuck-in-pending becomes visible.
    try:
        with get_db() as db:
            db.execute(
                "UPDATE scrape_jobs SET status='running', started_at=%s WHERE id=%s",
                (now, job_id),
            )
    except Exception as e:
        logger.exception("Failed to mark scrape_job %s as running: %s", job_id, e)

    # Import the scraper here so any ImportError surfaces as a job error
    # instead of a silent thread death.
    try:
        from app.services.lead_scrapers import run_scrape_job
    except Exception as e:
        import traceback as _tb
        err = f"Scraper import failed: {e}\n{_tb.format_exc()}"
        logger.error(err)
        try:
            with get_db() as db:
                db.execute(
                    "UPDATE scrape_jobs SET status='failed', error_message=%s, completed_at=%s WHERE id=%s",
                    (err[:2000], datetime.now(timezone.utc).isoformat(), job_id),
                )
        except Exception:
            pass
        return

    try:
        leads = run_scrape_job(source, config)
        completed_at = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            # Insert leads, deduplicating by agency_name + source
            inserted = 0
            for lead in leads:
                # Check for duplicates
                db.execute(
                    "SELECT id FROM leads WHERE agency_name=%s AND source=%s",
                    (lead["name"], source),
                )
                existing = db.fetchone()
                if existing:
                    continue

                lead_id = generate_id()
                db.execute(
                    """INSERT INTO leads (id, scrape_job_id, source, industry, industry_slug,
                       agency_name, description, website, email, phone, location, coverage,
                       employment_types, salary_range, source_url, verified, social_links, extra,
                       status, scraped_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'new', %s)""",
                    (
                        lead_id, job_id, source,
                        lead.get("industry", industry),
                        lead.get("industry_slug", industry_slug),
                        lead["name"],
                        lead.get("description", ""),
                        lead.get("website", ""),
                        lead.get("email", ""),
                        lead.get("phone", ""),
                        lead.get("location", ""),
                        lead.get("coverage", ""),
                        lead.get("employment_types", ""),
                        lead.get("salary_range", ""),
                        lead.get("source_url", ""),
                        1 if lead.get("verified") else 0,
                        json.dumps(lead.get("social_links", {})),
                        json.dumps(lead.get("extra", {})),
                        completed_at,
                    ),
                )
                inserted += 1

            db.execute(
                "UPDATE scrape_jobs SET status='completed', completed_at=%s, results_count=%s WHERE id=%s",
                (completed_at, inserted, job_id),
            )

        logger.info(f"Scrape job {job_id} completed: {inserted} new leads from {source}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Scrape job {job_id} failed: {error_msg}")
        with get_db() as db:
            db.execute(
                "UPDATE scrape_jobs SET status='failed', error_message=%s, completed_at=%s WHERE id=%s",
                (error_msg, datetime.now(timezone.utc).isoformat(), job_id),
            )


# ── Scrape Job Endpoints ─────────────────────────────────────────────

@router.post("/scrape")
@limiter.limit("5/minute")
async def trigger_scrape(request: Request, data: ScrapeJobRequest, current_user: dict = Depends(get_current_user)):
    """Trigger a new scrape job. Runs in background."""
    if current_user.get("role") != "admin" and current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    valid_sources = ["agencycentral", "indeed", "cqc", "nhs_jobs"]
    if data.source not in valid_sources:
        raise HTTPException(status_code=400, detail=f"Invalid source. Must be one of: {', '.join(valid_sources)}")

    job_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()
    config = data.config or {}

    # Set defaults based on source
    if data.source == "agencycentral" and data.industry_slug:
        config.setdefault("industry_slug", data.industry_slug)
    elif data.source == "indeed" and data.industry:
        config.setdefault("search_term", f"{data.industry} recruitment agency")
    elif data.source == "cqc":
        config.setdefault("search_type", "care_homes")

    with get_db() as db:
        db.execute(
            """INSERT INTO scrape_jobs (id, source, industry, industry_slug, config, status, created_at)
               VALUES (%s, %s, %s, %s, %s, 'pending', %s)""",
            (job_id, data.source, data.industry or "", data.industry_slug or "", json.dumps(config), now),
        )

    # Run in background thread
    thread = threading.Thread(
        target=_run_scrape_in_background,
        args=(job_id, data.source, config, data.industry or "", data.industry_slug or ""),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "pending", "message": f"Scrape job started for {data.source}"}


@router.post("/jobs/{job_id}/retry")
async def retry_scrape_job(job_id: str, current_user: dict = Depends(get_current_user)):
    """Retry a failed or stale scrape job."""
    if current_user.get("role") != "admin" and current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    with get_db() as db:
        db.execute("SELECT * FROM scrape_jobs WHERE id=%s", (job_id,))
        job = db.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job_dict = dict(job)
        if job_dict["status"] not in ("failed", "pending"):
            raise HTTPException(status_code=400, detail=f"Cannot retry job with status '{job_dict['status']}'")

        # Reset job status
        db.execute(
            "UPDATE scrape_jobs SET status='pending', error_message=NULL, started_at=NULL, completed_at=NULL, results_count=0 WHERE id=%s",
            (job_id,),
        )

    config = json.loads(job_dict.get("config") or "{}")
    thread = threading.Thread(
        target=_run_scrape_in_background,
        args=(job_id, job_dict["source"], config, job_dict.get("industry", ""), job_dict.get("industry_slug", "")),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "pending", "message": "Scrape job retried"}


@router.get("/jobs")
async def list_scrape_jobs(
    source: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    current_user: dict = Depends(get_current_user),
):
    """List scrape jobs with optional filters."""
    if current_user.get("role") != "admin" and current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    query = "SELECT * FROM scrape_jobs WHERE 1=1"
    params = []
    if source:
        query += " AND source=%s"
        params.append(source)
    if status:
        query += " AND status=%s"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with get_db() as db:
        db.execute(query, params)
        rows = db.fetchall()
        return [dict(r) for r in rows]


@router.get("/jobs/{job_id}")
async def get_scrape_job(job_id: str, current_user: dict = Depends(get_current_user)):
    """Get details of a specific scrape job."""
    if current_user.get("role") != "admin" and current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    with get_db() as db:
        db.execute("SELECT * FROM scrape_jobs WHERE id=%s", (job_id,))
        row = db.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scrape job not found")
        return dict(row)


# ── Lead Endpoints ───────────────────────────────────────────────────

@router.get("/leads")
async def list_leads(
    source: Optional[str] = None,
    industry: Optional[str] = None,
    status: Optional[str] = None,
    has_email: Optional[bool] = None,
    has_phone: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """List leads with optional filters."""
    if current_user.get("role") != "admin" and current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    query = "SELECT * FROM leads WHERE 1=1"
    count_query = "SELECT COUNT(*) AS cnt FROM leads WHERE 1=1"
    params = []
    count_params = []

    if source:
        query += " AND source=%s"
        count_query += " AND source=%s"
        params.append(source)
        count_params.append(source)
    if industry:
        query += " AND (industry LIKE %s OR industry_slug LIKE %s)"
        count_query += " AND (industry LIKE %s OR industry_slug LIKE %s)"
        params.extend([f"%{industry}%", f"%{industry}%"])
        count_params.extend([f"%{industry}%", f"%{industry}%"])
    if status:
        query += " AND status=%s"
        count_query += " AND status=%s"
        params.append(status)
        count_params.append(status)
    if has_email:
        query += " AND email IS NOT NULL AND email != ''"
        count_query += " AND email IS NOT NULL AND email != ''"
    if has_phone:
        query += " AND phone IS NOT NULL AND phone != ''"
        count_query += " AND phone IS NOT NULL AND phone != ''"
    if search:
        query += " AND (agency_name LIKE %s OR description LIKE %s OR location LIKE %s)"
        count_query += " AND (agency_name LIKE %s OR description LIKE %s OR location LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        count_params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with get_db() as db:
        db.execute(count_query, count_params)
        count_row = db.fetchone()
        total = count_row["cnt"] if count_row else 0
        db.execute(query, params)
        rows = db.fetchall()
        return {
            "total": total,
            "leads": [dict(r) for r in rows],
            "limit": limit,
            "offset": offset,
        }


@router.get("/leads/stats")
async def get_lead_stats(current_user: dict = Depends(get_current_user)):
    """Get aggregate stats for leads."""
    if current_user.get("role") != "admin" and current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    with get_db() as db:
        db.execute("SELECT COUNT(*) AS cnt FROM leads")
        row = db.fetchone()
        total = row["cnt"] if row else 0
        db.execute("SELECT COUNT(*) AS cnt FROM leads WHERE email IS NOT NULL AND email != ''")
        row = db.fetchone()
        with_email = row["cnt"] if row else 0
        db.execute("SELECT COUNT(*) AS cnt FROM leads WHERE phone IS NOT NULL AND phone != ''")
        row = db.fetchone()
        with_phone = row["cnt"] if row else 0

        by_source = {}
        db.execute("SELECT source, COUNT(*) as cnt FROM leads GROUP BY source")
        for row in db.fetchall():
            by_source[row["source"]] = row["cnt"]

        by_industry = {}
        db.execute("SELECT industry, COUNT(*) as cnt FROM leads GROUP BY industry")
        for row in db.fetchall():
            by_industry[row["industry"]] = row["cnt"]

        by_status = {}
        db.execute("SELECT status, COUNT(*) as cnt FROM leads GROUP BY status")
        for row in db.fetchall():
            by_status[row["status"]] = row["cnt"]

        return {
            "total": total,
            "with_email": with_email,
            "with_phone": with_phone,
            "by_source": by_source,
            "by_industry": by_industry,
            "by_status": by_status,
        }


@router.put("/leads/{lead_id}")
async def update_lead(lead_id: str, data: LeadUpdateRequest, current_user: dict = Depends(get_current_user)):
    """Update a lead's status or notes."""
    if current_user.get("role") != "admin" and current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    with get_db() as db:
        db.execute("SELECT * FROM leads WHERE id=%s", (lead_id,))
        existing = db.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Lead not found")

        updates = []
        params = []
        if data.status is not None:
            updates.append("status=%s")
            params.append(data.status)
        if data.notes is not None:
            updates.append("notes=%s")
            params.append(data.notes)

        if updates:
            params.append(lead_id)
            db.execute(f"UPDATE leads SET {', '.join(updates)} WHERE id=%s", params)

        db.execute("SELECT * FROM leads WHERE id=%s", (lead_id,))
        row = db.fetchone()
        return dict(row)


@router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a lead."""
    if current_user.get("role") != "admin" and current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    with get_db() as db:
        db.execute("SELECT * FROM leads WHERE id=%s", (lead_id,))
        existing = db.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Lead not found")
        db.execute("DELETE FROM leads WHERE id=%s", (lead_id,))
        return {"message": "Lead deleted"}


@router.post("/leads/bulk-delete")
async def bulk_delete_leads(data: BulkDeleteRequest, current_user: dict = Depends(get_current_user)):
    """Delete multiple leads at once."""
    if current_user.get("role") != "admin" and current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    if not data.lead_ids:
        raise HTTPException(status_code=400, detail="No lead IDs provided")

    deleted = 0
    with get_db() as db:
        for lead_id in data.lead_ids:
            db.execute("DELETE FROM leads WHERE id=%s", (lead_id,))
            deleted += 1

    return {"message": f"{deleted} leads deleted", "deleted_count": deleted}


@router.post("/leads/export")
@limiter.limit("10/minute")
async def export_leads(
    request: Request,
    source: Optional[str] = None,
    industry: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Export leads as an Excel (.xlsx) file."""
    if current_user.get("role") != "admin" and current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    query = "SELECT * FROM leads WHERE 1=1"
    params = []
    if source:
        query += " AND source=%s"
        params.append(source)
    if industry:
        query += " AND (industry LIKE %s OR industry_slug LIKE %s)"
        params.extend([f"%{industry}%", f"%{industry}%"])
    if status:
        query += " AND status=%s"
        params.append(status)
    query += " ORDER BY created_at DESC"

    with get_db() as db:
        db.execute(query, params)
        rows = db.fetchall()
        leads = [dict(r) for r in rows]

    # Build Excel workbook
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"

    # Column definitions (header -> dict key)
    columns = [
        ("Agency Name", "agency_name"),
        ("Website", "website"),
        ("Email", "email"),
        ("Phone", "phone"),
        ("Industry", "industry"),
        ("Source", "source"),
        ("Location", "location"),
        ("Coverage", "coverage"),
        ("Employment Types", "employment_types"),
        ("Salary Range", "salary_range"),
        ("Description", "description"),
        ("Source URL", "source_url"),
        ("Status", "status"),
        ("Verified", "verified"),
        ("Listed Since", "listed_since"),
        ("Scraped At", "created_at"),
    ]

    # Header row styling
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    for col_idx, (header, _) in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    # Data rows
    for row_idx, lead in enumerate(leads, start=2):
        for col_idx, (_, key) in enumerate(columns, start=1):
            value = lead.get(key, "")
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            if value is None:
                value = ""
            # Convert boolean "verified" to readable text
            if key == "verified":
                value = "Yes" if value in (True, 1, "1", "true") else "No"
            cell = ws.cell(row=row_idx, column=col_idx, value=str(value))
            cell.border = thin_border

    # Auto-size columns (approximate)
    for col_idx, (header, _) in enumerate(columns, start=1):
        max_len = len(header)
        for row_idx in range(2, min(len(leads) + 2, 52)):  # sample first 50 rows
            cell_val = str(ws.cell(row=row_idx, column=col_idx).value or "")
            max_len = max(max_len, min(len(cell_val), 50))
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = max_len + 3

    # Freeze header row
    ws.freeze_panes = "A2"

    # Write to buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"leads_export_{timestamp}.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Professional Registration Scraping ────────────────────────────────

@router.post("/registration-scrape")
@limiter.limit("10/minute")
async def scrape_professional_registration(request: Request, data: RegistrationScrapeRequest, current_user: dict = Depends(get_current_user)):
    """
    Scrape a professional register (NMC, GMC, HCPC, GPhC) for a candidate's registration.
    Returns real-time scraped data from the public register.
    """
    from app.services.registration_scrapers import scrape_registration

    result = scrape_registration(data.body, data.registration_number)

    # Store the scrape result
    scrape_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute(
            """INSERT INTO registration_scrape_results
               (id, candidate_id, body, registration_number, scrape_source,
                registrant_name, registration_status, expiry_date,
                sanctions, conditions, raw_data, scraped_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                scrape_id, data.candidate_id, data.body, data.registration_number,
                result.get("scrape_source", ""),
                result.get("registrant_name", ""),
                result.get("registration_status", "unknown"),
                result.get("expiry_date", ""),
                json.dumps(result.get("sanctions", [])),
                json.dumps(result.get("conditions", [])),
                json.dumps(result.get("raw_data", {})),
                now,
            ),
        )

        # If successful, also update the registration_checks table
        if result.get("success") and result.get("registration_status") != "unknown":
            # Find the latest registration check for this candidate
            db.execute(
                "SELECT id FROM registration_checks WHERE candidate_id=%s AND body=%s ORDER BY last_checked DESC LIMIT 1",
                (data.candidate_id, data.body),
            )
            check = db.fetchone()
            if check:
                db.execute(
                    "UPDATE registration_scrape_results SET registration_check_id=%s WHERE id=%s",
                    (check["id"], scrape_id),
                )

    return {
        "scrape_id": scrape_id,
        "success": result.get("success", False),
        "body": data.body,
        "registration_number": data.registration_number,
        "registrant_name": result.get("registrant_name", ""),
        "registration_status": result.get("registration_status", "unknown"),
        "expiry_date": result.get("expiry_date", ""),
        "sanctions": result.get("sanctions", []),
        "conditions": result.get("conditions", []),
        "error": result.get("error"),
    }


@router.get("/registration-scrape/{candidate_id}")
async def get_registration_scrapes(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Get all registration scrape results for a candidate."""
    with get_db() as db:
        db.execute(
            "SELECT * FROM registration_scrape_results WHERE candidate_id=%s ORDER BY scraped_at DESC",
            (candidate_id,),
        )
        rows = db.fetchall()
        return [dict(r) for r in rows]


# ── Available Sources & Industries ────────────────────────────────────

@router.get("/sources")
async def get_available_sources(current_user: dict = Depends(get_current_user)):
    """Get available scrape sources and their supported industries."""
    if current_user.get("role") != "admin" and current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    try:
        from app.services.lead_scrapers import AGENCY_CENTRAL_INDUSTRIES
    except Exception as e:
        import traceback as _tb
        logger.error("Failed to import lead_scrapers: %s\n%s", e, _tb.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Scraper module failed to import: {type(e).__name__}: {e}",
        )

    return {
        "sources": [
            {
                "id": "agencycentral",
                "name": "AgencyCentral",
                "description": "UK recruitment agency directory - two-stage scraping with website follow-through",
                "supports_industries": True,
                "industries": [
                    {"slug": slug, "name": name}
                    for slug, name in AGENCY_CENTRAL_INDUSTRIES.items()
                ],
                "healthcare_only": False,
            },
            {
                "id": "indeed",
                "name": "Indeed",
                "description": "Job board scraping - extracts recruitment agencies from job listings",
                "supports_industries": True,
                "industries": [
                    {"slug": "healthcare", "name": "Healthcare"},
                    {"slug": "education", "name": "Education"},
                    {"slug": "construction", "name": "Construction"},
                    {"slug": "social_care", "name": "Social Care"},
                    {"slug": "finance", "name": "Finance"},
                    {"slug": "logistics", "name": "Logistics"},
                    {"slug": "retail_hospitality", "name": "Retail & Hospitality"},
                    {"slug": "it", "name": "IT & Technology"},
                    {"slug": "engineering", "name": "Engineering"},
                ],
                "healthcare_only": False,
            },
            {
                "id": "cqc",
                "name": "CQC API",
                "description": "Care Quality Commission public API - healthcare providers and care homes",
                "supports_industries": False,
                "industries": [{"slug": "health", "name": "Health Care"}],
                "healthcare_only": True,
            },
            {
                "id": "nhs_jobs",
                "name": "NHS Jobs",
                "description": "NHS job board - identifies NHS employers and healthcare agencies",
                "supports_industries": False,
                "industries": [{"slug": "health", "name": "Health Care (NHS)"}],
                "healthcare_only": True,
            },
        ],
        "registration_bodies": [
            {"id": "NMC", "name": "Nursing and Midwifery Council", "professions": ["Nurse", "Midwife", "Nursing Associate"]},
            {"id": "GMC", "name": "General Medical Council", "professions": ["Doctor", "Physician", "Surgeon", "GP"]},
            {"id": "HCPC", "name": "Health and Care Professions Council", "professions": ["Physiotherapist", "Occupational Therapist", "Paramedic", "Speech Therapist", "Dietitian", "Radiographer"]},
            {"id": "GPhC", "name": "General Pharmaceutical Council", "professions": ["Pharmacist", "Pharmacy Technician"]},
        ],
    }
