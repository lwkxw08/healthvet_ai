// Build a clean base URL that strips any embedded credentials from the origin.
// This is needed when the app is served via a tunnel URL like https://user:pass@domain.com
// because fetch() rejects URLs with embedded credentials.
function getBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl) return envUrl;
  try {
    const url = new URL(window.location.href);
    return `${url.protocol}//${url.host}`;
  } catch {
    return "";
  }
}

const API_URL = getBaseUrl();

interface RequestOptions {
  method?: string;
  body?: unknown;
  token?: string;
}

export async function apiRequest<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (token) {
    // Send JWT via X-Auth-Token to avoid conflicts with tunnel Basic Auth
    // on the Authorization header. Backend accepts both headers.
    headers["X-Auth-Token"] = token;
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Auth API
export const authApi = {
  registerCandidate: (data: Record<string, unknown>) =>
    apiRequest<{ access_token: string; user_type: string; user_id: string }>("/api/auth/candidates/register", { method: "POST", body: data }),
  registerCandidateWithInvite: (data: Record<string, unknown>) =>
    apiRequest<{ access_token: string; user_type: string; user_id: string }>("/api/auth/candidates/register", { method: "POST", body: data }),
  loginCandidate: (email: string, password: string) =>
    apiRequest<{ access_token: string; user_type: string; user_id: string }>("/api/auth/candidates/login", { method: "POST", body: { email, password } }),
  registerAgency: (data: Record<string, unknown>) =>
    apiRequest<{ access_token: string; user_type: string; user_id: string }>("/api/auth/agencies/register", { method: "POST", body: data }),
  loginAgency: (email: string, password: string) =>
    apiRequest<{ access_token: string; user_type: string; user_id: string }>("/api/auth/agencies/login", { method: "POST", body: { email, password } }),
  loginAdmin: (email: string, password: string) =>
    apiRequest<{ access_token: string; user_type: string; user_id: string }>("/api/auth/admin/login", { method: "POST", body: { email, password } }),
};

// Candidates API
export const candidatesApi = {
  getMe: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/candidates/me", { token }),
  updateMe: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/candidates/me", { method: "PUT", body: data, token }),
  list: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/candidates", { token }),
  get: (token: string, id: string) =>
    apiRequest<Record<string, unknown>>(`/api/candidates/${id}`, { token }),
  assignAgency: (token: string, candidateId: string, agencyId: string) =>
    apiRequest<Record<string, unknown>>(`/api/candidates/${candidateId}/assign-agency/${agencyId}`, { method: "POST", token }),
};

// Checks API
export const checksApi = {
  identityCheck: (token: string, candidateId: string, data: {
    document_type: string;
    document_file_name?: string;
    selfie_file_name?: string;
    first_name?: string;
    last_name?: string;
    date_of_birth?: string;
  }) =>
    apiRequest<Record<string, unknown>>("/api/checks/identity", {
      method: "POST",
      body: { candidate_id: candidateId, ...data },
      token,
    }),
  identitySDKToken: (token: string, candidateId: string) =>
    apiRequest<{ sdk_token: string; applicant_id: string; workflow_run_id: string }>(
      "/api/checks/identity/sdk-token",
      { method: "POST", body: { candidate_id: candidateId }, token },
    ),
  getIdentityChecks: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/checks/identity/${candidateId}`, { token }),

  rightToWork: (token: string, candidateId: string, shareCode: string) =>
    apiRequest<Record<string, unknown>>("/api/checks/right-to-work", { method: "POST", body: { candidate_id: candidateId, share_code: shareCode }, token }),
  rightToWorkUKCitizen: (token: string, candidateId: string, data: { document_type: string; nationality?: string; document_reference?: string; ni_number?: string }) =>
    apiRequest<Record<string, unknown>>("/api/checks/right-to-work/uk-citizen", { method: "POST", body: { candidate_id: candidateId, ...data }, token }),
  getRightToWorkChecks: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/checks/right-to-work/${candidateId}`, { token }),

  dbsCheck: (token: string, candidateId: string, checkType = "enhanced") =>
    apiRequest<Record<string, unknown>>("/api/checks/dbs", { method: "POST", body: { candidate_id: candidateId, check_type: checkType }, token }),
  getDBSChecks: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/checks/dbs/${candidateId}`, { token }),

  cvAnalysis: (token: string, candidateId: string, cvText: string, cvFileName?: string) =>
    apiRequest<Record<string, unknown>>("/api/checks/cv-analysis", { method: "POST", body: { candidate_id: candidateId, cv_text: cvText, cv_file_name: cvFileName || null }, token }),
  getCVAnalyses: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/checks/cv-analysis/${candidateId}`, { token }),

  registrationCheck: (token: string, candidateId: string, body: string, registrationNumber: string) =>
    apiRequest<Record<string, unknown>>("/api/checks/registration", { method: "POST", body: { candidate_id: candidateId, body, registration_number: registrationNumber }, token }),
  getRegistrationChecks: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/checks/registration/${candidateId}`, { token }),

  createReference: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/checks/references", { method: "POST", body: data, token }),
  getReferences: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/checks/references/${candidateId}`, { token }),
  submitReference: (data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/checks/references/submit", { method: "POST", body: data }),
  sendReminder: (token: string, refId: string) =>
    apiRequest<Record<string, unknown>>(`/api/checks/references/${refId}/remind`, { method: "POST", token }),

  // Employment History
  getEmploymentHistory: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/checks/employment/${candidateId}`, { token }),
  addEmploymentEntry: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/checks/employment", { method: "POST", body: data, token }),
  updateEmploymentEntry: (token: string, entryId: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/api/checks/employment/${entryId}`, { method: "PUT", body: data, token }),
  deleteEmploymentEntry: (token: string, entryId: string) =>
    apiRequest<Record<string, unknown>>(`/api/checks/employment/${entryId}`, { method: "DELETE", token }),
  sendEmploymentVerification: (token: string, data: { candidate_id: string; employment_id: string; verifier_name: string; verifier_email: string; verifier_job_title?: string }) =>
    apiRequest<Record<string, unknown>>("/api/checks/employment/verify", { method: "POST", body: data, token }),
  getEmploymentVerifications: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/checks/employment-verifications/${candidateId}`, { token }),
  sendEmploymentVerificationReminder: (token: string, verId: string) =>
    apiRequest<Record<string, unknown>>(`/api/checks/employment-verifications/${verId}/remind`, { method: "POST", token }),

  submitImposterDeclaration: (token: string, candidateId: string, declarationText: string, documentsVerified?: string[]) =>
    apiRequest<Record<string, unknown>>("/api/checks/imposter-declaration", {
      method: "POST",
      body: { candidate_id: candidateId, declaration_text: declarationText, documents_verified: documentsVerified || null },
      token,
    }),
  getImposterDeclarations: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/checks/imposter-declaration/${candidateId}`, { token }),
};

// Compliance API
export const complianceApi = {
  evaluate: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>>(`/api/compliance/evaluate/${candidateId}`, { method: "POST", token }),
  get: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>>(`/api/compliance/${candidateId}`, { token }),
  getAuditLog: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/compliance/${candidateId}/audit-log`, { token }),
};

// Monitoring API
export const monitoringApi = {
  getAlerts: (token: string, candidateId?: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/monitoring/alerts${candidateId ? `?candidate_id=${candidateId}` : ""}`, { token }),
  resolveAlert: (token: string, alertId: string) =>
    apiRequest<Record<string, unknown>>(`/api/monitoring/alerts/${alertId}/resolve`, { method: "POST", token }),
  runChecks: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/monitoring/run-checks", { method: "POST", token }),
};

// Dashboard API
export const dashboardApi = {
  getStats: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/dashboard/stats", { token }),
};

// Admin API
export const adminApi = {
  getPricing: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/admin/pricing", { token }),
  updatePricing: (token: string, checkType: string, data: { cost_price?: number; sell_price?: number; label?: string }) =>
    apiRequest<Record<string, unknown>>(`/api/admin/pricing/${checkType}`, { method: "PUT", body: data, token }),
  getRevenueAnalytics: (token: string, params?: { period?: string; date_from?: string; date_to?: string; agency_id?: string }) => {
    const qs = new URLSearchParams();
    if (params?.period) qs.set("period", params.period);
    if (params?.date_from) qs.set("date_from", params.date_from);
    if (params?.date_to) qs.set("date_to", params.date_to);
    if (params?.agency_id) qs.set("agency_id", params.agency_id);
    return apiRequest<Record<string, unknown>>(`/api/admin/analytics/revenue?${qs.toString()}`, { token });
  },
  getOperationsAnalytics: (token: string, params?: { period?: string; date_from?: string; date_to?: string; agency_id?: string }) => {
    const qs = new URLSearchParams();
    if (params?.period) qs.set("period", params.period);
    if (params?.date_from) qs.set("date_from", params.date_from);
    if (params?.date_to) qs.set("date_to", params.date_to);
    if (params?.agency_id) qs.set("agency_id", params.agency_id);
    return apiRequest<Record<string, unknown>>(`/api/admin/analytics/operations?${qs.toString()}`, { token });
  },
  getAgencyAnalytics: (token: string, params?: { period?: string; date_from?: string; date_to?: string }) => {
    const qs = new URLSearchParams();
    if (params?.period) qs.set("period", params.period);
    if (params?.date_from) qs.set("date_from", params.date_from);
    if (params?.date_to) qs.set("date_to", params.date_to);
    return apiRequest<Record<string, unknown>[]>(`/api/admin/analytics/agencies?${qs.toString()}`, { token });
  },
  getInvoices: (token: string, params?: { period?: string; date_from?: string; date_to?: string; agency_id?: string; status?: string }) => {
    const qs = new URLSearchParams();
    if (params?.period) qs.set("period", params.period);
    if (params?.date_from) qs.set("date_from", params.date_from);
    if (params?.date_to) qs.set("date_to", params.date_to);
    if (params?.agency_id) qs.set("agency_id", params.agency_id);
    if (params?.status) qs.set("status", params.status);
    return apiRequest<Record<string, unknown>[]>(`/api/admin/invoices?${qs.toString()}`, { token });
  },
  createInvoice: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/admin/invoices", { method: "POST", body: data, token }),
  markInvoicePaid: (token: string, invoiceId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/invoices/${invoiceId}/mark-paid`, { method: "POST", token }),
  generateInvoices: (token: string, agencyId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/invoices/generate?agency_id=${agencyId}`, { method: "POST", token }),
  generateGroupedInvoices: (token: string, agencyId: string, dateFrom: string, dateTo: string) =>
    apiRequest<Record<string, unknown>>("/api/admin/invoices/generate-grouped", { method: "POST", body: { agency_id: agencyId, date_from: dateFrom, date_to: dateTo }, token }),
};

// Admin Extended API (override checks, suspend agencies, manage users, audit logs, etc.)
export const adminExtendedApi = {
  // Override check results
  overrideCheck: (token: string, candidateId: string, data: { check_type: string; status: string; notes?: string }) =>
    apiRequest<Record<string, unknown>>(`/api/admin/candidates/${candidateId}/override-check`, { method: "POST", body: data, token }),

  // Agency management
  listAgencies: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/admin/agencies", { token }),
  updateAgencyStatus: (token: string, agencyId: string, data: { status: string; reason?: string }) =>
    apiRequest<Record<string, unknown>>(`/api/admin/agencies/${agencyId}/status`, { method: "PUT", body: data, token }),

  // Edit candidate profile
  editCandidate: (token: string, candidateId: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/api/admin/candidates/${candidateId}`, { method: "PUT", body: data, token }),

  // User management
  createAgency: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/admin/agencies/create", { method: "POST", body: data, token }),
  createCandidate: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/admin/candidates/create", { method: "POST", body: data, token }),
  deleteAgency: (token: string, agencyId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/agencies/${agencyId}`, { method: "DELETE", token }),
  deleteCandidate: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/candidates/${candidateId}`, { method: "DELETE", token }),

  // Alert settings
  getAlertSettings: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/admin/alert-settings", { token }),
  updateAlertSettings: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/admin/alert-settings", { method: "PUT", body: data, token }),

  // Audit logs
  getAuditLogs: (token: string, params?: { entity_type?: string; action?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.entity_type) qs.set("entity_type", params.entity_type);
    if (params?.action) qs.set("action", params.action);
    if (params?.limit) qs.set("limit", params.limit.toString());
    if (params?.offset) qs.set("offset", params.offset.toString());
    return apiRequest<{ total: number; logs: Record<string, unknown>[] }>(`/api/admin/audit-logs?${qs.toString()}`, { token });
  },

  // Edit check data (automation fallout)
  editCheckData: (token: string, candidateId: string, checkType: string, checkId: string, fields: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/api/admin/candidates/${candidateId}/check-data/${checkType}/${checkId}`, { method: "PUT", body: { fields }, token }),

  // Re-trigger verifications
  retriggerReference: (token: string, candidateId: string, refId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/candidates/${candidateId}/retrigger-reference/${refId}`, { method: "POST", token }),
  retriggerEmployment: (token: string, candidateId: string, verId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/candidates/${candidateId}/retrigger-employment/${verId}`, { method: "POST", token }),

  // Full candidate detail (admin view)
  getCandidateFullDetail: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/candidates/${candidateId}/full-detail`, { token }),

  // Candidates monitoring status
  getCandidatesMonitoring: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/admin/candidates-monitoring", { token }),

  // Agency discount management
  getAgencyDiscount: (token: string, agencyId: string) =>
    apiRequest<{ agency_id: string; discount_percent: number }>(`/api/admin/agencies/${agencyId}/discount`, { token }),
  updateAgencyDiscount: (token: string, agencyId: string, discountPercent: number) =>
    apiRequest<Record<string, unknown>>(`/api/admin/agencies/${agencyId}/discount`, { method: "PUT", body: { discount_percent: discountPercent }, token }),

  // Invoice management
  listInvoices: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/admin/invoices", { token }),
  adjustInvoice: (token: string, invoiceId: string, adjustedAmount: number, notes?: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/invoices/${invoiceId}/adjust`, { method: "PUT", body: { adjusted_amount: adjustedAmount, adjustment_notes: notes }, token }),
  markInvoicePaid: (token: string, invoiceId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/invoices/${invoiceId}/status`, { method: "PUT", token }),

  // Agency billing mode management
  getAgencyBillingMode: (token: string, agencyId: string) =>
    apiRequest<{ agency_id: string; agency_name: string; billing_mode: string; stripe_customer_id: string | null }>(`/api/admin/agencies/${agencyId}/billing-mode`, { token }),
  updateAgencyBillingMode: (token: string, agencyId: string, billingMode: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/agencies/${agencyId}/billing-mode`, { method: "PUT", body: { billing_mode: billingMode }, token }),

  // Payment reminders
  sendPaymentReminders: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/admin/billing/send-reminders", { method: "POST", token }),
};

// Agency Services & Status API
export const agencyServicesApi = {
  getMyServices: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/agencies/my-services", { token }),
  getCandidatesWithStatus: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/agencies/candidates-with-status", { token }),
  updateCandidateStatus: (token: string, candidateId: string, employmentStatus: string) =>
    apiRequest<Record<string, unknown>>(`/api/agencies/candidates/${candidateId}/status`, {
      method: "PUT", body: { employment_status: employmentStatus }, token,
    }),
  getBillingMode: (token: string) =>
    apiRequest<{ agency_id: string; agency_name: string; billing_mode: string; stripe_customer_id: string | null }>("/api/agencies/billing-mode", { token }),
  payInvoice: (token: string, invoiceId: string) =>
    apiRequest<Record<string, unknown>>(`/api/agencies/billing/pay-invoice/${invoiceId}`, { method: "POST", token }),
};

// Training Certificates API
export const trainingApi = {
  getStandards: () =>
    apiRequest<Record<string, unknown>[]>("/api/training/standards", {}),
  getCertificates: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/training/${candidateId}`, { token }),
  addCertificate: (token: string, candidateId: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/api/training/${candidateId}`, { method: "POST", body: data, token }),
  updateCertificate: (token: string, certId: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/api/training/cert/${certId}`, { method: "PUT", body: data, token }),
  deleteCertificate: (token: string, certId: string) =>
    apiRequest<Record<string, unknown>>(`/api/training/cert/${certId}`, { method: "DELETE", token }),
  getCompliance: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>>(`/api/training/${candidateId}/compliance`, { token }),
};

// Fraud Detection API
export const fraudApi = {
  runScan: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/fraud/scan", { method: "POST", token }),
  getFlags: (token: string, candidateId?: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/fraud/flags${candidateId ? `?candidate_id=${candidateId}` : ""}`, { token }),
  getSummary: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/fraud/summary", { token }),
  resolveFlag: (token: string, flagId: string) =>
    apiRequest<Record<string, unknown>>(`/api/fraud/flags/${flagId}/resolve`, { method: "POST", token }),
};

// Billing & Subscriptions API
export const billingApi = {
  getTiers: (token?: string) =>
    apiRequest<Record<string, unknown>>("/api/billing/tiers", token ? { token } : {}),
  getSubscription: (token: string, agencyId: string) =>
    apiRequest<Record<string, unknown>>(`/api/billing/subscription/${agencyId}`, { token }),
  subscribe: (token: string, data: { agency_id: string; tier: string; billing_method: string; stripe_payment_method_id?: string }) =>
    apiRequest<Record<string, unknown>>("/api/billing/subscribe", { method: "POST", body: data, token }),
  cancel: (token: string, agencyId: string) =>
    apiRequest<Record<string, unknown>>(`/api/billing/cancel/${agencyId}`, { method: "POST", token }),
  topup: (token: string, data: { agency_id: string; tier: string; billing_method?: string }) =>
    apiRequest<Record<string, unknown>>("/api/billing/topup", { method: "POST", body: data, token }),
  updateAutoTopup: (token: string, data: { agency_id: string; enabled: boolean; tier?: string }) =>
    apiRequest<Record<string, unknown>>("/api/billing/auto-topup", { method: "PUT", body: data, token }),
  getHistory: (token: string, agencyId: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/billing/history/${agencyId}`, { token }),
  payInvoice: (token: string, invoiceId: string) =>
    apiRequest<Record<string, unknown>>(`/api/billing/pay/${invoiceId}`, { method: "POST", token }),
  generateRecurring: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/billing/generate-recurring", { method: "POST", token }),
  updateTier: (token: string, tierKey: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/api/billing/tiers/${tierKey}`, { method: "PUT", body: data, token }),
  createTier: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/billing/tiers", { method: "POST", body: data, token }),
  deleteTier: (token: string, tierKey: string) =>
    apiRequest<Record<string, unknown>>(`/api/billing/tiers/${tierKey}`, { method: "DELETE", token }),
  getRemainingChecks: (token: string, agencyId: string) =>
    apiRequest<Record<string, unknown>>(`/api/billing/remaining-checks/${agencyId}`, { token }),
  useCheck: (token: string, data: { agency_id: string; candidate_id?: string; description?: string; sell_amount?: number; cost_amount?: number; check_type?: string }) =>
    apiRequest<Record<string, unknown>>("/api/billing/use-check", { method: "POST", body: data, token }),
  getPartialCreditRates: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/billing/partial-credit-rates", { token }),
  updatePartialCreditRate: (token: string, checkType: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/api/billing/partial-credit-rates/${checkType}`, { method: "PUT", body: data, token }),
  createPartialCreditRate: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/billing/partial-credit-rates", { method: "POST", body: data, token }),
  deletePartialCreditRate: (token: string, checkType: string) =>
    apiRequest<Record<string, unknown>>(`/api/billing/partial-credit-rates/${checkType}`, { method: "DELETE", token }),
  getCreditTransactions: (token: string, agencyId: string, limit?: number) =>
    apiRequest<Record<string, unknown>[]>(`/api/billing/credit-transactions/${agencyId}${limit ? `?limit=${limit}` : ""}`, { token }),
};

// Audit Pack & PDF Reports API
export const reportsApi = {
  downloadCandidateAudit: (token: string, candidateId: string) => {
    const headers: Record<string, string> = { "X-Auth-Token": token };
    return fetch(`${API_URL}/api/audit/candidate/${candidateId}`, { headers });
  },
  downloadAgencyAudit: (token: string, agencyId: string) => {
    const headers: Record<string, string> = { "X-Auth-Token": token };
    return fetch(`${API_URL}/api/audit/agency/${agencyId}`, { headers });
  },
  downloadBulkCandidateAudit: (token: string, candidateIds: string[]) => {
    const headers: Record<string, string> = { "X-Auth-Token": token, "Content-Type": "application/json" };
    return fetch(`${API_URL}/api/reports/audit/bulk-candidates`, { method: "POST", headers, body: JSON.stringify({ candidate_ids: candidateIds }) });
  },
  downloadFinancialReport: (token: string, period?: string, dateFrom?: string, dateTo?: string) => {
    const qs = new URLSearchParams();
    if (period) qs.set("period", period);
    if (dateFrom) qs.set("date_from", dateFrom);
    if (dateTo) qs.set("date_to", dateTo);
    const headers: Record<string, string> = { "X-Auth-Token": token };
    return fetch(`${API_URL}/api/reports/financial?${qs.toString()}`, { headers });
  },
  downloadComplianceReport: (token: string, agencyId?: string) => {
    const qs = agencyId ? `?agency_id=${agencyId}` : "";
    const headers: Record<string, string> = { "X-Auth-Token": token };
    return fetch(`${API_URL}/api/reports/compliance${qs}`, { headers });
  },
};

// Notifications API (In-App Notification Centre)
export const notificationsApi = {
  getNotifications: (token: string, params?: { unread_only?: boolean; category?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.unread_only) qs.set("unread_only", "true");
    if (params?.category) qs.set("category", params.category);
    if (params?.limit) qs.set("limit", params.limit.toString());
    if (params?.offset) qs.set("offset", params.offset.toString());
    return apiRequest<{ notifications: Record<string, unknown>[]; unread_count: number; total: number }>(`/api/notifications?${qs.toString()}`, { token });
  },
  getUnreadCount: (token: string) =>
    apiRequest<{ unread_count: number }>("/api/notifications/unread-count", { token }),
  markRead: (token: string, notificationId: string) =>
    apiRequest<Record<string, unknown>>(`/api/notifications/${notificationId}/read`, { method: "POST", token }),
  markAllRead: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/notifications/mark-all-read", { method: "POST", token }),
  deleteNotification: (token: string, notificationId: string) =>
    apiRequest<Record<string, unknown>>(`/api/notifications/${notificationId}`, { method: "DELETE", token }),
  seedNotifications: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/notifications/seed", { method: "POST", token }),
};

// Bulk Import API
export const bulkImportApi = {
  importCandidates: (token: string, csvData: string, sendInvites: boolean = true) =>
    apiRequest<Record<string, unknown>>("/api/agencies/bulk-import", { method: "POST", body: { csv_data: csvData, send_invites: sendInvites }, token }),
  getTemplate: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/agencies/bulk-import/template", { token }),
};

// Shift Readiness API
export const shiftReadinessApi = {
  getReadiness: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>>(`/api/shift-readiness/${candidateId}`, { token }),
  getAgencyOverview: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/shift-readiness/agency/overview", { token }),
};

// Sub-Accounts API
export const subAccountsApi = {
  getRoles: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/agencies/sub-accounts/roles", { token }),
  list: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/agencies/sub-accounts", { token }),
  create: (token: string, data: { email: string; password: string; first_name: string; last_name: string; role: string; industry_template_id?: string }) =>
    apiRequest<Record<string, unknown>>("/api/agencies/sub-accounts", { method: "POST", body: data, token }),
  update: (token: string, accountId: string, data: { role?: string; is_active?: boolean; industry_template_id?: string }) =>
    apiRequest<Record<string, unknown>>(`/api/agencies/sub-accounts/${accountId}`, { method: "PUT", body: data, token }),
  remove: (token: string, accountId: string) =>
    apiRequest<Record<string, unknown>>(`/api/agencies/sub-accounts/${accountId}`, { method: "DELETE", token }),
  listTemplates: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/industry-templates/list", { token }),
};

// Benchmarking API (Admin)
export const benchmarkingApi = {
  getAgencyBenchmarks: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/admin/benchmarking/agencies", { token }),
  getTrends: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/admin/benchmarking/trends", { token }),
};

// Scheduler API
export const schedulerApi = {
  getStatus: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/scheduler/status", { token }),
  triggerJob: (token: string, jobName: string) =>
    apiRequest<Record<string, unknown>>(`/api/scheduler/trigger/${jobName}`, { method: "POST", token }),
};

// Submissions API (new candidate onboarding flow)
export const submissionsApi = {
  createSubmission: (token: string, data?: { submission_type?: string; sections_requested?: string[]; revet_token?: string }) =>
    apiRequest<Record<string, unknown>>("/api/submissions/create", { method: "POST", body: data || {}, token }),
  getCurrent: (token: string) =>
    apiRequest<Record<string, unknown> | null>("/api/submissions/current", { token }),
  getSubmission: (token: string, submissionId: string) =>
    apiRequest<Record<string, unknown>>(`/api/submissions/${submissionId}`, { token }),
  saveSection: (token: string, submissionId: string, section: string, data: Record<string, unknown>, completed: boolean) =>
    apiRequest<Record<string, unknown>>(`/api/submissions/${submissionId}/section/${section}`, {
      method: "PUT", body: { data, completed }, token,
    }),
  validate: (token: string, submissionId: string) =>
    apiRequest<Record<string, unknown>>(`/api/submissions/${submissionId}/validate`, { method: "POST", token }),
  submitWithConsent: (token: string, submissionId: string, data: { consent_given: boolean; privacy_policy_version?: string; terms_version?: string }) =>
    apiRequest<Record<string, unknown>>(`/api/submissions/${submissionId}/consent`, { method: "POST", body: data, token }),
  getStatus: (token: string, submissionId: string) =>
    apiRequest<Record<string, unknown>>(`/api/submissions/${submissionId}/status`, { token }),
  getRevetInfo: (revetToken: string) =>
    apiRequest<Record<string, unknown>>(`/api/submissions/revet-info/${revetToken}`, {}),
};

// Industry Templates API (Admin)
export const industryTemplatesApi = {
  list: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/admin/industry-templates", { token }),
  get: (token: string, templateId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/industry-templates/${templateId}`, { token }),
  create: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/admin/industry-templates", { method: "POST", body: data, token }),
  update: (token: string, templateId: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/api/admin/industry-templates/${templateId}`, { method: "PUT", body: data, token }),
  remove: (token: string, templateId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/industry-templates/${templateId}`, { method: "DELETE", token }),
  clone: (token: string, templateId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/industry-templates/clone/${templateId}`, { method: "POST", token }),
  assignToAgency: (token: string, agencyId: string, templateId: string) =>
    apiRequest<Record<string, unknown>>("/api/admin/industry-templates/assign", { method: "POST", body: { agency_id: agencyId, template_id: templateId }, token }),
  getAgencyTemplate: (token: string, agencyId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/industry-templates/agency/${agencyId}`, { token }),
};

// Lead Generation API (Admin)
export const leadGenerationApi = {
  getSources: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/lead-generation/sources", { token }),
  triggerScrape: (token: string, data: { source: string; industry?: string; industry_slug?: string; config?: Record<string, unknown> }) =>
    apiRequest<Record<string, unknown>>("/api/lead-generation/scrape", { method: "POST", body: data, token }),
  getJobs: (token: string, params?: { source?: string; status?: string }) =>
    apiRequest<Record<string, unknown>[]>(`/api/lead-generation/jobs${params ? '?' + new URLSearchParams(params as Record<string, string>).toString() : ''}`, { token }),
  getJob: (token: string, jobId: string) =>
    apiRequest<Record<string, unknown>>(`/api/lead-generation/jobs/${jobId}`, { token }),
  getLeads: (token: string, params?: Record<string, string>) =>
    apiRequest<Record<string, unknown>>(`/api/lead-generation/leads${params ? '?' + new URLSearchParams(params).toString() : ''}`, { token }),
  getLeadStats: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/lead-generation/leads/stats", { token }),
  updateLead: (token: string, leadId: string, data: { status?: string; notes?: string }) =>
    apiRequest<Record<string, unknown>>(`/api/lead-generation/leads/${leadId}`, { method: "PUT", body: data, token }),
  deleteLead: (token: string, leadId: string) =>
    apiRequest<Record<string, unknown>>(`/api/lead-generation/leads/${leadId}`, { method: "DELETE", token }),
  bulkDeleteLeads: (token: string, leadIds: string[]) =>
    apiRequest<Record<string, unknown>>("/api/lead-generation/leads/bulk-delete", { method: "POST", body: { lead_ids: leadIds }, token }),
  exportLeads: async (token: string, params?: Record<string, string>): Promise<void> => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["X-Auth-Token"] = token;
    const response = await fetch(`${API_URL}/api/lead-generation/leads/export`, {
      method: "POST",
      headers,
      body: params ? JSON.stringify(params) : undefined,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Export failed" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : "leads_export.xlsx";
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  },
  scrapeRegistration: (token: string, data: { candidate_id: string; body: string; registration_number: string }) =>
    apiRequest<Record<string, unknown>>("/api/lead-generation/registration-scrape", { method: "POST", body: data, token }),
  getRegistrationScrapes: (token: string, candidateId: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/lead-generation/registration-scrape/${candidateId}`, { token }),
};

// Subscription Plans API (Admin - Industry-Specific)
export const subscriptionPlansApi = {
  getIndustryPlans: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/subscription-plans/industry-plans", { token }),
  createIndustryPlan: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/subscription-plans/industry-plans", { method: "POST", body: data, token }),
  updateIndustryPlan: (token: string, linkId: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/api/subscription-plans/industry-plans/${linkId}`, { method: "PUT", body: data, token }),
  deleteIndustryPlan: (token: string, linkId: string) =>
    apiRequest<Record<string, unknown>>(`/api/subscription-plans/industry-plans/${linkId}`, { method: "DELETE", token }),
  getIndustryPricing: (token: string, templateId?: string) =>
    apiRequest<Record<string, unknown>[]>(`/api/subscription-plans/industry-pricing${templateId ? '?industry_template_id=' + templateId : ''}`, { token }),
  createIndustryPricing: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/subscription-plans/industry-pricing", { method: "POST", body: data, token }),
  updateIndustryPricing: (token: string, pricingId: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/api/subscription-plans/industry-pricing/${pricingId}`, { method: "PUT", body: data, token }),
  deleteIndustryPricing: (token: string, pricingId: string) =>
    apiRequest<Record<string, unknown>>(`/api/subscription-plans/industry-pricing/${pricingId}`, { method: "DELETE", token }),
  bulkSetPricing: (token: string, data: { industry_template_id: string; pricing: Record<string, unknown>[] }) =>
    apiRequest<Record<string, unknown>>("/api/subscription-plans/industry-pricing/bulk", { method: "POST", body: data, token }),
  getPlansByIndustry: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/subscription-plans/by-industry", { token }),
  getPricingMatrix: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/subscription-plans/pricing-matrix", { token }),
};

// Agency Re-vet API
export const agencyRevetApi = {
  requestRevet: (token: string, candidateId: string, sections: string[]) =>
    apiRequest<Record<string, unknown>>(`/api/agencies/candidates/${candidateId}/request-revet`, {
      method: "POST", body: { sections }, token,
    }),
  listRevetRequests: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/agencies/revet-requests", { token }),
};

// Email Templates API (Admin)
export const emailTemplatesApi = {
  list: (token: string) =>
    apiRequest<{ templates: Record<string, unknown>[] }>("/api/admin/email-templates", { token }),
  get: (token: string, templateId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/email-templates/${templateId}`, { token }),
  create: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/admin/email-templates", { method: "POST", body: data, token }),
  update: (token: string, templateId: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/api/admin/email-templates/${templateId}`, { method: "PUT", body: data, token }),
  remove: (token: string, templateId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/email-templates/${templateId}`, { method: "DELETE", token }),
  reset: (token: string, templateId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/email-templates/${templateId}/reset`, { method: "POST", token }),
  preview: (token: string, templateId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/email-templates/${templateId}/preview`, { token }),
  testSend: (token: string, data: { template_key: string; recipient_email: string; recipient_name?: string; variables?: Record<string, string> }) =>
    apiRequest<Record<string, unknown>>("/api/admin/email-templates/test-send", { method: "POST", body: data, token }),
  stats: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/admin/email-templates/stats", { token }),
  sendLog: (token: string, limit?: number) =>
    apiRequest<{ log: Record<string, unknown>[] }>(`/api/admin/email-templates/send-log${limit ? '?limit=' + limit : ''}`, { token }),
};

// Email Rules API
export const emailRulesApi = {
  list: (token: string) =>
    apiRequest<{ rules: Record<string, unknown>[] }>("/api/admin/email-rules", { token }),
  triggers: (token: string) =>
    apiRequest<{ triggers: Record<string, unknown> }>("/api/admin/email-rules/triggers", { token }),
  create: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/admin/email-rules", { method: "POST", body: data, token }),
  update: (token: string, ruleId: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/api/admin/email-rules/${ruleId}`, { method: "PUT", body: data, token }),
  remove: (token: string, ruleId: string) =>
    apiRequest<Record<string, unknown>>(`/api/admin/email-rules/${ruleId}`, { method: "DELETE", token }),
};

// Email Config API (Admin)
export const emailConfigApi = {
  get: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/admin/email-config", { token }),
  update: (token: string, data: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/admin/email-config", { method: "PUT", body: data, token }),
  test: (token: string) =>
    apiRequest<Record<string, unknown>>("/api/admin/email-config/test", { method: "POST", token }),
};

// Agency Invites API
export const agencyInvitesApi = {
  getVettingPricing: (token: string) =>
    apiRequest<{ vetting_total: number; monitoring_annual_price: number }>("/api/agencies/vetting-pricing", { token }),
  createInvite: (token: string, candidateEmail: string, includeMonitoring: boolean = false, subAccountId?: string) =>
    apiRequest<Record<string, unknown>>("/api/agencies/invites", { method: "POST", body: { candidate_email: candidateEmail, include_monitoring: includeMonitoring, sub_account_id: subAccountId }, token }),
  listInvites: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/agencies/invites", { token }),
  revokeInvite: (token: string, inviteId: string) =>
    apiRequest<Record<string, unknown>>(`/api/agencies/invites/${inviteId}`, { method: "DELETE", token }),
  getInviteInfo: (inviteCode: string) =>
    apiRequest<{ invite_code: string; agency_name: string; candidate_email: string }>(`/api/agencies/invite-info/${inviteCode}`, {}),
  acceptInvite: (token: string, inviteCode: string) =>
    apiRequest<Record<string, unknown>>(`/api/agencies/invites/${inviteCode}/accept`, { method: "POST", token }),
  getMyAgencies: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/agencies/my-agencies", { token }),
  getPendingInvites: (token: string) =>
    apiRequest<Record<string, unknown>[]>("/api/agencies/pending-invites", { token }),
};
