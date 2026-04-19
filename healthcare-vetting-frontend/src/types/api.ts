/** Shared TypeScript interfaces for Viper AI API responses. */

// ── Auth ──────────────────────────────────────────────────────────────────────
export interface AuthResponse {
  access_token: string;
  user_type: string;
  user_id: string;
}

// ── Candidate ─────────────────────────────────────────────────────────────────
export interface Candidate {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  date_of_birth?: string;
  address?: string;
  profession?: string;
  registration_body?: string;
  registration_number?: string;
  compliance_status?: string;
  created_at?: string;
  updated_at?: string;
}

// ── Agency ────────────────────────────────────────────────────────────────────
export interface Agency {
  id: string;
  name: string;
  email: string;
  contact_name?: string;
  phone?: string;
  status?: string;
  billing_mode?: string;
  discount_percentage?: number;
  industry_template_id?: string;
  created_at?: string;
}

// ── Compliance ────────────────────────────────────────────────────────────────
export interface ComplianceRecord {
  candidate_id: string;
  overall_status: string;
  score: number;
  checks: ComplianceCheck[];
  evaluated_at?: string;
}

export interface ComplianceCheck {
  check_type: string;
  status: string;
  details?: string;
  verified_at?: string;
}

// ── Monitoring Alert ──────────────────────────────────────────────────────────
export interface MonitoringAlert {
  id: string;
  candidate_id: string;
  alert_type: string;
  severity: string;
  message: string;
  status: string;
  created_at: string;
  resolved_at?: string;
}

// ── Invoice / Billing ─────────────────────────────────────────────────────────
export interface Invoice {
  id: string;
  agency_id: string;
  agency_name?: string;
  check_type?: string;
  description?: string;
  cost_amount: number;
  sell_amount: number;
  adjusted_amount?: number;
  status: string;
  created_at: string;
  paid_at?: string;
}

export interface SubscriptionTier {
  tier_key: string;
  name: string;
  monthly_price: number;
  per_worker_price: number;
  max_workers: number;
  monthly_checks: number;
  overage_rate: number;
  allow_rollover: boolean;
  features: string[];
}

export interface CreditRate {
  check_type: string;
  label: string;
  credit_value: number;
  third_party_cost: number;
}

export interface RemainingChecks {
  agency_id: string;
  credits_remaining: number;
  credits_used: number;
  monthly_allowance: number;
  tier: string;
  expires_at?: string;
}

// ── Notification ──────────────────────────────────────────────────────────────
export interface Notification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  category: string;
  severity: string;
  is_read: number;
  link?: string;
  created_at: string;
}

// ── Dashboard Stats ───────────────────────────────────────────────────────────
export interface DashboardStats {
  total_candidates: number;
  compliant: number;
  flagged: number;
  pending: number;
  total_agencies?: number;
  total_checks?: number;
}

// ── Audit Log ─────────────────────────────────────────────────────────────────
export interface AuditLog {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  details?: string;
  created_at: string;
}

// ── Fraud Flag ────────────────────────────────────────────────────────────────
export interface FraudFlag {
  id: string;
  candidate_id: string;
  flag_type: string;
  severity: string;
  description: string;
  status: string;
  created_at: string;
  resolved_at?: string;
}

// ── Reference ─────────────────────────────────────────────────────────────────
export interface Reference {
  id: string;
  candidate_id: string;
  referee_name: string;
  referee_email: string;
  referee_organisation?: string;
  referee_job_title?: string;
  status: string;
  response?: string;
  created_at: string;
  submitted_at?: string;
}

// ── Employment ────────────────────────────────────────────────────────────────
export interface EmploymentEntry {
  id: string;
  candidate_id: string;
  employer_name: string;
  job_title: string;
  start_date: string;
  end_date?: string;
  reason_for_leaving?: string;
  created_at?: string;
}

export interface EmploymentVerification {
  id: string;
  candidate_id: string;
  employment_id: string;
  verifier_name: string;
  verifier_email: string;
  verifier_job_title?: string;
  status: string;
  created_at: string;
}

// ── Check Results ─────────────────────────────────────────────────────────────
export interface IdentityCheck {
  id: string;
  candidate_id: string;
  document_type: string;
  status: string;
  confidence_score?: number;
  created_at: string;
}

export interface RightToWorkCheck {
  id: string;
  candidate_id: string;
  method: string;
  status: string;
  verified: boolean;
  visa_expiry?: string;
  created_at: string;
}

export interface DBSCheck {
  id: string;
  candidate_id: string;
  check_type: string;
  status: string;
  certificate_number?: string;
  next_renewal?: string;
  created_at: string;
}

export interface CVAnalysis {
  id: string;
  candidate_id: string;
  cv_file_name?: string;
  gap_analysis?: string;
  overlap_detection?: string;
  qualification_verification?: string;
  fraud_indicators?: string;
  created_at: string;
}

export interface RegistrationCheck {
  id: string;
  candidate_id: string;
  body: string;
  registration_number: string;
  is_active: boolean;
  status: string;
  next_check?: string;
  created_at: string;
}

// ── Pricing ───────────────────────────────────────────────────────────────────
export interface PricingItem {
  check_type: string;
  label: string;
  cost_price: number;
  sell_price: number;
}

// ── Scheduler ─────────────────────────────────────────────────────────────────
export interface SchedulerStatus {
  running: boolean;
  jobs: SchedulerJob[];
}

export interface SchedulerJob {
  id: string;
  name: string;
  next_run_time?: string;
  trigger: string;
}

// ── Revenue Analytics ─────────────────────────────────────────────────────────
export interface RevenueAnalytics {
  total_revenue: number;
  total_cost: number;
  profit: number;
  margin_percent: number;
  invoice_count: number;
  period: string;
}

export interface OperationsAnalytics {
  total_checks: number;
  checks_by_type: Record<string, number>;
  avg_turnaround_hours: number;
  period: string;
}

// ── Industry Template ─────────────────────────────────────────────────────────
export interface IndustryTemplate {
  id: string;
  name: string;
  description?: string;
  checks: string[];
  created_at?: string;
}

// ── Training ──────────────────────────────────────────────────────────────────
export interface TrainingCertificate {
  id: string;
  candidate_id: string;
  certificate_name: string;
  category: string;
  provider?: string;
  issue_date?: string;
  expiry_date?: string;
  reference_number?: string;
  status: string;
}

export interface TrainingStandard {
  id: string;
  name: string;
  category: string;
  required: boolean;
  description?: string;
}

// ── SSE Events ────────────────────────────────────────────────────────────────
export interface CheckStatusSnapshot {
  identity: string;
  dbs: string;
  right_to_work: string;
  professional_registration: string;
  training: string;
  references: string;
  employment: string;
}

export interface CheckStatusUpdate {
  changes: Record<string, { old: string; new: string }>;
  snapshot: CheckStatusSnapshot;
}
