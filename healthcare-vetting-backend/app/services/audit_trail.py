"""
3.4 Audit Trail & Compliance Reporting

Comprehensive mutation logging with tamper-evident hash chain,
exportable audit reports for CQC/regulatory inspections,
data access logging for GDPR subject access requests,
and retention policy enforcement reporting.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)


class AuditTrailService:
    """Tamper-evident audit trail with hash chain and export capabilities."""

    @staticmethod
    def log_mutation(entity_type: str, entity_id: str, action: str,
                     actor: str, actor_type: str = "user",
                     details: dict = None, ip_address: str = None) -> str:
        """Log a data mutation with hash chain integrity.

        Every audit entry includes a SHA-256 hash of the previous entry,
        creating a tamper-evident chain.
        """
        now = datetime.now(timezone.utc).isoformat()
        log_id = generate_id()
        details_json = json.dumps(details or {}, default=str)

        with get_db() as db:
            # Get the hash of the last audit entry for the chain
            prev = db.execute(
                "SELECT id, chain_hash FROM audit_trail ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
            prev_hash = dict(prev)["chain_hash"] if prev else "GENESIS"

            # Build the chain hash: SHA-256(prev_hash + log_id + entity + action + actor + timestamp)
            chain_input = f"{prev_hash}|{log_id}|{entity_type}|{entity_id}|{action}|{actor}|{now}"
            chain_hash = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()

            db.execute(
                """INSERT INTO audit_trail
                   (id, entity_type, entity_id, action, actor, actor_type,
                    details, ip_address, prev_hash, chain_hash, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (log_id, entity_type, entity_id, action, actor, actor_type,
                 details_json, ip_address, prev_hash, chain_hash, now),
            )

        return log_id

    @staticmethod
    def log_data_access(entity_type: str, entity_id: str,
                        accessor: str, accessor_type: str = "user",
                        purpose: str = None, ip_address: str = None) -> str:
        """Log a data access event for GDPR SAR compliance."""
        now = datetime.now(timezone.utc).isoformat()
        log_id = generate_id()

        with get_db() as db:
            db.execute(
                """INSERT INTO data_access_log
                   (id, entity_type, entity_id, accessor, accessor_type,
                    purpose, ip_address, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (log_id, entity_type, entity_id, accessor, accessor_type,
                 purpose, ip_address, now),
            )

        return log_id

    @staticmethod
    def verify_chain_integrity(limit: int = 1000) -> dict:
        """Verify the integrity of the audit trail hash chain."""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM audit_trail ORDER BY created_at ASC, rowid ASC LIMIT %s",
                (limit,),
            ).fetchall()

            if not rows:
                return {"status": "empty", "verified": 0, "broken_at": None}

            verified = 0
            prev_hash = "GENESIS"

            for row in rows:
                r = dict(row)
                # Recompute the expected chain hash
                chain_input = (
                    f"{prev_hash}|{r['id']}|{r['entity_type']}|{r['entity_id']}|"
                    f"{r['action']}|{r['actor']}|{r['created_at']}"
                )
                expected_hash = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()

                if expected_hash != r["chain_hash"]:
                    return {
                        "status": "broken",
                        "verified": verified,
                        "broken_at": r["id"],
                        "expected_hash": expected_hash,
                        "actual_hash": r["chain_hash"],
                    }

                prev_hash = r["chain_hash"]
                verified += 1

            return {"status": "intact", "verified": verified, "broken_at": None}

    @staticmethod
    def get_audit_log(entity_type: str = None, entity_id: str = None,
                      actor: str = None, action: str = None,
                      date_from: str = None, date_to: str = None,
                      limit: int = 100, offset: int = 0) -> dict:
        """Query the audit trail with filters."""
        conditions = []
        params = []

        if entity_type:
            conditions.append("entity_type=%s")
            params.append(entity_type)
        if entity_id:
            conditions.append("entity_id=%s")
            params.append(entity_id)
        if actor:
            conditions.append("actor=%s")
            params.append(actor)
        if action:
            conditions.append("action LIKE %s")
            params.append(f"%{action}%")
        if date_from:
            conditions.append("created_at >= %s")
            params.append(date_from)
        if date_to:
            conditions.append("created_at <= %s")
            params.append(date_to)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with get_db() as db:
            total = db.execute(
                f"SELECT COUNT(*) AS cnt FROM audit_trail {where}", tuple(params)
            ).fetchone()["cnt"]

            rows = db.execute(
                f"SELECT * FROM audit_trail {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                tuple(params) + (limit, offset),
            ).fetchall()

            items = []
            for row in rows:
                r = dict(row)
                if r.get("details"):
                    try:
                        r["details"] = json.loads(r["details"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                items.append(r)

            return {"total": total, "items": items, "limit": limit, "offset": offset}

    @staticmethod
    def get_data_access_log(entity_type: str = None, entity_id: str = None,
                            accessor: str = None, date_from: str = None,
                            date_to: str = None, limit: int = 100) -> dict:
        """Query data access logs for GDPR SAR responses."""
        conditions = []
        params = []

        if entity_type:
            conditions.append("entity_type=%s")
            params.append(entity_type)
        if entity_id:
            conditions.append("entity_id=%s")
            params.append(entity_id)
        if accessor:
            conditions.append("accessor=%s")
            params.append(accessor)
        if date_from:
            conditions.append("created_at >= %s")
            params.append(date_from)
        if date_to:
            conditions.append("created_at <= %s")
            params.append(date_to)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with get_db() as db:
            rows = db.execute(
                f"SELECT * FROM data_access_log {where} ORDER BY created_at DESC LIMIT %s",
                tuple(params) + (limit,),
            ).fetchall()

            return {"items": [dict(r) for r in rows], "total": len(rows)}

    @staticmethod
    def generate_cqc_audit_export(agency_id: str = None, date_from: str = None,
                                   date_to: str = None) -> dict:
        """Generate a comprehensive CQC audit export."""
        with get_db() as db:
            # Audit trail entries
            conditions = []
            params = []
            if date_from:
                conditions.append("created_at >= %s")
                params.append(date_from)
            if date_to:
                conditions.append("created_at <= %s")
                params.append(date_to)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            audit_entries = db.execute(
                f"SELECT * FROM audit_trail {where} ORDER BY created_at ASC",
                tuple(params),
            ).fetchall()

            # Data access entries
            access_entries = db.execute(
                f"SELECT * FROM data_access_log {where} ORDER BY created_at ASC",
                tuple(params),
            ).fetchall()

            # Chain integrity
            integrity = AuditTrailService.verify_chain_integrity()

            # Retention policy status
            retention_policies = []
            try:
                policies = db.execute("SELECT * FROM gdpr_retention_policies").fetchall()
                retention_policies = [dict(p) for p in policies]
            except Exception:
                pass

            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "agency_id": agency_id,
                "date_range": {"from": date_from, "to": date_to},
                "chain_integrity": integrity,
                "audit_entries": len(audit_entries),
                "data_access_entries": len(access_entries),
                "retention_policies": retention_policies,
                "entries": [dict(r) for r in audit_entries],
                "access_log": [dict(r) for r in access_entries],
            }

    @staticmethod
    def generate_sar_report(candidate_email: str) -> dict:
        """Generate a Subject Access Request report for a candidate."""
        with get_db() as db:
            # Find candidate
            candidate = db.execute(
                "SELECT * FROM candidates WHERE email=%s", (candidate_email,)
            ).fetchone()
            if not candidate:
                return {"status": "not_found", "email": candidate_email}

            c = dict(candidate)
            candidate_id = c["id"]

            # All data mutations related to this candidate
            mutations = db.execute(
                """SELECT * FROM audit_trail
                   WHERE (entity_type='candidate' AND entity_id=%s)
                      OR (entity_type LIKE '%check%' AND entity_id IN
                          (SELECT id FROM identity_checks WHERE candidate_id=%s
                           UNION SELECT id FROM dbs_checks WHERE candidate_id=%s
                           UNION SELECT id FROM right_to_work_checks WHERE candidate_id=%s))
                   ORDER BY created_at ASC""",
                (candidate_id, candidate_id, candidate_id, candidate_id),
            ).fetchall()

            # All data access events for this candidate
            access_events = db.execute(
                """SELECT * FROM data_access_log
                   WHERE (entity_type='candidate' AND entity_id=%s)
                   ORDER BY created_at ASC""",
                (candidate_id,),
            ).fetchall()

            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "candidate": {
                    "id": candidate_id,
                    "email": candidate_email,
                    "name": f"{c.get('first_name', '')} {c.get('last_name', '')}",
                },
                "data_mutations": [dict(r) for r in mutations],
                "data_access_events": [dict(r) for r in access_events],
                "total_mutations": len(mutations),
                "total_access_events": len(access_events),
            }

    @staticmethod
    def get_retention_report() -> dict:
        """Get retention policy enforcement report."""
        with get_db() as db:
            policies = []
            try:
                rows = db.execute("SELECT * FROM gdpr_retention_policies").fetchall()
                for row in rows:
                    p = dict(row)
                    category = p["data_category"]
                    days = p["retention_period_days"]

                    # Count records that would be affected
                    category_map = {
                        "draft_data": ("candidate_draft_data", "updated_at"),
                        "webhook_events": ("webhook_events", "created_at"),
                        "email_notifications": ("email_notifications", "created_at"),
                        "background_tasks": ("background_tasks", "created_at"),
                    }

                    affected = 0
                    if category in category_map:
                        table, date_col = category_map[category]
                        try:
                            affected = db.execute(
                                f"SELECT COUNT(*) AS cnt FROM {table} WHERE {date_col} < datetime('now', '-{days} days')",
                            ).fetchone()["cnt"]
                        except Exception:
                            pass

                    policies.append({
                        **p,
                        "records_due_for_deletion": affected,
                    })
            except Exception:
                pass

            # Last retention run from audit logs
            last_run = db.execute(
                """SELECT created_at, details FROM audit_logs
                   WHERE action='retention_policy_applied'
                   ORDER BY created_at DESC LIMIT 1""",
            ).fetchone()

            return {
                "policies": policies,
                "last_run": dict(last_run) if last_run else None,
            }
