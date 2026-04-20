"""Training catalogue service — per-industry course list used by the
candidate training dropdown and the compliance matcher.

Phase 1 of the training overhaul:
 - Catalogue table `training_courses` (admin-managed, scoped by industry template)
 - Alias-based / course_id matcher so candidates don't need exact string matches
 - Helper for the candidate UI to fetch the courses applicable to them
"""
from __future__ import annotations

import json
import re
import csv
import io
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.utils.auth import generate_id


_CATEGORIES = {"mandatory", "specialist", "cpd", "other"}


def _normalise(name: str) -> str:
    """Lowercase + strip punctuation for fuzzy-matching."""
    if not name:
        return ""
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


def _parse_aliases(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(a) for a in raw if a]
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(parsed, list):
            return [str(a) for a in parsed if a]
    except (json.JSONDecodeError, TypeError):
        # Fall back: comma-separated string
        return [a.strip() for a in str(raw).split(",") if a.strip()]
    return []


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["aliases"] = _parse_aliases(d.get("aliases"))
    d["is_mandatory"] = bool(d.get("is_mandatory"))
    d["is_active"] = bool(d.get("is_active"))
    return d


# ── Read ───────────────────────────────────────────────────────────

def list_courses(
    industry_template_id: Optional[str] = None,
    include_inactive: bool = False,
) -> list[dict]:
    """Return all courses (optionally filtered by template)."""
    with get_db() as db:
        sql = "SELECT * FROM training_courses WHERE 1=1"
        params: list = []
        if industry_template_id:
            sql += " AND industry_template_id=%s"
            params.append(industry_template_id)
        if not include_inactive:
            sql += " AND is_active=1"
        sql += " ORDER BY is_mandatory DESC, sort_order ASC, name ASC"
        db.execute(sql, tuple(params))
        rows = db.fetchall()
        return [_row_to_dict(r) for r in rows]


def get_course(course_id: str) -> Optional[dict]:
    with get_db() as db:
        db.execute("SELECT * FROM training_courses WHERE id=%s", (course_id,))
        row = db.fetchone()
        return _row_to_dict(row) if row else None


def list_courses_for_candidate(candidate_id: str) -> dict:
    """Return {template_id, template_name, policy, courses[]} for a candidate.

    Template resolution mirrors ComplianceEngine: sub-account → agency → default.
    Falls back to the default industry template if the candidate has no
    agency/sub-account mapping.
    """
    with get_db() as db:
        # Find candidate's agency and sub-account
        db.execute(
            "SELECT agency_id, sub_account_id FROM agency_candidates "
            "WHERE candidate_id=%s ORDER BY created_at DESC LIMIT 1",
            (candidate_id,),
        )
        ac = db.fetchone()

        template_id = None
        if ac:
            ac_data = dict(ac)
            sub_id = ac_data.get("sub_account_id")
            if sub_id:
                db.execute(
                    "SELECT industry_template_id FROM agency_sub_accounts WHERE id=%s AND is_active=1",
                    (sub_id,),
                )
                sub_row = db.fetchone()
                if sub_row and dict(sub_row).get("industry_template_id"):
                    template_id = dict(sub_row)["industry_template_id"]
            if not template_id and ac_data.get("agency_id"):
                db.execute(
                    "SELECT industry_template_id FROM agencies WHERE id=%s",
                    (ac_data["agency_id"],),
                )
                ag_row = db.fetchone()
                if ag_row and dict(ag_row).get("industry_template_id"):
                    template_id = dict(ag_row)["industry_template_id"]

        if not template_id:
            db.execute(
                "SELECT id FROM industry_templates WHERE is_default=1 AND is_active=1 LIMIT 1"
            )
            default_row = db.fetchone()
            if default_row:
                template_id = dict(default_row)["id"]

        # Get template metadata + policy
        template_name = None
        policy = "pass_fail"
        if template_id:
            db.execute(
                "SELECT id, name FROM industry_templates WHERE id=%s", (template_id,)
            )
            t_row = db.fetchone()
            if t_row:
                template_name = dict(t_row).get("name")
            db.execute(
                "SELECT config FROM industry_template_checks "
                "WHERE template_id=%s AND check_key='training_compliant'",
                (template_id,),
            )
            cfg_row = db.fetchone()
            if cfg_row:
                try:
                    raw = dict(cfg_row).get("config") or "{}"
                    cfg = json.loads(raw) if isinstance(raw, str) else (raw or {})
                    policy = cfg.get("policy", "pass_fail")
                except (json.JSONDecodeError, TypeError):
                    policy = "pass_fail"

    courses = list_courses(industry_template_id=template_id) if template_id else []
    return {
        "industry_template_id": template_id,
        "industry_template_name": template_name,
        "training_policy": policy,
        "courses": courses,
    }


# ── Matching (used by ComplianceEngine) ────────────────────────────

def build_matcher(industry_template_id: Optional[str]) -> dict:
    """Build a dict of helpers that compliance can use to match certs to courses.

    Returns:
        {
          "courses": [...],
          "by_id": {id: course},
          "by_name_norm": {normalised_name: course},  # includes aliases
        }
    """
    courses = list_courses(industry_template_id=industry_template_id) if industry_template_id else []
    by_id: dict[str, dict] = {}
    by_name_norm: dict[str, dict] = {}
    for c in courses:
        by_id[c["id"]] = c
        by_name_norm[_normalise(c["name"])] = c
        for alias in c.get("aliases", []):
            n = _normalise(alias)
            if n and n not in by_name_norm:
                by_name_norm[n] = c
    return {"courses": courses, "by_id": by_id, "by_name_norm": by_name_norm}


def resolve_cert_to_course(cert: dict, matcher: dict) -> Optional[dict]:
    """Given a training_certificate row (dict) and a matcher, return the
    matching course dict or None."""
    cid = cert.get("course_id")
    if cid and cid in matcher["by_id"]:
        return matcher["by_id"][cid]
    name = cert.get("certificate_name") or ""
    norm = _normalise(name)
    if norm and norm in matcher["by_name_norm"]:
        return matcher["by_name_norm"][norm]
    return None


# ── Write (admin CRUD) ─────────────────────────────────────────────

def create_course(
    *,
    industry_template_id: str,
    name: str,
    aliases: Optional[list[str]] = None,
    category: str = "mandatory",
    description: Optional[str] = None,
    default_validity_months: int = 12,
    is_mandatory: bool = False,
    is_active: bool = True,
    sort_order: int = 0,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    course_id = generate_id()
    cat = category if category in _CATEGORIES else "other"
    with get_db() as db:
        db.execute(
            """INSERT INTO training_courses
               (id, industry_template_id, name, aliases, category, description,
                default_validity_months, is_mandatory, is_active, sort_order,
                created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                course_id, industry_template_id, name,
                json.dumps(aliases or []), cat, description,
                default_validity_months, 1 if is_mandatory else 0,
                1 if is_active else 0, sort_order, now, now,
            ),
        )
    course = get_course(course_id)
    assert course is not None
    return course


def update_course(course_id: str, **fields) -> Optional[dict]:
    allowed = {
        "name", "aliases", "category", "description",
        "default_validity_months", "is_mandatory", "is_active", "sort_order",
        "industry_template_id",
    }
    updates = []
    params: list = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "aliases":
            v = json.dumps(v or [])
        elif k == "category" and v not in _CATEGORIES:
            v = "other"
        elif k in {"is_mandatory", "is_active"}:
            v = 1 if v else 0
        updates.append(f"{k}=%s")
        params.append(v)

    if not updates:
        return get_course(course_id)
    updates.append("updated_at=%s")
    params.append(datetime.now(timezone.utc).isoformat())
    params.append(course_id)

    with get_db() as db:
        db.execute(
            f"UPDATE training_courses SET {', '.join(updates)} WHERE id=%s",
            tuple(params),
        )
    return get_course(course_id)


def delete_course(course_id: str) -> bool:
    with get_db() as db:
        db.execute("DELETE FROM training_courses WHERE id=%s", (course_id,))
    return True


# ── CSV import ─────────────────────────────────────────────────────

def import_courses_csv(industry_template_id: str, csv_text: str) -> dict:
    """Import courses from CSV text.

    Expected columns (header row required, case-insensitive):
        name, aliases, category, default_validity_months, is_mandatory, description

    `aliases` is a semicolon-separated list. Unknown columns are ignored.
    Returns {created, updated, errors}.
    """
    result = {"created": 0, "updated": 0, "errors": []}
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        result["errors"].append("CSV has no header row")
        return result

    normalised_headers = {h.strip().lower(): h for h in reader.fieldnames if h}
    if "name" not in normalised_headers:
        result["errors"].append("CSV must contain a 'name' column")
        return result

    existing = list_courses(industry_template_id=industry_template_id, include_inactive=True)
    by_name = {_normalise(c["name"]): c for c in existing}

    for row_idx, row in enumerate(reader, start=2):
        try:
            name = (row.get(normalised_headers["name"]) or "").strip()
            if not name:
                continue

            aliases_raw = row.get(normalised_headers.get("aliases", ""), "") or ""
            aliases = [a.strip() for a in aliases_raw.split(";") if a.strip()]
            category = (row.get(normalised_headers.get("category", ""), "") or "mandatory").strip().lower()
            validity_raw = (row.get(normalised_headers.get("default_validity_months", ""), "") or "12").strip()
            try:
                validity = int(validity_raw) if validity_raw else 12
            except ValueError:
                validity = 12
            is_mand_raw = (row.get(normalised_headers.get("is_mandatory", ""), "") or "").strip().lower()
            is_mandatory = is_mand_raw in {"1", "true", "yes", "y", "mandatory"}
            description = (row.get(normalised_headers.get("description", ""), "") or "").strip() or None

            existing_course = by_name.get(_normalise(name))
            if existing_course:
                update_course(
                    existing_course["id"],
                    aliases=aliases or existing_course.get("aliases", []),
                    category=category,
                    default_validity_months=validity,
                    is_mandatory=is_mandatory,
                    description=description,
                )
                result["updated"] += 1
            else:
                create_course(
                    industry_template_id=industry_template_id,
                    name=name,
                    aliases=aliases,
                    category=category,
                    description=description,
                    default_validity_months=validity,
                    is_mandatory=is_mandatory,
                )
                result["created"] += 1
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"Row {row_idx}: {e}")

    return result


# ── Training policy (per-industry) ─────────────────────────────────

def get_training_policy(industry_template_id: str) -> str:
    """Return 'pass_fail' or 'informational'."""
    with get_db() as db:
        db.execute(
            "SELECT config FROM industry_template_checks "
            "WHERE template_id=%s AND check_key='training_compliant'",
            (industry_template_id,),
        )
        row = db.fetchone()
        if not row:
            return "pass_fail"
        try:
            raw = dict(row).get("config") or "{}"
            cfg = json.loads(raw) if isinstance(raw, str) else (raw or {})
            policy = cfg.get("policy", "pass_fail")
            if policy not in {"pass_fail", "informational"}:
                policy = "pass_fail"
            return policy
        except (json.JSONDecodeError, TypeError):
            return "pass_fail"


def set_training_policy(industry_template_id: str, policy: str) -> dict:
    """Update the training_compliant.policy for an industry template."""
    if policy not in {"pass_fail", "informational"}:
        raise ValueError("policy must be 'pass_fail' or 'informational'")

    with get_db() as db:
        db.execute(
            "SELECT id, config, is_required FROM industry_template_checks "
            "WHERE template_id=%s AND check_key='training_compliant'",
            (industry_template_id,),
        )
        row = db.fetchone()
        if not row:
            raise ValueError("Industry template has no training_compliant check")
        row_data = dict(row)
        try:
            raw = row_data.get("config") or "{}"
            cfg = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (json.JSONDecodeError, TypeError):
            cfg = {}
        cfg["policy"] = policy
        # When switching to informational, also flip is_required off so the
        # overall compliance summary doesn't block on training.
        new_required = 0 if policy == "informational" else (row_data.get("is_required") or 1)
        db.execute(
            "UPDATE industry_template_checks SET config=%s, is_required=%s WHERE id=%s",
            (json.dumps(cfg), new_required, row_data["id"]),
        )

    return {"industry_template_id": industry_template_id, "training_policy": policy}
