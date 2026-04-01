import sqlite3
import os
from contextlib import contextmanager

# Use /data/app.db for persistent storage in deployment, local otherwise
DB_PATH = os.environ.get("DATABASE_PATH", "/data/app.db" if os.path.isdir("/data") else "app.db")


def get_db_path():
    return DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def migrate_db():
    """Run database migrations for schema changes."""
    conn = get_connection()
    cursor = conn.cursor()
    # Add new columns to right_to_work_checks if they don't exist
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(right_to_work_checks)").fetchall()}
    new_cols = {
        "verification_method": "TEXT DEFAULT 'share_code'",
        "nationality": "TEXT",
        "document_type": "TEXT",
        "document_reference": "TEXT",
        "ni_number": "TEXT",
    }
    for col, col_type in new_cols.items():
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE right_to_work_checks ADD COLUMN {col} {col_type}")
    # Also create new tables if they don't exist (for existing databases)
    try:
        cursor.execute("SELECT 1 FROM employment_history LIMIT 1")
    except Exception:
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
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        )""")
    try:
        cursor.execute("SELECT 1 FROM employment_verifications LIMIT 1")
    except Exception:
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
            sent_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id),
            FOREIGN KEY (employment_id) REFERENCES employment_history(id)
        )""")
    # Create agency_invites table if it doesn't exist
    try:
        cursor.execute("SELECT 1 FROM agency_invites LIMIT 1")
    except Exception:
        cursor.execute("""CREATE TABLE IF NOT EXISTS agency_invites (
            id TEXT PRIMARY KEY,
            agency_id TEXT NOT NULL,
            candidate_email TEXT NOT NULL,
            invite_code TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'pending',
            candidate_id TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            accepted_at TEXT,
            FOREIGN KEY (agency_id) REFERENCES agencies(id),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        )""")
    # Add employment_status column to agency_candidates if missing
    try:
        existing_ac_cols = {row[1] for row in cursor.execute("PRAGMA table_info(agency_candidates)").fetchall()}
        if "employment_status" not in existing_ac_cols:
            cursor.execute("ALTER TABLE agency_candidates ADD COLUMN employment_status TEXT DEFAULT 'vetting'")
        if "employment_status_updated_at" not in existing_ac_cols:
            cursor.execute("ALTER TABLE agency_candidates ADD COLUMN employment_status_updated_at TEXT")
        if "annual_monitoring" not in existing_ac_cols:
            cursor.execute("ALTER TABLE agency_candidates ADD COLUMN annual_monitoring INTEGER DEFAULT 0")
        if "vetting_cost_accepted" not in existing_ac_cols:
            cursor.execute("ALTER TABLE agency_candidates ADD COLUMN vetting_cost_accepted REAL DEFAULT 0")
        if "monitoring_cost_accepted" not in existing_ac_cols:
            cursor.execute("ALTER TABLE agency_candidates ADD COLUMN monitoring_cost_accepted REAL DEFAULT 0")
    except Exception:
        pass
    # Add include_monitoring and cost columns to agency_invites if missing
    try:
        existing_inv_cols = {row[1] for row in cursor.execute("PRAGMA table_info(agency_invites)").fetchall()}
        if "include_monitoring" not in existing_inv_cols:
            cursor.execute("ALTER TABLE agency_invites ADD COLUMN include_monitoring INTEGER DEFAULT 0")
        if "vetting_cost" not in existing_inv_cols:
            cursor.execute("ALTER TABLE agency_invites ADD COLUMN vetting_cost REAL DEFAULT 0")
        if "monitoring_cost" not in existing_inv_cols:
            cursor.execute("ALTER TABLE agency_invites ADD COLUMN monitoring_cost REAL DEFAULT 0")
    except Exception:
        pass
    # Add discount_percent and billing_mode columns to agencies if missing
    try:
        existing_ag_cols = {row[1] for row in cursor.execute("PRAGMA table_info(agencies)").fetchall()}
        if "discount_percent" not in existing_ag_cols:
            cursor.execute("ALTER TABLE agencies ADD COLUMN discount_percent REAL DEFAULT 0")
        if "billing_mode" not in existing_ag_cols:
            cursor.execute("ALTER TABLE agencies ADD COLUMN billing_mode TEXT DEFAULT 'manual_invoicing'")
        if "stripe_customer_id" not in existing_ag_cols:
            cursor.execute("ALTER TABLE agencies ADD COLUMN stripe_customer_id TEXT")
    except Exception:
        pass
    # Add adjusted_amount, adjustment_notes, payment_method, stripe_session_id columns to invoices if missing
    try:
        existing_inv2_cols = {row[1] for row in cursor.execute("PRAGMA table_info(invoices)").fetchall()}
        if "adjusted_amount" not in existing_inv2_cols:
            cursor.execute("ALTER TABLE invoices ADD COLUMN adjusted_amount REAL")
        if "adjustment_notes" not in existing_inv2_cols:
            cursor.execute("ALTER TABLE invoices ADD COLUMN adjustment_notes TEXT")
        if "candidate_email" not in existing_inv2_cols:
            cursor.execute("ALTER TABLE invoices ADD COLUMN candidate_email TEXT")
        if "payment_method" not in existing_inv2_cols:
            cursor.execute("ALTER TABLE invoices ADD COLUMN payment_method TEXT DEFAULT 'manual'")
        if "stripe_session_id" not in existing_inv2_cols:
            cursor.execute("ALTER TABLE invoices ADD COLUMN stripe_session_id TEXT")
        if "stripe_payment_intent_id" not in existing_inv2_cols:
            cursor.execute("ALTER TABLE invoices ADD COLUMN stripe_payment_intent_id TEXT")
        if "due_date" not in existing_inv2_cols:
            cursor.execute("ALTER TABLE invoices ADD COLUMN due_date TEXT")
        if "reminder_sent_at" not in existing_inv2_cols:
            cursor.execute("ALTER TABLE invoices ADD COLUMN reminder_sent_at TEXT")
        if "reminder_count" not in existing_inv2_cols:
            cursor.execute("ALTER TABLE invoices ADD COLUMN reminder_count INTEGER DEFAULT 0")
    except Exception:
        pass
    # Create pricing_settings table if it doesn't exist
    try:
        cursor.execute("SELECT 1 FROM pricing_settings LIMIT 1")
    except Exception:
        cursor.execute("""CREATE TABLE IF NOT EXISTS pricing_settings (
            id TEXT PRIMARY KEY,
            check_type TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            cost_price REAL DEFAULT 0.0,
            sell_price REAL DEFAULT 0.0,
            updated_at TEXT DEFAULT (datetime('now'))
        )""")
    # Create invoices table if it doesn't exist
    try:
        cursor.execute("SELECT 1 FROM invoices LIMIT 1")
    except Exception:
        cursor.execute("""CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            agency_id TEXT NOT NULL,
            candidate_id TEXT,
            check_type TEXT,
            description TEXT,
            cost_amount REAL DEFAULT 0.0,
            sell_amount REAL DEFAULT 0.0,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            paid_at TEXT,
            FOREIGN KEY (agency_id) REFERENCES agencies(id)
        )""")
    # Add employment_verified column to compliance_records if missing
    try:
        existing_cr_cols = {row[1] for row in cursor.execute("PRAGMA table_info(compliance_records)").fetchall()}
        if "employment_verified" not in existing_cr_cols:
            cursor.execute("ALTER TABLE compliance_records ADD COLUMN employment_verified INTEGER DEFAULT 0")
        if "training_compliant" not in existing_cr_cols:
            cursor.execute("ALTER TABLE compliance_records ADD COLUMN training_compliant INTEGER DEFAULT 0")
    except Exception:
        pass
    # Add cv_file_name column to cv_analyses if missing
    try:
        existing_cv_cols = {row[1] for row in cursor.execute("PRAGMA table_info(cv_analyses)").fetchall()}
        if "cv_file_name" not in existing_cv_cols:
            cursor.execute("ALTER TABLE cv_analyses ADD COLUMN cv_file_name TEXT")
        if "employment_entries" not in existing_cv_cols:
            cursor.execute("ALTER TABLE cv_analyses ADD COLUMN employment_entries TEXT")
    except Exception:
        pass
    # Add monthly_checks and checks_used columns to agency_subscriptions if missing
    try:
        existing_sub_cols = {row[1] for row in cursor.execute("PRAGMA table_info(agency_subscriptions)").fetchall()}
        if "monthly_checks" not in existing_sub_cols:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN monthly_checks INTEGER DEFAULT 0")
        if "checks_used" not in existing_sub_cols:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN checks_used INTEGER DEFAULT 0")
    except Exception:
        pass
    # Add monthly_checks and new columns to subscription_tier_config if missing
    try:
        existing_stc_cols = {row[1] for row in cursor.execute("PRAGMA table_info(subscription_tier_config)").fetchall()}
        if "monthly_checks" not in existing_stc_cols:
            cursor.execute("ALTER TABLE subscription_tier_config ADD COLUMN monthly_checks INTEGER DEFAULT 0")
        if "overage_rate" not in existing_stc_cols:
            cursor.execute("ALTER TABLE subscription_tier_config ADD COLUMN overage_rate REAL DEFAULT 0")
        if "allow_rollover" not in existing_stc_cols:
            cursor.execute("ALTER TABLE subscription_tier_config ADD COLUMN allow_rollover INTEGER DEFAULT 0")
        if "monitoring_included" not in existing_stc_cols:
            cursor.execute("ALTER TABLE subscription_tier_config ADD COLUMN monitoring_included INTEGER DEFAULT 0")
        if "monitoring_cap" not in existing_stc_cols:
            cursor.execute("ALTER TABLE subscription_tier_config ADD COLUMN monitoring_cap INTEGER DEFAULT 0")
        if "monitoring_addon_rate" not in existing_stc_cols:
            cursor.execute("ALTER TABLE subscription_tier_config ADD COLUMN monitoring_addon_rate REAL DEFAULT 0")
        if "is_active" not in existing_stc_cols:
            cursor.execute("ALTER TABLE subscription_tier_config ADD COLUMN is_active INTEGER DEFAULT 1")
    except Exception:
        pass
    # Add rollover and credit columns to agency_subscriptions if missing
    try:
        existing_sub_cols2 = {row[1] for row in cursor.execute("PRAGMA table_info(agency_subscriptions)").fetchall()}
        if "credits_total" not in existing_sub_cols2:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN credits_total REAL DEFAULT 0")
        if "credits_used" not in existing_sub_cols2:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN credits_used REAL DEFAULT 0")
        if "rollover_credits" not in existing_sub_cols2:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN rollover_credits REAL DEFAULT 0")
        if "allow_rollover" not in existing_sub_cols2:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN allow_rollover INTEGER DEFAULT 0")
        if "overage_rate" not in existing_sub_cols2:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN overage_rate REAL DEFAULT 0")
    except Exception:
        pass
    # Seed default pricing if table is empty
    count = cursor.execute("SELECT COUNT(*) FROM pricing_settings").fetchone()[0]
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
                "INSERT INTO pricing_settings (id, check_type, label, cost_price, sell_price) VALUES (?, ?, ?, ?, ?)",
                (generate_id(), check_type, label, cost, sell),
            )

    # Seed default partial credit rates if table is empty
    try:
        pcr_count = cursor.execute("SELECT COUNT(*) FROM partial_credit_rates").fetchone()[0]
    except Exception:
        pcr_count = 0
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
                "INSERT INTO partial_credit_rates (id, check_type, label, credit_value, third_party_cost) VALUES (?, ?, ?, ?, ?)",
                (_gid(), ct, lbl, cv, cost),
            )

    # Seed default subscription tier config if table is empty
    try:
        stc_count = cursor.execute("SELECT COUNT(*) FROM subscription_tier_config").fetchone()[0]
    except Exception:
        stc_count = 0
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
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (_gid2(), tier_key, name, mp, pwp, mw, mc, ovr, ar, mi, mcap, mar, feats),
            )

    # Add industry_template_id column to agencies if missing
    try:
        existing_ag2_cols = {row[1] for row in cursor.execute("PRAGMA table_info(agencies)").fetchall()}
        if "industry_template_id" not in existing_ag2_cols:
            cursor.execute("ALTER TABLE agencies ADD COLUMN industry_template_id TEXT")
    except Exception:
        pass

    # Add industry_template_id column to agency_sub_accounts if missing
    try:
        existing_sa_cols = {row[1] for row in cursor.execute("PRAGMA table_info(agency_sub_accounts)").fetchall()}
        if "industry_template_id" not in existing_sa_cols:
            cursor.execute("ALTER TABLE agency_sub_accounts ADD COLUMN industry_template_id TEXT")
    except Exception:
        pass

    # Add invited_by_sub_account_id column to agency_candidates if missing
    try:
        existing_ac_cols = {row[1] for row in cursor.execute("PRAGMA table_info(agency_candidates)").fetchall()}
        if "invited_by_sub_account_id" not in existing_ac_cols:
            cursor.execute("ALTER TABLE agency_candidates ADD COLUMN invited_by_sub_account_id TEXT")
    except Exception:
        pass

    # Add sub_account_id column to agency_invites if missing
    try:
        existing_ai_cols = {row[1] for row in cursor.execute("PRAGMA table_info(agency_invites)").fetchall()}
        if "sub_account_id" not in existing_ai_cols:
            cursor.execute("ALTER TABLE agency_invites ADD COLUMN sub_account_id TEXT")
    except Exception:
        pass

    # Create industry_templates and seed defaults if needed
    try:
        cursor.execute("SELECT 1 FROM industry_templates LIMIT 1")
    except Exception:
        cursor.execute("""CREATE TABLE IF NOT EXISTS industry_templates (
            id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, description TEXT,
            compliance_label TEXT DEFAULT 'Compliant', compliance_threshold REAL DEFAULT 95.0,
            is_default INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')), updated_at TEXT
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS industry_template_checks (
            id TEXT PRIMARY KEY, template_id TEXT NOT NULL, check_key TEXT NOT NULL,
            check_label TEXT NOT NULL, is_required INTEGER DEFAULT 1, is_enabled INTEGER DEFAULT 1,
            weight REAL DEFAULT 10.0, config TEXT DEFAULT '{}', sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (template_id) REFERENCES industry_templates(id), UNIQUE(template_id, check_key)
        )""")

    # Seed default industry templates if table is empty
    try:
        tmpl_count = cursor.execute("SELECT COUNT(*) FROM industry_templates").fetchone()[0]
    except Exception:
        tmpl_count = 0
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
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (tid, tname, tdesc, tlabel, tthresh, tdefault),
            )
            for ck, cl, creq, cen, cw, ccfg, csort in tchecks:
                cursor.execute(
                    """INSERT INTO industry_template_checks (id, template_id, check_key, check_label, is_required, is_enabled, weight, config, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (_tid(), tid, ck, cl, creq, cen, cw, ccfg, csort),
                )

    # Seed expanded pricing elements if not present
    try:
        existing_pricing_types = {row[0] for row in cursor.execute("SELECT check_type FROM pricing_settings").fetchall()}
    except Exception:
        existing_pricing_types = set()
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
        if ct not in existing_pricing_types:
            from app.utils.auth import generate_id as _pid
            cursor.execute(
                "INSERT INTO pricing_settings (id, check_type, label, cost_price, sell_price) VALUES (?, ?, ?, ?, ?)",
                (_pid(), ct, lbl, cost, sell),
            )

    # Create imposter_declarations table if it doesn't exist (migration for existing DBs)
    try:
        cursor.execute("SELECT 1 FROM imposter_declarations LIMIT 1")
    except Exception:
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
    try:
        cursor.execute("SELECT 1 FROM scrape_jobs LIMIT 1")
    except Exception:
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
            created_at TEXT DEFAULT (datetime('now'))
        )""")
    try:
        cursor.execute("SELECT 1 FROM leads LIMIT 1")
    except Exception:
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
            scraped_at TEXT DEFAULT (datetime('now')),
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (scrape_job_id) REFERENCES scrape_jobs(id)
        )""")

    # Create registration_scrape_results table for real professional register scraping
    try:
        cursor.execute("SELECT 1 FROM registration_scrape_results LIMIT 1")
    except Exception:
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
            scraped_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        )""")

    # Create industry_plan_links table (Option A: Industry-Specific Plans)
    try:
        cursor.execute("SELECT 1 FROM industry_plan_links LIMIT 1")
    except Exception:
        cursor.execute("""CREATE TABLE IF NOT EXISTS industry_plan_links (
            id TEXT PRIMARY KEY,
            tier_key TEXT NOT NULL,
            industry_template_id TEXT NOT NULL,
            custom_monthly_price REAL,
            custom_per_worker_price REAL,
            custom_monthly_checks INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (industry_template_id) REFERENCES industry_templates(id),
            UNIQUE(tier_key, industry_template_id)
        )""")

    # Create industry_check_pricing table (Option C: Per-Element Industry Pricing)
    try:
        cursor.execute("SELECT 1 FROM industry_check_pricing LIMIT 1")
    except Exception:
        cursor.execute("""CREATE TABLE IF NOT EXISTS industry_check_pricing (
            id TEXT PRIMARY KEY,
            industry_template_id TEXT NOT NULL,
            check_type TEXT NOT NULL,
            label TEXT,
            credit_value REAL DEFAULT 1.0,
            third_party_cost REAL DEFAULT 0,
            sell_price REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (industry_template_id) REFERENCES industry_templates(id),
            UNIQUE(industry_template_id, check_type)
        )""")

    # Add industry_template_id column to subscription_tier_config if missing
    try:
        existing_stc_cols = {row[1] for row in cursor.execute("PRAGMA table_info(subscription_tier_config)").fetchall()}
        if "industry_template_id" not in existing_stc_cols:
            cursor.execute("ALTER TABLE subscription_tier_config ADD COLUMN industry_template_id TEXT")
        if "industry_name" not in existing_stc_cols:
            cursor.execute("ALTER TABLE subscription_tier_config ADD COLUMN industry_name TEXT")
    except Exception:
        pass

    # Add industry_template_id column to agency_subscriptions if missing
    try:
        existing_as_cols = {row[1] for row in cursor.execute("PRAGMA table_info(agency_subscriptions)").fetchall()}
        if "industry_template_id" not in existing_as_cols:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN industry_template_id TEXT")
        if "credits_total" not in existing_as_cols:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN credits_total REAL DEFAULT 0")
        if "credits_used" not in existing_as_cols:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN credits_used REAL DEFAULT 0")
        if "rollover_credits" not in existing_as_cols:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN rollover_credits REAL DEFAULT 0")
        if "allow_rollover" not in existing_as_cols:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN allow_rollover INTEGER DEFAULT 0")
        if "overage_rate" not in existing_as_cols:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN overage_rate REAL DEFAULT 0")
        # 12-month credit pack model columns
        if "expires_at" not in existing_as_cols:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN expires_at TEXT")
        if "auto_topup" not in existing_as_cols:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN auto_topup INTEGER DEFAULT 0")
        if "auto_topup_tier" not in existing_as_cols:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN auto_topup_tier TEXT")
        if "pack_name" not in existing_as_cols:
            cursor.execute("ALTER TABLE agency_subscriptions ADD COLUMN pack_name TEXT")
    except Exception:
        pass

    # Create email_templates table if it doesn't exist
    try:
        cursor.execute("SELECT 1 FROM email_templates LIMIT 1")
    except Exception:
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""")

    # Create email_send_log table if it doesn't exist
    try:
        cursor.execute("SELECT 1 FROM email_send_log LIMIT 1")
    except Exception:
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
            created_at TEXT DEFAULT (datetime('now')),
            sent_at TEXT
        )""")

    conn.commit()
    conn.close()


def init_db():
    """Initialize database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS agency_candidates (
            agency_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            assigned_at TEXT DEFAULT (datetime('now')),
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
            started_at TEXT DEFAULT (datetime('now')),
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
            checked_at TEXT DEFAULT (datetime('now')),
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
            submitted_at TEXT DEFAULT (datetime('now')),
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
            analysed_at TEXT DEFAULT (datetime('now')),
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
            last_checked TEXT DEFAULT (datetime('now')),
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
            sent_at TEXT DEFAULT (datetime('now')),
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
            last_evaluated TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action TEXT NOT NULL,
            actor TEXT,
            details TEXT,
            created_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
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
            sent_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now')),
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
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS alert_settings (
            id TEXT PRIMARY KEY,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value INTEGER NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS candidate_draft_data (
            id TEXT PRIMARY KEY,
            submission_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            section TEXT NOT NULL,
            data TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now')),
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
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (agency_id) REFERENCES agencies(id)
        );

        -- GDPR tables
        CREATE TABLE IF NOT EXISTS gdpr_erasure_requests (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS gdpr_retention_policies (
            id TEXT PRIMARY KEY,
            data_category TEXT UNIQUE NOT NULL,
            retention_period_days INTEGER NOT NULL,
            legal_basis TEXT NOT NULL,
            description TEXT,
            auto_delete INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now'))
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
            scraped_at TEXT DEFAULT (datetime('now')),
            created_at TEXT DEFAULT (datetime('now')),
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
            scraped_at TEXT DEFAULT (datetime('now')),
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
            created_at TEXT DEFAULT (datetime('now')),
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
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (industry_template_id) REFERENCES industry_templates(id),
            UNIQUE(industry_template_id, check_type)
        );
    """)

    conn.commit()
    conn.close()
