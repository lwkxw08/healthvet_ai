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
};

// Agency Invites API
export const agencyInvitesApi = {
  createInvite: (token: string, candidateEmail: string) =>
    apiRequest<Record<string, unknown>>("/api/agencies/invites", { method: "POST", body: { candidate_email: candidateEmail }, token }),
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
