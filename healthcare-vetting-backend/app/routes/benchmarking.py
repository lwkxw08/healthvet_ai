"""Admin Benchmarking Dashboard — compare agencies on compliance rate, vetting times."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from app.database import get_db
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/admin/benchmarking", tags=["Benchmarking"])


def require_admin(current_user: dict):
    if current_user["type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")


@router.get("/agencies")
async def get_agency_benchmarks(current_user: dict = Depends(get_current_user)):
    """Compare all agencies on compliance rate, vetting times, candidate volume, and revenue."""
    require_admin(current_user)

    with get_db() as db:
        db.execute("SELECT * FROM agencies")
        agencies = [dict(r) for r in db.fetchall()]
        benchmarks = []

        for agency in agencies:
            aid = agency["id"]

            # Get candidates
            db.execute(
                """SELECT c.id, c.created_at, c.compliance_status,
                          ac.employment_status
                   FROM candidates c
                   JOIN agency_candidates ac ON c.id = ac.candidate_id
                   WHERE ac.agency_id=%s""",
                (aid,),
            )
            candidates = db.fetchall()
            cands = [dict(r) for r in candidates]

            total = len(cands)
            compliant = sum(1 for c in cands if c["compliance_status"] == "compliant")
            hired = sum(1 for c in cands if c.get("employment_status") == "hired")
            compliance_rate = round((compliant / total * 100) if total > 0 else 0, 1)

            # Average vetting time (from candidate creation to compliance)
            avg_vetting_hours = 0.0
            vetting_count = 0
            for c in cands:
                db.execute(
                    "SELECT last_evaluated FROM compliance_records WHERE candidate_id=%s AND overall_status='compliant' ORDER BY last_evaluated DESC LIMIT 1",
                    (c["id"],),
                )
                comp_row = db.fetchone()
                if comp_row and c.get("created_at"):
                    try:
                        created = datetime.fromisoformat(c["created_at"])
                        evaluated = datetime.fromisoformat(dict(comp_row)["last_evaluated"])
                        hours = (evaluated - created).total_seconds() / 3600
                        if hours > 0:
                            avg_vetting_hours += hours
                            vetting_count += 1
                    except (ValueError, TypeError):
                        pass
            avg_vetting_hours = round(avg_vetting_hours / vetting_count, 1) if vetting_count > 0 else 0

            # Revenue and cost
            db.execute(
                "SELECT COALESCE(SUM(COALESCE(adjusted_amount, sell_amount)),0) as rev, COALESCE(SUM(cost_amount),0) as cost, COUNT(*) as cnt FROM invoices WHERE agency_id=%s",
                (aid,),
            )
            inv_row = db.fetchone()
            inv = dict(inv_row) if inv_row else {"rev": 0, "cost": 0, "cnt": 0}

            # Subscription info
            db.execute(
                "SELECT tier, status FROM agency_subscriptions WHERE agency_id=%s AND status='active' ORDER BY created_at DESC LIMIT 1",
                (aid,),
            )
            sub_row = db.fetchone()
            sub = dict(sub_row) if sub_row else None

            # CQC ready count
            db.execute(
                """SELECT COUNT(*) as cnt FROM compliance_records cr
                   JOIN agency_candidates ac ON cr.candidate_id = ac.candidate_id
                   WHERE ac.agency_id=%s AND cr.cqc_ready=1""",
                (aid,),
            )
            cqc_ready = db.fetchone()
            cqc_count = dict(cqc_ready)["cnt"] if cqc_ready else 0

            # Shift readiness breakdown
            ready = 0
            conditional = 0
            not_ready = 0
            for c in cands:
                db.execute(
                    "SELECT score, cqc_ready, identity_verified, right_to_work_valid, dbs_valid, registration_active, references_verified, training_compliant FROM compliance_records WHERE candidate_id=%s ORDER BY last_evaluated DESC LIMIT 1",
                    (c["id"],),
                )
                cr = db.fetchone()
                if cr:
                    crd = dict(cr)
                    required_keys = ["identity_verified", "right_to_work_valid", "dbs_valid",
                                     "registration_active", "references_verified", "training_compliant"]
                    blockers = sum(1 for k in required_keys if not crd.get(k))
                    if blockers == 0 and crd.get("cqc_ready"):
                        ready += 1
                    elif blockers <= 2 and (crd.get("score") or 0) >= 70:
                        conditional += 1
                    else:
                        not_ready += 1
                else:
                    not_ready += 1

            benchmarks.append({
                "agency_id": aid,
                "agency_name": agency["name"],
                "email": agency["email"],
                "plan": agency.get("plan", "standard"),
                "subscription_tier": sub["tier"] if sub else "none",
                "total_candidates": total,
                "compliant_candidates": compliant,
                "hired_candidates": hired,
                "cqc_ready_candidates": cqc_count,
                "compliance_rate": compliance_rate,
                "avg_vetting_hours": avg_vetting_hours,
                "revenue": round(inv["rev"], 2),
                "cost": round(inv["cost"], 2),
                "margin": round(inv["rev"] - inv["cost"], 2),
                "invoice_count": inv["cnt"],
                "shift_readiness": {
                    "ready": ready,
                    "conditional": conditional,
                    "not_ready": not_ready,
                },
            })

        # Sort by compliance rate descending
        benchmarks.sort(key=lambda b: b["compliance_rate"], reverse=True)

        # Calculate platform averages
        total_agencies = len(benchmarks)
        avg_compliance = round(sum(b["compliance_rate"] for b in benchmarks) / total_agencies, 1) if total_agencies > 0 else 0
        avg_vetting = round(sum(b["avg_vetting_hours"] for b in benchmarks) / total_agencies, 1) if total_agencies > 0 else 0
        total_revenue = round(sum(b["revenue"] for b in benchmarks), 2)
        total_candidates = sum(b["total_candidates"] for b in benchmarks)

        return {
            "agencies": benchmarks,
            "platform_averages": {
                "avg_compliance_rate": avg_compliance,
                "avg_vetting_hours": avg_vetting,
                "total_revenue": total_revenue,
                "total_candidates": total_candidates,
                "total_agencies": total_agencies,
            },
        }


@router.get("/trends")
async def get_benchmarking_trends(current_user: dict = Depends(get_current_user)):
    """Get monthly trends for compliance and vetting across all agencies."""
    require_admin(current_user)

    with get_db() as db:
        # Monthly candidate registrations
        db.execute(
            """SELECT TO_CHAR(created_at::timestamp, 'YYYY-MM') as month, COUNT(*) AS cnt
               FROM candidates
               GROUP BY month ORDER BY month"""
        )
        monthly_registrations = db.fetchall()

        # Monthly invoice revenue
        db.execute(
            """SELECT TO_CHAR(created_at::timestamp, 'YYYY-MM') as month,
                      COALESCE(SUM(COALESCE(adjusted_amount, sell_amount)), 0) as revenue,
                      COALESCE(SUM(cost_amount), 0) as cost,
                      COUNT(*) AS cnt
               FROM invoices
               GROUP BY month ORDER BY month"""
        )
        monthly_revenue = db.fetchone()
        monthly_revenue = db.fetchall()

        # Monthly compliance completions
        db.execute(
            """SELECT TO_CHAR(last_evaluated::timestamp, 'YYYY-MM') as month,
                      COUNT(*) AS cnt,
                      SUM(CASE WHEN overall_status='compliant' THEN 1 ELSE 0 END) as compliant,
                      SUM(CASE WHEN cqc_ready=1 THEN 1 ELSE 0 END) as cqc_ready
               FROM compliance_records
               GROUP BY month ORDER BY month"""
        )
        monthly_compliance = db.fetchone()
        monthly_compliance = db.fetchall()

        return {
            "monthly_registrations": [dict(r) for r in monthly_registrations],
            "monthly_revenue": [dict(r) for r in monthly_revenue],
            "monthly_compliance": [dict(r) for r in monthly_compliance],
        }
