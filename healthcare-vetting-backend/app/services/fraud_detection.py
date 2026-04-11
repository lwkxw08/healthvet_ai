"""
Cross-Candidate Fraud Detection Service
Detects document reuse, reference rings, suspicious patterns across candidates.
"""
import json
import hashlib
import logging
from datetime import datetime, timezone
from collections import defaultdict
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)


class FraudDetectionService:
    """Cross-candidate fraud detection and pattern analysis."""

    @staticmethod
    def run_full_scan() -> dict:
        """Run all fraud detection scans across all candidates."""
        results = {
            "duplicate_documents": FraudDetectionService.detect_duplicate_documents(),
            "reference_rings": FraudDetectionService.detect_reference_rings(),
            "suspicious_patterns": FraudDetectionService.detect_suspicious_patterns(),
            "email_domain_clusters": FraudDetectionService.detect_email_domain_clusters(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        results["total_flags"] = sum(len(v) for v in results.values() if isinstance(v, list))
        return results

    @staticmethod
    def detect_duplicate_documents() -> list:
        """Detect the same document (passport, certificate) used by multiple candidates."""
        flags = []
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            # Check DBS certificate numbers used by multiple candidates
            dbs_dupes = db.execute(
                """SELECT certificate_number, GROUP_CONCAT(candidate_id) as candidates,
                          COUNT(DISTINCT candidate_id) as cnt
                   FROM dbs_checks
                   WHERE certificate_number IS NOT NULL
                   GROUP BY certificate_number
                   HAVING cnt > 1""",
            ).fetchall()

            for dupe in dbs_dupes:
                d = dict(dupe)
                flag = {
                    "type": "duplicate_dbs_certificate",
                    "severity": "critical",
                    "certificate_number": d["certificate_number"],
                    "candidate_ids": d["candidates"].split(","),
                    "count": d["cnt"],
                    "message": f"DBS certificate {d['certificate_number']} used by {d['cnt']} candidates",
                }
                flags.append(flag)
                _create_fraud_alert(db, flag, now)

            # Check registration numbers used by multiple candidates
            reg_dupes = db.execute(
                """SELECT registration_number, body, GROUP_CONCAT(candidate_id) as candidates,
                          COUNT(DISTINCT candidate_id) as cnt
                   FROM registration_checks
                   WHERE registration_number IS NOT NULL
                   GROUP BY registration_number, body
                   HAVING cnt > 1""",
            ).fetchall()

            for dupe in reg_dupes:
                d = dict(dupe)
                flag = {
                    "type": "duplicate_registration",
                    "severity": "critical",
                    "registration_number": d["registration_number"],
                    "body": d["body"],
                    "candidate_ids": d["candidates"].split(","),
                    "count": d["cnt"],
                    "message": f"{d['body']} registration {d['registration_number']} used by {d['cnt']} candidates",
                }
                flags.append(flag)
                _create_fraud_alert(db, flag, now)

            # Check NI numbers used by multiple candidates
            ni_dupes = db.execute(
                """SELECT ni_number, GROUP_CONCAT(candidate_id) as candidates,
                          COUNT(DISTINCT candidate_id) as cnt
                   FROM right_to_work_checks
                   WHERE ni_number IS NOT NULL AND ni_number != ''
                   GROUP BY ni_number
                   HAVING cnt > 1""",
            ).fetchall()

            for dupe in ni_dupes:
                d = dict(dupe)
                flag = {
                    "type": "duplicate_ni_number",
                    "severity": "critical",
                    "ni_number": d["ni_number"],
                    "candidate_ids": d["candidates"].split(","),
                    "count": d["cnt"],
                    "message": f"NI number {d['ni_number']} used by {d['cnt']} candidates",
                }
                flags.append(flag)
                _create_fraud_alert(db, flag, now)

        return flags

    @staticmethod
    def detect_reference_rings() -> list:
        """Detect circular referencing patterns (A references B, B references A)."""
        flags = []
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            # Get all references with candidate emails
            refs = db.execute(
                """SELECT r.candidate_id, r.referee_email, c.email as candidate_email
                   FROM references_ r
                   JOIN candidates c ON r.candidate_id = c.id""",
            ).fetchall()

            # Build a graph: candidate_email -> set of referee_emails
            candidate_to_referees = defaultdict(set)
            email_to_candidate = {}
            for ref in refs:
                r = dict(ref)
                candidate_to_referees[r["candidate_email"]].add(r["referee_email"])
                email_to_candidate[r["candidate_email"]] = r["candidate_id"]

            # Detect rings: if candidate A has referee B, and candidate B has referee A
            checked = set()
            for email_a, referees_a in candidate_to_referees.items():
                for referee_email in referees_a:
                    if referee_email in candidate_to_referees:
                        referees_b = candidate_to_referees[referee_email]
                        if email_a in referees_b:
                            pair = tuple(sorted([email_a, referee_email]))
                            if pair not in checked:
                                checked.add(pair)
                                flag = {
                                    "type": "reference_ring",
                                    "severity": "high",
                                    "candidate_ids": [
                                        email_to_candidate.get(email_a, ""),
                                        email_to_candidate.get(referee_email, ""),
                                    ],
                                    "emails": list(pair),
                                    "message": f"Circular reference detected: {email_a} and {referee_email} reference each other",
                                }
                                flags.append(flag)
                                _create_fraud_alert(db, flag, now)

            # Also check employment verifications for rings
            emp_vers = db.execute(
                """SELECT ev.candidate_id, ev.verifier_email, c.email as candidate_email
                   FROM employment_verifications ev
                   JOIN candidates c ON ev.candidate_id = c.id""",
            ).fetchall()

            emp_to_verifiers = defaultdict(set)
            for ev in emp_vers:
                e = dict(ev)
                emp_to_verifiers[e["candidate_email"]].add(e["verifier_email"])

            for email_a, verifiers_a in emp_to_verifiers.items():
                for verifier_email in verifiers_a:
                    if verifier_email in emp_to_verifiers:
                        verifiers_b = emp_to_verifiers[verifier_email]
                        if email_a in verifiers_b:
                            pair = tuple(sorted([email_a, verifier_email]))
                            if pair not in checked:
                                checked.add(pair)
                                flag = {
                                    "type": "employment_verification_ring",
                                    "severity": "high",
                                    "emails": list(pair),
                                    "message": f"Circular employment verification: {email_a} and {verifier_email} verify each other",
                                }
                                flags.append(flag)
                                _create_fraud_alert(db, flag, now)

        return flags

    @staticmethod
    def detect_suspicious_patterns() -> list:
        """Detect suspicious behavioral patterns across candidates."""
        flags = []
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            # Candidates with all checks completed within 5 minutes (too fast)
            candidates = db.execute("SELECT * FROM candidates").fetchall()

            for cand in candidates:
                c = dict(cand)
                cid = c["id"]

                # Get timestamps of all check completions
                timestamps = []
                for table, col in [
                    ("identity_checks", "completed_at"),
                    ("right_to_work_checks", "checked_at"),
                    ("dbs_checks", "completed_at"),
                    ("cv_analyses", "analysed_at"),
                ]:
                    row = db.execute(
                        f"SELECT {col} FROM {table} WHERE candidate_id=%s AND {col} IS NOT NULL ORDER BY {col} DESC LIMIT 1",
                        (cid,),
                    ).fetchone()
                    if row:
                        try:
                            timestamps.append(datetime.fromisoformat(dict(row)[col]))
                        except (ValueError, TypeError):
                            pass

                if len(timestamps) >= 3:
                    timestamps.sort()
                    span = (timestamps[-1] - timestamps[0]).total_seconds()
                    if span < 300:  # All checks within 5 minutes
                        flag = {
                            "type": "rapid_completion",
                            "severity": "medium",
                            "candidate_id": cid,
                            "time_span_seconds": span,
                            "message": f"All checks completed within {span:.0f}s for {c.get('first_name', '')} {c.get('last_name', '')} - unusually fast",
                        }
                        flags.append(flag)

            # Check for same referee used across many unrelated candidates
            referee_counts = db.execute(
                """SELECT referee_email, COUNT(DISTINCT candidate_id) as cnt,
                          GROUP_CONCAT(DISTINCT candidate_id) as candidates
                   FROM references_
                   GROUP BY referee_email
                   HAVING cnt >= 3""",
            ).fetchall()

            for rc in referee_counts:
                r = dict(rc)
                flag = {
                    "type": "frequent_referee",
                    "severity": "medium",
                    "referee_email": r["referee_email"],
                    "candidate_count": r["cnt"],
                    "candidate_ids": r["candidates"].split(","),
                    "message": f"Referee {r['referee_email']} used by {r['cnt']} different candidates",
                }
                flags.append(flag)

        return flags

    @staticmethod
    def detect_email_domain_clusters() -> list:
        """Detect suspicious clustering of free email domains in references."""
        flags = []
        free_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
                        "protonmail.com", "mail.com", "icloud.com", "live.com", "yandex.com"}

        with get_db() as db:
            # References using free email domains for professional references
            free_refs = db.execute(
                """SELECT r.*, c.first_name, c.last_name
                   FROM references_ r
                   JOIN candidates c ON r.candidate_id = c.id""",
            ).fetchall()

            candidates_with_free = defaultdict(int)
            candidates_total = defaultdict(int)

            for ref in free_refs:
                r = dict(ref)
                email = r.get("referee_email", "")
                domain = email.split("@")[-1].lower() if "@" in email else ""
                cid = r["candidate_id"]
                candidates_total[cid] += 1
                if domain in free_domains:
                    candidates_with_free[cid] += 1

            for cid, free_count in candidates_with_free.items():
                total = candidates_total.get(cid, 0)
                if total > 0 and free_count == total and total >= 2:
                    flag = {
                        "type": "all_free_email_references",
                        "severity": "low",
                        "candidate_id": cid,
                        "free_email_count": free_count,
                        "message": f"All {free_count} references use free email providers (no professional domains)",
                    }
                    flags.append(flag)

        return flags

    @staticmethod
    def get_fraud_flags(candidate_id: str = None) -> list:
        """Get stored fraud flags."""
        with get_db() as db:
            if candidate_id:
                rows = db.execute(
                    """SELECT * FROM fraud_flags WHERE candidate_id=%s
                       ORDER BY created_at DESC""",
                    (candidate_id,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM fraud_flags ORDER BY created_at DESC LIMIT 100",
                ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_scan_summary() -> dict:
        """Get summary of latest fraud scan results."""
        with get_db() as db:
            total = db.execute("SELECT COUNT(*) as cnt FROM fraud_flags").fetchone()
            by_type = db.execute(
                """SELECT flag_type, severity, COUNT(*) as cnt
                   FROM fraud_flags GROUP BY flag_type, severity
                   ORDER BY cnt DESC""",
            ).fetchall()
            unresolved = db.execute(
                "SELECT COUNT(*) as cnt FROM fraud_flags WHERE is_resolved=0",
            ).fetchone()
            return {
                "total_flags": dict(total)["cnt"] if total else 0,
                "unresolved": dict(unresolved)["cnt"] if unresolved else 0,
                "by_type": [dict(r) for r in by_type],
            }


def _create_fraud_alert(db, flag: dict, timestamp: str):
    """Create a fraud flag entry in the database."""
    candidate_ids = flag.get("candidate_ids", [])
    candidate_id = flag.get("candidate_id") or (candidate_ids[0] if candidate_ids else None)
    if not candidate_id:
        return

    # Check if similar flag already exists
    existing = db.execute(
        """SELECT id FROM fraud_flags
           WHERE flag_type=%s AND candidate_id=%s AND is_resolved=0""",
        (flag["type"], candidate_id),
    ).fetchone()

    if not existing:
        db.execute(
            """INSERT INTO fraud_flags
               (id, candidate_id, flag_type, severity, message, details, is_resolved, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, 0, %s)""",
            (generate_id(), candidate_id, flag["type"], flag["severity"],
             flag["message"], json.dumps(flag), timestamp),
        )
