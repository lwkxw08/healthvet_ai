"""Shift Readiness Indicator — single 'Ready to Work' badge combining all compliance checks."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from app.database import get_db
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/shift-readiness", tags=["Shift Readiness"])


@router.get("/{candidate_id}")
async def get_shift_readiness(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Get a single 'Ready to Work' indicator combining all compliance checks.
    Returns: ready (green), conditional (amber), not_ready (red) with detailed breakdown.
    """
    with get_db() as db:
        # Get compliance record
        comp = db.execute(
            "SELECT * FROM compliance_records WHERE candidate_id=%s ORDER BY last_evaluated DESC LIMIT 1",
            (candidate_id,),
        )
        comp = db.fetchone()

        if not comp:
            return {
                "candidate_id": candidate_id,
                "status": "not_ready",
                "badge": "red",
                "label": "Not Ready to Work",
                "score": 0,
                "cqc_ready": False,
                "blockers": ["No compliance evaluation found — run compliance check first"],
                "warnings": [],
                "checks": {},
            }

        c = dict(comp)
        checks = {
            "identity_verified": bool(c.get("identity_verified")),
            "right_to_work_valid": bool(c.get("right_to_work_valid")),
            "dbs_valid": bool(c.get("dbs_valid")),
            "registration_active": bool(c.get("registration_active")),
            "references_verified": bool(c.get("references_verified")),
            "cv_validated": bool(c.get("cv_validated")),
            "employment_verified": bool(c.get("employment_verified")),
            "training_compliant": bool(c.get("training_compliant")),
        }

        # Required checks for shift readiness
        required_checks = {
            "identity_verified": "Identity Verification",
            "right_to_work_valid": "Right to Work",
            "dbs_valid": "Enhanced DBS",
            "registration_active": "Professional Registration",
            "references_verified": "References (2+)",
            "training_compliant": "Mandatory Training",
        }

        # Optional checks (nice to have)
        optional_checks = {
            "cv_validated": "CV Validation",
            "employment_verified": "Employment Verification",
        }

        blockers = []
        warnings = []

        for key, label in required_checks.items():
            if not checks.get(key):
                blockers.append(f"{label} not completed")

        for key, label in optional_checks.items():
            if not checks.get(key):
                warnings.append(f"{label} not completed")

        # Check for expiry warnings
        now = datetime.now(timezone.utc)

        # Check DBS expiry
        dbs = db.execute(
            "SELECT next_renewal FROM dbs_checks WHERE candidate_id=%s ORDER BY submitted_at DESC LIMIT 1",
            (candidate_id,),
        )
        dbs = db.fetchone()
        if dbs and dict(dbs).get("next_renewal"):
            try:
                renewal = datetime.fromisoformat(dict(dbs)["next_renewal"])
                if renewal.tzinfo is None:
                    renewal = renewal.replace(tzinfo=timezone.utc)
                days_until = (renewal - now).days
                if days_until < 0:
                    blockers.append(f"DBS expired {abs(days_until)} days ago")
                elif days_until < 30:
                    warnings.append(f"DBS renewal due in {days_until} days")
            except (ValueError, TypeError):
                pass

        # Check visa expiry
        rtw = db.execute(
            "SELECT visa_expiry FROM right_to_work_checks WHERE candidate_id=%s ORDER BY checked_at DESC LIMIT 1",
            (candidate_id,),
        )
        rtw = db.fetchone()
        if rtw and dict(rtw).get("visa_expiry"):
            try:
                expiry = datetime.fromisoformat(dict(rtw)["visa_expiry"])
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                days_until = (expiry - now).days
                if days_until < 0:
                    blockers.append(f"Visa expired {abs(days_until)} days ago")
                elif days_until < 30:
                    warnings.append(f"Visa expiring in {days_until} days")
            except (ValueError, TypeError):
                pass

        # Check training certificate expiries
        training_certs = db.execute(
            "SELECT certificate_name, expiry_date, status FROM training_certificates WHERE candidate_id=%s",
            (candidate_id,),
        )
        training_certs = db.fetchall()
        for cert in training_certs:
            cd = dict(cert)
            if cd.get("status") == "expired":
                warnings.append(f"Training: {cd['certificate_name']} expired")
            elif cd.get("expiry_date"):
                try:
                    exp = datetime.fromisoformat(cd["expiry_date"])
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    days_until = (exp - now).days
                    if days_until < 30 and days_until >= 0:
                        warnings.append(f"Training: {cd['certificate_name']} expiring in {days_until} days")
                except (ValueError, TypeError):
                    pass

        # Determine status
        score = c.get("score", 0)
        cqc_ready = bool(c.get("cqc_ready"))

        if len(blockers) == 0 and cqc_ready:
            status = "ready"
            badge = "green"
            label = "Ready to Work"
        elif len(blockers) <= 2 and score >= 70:
            status = "conditional"
            badge = "amber"
            label = "Conditional — Action Required"
        else:
            status = "not_ready"
            badge = "red"
            label = "Not Ready to Work"

        # Get candidate employment status from agency
        emp_status_row = db.execute(
            "SELECT employment_status FROM agency_candidates WHERE candidate_id=%s LIMIT 1",
            (candidate_id,),
        )
        emp_status_row = db.fetchone()
        employment_status = dict(emp_status_row)["employment_status"] if emp_status_row else "unknown"

        return {
            "candidate_id": candidate_id,
            "status": status,
            "badge": badge,
            "label": label,
            "score": score,
            "cqc_ready": cqc_ready,
            "employment_status": employment_status,
            "blockers": blockers,
            "warnings": warnings,
            "checks": checks,
            "last_evaluated": c.get("last_evaluated"),
        }


@router.get("/agency/overview")
async def get_agency_readiness_overview(current_user: dict = Depends(get_current_user)):
    """Get shift readiness overview for all candidates in the agency."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]

    with get_db() as db:
        # Get all agency candidates
        candidates = db.execute(
            """SELECT c.id, c.first_name, c.last_name, c.email, c.profession,
                      ac.employment_status,
                      cr.score, cr.cqc_ready, cr.overall_status,
                      cr.identity_verified, cr.right_to_work_valid, cr.dbs_valid,
                      cr.registration_active, cr.references_verified, cr.cv_validated,
                      cr.employment_verified, cr.training_compliant
               FROM candidates c
               JOIN agency_candidates ac ON c.id = ac.candidate_id
               LEFT JOIN compliance_records cr ON c.id = cr.candidate_id
               WHERE ac.agency_id=%s
               ORDER BY c.last_name, c.first_name""",
            (agency_id,),
        )
        candidates = db.fetchall()

        ready = 0
        conditional = 0
        not_ready = 0
        results = []

        for cand in candidates:
            cd = dict(cand)
            required_keys = ["identity_verified", "right_to_work_valid", "dbs_valid",
                             "registration_active", "references_verified", "training_compliant"]
            blockers_count = sum(1 for k in required_keys if not cd.get(k))
            score = cd.get("score") or 0
            cqc = bool(cd.get("cqc_ready"))

            if blockers_count == 0 and cqc:
                status = "ready"
                badge = "green"
                ready += 1
            elif blockers_count <= 2 and score >= 70:
                status = "conditional"
                badge = "amber"
                conditional += 1
            else:
                status = "not_ready"
                badge = "red"
                not_ready += 1

            results.append({
                "candidate_id": cd["id"],
                "name": f"{cd['first_name']} {cd['last_name']}",
                "email": cd["email"],
                "profession": cd.get("profession"),
                "employment_status": cd.get("employment_status", "vetting"),
                "readiness_status": status,
                "badge": badge,
                "score": score,
                "cqc_ready": cqc,
            })

        return {
            "total": len(results),
            "ready": ready,
            "conditional": conditional,
            "not_ready": not_ready,
            "candidates": results,
        }
