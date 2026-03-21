import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { candidatesApi, checksApi, complianceApi, monitoringApi, agencyInvitesApi, trainingApi, reportsApi } from "../api/client";
import {
  Shield, CheckCircle, XCircle, Clock, AlertTriangle, Upload,
  FileText, UserCheck, Fingerprint, Search, Send, LogOut, RefreshCw, ChevronRight,
  Camera, ScanFace, Loader2, ArrowRight, ArrowLeft, Eye, Briefcase, Plus, Trash2, Edit3, Building2, GraduationCap, Download,
} from "lucide-react";

type Tab = "overview" | "identity" | "rtw" | "dbs" | "cv" | "employment" | "registration" | "references" | "training";

export default function CandidatePortal() {
  const { token, userId, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("overview");
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);
  const [compliance, setCompliance] = useState<Record<string, unknown> | null>(null);
  const [alerts, setAlerts] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  // Identity verification wizard states
  type IdStep = "select_doc" | "upload_doc" | "selfie" | "processing" | "complete";
  const [idStep, setIdStep] = useState<IdStep>("select_doc");
  const [idDocType, setIdDocType] = useState("passport");
  const [idDocFileName, setIdDocFileName] = useState("");
  const [idSelfieFileName, setIdSelfieFileName] = useState("");
  const [idResult, setIdResult] = useState<Record<string, unknown> | null>(null);

  // Check-specific states
  const [rtwMethod, setRtwMethod] = useState<"uk_citizen" | "share_code">("uk_citizen");
  const [shareCode, setShareCode] = useState("");
  const [rtwDocType, setRtwDocType] = useState("uk_passport");
  const [rtwNationality, setRtwNationality] = useState("british");
  const [rtwDocRef, setRtwDocRef] = useState("");
  const [rtwNiNumber, setRtwNiNumber] = useState("");
  const [cvText, setCvText] = useState("");
  const [cvFileName, setCvFileName] = useState("");
  const [refName, setRefName] = useState("");
  const [refEmail, setRefEmail] = useState("");
  const [refOrg, setRefOrg] = useState("");
  const [refTitle, setRefTitle] = useState("");
  const [references, setReferences] = useState<Record<string, unknown>[]>([]);
  const [identityChecks, setIdentityChecks] = useState<Record<string, unknown>[]>([]);
  const [rtwChecks, setRtwChecks] = useState<Record<string, unknown>[]>([]);
  const [dbsChecks, setDbsChecks] = useState<Record<string, unknown>[]>([]);
  const [cvAnalyses, setCvAnalyses] = useState<Record<string, unknown>[]>([]);
  const [regChecks, setRegChecks] = useState<Record<string, unknown>[]>([]);

  // Training certificates
  const [trainingCerts, setTrainingCerts] = useState<Record<string, unknown>[]>([]);
  const [trainingStandards, setTrainingStandards] = useState<Record<string, unknown>[]>([]);
  const [trainingCompliance, setTrainingCompliance] = useState<Record<string, unknown> | null>(null);
  const [newCertName, setNewCertName] = useState("");
  const [newCertCategory, setNewCertCategory] = useState("mandatory");
  const [newCertProvider, setNewCertProvider] = useState("");
  const [newCertIssueDate, setNewCertIssueDate] = useState("");
  const [newCertExpiryDate, setNewCertExpiryDate] = useState("");
  const [newCertRef, setNewCertRef] = useState("");
  const [downloadingAudit, setDownloadingAudit] = useState(false);

  // Agency affiliation
  const [myAgencies, setMyAgencies] = useState<Record<string, unknown>[]>([]);
  const [pendingInvites, setPendingInvites] = useState<Record<string, unknown>[]>([]);

  // Employment history states
  const [employmentEntries, setEmploymentEntries] = useState<Record<string, unknown>[]>([]);
  const [employmentVerifications, setEmploymentVerifications] = useState<Record<string, unknown>[]>([]);
  const [editingEntryId, setEditingEntryId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Record<string, string>>({});
  const [addingEntry, setAddingEntry] = useState(false);
  const [newEntry, setNewEntry] = useState({ employer_name: "", job_title: "", start_date: "", end_date: "", reason_for_leaving: "" });
  const [verifierForm, setVerifierForm] = useState<Record<string, { name: string; email: string; job_title: string }>>({});

  const loadData = useCallback(async () => {
    if (!token || !userId) return;
    try {
      const [p, a] = await Promise.all([
        candidatesApi.getMe(token),
        monitoringApi.getAlerts(token, userId),
      ]);
      setProfile(p);
      setAlerts(a);
      try {
        const c = await complianceApi.get(token, userId);
        setCompliance(c);
      } catch {
        setCompliance(null);
      }
      try {
        const [agencies, invs] = await Promise.all([
          agencyInvitesApi.getMyAgencies(token),
          agencyInvitesApi.getPendingInvites(token),
        ]);
        setMyAgencies(agencies);
        setPendingInvites(invs);
      } catch {
        // ignore
      }
    } catch (err) {
      console.error("Failed to load data", err);
    }
  }, [token, userId]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (!token || !userId || tab !== "training") return;
    const loadTraining = async () => {
      try {
        const [certs, standards, comp] = await Promise.all([
          trainingApi.getCertificates(token, userId),
          trainingApi.getStandards(),
          trainingApi.getCompliance(token, userId),
        ]);
        setTrainingCerts(certs);
        setTrainingStandards(standards);
        setTrainingCompliance(comp);
      } catch (err) { console.error("Failed to load training data", err); }
    };
    loadTraining();
  }, [token, userId, tab]);

  const loadCheckData = useCallback(async () => {
    if (!token || !userId) return;
    try {
      const [id, rtw, dbs, cv, reg, refs, emp, empVer] = await Promise.all([
        checksApi.getIdentityChecks(token, userId),
        checksApi.getRightToWorkChecks(token, userId),
        checksApi.getDBSChecks(token, userId),
        checksApi.getCVAnalyses(token, userId),
        checksApi.getRegistrationChecks(token, userId),
        checksApi.getReferences(token, userId),
        checksApi.getEmploymentHistory(token, userId),
        checksApi.getEmploymentVerifications(token, userId),
      ]);
      setIdentityChecks(id);
      setRtwChecks(rtw);
      setDbsChecks(dbs);
      setCvAnalyses(cv);
      setRegChecks(reg);
      setReferences(refs);
      setEmploymentEntries(emp);
      setEmploymentVerifications(empVer);
    } catch {
      // Some may 404 if no checks yet
    }
  }, [token, userId]);

  useEffect(() => { loadCheckData(); }, [loadCheckData]);

  const showMessage = (msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(""), 4000);
  };

  const runIdentityCheck = async () => {
    if (!token || !userId) return;
    if (!idDocFileName) {
      showMessage("Error: Please upload your identity document first");
      return;
    }
    if (!idSelfieFileName) {
      showMessage("Error: Please upload your selfie photo first");
      return;
    }
    setIdStep("processing");
    setLoading(true);
    try {
      // Step 1: Get SDK token (simulated - in production this initialises the Onfido SDK)
      await checksApi.identitySDKToken(token, userId);
      // Step 2: Submit the check with document + selfie data
      const result = await checksApi.identityCheck(token, userId, {
        document_type: idDocType,
        document_file_name: idDocFileName,
        selfie_file_name: idSelfieFileName,
        first_name: profile?.first_name as string | undefined,
        last_name: profile?.last_name as string | undefined,
        date_of_birth: profile?.date_of_birth as string | undefined,
      });
      setIdResult(result);
      setIdStep("complete");
      showMessage("Identity verification completed!");
      await Promise.all([loadData(), loadCheckData()]);
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`);
      setIdStep("selfie"); // Go back to allow retry
    } finally { setLoading(false); }
  };

  const resetIdentityWizard = () => {
    setIdStep("select_doc");
    setIdDocType("passport");
    setIdDocFileName("");
    setIdSelfieFileName("");
    setIdResult(null);
  };

  const runRTWCheck = async () => {
    if (!token || !userId) return;
    setLoading(true);
    try {
      if (rtwMethod === "uk_citizen") {
        const needsNI = ["birth_certificate", "adoption_certificate", "naturalisation_certificate"].includes(rtwDocType);
        if (needsNI && !rtwNiNumber) {
          showMessage("Error: National Insurance number is required for this document type");
          setLoading(false);
          return;
        }
        await checksApi.rightToWorkUKCitizen(token, userId, {
          document_type: rtwDocType,
          nationality: rtwNationality,
          document_reference: rtwDocRef || undefined,
          ni_number: rtwNiNumber || undefined,
        });
      } else {
        if (!shareCode) {
          showMessage("Error: Share code is required");
          setLoading(false);
          return;
        }
        await checksApi.rightToWork(token, userId, shareCode);
      }
      showMessage("Right to Work verification completed!");
      setShareCode("");
      setRtwDocRef("");
      setRtwNiNumber("");
      await Promise.all([loadData(), loadCheckData()]);
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally { setLoading(false); }
  };

  const runDBSCheck = async () => {
    if (!token || !userId) return;
    setLoading(true);
    try {
      await checksApi.dbsCheck(token, userId);
      showMessage("Enhanced DBS check submitted!");
      await Promise.all([loadData(), loadCheckData()]);
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally { setLoading(false); }
  };

  const runCVAnalysis = async () => {
    if (!token || !userId || !cvText) return;
    setLoading(true);
    try {
      await checksApi.cvAnalysis(token, userId, cvText, cvFileName || undefined);
      showMessage("CV analysis completed! Employment history extracted.");
      setCvText("");
      setCvFileName("");
      await Promise.all([loadData(), loadCheckData()]);
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally { setLoading(false); }
  };

  const handleCvFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setCvFileName(file.name);
      // Simulate reading file text (in production, would parse PDF/DOCX on backend)
      const reader = new FileReader();
      reader.onload = (ev) => {
        const text = ev.target?.result as string;
        if (text) setCvText(text);
      };
      reader.readAsText(file);
    }
  };

  const sendEmploymentVerification = async (entryId: string) => {
    if (!token || !userId) return;
    const vf = verifierForm[entryId];
    if (!vf?.name || !vf?.email) {
      showMessage("Error: Verifier name and email are required");
      return;
    }
    setLoading(true);
    try {
      await checksApi.sendEmploymentVerification(token, {
        candidate_id: userId,
        employment_id: entryId,
        verifier_name: vf.name,
        verifier_email: vf.email,
        verifier_job_title: vf.job_title || undefined,
      });
      showMessage("Employment verification request sent!");
      setVerifierForm((prev) => { const copy = { ...prev }; delete copy[entryId]; return copy; });
      await loadCheckData();
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally { setLoading(false); }
  };

  const deleteEmploymentEntry = async (entryId: string) => {
    if (!token) return;
    setLoading(true);
    try {
      await checksApi.deleteEmploymentEntry(token, entryId);
      showMessage("Employment entry deleted");
      await loadCheckData();
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally { setLoading(false); }
  };

  const updateEmploymentEntry = async (entryId: string) => {
    if (!token) return;
    setLoading(true);
    try {
      await checksApi.updateEmploymentEntry(token, entryId, editForm);
      showMessage("Employment entry updated");
      setEditingEntryId(null);
      setEditForm({});
      await loadCheckData();
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally { setLoading(false); }
  };

  const addEmploymentEntry = async () => {
    if (!token || !userId || !newEntry.employer_name || !newEntry.job_title) return;
    setLoading(true);
    try {
      await checksApi.addEmploymentEntry(token, { candidate_id: userId, ...newEntry });
      showMessage("Employment entry added");
      setAddingEntry(false);
      setNewEntry({ employer_name: "", job_title: "", start_date: "", end_date: "", reason_for_leaving: "" });
      await loadCheckData();
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally { setLoading(false); }
  };

  const runRegistrationCheck = async () => {
    if (!token || !userId || !profile) return;
    const body = profile.registration_body as string;
    const num = profile.registration_number as string;
    if (!body || !num) { showMessage("Set your registration body and number in your profile first"); return; }
    setLoading(true);
    try {
      await checksApi.registrationCheck(token, userId, body, num);
      showMessage("Registration check completed!");
      await Promise.all([loadData(), loadCheckData()]);
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally { setLoading(false); }
  };

  const createReference = async () => {
    if (!token || !userId || !refName || !refEmail) return;
    setLoading(true);
    try {
      await checksApi.createReference(token, {
        candidate_id: userId, referee_name: refName, referee_email: refEmail,
        referee_organisation: refOrg, referee_job_title: refTitle,
      });
      showMessage("Reference request sent!");
      setRefName(""); setRefEmail(""); setRefOrg(""); setRefTitle("");
      await loadCheckData();
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally { setLoading(false); }
  };

  const addTrainingCert = async () => {
    if (!token || !userId || !newCertName) return;
    setLoading(true);
    try {
      await trainingApi.addCertificate(token, userId, {
        certificate_name: newCertName,
        category: newCertCategory,
        provider: newCertProvider || undefined,
        issue_date: newCertIssueDate || undefined,
        expiry_date: newCertExpiryDate || undefined,
        certificate_ref: newCertRef || undefined,
      });
      setNewCertName(""); setNewCertProvider(""); setNewCertIssueDate(""); setNewCertExpiryDate(""); setNewCertRef("");
      showMessage("Training certificate added");
      loadCheckData();
    } catch (err) { showMessage("Error: " + (err instanceof Error ? err.message : "Failed")); }
    finally { setLoading(false); }
  };

  const deleteTrainingCert = async (certId: string) => {
    if (!token) return;
    try {
      await trainingApi.deleteCertificate(token, certId);
      showMessage("Certificate deleted");
      loadCheckData();
    } catch (err) { showMessage("Error: " + (err instanceof Error ? err.message : "Failed")); }
  };

  const downloadAuditPack = async () => {
    if (!token || !userId) return;
    setDownloadingAudit(true);
    try {
      const resp = await reportsApi.downloadCandidateAudit(token, userId);
      if (!resp.ok) throw new Error("Failed to download");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "audit_pack.pdf"; a.click();
      URL.revokeObjectURL(url);
      showMessage("Audit pack downloaded");
    } catch (err) { showMessage("Error: " + (err instanceof Error ? err.message : "Failed")); }
    finally { setDownloadingAudit(false); }
  };

  const StatusBadge = ({ status }: { status: string }) => {
    const colors: Record<string, string> = {
      clear: "bg-green-500/20 text-green-400 border-green-500/30",
      valid: "bg-green-500/20 text-green-400 border-green-500/30",
      active: "bg-green-500/20 text-green-400 border-green-500/30",
      verified: "bg-green-500/20 text-green-400 border-green-500/30",
      completed: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      compliant: "bg-green-500/20 text-green-400 border-green-500/30",
      pending: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      processing: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      sent: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      in_progress: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      pending_review: "bg-orange-500/20 text-orange-400 border-orange-500/30",
      disputed: "bg-orange-500/20 text-orange-400 border-orange-500/30",
      flagged: "bg-red-500/20 text-red-400 border-red-500/30",
      failed: "bg-red-500/20 text-red-400 border-red-500/30",
      consider: "bg-red-500/20 text-red-400 border-red-500/30",
      incomplete: "bg-gray-500/20 text-gray-400 border-gray-500/30",
    };
    return (
      <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium border ${colors[status] || colors.incomplete}`}>
        {status.replace(/_/g, " ").toUpperCase()}
      </span>
    );
  };

  const CheckIcon = ({ passed }: { passed: boolean | number | null }) => {
    if (passed === true || passed === 1) return <CheckCircle className="text-green-400" size={18} />;
    if (passed === false || passed === 0) return <XCircle className="text-red-400" size={18} />;
    return <Clock className="text-gray-500" size={18} />;
  };

  const navItems: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "overview", label: "Overview", icon: <Shield size={18} /> },
    { key: "identity", label: "Identity", icon: <Fingerprint size={18} /> },
    { key: "rtw", label: "Right to Work", icon: <UserCheck size={18} /> },
    { key: "dbs", label: "DBS Check", icon: <Search size={18} /> },
    { key: "cv", label: "CV Analysis", icon: <FileText size={18} /> },
    { key: "employment", label: "Employment", icon: <Briefcase size={18} /> },
    { key: "registration", label: "Registration", icon: <CheckCircle size={18} /> },
    { key: "references", label: "References", icon: <Send size={18} /> },
    { key: "training", label: "Training", icon: <GraduationCap size={18} /> },
  ];

  const complianceScore = compliance ? (compliance.score as number) : 0;

  return (
    <div className="min-h-screen bg-slate-900">
      {/* Header */}
      <header className="bg-slate-800/80 border-b border-slate-700 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="text-blue-400" size={28} />
          <h1 className="text-xl font-bold text-white">HealthVet AI</h1>
          <span className="text-xs bg-blue-600/30 text-blue-300 px-2 py-0.5 rounded-full">Candidate Portal</span>
        </div>
        <div className="flex items-center gap-4">
          {profile && <span className="text-slate-300 text-sm">{profile.first_name as string} {profile.last_name as string}</span>}
          <button onClick={() => { loadData(); loadCheckData(); }} className="text-slate-400 hover:text-white">
            <RefreshCw size={18} />
          </button>
          <button onClick={logout} className="text-slate-400 hover:text-red-400 flex items-center gap-1 text-sm">
            <LogOut size={16} /> Sign Out
          </button>
        </div>
      </header>

      {message && (
        <div className={`mx-6 mt-4 p-3 rounded-lg text-sm ${message.startsWith("Error") ? "bg-red-500/20 text-red-300 border border-red-500/30" : "bg-green-500/20 text-green-300 border border-green-500/30"}`}>
          {message}
        </div>
      )}

      <div className="flex">
        {/* Sidebar */}
        <nav className="w-56 min-h-screen bg-slate-800/50 border-r border-slate-700 p-4">
          <div className="space-y-1">
            {navItems.map((item) => (
              <button key={item.key} onClick={() => setTab(item.key)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  tab === item.key ? "bg-blue-600/20 text-blue-400 border border-blue-600/30" : "text-slate-400 hover:text-white hover:bg-slate-700/50"
                }`}>
                {item.icon}
                {item.label}
                {tab === item.key && <ChevronRight size={14} className="ml-auto" />}
              </button>
            ))}
          </div>

          {/* Compliance Score Card */}
          <div className="mt-6 p-4 bg-slate-700/50 rounded-xl border border-slate-600">
            <p className="text-xs text-slate-400 mb-2">Compliance Score</p>
            <div className="text-3xl font-bold text-white mb-2">{complianceScore}%</div>
            <div className="w-full bg-slate-600 rounded-full h-2">
              <div className="h-2 rounded-full transition-all" style={{ width: `${complianceScore}%`, backgroundColor: complianceScore >= 95 ? "#22c55e" : complianceScore >= 60 ? "#f59e0b" : "#ef4444" }} />
            </div>
            {compliance && <StatusBadge status={compliance.overall_status as string} />}
          </div>
        </nav>

        {/* Main Content */}
        <main className="flex-1 p-6">
          {/* Overview Tab */}
          {tab === "overview" && (
            <div className="space-y-6">
              <h2 className="text-xl font-bold text-white">Compliance Overview</h2>

              {/* Agency Affiliation */}
              {myAgencies.length > 0 && (
                <div className="bg-emerald-500/10 rounded-xl border border-emerald-500/30 p-5">
                  <div className="flex items-center gap-3 mb-3">
                    <Building2 className="text-emerald-400" size={20} />
                    <h3 className="text-md font-semibold text-white">Linked Agencies</h3>
                  </div>
                  <div className="space-y-2">
                    {myAgencies.map((agency) => (
                      <div key={agency.id as string} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                        <div>
                          <span className="text-white font-medium text-sm">{agency.name as string}</span>
                          {typeof agency.contact_name === "string" && agency.contact_name && <span className="text-slate-400 text-xs ml-3">Contact: {agency.contact_name}</span>}
                        </div>
                        <span className="text-xs text-slate-500">Joined {(agency.assigned_at as string)?.split("T")[0]}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Pending Invites */}
              {pendingInvites.length > 0 && (
                <div className="bg-blue-500/10 rounded-xl border border-blue-500/30 p-5">
                  <h3 className="text-md font-semibold text-white mb-3">Pending Agency Invites</h3>
                  <div className="space-y-2">
                    {pendingInvites.map((inv) => (
                      <div key={inv.id as string} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                        <div>
                          <span className="text-white text-sm">Invite from <span className="font-bold">{inv.agency_name as string}</span></span>
                        </div>
                        <button
                          onClick={async () => {
                            if (!token) return;
                            try {
                              await agencyInvitesApi.acceptInvite(token, inv.invite_code as string);
                              await loadData();
                            } catch (err) {
                              showMessage(`Error: ${err instanceof Error ? err.message : "Failed to accept invite"}`);
                            }
                          }}
                          className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-4 py-1.5 rounded-full font-medium transition-colors"
                        >
                          Accept Invite
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Compliance Checklist */}
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Vetting Checklist</h3>
                <div className="space-y-3">
                  {[
                    { label: "Identity Verification", key: "identity_verified", weight: "15%" },
                    { label: "Right to Work", key: "right_to_work_valid", weight: "15%" },
                    { label: "Enhanced DBS Check", key: "dbs_valid", weight: "20%" },
                    { label: "CV Validation", key: "cv_validated", weight: "5%" },
                    { label: "Employment Verification", key: "employment_verified", weight: "15%" },
                    { label: "Professional Registration", key: "registration_active", weight: "10%" },
                    { label: "References (2 required)", key: "references_verified", weight: "15%" },
                  ].map((item) => (
                    <div key={item.key} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <CheckIcon passed={compliance ? (compliance[item.key] as boolean) : null} />
                        <span className="text-slate-200 text-sm">{item.label}</span>
                      </div>
                      <span className="text-slate-500 text-xs">{item.weight}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Active Alerts */}
              {alerts.length > 0 && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <AlertTriangle className="text-amber-400" size={20} /> Active Alerts
                  </h3>
                  <div className="space-y-2">
                    {alerts.map((alert) => (
                      <div key={alert.id as string} className={`p-3 rounded-lg border ${
                        alert.severity === "critical" ? "bg-red-500/10 border-red-500/30" :
                        alert.severity === "high" ? "bg-orange-500/10 border-orange-500/30" :
                        "bg-yellow-500/10 border-yellow-500/30"}`}>
                        <div className="flex items-center justify-between">
                          <span className="text-slate-200 text-sm">{alert.message as string}</span>
                          <StatusBadge status={alert.severity as string} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Identity Verification Tab */}
          {tab === "identity" && (
            <div className="space-y-6">
              <h2 className="text-xl font-bold text-white">Identity Verification</h2>

              {/* Step progress indicator */}
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-4">
                <div className="flex items-center justify-between mb-1">
                  {([
                    { key: "select_doc", label: "Document Type", icon: <FileText size={16} /> },
                    { key: "upload_doc", label: "Upload Document", icon: <Upload size={16} /> },
                    { key: "selfie", label: "Selfie Photo", icon: <Camera size={16} /> },
                    { key: "processing", label: "Verification", icon: <Loader2 size={16} /> },
                    { key: "complete", label: "Results", icon: <CheckCircle size={16} /> },
                  ] as const).map((s, i, arr) => {
                    const steps: IdStep[] = ["select_doc", "upload_doc", "selfie", "processing", "complete"];
                    const currentIdx = steps.indexOf(idStep);
                    const stepIdx = steps.indexOf(s.key);
                    const isDone = stepIdx < currentIdx;
                    const isCurrent = s.key === idStep;
                    return (
                      <div key={s.key} className="flex items-center flex-1">
                        <div className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-medium ${
                          isCurrent ? "bg-blue-600/30 text-blue-300 border border-blue-500/40" :
                          isDone ? "text-green-400" : "text-slate-500"
                        }`}>
                          {isDone ? <CheckCircle size={14} /> : s.icon}
                          <span className="hidden sm:inline">{s.label}</span>
                        </div>
                        {i < arr.length - 1 && (
                          <div className={`flex-1 h-px mx-2 ${isDone ? "bg-green-500/40" : "bg-slate-700"}`} />
                        )}
                      </div>
                    );
                  })}
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  Powered by Onfido API &middot; Document authenticity + facial matching + liveness detection &middot; ~£2 per check
                </p>
              </div>

              {/* Step 1: Select Document Type */}
              {idStep === "select_doc" && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-lg font-semibold text-white mb-2">Step 1: Select Document Type</h3>
                  <p className="text-slate-400 text-sm mb-5">
                    Choose the identity document you will use for verification. In production, the Onfido Smart Capture SDK
                    opens here to guide you through document capture with real-time quality feedback.
                  </p>
                  <div className="grid grid-cols-2 gap-3 mb-6">
                    {([
                      { value: "passport", label: "Passport", desc: "International passport (any country)" },
                      { value: "driving_licence", label: "Driving Licence", desc: "UK or international driving licence" },
                      { value: "national_identity_card", label: "National ID Card", desc: "Government-issued national ID" },
                      { value: "residence_permit", label: "Residence Permit", desc: "UK Biometric Residence Permit" },
                    ]).map((doc) => (
                      <button key={doc.value} onClick={() => setIdDocType(doc.value)}
                        className={`p-4 rounded-lg border text-left transition-all ${
                          idDocType === doc.value
                            ? "bg-blue-600/20 border-blue-500/50 text-blue-300"
                            : "bg-slate-700/50 border-slate-600 text-slate-300 hover:border-slate-500"
                        }`}>
                        <div className="font-medium text-sm">{doc.label}</div>
                        <div className="text-xs text-slate-400 mt-1">{doc.desc}</div>
                      </button>
                    ))}
                  </div>
                  <button onClick={() => setIdStep("upload_doc")}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2">
                    Continue <ArrowRight size={16} />
                  </button>
                </div>
              )}

              {/* Step 2: Upload Document */}
              {idStep === "upload_doc" && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-lg font-semibold text-white mb-2">Step 2: Upload Identity Document</h3>
                  <p className="text-slate-400 text-sm mb-5">
                    Upload a clear photo of your {idDocType === "passport" ? "passport photo page" :
                    idDocType === "driving_licence" ? "driving licence (front)" :
                    idDocType === "national_identity_card" ? "national ID card (front)" :
                    "residence permit (front)"}. In production, the Onfido SDK captures this via your device camera
                    with real-time edge detection and quality checks.
                  </p>

                  <div className="bg-slate-700/30 border-2 border-dashed border-slate-600 rounded-xl p-8 text-center mb-4">
                    {idDocFileName ? (
                      <div className="space-y-2">
                        <CheckCircle className="mx-auto text-green-400" size={40} />
                        <p className="text-green-400 font-medium">{idDocFileName}</p>
                        <p className="text-xs text-slate-500">Document uploaded successfully</p>
                        <button onClick={() => setIdDocFileName("")}
                          className="text-xs text-slate-400 hover:text-red-400 underline">Remove and re-upload</button>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <Upload className="mx-auto text-slate-500" size={40} />
                        <p className="text-slate-400 text-sm">Click to upload or drag and drop</p>
                        <p className="text-xs text-slate-500">PNG, JPG, or PDF up to 10MB</p>
                        <label className="inline-block bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm cursor-pointer">
                          Select File
                          <input type="file" className="hidden" accept="image/*,.pdf"
                            onChange={(e) => {
                              const f = e.target.files?.[0];
                              if (f) setIdDocFileName(f.name);
                            }} />
                        </label>
                      </div>
                    )}
                  </div>

                  <div className="bg-slate-700/30 border border-slate-600/50 rounded-lg p-3 mb-5">
                    <p className="text-xs text-amber-300">
                      <strong>Onfido checks performed on this document:</strong> MRZ/barcode reading, visual authenticity analysis,
                      image integrity, data consistency, and data validation against issuing authority records.
                    </p>
                  </div>

                  <div className="flex gap-3">
                    <button onClick={() => setIdStep("select_doc")}
                      className="bg-slate-700 hover:bg-slate-600 text-slate-300 px-5 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2">
                      <ArrowLeft size={16} /> Back
                    </button>
                    <button onClick={() => { if (idDocFileName) setIdStep("selfie"); else showMessage("Error: Please upload your document first"); }}
                      disabled={!idDocFileName}
                      className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-500 text-white px-6 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2">
                      Continue <ArrowRight size={16} />
                    </button>
                  </div>
                </div>
              )}

              {/* Step 3: Selfie / Liveness */}
              {idStep === "selfie" && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-lg font-semibold text-white mb-2">Step 3: Selfie &amp; Liveness Check</h3>
                  <p className="text-slate-400 text-sm mb-5">
                    Upload a selfie photo or take one using your device camera. In production, the Onfido SDK uses
                    motion-based liveness detection — you&apos;ll be asked to move your head naturally to prove you are a real person.
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
                    {/* Selfie upload area */}
                    <div className="bg-slate-700/30 border-2 border-dashed border-slate-600 rounded-xl p-6 text-center">
                      {idSelfieFileName ? (
                        <div className="space-y-2">
                          <ScanFace className="mx-auto text-green-400" size={40} />
                          <p className="text-green-400 font-medium text-sm">{idSelfieFileName}</p>
                          <p className="text-xs text-slate-500">Selfie uploaded successfully</p>
                          <button onClick={() => setIdSelfieFileName("")}
                            className="text-xs text-slate-400 hover:text-red-400 underline">Remove and re-upload</button>
                        </div>
                      ) : (
                        <div className="space-y-3">
                          <Camera className="mx-auto text-slate-500" size={40} />
                          <p className="text-slate-400 text-sm">Upload selfie photo</p>
                          <p className="text-xs text-slate-500">Clear, front-facing photo</p>
                          <label className="inline-block bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm cursor-pointer">
                            Select Photo
                            <input type="file" className="hidden" accept="image/*"
                              onChange={(e) => {
                                const f = e.target.files?.[0];
                                if (f) setIdSelfieFileName(f.name);
                              }} />
                          </label>
                        </div>
                      )}
                    </div>

                    {/* Liveness info */}
                    <div className="bg-slate-700/30 border border-slate-600/50 rounded-xl p-5">
                      <h4 className="text-white font-medium text-sm mb-3 flex items-center gap-2">
                        <Eye size={16} className="text-blue-400" /> What Onfido Checks
                      </h4>
                      <ul className="space-y-2 text-xs text-slate-400">
                        <li className="flex items-start gap-2">
                          <CheckCircle size={12} className="text-blue-400 mt-0.5 shrink-0" />
                          <span><strong className="text-slate-300">Facial similarity:</strong> Compares your selfie against the photo on your identity document</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <CheckCircle size={12} className="text-blue-400 mt-0.5 shrink-0" />
                          <span><strong className="text-slate-300">Liveness detection:</strong> Motion analysis confirms you are a real person (not a photo of a photo)</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <CheckCircle size={12} className="text-blue-400 mt-0.5 shrink-0" />
                          <span><strong className="text-slate-300">Image quality:</strong> Checks lighting, blur, and face visibility</span>
                        </li>
                      </ul>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <button onClick={() => setIdStep("upload_doc")}
                      className="bg-slate-700 hover:bg-slate-600 text-slate-300 px-5 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2">
                      <ArrowLeft size={16} /> Back
                    </button>
                    <button onClick={runIdentityCheck}
                      disabled={loading || !idSelfieFileName}
                      className="bg-green-600 hover:bg-green-700 disabled:bg-slate-700 disabled:text-slate-500 text-white px-6 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2">
                      <Fingerprint size={16} /> {loading ? "Submitting..." : "Submit for Verification"}
                    </button>
                  </div>
                </div>
              )}

              {/* Step 4: Processing */}
              {idStep === "processing" && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-8 text-center">
                  <Loader2 className="mx-auto text-blue-400 animate-spin mb-4" size={48} />
                  <h3 className="text-lg font-semibold text-white mb-2">Verifying Your Identity</h3>
                  <p className="text-slate-400 text-sm mb-6">
                    Onfido is processing your document and selfie. This typically takes 60-120 seconds.
                  </p>
                  <div className="max-w-md mx-auto space-y-3">
                    {[
                      { label: "Initialising Onfido SDK session", done: true },
                      { label: "Uploading document for analysis", done: true },
                      { label: "Running MRZ / barcode extraction", done: true },
                      { label: "Checking visual authenticity", done: true },
                      { label: "Analysing facial similarity", done: false },
                      { label: "Running liveness detection", done: false },
                    ].map((step, i) => (
                      <div key={i} className="flex items-center gap-3 text-sm">
                        {step.done ? (
                          <CheckCircle size={16} className="text-green-400 shrink-0" />
                        ) : (
                          <Loader2 size={16} className="text-blue-400 animate-spin shrink-0" />
                        )}
                        <span className={step.done ? "text-slate-400" : "text-white"}>{step.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Step 5: Results */}
              {idStep === "complete" && idResult && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-white">Verification Results</h3>
                    <StatusBadge status={idResult.result as string} />
                  </div>

                  {/* Result summary */}
                  <div className={`p-4 rounded-lg border mb-5 ${
                    idResult.result === "clear"
                      ? "bg-green-500/10 border-green-500/30"
                      : "bg-red-500/10 border-red-500/30"
                  }`}>
                    <p className={`text-sm font-medium ${idResult.result === "clear" ? "text-green-400" : "text-red-400"}`}>
                      {idResult.result === "clear"
                        ? "Identity verified successfully. All Onfido checks passed."
                        : "Identity verification requires review. One or more checks returned 'consider'."}
                    </p>
                  </div>

                  {/* Detailed sub-checks */}
                  <div className="grid grid-cols-2 gap-4 mb-5">
                    <div className="p-3 bg-slate-700/50 rounded-lg">
                      <span className="text-xs text-slate-400 block mb-1">Document Authenticity</span>
                      <span className={`text-sm font-medium ${idResult.document_authenticity === "verified" ? "text-green-400" : "text-red-400"}`}>
                        {(idResult.document_authenticity as string || "").replace(/_/g, " ").toUpperCase()}
                      </span>
                    </div>
                    <div className="p-3 bg-slate-700/50 rounded-lg">
                      <span className="text-xs text-slate-400 block mb-1">Facial Match Score</span>
                      <span className={`text-sm font-medium ${(idResult.facial_match_score as number) >= 0.8 ? "text-green-400" : "text-red-400"}`}>
                        {((idResult.facial_match_score as number) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="p-3 bg-slate-700/50 rounded-lg">
                      <span className="text-xs text-slate-400 block mb-1">Liveness Detection</span>
                      <span className={`text-sm font-medium ${idResult.liveness_check === "passed" ? "text-green-400" : "text-red-400"}`}>
                        {(idResult.liveness_check as string || "").toUpperCase()}
                      </span>
                    </div>
                    <div className="p-3 bg-slate-700/50 rounded-lg">
                      <span className="text-xs text-slate-400 block mb-1">Address Verified</span>
                      <span className={`text-sm font-medium ${idResult.address_verified ? "text-green-400" : "text-red-400"}`}>
                        {idResult.address_verified ? "YES" : "NO"}
                      </span>
                    </div>
                  </div>

                  <button onClick={resetIdentityWizard}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2">
                    <RefreshCw size={16} /> Run Another Verification
                  </button>
                </div>
              )}

              {/* Verification History */}
              {identityChecks.length > 0 && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-md font-semibold text-white mb-3">Verification History</h3>
                  {identityChecks.map((check) => {
                    let details: Record<string, unknown> = {};
                    try { details = JSON.parse(check.details as string || "{}"); } catch { /* ignore */ }
                    const reports = details.reports as Record<string, Record<string, unknown>> | undefined;
                    return (
                      <div key={check.id as string} className="p-4 bg-slate-700/50 rounded-lg mb-2">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <StatusBadge status={check.result as string} />
                            {typeof check.document_type === "string" && check.document_type && (
                              <span className="text-xs bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded-full border border-blue-500/30">
                                {(details.document_type_label as string) || check.document_type.replace(/_/g, " ")}
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-slate-500">{check.started_at as string}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div><span className="text-slate-400">Document:</span> <span className="text-white">{check.document_authenticity as string}</span></div>
                          <div><span className="text-slate-400">Facial Match:</span> <span className="text-white">{((check.facial_match_score as number) * 100).toFixed(0)}%</span></div>
                          <div><span className="text-slate-400">Liveness:</span> <span className="text-white">{check.liveness_check as string}</span></div>
                          <div><span className="text-slate-400">Address:</span> <span className="text-white">{check.address_verified ? "Verified" : "Not Verified"}</span></div>
                        </div>
                        {reports && (
                          <div className="mt-3 pt-3 border-t border-slate-600/50">
                            <p className="text-xs text-slate-500 mb-2">Onfido Report Details</p>
                            <div className="grid grid-cols-3 gap-2 text-xs">
                              {reports.document && (
                                <div className="bg-slate-800/50 rounded p-2">
                                  <span className="text-slate-400 block mb-1">Document Report</span>
                                  <span className={`font-medium ${(reports.document as Record<string, unknown>).mrz_check === "clear" ? "text-green-400" : "text-amber-400"}`}>
                                    MRZ: {(reports.document as Record<string, unknown>).mrz_check as string}
                                  </span>
                                </div>
                              )}
                              {reports.facial_similarity && (
                                <div className="bg-slate-800/50 rounded p-2">
                                  <span className="text-slate-400 block mb-1">Facial Report</span>
                                  <span className={`font-medium ${(reports.facial_similarity as Record<string, unknown>).face_match_result === "clear" ? "text-green-400" : "text-amber-400"}`}>
                                    Match: {(reports.facial_similarity as Record<string, unknown>).face_match_result as string}
                                  </span>
                                </div>
                              )}
                              {reports.liveness && (
                                <div className="bg-slate-800/50 rounded p-2">
                                  <span className="text-slate-400 block mb-1">Liveness Report</span>
                                  <span className={`font-medium ${(reports.liveness as Record<string, unknown>).liveness_result === "clear" ? "text-green-400" : "text-amber-400"}`}>
                                    Result: {(reports.liveness as Record<string, unknown>).liveness_result as string}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Right to Work Tab */}
          {tab === "rtw" && (
            <div className="space-y-6">
              <h2 className="text-xl font-bold text-white">Right to Work Verification</h2>

              {/* Method Selector */}
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <p className="text-slate-300 text-sm mb-4">
                  Select your citizenship status to determine the appropriate verification method.
                  British and Irish citizens do not need a Home Office share code.
                </p>
                <div className="flex gap-2 mb-6">
                  <button onClick={() => setRtwMethod("uk_citizen")}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      rtwMethod === "uk_citizen"
                        ? "bg-blue-600 text-white"
                        : "bg-slate-700 text-slate-400 hover:text-white hover:bg-slate-600"
                    }`}>
                    British / Irish Citizen
                  </button>
                  <button onClick={() => setRtwMethod("share_code")}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      rtwMethod === "share_code"
                        ? "bg-blue-600 text-white"
                        : "bg-slate-700 text-slate-400 hover:text-white hover:bg-slate-600"
                    }`}>
                    Other Nationality (Share Code)
                  </button>
                </div>

                {rtwMethod === "uk_citizen" ? (
                  <div className="space-y-4">
                    <div className="bg-slate-700/30 border border-slate-600/50 rounded-lg p-3">
                      <p className="text-xs text-blue-300">
                        <strong>Home Office List A:</strong> British/Irish citizens can prove their right to work with a passport (current or expired),
                        or a UK birth/adoption/naturalisation certificate together with an official document showing your National Insurance number.
                      </p>
                    </div>

                    {/* Nationality */}
                    <div>
                      <label className="block text-slate-400 text-xs mb-1.5">Nationality</label>
                      <select value={rtwNationality} onChange={(e) => setRtwNationality(e.target.value)}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <option value="british">British</option>
                        <option value="irish">Irish</option>
                      </select>
                    </div>

                    {/* Document Type */}
                    <div>
                      <label className="block text-slate-400 text-xs mb-1.5">Document Type</label>
                      <select value={rtwDocType} onChange={(e) => setRtwDocType(e.target.value)}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                        {rtwNationality === "british" ? (
                          <>
                            <option value="uk_passport">UK Passport (current or expired)</option>
                            <option value="birth_certificate">UK Birth Certificate</option>
                            <option value="adoption_certificate">UK Adoption Certificate</option>
                            <option value="naturalisation_certificate">Certificate of Naturalisation</option>
                          </>
                        ) : (
                          <option value="irish_passport">Irish Passport or Passport Card (current or expired)</option>
                        )}
                      </select>
                    </div>

                    {/* Document Reference (optional for all) */}
                    <div>
                      <label className="block text-slate-400 text-xs mb-1.5">
                        Document Reference Number <span className="text-slate-500">(optional)</span>
                      </label>
                      <input type="text"
                        placeholder={rtwDocType.includes("passport") ? "Passport number" : "Certificate reference number"}
                        value={rtwDocRef} onChange={(e) => setRtwDocRef(e.target.value)}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    </div>

                    {/* NI Number - required for certificates */}
                    {["birth_certificate", "adoption_certificate", "naturalisation_certificate"].includes(rtwDocType) && (
                      <div>
                        <label className="block text-slate-400 text-xs mb-1.5">
                          National Insurance Number <span className="text-red-400">*</span>
                        </label>
                        <input type="text" placeholder="e.g. QQ 12 34 56 A"
                          value={rtwNiNumber} onChange={(e) => setRtwNiNumber(e.target.value)}
                          className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                        <p className="text-xs text-slate-500 mt-1">
                          Required when using a birth/adoption/naturalisation certificate. You must also hold an official document
                          (e.g. HMRC letter, P60, DWP letter) that shows your NI number and name.
                        </p>
                      </div>
                    )}

                    <button onClick={runRTWCheck} disabled={loading}
                      className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-6 py-2.5 rounded-lg text-sm font-medium">
                      {loading ? "Verifying..." : "Verify Right to Work"}
                    </button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="bg-slate-700/30 border border-slate-600/50 rounded-lg p-3">
                      <p className="text-xs text-amber-300">
                        <strong>Non-UK/Irish nationals:</strong> Enter your Home Office digital share code to verify your right to work.
                        You can generate a share code at{" "}
                        <a href="https://www.gov.uk/prove-right-to-work" target="_blank" rel="noopener noreferrer"
                          className="underline text-blue-400 hover:text-blue-300">gov.uk/prove-right-to-work</a>.
                        Includes ongoing visa expiry monitoring and alerts.
                      </p>
                    </div>
                    <div className="flex gap-3">
                      <input type="text" placeholder="Enter Home Office share code (e.g. ABC123XYZ)"
                        value={shareCode} onChange={(e) => setShareCode(e.target.value)}
                        className="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      <button onClick={runRTWCheck} disabled={loading || !shareCode}
                        className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-6 py-2.5 rounded-lg text-sm font-medium">
                        {loading ? "Verifying..." : "Verify"}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {rtwChecks.length > 0 && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-md font-semibold text-white mb-3">Verification History</h3>
                  {rtwChecks.map((check) => (
                    <div key={check.id as string} className="p-4 bg-slate-700/50 rounded-lg mb-2">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <StatusBadge status={check.result as string} />
                          {(check.verification_method as string) === "uk_citizen" && (
                            <span className="text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                              {(check.nationality as string) === "irish" ? "Irish" : "UK"} Citizen
                            </span>
                          )}
                          {(check.verification_method as string) === "share_code" && (
                            <span className="text-xs bg-purple-500/20 text-purple-400 border border-purple-500/30 px-2 py-0.5 rounded-full">
                              Share Code
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-slate-500">{check.checked_at as string}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div><span className="text-slate-400">Status:</span> <span className="text-white">{(check.visa_type as string) || "N/A"}</span></div>
                        <div><span className="text-slate-400">Expiry:</span> <span className="text-white">{(check.visa_expiry as string) || "No expiry"}</span></div>
                        <div><span className="text-slate-400">Restrictions:</span> <span className="text-white">{(check.work_restrictions as string) || "None"}</span></div>
                        {(check.verification_method as string) === "uk_citizen" && (check.document_type as string) && (
                          <div><span className="text-slate-400">Document:</span> <span className="text-white">{(check.document_type as string).replace(/_/g, " ")}</span></div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* DBS Check Tab */}
          {tab === "dbs" && (
            <div className="space-y-6">
              <h2 className="text-xl font-bold text-white">Enhanced DBS Check</h2>
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <p className="text-slate-300 text-sm mb-4">
                  Automated enhanced DBS submission via uCheck API. ID validated, submitted electronically,
                  status tracked via webhooks. Typical turnaround: 24-72 hours.
                </p>
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-xs text-slate-400">Providers: uCheck &middot; CareCheck &middot; First Advantage</span>
                  <span className="text-xs text-slate-400">&middot; Cost: £38-£60</span>
                </div>
                <button onClick={runDBSCheck} disabled={loading}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-6 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2">
                  <Search size={16} /> {loading ? "Submitting..." : "Submit Enhanced DBS Check"}
                </button>
              </div>

              {dbsChecks.length > 0 && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-md font-semibold text-white mb-3">DBS Check History</h3>
                  {dbsChecks.map((check) => (
                    <div key={check.id as string} className="p-4 bg-slate-700/50 rounded-lg mb-2">
                      <div className="flex items-center justify-between mb-2">
                        <StatusBadge status={check.result as string} />
                        <span className="text-xs text-slate-500">{check.submitted_at as string}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div><span className="text-slate-400">Certificate:</span> <span className="text-white">{(check.certificate_number as string) || "Pending"}</span></div>
                        <div><span className="text-slate-400">Ref:</span> <span className="text-white">{check.application_ref as string}</span></div>
                        <div><span className="text-slate-400">Type:</span> <span className="text-white">{check.check_type as string}</span></div>
                        <div><span className="text-slate-400">Renewal:</span> <span className="text-white">{(check.next_renewal as string)?.split("T")[0] || "N/A"}</span></div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* CV Analysis Tab */}
          {tab === "cv" && (
            <div className="space-y-6">
              <h2 className="text-xl font-bold text-white">AI CV & Document Analysis</h2>
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <p className="text-slate-300 text-sm mb-4">
                  AI-powered analysis: employment gap detection, overlap identification, qualification verification,
                  fraud risk scoring, and cross-referencing with professional registers.
                  Employment history is automatically extracted to pre-fill the Employment tab.
                </p>

                {/* File Upload */}
                <div className="mb-4">
                  <label className="block text-slate-400 text-xs mb-1.5">Upload CV File</label>
                  <div className="flex items-center gap-3">
                    <label className="cursor-pointer bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg px-4 py-2.5 text-sm text-slate-300 flex items-center gap-2 transition-colors">
                      <Upload size={16} />
                      {cvFileName ? cvFileName : "Choose file (PDF, DOCX, TXT)"}
                      <input type="file" accept=".pdf,.docx,.doc,.txt,.rtf" onChange={handleCvFileSelect} className="hidden" />
                    </label>
                    {cvFileName && (
                      <button onClick={() => { setCvFileName(""); }} className="text-slate-500 hover:text-red-400 text-xs">Clear</button>
                    )}
                  </div>
                </div>

                {/* Divider */}
                <div className="flex items-center gap-3 mb-4">
                  <div className="flex-1 border-t border-slate-600"></div>
                  <span className="text-slate-500 text-xs">OR paste your CV text below</span>
                  <div className="flex-1 border-t border-slate-600"></div>
                </div>

                <textarea rows={8} placeholder="Paste your CV text here..."
                  value={cvText} onChange={(e) => setCvText(e.target.value)}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-3" />
                <button onClick={runCVAnalysis} disabled={loading || !cvText}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-6 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2">
                  <FileText size={16} /> {loading ? "Analysing..." : "Analyse CV"}
                </button>
              </div>

              {cvAnalyses.length > 0 && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-md font-semibold text-white mb-3">Analysis Results</h3>
                  {cvAnalyses.map((analysis) => (
                    <div key={analysis.id as string} className="p-4 bg-slate-700/50 rounded-lg mb-3">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <span className="text-slate-200 text-sm font-medium">Fraud Risk Score:</span>
                          <span className={`text-lg font-bold ${
                            (analysis.fraud_risk_score as number) < 0.3 ? "text-green-400" :
                            (analysis.fraud_risk_score as number) < 0.6 ? "text-amber-400" : "text-red-400"
                          }`}>{((analysis.fraud_risk_score as number) * 100).toFixed(0)}%</span>
                        </div>
                        <div className="flex items-center gap-2">
                          {typeof analysis.cv_file_name === "string" && analysis.cv_file_name && (
                            <span className="text-xs bg-slate-600 text-slate-300 px-2 py-0.5 rounded">{analysis.cv_file_name}</span>
                          )}
                          <span className="text-xs text-slate-500">{analysis.analysed_at as string}</span>
                        </div>
                      </div>
                      <p className="text-slate-300 text-sm mb-3">{analysis.ai_summary as string}</p>
                      <div className="grid grid-cols-1 gap-2 text-sm">
                        <div className="p-2 bg-slate-600/50 rounded"><span className="text-slate-400">Gaps:</span> <span className="text-slate-200">{analysis.gap_analysis as string}</span></div>
                        <div className="p-2 bg-slate-600/50 rounded"><span className="text-slate-400">Qualifications:</span> <span className="text-slate-200">{analysis.qualification_flags as string}</span></div>
                      </div>
                      {typeof analysis.employment_entries === "string" && analysis.employment_entries && (
                        <div className="mt-3 p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                          <p className="text-blue-300 text-xs font-medium mb-1">
                            Employment history extracted — view and manage entries in the Employment tab
                          </p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Employment History Tab */}
          {tab === "employment" && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-white">Employment History Verification</h2>
                <button onClick={() => setAddingEntry(true)} disabled={addingEntry}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
                  <Plus size={16} /> Add Entry
                </button>
              </div>

              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <p className="text-slate-300 text-sm mb-2">
                  Verify your employment history from the past 5 years. Entries are pre-filled from your CV analysis.
                  For each role, add the contact details of someone who can confirm your job title, dates, and reason for leaving.
                </p>
                <p className="text-slate-400 text-xs">
                  Verification requests are sent and managed the same way as references — with domain verification,
                  fraud detection, and automated reminders.
                </p>
              </div>

              {/* Add new entry form */}
              {addingEntry && (
                <div className="bg-slate-800/80 rounded-xl border border-blue-500/30 p-6">
                  <h3 className="text-md font-semibold text-white mb-3">Add Employment Entry</h3>
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <input type="text" placeholder="Employer name *" value={newEntry.employer_name}
                      onChange={(e) => setNewEntry({ ...newEntry, employer_name: e.target.value })}
                      className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    <input type="text" placeholder="Job title *" value={newEntry.job_title}
                      onChange={(e) => setNewEntry({ ...newEntry, job_title: e.target.value })}
                      className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    <input type="month" placeholder="Start date" value={newEntry.start_date}
                      onChange={(e) => setNewEntry({ ...newEntry, start_date: e.target.value })}
                      className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    <input type="month" placeholder="End date" value={newEntry.end_date}
                      onChange={(e) => setNewEntry({ ...newEntry, end_date: e.target.value })}
                      className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    <input type="text" placeholder="Reason for leaving" value={newEntry.reason_for_leaving}
                      onChange={(e) => setNewEntry({ ...newEntry, reason_for_leaving: e.target.value })}
                      className="col-span-2 bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  </div>
                  <div className="flex gap-2">
                    <button onClick={addEmploymentEntry} disabled={loading || !newEntry.employer_name || !newEntry.job_title}
                      className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-4 py-2 rounded-lg text-sm font-medium">
                      {loading ? "Adding..." : "Add Entry"}
                    </button>
                    <button onClick={() => { setAddingEntry(false); setNewEntry({ employer_name: "", job_title: "", start_date: "", end_date: "", reason_for_leaving: "" }); }}
                      className="bg-slate-700 hover:bg-slate-600 text-slate-300 px-4 py-2 rounded-lg text-sm">
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Employment entries */}
              {employmentEntries.length === 0 && !addingEntry && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-8 text-center">
                  <Briefcase className="text-slate-600 mx-auto mb-3" size={32} />
                  <p className="text-slate-400 text-sm">No employment history entries yet.</p>
                  <p className="text-slate-500 text-xs mt-1">Upload and analyse your CV first to auto-extract entries, or add them manually.</p>
                </div>
              )}

              {employmentEntries.map((entry) => {
                const entryId = entry.id as string;
                const isEditing = editingEntryId === entryId;
                const hasVerification = employmentVerifications.some((v) => v.employment_id === entryId);
                const verification = employmentVerifications.find((v) => v.employment_id === entryId);
                const vf = verifierForm[entryId] || { name: "", email: "", job_title: "" };

                return (
                  <div key={entryId} className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                    {isEditing ? (
                      /* Edit mode */
                      <div>
                        <h3 className="text-sm font-semibold text-blue-400 mb-3">Edit Employment Entry</h3>
                        <div className="grid grid-cols-2 gap-3 mb-3">
                          <input type="text" placeholder="Employer name" value={editForm.employer_name || ""}
                            onChange={(e) => setEditForm({ ...editForm, employer_name: e.target.value })}
                            className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                          <input type="text" placeholder="Job title" value={editForm.job_title || ""}
                            onChange={(e) => setEditForm({ ...editForm, job_title: e.target.value })}
                            className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                          <input type="month" value={editForm.start_date || ""}
                            onChange={(e) => setEditForm({ ...editForm, start_date: e.target.value })}
                            className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                          <input type="month" value={editForm.end_date || ""}
                            onChange={(e) => setEditForm({ ...editForm, end_date: e.target.value })}
                            className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                          <input type="text" placeholder="Reason for leaving" value={editForm.reason_for_leaving || ""}
                            onChange={(e) => setEditForm({ ...editForm, reason_for_leaving: e.target.value })}
                            className="col-span-2 bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                        </div>
                        <div className="flex gap-2">
                          <button onClick={() => updateEmploymentEntry(entryId)} disabled={loading}
                            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium">Save</button>
                          <button onClick={() => { setEditingEntryId(null); setEditForm({}); }}
                            className="bg-slate-700 hover:bg-slate-600 text-slate-300 px-4 py-2 rounded-lg text-sm">Cancel</button>
                        </div>
                      </div>
                    ) : (
                      /* View mode */
                      <div>
                        <div className="flex items-start justify-between mb-3">
                          <div>
                            <h3 className="text-white font-semibold text-sm">{entry.employer_name as string}</h3>
                            <p className="text-blue-400 text-sm">{entry.job_title as string}</p>
                            <p className="text-slate-400 text-xs mt-0.5">
                              {entry.start_date as string || "?"} — {entry.is_current ? "Present" : (entry.end_date as string || "?")}
                              {entry.source === "cv_extracted" && (
                                <span className="ml-2 bg-purple-500/20 text-purple-400 border border-purple-500/30 px-1.5 py-0 rounded text-xs">
                                  Extracted from CV
                                </span>
                              )}
                            </p>
                            {typeof entry.reason_for_leaving === "string" && entry.reason_for_leaving && (
                              <p className="text-slate-500 text-xs mt-0.5">Reason: {entry.reason_for_leaving}</p>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {hasVerification && verification && (
                              <StatusBadge status={verification.status as string} />
                            )}
                            <button onClick={() => {
                              setEditingEntryId(entryId);
                              setEditForm({
                                employer_name: (entry.employer_name as string) || "",
                                job_title: (entry.job_title as string) || "",
                                start_date: (entry.start_date as string) || "",
                                end_date: (entry.end_date as string) || "",
                                reason_for_leaving: (entry.reason_for_leaving as string) || "",
                              });
                            }} className="text-slate-400 hover:text-blue-400">
                              <Edit3 size={14} />
                            </button>
                            <button onClick={() => deleteEmploymentEntry(entryId)} className="text-slate-400 hover:text-red-400">
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>

                        {/* Verification result */}
                        {hasVerification && verification && (
                          <div className="mt-3 p-3 bg-slate-700/50 rounded-lg text-sm">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-slate-400">Verified by:</span>
                              <span className="text-white">{verification.verifier_name as string}</span>
                              <span className="text-slate-500">({verification.verifier_email as string})</span>
                              {verification.domain_verified ? (
                                <span className="text-xs bg-green-500/20 text-green-400 border border-green-500/30 px-1.5 py-0 rounded">Domain OK</span>
                              ) : (
                                <span className="text-xs bg-red-500/20 text-red-400 border border-red-500/30 px-1.5 py-0 rounded">Domain Mismatch</span>
                              )}
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-xs">
                              <div><span className="text-slate-400">Job Title Confirmed:</span> <span className={verification.job_title_confirmed ? "text-green-400" : "text-red-400"}>{verification.job_title_confirmed ? "Yes" : "No"}</span></div>
                              <div><span className="text-slate-400">Dates Confirmed:</span> <span className={verification.dates_confirmed ? "text-green-400" : "text-red-400"}>{verification.dates_confirmed ? "Yes" : "No"}</span></div>
                              {typeof verification.reason_for_leaving_confirmed === "string" && verification.reason_for_leaving_confirmed && (
                                <div className="col-span-2"><span className="text-slate-400">Reason for Leaving:</span> <span className="text-slate-300">{verification.reason_for_leaving_confirmed}</span></div>
                              )}
                              {typeof verification.additional_comments === "string" && verification.additional_comments && (
                                <div className="col-span-2"><span className="text-slate-400">Comments:</span> <span className="text-slate-300">{verification.additional_comments}</span></div>
                              )}
                              {typeof verification.fraud_flags === "string" && verification.fraud_flags && (
                                <div className="col-span-2"><span className="text-red-400">Fraud Flags:</span> <span className="text-red-300">{verification.fraud_flags}</span></div>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Verifier form - show only if no verification sent yet */}
                        {!hasVerification && (
                          <div className="mt-3 p-3 bg-slate-700/30 border border-slate-600/50 rounded-lg">
                            <p className="text-slate-400 text-xs mb-2 font-medium">
                              Add verifier details — someone from this employer who can confirm your role:
                            </p>
                            <div className="grid grid-cols-3 gap-2 mb-2">
                              <input type="text" placeholder="Verifier name *" value={vf.name}
                                onChange={(e) => setVerifierForm({ ...verifierForm, [entryId]: { ...vf, name: e.target.value } })}
                                className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:ring-2 focus:ring-blue-500" />
                              <input type="email" placeholder="Verifier email *" value={vf.email}
                                onChange={(e) => setVerifierForm({ ...verifierForm, [entryId]: { ...vf, email: e.target.value } })}
                                className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:ring-2 focus:ring-blue-500" />
                              <input type="text" placeholder="Verifier job title" value={vf.job_title}
                                onChange={(e) => setVerifierForm({ ...verifierForm, [entryId]: { ...vf, job_title: e.target.value } })}
                                className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:ring-2 focus:ring-blue-500" />
                            </div>
                            <button onClick={() => sendEmploymentVerification(entryId)} disabled={loading || !vf.name || !vf.email}
                              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-4 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1">
                              <Send size={12} /> {loading ? "Sending..." : "Send Verification Request"}
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Summary */}
              {employmentEntries.length > 0 && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-4">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">
                      {employmentEntries.length} employment {employmentEntries.length === 1 ? "entry" : "entries"} &middot;{" "}
                      {employmentVerifications.filter((v) => v.status === "verified").length} verified &middot;{" "}
                      {employmentVerifications.filter((v) => v.status === "disputed" || v.status === "flagged").length} flagged
                    </span>
                    <span className="text-slate-500 text-xs">
                      {employmentEntries.filter((e) => !employmentVerifications.some((v) => v.employment_id === e.id)).length} pending verification
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Registration Check Tab */}
          {tab === "registration" && (
            <div className="space-y-6">
              <h2 className="text-xl font-bold text-white">Professional Registration Check</h2>
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <p className="text-slate-300 text-sm mb-4">
                  Automated verification against public registers: NMC (nurses), GMC (doctors),
                  HCPC (allied health), GPhC (pharmacists). Checks active status, sanctions, and conditions.
                </p>
                {profile && (
                  <div className="flex items-center gap-4 mb-4">
                    <span className="text-sm text-slate-300">Body: <strong className="text-white">{(profile.registration_body as string) || "Not set"}</strong></span>
                    <span className="text-sm text-slate-300">Number: <strong className="text-white">{(profile.registration_number as string) || "Not set"}</strong></span>
                  </div>
                )}
                <button onClick={runRegistrationCheck} disabled={loading}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-6 py-2.5 rounded-lg text-sm font-medium">
                  {loading ? "Checking..." : "Check Registration"}
                </button>
              </div>

              {regChecks.length > 0 && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-md font-semibold text-white mb-3">Registration History</h3>
                  {regChecks.map((check) => (
                    <div key={check.id as string} className="p-4 bg-slate-700/50 rounded-lg mb-2">
                      <div className="flex items-center justify-between mb-2">
                        <StatusBadge status={check.result as string} />
                        <span className="text-xs text-slate-500">{check.last_checked as string}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div><span className="text-slate-400">Body:</span> <span className="text-white">{check.body as string}</span></div>
                        <div><span className="text-slate-400">Active:</span> <span className="text-white">{check.is_active ? "Yes" : "No"}</span></div>
                        <div><span className="text-slate-400">Sanctions:</span> <span className="text-white">{(check.sanctions as string) || "None"}</span></div>
                        <div><span className="text-slate-400">Next Check:</span> <span className="text-white">{(check.next_check as string)?.split("T")[0] || "N/A"}</span></div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* References Tab */}
          {tab === "references" && (
            <div className="space-y-6">
              <h2 className="text-xl font-bold text-white">Automated References</h2>
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <p className="text-slate-300 text-sm mb-4">
                  Secure reference links sent to employers. Includes AI sentiment analysis,
                  fraud detection (IP matching, domain verification), and auto-reminders.
                </p>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <input type="text" placeholder="Referee name" value={refName} onChange={(e) => setRefName(e.target.value)}
                    className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  <input type="email" placeholder="Referee email" value={refEmail} onChange={(e) => setRefEmail(e.target.value)}
                    className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  <input type="text" placeholder="Organisation" value={refOrg} onChange={(e) => setRefOrg(e.target.value)}
                    className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  <input type="text" placeholder="Job title" value={refTitle} onChange={(e) => setRefTitle(e.target.value)}
                    className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <button onClick={createReference} disabled={loading || !refName || !refEmail}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-6 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2">
                  <Send size={16} /> {loading ? "Sending..." : "Send Reference Request"}
                </button>
              </div>

              {references.length > 0 && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-md font-semibold text-white mb-3">References ({references.length})</h3>
                  {references.map((ref) => (
                    <div key={ref.id as string} className="p-4 bg-slate-700/50 rounded-lg mb-2">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-white text-sm font-medium">{ref.referee_name as string}</span>
                        <StatusBadge status={ref.status as string} />
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div><span className="text-slate-400">Email:</span> <span className="text-slate-300">{ref.referee_email as string}</span></div>
                        <div><span className="text-slate-400">Domain Verified:</span> <span className="text-slate-300">{ref.domain_verified ? "Yes" : "No"}</span></div>
                        <div><span className="text-slate-400">Reminders:</span> <span className="text-slate-300">{ref.reminder_count as number}</span></div>
                        {ref.sentiment_score !== null && (
                          <div><span className="text-slate-400">Sentiment:</span> <span className="text-slate-300">{((ref.sentiment_score as number) * 100).toFixed(0)}%</span></div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Training Certificates Tab */}
          {tab === "training" && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-white flex items-center gap-2"><GraduationCap size={22} className="text-blue-400" /> Training Certificates</h2>
                <button onClick={downloadAuditPack} disabled={downloadingAudit}
                  className="bg-green-600 hover:bg-green-700 disabled:bg-green-800 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
                  <Download size={16} /> {downloadingAudit ? "Generating..." : "Download CQC Audit Pack"}
                </button>
              </div>

              {/* Training Compliance Summary */}
              {trainingCompliance && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-md font-semibold text-white mb-3">Compliance Summary</h3>
                  <div className="grid grid-cols-4 gap-4">
                    <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                      <p className="text-slate-400 text-xs mb-1">Total Certs</p>
                      <p className="text-2xl font-bold text-white">{trainingCompliance.total_certificates as number}</p>
                    </div>
                    <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                      <p className="text-slate-400 text-xs mb-1">Valid</p>
                      <p className="text-2xl font-bold text-green-400">{trainingCompliance.valid as number}</p>
                    </div>
                    <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                      <p className="text-slate-400 text-xs mb-1">Expired</p>
                      <p className="text-2xl font-bold text-red-400">{trainingCompliance.expired as number}</p>
                    </div>
                    <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                      <p className="text-slate-400 text-xs mb-1">Compliance Rate</p>
                      <p className="text-2xl font-bold text-blue-400">{trainingCompliance.compliance_rate as number}%</p>
                    </div>
                  </div>
                  {(trainingCompliance.missing_mandatory as string[])?.length > 0 && (
                    <div className="mt-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                      <p className="text-amber-300 text-sm font-medium mb-1">Missing Mandatory Certificates:</p>
                      <p className="text-amber-200 text-xs">{(trainingCompliance.missing_mandatory as string[]).join(", ")}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Add New Certificate */}
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-3">Add Training Certificate</h3>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <select value={newCertName} onChange={(e) => setNewCertName(e.target.value)}
                    className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="">Select certificate...</option>
                    {trainingStandards.map((s) => (
                      <option key={s.name as string} value={s.name as string}>{s.name as string} ({s.category as string})</option>
                    ))}
                    <option value="__custom">Other (custom)</option>
                  </select>
                  <select value={newCertCategory} onChange={(e) => setNewCertCategory(e.target.value)}
                    className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="mandatory">Mandatory</option>
                    <option value="recommended">Recommended</option>
                    <option value="role_specific">Role-Specific</option>
                  </select>
                  <input type="text" placeholder="Provider" value={newCertProvider} onChange={(e) => setNewCertProvider(e.target.value)}
                    className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  <input type="text" placeholder="Certificate Reference" value={newCertRef} onChange={(e) => setNewCertRef(e.target.value)}
                    className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  <div>
                    <label className="text-slate-400 text-xs mb-1 block">Issue Date</label>
                    <input type="date" value={newCertIssueDate} onChange={(e) => setNewCertIssueDate(e.target.value)}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  </div>
                  <div>
                    <label className="text-slate-400 text-xs mb-1 block">Expiry Date</label>
                    <input type="date" value={newCertExpiryDate} onChange={(e) => setNewCertExpiryDate(e.target.value)}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  </div>
                </div>
                <button onClick={addTrainingCert} disabled={loading || !newCertName || newCertName === "__custom"}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-6 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2">
                  <Plus size={16} /> {loading ? "Adding..." : "Add Certificate"}
                </button>
              </div>

              {/* Existing Certificates */}
              {trainingCerts.length > 0 && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-md font-semibold text-white mb-3">Your Certificates ({trainingCerts.length})</h3>
                  <div className="space-y-2">
                    {trainingCerts.map((cert) => (
                      <div key={cert.id as string} className="p-4 bg-slate-700/50 rounded-lg">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-3">
                            <span className="text-white text-sm font-medium">{cert.certificate_name as string}</span>
                            <span className={`text-xs px-2 py-0.5 rounded-full ${cert.category === "mandatory" ? "bg-red-500/20 text-red-300" : cert.category === "recommended" ? "bg-blue-500/20 text-blue-300" : "bg-purple-500/20 text-purple-300"}`}>{String(cert.category)}</span>
                            <StatusBadge status={cert.status as string} />
                          </div>
                          <button onClick={() => deleteTrainingCert(cert.id as string)} className="text-red-400 hover:text-red-300"><Trash2 size={14} /></button>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-sm">
                          {cert.provider ? <div><span className="text-slate-400">Provider:</span> <span className="text-slate-300">{String(cert.provider)}</span></div> : null}
                          {cert.issue_date ? <div><span className="text-slate-400">Issued:</span> <span className="text-slate-300">{String(cert.issue_date)}</span></div> : null}
                          {cert.expiry_date ? <div><span className="text-slate-400">Expires:</span> <span className={`${cert.status === "expired" ? "text-red-400" : "text-slate-300"}`}>{String(cert.expiry_date)}</span></div> : null}
                          {cert.certificate_ref ? <div><span className="text-slate-400">Ref:</span> <span className="text-slate-300">{String(cert.certificate_ref)}</span></div> : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

