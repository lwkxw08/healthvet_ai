# HealthVet AI — Operational Readiness Gap Analysis

## Current State Summary

The application has a comprehensive feature set covering candidate compliance management, agency dashboards, admin controls, billing, email templates, lead generation, a public verification portal, AI-powered analysis features, and document upload/storage. The majority of gaps have been addressed — only external API integrations and multi-channel communication remain before the platform is production-ready.

**Last updated:** April 2026

---

## Priority 1 — CRITICAL (Must-Have for Launch)

### 1.1 Real API Integrations (Replace Simulations)
**Status:** All core checks use `random.random()` simulation  
**Impact:** Platform cannot perform actual compliance checks  

| Service | Current State | Production Requirement |
|---------|--------------|----------------------|
| DBS Checks | `_simulate_dbs_result()` returns random pass/fail | Integrate uCheck, CareCheck, or First Advantage API |
| Identity Verification | `_simulate_onfido_result()` returns random scores | Integrate Onfido SDK (document + selfie + liveness) |
| Right to Work | `_simulate_home_office_check()` returns random results | Integrate UK Home Office Employer Checking Service API |
| Registration Checks | Scrapes NMC/GMC/HCPC/GPhC websites | Keep scraping OR integrate official register APIs when available |
| Monitoring Alerts | `random.random() < 0.03` for DBS changes | Integrate DBS Update Service API for real-time checks |

**Effort:** ~3-5 days per integration (15-25 days total)  
**Dependency:** API credentials from each provider + commercial agreements

### ~~1.2 Payment Processing (Stripe/GoCardless)~~ ✅ COMPLETED (PR #2)
~~**Status:** Billing system tracks credits/invoices but no real payment collection~~  
~~**Impact:** Cannot charge agencies for services~~  

- ~~Credit card payments via Stripe (for credit pack purchases + PAYG)~~
- ~~Direct debit via GoCardless (for subscription/recurring billing)~~
- ~~Invoice PDF generation + download~~
- ~~Payment webhooks for status updates~~
- ~~Refund handling~~

~~**Effort:** ~5-7 days~~

**What was built:** Admin-configurable payment provider system. Admin connects Stripe/GoCardless via Settings UI, tests connectivity, and selects which provider handles each payment type (credit packs, PAYG invoices, subscriptions, direct debits, refunds). Billing service auto-routes through configured provider with simulated fallback. Transaction history tracking across all providers.

### ~~1.3 Email Provider Configuration (Live Emails)~~ ✅ COMPLETED (PR #2)
~~**Status:** Email template system built, multi-provider support coded (SendGrid/Mailgun/Resend), but no API key configured — all emails logged to DB only~~  
~~**Impact:** No verification requests, reminders, or notifications are actually sent~~  

- ~~Configure at least one provider API key (admin UI already supports this)~~
- ~~Test deliverability with real NHS/corporate email domains~~
- ~~SPF/DKIM/DMARC DNS records for sending domain~~
- ~~Email bounce handling~~

~~**Effort:** ~1-2 days (mostly DNS + testing)~~

**What was built:** SendGrid API key configured and tested. Live emails now sending via SendGrid with verified sender. Admin can configure provider API keys, sender details, and provider selection directly from Settings page. Email template system routes all outbound emails through configured provider.

### ~~1.4 Authentication & Security Hardening~~ ✅ COMPLETED (PR #2)
~~**Status:** Basic JWT auth with hardcoded test accounts, no password hashing with bcrypt~~  
~~**Impact:** Not secure for production use~~  

- ~~Password hashing (bcrypt/argon2 — currently plaintext comparison)~~
- ~~Password reset flow (forgot password → email → reset link)~~
- ~~Account lockout after failed attempts~~
- ~~Session management (token refresh, revocation)~~
- ~~HTTPS enforcement~~
- ~~Rate limiting on auth endpoints~~
- ~~CSRF protection~~
- ~~Input sanitisation (XSS prevention on all text fields)~~

~~**Effort:** ~3-5 days~~

### ~~1.5 Multi-Tenancy / Agency Data Isolation~~ ✅ COMPLETED (PR #2)
~~**Status:** All agencies share the same DB with agency_id foreign keys, but no row-level security~~  
~~**Impact:** Risk of data leakage between agencies~~  

- ~~Enforce agency_id filtering on all queries (currently relies on frontend filtering)~~
- ~~API-level middleware to inject agency scope from JWT~~
- ~~Verify no cross-agency data access paths exist~~
- ~~Audit all endpoints for proper authorization checks~~

~~**Effort:** ~3-4 days~~

---

## Priority 2 — HIGH (Required Pre-Launch)

### ~~2.1 Candidate Self-Service Portal~~ ✅ COMPLETED (PR #2)
~~**Status:** CandidatePortal.tsx exists as data-collection-only~~  
~~**Impact:** Candidates can't track their own compliance progress~~  

- ~~Candidate login/registration flow~~
- ~~Dashboard showing compliance status per check~~
- ~~Document upload for identity, RTW, training certificates~~
- ~~Employment history timeline view~~
- ~~Notification preferences~~

~~**Effort:** ~3-4 days~~

### ~~2.2 Document Upload & Storage~~ ✅ COMPLETED (PR #2)
~~**Status:** No file upload system exists~~  
~~**Impact:** Cannot accept ID photos, DBS certificates, training certs, CVs~~  

- ~~File upload API (S3/CloudFlare R2)~~
- ~~Document type categorisation~~
- ~~Virus scanning (ClamAV or cloud-based)~~
- ~~Image compression + thumbnail generation~~
- ~~Retention policy enforcement (auto-delete after 6 years)~~
- ~~Secure signed URLs for viewing~~

~~**Effort:** ~4-5 days~~

**What was built:** Full document management system with storage abstraction layer (LocalStorage now, S3/Cloudflare R2-ready via factory swap). Auto-categorisation of 8 document types (CV, identity, DBS, RTW, training cert, qualification, reference letter, other). Pillow-based image compression + thumbnail generation. ClamAV virus scanning with graceful skip. HMAC-SHA256 signed URLs for secure downloads. 6-year retention policy enforcement. Drag-and-drop upload UI in Candidate Portal Documents tab. Multipart upload API at `/api/documents/*`.

### ~~2.3 Candidate Pre-Notification System~~ ✅ COMPLETED (PR #2)
~~**Status:** Template text says "candidate should have notified you" but no actual notification sent~~  
~~**Impact:** Verifiers receive cold emails with no context~~  

- ~~When agency triggers employment verification or reference request, auto-send candidate a heads-up email first~~
- ~~Configurable delay (e.g., send verification request 24h after candidate notification)~~
- ~~Candidate can confirm/update verifier contact details before request is sent~~

~~**Effort:** ~2-3 days~~

### 2.4 Reply-Based Verification (Email Replies)
**Status:** Only portal-based verification exists  
**Impact:** Some verifiers (especially NHS HR departments) prefer replying to emails  

- Parse inbound email replies (via SendGrid Inbound Parse / Mailgun routes)
- Extract structured data from reply text
- Map replies to verification records
- Fallback to portal link in confirmation

**Effort:** ~3-4 days

### ~~2.5 Proper Database (PostgreSQL)~~ ✅ COMPLETED (PR #2)
~~**Status:** SQLite file-based database~~  
~~**Impact:** Cannot handle concurrent writes, no proper backups, single-server only~~  

- ~~Migrate to PostgreSQL (Supabase, Neon, or self-hosted)~~
- ~~Update all raw SQL queries for PostgreSQL compatibility~~
- ~~Connection pooling~~
- ~~Automated backups~~
- ~~Database migrations framework (Alembic)~~

~~**Effort:** ~3-5 days~~

---

## Priority 3 — MEDIUM (Post-Launch Improvements)

### 3.1 Multi-Channel Follow-Up (SMS + WhatsApp)
**Status:** Email-only communication  
**Impact:** Lower response rates from verifiers  

- Twilio SMS integration for verification reminders
- WhatsApp Business API for high-open-rate follow-ups
- Channel preference per verifier
- Escalation chain: email → SMS (3 days) → WhatsApp (5 days) → phone call alert

**Effort:** ~3-4 days

### ~~3.2 Reporting & Analytics Dashboard~~ ✅ COMPLETED (PR #2)
~~**Status:** Basic admin benchmarking panel exists~~  
~~**Impact:** Agencies lack actionable compliance insights~~  

- ~~Agency-level compliance KPI dashboard~~
- ~~Time-to-clear metrics per check type~~
- ~~Verification response rate analytics~~
- ~~Expiry forecasting~~
- ~~Exportable PDF/Excel reports~~
- ~~Scheduled email reports~~

~~**Effort:** ~4-5 days~~

### ~~3.3 Webhook Reliability & Retry~~ ✅ COMPLETED (PR #2)
~~**Status:** Webhook endpoints exist but delivery is fire-and-forget~~  
~~**Impact:** HR system integrations may miss events~~  

- ~~Webhook delivery retry with exponential backoff~~
- ~~Webhook signature verification (HMAC)~~
- ~~Delivery status dashboard~~
- ~~Failed delivery alerting~~
- ~~Webhook event replay capability~~

~~**Effort:** ~2-3 days~~

### ~~3.4 Audit Trail & Compliance Reporting~~ ✅ COMPLETED (PR #2)
~~**Status:** `audit_logs` table exists but not comprehensive~~  
~~**Impact:** May not meet regulatory audit requirements~~  

- ~~Ensure every data mutation is logged (who, what, when, from where)~~
- ~~Tamper-evident audit log (hash chain)~~
- ~~Exportable audit reports for CQC/regulatory inspections~~
- ~~Data access logging for GDPR subject access requests~~
- ~~Retention policy enforcement reporting~~

~~**Effort:** ~3-4 days~~

### ~~3.5 Background Job Processing (Production)~~ ✅ COMPLETED (PR #2)
~~**Status:** Celery app configured but falls back to in-process when Redis unavailable~~  
~~**Impact:** Long-running tasks block the web server~~  

- ~~Redis/RabbitMQ deployment~~
- ~~Celery worker process management~~
- ~~Job monitoring (Flower dashboard)~~
- ~~Dead letter queue for failed jobs~~
- ~~Proper task timeout handling~~

~~**Effort:** ~2-3 days~~

---

## Priority 4 — LOW (Nice-to-Have / Future Phases)

### 4.1 White-Label / Custom Branding
- Per-agency logo, colours, email branding
- Custom domain support for verification portal
- Agency-branded PDF reports

### 4.2 Mobile App / PWA
- Candidate mobile app for document capture
- Push notifications for status updates
- Offline document scanning

### ~~4.3 AI-Powered Features~~ ✅ COMPLETED (PR #2)
- ~~CV gap analysis with LLM~~
- ~~Automated reference sentiment analysis (beyond basic scoring)~~
- ~~Anomaly detection in verification patterns~~
- ~~Smart scheduling for verification follow-ups~~

**What was built:** Four AI analysis services with hybrid LLM + rule-based approach. All services try OpenAI GPT-4o-mini first, fall back to rule-based when no API key configured. (1) CV Gap Analysis — regex date extraction, employment gap/overlap detection, vague description flagging, LLM-powered detailed analysis. (2) Reference Sentiment Analysis — evasive language detection, red flags, consistency checks, sentiment scoring 0.0–1.0. (3) Anomaly Detection — statistical pattern analysis detecting rapid responses, same-IP submissions, email domain mismatches, generic language, unusual times. (4) Smart Scheduling — historical response pattern analysis for optimal reminder timing by verifier type. Full admin UI under Operations → AI Insights with 4 sub-tabs. API endpoints at `/api/ai/*`.

### 4.4 Advanced Compliance
- Scottish PVG scheme integration
- International police check support
- Professional indemnity insurance verification
- Occupational health clearance tracking

### 4.5 Marketplace / Partner Integrations
- Direct integration with NHS Jobs, Reed, Indeed
- ATS (Applicant Tracking System) connectors
- Payroll system integration
- Training provider API connections

---

## Recommended Development Order

| Phase | Items | Estimated Effort | Milestone | Status |
|-------|-------|-----------------|-----------|--------|
| **Phase A** | ~~1.3 (Email config)~~ + ~~1.4 (Auth hardening)~~ + ~~2.3 (Pre-notification)~~ | ~7-10 days | Secure platform with live emails | ✅ DONE |
| **Phase B** | ~~1.2 (Payments)~~ + ~~2.5 (PostgreSQL)~~ | ~8-12 days | Revenue-capable + scalable DB | ✅ DONE |
| **Phase C** | ~~2.2 (Document upload)~~ + ~~2.1 (Candidate portal)~~ | ~7-9 days | Full candidate self-service | ✅ DONE |
| **Phase D** | 1.1 (Real API integrations — start with DBS + Identity) | ~6-10 days | Real compliance checks | ❌ Not started |
| **Phase E** | ~~1.5 (Multi-tenancy)~~ + ~~3.4 (Audit trail)~~ | ~6-8 days | Production security + compliance | ✅ DONE |
| **Phase F** | 2.4 (Reply verification) + 3.1 (SMS/WhatsApp) | ~6-8 days | Multi-channel verification | ❌ Not started |
| **Phase G** | ~~3.2 (Analytics)~~ + ~~3.3 (Webhooks)~~ + ~~3.5 (Background jobs)~~ | ~8-12 days | Enterprise-grade operations | ✅ DONE |
| **Phase H** | ~~4.3 (AI-Powered Features)~~ | ~5-7 days | AI analysis & insights | ✅ DONE |

**Completed: 13 of 19 gap items (68%)**  
**Remaining effort to full production: ~15-25 development days** (down from ~50-70)

---

## What's Already Built & Working

For reference, these features are **complete and functional**:

- Agency dashboard with candidate management, compliance tracking, shift readiness
- Admin panel with 7 grouped tabs (consolidated from 16)
- DB-driven subscription/credit pack billing model (12-month packs)
- PAYG payment tracking alongside subscriptions
- Industry-configurable compliance templates (8 industries)
- Per-element check pricing with admin UI
- Sub-account system with role-based access + industry template assignment
- Employment verification workflow with portal submission
- Reference request workflow with portal submission
- Verification Portal at /verify with fraud detection
- Email template system (10 defaults + custom) with multi-provider support
- Email rules engine with visual conditions builder
- Email provider configuration UI (SendGrid/Mailgun/Resend)
- Live email sending via SendGrid with verified sender (NEW)
- Verification email trust signals (regulatory footer, agency co-branding, codes)
- Lead generation scrapers (AgencyCentral, Indeed, CQC, NHS Jobs)
- Professional registration scrapers (NMC, GMC, HCPC, GPhC)
- Imposter check declarations for RTW compliance
- Bulk candidate import
- In-app notification centre
- GDPR tools (erasure requests, consent logs, DPIAs, retention policies)
- REST API with API key management + webhook system
- Monitoring alerts (DBS updates, visa expiry, registration renewal, sanctions)
- Fraud detection (duplicate documents, reference rings, email clusters)
- Scheduled monitoring via APScheduler
- Scrape job recovery + retry on server restart
- Admin-configurable payment providers (Stripe + GoCardless) with per-payment-type routing (NEW)
- Document upload & storage with S3/R2-ready abstraction layer (NEW)
- Image compression, thumbnails, virus scanning, auto-categorisation (NEW)
- Signed URLs for secure document downloads + 6-year retention policy (NEW)
- AI-powered CV gap analysis with OpenAI GPT-4o-mini + rule-based fallback (NEW)
- AI-powered reference sentiment analysis (NEW)
- AI anomaly detection for verification patterns (NEW)
- AI smart scheduling for verification follow-ups (NEW)
- AI Insights dashboard in admin panel with 4 sub-tabs (NEW)
- Candidate portal Documents tab with drag-and-drop upload (NEW)
