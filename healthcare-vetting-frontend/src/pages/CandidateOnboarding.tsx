import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { submissionsApi, candidatesApi } from "../api/client";

const SECTIONS = [
  { key: "personal", label: "Personal Details", icon: "\u{1F464}" },
  { key: "identity", label: "Identity Documents", icon: "\u{1FAAA}" },
  { key: "rtw", label: "Right to Work", icon: "\u{1F3DB}\uFE0F" },
  { key: "dbs", label: "DBS Information", icon: "\u{1F50D}" },
  { key: "cv", label: "CV / Work History", icon: "\u{1F4C4}" },
  { key: "registration", label: "Professional Registration", icon: "\u{1F3E5}" },
  { key: "references", label: "References", icon: "\u{1F4DD}" },
  { key: "training", label: "Training Certificates", icon: "\u{1F393}" },
];

const CONSENT_STEP = 8;

interface SectionData {
  [key: string]: Record<string, unknown>;
}
interface SectionCompleted {
  [key: string]: boolean;
}

export default function CandidateOnboarding() {
  const { token, logout } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const [submissionStatus, setSubmissionStatus] = useState<string>("draft");
  const [sectionData, setSectionData] = useState<SectionData>({});
  const [sectionCompleted, setSectionCompleted] = useState<SectionCompleted>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [consentChecked, setConsentChecked] = useState(false);
  const [validationErrors, setValidationErrors] = useState<{section: string; message: string}[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [candidateInfo, setCandidateInfo] = useState<Record<string, unknown>>({});
  const [checkStatuses, setCheckStatuses] = useState<Record<string, {status: string; label: string}>>({});
  const [complianceScore, setComplianceScore] = useState(0);
  const [complianceStatus, setComplianceStatus] = useState("pending");

  useEffect(() => {
    loadSubmission();
    loadCandidateInfo();
  }, []);

  const loadCandidateInfo = async () => {
    try {
      if (!token) return;
      const me = await candidatesApi.getMe(token);
      setCandidateInfo(me);
    } catch { /* ignore */ }
  };

  const loadSubmission = async () => {
    try {
      if (!token) return;
      const current = await submissionsApi.getCurrent(token);
      if (current && typeof current === "object" && "id" in current) {
        const sub = current as Record<string, unknown>;
        setSubmissionId(sub.id as string);
        setSubmissionStatus(sub.status as string || "draft");
        const sections = (sub.sections || {}) as Record<string, {data: Record<string, unknown>; completed: boolean}>;
        const data: SectionData = {};
        const completed: SectionCompleted = {};
        for (const [key, val] of Object.entries(sections)) {
          data[key] = val.data || {};
          completed[key] = val.completed || false;
        }
        setSectionData(data);
        setSectionCompleted(completed);
        if (sub.status === "submitted" || sub.status === "processing" || sub.status === "completed") {
          loadStatus(sub.id as string);
        }
      } else {
        const newSub = await submissionsApi.createSubmission(token);
        setSubmissionId(newSub.id as string);
        setSubmissionStatus("draft");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  const loadStatus = async (subId: string) => {
    try {
      if (!token) return;
      const status = await submissionsApi.getStatus(token, subId);
      setCheckStatuses((status.check_statuses || {}) as Record<string, {status: string; label: string}>);
      setComplianceScore(status.compliance_score as number || 0);
      setComplianceStatus(status.compliance_status as string || "pending");
    } catch { /* ignore */ }
  };

  const saveSection = useCallback(async (section: string, data: Record<string, unknown>, completed: boolean) => {
    if (!token || !submissionId) return;
    setSaving(true);
    try {
      await submissionsApi.saveSection(token, submissionId, section, data, completed);
      setSectionData(prev => ({ ...prev, [section]: data }));
      setSectionCompleted(prev => ({ ...prev, [section]: completed }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [token, submissionId]);

  const runValidation = async () => {
    if (!token || !submissionId) return false;
    try {
      const result = await submissionsApi.validate(token, submissionId);
      const errors = (result.errors || []) as {section: string; message: string}[];
      setValidationErrors(errors);
      return errors.length === 0;
    } catch {
      return false;
    }
  };

  const handleSubmit = async () => {
    if (!token || !submissionId || !consentChecked) return;
    setSubmitting(true);
    setError("");
    try {
      const valid = await runValidation();
      if (!valid) { setSubmitting(false); return; }
      await submissionsApi.submitWithConsent(token, submissionId, {
        consent_given: true,
        privacy_policy_version: "1.0",
        terms_version: "1.0",
      });
      setSubmissionStatus("submitted");
      setTimeout(() => { if (submissionId) loadStatus(submissionId); }, 1500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  const goNext = async () => {
    const sec = SECTIONS[currentStep];
    if (sec && sectionData[sec.key]) {
      await saveSection(sec.key, sectionData[sec.key], true);
    }
    setCurrentStep(prev => Math.min(prev + 1, CONSENT_STEP));
  };

  const goPrev = () => setCurrentStep(prev => Math.max(prev - 1, 0));
  const goToStep = (step: number) => setCurrentStep(step);

  const updateField = (section: string, field: string, value: unknown) => {
    setSectionData(prev => ({
      ...prev,
      [section]: { ...(prev[section] || {}), [field]: value },
    }));
  };

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "#f8fafc" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>Loading...</div>
          <p style={{ color: "#64748b" }}>Loading your application...</p>
        </div>
      </div>
    );
  }

  if (submissionStatus !== "draft") {
    return <StatusDashboard
      checkStatuses={checkStatuses}
      complianceScore={complianceScore}
      complianceStatus={complianceStatus}
      submissionStatus={submissionStatus}
      onRefresh={() => submissionId ? loadStatus(submissionId) : undefined}
      onLogout={logout}
    />;
  }

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc" }}>
      <div style={{ background: "#1e293b", color: "white", padding: "16px 24px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>HealthVet AI</h1>
          <p style={{ fontSize: 12, margin: 0, color: "#94a3b8" }}>Candidate Vetting Application</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {saving && <span style={{ fontSize: 12, color: "#fbbf24" }}>Saving...</span>}
          <button onClick={logout} style={{ background: "#ef4444", color: "white", border: "none", borderRadius: 6, padding: "6px 14px", cursor: "pointer", fontSize: 13 }}>Sign Out</button>
        </div>
      </div>

      <div style={{ background: "white", borderBottom: "1px solid #e2e8f0", padding: "12px 24px" }}>
        <div style={{ display: "flex", gap: 4, alignItems: "center", overflowX: "auto" }}>
          {SECTIONS.map((s, i) => (
            <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <button
                onClick={() => goToStep(i)}
                style={{
                  padding: "6px 12px", borderRadius: 16, border: "none", cursor: "pointer", fontSize: 12, fontWeight: 500,
                  background: currentStep === i ? "#3b82f6" : sectionCompleted[s.key] ? "#10b981" : "#e2e8f0",
                  color: currentStep === i || sectionCompleted[s.key] ? "white" : "#64748b",
                  whiteSpace: "nowrap",
                }}
              >
                {s.icon} {s.label}
              </button>
              {i < SECTIONS.length - 1 && <span style={{ color: "#cbd5e1" }}>{"\u2192"}</span>}
            </div>
          ))}
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ color: "#cbd5e1" }}>{"\u2192"}</span>
            <button
              onClick={() => goToStep(CONSENT_STEP)}
              style={{
                padding: "6px 12px", borderRadius: 16, border: "none", cursor: "pointer", fontSize: 12, fontWeight: 500,
                background: currentStep === CONSENT_STEP ? "#3b82f6" : "#e2e8f0",
                color: currentStep === CONSENT_STEP ? "white" : "#64748b",
                whiteSpace: "nowrap",
              }}
            >
              Consent & Submit
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div style={{ margin: "16px 24px", padding: 12, background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, color: "#dc2626", fontSize: 14 }}>
          {error}
          <button onClick={() => setError("")} style={{ float: "right", background: "none", border: "none", cursor: "pointer", color: "#dc2626" }}>X</button>
        </div>
      )}

      <div style={{ maxWidth: 800, margin: "24px auto", padding: "0 24px" }}>
        {currentStep < SECTIONS.length ? (
          <SectionForm
            section={SECTIONS[currentStep]}
            data={sectionData[SECTIONS[currentStep].key] || {}}
            candidateInfo={candidateInfo}
            onUpdate={(field, value) => updateField(SECTIONS[currentStep].key, field, value)}
            onUpdateBulk={(data) => setSectionData(prev => ({ ...prev, [SECTIONS[currentStep].key]: { ...(prev[SECTIONS[currentStep].key] || {}), ...data } }))}
          />
        ) : (
          <ConsentStep
            sectionCompleted={sectionCompleted}
            consentChecked={consentChecked}
            onConsentChange={setConsentChecked}
            validationErrors={validationErrors}
            onValidate={runValidation}
            onSubmit={handleSubmit}
            submitting={submitting}
          />
        )}

        {currentStep < CONSENT_STEP && (
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
            <button
              onClick={goPrev}
              disabled={currentStep === 0}
              style={{ padding: "10px 24px", borderRadius: 8, border: "1px solid #e2e8f0", background: "white", cursor: currentStep === 0 ? "not-allowed" : "pointer", color: "#64748b" }}
            >
              Previous
            </button>
            <button
              onClick={goNext}
              style={{ padding: "10px 24px", borderRadius: 8, border: "none", background: "#3b82f6", color: "white", cursor: "pointer", fontWeight: 600 }}
            >
              Save & Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function StatusDashboard({ checkStatuses, complianceScore, complianceStatus, submissionStatus, onRefresh, onLogout }: {
  checkStatuses: Record<string, {status: string; label: string}>;
  complianceScore: number;
  complianceStatus: string;
  submissionStatus: string;
  onRefresh: () => void;
  onLogout: () => void;
}) {
  const statusColor = (s: string) => {
    if (s === "verified") return { bg: "#dcfce7", color: "#166534", icon: "OK" };
    if (s === "processing") return { bg: "#fef3c7", color: "#92400e", icon: "..." };
    if (s === "review") return { bg: "#fee2e2", color: "#991b1b", icon: "!" };
    return { bg: "#f1f5f9", color: "#475569", icon: "o" };
  };

  const overallColor = complianceStatus === "compliant" ? "#10b981" : complianceStatus === "flagged" ? "#ef4444" : "#f59e0b";

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc" }}>
      <div style={{ background: "#1e293b", color: "white", padding: "16px 24px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>HealthVet AI</h1>
          <p style={{ fontSize: 12, margin: 0, color: "#94a3b8" }}>Application Status</p>
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <button onClick={onRefresh} style={{ background: "#3b82f6", color: "white", border: "none", borderRadius: 6, padding: "6px 14px", cursor: "pointer", fontSize: 13 }}>Refresh</button>
          <button onClick={onLogout} style={{ background: "#ef4444", color: "white", border: "none", borderRadius: 6, padding: "6px 14px", cursor: "pointer", fontSize: 13 }}>Sign Out</button>
        </div>
      </div>

      <div style={{ maxWidth: 700, margin: "32px auto", padding: "0 24px" }}>
        <div style={{ background: submissionStatus === "completed" ? "#dcfce7" : "#eff6ff", border: "1px solid " + (submissionStatus === "completed" ? "#86efac" : "#bfdbfe"), borderRadius: 12, padding: 24, marginBottom: 24, textAlign: "center" }}>
          <h2 style={{ margin: "0 0 4px 0", fontSize: 18, color: "#1e293b" }}>
            {submissionStatus === "completed" ? "Application Complete" : submissionStatus === "processing" ? "Application Processing" : "Application Submitted"}
          </h2>
          <p style={{ margin: 0, color: "#64748b", fontSize: 14 }}>
            {submissionStatus === "completed" ? "All checks have been processed. Your results are being reviewed." : "Your vetting checks are running automatically. Check back for updates."}
          </p>
        </div>

        <div style={{ background: "white", borderRadius: 12, padding: 20, marginBottom: 24, border: "1px solid #e2e8f0", textAlign: "center" }}>
          <h3 style={{ margin: "0 0 12px 0", fontSize: 16, color: "#1e293b" }}>Compliance Score</h3>
          <div style={{ fontSize: 48, fontWeight: 700, color: overallColor }}>{complianceScore}%</div>
          <div style={{ display: "inline-block", marginTop: 8, padding: "4px 16px", borderRadius: 20, background: overallColor + "20", color: overallColor, fontWeight: 600, fontSize: 13, textTransform: "capitalize" as const }}>
            {complianceStatus}
          </div>
        </div>

        <div style={{ background: "white", borderRadius: 12, padding: 20, border: "1px solid #e2e8f0" }}>
          <h3 style={{ margin: "0 0 16px 0", fontSize: 16, color: "#1e293b" }}>Check Status</h3>
          <div style={{ display: "flex", flexDirection: "column" as const, gap: 8 }}>
            {SECTIONS.map(s => {
              const check = checkStatuses[s.key] || { status: "pending", label: s.label + " Pending" };
              const sc = statusColor(check.status);
              return (
                <div key={s.key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", borderRadius: 8, background: "#f8fafc" }}>
                  <span style={{ fontWeight: 500, color: "#334155" }}>{s.icon} {s.label}</span>
                  <span style={{ padding: "4px 12px", borderRadius: 12, background: sc.bg, color: sc.color, fontSize: 13, fontWeight: 500 }}>
                    {sc.icon} {check.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <p style={{ textAlign: "center", color: "#94a3b8", fontSize: 12, marginTop: 24 }}>
          Statuses update automatically. Click Refresh to check for the latest updates.
        </p>
      </div>
    </div>
  );
}

function SectionForm({ section, data, candidateInfo, onUpdate, onUpdateBulk }: {
  section: { key: string; label: string; icon: string };
  data: Record<string, unknown>;
  candidateInfo: Record<string, unknown>;
  onUpdate: (field: string, value: unknown) => void;
  onUpdateBulk: (data: Record<string, unknown>) => void;
}) {
  const inputStyle: React.CSSProperties = { width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 14, boxSizing: "border-box" };
  const labelStyle: React.CSSProperties = { display: "block", fontWeight: 500, marginBottom: 4, color: "#334155", fontSize: 14 };

  useEffect(() => {
    if (section.key === "personal" && candidateInfo && Object.keys(data).length === 0) {
      const prefill: Record<string, unknown> = {};
      for (const field of ["first_name", "last_name", "phone", "date_of_birth", "address_line1", "address_line2", "city", "postcode", "profession"]) {
        if (candidateInfo[field]) prefill[field] = candidateInfo[field];
      }
      if (Object.keys(prefill).length > 0) onUpdateBulk(prefill);
    }
  }, [section.key, candidateInfo]);

  const renderSection = () => {
    switch (section.key) {
      case "personal":
        return (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div><label style={labelStyle}>First Name *</label><input style={inputStyle} value={(data.first_name as string) || ""} onChange={e => onUpdate("first_name", e.target.value)} /></div>
              <div><label style={labelStyle}>Last Name *</label><input style={inputStyle} value={(data.last_name as string) || ""} onChange={e => onUpdate("last_name", e.target.value)} /></div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
              <div><label style={labelStyle}>Phone</label><input style={inputStyle} value={(data.phone as string) || ""} onChange={e => onUpdate("phone", e.target.value)} /></div>
              <div><label style={labelStyle}>Date of Birth</label><input type="date" style={inputStyle} value={(data.date_of_birth as string) || ""} onChange={e => onUpdate("date_of_birth", e.target.value)} /></div>
            </div>
            <div style={{ marginTop: 16 }}><label style={labelStyle}>Address Line 1</label><input style={inputStyle} value={(data.address_line1 as string) || ""} onChange={e => onUpdate("address_line1", e.target.value)} /></div>
            <div style={{ marginTop: 16 }}><label style={labelStyle}>Address Line 2</label><input style={inputStyle} value={(data.address_line2 as string) || ""} onChange={e => onUpdate("address_line2", e.target.value)} /></div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
              <div><label style={labelStyle}>City</label><input style={inputStyle} value={(data.city as string) || ""} onChange={e => onUpdate("city", e.target.value)} /></div>
              <div><label style={labelStyle}>Postcode</label><input style={inputStyle} value={(data.postcode as string) || ""} onChange={e => onUpdate("postcode", e.target.value)} /></div>
            </div>
            <div style={{ marginTop: 16 }}><label style={labelStyle}>Profession</label>
              <select style={inputStyle} value={(data.profession as string) || ""} onChange={e => onUpdate("profession", e.target.value)}>
                <option value="">Select profession...</option>
                <option value="Nurse">Nurse</option><option value="Doctor">Doctor</option><option value="Healthcare Assistant">Healthcare Assistant</option>
                <option value="Midwife">Midwife</option><option value="Physiotherapist">Physiotherapist</option><option value="Paramedic">Paramedic</option>
                <option value="Occupational Therapist">Occupational Therapist</option><option value="Other">Other</option>
              </select>
            </div>
          </>
        );

      case "identity":
        return (
          <>
            <div><label style={labelStyle}>Document Type *</label>
              <select style={inputStyle} value={(data.document_type as string) || ""} onChange={e => onUpdate("document_type", e.target.value)}>
                <option value="">Select document type...</option>
                <option value="passport">Passport</option>
                <option value="driving_licence">Driving Licence</option>
                <option value="national_identity_card">National Identity Card</option>
                <option value="residence_permit">Residence Permit</option>
              </select>
            </div>
            <div style={{ marginTop: 16 }}><label style={labelStyle}>Upload Identity Document *</label>
              <div style={{ border: "2px dashed #d1d5db", borderRadius: 8, padding: 32, textAlign: "center", cursor: "pointer", background: "#f8fafc" }}
                onClick={() => onUpdate("document_file_name", "uploaded_document_" + Date.now() + ".pdf")}>
                {data.document_file_name
                  ? <><span style={{ color: "#10b981", fontSize: 24 }}>OK</span><p style={{ margin: "8px 0 0 0", color: "#10b981" }}>Document uploaded: {data.document_file_name as string}</p></>
                  : <><p style={{ margin: "8px 0 0 0", color: "#64748b" }}>Click to upload your identity document (PDF, JPG, PNG)</p></>}
              </div>
            </div>
            <div style={{ marginTop: 16 }}><label style={labelStyle}>Take / Upload Selfie *</label>
              <div style={{ border: "2px dashed #d1d5db", borderRadius: 8, padding: 32, textAlign: "center", cursor: "pointer", background: "#f8fafc" }}
                onClick={() => onUpdate("selfie_file_name", "selfie_" + Date.now() + ".jpg")}>
                {data.selfie_file_name
                  ? <><span style={{ color: "#10b981", fontSize: 24 }}>OK</span><p style={{ margin: "8px 0 0 0", color: "#10b981" }}>Selfie captured</p></>
                  : <><p style={{ margin: "8px 0 0 0", color: "#64748b" }}>Click to take or upload a selfie photo</p></>}
              </div>
            </div>
          </>
        );

      case "rtw":
        return (
          <>
            <div><label style={labelStyle}>Are you a UK or Irish citizen?</label>
              <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
                <button onClick={() => onUpdate("method", "uk_citizen")} style={{ flex: 1, padding: 14, borderRadius: 8, border: "2px solid " + (data.method === "uk_citizen" ? "#3b82f6" : "#e2e8f0"), background: data.method === "uk_citizen" ? "#eff6ff" : "white", cursor: "pointer", fontWeight: 500 }}>
                  Yes - UK/Irish Citizen
                </button>
                <button onClick={() => onUpdate("method", "share_code")} style={{ flex: 1, padding: 14, borderRadius: 8, border: "2px solid " + (data.method === "share_code" ? "#3b82f6" : "#e2e8f0"), background: data.method === "share_code" ? "#eff6ff" : "white", cursor: "pointer", fontWeight: 500 }}>
                  No - I have a visa/share code
                </button>
              </div>
            </div>
            {data.method === "uk_citizen" && (
              <>
                <div style={{ marginTop: 16 }}><label style={labelStyle}>Document Type</label>
                  <select style={inputStyle} value={(data.document_type as string) || ""} onChange={e => onUpdate("document_type", e.target.value)}>
                    <option value="">Select...</option>
                    <option value="uk_passport">UK Passport</option>
                    <option value="irish_passport">Irish Passport</option>
                    <option value="birth_certificate">UK Birth Certificate</option>
                    <option value="naturalisation_certificate">Naturalisation Certificate</option>
                  </select>
                </div>
                <div style={{ marginTop: 16 }}><label style={labelStyle}>Nationality</label>
                  <select style={inputStyle} value={(data.nationality as string) || "british"} onChange={e => onUpdate("nationality", e.target.value)}>
                    <option value="british">British</option><option value="irish">Irish</option>
                  </select>
                </div>
                <div style={{ marginTop: 16 }}><label style={labelStyle}>National Insurance Number</label>
                  <input style={inputStyle} placeholder="e.g. AB 12 34 56 C" value={(data.ni_number as string) || ""} onChange={e => onUpdate("ni_number", e.target.value)} />
                </div>
              </>
            )}
            {data.method === "share_code" && (
              <div style={{ marginTop: 16 }}>
                <label style={labelStyle}>Home Office Share Code *</label>
                <input style={inputStyle} placeholder="Enter your 9-character share code" value={(data.share_code as string) || ""} onChange={e => onUpdate("share_code", e.target.value)} />
                <p style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>Get your share code from gov.uk/prove-right-to-work</p>
              </div>
            )}
          </>
        );

      case "dbs":
        return (
          <>
            <div><label style={labelStyle}>DBS Check Type</label>
              <select style={inputStyle} value={(data.check_type as string) || "enhanced"} onChange={e => onUpdate("check_type", e.target.value)}>
                <option value="enhanced">Enhanced DBS Check</option>
                <option value="enhanced_barred">Enhanced DBS with Barred List</option>
                <option value="standard">Standard DBS Check</option>
                <option value="basic">Basic DBS Check</option>
              </select>
            </div>
            <div style={{ marginTop: 16 }}><label style={labelStyle}>Existing DBS Certificate Number (if any)</label>
              <input style={inputStyle} placeholder="Enter existing certificate number" value={(data.certificate_number as string) || ""} onChange={e => onUpdate("certificate_number", e.target.value)} />
            </div>
            <div style={{ marginTop: 16 }}><label style={labelStyle}>Registered on DBS Update Service?</label>
              <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
                <button onClick={() => onUpdate("update_service", true)} style={{ padding: "10px 24px", borderRadius: 8, border: "2px solid " + (data.update_service === true ? "#10b981" : "#e2e8f0"), background: data.update_service === true ? "#dcfce7" : "white", cursor: "pointer" }}>Yes</button>
                <button onClick={() => onUpdate("update_service", false)} style={{ padding: "10px 24px", borderRadius: 8, border: "2px solid " + (data.update_service === false ? "#ef4444" : "#e2e8f0"), background: data.update_service === false ? "#fee2e2" : "white", cursor: "pointer" }}>No</button>
              </div>
            </div>
            <div style={{ marginTop: 16, padding: 16, background: "#eff6ff", borderRadius: 8, fontSize: 13, color: "#1e40af" }}>
              <strong>Note:</strong> An Enhanced DBS check will be submitted automatically when you complete this application. You will receive a certificate by post within 2-6 weeks.
            </div>
          </>
        );

      case "cv":
        return (
          <>
            <div><label style={labelStyle}>Upload CV (PDF, DOCX, TXT)</label>
              <div style={{ border: "2px dashed #d1d5db", borderRadius: 8, padding: 32, textAlign: "center", cursor: "pointer", background: "#f8fafc" }}
                onClick={() => onUpdate("cv_file_name", "cv_upload_" + Date.now() + ".pdf")}>
                {data.cv_file_name
                  ? <><span style={{ color: "#10b981", fontSize: 24 }}>OK</span><p style={{ margin: "8px 0 0 0", color: "#10b981" }}>CV uploaded: {data.cv_file_name as string}</p></>
                  : <p style={{ margin: "8px 0 0 0", color: "#64748b" }}>Click to upload your CV</p>}
              </div>
            </div>
            <div style={{ marginTop: 16 }}><label style={labelStyle}>Or paste CV text</label>
              <textarea style={{ ...inputStyle, minHeight: 120, fontFamily: "inherit" }} placeholder="Paste your CV content here..." value={(data.cv_text as string) || ""} onChange={e => onUpdate("cv_text", e.target.value)} />
            </div>
            <div style={{ marginTop: 24 }}>
              <h4 style={{ margin: "0 0 12px 0", color: "#334155" }}>Employment History (Last 5 Years)</h4>
              <p style={{ fontSize: 13, color: "#64748b", margin: "0 0 12px 0" }}>Add your employment history. Include verifier details for each employer.</p>
              <EmploymentEntries entries={(data.employment_entries as Record<string, unknown>[]) || []} onChange={(entries) => onUpdate("employment_entries", entries)} />
            </div>
          </>
        );

      case "registration":
        return (
          <>
            <div><label style={labelStyle}>Registration Body *</label>
              <select style={inputStyle} value={(data.registration_body as string) || ""} onChange={e => onUpdate("registration_body", e.target.value)}>
                <option value="">Select registration body...</option>
                <option value="NMC">NMC - Nursing and Midwifery Council</option>
                <option value="GMC">GMC - General Medical Council</option>
                <option value="HCPC">HCPC - Health and Care Professions Council</option>
                <option value="GPhC">GPhC - General Pharmaceutical Council</option>
              </select>
            </div>
            <div style={{ marginTop: 16 }}><label style={labelStyle}>Registration / PIN Number *</label>
              <input style={inputStyle} placeholder="Enter your registration number" value={(data.registration_number as string) || ""} onChange={e => onUpdate("registration_number", e.target.value)} />
            </div>
            <div style={{ marginTop: 16, padding: 16, background: "#eff6ff", borderRadius: 8, fontSize: 13, color: "#1e40af" }}>
              <strong>Note:</strong> Your registration will be verified against the public register automatically.
            </div>
          </>
        );

      case "references":
        return (
          <>
            <p style={{ fontSize: 14, color: "#64748b", margin: "0 0 16px 0" }}>Provide at least 2 professional references. Reference requests will be sent automatically.</p>
            <RefereeEntries referees={(data.referees as Record<string, unknown>[]) || []} onChange={(refs) => onUpdate("referees", refs)} />
          </>
        );

      case "training":
        return (
          <>
            <p style={{ fontSize: 14, color: "#64748b", margin: "0 0 16px 0" }}>Add your training certificates (mandatory training, CPD, specialist certifications).</p>
            <CertificateEntries certificates={(data.certificates as Record<string, unknown>[]) || []} onChange={(certs) => onUpdate("certificates", certs)} />
          </>
        );

      default:
        return <p>Unknown section</p>;
    }
  };

  return (
    <div style={{ background: "white", borderRadius: 12, padding: 24, border: "1px solid #e2e8f0" }}>
      <h2 style={{ margin: "0 0 4px 0", fontSize: 20, color: "#1e293b" }}>{section.icon} {section.label}</h2>
      <p style={{ margin: "0 0 20px 0", fontSize: 14, color: "#64748b" }}>
        {section.key === "personal" && "Enter your personal details below."}
        {section.key === "identity" && "Upload your identity document and a selfie for verification."}
        {section.key === "rtw" && "Provide evidence of your right to work in the UK."}
        {section.key === "dbs" && "Provide DBS check information."}
        {section.key === "cv" && "Upload your CV and employment history."}
        {section.key === "registration" && "Enter your professional registration details."}
        {section.key === "references" && "Provide your professional references."}
        {section.key === "training" && "Add your training and certification records."}
      </p>
      {renderSection()}
    </div>
  );
}

function ConsentStep({ sectionCompleted, consentChecked, onConsentChange, validationErrors, onValidate, onSubmit, submitting }: {
  sectionCompleted: SectionCompleted;
  consentChecked: boolean;
  onConsentChange: (v: boolean) => void;
  validationErrors: {section: string; message: string}[];
  onValidate: () => Promise<boolean>;
  onSubmit: () => void;
  submitting: boolean;
}) {
  const completedCount = SECTIONS.filter(s => sectionCompleted[s.key]).length;

  return (
    <div style={{ background: "white", borderRadius: 12, padding: 24, border: "1px solid #e2e8f0" }}>
      <h2 style={{ margin: "0 0 16px 0", fontSize: 20, color: "#1e293b" }}>Review & Consent</h2>

      <div style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: 15, color: "#334155", margin: "0 0 12px 0" }}>Sections Completed: {completedCount}/{SECTIONS.length}</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {SECTIONS.map(s => (
            <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", borderRadius: 8, background: sectionCompleted[s.key] ? "#dcfce7" : "#fef2f2" }}>
              <span>{sectionCompleted[s.key] ? "OK" : "o"}</span>
              <span style={{ fontSize: 13, color: sectionCompleted[s.key] ? "#166534" : "#991b1b" }}>{s.icon} {s.label}</span>
            </div>
          ))}
        </div>
      </div>

      {validationErrors.length > 0 && (
        <div style={{ marginBottom: 20, padding: 16, background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8 }}>
          <h4 style={{ margin: "0 0 8px 0", color: "#dc2626", fontSize: 14 }}>Please fix the following before submitting:</h4>
          {validationErrors.map((e, i) => (
            <div key={i} style={{ fontSize: 13, color: "#991b1b", padding: "4px 0" }}>- [{e.section}] {e.message}</div>
          ))}
        </div>
      )}

      <div style={{ marginBottom: 20, padding: 16, background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0", maxHeight: 200, overflowY: "auto" as const }}>
        <h4 style={{ margin: "0 0 8px 0", fontSize: 14, color: "#1e293b" }}>Privacy Policy & Terms of Service (v1.0)</h4>
        <div style={{ fontSize: 12, color: "#64748b", lineHeight: 1.6 }}>
          <p><strong>Data Processing:</strong> By submitting this application, you consent to HealthVet AI processing your personal data for the purpose of employment vetting and compliance checks. This includes identity verification, DBS checks, right to work verification, reference collection, and professional registration verification.</p>
          <p><strong>Data Controller:</strong> The agency that invited you to complete this vetting process acts as the data controller. HealthVet AI acts as the data processor on behalf of the agency.</p>
          <p><strong>Data Retention:</strong> Your data will be retained for the duration required by CQC regulations and applicable employment law. You may request deletion of your data at any time, subject to legal retention requirements.</p>
          <p><strong>Your Rights:</strong> Under GDPR, you have the right to: access your data, request correction of inaccurate data, request deletion (right to be forgotten), data portability, and to lodge a complaint with the ICO.</p>
          <p><strong>Third Parties:</strong> Your data may be shared with: Onfido (identity verification), DBS providers (criminal record checks), the Home Office (right to work), professional registration bodies (NMC, GMC, HCPC), and your referees/former employers.</p>
          <p><strong>DBS Consent:</strong> By proceeding, you specifically consent to an Enhanced DBS check being carried out, which may include checks against the children and/or adults barred lists as required by the role.</p>
        </div>
      </div>

      <div style={{ marginBottom: 24, padding: 16, background: "#eff6ff", borderRadius: 8, border: "1px solid #bfdbfe" }}>
        <label style={{ display: "flex", gap: 12, cursor: "pointer", alignItems: "flex-start" }}>
          <input type="checkbox" checked={consentChecked} onChange={e => onConsentChange(e.target.checked)} style={{ marginTop: 4, width: 20, height: 20, accentColor: "#3b82f6" }} />
          <span style={{ fontSize: 14, color: "#1e293b", lineHeight: 1.5 }}>
            <strong>I confirm that:</strong> All information provided is accurate and complete. I have read and agree to the Privacy Policy and Terms of Service. I consent to the processing of my personal data for employment vetting purposes, including DBS checks, identity verification, and all other compliance checks listed above. I understand my rights under GDPR.
          </span>
        </label>
      </div>

      <div style={{ display: "flex", gap: 12 }}>
        <button onClick={() => onValidate()} style={{ flex: 1, padding: "12px 24px", borderRadius: 8, border: "1px solid #e2e8f0", background: "white", cursor: "pointer", fontWeight: 500 }}>
          Validate Application
        </button>
        <button
          onClick={onSubmit}
          disabled={!consentChecked || submitting}
          style={{ flex: 1, padding: "12px 24px", borderRadius: 8, border: "none", background: consentChecked ? "#10b981" : "#d1d5db", color: "white", cursor: consentChecked ? "pointer" : "not-allowed", fontWeight: 700, fontSize: 15 }}
        >
          {submitting ? "Submitting..." : "Submit Application"}
        </button>
      </div>
    </div>
  );
}

function EmploymentEntries({ entries, onChange }: { entries: Record<string, unknown>[]; onChange: (e: Record<string, unknown>[]) => void }) {
  const inputStyle: React.CSSProperties = { width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, boxSizing: "border-box" };
  const addEntry = () => onChange([...entries, { employer_name: "", job_title: "", start_date: "", end_date: "", reason_for_leaving: "", verifier_name: "", verifier_email: "", verifier_job_title: "" }]);
  const updateEntry = (i: number, field: string, value: string) => { const e = [...entries]; e[i] = { ...e[i], [field]: value }; onChange(e); };
  const removeEntry = (i: number) => onChange(entries.filter((_, idx) => idx !== i));

  return (
    <div>
      {entries.map((entry, i) => (
        <div key={i} style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 16, marginBottom: 12, background: "#fafafa" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <strong style={{ fontSize: 14 }}>Employment {i + 1}</strong>
            <button onClick={() => removeEntry(i)} style={{ background: "#fee2e2", color: "#dc2626", border: "none", borderRadius: 4, padding: "4px 8px", cursor: "pointer", fontSize: 12 }}>Remove</button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>Employer Name</label><input style={inputStyle} value={(entry.employer_name as string) || ""} onChange={e => updateEntry(i, "employer_name", e.target.value)} /></div>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>Job Title</label><input style={inputStyle} value={(entry.job_title as string) || ""} onChange={e => updateEntry(i, "job_title", e.target.value)} /></div>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>Start Date</label><input type="date" style={inputStyle} value={(entry.start_date as string) || ""} onChange={e => updateEntry(i, "start_date", e.target.value)} /></div>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>End Date</label><input type="date" style={inputStyle} value={(entry.end_date as string) || ""} onChange={e => updateEntry(i, "end_date", e.target.value)} /></div>
            <div style={{ gridColumn: "1 / -1" }}><label style={{ fontSize: 12, color: "#64748b" }}>Reason for Leaving</label><input style={inputStyle} value={(entry.reason_for_leaving as string) || ""} onChange={e => updateEntry(i, "reason_for_leaving", e.target.value)} /></div>
          </div>
          <div style={{ marginTop: 12, padding: 12, background: "#eff6ff", borderRadius: 6 }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: "#1e40af", margin: "0 0 8px 0" }}>Employer Verifier Details</p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
              <div><label style={{ fontSize: 12, color: "#64748b" }}>Verifier Name</label><input style={inputStyle} value={(entry.verifier_name as string) || ""} onChange={e => updateEntry(i, "verifier_name", e.target.value)} /></div>
              <div><label style={{ fontSize: 12, color: "#64748b" }}>Verifier Email</label><input style={inputStyle} value={(entry.verifier_email as string) || ""} onChange={e => updateEntry(i, "verifier_email", e.target.value)} /></div>
              <div><label style={{ fontSize: 12, color: "#64748b" }}>Verifier Job Title</label><input style={inputStyle} value={(entry.verifier_job_title as string) || ""} onChange={e => updateEntry(i, "verifier_job_title", e.target.value)} /></div>
            </div>
          </div>
        </div>
      ))}
      <button onClick={addEntry} style={{ width: "100%", padding: 12, borderRadius: 8, border: "2px dashed #d1d5db", background: "white", cursor: "pointer", color: "#3b82f6", fontWeight: 500, fontSize: 14 }}>
        + Add Employment Entry
      </button>
    </div>
  );
}

function RefereeEntries({ referees, onChange }: { referees: Record<string, unknown>[]; onChange: (r: Record<string, unknown>[]) => void }) {
  const inputStyle: React.CSSProperties = { width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, boxSizing: "border-box" };
  const addRef = () => onChange([...referees, { name: "", email: "", organisation: "", job_title: "" }]);
  const updateRef = (i: number, field: string, value: string) => { const r = [...referees]; r[i] = { ...r[i], [field]: value }; onChange(r); };
  const removeRef = (i: number) => onChange(referees.filter((_, idx) => idx !== i));

  useEffect(() => {
    if (referees.length === 0) {
      onChange([{ name: "", email: "", organisation: "", job_title: "" }, { name: "", email: "", organisation: "", job_title: "" }]);
    }
  }, []);

  return (
    <div>
      {referees.map((ref, i) => (
        <div key={i} style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 16, marginBottom: 12, background: "#fafafa" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <strong style={{ fontSize: 14 }}>Reference {i + 1} {i < 2 ? "*" : ""}</strong>
            {i >= 2 && <button onClick={() => removeRef(i)} style={{ background: "#fee2e2", color: "#dc2626", border: "none", borderRadius: 4, padding: "4px 8px", cursor: "pointer", fontSize: 12 }}>Remove</button>}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>Referee Name *</label><input style={inputStyle} value={(ref.name as string) || ""} onChange={e => updateRef(i, "name", e.target.value)} /></div>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>Referee Email *</label><input type="email" style={inputStyle} value={(ref.email as string) || ""} onChange={e => updateRef(i, "email", e.target.value)} /></div>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>Organisation</label><input style={inputStyle} value={(ref.organisation as string) || ""} onChange={e => updateRef(i, "organisation", e.target.value)} /></div>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>Job Title</label><input style={inputStyle} value={(ref.job_title as string) || ""} onChange={e => updateRef(i, "job_title", e.target.value)} /></div>
          </div>
        </div>
      ))}
      <button onClick={addRef} style={{ width: "100%", padding: 12, borderRadius: 8, border: "2px dashed #d1d5db", background: "white", cursor: "pointer", color: "#3b82f6", fontWeight: 500, fontSize: 14 }}>
        + Add Another Reference
      </button>
    </div>
  );
}

function CertificateEntries({ certificates, onChange }: { certificates: Record<string, unknown>[]; onChange: (c: Record<string, unknown>[]) => void }) {
  const inputStyle: React.CSSProperties = { width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, boxSizing: "border-box" };
  const addCert = () => onChange([...certificates, { certificate_name: "", category: "mandatory", provider: "", issue_date: "", expiry_date: "", certificate_ref: "" }]);
  const updateCert = (i: number, field: string, value: string) => { const c = [...certificates]; c[i] = { ...c[i], [field]: value }; onChange(c); };
  const removeCert = (i: number) => onChange(certificates.filter((_, idx) => idx !== i));

  return (
    <div>
      {certificates.map((cert, i) => (
        <div key={i} style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 16, marginBottom: 12, background: "#fafafa" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <strong style={{ fontSize: 14 }}>Certificate {i + 1}</strong>
            <button onClick={() => removeCert(i)} style={{ background: "#fee2e2", color: "#dc2626", border: "none", borderRadius: 4, padding: "4px 8px", cursor: "pointer", fontSize: 12 }}>Remove</button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>Certificate Name *</label><input style={inputStyle} value={(cert.certificate_name as string) || ""} onChange={e => updateCert(i, "certificate_name", e.target.value)} /></div>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>Category</label>
              <select style={inputStyle} value={(cert.category as string) || "mandatory"} onChange={e => updateCert(i, "category", e.target.value)}>
                <option value="mandatory">Mandatory Training</option><option value="specialist">Specialist</option><option value="cpd">CPD</option><option value="other">Other</option>
              </select>
            </div>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>Provider</label><input style={inputStyle} value={(cert.provider as string) || ""} onChange={e => updateCert(i, "provider", e.target.value)} /></div>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>Certificate Ref</label><input style={inputStyle} value={(cert.certificate_ref as string) || ""} onChange={e => updateCert(i, "certificate_ref", e.target.value)} /></div>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>Issue Date</label><input type="date" style={inputStyle} value={(cert.issue_date as string) || ""} onChange={e => updateCert(i, "issue_date", e.target.value)} /></div>
            <div><label style={{ fontSize: 12, color: "#64748b" }}>Expiry Date</label><input type="date" style={inputStyle} value={(cert.expiry_date as string) || ""} onChange={e => updateCert(i, "expiry_date", e.target.value)} /></div>
          </div>
        </div>
      ))}
      <button onClick={addCert} style={{ width: "100%", padding: 12, borderRadius: 8, border: "2px dashed #d1d5db", background: "white", cursor: "pointer", color: "#3b82f6", fontWeight: 500, fontSize: 14 }}>
        + Add Training Certificate
      </button>
    </div>
  );
}
