"""
Compliance Engine - The Core
Rule-based compliance scoring with CQC-ready audit logs.
"""
import json
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id


class ComplianceEngine:
    """Rule-based compliance evaluation engine."""

    RULES = {
        "identity_verified": {"weight": 20, "required": True},
        "right_to_work_valid": {"weight": 20, "required": True},
        "dbs_valid": {"weight": 25, "required": True},
        "registration_active": {"weight": 15, "required": True},
        "references_verified": {"weight": 15, "required": True, "min_count": 2},
        "cv_validated": {"weight": 5, "required": False},
    }

    @staticmethod
    def evaluate_candidate(candidate_id: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            # Gather all check results
            identity = db.execute(
                "SELECT * FROM identity_checks WHERE candidate_id=? ORDER BY started_at DESC LIMIT 1",
                (candidate_id,),
            ).fetchone()

            rtw = db.execute(
                "SELECT * FROM right_to_work_checks WHERE candidate_id=? ORDER BY checked_at DESC LIMIT 1",
                (candidate_id,),
            ).fetchone()

            dbs = db.execute(
                "SELECT * FROM dbs_checks WHERE candidate_id=? ORDER BY submitted_at DESC LIMIT 1",
                (candidate_id,),
            ).fetchone()

            reg = db.execute(
                "SELECT * FROM registration_checks WHERE candidate_id=? ORDER BY last_checked DESC LIMIT 1",
                (candidate_id,),
            ).fetchone()

            refs = db.execute(
                "SELECT * FROM references_ WHERE candidate_id=? AND status='completed'",
                (candidate_id,),
            ).fetchall()

            cv = db.execute(
                "SELECT * FROM cv_analyses WHERE candidate_id=? ORDER BY analysed_at DESC LIMIT 1",
                (candidate_id,),
            ).fetchone()

            # Evaluate each rule
            checks = {}
            audit_entries = []
            flags = []

            # Identity verification
            id_pass = identity and dict(identity).get("result") == "clear"
            checks["identity_verified"] = id_pass
            audit_entries.append({
                "check": "identity_verification",
                "result": "passed" if id_pass else "failed",
                "timestamp": now,
                "details": dict(identity)["result"] if identity else "not_submitted",
            })
            if not id_pass:
                flags.append("Identity verification incomplete or failed")

            # Right to Work
            rtw_pass = rtw and dict(rtw).get("verified") == 1
            checks["right_to_work_valid"] = rtw_pass
            audit_entries.append({
                "check": "right_to_work",
                "result": "passed" if rtw_pass else "failed",
                "timestamp": now,
                "details": dict(rtw)["result"] if rtw else "not_submitted",
            })
            if not rtw_pass:
                flags.append("Right to Work verification incomplete or invalid")

            # DBS Check
            dbs_pass = dbs and dict(dbs).get("result") == "clear"
            checks["dbs_valid"] = dbs_pass
            audit_entries.append({
                "check": "dbs_check",
                "result": "passed" if dbs_pass else "failed",
                "timestamp": now,
                "details": dict(dbs)["result"] if dbs else "not_submitted",
            })
            if not dbs_pass:
                dbs_result = dict(dbs)["result"] if dbs else "not_submitted"
                if dbs_result == "has_information":
                    flags.append("DBS check returned information - requires review")
                elif dbs_result == "flagged":
                    flags.append("DBS check flagged - DO NOT CLEAR")
                else:
                    flags.append("DBS check incomplete")

            # Registration
            reg_pass = reg and dict(reg).get("is_active") == 1
            checks["registration_active"] = reg_pass
            reg_result = dict(reg)["result"] if reg else "not_submitted"
            audit_entries.append({
                "check": "registration",
                "result": "passed" if reg_pass else "failed",
                "timestamp": now,
                "details": reg_result,
            })
            if not reg_pass:
                flags.append("Professional registration not active or not verified")

            # References (need at least 2 completed)
            completed_refs = len(refs)
            refs_pass = completed_refs >= 2
            checks["references_verified"] = refs_pass
            audit_entries.append({
                "check": "references",
                "result": "passed" if refs_pass else "failed",
                "timestamp": now,
                "details": f"{completed_refs} of 2 required references completed",
            })
            if not refs_pass:
                flags.append(f"References: {completed_refs}/2 completed")

            # CV Validation
            cv_pass = cv and dict(cv).get("fraud_risk_score", 1.0) < 0.5
            checks["cv_validated"] = cv_pass
            audit_entries.append({
                "check": "cv_validation",
                "result": "passed" if cv_pass else "failed",
                "timestamp": now,
                "details": f"Fraud risk: {dict(cv)['fraud_risk_score']}" if cv else "not_submitted",
            })
            if not cv_pass and cv:
                flags.append(f"CV fraud risk score: {dict(cv)['fraud_risk_score']}")

            # Calculate compliance score
            score = 0.0
            for check_name, passed in checks.items():
                if passed:
                    score += ComplianceEngine.RULES[check_name]["weight"]

            # Determine overall status
            required_checks = [k for k, v in ComplianceEngine.RULES.items() if v["required"]]
            all_required_pass = all(checks.get(c, False) for c in required_checks)

            if all_required_pass and score >= 95:
                overall_status = "compliant"
            elif score >= 60:
                overall_status = "pending_review"
            elif any(checks.values()):
                overall_status = "in_progress"
            else:
                overall_status = "incomplete"

            cqc_ready = overall_status == "compliant"

            # Upsert compliance record
            existing = db.execute(
                "SELECT id FROM compliance_records WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()

            if existing:
                db.execute(
                    """UPDATE compliance_records SET
                       overall_status=?, score=?, identity_verified=?,
                       right_to_work_valid=?, dbs_valid=?, registration_active=?,
                       references_verified=?, cv_validated=?, flags=?,
                       audit_log=?, last_evaluated=?, cqc_ready=?
                       WHERE candidate_id=?""",
                    (
                        overall_status, score,
                        1 if checks["identity_verified"] else 0,
                        1 if checks["right_to_work_valid"] else 0,
                        1 if checks["dbs_valid"] else 0,
                        1 if checks["registration_active"] else 0,
                        1 if checks["references_verified"] else 0,
                        1 if checks["cv_validated"] else 0,
                        json.dumps(flags),
                        json.dumps(audit_entries),
                        now,
                        1 if cqc_ready else 0,
                        candidate_id,
                    ),
                )
            else:
                db.execute(
                    """INSERT INTO compliance_records
                       (id, candidate_id, overall_status, score, identity_verified,
                        right_to_work_valid, dbs_valid, registration_active,
                        references_verified, cv_validated, flags, audit_log,
                        last_evaluated, cqc_ready)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        generate_id(), candidate_id, overall_status, score,
                        1 if checks["identity_verified"] else 0,
                        1 if checks["right_to_work_valid"] else 0,
                        1 if checks["dbs_valid"] else 0,
                        1 if checks["registration_active"] else 0,
                        1 if checks["references_verified"] else 0,
                        1 if checks["cv_validated"] else 0,
                        json.dumps(flags),
                        json.dumps(audit_entries),
                        now,
                        1 if cqc_ready else 0,
                    ),
                )

            # Update candidate's compliance status
            db.execute(
                "UPDATE candidates SET compliance_score=?, compliance_status=?, updated_at=? WHERE id=?",
                (score, overall_status, now, candidate_id),
            )

            # Audit log
            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (?, 'compliance', ?, 'evaluated', 'compliance_engine', ?, ?)""",
                (
                    generate_id(), candidate_id,
                    json.dumps({"score": score, "status": overall_status, "flags": len(flags)}),
                    now,
                ),
            )

            row = db.execute(
                "SELECT * FROM compliance_records WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            return dict(row)

    @staticmethod
    def get_compliance(candidate_id: str) -> dict:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM compliance_records WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_audit_log(candidate_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM audit_logs WHERE entity_id=? ORDER BY created_at DESC",
                (candidate_id,),
            ).fetchall()
            return [dict(r) for r in rows]
