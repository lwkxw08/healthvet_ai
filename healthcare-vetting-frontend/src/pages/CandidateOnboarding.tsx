import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { submissionsApi, candidatesApi, trustidApi } from "../api/client";
import { LogOut, RefreshCw, ChevronRight, CheckCircle, XCircle, Clock, AlertTriangle, Loader2 } from "lucide-react";

const SECTIONS = [
  { key: "personal", label: "Personal Details" },
  { key: "identity", label: "Identity Documents" },
  { key: "rtw", label: "Right to Work" },
  { key: "dbs", label: "DBS Information" },
  { key: "cv", label: "CV / Work History" },
  { key: "registration", label: "Professional Registration" },
  { key: "references", label: "References" },
  { key: "training", label: "Training Certificates" },
];

// CONSENT_STEP is now dynamically computed as activeSections.length

interface SectionData {
  [key: string]: Record<string, unknown>;
}
interface SectionCompleted {
  [key: string]: boolean;
}

function getRevetTokenFromURL(): string | null {
  const params = new URLSearchParams(window.location.search);
  return params.get("revet");
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

  // TrustID state
  const [trustidConfig, setTrustidConfig] = useState<Record<string, Record<string, unknown>>>({});
  const [trustidChecks, setTrustidChecks] = useState<Record<string, unknown>[]>([]);
  const [trustidSubmitted, setTrustidSubmitted] = useState(false);
  const [submittingTrustid, setSubmittingTrustid] = useState(false);

  // Re-vet state
  const [revetToken] = useState<string | null>(getRevetTokenFromURL());
  const [revetInfo, setRevetInfo] = useState<{agency_name: string; sections: string[]; candidate_name: string} | null>(null);
  const [revetSections, setRevetSections] = useState<{key: string; label: string}[]>([]);

  useEffect(() => {
    if (revetToken) {
      loadRevetInfo();
    } else {
      loadSubmission();
    }
    loadCandidateInfo();
    loadTrustidData();
  }, []);

  const loadRevetInfo = async () => {
    try {
      const info = await submissionsApi.getRevetInfo(revetToken as string);
      const ri = info as {agency_name: string; sections: string[]; candidate_name: string};
      setRevetInfo(ri);
      const filteredSections = SECTIONS.filter(s => ri.sections.includes(s.key));
      setRevetSections(filteredSections);
      // Create a re-vet submission
      if (token) {
        const newSub = await submissionsApi.createSubmission(token, {
          submission_type: "partial",
          sections_requested: ri.sections,
          revet_token: revetToken as string,
        });
        setSubmissionId(newSub.id as string);
        setSubmissionStatus("draft");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Invalid or expired re-vet link");
    } finally {
      setLoading(false);
    }
  };

  const loadCandidateInfo = async () => {
    try {
      if (!token) return;
      const me = await candidatesApi.getMe(token);
      setCandidateInfo(me);
    } catch { /* ignore */ }
  };

  const loadTrustidData = async () => {
    if (!token) return;
    try {
      const config = await trustidApi.getConfig(token);
      setTrustidConfig(config);
      const candidateId = (candidateInfo.id as string) || "";
      if (candidateId) {
        const checks = await trustidApi.getCandidateChecks(token, candidateId).catch(() => []);
        setTrustidChecks(checks);
      }
    } catch { /* ignore */ }
  };

  const isManualMode = (checkType: string) => {
    const cfg = trustidConfig[checkType];
    if (!cfg) return true; // Default to manual
    return cfg.submission_mode === "manual";
  };

  const submitTrustidChecks = async () => {
    if (!token) return;
    setSubmittingTrustid(true);
    try {
      const candidateId = (candidateInfo.id as string) || "";
      await trustidApi.submitChecks(token, {
        candidate_id: candidateId,
        candidate_name: `${candidateInfo.first_name || ""} ${candidateInfo.last_name || ""}`.trim() || undefined,
        candidate_email: candidateInfo.email as string || undefined,
        candidate_dob: candidateInfo.date_of_birth as string || undefined,
      });
      setTrustidSubmitted(true);
      setError("");
      await loadTrustidData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit TrustID checks");
    } finally { setSubmittingTrustid(false); }
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
          const newSub = await submissionsApi.createSubmission(token, {});
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

  const activeSections = revetToken && revetSections.length > 0 ? revetSections : SECTIONS;
  const activeConsentStep = activeSections.length;

  const goNext = async () => {
    const sec = activeSections[currentStep];
    if (sec) {
      const data = sectionData[sec.key] || {};
      // For TrustID manual-mode sections, mark with a flag so backend knows to skip field validation
      const isTrustidManual = (
        (sec.key === "identity" && isManualMode("identity_verification")) ||
        (sec.key === "rtw" && isManualMode("right_to_work")) ||
        (sec.key === "dbs" && isManualMode("dbs_check"))
      );
      const saveData = isTrustidManual ? { ...data, trustid_manual: true } : data;
      await saveSection(sec.key, saveData, true);
    }
    setCurrentStep(prev => Math.min(prev + 1, activeConsentStep));
  };

  const goPrev = () => setCurrentStep(prev => Math.max(prev - 1, 0));
  const goToStep = (step: number) => setCurrentStep(Math.min(step, activeConsentStep));

  const updateField = (section: string, field: string, value: unknown) => {
    setSectionData(prev => ({
      ...prev,
      [section]: { ...(prev[section] || {}), [field]: value },
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-900">
        <div className="text-center">
          <Loader2 className="text-blue-400 animate-spin mx-auto mb-4" size={48} />
          <p className="text-slate-400">Loading your application...</p>
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
      submissionId={submissionId}
      token={token}
      sectionData={sectionData}
      candidateInfo={candidateInfo}
      isManualMode={isManualMode}
      trustidChecks={trustidChecks}
      trustidSubmitted={trustidSubmitted}
      submittingTrustid={submittingTrustid}
      onSubmitTrustid={submitTrustidChecks}
      onRefresh={() => submissionId ? loadStatus(submissionId) : undefined}
      onLogout={logout}
    />;
  }

  return (
    <div className="min-h-screen bg-slate-900">
      <header className="bg-slate-800/80 border-b border-slate-700 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img src="/viper-logo.png" alt="Viper AI" className="h-8" />
          <div>
            <h1 className="text-xl font-bold text-white">Viper AI</h1>
            <p className="text-xs text-slate-400">Candidate Vetting Application</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {saving && <span className="text-xs text-yellow-400 flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> Saving...</span>}
          <button onClick={logout} className="bg-red-600 hover:bg-red-700 text-white border-none rounded-lg px-4 py-1.5 cursor-pointer text-sm flex items-center gap-1">
            <LogOut size={14} /> Sign Out
          </button>
        </div>
      </header>

      {revetInfo && (
        <div className="bg-amber-500/10 border-b border-amber-500/30 px-6 py-3">
          <p className="text-amber-300 text-sm">
            <strong>Re-Vet Request</strong> from <span className="text-white font-semibold">{revetInfo.agency_name}</span> — 
            Please complete the following sections: {revetInfo.sections.map(s => s.replace(/_/g, ' ')).join(', ')}
          </p>
        </div>
      )}

      <div className="bg-slate-800/50 border-b border-slate-700 px-6 py-3">
        <div className="flex gap-1 items-center overflow-x-auto">
          {activeSections.map((s, i) => (
            <div key={s.key} className="flex items-center gap-1">
              <button
                onClick={() => goToStep(i)}
                className={`px-3 py-1.5 rounded-full border-none cursor-pointer text-xs font-medium whitespace-nowrap transition-all ${
                  currentStep === i
                    ? "bg-blue-600 text-white"
                    : sectionCompleted[s.key]
                    ? "bg-emerald-600/30 text-emerald-300"
                    : "bg-slate-700 text-slate-400 hover:text-white hover:bg-slate-600"
                }`}
              >
                {sectionCompleted[s.key] && currentStep !== i ? <span className="mr-1">&#10003;</span> : null}
                {s.label}
              </button>
              {i < activeSections.length - 1 && <ChevronRight size={14} className="text-slate-600" />}
            </div>
          ))}
          <div className="flex items-center gap-1">
            <ChevronRight size={14} className="text-slate-600" />
            <button
              onClick={() => goToStep(activeConsentStep)}
              className={`px-3 py-1.5 rounded-full border-none cursor-pointer text-xs font-medium whitespace-nowrap transition-all ${
                currentStep === activeConsentStep
                  ? "bg-blue-600 text-white"
                  : "bg-slate-700 text-slate-400 hover:text-white hover:bg-slate-600"
              }`}
            >
              Consent & Submit
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="mx-6 mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError("")} className="text-red-400 hover:text-red-300 bg-transparent border-none cursor-pointer text-sm">&#10005;</button>
        </div>
      )}

      <div className="max-w-3xl mx-auto py-6 px-6">
        {currentStep < activeSections.length ? (
          <SectionForm
            section={activeSections[currentStep]}
            data={sectionData[activeSections[currentStep].key] || {}}
            candidateInfo={candidateInfo}
            onUpdate={(field, value) => updateField(activeSections[currentStep].key, field, value)}
            onUpdateBulk={(data) => setSectionData(prev => ({ ...prev, [activeSections[currentStep].key]: { ...(prev[activeSections[currentStep].key] || {}), ...data } }))}
            isManualMode={isManualMode}
            trustidChecks={trustidChecks}
            trustidSubmitted={trustidSubmitted}
            submittingTrustid={submittingTrustid}
            onSubmitTrustid={submitTrustidChecks}
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

        {currentStep < activeConsentStep && (
          <div className="flex justify-between mt-6">
            <button
              onClick={goPrev}
              disabled={currentStep === 0}
              className={`px-6 py-2.5 rounded-lg border text-sm font-medium transition-all ${
                currentStep === 0
                  ? "border-slate-700 bg-slate-800 text-slate-600 cursor-not-allowed"
                  : "border-slate-600 bg-slate-800 text-slate-300 hover:bg-slate-700 cursor-pointer"
              }`}
            >
              Previous
            </button>
            <button
              onClick={goNext}
              className="px-6 py-2.5 rounded-lg border-none bg-blue-600 hover:bg-blue-700 text-white cursor-pointer font-semibold text-sm transition-all"
            >
              Save & Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// Sections that candidates can update after submission
const EDITABLE_SECTIONS = new Set(["references", "training", "cv", "employment"]);

function StatusDashboard({ checkStatuses, complianceScore, complianceStatus, submissionStatus, submissionId, token, sectionData, candidateInfo, isManualMode, trustidChecks, trustidSubmitted, submittingTrustid, onSubmitTrustid, onRefresh, onLogout }: {
  checkStatuses: Record<string, {status: string; label: string}>;
  complianceScore: number;
  complianceStatus: string;
  submissionStatus: string;
  submissionId: string | null;
  token: string | null;
  sectionData: SectionData;
  candidateInfo: Record<string, unknown>;
  isManualMode: (checkType: string) => boolean;
  trustidChecks: Record<string, unknown>[];
  trustidSubmitted: boolean;
  submittingTrustid: boolean;
  onSubmitTrustid: () => void;
  onRefresh: () => void;
  onLogout: () => void;
}) {
  const [editingSection, setEditingSection] = useState<string | null>(null);
  const [editData, setEditData] = useState<Record<string, unknown>>({});
  const [savingUpdate, setSavingUpdate] = useState(false);
  const [updateMessage, setUpdateMessage] = useState("");

  const StatusIcon = ({ status }: { status: string }) => {
    if (status === "verified") return <CheckCircle size={18} className="text-green-400" />;
    if (status === "processing") return <Clock size={18} className="text-yellow-400 animate-pulse" />;
    if (status === "review") return <AlertTriangle size={18} className="text-red-400" />;
    return <Clock size={18} className="text-slate-500" />;
  };

  const statusBadgeClass = (status: string) => {
    if (status === "verified") return "bg-green-500/20 text-green-400 border-green-500/30";
    if (status === "processing") return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
    if (status === "review") return "bg-red-500/20 text-red-400 border-red-500/30";
    return "bg-slate-700 text-slate-400 border-slate-600";
  };

  const startEditing = (sectionKey: string) => {
    setEditData(sectionData[sectionKey] || {});
    setEditingSection(sectionKey);
    setUpdateMessage("");
  };

  const cancelEditing = () => {
    setEditingSection(null);
    setEditData({});
    setUpdateMessage("");
  };

  const saveUpdate = async () => {
    if (!token || !submissionId || !editingSection) return;
    setSavingUpdate(true);
    setUpdateMessage("");
    try {
      const result = await submissionsApi.updateSection(token, submissionId, editingSection, editData);
      setUpdateMessage((result.message as string) || "Section updated successfully.");
      setEditingSection(null);
      setEditData({});
      onRefresh();
    } catch (e: unknown) {
      setUpdateMessage(e instanceof Error ? e.message : "Update failed");
    } finally {
      setSavingUpdate(false);
    }
  };

  const updateEditField = (field: string, value: unknown) => {
    setEditData(prev => ({ ...prev, [field]: value }));
  };

  const overallColor = complianceStatus === "compliant" ? "text-green-400" : complianceStatus === "flagged" ? "text-red-400" : "text-yellow-400";
  const overallBg = complianceStatus === "compliant" ? "bg-green-500/20 border-green-500/30 text-green-400" : complianceStatus === "flagged" ? "bg-red-500/20 border-red-500/30 text-red-400" : "bg-yellow-500/20 border-yellow-500/30 text-yellow-400";

  return (
    <div className="min-h-screen bg-slate-900">
      <header className="bg-slate-800/80 border-b border-slate-700 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img src="/viper-logo.png" alt="Viper AI" className="h-8" />
          <div>
            <h1 className="text-xl font-bold text-white">Viper AI</h1>
            <p className="text-xs text-slate-400">Application Status</p>
          </div>
        </div>
        <div className="flex gap-3">
          <button onClick={onRefresh} className="bg-blue-600 hover:bg-blue-700 text-white border-none rounded-lg px-4 py-1.5 cursor-pointer text-sm flex items-center gap-1">
            <RefreshCw size={14} /> Refresh
          </button>
          <button onClick={onLogout} className="bg-red-600 hover:bg-red-700 text-white border-none rounded-lg px-4 py-1.5 cursor-pointer text-sm flex items-center gap-1">
            <LogOut size={14} /> Sign Out
          </button>
        </div>
      </header>

      <div className="max-w-2xl mx-auto py-8 px-6">
        <div className={`rounded-xl border p-6 mb-6 text-center ${
          submissionStatus === "completed" ? "bg-green-500/10 border-green-500/30" : "bg-blue-500/10 border-blue-500/30"
        }`}>
          <h2 className="text-lg font-bold text-white mb-1">
            {submissionStatus === "completed" ? "Application Complete" : submissionStatus === "processing" ? "Application Processing" : "Application Submitted"}
          </h2>
          <p className="text-slate-400 text-sm">
            {submissionStatus === "completed" ? "All checks have been processed. Your results are being reviewed." : "Your vetting checks are running automatically. Check back for updates."}
          </p>
        </div>

        <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6 mb-6 text-center">
          <h3 className="text-md font-semibold text-white mb-3">Compliance Score</h3>
          <div className={`text-5xl font-bold ${overallColor}`}>{Number(complianceScore).toFixed(1)}%</div>
          <div className={`inline-block mt-3 px-4 py-1 rounded-full border text-sm font-semibold capitalize ${overallBg}`}>
            {complianceStatus}
          </div>
        </div>

        {updateMessage && (
          <div className={`mb-4 p-3 rounded-lg border text-sm ${
            updateMessage.includes("failed") || updateMessage.includes("error")
              ? "bg-red-500/10 border-red-500/30 text-red-400"
              : "bg-green-500/10 border-green-500/30 text-green-400"
          }`}>
            {updateMessage}
            <button onClick={() => setUpdateMessage("")} className="float-right text-current bg-transparent border-none cursor-pointer">&#10005;</button>
          </div>
        )}

        <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
          <h3 className="text-md font-semibold text-white mb-4">Check Status</h3>
          <div className="flex flex-col gap-2">
            {SECTIONS.map(s => {
              const check = checkStatuses[s.key] || { status: "pending", label: s.label + " Pending" };
              const isEditable = EDITABLE_SECTIONS.has(s.key);
              const isCurrentlyEditing = editingSection === s.key;
              return (
                <div key={s.key}>
                  <div className="flex justify-between items-center p-3 rounded-lg bg-slate-700/50">
                    <span className="text-sm font-medium text-slate-200">{s.label}</span>
                    <div className="flex items-center gap-2">
                      <span className={`flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-medium ${statusBadgeClass(check.status)}`}>
                        <StatusIcon status={check.status} />
                        {check.label}
                      </span>
                      {isEditable && !isCurrentlyEditing && (
                        <button
                          onClick={() => startEditing(s.key)}
                          className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-2.5 py-1 rounded-lg hover:bg-blue-600/30 cursor-pointer"
                        >
                          Update
                        </button>
                      )}
                    </div>
                  </div>
                  {isCurrentlyEditing && (
                    <div className="mt-2 p-4 bg-slate-800/80 rounded-lg border border-blue-500/30">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-semibold text-blue-400">Update {s.label}</h4>
                        <button onClick={cancelEditing} className="text-slate-400 hover:text-white bg-transparent border-none cursor-pointer text-xs">Cancel</button>
                      </div>
                      <SectionForm
                        section={s}
                        data={editData}
                        candidateInfo={candidateInfo}
                        onUpdate={(field, value) => updateEditField(field, value)}
                        onUpdateBulk={(data) => setEditData(prev => ({ ...prev, ...data }))}
                        isManualMode={isManualMode}
                        trustidChecks={trustidChecks}
                        trustidSubmitted={trustidSubmitted}
                        submittingTrustid={submittingTrustid}
                        onSubmitTrustid={onSubmitTrustid}
                      />
                      <div className="flex justify-end gap-3 mt-4">
                        <button onClick={cancelEditing} className="px-4 py-2 rounded-lg border border-slate-600 bg-slate-800 text-slate-300 hover:bg-slate-700 cursor-pointer text-sm">
                          Cancel
                        </button>
                        <button
                          onClick={saveUpdate}
                          disabled={savingUpdate}
                          className="px-4 py-2 rounded-lg border-none bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white cursor-pointer font-semibold text-sm flex items-center gap-1"
                        >
                          {savingUpdate ? <><Loader2 size={14} className="animate-spin" /> Saving...</> : "Save & Re-process"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <p className="text-center text-slate-500 text-xs mt-6">
          Sections marked with "Update" can be edited after submission. Identity, DBS, and Right to Work sections are locked once verified.
        </p>
      </div>
    </div>
  );
}

function SectionForm({ section, data, candidateInfo, onUpdate, onUpdateBulk, isManualMode, trustidChecks, trustidSubmitted, submittingTrustid, onSubmitTrustid }: {
  section: { key: string; label: string };
  data: Record<string, unknown>;
  candidateInfo: Record<string, unknown>;
  onUpdate: (field: string, value: unknown) => void;
  onUpdateBulk: (data: Record<string, unknown>) => void;
  isManualMode: (checkType: string) => boolean;
  trustidChecks: Record<string, unknown>[];
  trustidSubmitted: boolean;
  submittingTrustid: boolean;
  onSubmitTrustid: () => void;
}) {
  const hasSubmittedTrustid = trustidSubmitted || trustidChecks.length > 0;
  const inputClass = "w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";
  const labelClass = "block text-slate-400 text-xs mb-1.5 font-medium";

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
            <div className="grid grid-cols-2 gap-4">
              <div><label className={labelClass}>First Name *</label><input className={inputClass} value={(data.first_name as string) || ""} onChange={e => onUpdate("first_name", e.target.value)} /></div>
              <div><label className={labelClass}>Last Name *</label><input className={inputClass} value={(data.last_name as string) || ""} onChange={e => onUpdate("last_name", e.target.value)} /></div>
            </div>
            <div className="grid grid-cols-2 gap-4 mt-4">
              <div><label className={labelClass}>Phone</label><input className={inputClass} value={(data.phone as string) || ""} onChange={e => onUpdate("phone", e.target.value)} /></div>
              <div><label className={labelClass}>Date of Birth</label><input type="date" className={inputClass} value={(data.date_of_birth as string) || ""} onChange={e => onUpdate("date_of_birth", e.target.value)} /></div>
            </div>
            <div className="mt-4"><label className={labelClass}>Address Line 1</label><input className={inputClass} value={(data.address_line1 as string) || ""} onChange={e => onUpdate("address_line1", e.target.value)} /></div>
            <div className="mt-4"><label className={labelClass}>Address Line 2</label><input className={inputClass} value={(data.address_line2 as string) || ""} onChange={e => onUpdate("address_line2", e.target.value)} /></div>
            <div className="grid grid-cols-2 gap-4 mt-4">
              <div><label className={labelClass}>City</label><input className={inputClass} value={(data.city as string) || ""} onChange={e => onUpdate("city", e.target.value)} /></div>
              <div><label className={labelClass}>Postcode</label><input className={inputClass} value={(data.postcode as string) || ""} onChange={e => onUpdate("postcode", e.target.value)} /></div>
            </div>
            <div className="mt-4"><label className={labelClass}>Profession</label>
              <select className={inputClass} value={(data.profession as string) || ""} onChange={e => onUpdate("profession", e.target.value)}>
                <option value="">Select profession...</option>
                <option value="Nurse">Nurse</option><option value="Doctor">Doctor</option><option value="Healthcare Assistant">Healthcare Assistant</option>
                <option value="Midwife">Midwife</option><option value="Physiotherapist">Physiotherapist</option><option value="Paramedic">Paramedic</option>
                <option value="Occupational Therapist">Occupational Therapist</option><option value="Other">Other</option>
              </select>
            </div>
          </>
        );

      case "identity":
        if (isManualMode("identity_verification")) {
          return (
            <>
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4 mb-4">
                <p className="text-blue-300 text-sm"><strong>Identity Verification via TrustID</strong></p>
                <p className="text-slate-400 text-xs mt-1">Your identity verification will be handled by our trusted partner TrustID. No document upload or selfie is required here — TrustID will contact you directly to complete the verification process.</p>
              </div>
              {hasSubmittedTrustid ? (
                <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-6 text-center">
                  <CheckCircle className="text-green-400 mx-auto mb-2" size={32} />
                  <h3 className="text-green-400 font-semibold text-lg">Submission Confirmed</h3>
                  <p className="text-slate-400 text-sm mt-2">TrustID will contact you within 24 hours to complete your identity verification.</p>
                </div>
              ) : (
                <div className="text-center mt-4">
                  <p className="text-slate-400 text-sm mb-4">Click below to submit your details for TrustID verification. Your personal information will be securely shared with TrustID.</p>
                  <button
                    onClick={onSubmitTrustid}
                    disabled={submittingTrustid}
                    className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white rounded-lg font-semibold text-sm cursor-pointer border-none transition-all"
                  >
                    {submittingTrustid ? "Submitting..." : "Submit for TrustID Verification"}
                  </button>
                </div>
              )}
            </>
          );
        }
        return (
          <>
            <div><label className={labelClass}>Document Type *</label>
              <select className={inputClass} value={(data.document_type as string) || ""} onChange={e => onUpdate("document_type", e.target.value)}>
                <option value="">Select document type...</option>
                <option value="passport">Passport</option>
                <option value="driving_licence">Driving Licence</option>
                <option value="national_identity_card">National Identity Card</option>
                <option value="residence_permit">Residence Permit</option>
              </select>
            </div>
            <div className="mt-4"><label className={labelClass}>Upload Identity Document *</label>
              <div className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all ${data.document_file_name ? "border-green-500/50 bg-green-500/10" : "border-slate-600 bg-slate-800/50 hover:border-blue-500/50 hover:bg-slate-800"}`}
                onClick={() => onUpdate("document_file_name", "uploaded_document_" + Date.now() + ".pdf")}>
                {data.document_file_name
                  ? <><CheckCircle className="text-green-400 mx-auto mb-2" size={24} /><p className="text-green-400 text-sm">Document uploaded: {data.document_file_name as string}</p></>
                  : <p className="text-slate-400 text-sm">Click to upload your identity document (PDF, JPG, PNG)</p>}
              </div>
            </div>
            <div className="mt-4"><label className={labelClass}>Take / Upload Selfie *</label>
              <div className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all ${data.selfie_file_name ? "border-green-500/50 bg-green-500/10" : "border-slate-600 bg-slate-800/50 hover:border-blue-500/50 hover:bg-slate-800"}`}
                onClick={() => onUpdate("selfie_file_name", "selfie_" + Date.now() + ".jpg")}>
                {data.selfie_file_name
                  ? <><CheckCircle className="text-green-400 mx-auto mb-2" size={24} /><p className="text-green-400 text-sm">Selfie captured</p></>
                  : <p className="text-slate-400 text-sm">Click to take or upload a selfie photo</p>}
              </div>
            </div>
          </>
        );

      case "rtw":
        if (isManualMode("right_to_work")) {
          return (
            <>
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4 mb-4">
                <p className="text-blue-300 text-sm"><strong>Right to Work via TrustID</strong></p>
                <p className="text-slate-400 text-xs mt-1">Your right to work check will be handled by our trusted partner TrustID. No document upload is required here — TrustID will contact you directly.</p>
              </div>
              {hasSubmittedTrustid ? (
                <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-6 text-center">
                  <CheckCircle className="text-green-400 mx-auto mb-2" size={32} />
                  <h3 className="text-green-400 font-semibold text-lg">Submitted to TrustID</h3>
                  <p className="text-slate-400 text-sm mt-2">TrustID will contact you within 24 hours to verify your right to work.</p>
                </div>
              ) : (
                <div className="text-center mt-4">
                  <p className="text-slate-400 text-sm mb-4">Submit your details on the Identity Documents tab to begin all TrustID verifications.</p>
                  <button onClick={() => {}} disabled className="px-6 py-3 bg-slate-600 text-slate-400 rounded-lg font-semibold text-sm cursor-not-allowed border-none">Submit via Identity Tab First</button>
                </div>
              )}
            </>
          );
        }
        return (
          <>
            <div><label className={labelClass}>Are you a UK or Irish citizen?</label>
              <div className="flex gap-3 mt-2">
                <button onClick={() => onUpdate("method", "uk_citizen")} className={`flex-1 px-4 py-3 rounded-lg border-2 cursor-pointer font-medium text-sm transition-all ${
                  data.method === "uk_citizen" ? "border-blue-500 bg-blue-500/10 text-blue-400" : "border-slate-600 bg-slate-800 text-slate-400 hover:border-slate-500"
                }`}>
                  Yes - UK/Irish Citizen
                </button>
                <button onClick={() => onUpdate("method", "share_code")} className={`flex-1 px-4 py-3 rounded-lg border-2 cursor-pointer font-medium text-sm transition-all ${
                  data.method === "share_code" ? "border-blue-500 bg-blue-500/10 text-blue-400" : "border-slate-600 bg-slate-800 text-slate-400 hover:border-slate-500"
                }`}>
                  No - I have a visa/share code
                </button>
              </div>
            </div>
            {data.method === "uk_citizen" && (
              <>
                <div className="mt-4"><label className={labelClass}>Document Type</label>
                  <select className={inputClass} value={(data.document_type as string) || ""} onChange={e => onUpdate("document_type", e.target.value)}>
                    <option value="">Select...</option>
                    <option value="uk_passport">UK Passport</option>
                    <option value="irish_passport">Irish Passport</option>
                    <option value="birth_certificate">UK Birth Certificate</option>
                    <option value="naturalisation_certificate">Naturalisation Certificate</option>
                  </select>
                </div>
                <div className="mt-4"><label className={labelClass}>Nationality</label>
                  <select className={inputClass} value={(data.nationality as string) || "british"} onChange={e => onUpdate("nationality", e.target.value)}>
                    <option value="british">British</option><option value="irish">Irish</option>
                  </select>
                </div>
                <div className="mt-4"><label className={labelClass}>National Insurance Number</label>
                  <input className={inputClass} placeholder="e.g. AB 12 34 56 C" value={(data.ni_number as string) || ""} onChange={e => onUpdate("ni_number", e.target.value)} />
                </div>
              </>
            )}
            {data.method === "share_code" && (
              <div className="mt-4">
                <label className={labelClass}>Home Office Share Code *</label>
                <input className={inputClass} placeholder="Enter your 9-character share code" value={(data.share_code as string) || ""} onChange={e => onUpdate("share_code", e.target.value)} />
                <p className="text-xs text-slate-500 mt-1">Get your share code from gov.uk/prove-right-to-work</p>
              </div>
            )}
          </>
        );

      case "dbs":
        if (isManualMode("dbs_check")) {
          return (
            <>
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4 mb-4">
                <p className="text-blue-300 text-sm"><strong>DBS Check via TrustID</strong></p>
                <p className="text-slate-400 text-xs mt-1">Your DBS check will be handled by our trusted partner TrustID. No application form is required here — TrustID will contact you directly.</p>
              </div>
              {hasSubmittedTrustid ? (
                <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-6 text-center">
                  <CheckCircle className="text-green-400 mx-auto mb-2" size={32} />
                  <h3 className="text-green-400 font-semibold text-lg">Submitted to TrustID</h3>
                  <p className="text-slate-400 text-sm mt-2">TrustID will contact you within 24 hours regarding your DBS check.</p>
                </div>
              ) : (
                <div className="text-center mt-4">
                  <p className="text-slate-400 text-sm mb-4">Submit your details on the Identity Documents tab to begin all TrustID verifications.</p>
                  <button onClick={() => {}} disabled className="px-6 py-3 bg-slate-600 text-slate-400 rounded-lg font-semibold text-sm cursor-not-allowed border-none">Submit via Identity Tab First</button>
                </div>
              )}
            </>
          );
        }
        return (
          <>
            <div><label className={labelClass}>DBS Check Type</label>
              <select className={inputClass} value={(data.check_type as string) || "enhanced"} onChange={e => onUpdate("check_type", e.target.value)}>
                <option value="enhanced">Enhanced DBS Check</option>
                <option value="enhanced_barred">Enhanced DBS with Barred List</option>
                <option value="standard">Standard DBS Check</option>
                <option value="basic">Basic DBS Check</option>
              </select>
            </div>
            <div className="mt-4"><label className={labelClass}>Existing DBS Certificate Number (if any)</label>
              <input className={inputClass} placeholder="Enter existing certificate number" value={(data.certificate_number as string) || ""} onChange={e => onUpdate("certificate_number", e.target.value)} />
            </div>
            <div className="mt-4"><label className={labelClass}>Registered on DBS Update Service?</label>
              <div className="flex gap-3 mt-2">
                <button onClick={() => onUpdate("update_service", true)} className={`px-6 py-2.5 rounded-lg border-2 cursor-pointer text-sm font-medium transition-all ${
                  data.update_service === true ? "border-green-500 bg-green-500/10 text-green-400" : "border-slate-600 bg-slate-800 text-slate-400 hover:border-slate-500"
                }`}>Yes</button>
                <button onClick={() => onUpdate("update_service", false)} className={`px-6 py-2.5 rounded-lg border-2 cursor-pointer text-sm font-medium transition-all ${
                  data.update_service === false ? "border-red-500 bg-red-500/10 text-red-400" : "border-slate-600 bg-slate-800 text-slate-400 hover:border-slate-500"
                }`}>No</button>
              </div>
            </div>
            <div className="mt-4 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg text-sm text-blue-300">
              <strong>Note:</strong> An Enhanced DBS check will be submitted automatically when you complete this application. You will receive a certificate by post within 2-6 weeks.
            </div>
          </>
        );

      case "cv":
        return (
          <>
            <div><label className={labelClass}>Upload CV (PDF, DOCX, TXT)</label>
              <div className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all ${data.cv_file_name ? "border-green-500/50 bg-green-500/10" : "border-slate-600 bg-slate-800/50 hover:border-blue-500/50 hover:bg-slate-800"}`}
                onClick={() => onUpdate("cv_file_name", "cv_upload_" + Date.now() + ".pdf")}>
                {data.cv_file_name
                  ? <><CheckCircle className="text-green-400 mx-auto mb-2" size={24} /><p className="text-green-400 text-sm">CV uploaded: {data.cv_file_name as string}</p></>
                  : <p className="text-slate-400 text-sm">Click to upload your CV</p>}
              </div>
            </div>
            <div className="mt-4"><label className={labelClass}>Or paste CV text</label>
              <textarea className={`${inputClass} min-h-[120px] font-inherit`} placeholder="Paste your CV content here..." value={(data.cv_text as string) || ""} onChange={e => onUpdate("cv_text", e.target.value)} />
            </div>
            <div className="mt-6">
              <h4 className="text-white text-sm font-semibold mb-3">Employment History (Last 5 Years)</h4>
              <p className="text-slate-400 text-xs mb-3">Add your employment history. Include verifier details for each employer.</p>
              <EmploymentEntries entries={(data.employment_entries as Record<string, unknown>[]) || []} onChange={(entries) => onUpdate("employment_entries", entries)} />
            </div>
          </>
        );

      case "registration":
        return (
          <>
            <div><label className={labelClass}>Registration Body *</label>
              <select className={inputClass} value={(data.registration_body as string) || ""} onChange={e => onUpdate("registration_body", e.target.value)}>
                <option value="">Select registration body...</option>
                <option value="NMC">NMC - Nursing and Midwifery Council</option>
                <option value="GMC">GMC - General Medical Council</option>
                <option value="HCPC">HCPC - Health and Care Professions Council</option>
                <option value="GPhC">GPhC - General Pharmaceutical Council</option>
              </select>
            </div>
            <div className="mt-4"><label className={labelClass}>Registration / PIN Number *</label>
              <input className={inputClass} placeholder="Enter your registration number" value={(data.registration_number as string) || ""} onChange={e => onUpdate("registration_number", e.target.value)} />
            </div>
            <div className="mt-4 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg text-sm text-blue-300">
              <strong>Note:</strong> Your registration will be verified against the public register automatically.
            </div>
          </>
        );

      case "references":
        return (
          <>
            <p className="text-slate-400 text-sm mb-4">Provide at least 2 professional references. Reference requests will be sent automatically.</p>
            <RefereeEntries referees={(data.referees as Record<string, unknown>[]) || []} onChange={(refs) => onUpdate("referees", refs)} />
          </>
        );

      case "training":
        return (
          <>
            <p className="text-slate-400 text-sm mb-4">Add your training certificates (mandatory training, CPD, specialist certifications).</p>
            <div className="mb-4">
              <label className="flex items-center gap-3 cursor-pointer p-3 rounded-lg border border-slate-600 bg-slate-700/30 hover:bg-slate-700/50 transition-all">
                <input
                  type="checkbox"
                  checked={data.no_certificates === true}
                  onChange={e => {
                    onUpdate("no_certificates", e.target.checked);
                    if (e.target.checked) onUpdate("certificates", []);
                  }}
                  className="w-5 h-5 accent-blue-500"
                />
                <span className="text-sm text-slate-300">I have no training certificates to supply at this time</span>
              </label>
            </div>
            {!data.no_certificates && (
              <CertificateEntries certificates={(data.certificates as Record<string, unknown>[]) || []} onChange={(certs) => onUpdate("certificates", certs)} />
            )}
          </>
        );

      default:
        return <p className="text-slate-400">Unknown section</p>;
    }
  };

  return (
    <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
      <h2 className="text-lg font-bold text-white mb-1">{section.label}</h2>
      <p className="text-slate-400 text-sm mb-5">
        {section.key === "personal" && "Enter your personal details below."}
        {section.key === "identity" && (isManualMode("identity_verification") ? "Identity verification handled by TrustID partner." : "Upload your identity document and a selfie for verification.")}
        {section.key === "rtw" && (isManualMode("right_to_work") ? "Right to work check handled by TrustID partner." : "Provide evidence of your right to work in the UK.")}
        {section.key === "dbs" && (isManualMode("dbs_check") ? "DBS check handled by TrustID partner." : "Provide DBS check information.")}
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
  const [validationPassed, setValidationPassed] = useState(false);
  const [validating, setValidating] = useState(false);
  const completedCount = SECTIONS.filter(s => sectionCompleted[s.key]).length;

  const handleValidate = async () => {
    setValidating(true);
    const passed = await onValidate();
    setValidationPassed(passed);
    setValidating(false);
  };

  return (
    <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
      <h2 className="text-lg font-bold text-white mb-4">Review & Consent</h2>

      <div className="mb-6">
        <h3 className="text-sm font-semibold text-slate-300 mb-3">Sections Completed: {completedCount}/{SECTIONS.length}</h3>
        <div className="grid grid-cols-2 gap-2">
          {SECTIONS.map(s => (
            <div key={s.key} className={`flex items-center gap-2 p-2.5 rounded-lg ${sectionCompleted[s.key] ? "bg-green-500/10 border border-green-500/20" : "bg-red-500/10 border border-red-500/20"}`}>
              {sectionCompleted[s.key] ? <CheckCircle size={16} className="text-green-400" /> : <XCircle size={16} className="text-red-400" />}
              <span className={`text-xs ${sectionCompleted[s.key] ? "text-green-400" : "text-red-400"}`}>{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      {validationErrors.length > 0 && (
        <div className="mb-5 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
          <h4 className="text-red-400 text-sm font-semibold mb-2">Please fix the following before submitting:</h4>
          {validationErrors.map((e, i) => (
            <div key={i} className="text-xs text-red-300 py-1">- [{e.section}] {e.message}</div>
          ))}
        </div>
      )}

      <div className="mb-5 p-4 bg-slate-700/50 rounded-lg border border-slate-600 max-h-48 overflow-y-auto">
        <h4 className="text-sm font-semibold text-white mb-2">Privacy Policy & Terms of Service (v1.0)</h4>
        <div className="text-xs text-slate-400 leading-relaxed space-y-2">
          <p><strong className="text-slate-300">Data Processing:</strong> By submitting this application, you consent to Viper AI processing your personal data for the purpose of employment vetting and compliance checks. This includes identity verification, DBS checks, right to work verification, reference collection, and professional registration verification.</p>
          <p><strong className="text-slate-300">Data Controller:</strong> The agency that invited you to complete this vetting process acts as the data controller. Viper AI acts as the data processor on behalf of the agency.</p>
          <p><strong className="text-slate-300">Data Retention:</strong> Your data will be retained for the duration required by CQC regulations and applicable employment law. You may request deletion of your data at any time, subject to legal retention requirements.</p>
          <p><strong className="text-slate-300">Your Rights:</strong> Under GDPR, you have the right to: access your data, request correction of inaccurate data, request deletion (right to be forgotten), data portability, and to lodge a complaint with the ICO.</p>
          <p><strong className="text-slate-300">Third Parties:</strong> Your data may be shared with: Onfido (identity verification), DBS providers (criminal record checks), the Home Office (right to work), professional registration bodies (NMC, GMC, HCPC), and your referees/former employers.</p>
          <p><strong className="text-slate-300">DBS Consent:</strong> By proceeding, you specifically consent to an Enhanced DBS check being carried out, which may include checks against the children and/or adults barred lists as required by the role.</p>
        </div>
      </div>

      <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
        <label className="flex gap-3 cursor-pointer items-start">
          <input type="checkbox" checked={consentChecked} onChange={e => onConsentChange(e.target.checked)} className="mt-1 w-5 h-5 accent-blue-500" />
          <span className="text-sm text-slate-300 leading-relaxed">
            <strong className="text-white">I confirm that:</strong> All information provided is accurate and complete. I have read and agree to the Privacy Policy and Terms of Service. I consent to the processing of my personal data for employment vetting purposes, including DBS checks, identity verification, and all other compliance checks listed above. I understand my rights under GDPR.
          </span>
        </label>
      </div>

      <div className="flex gap-3">
        <button
          onClick={handleValidate}
          disabled={validating || validationPassed}
          className={`flex-1 px-6 py-3 rounded-lg border font-medium text-sm transition-all ${
            validationPassed
              ? "border-green-500/30 bg-green-500/10 text-green-400 cursor-default"
              : validating
                ? "border-slate-600 bg-slate-700 text-slate-400 cursor-wait"
                : "border-slate-600 bg-slate-700 hover:bg-slate-600 text-slate-300 cursor-pointer"
          }`}
        >
          {validating ? "Validating..." : validationPassed ? "✓ Validation Passed" : "Validate Application"}
        </button>
        <button
          onClick={onSubmit}
          disabled={!consentChecked || !validationPassed || submitting}
          className={`flex-1 px-6 py-3 rounded-lg border-none text-white font-bold text-sm transition-all ${
            consentChecked && validationPassed ? "bg-emerald-600 hover:bg-emerald-700 cursor-pointer" : "bg-slate-600 text-slate-500 cursor-not-allowed"
          }`}
        >
          {submitting ? "Submitting..." : "Submit Application"}
        </button>
      </div>
    </div>
  );
}

function EmploymentEntries({ entries, onChange }: { entries: Record<string, unknown>[]; onChange: (e: Record<string, unknown>[]) => void }) {
  const inputClass = "w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:ring-2 focus:ring-blue-500";
  const addEntry = () => onChange([...entries, { employer_name: "", job_title: "", start_date: "", end_date: "", reason_for_leaving: "", verifier_name: "", verifier_email: "", verifier_job_title: "" }]);
  const updateEntry = (i: number, field: string, value: string) => { const e = [...entries]; e[i] = { ...e[i], [field]: value }; onChange(e); };
  const removeEntry = (i: number) => onChange(entries.filter((_, idx) => idx !== i));

  return (
    <div>
      {entries.map((entry, i) => (
        <div key={i} className="border border-slate-600 rounded-lg p-4 mb-3 bg-slate-700/30">
          <div className="flex justify-between items-center mb-3">
            <strong className="text-white text-sm">Employment {i + 1}</strong>
            <button onClick={() => removeEntry(i)} className="bg-red-500/20 text-red-400 border border-red-500/30 rounded px-2 py-1 cursor-pointer text-xs hover:bg-red-500/30">Remove</button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="text-xs text-slate-400">Employer Name</label><input className={inputClass} value={(entry.employer_name as string) || ""} onChange={e => updateEntry(i, "employer_name", e.target.value)} /></div>
            <div><label className="text-xs text-slate-400">Job Title</label><input className={inputClass} value={(entry.job_title as string) || ""} onChange={e => updateEntry(i, "job_title", e.target.value)} /></div>
            <div><label className="text-xs text-slate-400">Start Date</label><input type="date" className={inputClass} value={(entry.start_date as string) || ""} onChange={e => updateEntry(i, "start_date", e.target.value)} /></div>
            <div><label className="text-xs text-slate-400">End Date</label><input type="date" className={inputClass} value={(entry.end_date as string) || ""} onChange={e => updateEntry(i, "end_date", e.target.value)} /></div>
            <div className="col-span-2"><label className="text-xs text-slate-400">Reason for Leaving</label><input className={inputClass} value={(entry.reason_for_leaving as string) || ""} onChange={e => updateEntry(i, "reason_for_leaving", e.target.value)} /></div>
          </div>
          <div className="mt-3 p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
            <p className="text-xs font-semibold text-blue-300 mb-2">Employer Verifier Details</p>
            <div className="grid grid-cols-3 gap-3">
              <div><label className="text-xs text-slate-400">Verifier Name</label><input className={inputClass} value={(entry.verifier_name as string) || ""} onChange={e => updateEntry(i, "verifier_name", e.target.value)} /></div>
              <div><label className="text-xs text-slate-400">Verifier Email</label><input className={inputClass} value={(entry.verifier_email as string) || ""} onChange={e => updateEntry(i, "verifier_email", e.target.value)} /></div>
              <div><label className="text-xs text-slate-400">Verifier Job Title</label><input className={inputClass} value={(entry.verifier_job_title as string) || ""} onChange={e => updateEntry(i, "verifier_job_title", e.target.value)} /></div>
            </div>
          </div>
        </div>
      ))}
      <button onClick={addEntry} className="w-full p-3 rounded-lg border-2 border-dashed border-slate-600 bg-transparent hover:border-blue-500/50 hover:bg-slate-800 cursor-pointer text-blue-400 font-medium text-sm transition-all">
        + Add Employment Entry
      </button>
    </div>
  );
}

function RefereeEntries({ referees, onChange }: { referees: Record<string, unknown>[]; onChange: (r: Record<string, unknown>[]) => void }) {
  const inputClass = "w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:ring-2 focus:ring-blue-500";
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
        <div key={i} className="border border-slate-600 rounded-lg p-4 mb-3 bg-slate-700/30">
          <div className="flex justify-between items-center mb-3">
            <strong className="text-white text-sm">Reference {i + 1} {i < 2 ? "*" : ""}</strong>
            {i >= 2 && <button onClick={() => removeRef(i)} className="bg-red-500/20 text-red-400 border border-red-500/30 rounded px-2 py-1 cursor-pointer text-xs hover:bg-red-500/30">Remove</button>}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="text-xs text-slate-400">Referee Name *</label><input className={inputClass} value={(ref.name as string) || ""} onChange={e => updateRef(i, "name", e.target.value)} /></div>
            <div><label className="text-xs text-slate-400">Referee Email *</label><input type="email" className={inputClass} value={(ref.email as string) || ""} onChange={e => updateRef(i, "email", e.target.value)} /></div>
            <div><label className="text-xs text-slate-400">Organisation</label><input className={inputClass} value={(ref.organisation as string) || ""} onChange={e => updateRef(i, "organisation", e.target.value)} /></div>
            <div><label className="text-xs text-slate-400">Job Title</label><input className={inputClass} value={(ref.job_title as string) || ""} onChange={e => updateRef(i, "job_title", e.target.value)} /></div>
          </div>
        </div>
      ))}
      <button onClick={addRef} className="w-full p-3 rounded-lg border-2 border-dashed border-slate-600 bg-transparent hover:border-blue-500/50 hover:bg-slate-800 cursor-pointer text-blue-400 font-medium text-sm transition-all">
        + Add Another Reference
      </button>
    </div>
  );
}

function CertificateEntries({ certificates, onChange }: { certificates: Record<string, unknown>[]; onChange: (c: Record<string, unknown>[]) => void }) {
  const inputClass = "w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:ring-2 focus:ring-blue-500";
  const addCert = () => onChange([...certificates, { certificate_name: "", category: "mandatory", provider: "", issue_date: "", expiry_date: "", certificate_ref: "" }]);
  const updateCert = (i: number, field: string, value: string) => { const c = [...certificates]; c[i] = { ...c[i], [field]: value }; onChange(c); };
  const removeCert = (i: number) => onChange(certificates.filter((_, idx) => idx !== i));

  return (
    <div>
      {certificates.map((cert, i) => (
        <div key={i} className="border border-slate-600 rounded-lg p-4 mb-3 bg-slate-700/30">
          <div className="flex justify-between items-center mb-3">
            <strong className="text-white text-sm">Certificate {i + 1}</strong>
            <button onClick={() => removeCert(i)} className="bg-red-500/20 text-red-400 border border-red-500/30 rounded px-2 py-1 cursor-pointer text-xs hover:bg-red-500/30">Remove</button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="text-xs text-slate-400">Certificate Name *</label><input className={inputClass} value={(cert.certificate_name as string) || ""} onChange={e => updateCert(i, "certificate_name", e.target.value)} /></div>
            <div><label className="text-xs text-slate-400">Category</label>
              <select className={inputClass} value={(cert.category as string) || "mandatory"} onChange={e => updateCert(i, "category", e.target.value)}>
                <option value="mandatory">Mandatory Training</option><option value="specialist">Specialist</option><option value="cpd">CPD</option><option value="other">Other</option>
              </select>
            </div>
            <div><label className="text-xs text-slate-400">Provider</label><input className={inputClass} value={(cert.provider as string) || ""} onChange={e => updateCert(i, "provider", e.target.value)} /></div>
            <div><label className="text-xs text-slate-400">Certificate Ref</label><input className={inputClass} value={(cert.certificate_ref as string) || ""} onChange={e => updateCert(i, "certificate_ref", e.target.value)} /></div>
            <div><label className="text-xs text-slate-400">Issue Date</label><input type="date" className={inputClass} value={(cert.issue_date as string) || ""} onChange={e => updateCert(i, "issue_date", e.target.value)} /></div>
            <div><label className="text-xs text-slate-400">Expiry Date</label><input type="date" className={inputClass} value={(cert.expiry_date as string) || ""} onChange={e => updateCert(i, "expiry_date", e.target.value)} /></div>
          </div>
        </div>
      ))}
      <button onClick={addCert} className="w-full p-3 rounded-lg border-2 border-dashed border-slate-600 bg-transparent hover:border-blue-500/50 hover:bg-slate-800 cursor-pointer text-blue-400 font-medium text-sm transition-all">
        + Add Training Certificate
      </button>
    </div>
  );
}
