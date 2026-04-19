import psycopg2
import psycopg2.extras
import psycopg2.pool
import os
from contextlib import contextmanager

# PostgreSQL connection via DATABASE_URL (Railway provides this)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://healthvet:healthvet@localhost:5432/healthvet_db",
)
# Railway uses postgres:// but psycopg2 requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Connection pool for efficiency
_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL,
        )
    return _pool


def get_connection():
    pool = _get_pool()
    conn = pool.getconn()
    conn.autocommit = False
    return conn


def _return_connection(conn):
    try:
        _get_pool().putconn(conn)
    except Exception:
        pass


@contextmanager
def get_db():
    """Yield a *cursor* (RealDictCursor) with auto-commit/rollback.

    The old SQLite version yielded a connection whose .execute() returned a
    cursor-like object.  psycopg2 connections also have .execute() but the
    semantics differ.  By yielding a cursor directly every call-site that does
    ``db.execute(…)`` / ``db.fetchone()`` / ``db.fetchall()`` keeps working
    without changes.
    """
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        _return_connection(conn)


# ---------------------------------------------------------------------------
# Helpers for migration
# ---------------------------------------------------------------------------

def _column_exists(cursor, table, column):
    cursor.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return cursor.fetchone() is not None


def _table_exists(cursor, table):
    cursor.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s AND table_schema = 'public'",
        (table,),
    )
    return cursor.fetchone() is not None


def _add_column_if_missing(cursor, table, column, col_type):
    if not _column_exists(cursor, table, column):
        cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {col_type}')


def migrate_db():
    """Run database migrations for schema changes."""
    conn = get_connection()
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    cursor = conn.cursor()
    # Add new columns to right_to_work_checks if they don't exist
    _add_column_if_missing(cursor, "right_to_work_checks", "verification_method", "TEXT DEFAULT 'share_code'")
    _add_column_if_missing(cursor, "right_to_work_checks", "nationality", "TEXT")
    _add_column_if_missing(cursor, "right_to_work_checks", "document_type", "TEXT")
    _add_column_if_missing(cursor, "right_to_work_checks", "document_reference", "TEXT")
    _add_column_if_missing(cursor, "right_to_work_checks", "ni_number", "TEXT")
    # Also create new tables if they don't exist (for existing databases)
    if not _table_exists(cursor, "employment_history"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS employment_history (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            cv_analysis_id TEXT,
            employer_name TEXT NOT NULL,
            job_title TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            is_current INTEGER DEFAULT 0,
            reason_for_leaving TEXT,
            duties TEXT,
            verifier_name TEXT,
            verifier_email TEXT,
            verifier_job_title TEXT,
            source TEXT DEFAULT 'cv_extracted',
            created_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        )""")
    if not _table_exists(cursor, "employment_verifications"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS employment_verifications (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            employment_id TEXT NOT NULL,
            verifier_name TEXT NOT NULL,
            verifier_email TEXT NOT NULL,
            verifier_job_title TEXT,
            employer_name TEXT,
            token TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            job_title_confirmed INTEGER,
            dates_confirmed INTEGER,
            reason_for_leaving_confirmed TEXT,
            additional_comments TEXT,
            fraud_flags TEXT,
            ip_address TEXT,
            domain_verified INTEGER DEFAULT 0,
            reminder_count INTEGER DEFAULT 0,
            sent_at TEXT DEFAULT (NOW()::text),
            completed_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id),
            FOREIGN KEY (employment_id) REFERENCES employment_history(id)
        )""")
    # Create agency_invites table if it doesn't exist
    if not _table_exists(cursor, "agency_invites"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS agency_invites (
            id TEXT PRIMARY KEY,
            agency_id TEXT NOT NULL,
            candidate_email TEXT NOT NULL,
            invite_code TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'pending',
            candidate_id TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            accepted_at TEXT,
            FOREIGN KEY (agency_id) REFERENCES agencies(id),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        )""")
    # Add employment_status column to agency_candidates if missing
    _add_column_if_missing(cursor, "agency_candidates", "employment_status", "TEXT DEFAULT 'vetting'")
    _add_column_if_missing(cursor, "agency_candidates", "employment_status_updated_at", "TEXT")
    _add_column_if_missing(cursor, "agency_candidates", "annual_monitoring", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "agency_candidates", "vetting_cost_accepted", "REAL DEFAULT 0")
    _add_column_if_missing(cursor, "agency_candidates", "monitoring_cost_accepted", "REAL DEFAULT 0")
    # Add include_monitoring and cost columns to agency_invites if missing
    _add_column_if_missing(cursor, "agency_invites", "include_monitoring", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "agency_invites", "vetting_cost", "REAL DEFAULT 0")
    _add_column_if_missing(cursor, "agency_invites", "monitoring_cost", "REAL DEFAULT 0")
    # Add missing columns to agencies table
    _add_column_if_missing(cursor, "agencies", "status", "TEXT DEFAULT 'active'")
    _add_column_if_missing(cursor, "agencies", "discount_percent", "REAL DEFAULT 0")
    _add_column_if_missing(cursor, "agencies", "billing_mode", "TEXT DEFAULT 'manual_invoicing'")
    _add_column_if_missing(cursor, "agencies", "stripe_customer_id", "TEXT")
    _add_column_if_missing(cursor, "agencies", "industry_template_id", "TEXT")
    # Add adjusted_amount, adjustment_notes, payment_method, stripe_session_id columns to invoices if missing
    _add_column_if_missing(cursor, "invoices", "adjusted_amount", "REAL")
    _add_column_if_missing(cursor, "invoices", "adjustment_notes", "TEXT")
    _add_column_if_missing(cursor, "invoices", "candidate_email", "TEXT")
    _add_column_if_missing(cursor, "invoices", "payment_method", "TEXT DEFAULT 'manual'")
    _add_column_if_missing(cursor, "invoices", "stripe_session_id", "TEXT")
    _add_column_if_missing(cursor, "invoices", "stripe_payment_intent_id", "TEXT")
    _add_column_if_missing(cursor, "invoices", "due_date", "TEXT")
    _add_column_if_missing(cursor, "invoices", "reminder_sent_at", "TEXT")
    _add_column_if_missing(cursor, "invoices", "reminder_count", "INTEGER DEFAULT 0")
    # Create pricing_settings table if it doesn't exist
    if not _table_exists(cursor, "pricing_settings"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS pricing_settings (
            id TEXT PRIMARY KEY,
            check_type TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            cost_price REAL DEFAULT 0.0,
            sell_price REAL DEFAULT 0.0,
            updated_at TEXT DEFAULT (NOW()::text)
        )""")
    # Create invoices table if it doesn't exist
    if not _table_exists(cursor, "invoices"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            agency_id TEXT NOT NULL,
            candidate_id TEXT,
            check_type TEXT,
            description TEXT,
            cost_amount REAL DEFAULT 0.0,
            sell_amount REAL DEFAULT 0.0,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (NOW()::text),
            paid_at TEXT,
            FOREIGN KEY (agency_id) REFERENCES agencies(id)
        )""")
    # Add employment_verified column to compliance_records if missing
    _add_column_if_missing(cursor, "compliance_records", "employment_verified", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "compliance_records", "training_compliant", "INTEGER DEFAULT 0")
    # Add cv_file_name column to cv_analyses if missing
    _add_column_if_missing(cursor, "cv_analyses", "cv_file_name", "TEXT")
    _add_column_if_missing(cursor, "cv_analyses", "employment_entries", "TEXT")
    # Add monthly_checks and checks_used columns to agency_subscriptions if missing
    _add_column_if_missing(cursor, "agency_subscriptions", "monthly_checks", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "agency_subscriptions", "checks_used", "INTEGER DEFAULT 0")
    # Add monthly_checks and new columns to subscription_tier_config if missing
    _add_column_if_missing(cursor, "subscription_tier_config", "monthly_checks", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "subscription_tier_config", "overage_rate", "REAL DEFAULT 0")
    _add_column_if_missing(cursor, "subscription_tier_config", "allow_rollover", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "subscription_tier_config", "monitoring_included", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "subscription_tier_config", "monitoring_cap", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "subscription_tier_config", "monitoring_addon_rate", "REAL DEFAULT 0")
    _add_column_if_missing(cursor, "subscription_tier_config", "is_active", "INTEGER DEFAULT 1")
    # Add rollover and credit columns to agency_subscriptions if missing
    _add_column_if_missing(cursor, "agency_subscriptions", "credits_total", "REAL DEFAULT 0")
    _add_column_if_missing(cursor, "agency_subscriptions", "credits_used", "REAL DEFAULT 0")
    _add_column_if_missing(cursor, "agency_subscriptions", "rollover_credits", "REAL DEFAULT 0")
    _add_column_if_missing(cursor, "agency_subscriptions", "allow_rollover", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "agency_subscriptions", "overage_rate", "REAL DEFAULT 0")
    # Seed default pricing if table is empty
    cursor.execute("SELECT COUNT(*) AS cnt FROM pricing_settings")
    count = cursor.fetchone()["cnt"]
    if count == 0:
        defaults = [
            ("identity", "Identity Verification", 2.0, 15.0),
            ("dbs", "Enhanced DBS Check", 49.0, 85.0),
            ("right_to_work", "Right to Work", 1.0, 10.0),
            ("cv_analysis", "CV Analysis", 1.5, 12.0),
            ("registration", "Registration Check", 1.0, 10.0),
            ("references", "References (per ref)", 0.5, 8.0),
            ("employment", "Employment Verification", 1.0, 10.0),
            ("monitoring", "Continuous Monitoring (annual)", 5.0, 50.0),
        ]
        for check_type, label, cost, sell in defaults:
            from app.utils.auth import generate_id
            cursor.execute(
                "INSERT INTO pricing_settings (id, check_type, label, cost_price, sell_price) VALUES (%s, %s, %s, %s, %s)",
                (generate_id(), check_type, label, cost, sell),
            )

    # Seed expanded check types (granular DBS variants, etc.) if not already present
    from app.utils.auth import generate_id as _gid_expand
    expanded_checks = [
        ("dbs_standard", "Standard DBS Check", 26.0, 45.0),
        ("dbs_enhanced", "Enhanced DBS Check", 49.0, 85.0),
        ("dbs_enhanced_barred", "Enhanced DBS + Barred List", 49.0, 95.0),
        ("dbs_basic", "Basic DBS Check", 18.0, 30.0),
        ("dbs_update_service", "DBS Update Service Check", 6.0, 15.0),
        ("overseas_criminal", "Overseas Criminal Record Check", 20.0, 55.0),
        ("professional_registration", "Professional Registration (NMC/GMC/HCPC)", 2.0, 15.0),
        ("fit_to_work", "Fit to Work / Occupational Health", 15.0, 40.0),
        ("training_verification", "Training Certificate Verification", 1.0, 8.0),
        ("address_history", "Address History Check (5yr)", 3.0, 12.0),
        ("sanctions_check", "Sanctions & Barred List Check", 5.0, 20.0),
    ]
    for check_type, label, cost, sell in expanded_checks:
        cursor.execute(
            "INSERT INTO pricing_settings (id, check_type, label, cost_price, sell_price) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (check_type) DO NOTHING",
            (_gid_expand(), check_type, label, cost, sell),
        )

    # Seed default partial credit rates if table is empty
    pcr_count = 0
    if _table_exists(cursor, "partial_credit_rates"):
        cursor.execute("SELECT COUNT(*) AS cnt FROM partial_credit_rates")
        pcr_count = cursor.fetchone()["cnt"]
    if pcr_count == 0:
        from app.utils.auth import generate_id as _gid
        pcr_defaults = [
            ("full_vetting", "Full Vetting", 1.0, 73.50),
            ("dbs_recheck", "DBS Recheck", 0.5, 41.00),
            ("rtw_recheck", "Right to Work Recheck", 0.15, 4.00),
            ("registration_check", "Registration Check Only", 0.10, 2.00),
            ("reference_recheck", "Reference Re-chase (x1)", 0.12, 7.50),
            ("training_update", "Training Certificate Update", 0.08, 1.50),
            ("health_declaration", "Health Declaration Only", 0.05, 0.00),
        ]
        for ct, lbl, cv, cost in pcr_defaults:
            cursor.execute(
                "INSERT INTO partial_credit_rates (id, check_type, label, credit_value, third_party_cost) VALUES (%s, %s, %s, %s, %s)",
                (_gid(), ct, lbl, cv, cost),
            )

    # Seed default subscription tier config if table is empty
    stc_count = 0
    if _table_exists(cursor, "subscription_tier_config"):
        cursor.execute("SELECT COUNT(*) AS cnt FROM subscription_tier_config")
        stc_count = cursor.fetchone()["cnt"]
    if stc_count == 0:
        from app.utils.auth import generate_id as _gid2
        import json as _json
        # Credit pack model: no monthly recurring charge, credits valid for 12 months
        stc_defaults = [
            ("starter", "Starter Pack", 125.0, 0, 99999, 25, 0, 0, 0, 0, 0,
             _json.dumps(["25 credits", "12-month validity", "Full compliance dashboard", "Email alerts", "Standard support"])),
            ("standard", "Standard Pack", 225.0, 0, 99999, 50, 0, 0, 0, 0, 0,
             _json.dumps(["50 credits", "12-month validity", "10% saving per check", "Advanced analytics", "Priority alerts", "CQC audit pack"])),
            ("professional", "Professional Pack", 400.0, 0, 99999, 100, 0, 0, 0, 0, 0,
             _json.dumps(["100 credits", "12-month validity", "20% saving per check", "Full analytics suite", "Dedicated account manager", "SLA guarantee"])),
            ("enterprise", "Enterprise Pack", 875.0, 0, 99999, 250, 0, 0, 0, 0, 0,
             _json.dumps(["250 credits", "12-month validity", "30% saving per check", "Unlimited monitoring", "Custom integrations", "White-label options", "Dedicated account manager"])),
        ]
        for tier_key, name, mp, pwp, mw, mc, ovr, ar, mi, mcap, mar, feats in stc_defaults:
            cursor.execute(
                """INSERT INTO subscription_tier_config
                   (id, tier_key, name, monthly_price, per_worker_price, max_workers, monthly_checks,
                    overage_rate, allow_rollover, monitoring_included, monitoring_cap, monitoring_addon_rate, features, is_active)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)""",
                (_gid2(), tier_key, name, mp, pwp, mw, mc, ovr, ar, mi, mcap, mar, feats),
            )

    # Add industry_template_id column to agencies if missing
    _add_column_if_missing(cursor, "agencies", "industry_template_id", "TEXT")

    # Add industry_template_id column to agency_sub_accounts if missing
    _add_column_if_missing(cursor, "agency_sub_accounts", "industry_template_id", "TEXT")

    # Add invited_by_sub_account_id column to agency_candidates if missing
    _add_column_if_missing(cursor, "agency_candidates", "invited_by_sub_account_id", "TEXT")

    # Add sub_account_id column to agency_invites if missing
    _add_column_if_missing(cursor, "agency_invites", "sub_account_id", "TEXT")

    # Create industry_templates and seed defaults if needed
    if not _table_exists(cursor, "industry_templates"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS industry_templates (
            id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, description TEXT,
            compliance_label TEXT DEFAULT 'Compliant', compliance_threshold REAL DEFAULT 95.0,
            is_default INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (NOW()::text), updated_at TEXT
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS industry_template_checks (
            id TEXT PRIMARY KEY, template_id TEXT NOT NULL, check_key TEXT NOT NULL,
            check_label TEXT NOT NULL, is_required INTEGER DEFAULT 1, is_enabled INTEGER DEFAULT 1,
            weight REAL DEFAULT 10.0, config TEXT DEFAULT '{}', sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (template_id) REFERENCES industry_templates(id), UNIQUE(template_id, check_key)
        )""")

    # Seed default industry templates if table is empty
    tmpl_count = 0
    if _table_exists(cursor, "industry_templates"):
        cursor.execute("SELECT COUNT(*) AS cnt FROM industry_templates")
        tmpl_count = cursor.fetchone()["cnt"]
    if tmpl_count == 0:
        from app.utils.auth import generate_id as _tid
        import json as _tjson
        _templates = [
            ("healthcare_cqc", "Healthcare (CQC)", "CQC-regulated healthcare staffing — nurses, care workers, allied health professionals", "CQC Ready", 95.0, 1, [
                ("identity_verified", "Identity Verification", 1, 1, 13, _tjson.dumps({"provider": "onfido"}), 1),
                ("right_to_work_valid", "Right to Work", 1, 1, 13, _tjson.dumps({"requires_imposter_check": True}), 2),
                ("dbs_valid", "DBS Check", 1, 1, 17, _tjson.dumps({"level": "enhanced_barred", "workforce": "adults"}), 3),
                ("registration_active", "Professional Registration", 1, 1, 9, _tjson.dumps({"bodies": ["NMC", "GMC", "HCPC", "GPhC", "GOC", "GDC"]}), 4),
                ("cv_validated", "CV Validation", 0, 1, 5, _tjson.dumps({}), 5),
                ("employment_verified", "Employment Verification", 1, 1, 13, _tjson.dumps({}), 6),
                ("references_verified", "References", 1, 1, 13, _tjson.dumps({"min_count": 2}), 7),
                ("training_compliant", "Mandatory Training", 1, 1, 12, _tjson.dumps({"certificates": ["Manual Handling", "Infection Prevention & Control", "Safeguarding Adults", "Safeguarding Children", "Basic Life Support (BLS)", "Fire Safety", "Health & Safety"]}), 8),
            ]),
            ("education", "Education", "Schools, colleges, and educational institutions", "Safeguarding Compliant", 95.0, 0, [
                ("identity_verified", "Identity Verification", 1, 1, 15, _tjson.dumps({"provider": "onfido"}), 1),
                ("right_to_work_valid", "Right to Work", 1, 1, 15, _tjson.dumps({"requires_imposter_check": True}), 2),
                ("dbs_valid", "DBS Check", 1, 1, 20, _tjson.dumps({"level": "enhanced_barred", "workforce": "children"}), 3),
                ("registration_active", "Teaching Registration", 0, 1, 5, _tjson.dumps({"bodies": ["TRA", "EWC", "GTCS"]}), 4),
                ("cv_validated", "CV Validation", 1, 1, 10, _tjson.dumps({}), 5),
                ("employment_verified", "Employment Verification", 1, 1, 15, _tjson.dumps({}), 6),
                ("references_verified", "References", 1, 1, 15, _tjson.dumps({"min_count": 2}), 7),
                ("training_compliant", "Safeguarding Training", 1, 1, 5, _tjson.dumps({"certificates": ["Safeguarding Children", "Prevent Duty", "First Aid"]}), 8),
            ]),
            ("construction", "Construction (CSCS)", "Construction sites and trades — requires CSCS card verification", "Site Ready", 90.0, 0, [
                ("identity_verified", "Identity Verification", 1, 1, 20, _tjson.dumps({"provider": "onfido"}), 1),
                ("right_to_work_valid", "Right to Work", 1, 1, 20, _tjson.dumps({"requires_imposter_check": False}), 2),
                ("dbs_valid", "DBS Check", 1, 1, 15, _tjson.dumps({"level": "basic"}), 3),
                ("registration_active", "CSCS Card", 0, 0, 0, _tjson.dumps({"bodies": ["CSCS"]}), 4),
                ("cv_validated", "CV Validation", 0, 1, 5, _tjson.dumps({}), 5),
                ("employment_verified", "Employment Verification", 1, 1, 15, _tjson.dumps({}), 6),
                ("references_verified", "References", 1, 1, 15, _tjson.dumps({"min_count": 1}), 7),
                ("training_compliant", "Site Safety Training", 1, 1, 10, _tjson.dumps({"certificates": ["CSCS Health & Safety", "Working at Heights", "Manual Handling"]}), 8),
            ]),
            ("social_care", "Social Care", "Domiciliary care, residential care homes, supported living", "CQC Ready", 95.0, 0, [
                ("identity_verified", "Identity Verification", 1, 1, 13, _tjson.dumps({"provider": "onfido"}), 1),
                ("right_to_work_valid", "Right to Work", 1, 1, 13, _tjson.dumps({"requires_imposter_check": True}), 2),
                ("dbs_valid", "DBS Check", 1, 1, 17, _tjson.dumps({"level": "enhanced_barred", "workforce": "adults"}), 3),
                ("registration_active", "Professional Registration", 0, 1, 5, _tjson.dumps({"bodies": ["Social Work England"]}), 4),
                ("cv_validated", "CV Validation", 0, 1, 5, _tjson.dumps({}), 5),
                ("employment_verified", "Employment Verification", 1, 1, 13, _tjson.dumps({}), 6),
                ("references_verified", "References", 1, 1, 17, _tjson.dumps({"min_count": 2}), 7),
                ("training_compliant", "Care Training", 1, 1, 12, _tjson.dumps({"certificates": ["Manual Handling", "Medication Administration", "Safeguarding Adults", "Infection Prevention & Control", "First Aid", "Fire Safety"]}), 8),
            ]),
            ("finance", "Finance (FCA)", "FCA-regulated financial services — banking, insurance, fintech", "FCA Compliant", 95.0, 0, [
                ("identity_verified", "Identity Verification", 1, 1, 15, _tjson.dumps({"provider": "onfido"}), 1),
                ("right_to_work_valid", "Right to Work", 1, 1, 15, _tjson.dumps({"requires_imposter_check": False}), 2),
                ("dbs_valid", "DBS Check", 1, 1, 10, _tjson.dumps({"level": "basic"}), 3),
                ("registration_active", "FCA Register", 1, 1, 15, _tjson.dumps({"bodies": ["FCA"]}), 4),
                ("cv_validated", "CV Validation", 1, 1, 10, _tjson.dumps({}), 5),
                ("employment_verified", "Employment Verification", 1, 1, 15, _tjson.dumps({}), 6),
                ("references_verified", "References", 1, 1, 15, _tjson.dumps({"min_count": 2}), 7),
                ("training_compliant", "Compliance Training", 0, 1, 5, _tjson.dumps({"certificates": ["AML Training", "GDPR Training"]}), 8),
            ]),
            ("logistics", "Logistics & Warehouse", "Warehouse, delivery, distribution, and logistics operations", "Cleared", 85.0, 0, [
                ("identity_verified", "Identity Verification", 1, 1, 25, _tjson.dumps({"provider": "onfido"}), 1),
                ("right_to_work_valid", "Right to Work", 1, 1, 25, _tjson.dumps({"requires_imposter_check": False}), 2),
                ("dbs_valid", "DBS Check", 1, 1, 15, _tjson.dumps({"level": "basic"}), 3),
                ("registration_active", "Registration", 0, 0, 0, _tjson.dumps({}), 4),
                ("cv_validated", "CV Validation", 0, 1, 5, _tjson.dumps({}), 5),
                ("employment_verified", "Employment Verification", 0, 1, 10, _tjson.dumps({}), 6),
                ("references_verified", "References", 1, 1, 10, _tjson.dumps({"min_count": 1}), 7),
                ("training_compliant", "Safety Training", 0, 1, 10, _tjson.dumps({"certificates": ["Manual Handling", "Health & Safety"]}), 8),
            ]),
            ("retail_hospitality", "Retail & Hospitality", "Shops, restaurants, hotels, and hospitality venues", "Cleared", 80.0, 0, [
                ("identity_verified", "Identity Verification", 1, 1, 30, _tjson.dumps({"provider": "onfido"}), 1),
                ("right_to_work_valid", "Right to Work", 1, 1, 30, _tjson.dumps({"requires_imposter_check": False}), 2),
                ("dbs_valid", "DBS Check", 0, 0, 0, _tjson.dumps({"level": "none"}), 3),
                ("registration_active", "Registration", 0, 0, 0, _tjson.dumps({}), 4),
                ("cv_validated", "CV Validation", 0, 1, 5, _tjson.dumps({}), 5),
                ("employment_verified", "Employment Verification", 0, 1, 10, _tjson.dumps({}), 6),
                ("references_verified", "References", 1, 1, 15, _tjson.dumps({"min_count": 1}), 7),
                ("training_compliant", "Training", 0, 1, 10, _tjson.dumps({"certificates": ["Food Hygiene", "Health & Safety"]}), 8),
            ]),
        ]
        for tkey, tname, tdesc, tlabel, tthresh, tdefault, tchecks in _templates:
            tid = _tid()
            cursor.execute(
                """INSERT INTO industry_templates (id, name, description, compliance_label, compliance_threshold, is_default, is_active)
                   VALUES (%s, %s, %s, %s, %s, %s, 1)""",
                (tid, tname, tdesc, tlabel, tthresh, tdefault),
            )
            for ck, cl, creq, cen, cw, ccfg, csort in tchecks:
                cursor.execute(
                    """INSERT INTO industry_template_checks (id, template_id, check_key, check_label, is_required, is_enabled, weight, config, sort_order)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (_tid(), tid, ck, cl, creq, cen, cw, ccfg, csort),
                )

    # Seed expanded pricing elements if not present
    existing_pricing_types = set()
    if _table_exists(cursor, "pricing_settings"):
        cursor.execute("SELECT check_type FROM pricing_settings")
        existing_pricing_types = {row["check_type"] for row in cursor.fetchall()}
    expanded_pricing = [
        ("standard_dbs", "Standard DBS Check", 18.0, 45.0),
        ("enhanced_dbs", "Enhanced DBS Check (no barred)", 38.0, 65.0),
        ("enhanced_barred_dbs", "Enhanced DBS + Barred List", 49.0, 85.0),
        ("basic_dbs", "Basic DBS Check", 18.0, 35.0),
        ("dbs_update_service", "DBS Update Service Check", 1.0, 15.0),
        ("training_verification", "Training Certificate Verification", 1.0, 8.0),
        ("imposter_check", "Imposter Check (in-person/video)", 0.0, 5.0),
    ]
    for ct, lbl, cost, sell in expanded_pricing:
        from app.utils.auth import generate_id as _pid
        cursor.execute(
            "INSERT INTO pricing_settings (id, check_type, label, cost_price, sell_price) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (check_type) DO NOTHING",
            (_pid(), ct, lbl, cost, sell),
        )

    # Create imposter_declarations table if it doesn't exist (migration for existing DBs)
    if not _table_exists(cursor, "imposter_declarations"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS imposter_declarations (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            agency_id TEXT NOT NULL,
            declared_by_user_id TEXT NOT NULL,
            declared_by_email TEXT NOT NULL,
            declaration_text TEXT NOT NULL,
            documents_verified TEXT,
            ip_address TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id),
            FOREIGN KEY (agency_id) REFERENCES agencies(id)
        )""")

    # Create lead generation tables if they don't exist
    if not _table_exists(cursor, "scrape_jobs"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS scrape_jobs (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            industry TEXT,
            industry_slug TEXT,
            config TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            started_at TEXT,
            completed_at TEXT,
            results_count INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TEXT DEFAULT (NOW()::text)
        )""")
    if not _table_exists(cursor, "leads"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            scrape_job_id TEXT,
            source TEXT NOT NULL,
            industry TEXT,
            industry_slug TEXT,
            agency_name TEXT NOT NULL,
            description TEXT,
            website TEXT,
            email TEXT,
            phone TEXT,
            location TEXT,
            coverage TEXT,
            employment_types TEXT,
            salary_range TEXT,
            source_url TEXT,
            verified INTEGER DEFAULT 0,
            social_links TEXT DEFAULT '{}',
            extra TEXT DEFAULT '{}',
            status TEXT DEFAULT 'new',
            notes TEXT,
            scraped_at TEXT DEFAULT (NOW()::text),
            created_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (scrape_job_id) REFERENCES scrape_jobs(id)
        )""")

    # Create registration_scrape_results table for real professional register scraping
    if not _table_exists(cursor, "registration_scrape_results"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS registration_scrape_results (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            registration_check_id TEXT,
            body TEXT NOT NULL,
            registration_number TEXT NOT NULL,
            scrape_source TEXT NOT NULL,
            registrant_name TEXT,
            registration_status TEXT,
            expiry_date TEXT,
            sanctions TEXT DEFAULT '[]',
            conditions TEXT DEFAULT '[]',
            raw_data TEXT DEFAULT '{}',
            scraped_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        )""")

    # Create industry_plan_links table (Option A: Industry-Specific Plans)
    if not _table_exists(cursor, "industry_plan_links"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS industry_plan_links (
            id TEXT PRIMARY KEY,
            tier_key TEXT NOT NULL,
            industry_template_id TEXT NOT NULL,
            custom_monthly_price REAL,
            custom_per_worker_price REAL,
            custom_monthly_checks INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (industry_template_id) REFERENCES industry_templates(id),
            UNIQUE(tier_key, industry_template_id)
        )""")

    # Create industry_check_pricing table (Option C: Per-Element Industry Pricing)
    if not _table_exists(cursor, "industry_check_pricing"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS industry_check_pricing (
            id TEXT PRIMARY KEY,
            industry_template_id TEXT NOT NULL,
            check_type TEXT NOT NULL,
            label TEXT,
            credit_value REAL DEFAULT 1.0,
            third_party_cost REAL DEFAULT 0,
            sell_price REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (industry_template_id) REFERENCES industry_templates(id),
            UNIQUE(industry_template_id, check_type)
        )""")

    # Add industry_template_id column to subscription_tier_config if missing
    _add_column_if_missing(cursor, "subscription_tier_config", "industry_template_id", "TEXT")
    _add_column_if_missing(cursor, "subscription_tier_config", "industry_name", "TEXT")

    # Add industry_template_id column to agency_subscriptions if missing
    _add_column_if_missing(cursor, "agency_subscriptions", "industry_template_id", "TEXT")
    _add_column_if_missing(cursor, "agency_subscriptions", "credits_total", "REAL DEFAULT 0")
    _add_column_if_missing(cursor, "agency_subscriptions", "credits_used", "REAL DEFAULT 0")
    _add_column_if_missing(cursor, "agency_subscriptions", "rollover_credits", "REAL DEFAULT 0")
    _add_column_if_missing(cursor, "agency_subscriptions", "allow_rollover", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "agency_subscriptions", "overage_rate", "REAL DEFAULT 0")
    _add_column_if_missing(cursor, "agency_subscriptions", "expires_at", "TEXT")
    _add_column_if_missing(cursor, "agency_subscriptions", "auto_topup", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "agency_subscriptions", "auto_topup_tier", "TEXT")
    _add_column_if_missing(cursor, "agency_subscriptions", "pack_name", "TEXT")

    # Create email_templates table if it doesn't exist
    if not _table_exists(cursor, "email_templates"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS email_templates (
            id TEXT PRIMARY KEY,
            template_key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            subject TEXT NOT NULL,
            body_html TEXT NOT NULL,
            body_text TEXT,
            category TEXT DEFAULT 'general',
            variables TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (NOW()::text),
            updated_at TEXT DEFAULT (NOW()::text)
        )""")

    # Create email_send_log table if it doesn't exist
    if not _table_exists(cursor, "email_send_log"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS email_send_log (
            id TEXT PRIMARY KEY,
            template_key TEXT,
            recipient_email TEXT NOT NULL,
            recipient_name TEXT,
            subject TEXT NOT NULL,
            body_rendered TEXT,
            status TEXT DEFAULT 'queued',
            provider TEXT DEFAULT 'sendgrid',
            provider_message_id TEXT,
            error_message TEXT,
            variables_used TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            sent_at TEXT
        )""")

    # Create email_rules table if it doesn't exist
    if not _table_exists(cursor, "email_rules"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS email_rules (
            id TEXT PRIMARY KEY,
            action_trigger TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            template_key TEXT NOT NULL,
            recipient_type TEXT DEFAULT 'primary',
            conditions TEXT DEFAULT '{}',
            priority INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (NOW()::text),
            updated_at TEXT DEFAULT (NOW()::text)
        )""")

    # Create system_settings table for admin-configurable settings (email provider, API keys, etc.)
    if not _table_exists(cursor, "system_settings"):
        cursor.execute("""CREATE TABLE IF NOT EXISTS system_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT,
            updated_at TEXT DEFAULT (NOW()::text)
        )""")

    # Add verification_code column to employment_verifications
    _add_column_if_missing(cursor, "employment_verifications", "verification_code", "TEXT")

    # Add verification_code column to references_
    _add_column_if_missing(cursor, "references_", "verification_code", "TEXT")

    # ── 1.4 Auth & Security Hardening ──────────────────────────────────────────
    # Create admin_users table (replaces hardcoded admin login)
    cursor.execute("""CREATE TABLE IF NOT EXISTS admin_users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        display_name TEXT NOT NULL,
        role TEXT DEFAULT 'admin',
        is_active INTEGER DEFAULT 1,
        failed_login_attempts INTEGER DEFAULT 0,
        locked_until TEXT,
        last_login_at TEXT,
        created_at TEXT DEFAULT (NOW()::text),
        updated_at TEXT
    )""")

    # Create login_attempts table for account lockout tracking
    cursor.execute("""CREATE TABLE IF NOT EXISTS login_attempts (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        user_type TEXT NOT NULL,
        ip_address TEXT,
        success INTEGER NOT NULL,
        created_at TEXT DEFAULT (NOW()::text)
    )""")

    # Create password_reset_tokens table
    cursor.execute("""CREATE TABLE IF NOT EXISTS password_reset_tokens (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        user_type TEXT NOT NULL,
        token_hash TEXT UNIQUE NOT NULL,
        expires_at TEXT NOT NULL,
        used_at TEXT,
        created_at TEXT DEFAULT (NOW()::text)
    )""")

    # Create token_blacklist table for revoked JWT tokens
    cursor.execute("""CREATE TABLE IF NOT EXISTS token_blacklist (
        id TEXT PRIMARY KEY,
        token_jti TEXT UNIQUE NOT NULL,
        user_id TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        revoked_at TEXT DEFAULT (NOW()::text)
    )""")

    # Add failed_login_attempts and locked_until to agencies
    _add_column_if_missing(cursor, "agencies", "failed_login_attempts", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "agencies", "locked_until", "TEXT")
    _add_column_if_missing(cursor, "agencies", "last_login_at", "TEXT")

    # Add failed_login_attempts and locked_until to candidates
    _add_column_if_missing(cursor, "candidates", "failed_login_attempts", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "candidates", "locked_until", "TEXT")
    _add_column_if_missing(cursor, "candidates", "last_login_at", "TEXT")

    # ── 2.3 Candidate Pre-Notification ─────────────────────────────────────────
    # Create candidate_pre_notifications table
    cursor.execute("""CREATE TABLE IF NOT EXISTS candidate_pre_notifications (
        id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        verification_type TEXT NOT NULL,
        verifier_name TEXT NOT NULL,
        verifier_email TEXT NOT NULL,
        verifier_organisation TEXT,
        status TEXT DEFAULT 'pending',
        sent_at TEXT,
        candidate_confirmed_at TEXT,
        verification_request_id TEXT,
        created_at TEXT DEFAULT (NOW()::text),
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    )""")

    # ── 3.4 Audit Trail (tamper-evident hash chain) ──────────────────────────────
    cursor.execute("""CREATE TABLE IF NOT EXISTS audit_trail (
        id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        actor TEXT NOT NULL,
        actor_type TEXT DEFAULT 'user',
        details TEXT,
        ip_address TEXT,
        prev_hash TEXT,
        chain_hash TEXT NOT NULL,
        created_at TEXT DEFAULT (NOW()::text)
    )""")

    # Data access log for GDPR SAR compliance
    cursor.execute("""CREATE TABLE IF NOT EXISTS data_access_log (
        id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        accessor TEXT NOT NULL,
        accessor_type TEXT DEFAULT 'user',
        purpose TEXT,
        ip_address TEXT,
        created_at TEXT DEFAULT (NOW()::text)
    )""")

    # ── 3.3 Webhook delivery enhancements ──────────────────────────────────────
    # Add next_retry_at column to webhook_deliveries if not present
    _add_column_if_missing(cursor, "webhook_deliveries", "next_retry_at", "TEXT")

    # ── 3.5 Background Jobs (enhanced) ─────────────────────────────────────────
    cursor.execute("""CREATE TABLE IF NOT EXISTS background_jobs (
        id TEXT PRIMARY KEY,
        task_name TEXT NOT NULL,
        args TEXT DEFAULT '[]',
        kwargs TEXT DEFAULT '{}',
        status TEXT DEFAULT 'queued',
        priority INTEGER DEFAULT 5,
        timeout_seconds INTEGER DEFAULT 180,
        max_retries INTEGER DEFAULT 3,
        attempt INTEGER DEFAULT 0,
        celery_task_id TEXT,
        result TEXT,
        error TEXT,
        scheduled_at TEXT,
        started_at TEXT,
        completed_at TEXT,
        created_at TEXT DEFAULT (NOW()::text)
    )""")

    # ── 3.2 Scheduled reports ──────────────────────────────────────────────────
    cursor.execute("""CREATE TABLE IF NOT EXISTS scheduled_reports (
        id TEXT PRIMARY KEY,
        agency_id TEXT NOT NULL,
        report_type TEXT NOT NULL,
        frequency TEXT DEFAULT 'weekly',
        recipients TEXT DEFAULT '[]',
        last_sent_at TEXT,
        next_send_at TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (NOW()::text),
        FOREIGN KEY (agency_id) REFERENCES agencies(id)
    )""")

    # ── 1.2 Payment Provider Configuration ─────────────────────────────────────
    cursor.execute("""CREATE TABLE IF NOT EXISTS payment_provider_config (
        id TEXT PRIMARY KEY,
        provider TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        is_enabled INTEGER DEFAULT 0,
        api_key_set INTEGER DEFAULT 0,
        api_key_encrypted TEXT,
        api_secret_encrypted TEXT,
        webhook_secret TEXT,
        environment TEXT DEFAULT 'sandbox',
        account_id TEXT,
        account_name TEXT,
        currency TEXT DEFAULT 'GBP',
        config_json TEXT DEFAULT '{}',
        last_tested_at TEXT,
        test_status TEXT,
        connected_at TEXT,
        updated_at TEXT DEFAULT (NOW()::text)
    )""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS payment_routing (
        id TEXT PRIMARY KEY,
        payment_type TEXT NOT NULL UNIQUE,
        label TEXT NOT NULL,
        provider TEXT,
        fallback_provider TEXT,
        is_enabled INTEGER DEFAULT 1,
        description TEXT,
        updated_at TEXT DEFAULT (NOW()::text)
    )""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS payment_transactions (
        id TEXT PRIMARY KEY,
        agency_id TEXT NOT NULL,
        invoice_id TEXT,
        provider TEXT NOT NULL,
        payment_type TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'GBP',
        status TEXT DEFAULT 'pending',
        provider_payment_id TEXT,
        provider_customer_id TEXT,
        provider_session_url TEXT,
        error_message TEXT,
        metadata_json TEXT DEFAULT '{}',
        created_at TEXT DEFAULT (NOW()::text),
        completed_at TEXT,
        FOREIGN KEY (agency_id) REFERENCES agencies(id)
    )""")

    # Seed default payment routing if empty
    cursor.execute("SELECT COUNT(*) AS cnt FROM payment_routing")
    routing_count = cursor.fetchone()["cnt"]
    if routing_count == 0:
        from app.utils.auth import generate_id as _gen_id
        default_routes = [
            ("credit_pack_purchase", "Credit Pack Purchases", "Card payments for credit pack top-ups"),
            ("payg_invoice", "Pay-As-You-Go Invoices", "One-off invoice payments for individual checks"),
            ("subscription_recurring", "Recurring Subscriptions", "Automatic monthly/annual subscription billing"),
            ("direct_debit", "Direct Debit Collections", "Recurring direct debit mandate payments"),
            ("refund", "Refunds", "Refund processing back to original payment method"),
        ]
        for ptype, label, desc in default_routes:
            cursor.execute(
                """INSERT INTO payment_routing (id, payment_type, label, description)
                   VALUES (%s, %s, %s, %s)""",
                (_gen_id(), ptype, label, desc),
            )

    # Seed default provider entries if empty
    cursor.execute("SELECT COUNT(*) AS cnt FROM payment_provider_config")
    ppc_count = cursor.fetchone()["cnt"]
    if ppc_count == 0:
        from app.utils.auth import generate_id as _gen_id2
        for provider, name in [("stripe", "Stripe"), ("gocardless", "GoCardless")]:
            cursor.execute(
                """INSERT INTO payment_provider_config (id, provider, display_name)
                   VALUES (%s, %s, %s)""",
                (_gen_id2(), provider, name),
            )

    # ── TrustID Check Tables ──────────────────────────────────────────────────
    cursor.execute("""CREATE TABLE IF NOT EXISTS trustid_config (
        id TEXT PRIMARY KEY,
        check_type TEXT UNIQUE NOT NULL,
        label TEXT NOT NULL,
        submission_mode TEXT DEFAULT 'manual',
        api_key TEXT,
        api_secret TEXT,
        environment TEXT DEFAULT 'production',
        updated_at TEXT DEFAULT (NOW()::text)
    )""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS trustid_checks (
        id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        check_type TEXT NOT NULL,
        submission_mode TEXT DEFAULT 'manual',
        status TEXT DEFAULT 'pending_admin',
        result TEXT,
        candidate_name TEXT,
        candidate_email TEXT,
        candidate_dob TEXT,
        trustid_reference TEXT,
        report_document_id TEXT,
        submitted_by TEXT,
        admin_submitted_by TEXT,
        admin_submitted_at TEXT,
        admin_completed_by TEXT,
        admin_notes TEXT,
        notes TEXT,
        raw_response TEXT,
        created_at TEXT DEFAULT (NOW()::text),
        updated_at TEXT DEFAULT (NOW()::text),
        completed_at TEXT,
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    )""")

    # Seed default TrustID config if empty
    tid_count = 0
    if _table_exists(cursor, "trustid_config"):
        cursor.execute("SELECT COUNT(*) AS cnt FROM trustid_config")
        tid_count = cursor.fetchone()["cnt"]
    if tid_count == 0:
        from app.utils.auth import generate_id as _tid_gen
        for ct, label in [
            ("identity_verification", "Identity Verification"),
            ("dbs_check", "DBS Check"),
            ("right_to_work", "Right to Work"),
        ]:
            cursor.execute(
                """INSERT INTO trustid_config (id, check_type, label, submission_mode)
                   VALUES (%s, %s, %s, 'manual')""",
                (_tid_gen(), ct, label),
            )

    # Create sms_notifications table if it doesn't exist
    cursor.execute("""CREATE TABLE IF NOT EXISTS sms_notifications (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        user_type TEXT,
        to_number TEXT NOT NULL,
        message TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        reference_id TEXT,
        provider TEXT DEFAULT 'console',
        status TEXT DEFAULT 'pending',
        provider_response TEXT,
        created_at TEXT DEFAULT (NOW()::text)
    )""")

    # Migrate admin email from old healthvet.ai domain to viperai.io
    cursor.execute("UPDATE admin_users SET email = REPLACE(email, '@healthvet.ai', '@viperai.io') WHERE email LIKE '%@healthvet.ai'")

    # Seed default admin user if admin_users table is empty
    cursor.execute("SELECT COUNT(*) AS cnt FROM admin_users")
    admin_count = cursor.fetchone()["cnt"]
    if admin_count == 0:
        import os
        from app.utils.auth import generate_id, hash_password
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@viperai.io")
        admin_pw = os.environ.get("ADMIN_PASSWORD", "Password123!")
        cursor.execute(
            """INSERT INTO admin_users (id, email, password_hash, display_name, role)
               VALUES (%s, %s, %s, %s, %s)""",
            (generate_id(), admin_email, hash_password(admin_pw),
             "System Administrator", "super_admin"),
        )

    conn.commit()
    _return_connection(conn)


def init_db():
    """Initialize database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            phone TEXT,
            date_of_birth TEXT,
            address_line1 TEXT,
            address_line2 TEXT,
            city TEXT,
            postcode TEXT,
            country TEXT DEFAULT 'GB',
            profession TEXT,
            registration_number TEXT,
            registration_body TEXT,
            status TEXT DEFAULT 'pending',
            compliance_score REAL DEFAULT 0.0,
            compliance_status TEXT DEFAULT 'incomplete',
            created_at TEXT DEFAULT (NOW()::text),
            updated_at TEXT DEFAULT (NOW()::text)
        );

        CREATE TABLE IF NOT EXISTS agencies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            contact_name TEXT,
            phone TEXT,
            plan TEXT DEFAULT 'standard',
            monthly_fee REAL DEFAULT 300.0,
            status TEXT DEFAULT 'active',
            discount_percent REAL DEFAULT 0,
            billing_mode TEXT DEFAULT 'manual_invoicing',
            stripe_customer_id TEXT,
            industry_template_id TEXT,
            created_at TEXT DEFAULT (NOW()::text)
        );

        CREATE TABLE IF NOT EXISTS agency_candidates (
            agency_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            assigned_at TEXT DEFAULT (NOW()::text),
            employment_status TEXT DEFAULT 'vetting',
            employment_status_updated_at TEXT,
            PRIMARY KEY (agency_id, candidate_id),
            FOREIGN KEY (agency_id) REFERENCES agencies(id),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS identity_checks (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            provider TEXT DEFAULT 'onfido',
            status TEXT DEFAULT 'pending',
            document_type TEXT,
            document_authenticity TEXT,
            facial_match_score REAL,
            liveness_check TEXT,
            address_verified INTEGER DEFAULT 0,
            result TEXT,
            details TEXT,
            started_at TEXT DEFAULT (NOW()::text),
            completed_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS right_to_work_checks (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            share_code TEXT,
            verification_method TEXT DEFAULT 'share_code',
            nationality TEXT,
            document_type TEXT,
            document_reference TEXT,
            ni_number TEXT,
            status TEXT DEFAULT 'pending',
            visa_type TEXT,
            visa_expiry TEXT,
            work_restrictions TEXT,
            verified INTEGER DEFAULT 0,
            result TEXT,
            details TEXT,
            checked_at TEXT DEFAULT (NOW()::text),
            next_check_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS dbs_checks (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            provider TEXT DEFAULT 'ucheck',
            check_type TEXT DEFAULT 'enhanced',
            status TEXT DEFAULT 'pending',
            application_ref TEXT,
            certificate_number TEXT,
            issue_date TEXT,
            result TEXT,
            details TEXT,
            update_service_registered INTEGER DEFAULT 0,
            next_renewal TEXT,
            submitted_at TEXT DEFAULT (NOW()::text),
            completed_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS cv_analyses (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            cv_text TEXT,
            cv_file_name TEXT,
            gap_analysis TEXT,
            overlap_detection TEXT,
            qualification_flags TEXT,
            fraud_risk_score REAL DEFAULT 0.0,
            inconsistencies TEXT,
            ai_summary TEXT,
            employment_entries TEXT,
            status TEXT DEFAULT 'pending',
            analysed_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS registration_checks (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            body TEXT NOT NULL,
            registration_number TEXT,
            status TEXT DEFAULT 'pending',
            is_active INTEGER,
            sanctions TEXT,
            conditions TEXT,
            last_checked TEXT DEFAULT (NOW()::text),
            next_check TEXT,
            result TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS references_ (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            referee_name TEXT NOT NULL,
            referee_email TEXT NOT NULL,
            referee_phone TEXT,
            referee_organisation TEXT,
            referee_job_title TEXT,
            relationship TEXT,
            token TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            responses TEXT,
            sentiment_score REAL,
            fraud_flags TEXT,
            ip_address TEXT,
            domain_verified INTEGER DEFAULT 0,
            reminder_count INTEGER DEFAULT 0,
            sent_at TEXT DEFAULT (NOW()::text),
            completed_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS compliance_records (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            overall_status TEXT DEFAULT 'incomplete',
            score REAL DEFAULT 0.0,
            identity_verified INTEGER DEFAULT 0,
            right_to_work_valid INTEGER DEFAULT 0,
            dbs_valid INTEGER DEFAULT 0,
            registration_active INTEGER DEFAULT 0,
            references_verified INTEGER DEFAULT 0,
            cv_validated INTEGER DEFAULT 0,
            employment_verified INTEGER DEFAULT 0,
            training_compliant INTEGER DEFAULT 0,
            flags TEXT,
            audit_log TEXT,
            last_evaluated TEXT DEFAULT (NOW()::text),
            cqc_ready INTEGER DEFAULT 0,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS monitoring_alerts (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            message TEXT NOT NULL,
            details TEXT,
            is_read INTEGER DEFAULT 0,
            is_resolved INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (NOW()::text),
            resolved_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS webhook_events (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT,
            status TEXT DEFAULT 'received',
            processed_at TEXT,
            created_at TEXT DEFAULT (NOW()::text)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action TEXT NOT NULL,
            actor TEXT,
            details TEXT,
            created_at TEXT DEFAULT (NOW()::text)
        );

        CREATE TABLE IF NOT EXISTS employment_history (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            cv_analysis_id TEXT,
            employer_name TEXT NOT NULL,
            job_title TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            is_current INTEGER DEFAULT 0,
            reason_for_leaving TEXT,
            duties TEXT,
            verifier_name TEXT,
            verifier_email TEXT,
            verifier_job_title TEXT,
            source TEXT DEFAULT 'cv_extracted',
            created_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS employment_verifications (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            employment_id TEXT NOT NULL,
            verifier_name TEXT NOT NULL,
            verifier_email TEXT NOT NULL,
            verifier_job_title TEXT,
            employer_name TEXT,
            token TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            job_title_confirmed INTEGER,
            dates_confirmed INTEGER,
            reason_for_leaving_confirmed TEXT,
            additional_comments TEXT,
            fraud_flags TEXT,
            ip_address TEXT,
            domain_verified INTEGER DEFAULT 0,
            reminder_count INTEGER DEFAULT 0,
            sent_at TEXT DEFAULT (NOW()::text),
            completed_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id),
            FOREIGN KEY (employment_id) REFERENCES employment_history(id)
        );

        CREATE TABLE IF NOT EXISTS agency_invites (
            id TEXT PRIMARY KEY,
            agency_id TEXT NOT NULL,
            candidate_email TEXT NOT NULL,
            invite_code TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'pending',
            candidate_id TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            accepted_at TEXT,
            FOREIGN KEY (agency_id) REFERENCES agencies(id),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS pricing_settings (
            id TEXT PRIMARY KEY,
            check_type TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            cost_price REAL DEFAULT 0.0,
            sell_price REAL DEFAULT 0.0,
            updated_at TEXT DEFAULT (NOW()::text)
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            agency_id TEXT NOT NULL,
            candidate_id TEXT,
            check_type TEXT,
            description TEXT,
            cost_amount REAL DEFAULT 0.0,
            sell_amount REAL DEFAULT 0.0,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (NOW()::text),
            paid_at TEXT,
            FOREIGN KEY (agency_id) REFERENCES agencies(id)
        );

        CREATE TABLE IF NOT EXISTS email_notifications (
            id TEXT PRIMARY KEY,
            recipient_email TEXT NOT NULL,
            recipient_name TEXT,
            subject TEXT NOT NULL,
            body TEXT,
            notification_type TEXT,
            related_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (NOW()::text)
        );

        CREATE TABLE IF NOT EXISTS training_certificates (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            certificate_name TEXT NOT NULL,
            category TEXT DEFAULT 'mandatory',
            provider TEXT,
            issue_date TEXT,
            expiry_date TEXT,
            certificate_ref TEXT,
            file_name TEXT,
            status TEXT DEFAULT 'valid',
            created_at TEXT DEFAULT (NOW()::text),
            updated_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS fraud_flags (
            id TEXT PRIMARY KEY,
            candidate_id TEXT,
            flag_type TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            message TEXT NOT NULL,
            details TEXT,
            is_resolved INTEGER DEFAULT 0,
            resolved_by TEXT,
            resolved_at TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS alert_settings (
            id TEXT PRIMARY KEY,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value INTEGER NOT NULL,
            updated_at TEXT DEFAULT (NOW()::text)
        );

        CREATE TABLE IF NOT EXISTS agency_subscriptions (
            id TEXT PRIMARY KEY,
            agency_id TEXT NOT NULL,
            tier TEXT NOT NULL,
            billing_method TEXT DEFAULT 'stripe',
            monthly_amount REAL DEFAULT 0.0,
            per_worker_amount REAL DEFAULT 0.0,
            max_workers INTEGER DEFAULT 50,
            monthly_checks INTEGER DEFAULT 0,
            checks_used INTEGER DEFAULT 0,
            stripe_payment_method_id TEXT,
            stripe_subscription_id TEXT,
            status TEXT DEFAULT 'active',
            current_period_start TEXT,
            current_period_end TEXT,
            next_billing_date TEXT,
            cancelled_at TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (agency_id) REFERENCES agencies(id)
        );

        CREATE TABLE IF NOT EXISTS candidate_submissions (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            submission_type TEXT DEFAULT 'full',
            sections_requested TEXT,
            status TEXT DEFAULT 'draft',
            consent_given INTEGER DEFAULT 0,
            consent_timestamp TEXT,
            consent_ip_address TEXT,
            privacy_policy_version TEXT DEFAULT '1.0',
            terms_version TEXT DEFAULT '1.0',
            submitted_at TEXT,
            processing_started_at TEXT,
            processing_completed_at TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS candidate_draft_data (
            id TEXT PRIMARY KEY,
            submission_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            section TEXT NOT NULL,
            data TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (submission_id) REFERENCES candidate_submissions(id)
        );

        CREATE TABLE IF NOT EXISTS consent_logs (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            submission_id TEXT,
            consent_type TEXT NOT NULL,
            consent_given INTEGER NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            privacy_policy_version TEXT,
            terms_version TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS revet_requests (
            id TEXT PRIMARY KEY,
            agency_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            sections TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'pending',
            submission_id TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            completed_at TEXT,
            FOREIGN KEY (agency_id) REFERENCES agencies(id),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS subscription_tier_config (
            id TEXT PRIMARY KEY,
            tier_key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            monthly_price REAL DEFAULT 0,
            per_worker_price REAL DEFAULT 0,
            max_workers INTEGER DEFAULT 0,
            monthly_checks INTEGER DEFAULT 0,
            overage_rate REAL DEFAULT 0,
            allow_rollover INTEGER DEFAULT 0,
            monitoring_included INTEGER DEFAULT 0,
            monitoring_cap INTEGER DEFAULT 0,
            monitoring_addon_rate REAL DEFAULT 0,
            features TEXT DEFAULT '[]',
            is_active INTEGER DEFAULT 1,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS partial_credit_rates (
            id TEXT PRIMARY KEY,
            check_type TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            credit_value REAL DEFAULT 1.0,
            third_party_cost REAL DEFAULT 0,
            updated_at TEXT DEFAULT (NOW()::text)
        );

        CREATE TABLE IF NOT EXISTS imposter_declarations (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            agency_id TEXT NOT NULL,
            declared_by_user_id TEXT NOT NULL,
            declared_by_email TEXT NOT NULL,
            declaration_text TEXT NOT NULL,
            documents_verified TEXT,
            ip_address TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id),
            FOREIGN KEY (agency_id) REFERENCES agencies(id)
        );

        CREATE TABLE IF NOT EXISTS credit_transactions (
            id TEXT PRIMARY KEY,
            agency_id TEXT NOT NULL,
            candidate_id TEXT,
            order_id TEXT,
            check_type TEXT NOT NULL,
            credits_consumed REAL DEFAULT 0,
            credit_balance_after REAL DEFAULT 0,
            unit_cost REAL DEFAULT 0,
            charge_amount REAL DEFAULT 0,
            is_overage INTEGER DEFAULT 0,
            is_rollover INTEGER DEFAULT 0,
            description TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (agency_id) REFERENCES agencies(id)
        );

        -- GDPR tables
        CREATE TABLE IF NOT EXISTS gdpr_erasure_requests (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (NOW()::text),
            completed_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS gdpr_dpias (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            data_types TEXT NOT NULL,
            processing_purpose TEXT NOT NULL,
            risk_level TEXT DEFAULT 'medium',
            mitigations TEXT,
            status TEXT DEFAULT 'draft',
            created_by TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS gdpr_retention_policies (
            id TEXT PRIMARY KEY,
            data_category TEXT UNIQUE NOT NULL,
            retention_period_days INTEGER NOT NULL,
            legal_basis TEXT NOT NULL,
            description TEXT,
            auto_delete INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (NOW()::text),
            updated_at TEXT
        );

        -- API keys for external integrations
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            agency_id TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            key_prefix TEXT NOT NULL,
            name TEXT NOT NULL,
            scopes TEXT DEFAULT '[]',
            is_active INTEGER DEFAULT 1,
            last_used_at TEXT,
            expires_at TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (agency_id) REFERENCES agencies(id)
        );

        -- Webhook subscriptions for agency HR integrations
        CREATE TABLE IF NOT EXISTS webhook_subscriptions (
            id TEXT PRIMARY KEY,
            agency_id TEXT NOT NULL,
            url TEXT NOT NULL,
            secret TEXT NOT NULL,
            events TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            failure_count INTEGER DEFAULT 0,
            last_triggered_at TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (agency_id) REFERENCES agencies(id)
        );

        -- Webhook delivery log
        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            id TEXT PRIMARY KEY,
            subscription_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            response_status INTEGER,
            response_body TEXT,
            attempt INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            next_retry_at TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            delivered_at TEXT,
            FOREIGN KEY (subscription_id) REFERENCES webhook_subscriptions(id)
        );

        -- Celery-compatible task results (optional, for tracking)
        CREATE TABLE IF NOT EXISTS background_tasks (
            id TEXT PRIMARY KEY,
            task_name TEXT NOT NULL,
            args TEXT,
            status TEXT DEFAULT 'pending',
            result TEXT,
            error TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            started_at TEXT,
            completed_at TEXT
        );

        -- In-App Notifications
        CREATE TABLE IF NOT EXISTS in_app_notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            user_type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            severity TEXT DEFAULT 'info',
            link TEXT,
            metadata TEXT,
            is_read INTEGER DEFAULT 0,
            read_at TEXT,
            created_at TEXT DEFAULT (NOW()::text)
        );

        -- Agency Sub-Accounts
        CREATE TABLE IF NOT EXISTS agency_sub_accounts (
            id TEXT PRIMARY KEY,
            agency_id TEXT NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            role TEXT DEFAULT 'recruiter',
            industry_template_id TEXT,
            is_active INTEGER DEFAULT 1,
            last_login_at TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (agency_id) REFERENCES agencies(id)
        );

        -- Industry Templates
        CREATE TABLE IF NOT EXISTS industry_templates (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            compliance_label TEXT DEFAULT 'Compliant',
            compliance_threshold REAL DEFAULT 95.0,
            is_default INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (NOW()::text),
            updated_at TEXT
        );

        -- Industry Template Checks — configurable checks per industry
        CREATE TABLE IF NOT EXISTS industry_template_checks (
            id TEXT PRIMARY KEY,
            template_id TEXT NOT NULL,
            check_key TEXT NOT NULL,
            check_label TEXT NOT NULL,
            is_required INTEGER DEFAULT 1,
            is_enabled INTEGER DEFAULT 1,
            weight REAL DEFAULT 10.0,
            config TEXT DEFAULT '{}',
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (template_id) REFERENCES industry_templates(id),
            UNIQUE(template_id, check_key)
        );

        -- Lead Generation: Scrape Jobs
        CREATE TABLE IF NOT EXISTS scrape_jobs (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            industry TEXT,
            industry_slug TEXT,
            config TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            started_at TEXT,
            completed_at TEXT,
            results_count INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TEXT DEFAULT (NOW()::text)
        );

        -- Lead Generation: Leads
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            scrape_job_id TEXT,
            source TEXT NOT NULL,
            industry TEXT,
            industry_slug TEXT,
            agency_name TEXT NOT NULL,
            description TEXT,
            website TEXT,
            email TEXT,
            phone TEXT,
            location TEXT,
            coverage TEXT,
            employment_types TEXT,
            salary_range TEXT,
            source_url TEXT,
            verified INTEGER DEFAULT 0,
            social_links TEXT DEFAULT '{}',
            extra TEXT DEFAULT '{}',
            status TEXT DEFAULT 'new',
            notes TEXT,
            scraped_at TEXT DEFAULT (NOW()::text),
            created_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (scrape_job_id) REFERENCES scrape_jobs(id)
        );

        -- Professional Registration Scrape Results
        CREATE TABLE IF NOT EXISTS registration_scrape_results (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            registration_check_id TEXT,
            body TEXT NOT NULL,
            registration_number TEXT NOT NULL,
            scrape_source TEXT NOT NULL,
            registrant_name TEXT,
            registration_status TEXT,
            expiry_date TEXT,
            sanctions TEXT DEFAULT '[]',
            conditions TEXT DEFAULT '[]',
            raw_data TEXT DEFAULT '{}',
            scraped_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        -- Industry-Specific Plan Links (Option A)
        CREATE TABLE IF NOT EXISTS industry_plan_links (
            id TEXT PRIMARY KEY,
            tier_key TEXT NOT NULL,
            industry_template_id TEXT NOT NULL,
            custom_monthly_price REAL,
            custom_per_worker_price REAL,
            custom_monthly_checks INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (industry_template_id) REFERENCES industry_templates(id),
            UNIQUE(tier_key, industry_template_id)
        );

        -- Per-Element Industry Pricing (Option C)
        CREATE TABLE IF NOT EXISTS industry_check_pricing (
            id TEXT PRIMARY KEY,
            industry_template_id TEXT NOT NULL,
            check_type TEXT NOT NULL,
            label TEXT,
            credit_value REAL DEFAULT 1.0,
            third_party_cost REAL DEFAULT 0,
            sell_price REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (NOW()::text),
            FOREIGN KEY (industry_template_id) REFERENCES industry_templates(id),
            UNIQUE(industry_template_id, check_type)
        );

        -- TrustID Configuration (manual/api mode per check type)
        CREATE TABLE IF NOT EXISTS trustid_config (
            id TEXT PRIMARY KEY,
            check_type TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            submission_mode TEXT DEFAULT 'manual',
            api_key TEXT,
            api_secret TEXT,
            environment TEXT DEFAULT 'production',
            updated_at TEXT DEFAULT (NOW()::text)
        );

        -- TrustID Checks (individual check submissions)
        CREATE TABLE IF NOT EXISTS trustid_checks (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            check_type TEXT NOT NULL,
            submission_mode TEXT DEFAULT 'manual',
            status TEXT DEFAULT 'pending_admin',
            result TEXT,
            candidate_name TEXT,
            candidate_email TEXT,
            candidate_dob TEXT,
            trustid_reference TEXT,
            report_document_id TEXT,
            submitted_by TEXT,
            admin_submitted_by TEXT,
            admin_submitted_at TEXT,
            admin_completed_by TEXT,
            admin_notes TEXT,
            notes TEXT,
            raw_response TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            updated_at TEXT DEFAULT (NOW()::text),
            completed_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );
    """)

    conn.commit()
    _return_connection(conn)
