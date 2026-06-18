"""
QR Code Management & Expo Lead Generation Routes

Create QR codes for expos, track scans, capture leads via landing page contact forms,
and view analytics in the admin dashboard.
"""
import io
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.utils.auth import get_current_admin

router = APIRouter(prefix="/api/qr", tags=["QR Codes"])


# ── Pydantic models ────────────────────────────────────────────────
class QRCodeCreate(BaseModel):
    name: str
    campaign: Optional[str] = None
    event_name: Optional[str] = None
    redirect_url: Optional[str] = None


class ExpoLeadSubmit(BaseModel):
    qr_code: Optional[str] = None
    name: str
    email: str
    company: str
    phone: Optional[str] = None
    industry: Optional[str] = None
    team_size: Optional[str] = None
    message: Optional[str] = None


# ── Public endpoints (no auth) ─────────────────────────────────────

@router.post("/scan/{code}")
async def track_qr_scan(code: str, request: Request):
    """Track a QR code scan (called when landing page loads)."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")
    referer = request.headers.get("referer", "")

    with get_db() as db:
        db.execute("SELECT id FROM qr_codes WHERE code=%s", (code,))
        qr = db.fetchone()
        if not qr:
            raise HTTPException(status_code=404, detail="QR code not found")

        scan_id = str(uuid.uuid4())
        db.execute(
            """INSERT INTO qr_scans (id, qr_code_id, ip_address, user_agent, referer, scanned_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (scan_id, qr["id"], ip, ua[:500], referer[:500],
             datetime.now(timezone.utc).isoformat()),
        )
        db.execute(
            "UPDATE qr_codes SET scan_count = scan_count + 1 WHERE id=%s",
            (qr["id"],),
        )
    return {"status": "tracked", "scan_id": scan_id}


@router.post("/expo-lead")
async def submit_expo_lead(lead: ExpoLeadSubmit):
    """Submit a contact form from the expo landing page."""
    qr_code_id = None
    if lead.qr_code:
        with get_db() as db:
            db.execute("SELECT id FROM qr_codes WHERE code=%s", (lead.qr_code,))
            qr = db.fetchone()
            if qr:
                qr_code_id = qr["id"]

    lead_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute(
            """INSERT INTO expo_leads
               (id, qr_code_id, name, email, company, phone, industry, team_size, message, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (lead_id, qr_code_id, lead.name, lead.email, lead.company,
             lead.phone, lead.industry, lead.team_size, lead.message, now),
        )

        if qr_code_id:
            db.execute(
                "UPDATE qr_codes SET lead_count = lead_count + 1 WHERE id=%s",
                (qr_code_id,),
            )

    return {"status": "submitted", "lead_id": lead_id}


# ── Admin endpoints ────────────────────────────────────────────────

@router.get("/codes")
async def list_qr_codes(user=Depends(get_current_admin)):
    """List all QR codes with scan/lead counts."""
    with get_db() as db:
        db.execute(
            """SELECT * FROM qr_codes ORDER BY created_at DESC"""
        )
        rows = db.fetchall()
    return [dict(r) for r in rows]


@router.post("/codes")
async def create_qr_code(data: QRCodeCreate, user=Depends(get_current_admin)):
    """Create a new QR code for an expo/campaign."""
    code = str(uuid.uuid4())[:8]
    qr_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute(
            """INSERT INTO qr_codes (id, code, name, campaign, event_name, redirect_url, scan_count, lead_count, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, 0, 0, %s)""",
            (qr_id, code, data.name, data.campaign, data.event_name, data.redirect_url, now),
        )
    return {"id": qr_id, "code": code, "name": data.name}


@router.delete("/codes/{qr_id}")
async def delete_qr_code(qr_id: str, user=Depends(get_current_admin)):
    """Delete a QR code and all related scans/leads."""
    with get_db() as db:
        db.execute("DELETE FROM qr_scans WHERE qr_code_id=%s", (qr_id,))
        db.execute("DELETE FROM expo_leads WHERE qr_code_id=%s", (qr_id,))
        db.execute("DELETE FROM qr_codes WHERE id=%s", (qr_id,))
    return {"status": "deleted"}


@router.get("/codes/{code}/qr-image")
async def get_qr_image(code: str):
    """Generate a scannable QR code PNG image for the given code."""
    import qrcode

    marketing_url = "https://viperai.io"
    landing_url = f"{marketing_url}/expo?qr={code}"

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(landing_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#17365D", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png",
                             headers={"Content-Disposition": f"inline; filename=qr-{code}.png"})


@router.get("/analytics")
async def get_qr_analytics(user=Depends(get_current_admin)):
    """Get aggregated QR scan analytics."""
    with get_db() as db:
        db.execute("SELECT COUNT(*) as total_codes FROM qr_codes")
        total_codes = db.fetchone()["total_codes"]

        db.execute("SELECT COALESCE(SUM(scan_count), 0) as total_scans FROM qr_codes")
        total_scans = db.fetchone()["total_scans"]

        db.execute("SELECT COALESCE(SUM(lead_count), 0) as total_leads FROM qr_codes")
        total_leads = db.fetchone()["total_leads"]

        # Per-code breakdown
        db.execute(
            """SELECT qc.id, qc.code, qc.name, qc.campaign, qc.event_name,
                      qc.scan_count, qc.lead_count, qc.created_at
               FROM qr_codes qc ORDER BY qc.scan_count DESC"""
        )
        codes = [dict(r) for r in db.fetchall()]

        # Recent scans (last 50)
        db.execute(
            """SELECT qs.scanned_at, qs.ip_address, qs.user_agent, qc.name as qr_name, qc.code
               FROM qr_scans qs
               JOIN qr_codes qc ON qs.qr_code_id = qc.id
               ORDER BY qs.scanned_at DESC LIMIT 50"""
        )
        recent_scans = [dict(r) for r in db.fetchall()]

        # Recent leads (last 50)
        db.execute(
            """SELECT el.*, qc.name as qr_name, qc.code as qr_code_value
               FROM expo_leads el
               LEFT JOIN qr_codes qc ON el.qr_code_id = qc.id
               ORDER BY el.created_at DESC LIMIT 50"""
        )
        recent_leads = [dict(r) for r in db.fetchall()]

        # Daily scan counts (last 30 days)
        db.execute(
            """SELECT LEFT(scanned_at, 10) as scan_date, COUNT(*) as count
               FROM qr_scans
               WHERE scanned_at >= to_char(NOW() - INTERVAL '30 days', 'YYYY-MM-DD')
               GROUP BY LEFT(scanned_at, 10)
               ORDER BY scan_date DESC"""
        )
        daily_scans = [dict(r) for r in db.fetchall()]

    conversion_rate = (total_leads / total_scans * 100) if total_scans > 0 else 0

    return {
        "total_codes": total_codes,
        "total_scans": total_scans,
        "total_leads": total_leads,
        "conversion_rate": round(conversion_rate, 1),
        "codes": codes,
        "recent_scans": recent_scans,
        "recent_leads": recent_leads,
        "daily_scans": daily_scans,
    }
