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
    """)

    conn.commit()
    conn.close()
