import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { candidatesApi, complianceApi, monitoringApi, dashboardApi, agencyInvitesApi, agencyServicesApi, billingApi, reportsApi, agencyRevetApi, checksApi } from "../api/client";
import {
  Shield, CheckCircle, XCircle, Clock, AlertTriangle, Users,
  BarChart3, Bell, LogOut, RefreshCw, Eye, Mail, Send, Copy, Trash2,
  DollarSign, FileText, Briefcase, CreditCard, Download,
} from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend, BarChart, Bar, XAxis, YAxis } from "recharts";

type Tab = "dashboard" | "candidates" | "alerts" | "candidate-detail" | "invites" | "billing" | "audit";

export default function AgencyDashboard() {
  const { token, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("dashboard");
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [, setCandidates] = useState<Record<string, unknown>[]>([]);
  const [alerts, setAlerts] = useState<Record<string, unknown>[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<Record<string, unknown> | null>(null);
  const [candidateCompliance, setCandidateCompliance] = useState<Record<string, unknown> | null>(null);
  const [candidateAlerts, setCandidateAlerts] = useState<Record<string, unknown>[]>([]);
  const [invites, setInvites] = useState<Record<string, unknown>[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteSuccess, setInviteSuccess] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [copiedCode, setCopiedCode] = useState("");

  // Services breakdown data
  const [servicesData, setServicesData] = useState<Record<string, unknown> | null>(null);

  // Candidate status tracking
  const [candidatesWithStatus, setCandidatesWithStatus] = useState<Record<string, unknown>[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [ragFilter, setRagFilter] = useState<string>("all");

  // Billing state
  const [subscription, setSubscription] = useState<Record<string, unknown> | null>(null);
  const [billingHistory, setBillingHistory] = useState<Record<string, unknown>[]>([]);
  const [selectedTier, setSelectedTier] = useState("starter");
  const [selectedBillingMethod, setSelectedBillingMethod] = useState("stripe");
  const [subscribing, setSubscribing] = useState(false);
  const [downloadingAudit, setDownloadingAudit] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState<string | null>(null);

  // Multi-select audit state
  const [selectedAuditCandidates, setSelectedAuditCandidates] = useState<string[]>([]);
  const [downloadingBulkAudit, setDownloadingBulkAudit] = useState(false);
  const [downloadingSingleAudit, setDownloadingSingleAudit] = useState("");

  // Invite cost confirmation modal state
  const [inviteCostModalOpen, setInviteCostModalOpen] = useState(false);
  const [invitePricing, setInvitePricing] = useState<{ vetting_total: number; monitoring_annual_price: number } | null>(null);
  const [includeMonitoring, setIncludeMonitoring] = useState(false);
  const [invitePricingLoading, setInvitePricingLoading] = useState(false);

  // Remaining checks state (subscription credit)
  const [remainingChecks, setRemainingChecks] = useState<Record<string, unknown> | null>(null);

  // Agency billing mode state
  const [billingMode, setBillingMode] = useState<string>("manual_invoicing");
  const [payingInvoice, setPayingInvoice] = useState<string | null>(null);
  const [, setPaymentResult] = useState<Record<string, unknown> | null>(null);

  // Imposter declaration state
  const [imposterDeclaration, setImposterDeclaration] = useState<Record<string, unknown> | null>(null);
  const [imposterDeclLoading, setImposterDeclLoading] = useState(false);
  const [imposterDeclConfirmed, setImposterDeclConfirmed] = useState(false);
  const [imposterDocsVerified, setImposterDocsVerified] = useState<string[]>([]);
  const [imposterDeclError, setImposterDeclError] = useState<string | null>(null);

  // Re-vet state
  const [revetModalOpen, setRevetModalOpen] = useState(false);
  const [revetCandidate, setRevetCandidate] = useState<Record<string, unknown> | null>(null);
  const [revetSections, setRevetSections] = useState<string[]>([]);
  const [revetLoading, setRevetLoading] = useState(false);
  const [revetResult, setRevetResult] = useState<Record<string, unknown> | null>(null);
  const [revetRequests, setRevetRequests] = useState<Record<string, unknown>[]>([]);

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      const [s, c, a, inv] = await Promise.all([
        dashboardApi.getStats(token),
        candidatesApi.list(token).catch(() => []),
        monitoringApi.getAlerts(token).catch(() => []),
        agencyInvitesApi.listInvites(token).catch(() => []),
      ]);
      setStats(s);
      setCandidates(c);
      setAlerts(a);
      setInvites(inv);

      // Load services breakdown and candidates with status
      try {
        const svc = await agencyServicesApi.getMyServices(token);
        setServicesData(svc);
      } catch {
        // endpoint may not exist yet
      }
      try {
        const cws = await agencyServicesApi.getCandidatesWithStatus(token);
        setCandidatesWithStatus(cws);
      } catch {
        // fallback to regular candidates
        setCandidatesWithStatus(c);
      }
      // Load billing mode
      try {
        const bm = await agencyServicesApi.getBillingMode(token);
        setBillingMode(bm.billing_mode || "manual_invoicing");
      } catch { /* ignore */ }
      // Load billing data
      try {
        const sub = await billingApi.getSubscription(token, "me");
        if (sub && sub.status !== "none") setSubscription(sub);
      } catch { /* ignore */ }
      try {
        const hist = await billingApi.getHistory(token, "me");
        setBillingHistory(hist);
      } catch { /* ignore */ }
      // Load remaining checks for subscription credit tracking
      try {
        const rc = await billingApi.getRemainingChecks(token, "me");
        setRemainingChecks(rc);
      } catch { /* ignore */ }
      // Load re-vet requests
      try {
        const rr = await agencyRevetApi.listRevetRequests(token);
        setRevetRequests(rr);
      } catch { /* ignore */ }
    } catch (err) {
      console.error("Failed to load data", err);
    }
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);

  const viewCandidate = async (candidate: Record<string, unknown>) => {
    setSelectedCandidate(candidate);
    setTab("candidate-detail");
    if (token) {
      try {
        const [comp, alts] = await Promise.all([
          complianceApi.get(token, candidate.id as string).catch(() => null),
          monitoringApi.getAlerts(token, candidate.id as string).catch(() => []),
        ]);
        setCandidateCompliance(comp);
        setCandidateAlerts(alts);
        // Load imposter declaration
        try {
          const decls = await checksApi.getImposterDeclarations(token, candidate.id as string);
          setImposterDeclaration(decls && decls.length > 0 ? decls[0] : null);
        } catch { setImposterDeclaration(null); }
      } catch {
        // ignore
      }
      setImposterDeclConfirmed(false);
      setImposterDocsVerified([]);
    }
  };

  const submitImposterDeclaration = async () => {
    if (!token || !selectedCandidate || !imposterDeclConfirmed) return;
    setImposterDeclLoading(true);
    setImposterDeclError(null);
    try {
      const declarationText = "I confirm that I have conducted an in-person (or compliant video) imposter check and confirm the individual matches the documentation.";
      const result = await checksApi.submitImposterDeclaration(
        token,
        selectedCandidate.id as string,
        declarationText,
        imposterDocsVerified.length > 0 ? imposterDocsVerified : undefined,
      );
      setImposterDeclaration(result);
      // Refresh compliance to reflect new RTW status
      const comp = await complianceApi.get(token, selectedCandidate.id as string).catch(() => null);
      setCandidateCompliance(comp);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to submit imposter declaration";
      setImposterDeclError(msg);
      console.error("Failed to submit imposter declaration", err);
    } finally {
      setImposterDeclLoading(false);
    }
  };

  const toggleImposterDoc = (doc: string) => {
    setImposterDocsVerified(prev => prev.includes(doc) ? prev.filter(d => d !== doc) : [...prev, doc]);
  };

  const openRevetModal = (candidate: Record<string, unknown>) => {
    setRevetCandidate(candidate);
    setRevetSections([]);
    setRevetResult(null);
    setRevetModalOpen(true);
  };

  const toggleRevetSection = (section: string) => {
    setRevetSections(prev => prev.includes(section) ? prev.filter(s => s !== section) : [...prev, section]);
  };

  const submitRevetRequest = async () => {
    if (!token || !revetCandidate || revetSections.length === 0) return;
    setRevetLoading(true);
    try {
      const cId = (revetCandidate.id as string) || (revetCandidate.candidate_id as string);
      const result = await agencyRevetApi.requestRevet(token, cId, revetSections);
      setRevetResult(result);
      await loadData();
    } catch (err) {
      console.error("Re-vet request failed", err);
    } finally {
      setRevetLoading(false);
    }
  };

  const resolveAlert = async (alertId: string) => {
    if (!token) return;
    try {
      await monitoringApi.resolveAlert(token, alertId);
      await loadData();
    } catch (err) {
      console.error("Failed to resolve alert", err);
    }
  };

  const openInviteCostModal = async () => {
    if (!token || !inviteEmail.trim()) return;
    setInvitePricingLoading(true);
    setInviteError("");
    try {
      const pricing = await agencyInvitesApi.getVettingPricing(token);
      setInvitePricing(pricing);
      setIncludeMonitoring(false);
      // Also refresh remaining checks
      try {
        const rc = await billingApi.getRemainingChecks(token, "me");
        setRemainingChecks(rc);
      } catch { /* ignore */ }
      setInviteCostModalOpen(true);
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : "Failed to load pricing");
    } finally {
      setInvitePricingLoading(false);
    }
  };

  const confirmAndSendInvite = async () => {
    if (!token || !inviteEmail.trim()) return;
    setInviteLoading(true);
    setInviteError("");
    setInviteSuccess("");
    setPaymentResult(null);
    try {
      const result = await agencyInvitesApi.createInvite(token, inviteEmail.trim(), includeMonitoring);
      const payment = result.payment as Record<string, unknown> | undefined;
      if (payment && payment.payment_required) {
        // PAYG or subscription overflow — show payment info
        setPaymentResult(payment);
        const amt = payment.amount as number;
        const status = payment.status as string;
        if (status === "awaiting_payment") {
          setInviteSuccess(`Invite sent to ${inviteEmail}. Payment of £${amt?.toFixed(2)} required. Use Pay Now in Billing History.`);
        } else if (status === "credits_exceeded") {
          setInviteSuccess(`Invite sent to ${inviteEmail}. Subscription credits exceeded — £${amt?.toFixed(2)} overage charge created.`);
        } else {
          setInviteSuccess(`Invite sent to ${inviteEmail}. Code: ${result.invite_code as string}`);
        }
      } else if (payment && payment.status === "paid_by_subscription") {
        const creditsLeft = payment.credits_remaining as number;
        setInviteSuccess(`Invite sent to ${inviteEmail}. Paid by subscription credit. ${creditsLeft?.toFixed(1)} credits remaining.`);
      } else {
        setInviteSuccess(`Invite sent to ${inviteEmail}. Code: ${result.invite_code as string}`);
      }
      setInviteEmail("");
      setInviteCostModalOpen(false);
      await loadData();
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : "Failed to send invite");
    } finally {
      setInviteLoading(false);
    }
  };

  const handlePayInvoice = async (invoiceId: string) => {
    if (!token) return;
    setPayingInvoice(invoiceId);
    try {
      await agencyServicesApi.payInvoice(token, invoiceId);
      await loadData();
    } catch (err) {
      console.error("Payment failed", err);
      setInviteError(err instanceof Error ? err.message : "Payment failed");
    } finally {
      setPayingInvoice(null);
    }
  };

  const revokeInvite = async (inviteId: string) => {
    if (!token) return;
    try {
      await agencyInvitesApi.revokeInvite(token, inviteId);
      await loadData();
    } catch (err) {
      console.error("Failed to revoke invite", err);
    }
  };

  const copyInviteLink = (code: string) => {
    const link = `${window.location.origin}/?invite=${code}`;
    navigator.clipboard.writeText(link).then(() => {
      setCopiedCode(code);
      setTimeout(() => setCopiedCode(""), 2000);
    });
  };

  const subscribeToPlan = async () => {
    if (!token) return;
    setSubscribing(true);
    try {
      const result = await billingApi.subscribe(token, { agency_id: "me", tier: selectedTier, billing_method: selectedBillingMethod });
      setSubscription(result);
      loadData();
    } catch (err) { console.error("Failed to subscribe", err); }
    finally { setSubscribing(false); }
  };

  const cancelSubscription = async () => {
    if (!token) return;
    try {
      await billingApi.cancel(token, "me");
      setSubscription(null);
      loadData();
    } catch (err) { console.error("Failed to cancel", err); }
  };

  const downloadAgencyAudit = async () => {
    if (!token) return;
    setDownloadingAudit(true);
    try {
      const resp = await reportsApi.downloadAgencyAudit(token, "me");
      if (!resp.ok) throw new Error("Failed");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "agency_audit_pack.pdf"; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { console.error("Download failed", err); }
    finally { setDownloadingAudit(false); }
  };

  const downloadCandidateAudit = async (candidateId: string) => {
    if (!token) return;
    setDownloadingSingleAudit(candidateId);
    try {
      const resp = await reportsApi.downloadCandidateAudit(token, candidateId);
      if (!resp.ok) throw new Error("Failed");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = `candidate_audit_${candidateId}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { console.error("Download failed", err); }
    finally { setDownloadingSingleAudit(""); }
  };

  const downloadBulkCandidateAudit = async () => {
    if (!token || selectedAuditCandidates.length === 0) return;
    setDownloadingBulkAudit(true);
    try {
      const resp = await reportsApi.downloadBulkCandidateAudit(token, selectedAuditCandidates);
      if (!resp.ok) throw new Error("Failed");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "bulk_candidate_audit.pdf"; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { console.error("Download failed", err); }
    finally { setDownloadingBulkAudit(false); }
  };

  const toggleAuditCandidate = (candidateId: string) => {
    setSelectedAuditCandidates((prev) =>
      prev.includes(candidateId) ? prev.filter((id) => id !== candidateId) : [...prev, candidateId]
    );
  };

  const toggleAllAuditCandidates = () => {
    if (selectedAuditCandidates.length === candidatesWithStatus.length) {
      setSelectedAuditCandidates([]);
    } else {
      setSelectedAuditCandidates(candidatesWithStatus.map((c) => String(c.id || c.candidate_id)));
    }
  };

  const updateCandidateStatus = async (candidateId: string, newStatus: string) => {
    if (!token) return;
    setUpdatingStatus(candidateId);
    try {
      await agencyServicesApi.updateCandidateStatus(token, candidateId, newStatus);
      // Update local state
      setCandidatesWithStatus((prev) =>
        prev.map((c) => (c.id === candidateId || c.candidate_id === candidateId)
          ? { ...c, employment_status: newStatus }
          : c
        )
      );
      setCandidates((prev) =>
        prev.map((c) => (c.id === candidateId)
          ? { ...c, employment_status: newStatus }
          : c
        )
      );
    } catch (err) {
      console.error("Failed to update status", err);
    } finally {
      setUpdatingStatus(null);
    }
  };

  const StatusBadge = ({ status }: { status: string }) => {
    const colors: Record<string, string> = {
      compliant: "bg-green-500/20 text-green-400 border-green-500/30",
      clear: "bg-green-500/20 text-green-400 border-green-500/30",
      active: "bg-green-500/20 text-green-400 border-green-500/30",
      valid: "bg-green-500/20 text-green-400 border-green-500/30",
      hired: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
      pending: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      in_progress: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      vetting: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      pending_review: "bg-orange-500/20 text-orange-400 border-orange-500/30",
      flagged: "bg-red-500/20 text-red-400 border-red-500/30",
      rejected: "bg-red-500/20 text-red-400 border-red-500/30",
      left_business: "bg-gray-500/20 text-gray-400 border-gray-500/30",
      critical: "bg-red-500/20 text-red-400 border-red-500/30",
      high: "bg-orange-500/20 text-orange-400 border-orange-500/30",
      medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      low: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      incomplete: "bg-gray-500/20 text-gray-400 border-gray-500/30",
    };
    return (
      <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium border ${colors[status] || colors.incomplete}`}>
        {status.replace(/_/g, " ").toUpperCase()}
      </span>
    );
  };

  const CheckIcon = ({ passed }: { passed: boolean | number | null }) => {
    if (passed === true || passed === 1) return <CheckCircle className="text-green-400" size={16} />;
    if (passed === false || passed === 0) return <XCircle className="text-red-400" size={16} />;
    return <Clock className="text-gray-500" size={16} />;
  };

  const pieData = stats ? [
    { name: "Compliant", value: stats.compliant as number, color: "#22c55e" },
    { name: "Pending", value: stats.pending as number, color: "#f59e0b" },
    { name: "Flagged", value: stats.flagged as number, color: "#ef4444" },
  ] : [];

  // RAG status helper
  const getRagStatus = (candidate: Record<string, unknown>): { label: string; color: string; bg: string; border: string } => {
    const status = String(candidate.compliance_status || "incomplete");
    const score = Number(candidate.compliance_score || 0);
    if (status === "compliant" || score >= 80) return { label: "GREEN", color: "text-green-400", bg: "bg-green-500/20", border: "border-green-500/30" };
    if (status === "flagged" || status === "failed" || score < 40) return { label: "RED", color: "text-red-400", bg: "bg-red-500/20", border: "border-red-500/30" };
    return { label: "AMBER", color: "text-amber-400", bg: "bg-amber-500/20", border: "border-amber-500/30" };
  };

  const RagBadge = ({ candidate }: { candidate: Record<string, unknown> }) => {
    const rag = getRagStatus(candidate);
    return <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-bold border ${rag.bg} ${rag.color} ${rag.border}`}>{rag.label}</span>;
  };

  // Services breakdown from backend
  const services = servicesData?.services as Record<string, unknown>[] | undefined;
  const _totalCostFromServices = servicesData?.total_cost as number | undefined;
  const totalRevenueFromServices = servicesData?.total_revenue as number | undefined;
  const _totalMargin = servicesData?.total_margin as number | undefined;
  void _totalCostFromServices;
  void _totalMargin;

  // Filter candidates by status and RAG

  const REVET_SECTION_OPTIONS = [
    { key: "identity", label: "Identity Verification", price: 15.00 },
    { key: "rtw", label: "Right to Work", price: 10.00 },
    { key: "dbs", label: "DBS Check", price: 25.00 },
    { key: "cv", label: "CV Analysis", price: 8.00 },
    { key: "registration", label: "Professional Registration", price: 12.00 },
    { key: "references", label: "References", price: 10.00 },
    { key: "training", label: "Training Certificates", price: 8.00 },
  ];

  const revetTotalCost = revetSections.reduce((sum, sec) => {
    const opt = REVET_SECTION_OPTIONS.find(o => o.key === sec);
    return sum + (opt?.price || 0);
  }, 0);

  const filteredCandidates = candidatesWithStatus.filter((c) => {
    const empStatus = (c.employment_status as string) || "vetting";
    const passesStatus = statusFilter === "all" || empStatus === statusFilter;
    const rag = getRagStatus(c);
    const passesRag = ragFilter === "all" || rag.label === ragFilter;
    return passesStatus && passesRag;
  });

  return (
    <div className="min-h-screen bg-slate-900">
      <header className="bg-slate-800/80 border-b border-slate-700 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="text-blue-400" size={28} />
          <h1 className="text-xl font-bold text-white">HealthVet AI</h1>
          <span className="text-xs bg-emerald-600/30 text-emerald-300 px-2 py-0.5 rounded-full">Agency Dashboard</span>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={loadData} className="text-slate-400 hover:text-white"><RefreshCw size={18} /></button>
          <button onClick={logout} className="text-slate-400 hover:text-red-400 flex items-center gap-1 text-sm">
            <LogOut size={16} /> Sign Out
          </button>
        </div>
      </header>

      {/* Navigation Tabs */}
      <div className="bg-slate-800/50 border-b border-slate-700 px-6">
        <div className="flex gap-1">
          {[
            { key: "dashboard" as Tab, label: "Dashboard", icon: <BarChart3 size={16} /> },
            { key: "candidates" as Tab, label: "Candidates", icon: <Users size={16} /> },
            { key: "invites" as Tab, label: `Invites (${invites.length})`, icon: <Mail size={16} /> },
            { key: "alerts" as Tab, label: `Alerts (${alerts.length})`, icon: <Bell size={16} /> },
            { key: "audit" as Tab, label: "CQC Audit", icon: <FileText size={16} /> },
            { key: "billing" as Tab, label: "Billing", icon: <CreditCard size={16} /> },
          ].map((item) => (
            <button key={item.key} onClick={() => setTab(item.key)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-all ${
                tab === item.key ? "text-blue-400 border-blue-400" : "text-slate-400 border-transparent hover:text-white"
              }`}>
              {item.icon} {item.label}
            </button>
          ))}
        </div>
      </div>

      <main className="p-6">
        {/* Dashboard Tab */}
        {tab === "dashboard" && stats && (
          <div className="space-y-6">
            {/* Risk Flags Panel */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-5">
              <h3 className="text-md font-semibold text-white mb-3 flex items-center gap-2"><AlertTriangle className="text-amber-400" size={18} /> Candidate Risk Overview</h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-center">
                  <div className="text-3xl font-bold text-green-400">{stats.compliant as number}</div>
                  <div className="text-xs text-green-300 mt-1 font-medium">COMPLIANT</div>
                  <div className="text-xs text-slate-400 mt-0.5">Fully vetted &amp; up to date</div>
                </div>
                <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg text-center">
                  <div className="text-3xl font-bold text-amber-400">{stats.pending as number}</div>
                  <div className="text-xs text-amber-300 mt-1 font-medium">AT RISK</div>
                  <div className="text-xs text-slate-400 mt-0.5">Pending checks or expiring soon</div>
                </div>
                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-center">
                  <div className="text-3xl font-bold text-red-400">{stats.flagged as number}</div>
                  <div className="text-xs text-red-300 mt-1 font-medium">NON-COMPLIANT</div>
                  <div className="text-xs text-slate-400 mt-0.5">Failed checks or expired docs</div>
                </div>
              </div>
              {(stats.active_alerts as number) > 0 && (
                <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-center gap-2">
                  <Bell className="text-amber-400" size={16} />
                  <span className="text-amber-300 text-sm font-medium">{stats.active_alerts as number} active alert{(stats.active_alerts as number) !== 1 ? "s" : ""}</span>
                  <span className="text-slate-400 text-sm">requiring attention</span>
                  <button onClick={() => setTab("alerts")} className="ml-auto text-xs bg-amber-600/20 text-amber-400 border border-amber-600/30 px-3 py-1 rounded-full hover:bg-amber-600/30">View Alerts</button>
                </div>
              )}
            </div>

            {/* Subscription Credit Countdown */}
            {remainingChecks && (remainingChecks.has_subscription as boolean) && (
              <div className="bg-slate-800/80 rounded-xl border border-blue-500/30 p-5">
                <h3 className="text-md font-semibold text-white mb-3 flex items-center gap-2"><CreditCard className="text-blue-400" size={18} /> Monthly Credit Balance</h3>
                <div className="grid grid-cols-5 gap-3">
                  <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg text-center">
                    <div className="text-2xl font-bold text-blue-400">{(remainingChecks.credits_total as number) >= 999999 ? "\u221E" : (remainingChecks.credits_total as number ?? remainingChecks.monthly_checks as number)}</div>
                    <div className="text-xs text-blue-300 mt-1 font-medium">MONTHLY CREDITS</div>
                  </div>
                  <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-center">
                    <div className="text-2xl font-bold text-green-400">{(remainingChecks.credits_remaining as number) >= 999999 ? "\u221E" : typeof remainingChecks.credits_remaining === "number" ? (remainingChecks.credits_remaining as number).toFixed(1) : remainingChecks.checks_remaining as number}</div>
                    <div className="text-xs text-green-300 mt-1 font-medium">REMAINING</div>
                  </div>
                  <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg text-center">
                    <div className="text-2xl font-bold text-amber-400">{typeof remainingChecks.credits_used === "number" ? (remainingChecks.credits_used as number).toFixed(1) : remainingChecks.checks_used as number}</div>
                    <div className="text-xs text-amber-300 mt-1 font-medium">USED THIS MONTH</div>
                  </div>
                  <div className="p-4 bg-purple-500/10 border border-purple-500/30 rounded-lg text-center">
                    <div className="text-2xl font-bold text-purple-400">{typeof remainingChecks.rollover_credits === "number" ? (remainingChecks.rollover_credits as number).toFixed(1) : "0"}</div>
                    <div className="text-xs text-purple-300 mt-1 font-medium">ROLLOVER</div>
                  </div>
                  <div className="p-4 bg-slate-700/50 border border-slate-600 rounded-lg text-center">
                    <div className="text-lg font-bold text-white">{remainingChecks.tier_name as string}</div>
                    <div className="text-xs text-slate-400 mt-1 font-medium">{remainingChecks.allow_rollover ? "ROLLOVER ON" : "NO ROLLOVER"}</div>
                  </div>
                </div>
                {/* Progress bar */}
                {typeof remainingChecks.credits_total === "number" && (remainingChecks.credits_total as number) < 999999 && (
                  <div className="mt-3">
                    <div className="flex justify-between text-xs text-slate-400 mb-1">
                      <span>{typeof remainingChecks.credits_used === "number" ? (remainingChecks.credits_used as number).toFixed(1) : 0} used of {(remainingChecks.credits_total as number) + (typeof remainingChecks.rollover_credits === "number" ? (remainingChecks.rollover_credits as number) : 0)} total</span>
                      <span>{typeof remainingChecks.credits_remaining === "number" ? (remainingChecks.credits_remaining as number).toFixed(1) : 0} remaining</span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-2.5">
                      <div className="bg-gradient-to-r from-blue-500 to-blue-400 h-2.5 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(100, ((typeof remainingChecks.credits_used === "number" ? remainingChecks.credits_used as number : 0) / ((remainingChecks.credits_total as number) + (typeof remainingChecks.rollover_credits === "number" ? (remainingChecks.rollover_credits as number) : 0))) * 100)}%` }} />
                    </div>
                  </div>
                )}
                {typeof remainingChecks.credits_remaining === "number" && (remainingChecks.credits_remaining as number) <= 2 && (remainingChecks.credits_total as number) < 999999 && (
                  <div className="mt-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-2">
                    <AlertTriangle className="text-red-400" size={16} />
                    <span className="text-red-300 text-sm font-medium">
                      {(remainingChecks.credits_remaining as number) <= 0
                        ? `No credits remaining. Additional checks charged at overage rate${typeof remainingChecks.overage_rate === "number" ? ` (£${remainingChecks.overage_rate}/credit)` : ""}.`
                        : `Only ${(remainingChecks.credits_remaining as number).toFixed(1)} credits remaining this month.`}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Stats Cards */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: "Total Candidates", value: stats.total_candidates, color: "blue" },
                { label: "Compliant", value: stats.compliant, color: "green" },
                { label: "Pending", value: stats.pending, color: "yellow" },
                { label: "Flagged", value: stats.flagged, color: "red" },
              ].map((stat) => (
                <div key={stat.label} className="bg-slate-800/80 rounded-xl border border-slate-700 p-5">
                  <p className="text-slate-400 text-xs mb-1">{stat.label}</p>
                  <p className="text-3xl font-bold text-white">{stat.value as number}</p>
                </div>
              ))}
            </div>

            {/* Second Row Stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-5">
                <p className="text-slate-400 text-xs mb-1">Compliance Rate</p>
                <p className="text-3xl font-bold text-green-400">{stats.compliance_rate as number}%</p>
              </div>
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-5">
                <p className="text-slate-400 text-xs mb-1">Active Alerts</p>
                <p className="text-3xl font-bold text-amber-400">{stats.active_alerts as number}</p>
              </div>
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-5">
                <p className="text-slate-400 text-xs mb-1">Avg Completion</p>
                <p className="text-3xl font-bold text-blue-400">{stats.avg_completion_time_hours as number}h</p>
              </div>
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-2 gap-6">
              {/* FIXED Pie Chart - increased height, donut style, Legend */}
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4">Compliance Distribution</h3>
                <ResponsiveContainer width="100%" height={320}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="45%"
                      outerRadius={100}
                      innerRadius={50}
                      dataKey="value"
                      paddingAngle={2}
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={index} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#1e293b",
                        border: "1px solid #334155",
                        borderRadius: "8px",
                        color: "white",
                      }}
                    />
                    <Legend
                      verticalAlign="bottom"
                      height={36}
                      formatter={(value: string, entry: Record<string, unknown>) => {
                        const payload = entry.payload as Record<string, unknown> | undefined;
                        const val = payload?.value ?? "";
                        return <span style={{ color: "#cbd5e1", fontSize: "13px" }}>{value}: {String(val)}</span>;
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Services Summary Chart */}
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4 flex items-center gap-2">
                  <FileText className="text-blue-400" size={18} /> Services Summary
                </h3>
                {services && services.length > 0 ? (
                  <ResponsiveContainer width="100%" height={320}>
                    <BarChart data={services.map((s) => ({
                      name: (s.label as string || "").length > 12
                        ? (s.label as string || "").substring(0, 12) + "..."
                        : (s.label as string || ""),
                      count: s.count as number,
                      revenue: s.total_sell as number,
                    }))}>
                      <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} angle={-20} textAnchor="end" height={60} />
                      <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#1e293b",
                          border: "1px solid #334155",
                          borderRadius: "8px",
                          color: "white",
                        }}
                        formatter={(value: number, name: string) => {
                          if (name === "revenue") return [`£{value.toFixed(2)}`, "Revenue"];
                          return [value, "Checks"];
                        }}
                      />
                      <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} name="count" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-64 text-slate-400">
                    <div className="text-center">
                      <FileText className="mx-auto mb-2 text-slate-600" size={32} />
                      <p className="text-sm">No services data available yet</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* REDESIGNED Services Rendered Breakdown */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-4 flex items-center gap-2">
                <DollarSign className="text-green-400" size={18} /> Services Rendered
              </h3>
              {services && services.length > 0 ? (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-slate-700">
                          <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Service</th>
                          <th className="text-right text-xs text-slate-400 font-medium px-4 py-3">Checks Completed</th>
                          <th className="text-right text-xs text-slate-400 font-medium px-4 py-3">Unit Price</th>
                          <th className="text-right text-xs text-slate-400 font-medium px-4 py-3">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {services.map((svc) => {
                          const checkType = svc.check_type as string;
                          const label = svc.label as string;
                          const count = svc.count as number;
                          const sellPrice = svc.sell_price as number;
                          const totalSell = svc.total_sell as number;
                          return (
                            <tr key={checkType} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                              <td className="px-4 py-3">
                                <div className="flex items-center gap-2">
                                  <Briefcase className="text-blue-400" size={14} />
                                  <span className="text-sm text-white">{label}</span>
                                </div>
                              </td>
                              <td className="px-4 py-3 text-right">
                                <span className="text-sm text-white font-medium">{count}</span>
                              </td>
                              <td className="px-4 py-3 text-right">
                                <span className="text-sm text-slate-300">£{sellPrice.toFixed(2)}</span>
                              </td>
                              <td className="px-4 py-3 text-right">
                                <span className="text-sm text-green-400 font-medium">£{totalSell.toFixed(2)}</span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                      <tfoot>
                        <tr className="border-t-2 border-slate-600">
                          <td className="px-4 py-3 text-sm text-white font-bold" colSpan={3}>Total Services Charged</td>
                          <td className="px-4 py-3 text-right">
                            <span className="text-lg text-green-400 font-bold">
                              £{(totalRevenueFromServices ?? 0).toFixed(2)}
                            </span>
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* Summary Cards */}
                  <div className="grid grid-cols-3 gap-4 mt-4">
                    <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                      <p className="text-slate-400 text-xs mb-1">Total Services</p>
                      <p className="text-2xl font-bold text-white">
                        {services.reduce((sum, s) => sum + (s.count as number), 0)}
                      </p>
                      <p className="text-slate-500 text-xs mt-1">checks completed</p>
                    </div>
                    <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                      <p className="text-slate-400 text-xs mb-1">Total Amount</p>
                      <p className="text-2xl font-bold text-green-400">£{(totalRevenueFromServices ?? 0).toFixed(2)}</p>
                      <p className="text-slate-500 text-xs mt-1">services charged</p>
                    </div>
                    <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                      <p className="text-slate-400 text-xs mb-1">Avg per Candidate</p>
                      <p className="text-2xl font-bold text-blue-400">
                        £{stats.total_candidates && (stats.total_candidates as number) > 0
                          ? ((totalRevenueFromServices ?? 0) / (stats.total_candidates as number)).toFixed(2)
                          : "0.00"}
                      </p>
                      <p className="text-slate-500 text-xs mt-1">per candidate</p>
                    </div>
                  </div>
                </>
              ) : (
                <div className="p-8 text-center text-slate-400">
                  <DollarSign className="mx-auto mb-2 text-slate-600" size={32} />
                  <p className="text-sm">No services data available yet.</p>
                  <p className="text-xs text-slate-500 mt-1">Services will appear here once candidates complete vetting checks.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Candidates Tab - WITH STATUS TRACKING */}
        {tab === "candidates" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-white">Candidates ({candidatesWithStatus.length})</h2>
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">Status:</span>
                  {["all", "vetting", "hired", "rejected", "left_business"].map((s) => (
                    <button
                      key={s}
                      onClick={() => setStatusFilter(s)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                        statusFilter === s
                          ? "bg-blue-600 text-white"
                          : "bg-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700"
                      }`}
                    >
                      {s === "all" ? "All" : s.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">RAG:</span>
                  {["all", "GREEN", "AMBER", "RED"].map((r) => (
                    <button
                      key={r}
                      onClick={() => setRagFilter(r)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                        ragFilter === r
                          ? r === "GREEN" ? "bg-green-600 text-white" : r === "AMBER" ? "bg-amber-600 text-white" : r === "RED" ? "bg-red-600 text-white" : "bg-blue-600 text-white"
                          : r === "GREEN" ? "bg-green-500/20 text-green-400 hover:bg-green-500/30" : r === "AMBER" ? "bg-amber-500/20 text-amber-400 hover:bg-amber-500/30" : r === "RED" ? "bg-red-500/20 text-red-400 hover:bg-red-500/30" : "bg-slate-700/50 text-slate-400 hover:bg-slate-700"
                      }`}
                    >
                      {r === "all" ? "All RAG" : r}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {filteredCandidates.length === 0 ? (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-12 text-center">
                <Users className="text-slate-600 mx-auto mb-3" size={48} />
                <p className="text-slate-400">
                  {statusFilter === "all" && ragFilter === "all" ? "No candidates assigned yet" : `No candidates matching current filters`}
                </p>
                <p className="text-slate-500 text-sm mt-1">
                  {statusFilter === "all" && ragFilter === "all"
                    ? "Candidates will appear here once assigned to your agency"
                    : "Try a different filter combination"}
                </p>
              </div>
            ) : (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Name</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Profession</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Registration</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Score</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">RAG</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Compliance</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Employment Status</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCandidates.map((c) => {
                      const cId = (c.id as string) || (c.candidate_id as string);
                      const empStatus = (c.employment_status as string) || "vetting";
                      return (
                        <tr key={cId} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                          <td className="px-4 py-3 text-sm text-white">{c.first_name as string} {c.last_name as string}</td>
                          <td className="px-4 py-3 text-sm text-slate-300">{(c.profession as string) || "N/A"}</td>
                          <td className="px-4 py-3 text-sm text-slate-300">{(c.registration_body as string) || "N/A"} {(c.registration_number as string) || ""}</td>
                          <td className="px-4 py-3 text-sm font-medium text-white">{c.compliance_score as number}%</td>
                          <td className="px-4 py-3"><RagBadge candidate={c} /></td>
                          <td className="px-4 py-3"><StatusBadge status={c.compliance_status as string} /></td>
                          <td className="px-4 py-3">
                            <select
                              value={empStatus}
                              onChange={(e) => updateCandidateStatus(cId, e.target.value)}
                              disabled={updatingStatus === cId}
                              className={`text-xs rounded-lg px-2 py-1.5 border cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                                empStatus === "hired"
                                  ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                                  : empStatus === "rejected"
                                  ? "bg-red-500/20 text-red-400 border-red-500/30"
                                  : empStatus === "left_business"
                                  ? "bg-gray-500/20 text-gray-400 border-gray-500/30"
                                  : "bg-blue-500/20 text-blue-400 border-blue-500/30"
                              } ${updatingStatus === cId ? "opacity-50" : ""}`}
                            >
                              <option value="vetting">Vetting</option>
                              <option value="hired">Hired</option>
                              <option value="rejected">Rejected</option>
                              <option value="left_business">Left Business</option>
                            </select>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <button onClick={() => viewCandidate(c)} className="text-blue-400 hover:text-blue-300 text-sm flex items-center gap-1">
                                <Eye size={14} /> View
                              </button>
                              <button onClick={() => openRevetModal(c)} className="text-amber-400 hover:text-amber-300 text-sm flex items-center gap-1">
                                <RefreshCw size={14} /> Re-Vet
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Re-Vet Requests History */}
            {revetRequests.length > 0 && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-700">
                  <h3 className="text-md font-semibold text-white flex items-center gap-2">
                    <RefreshCw className="text-amber-400" size={18} /> Re-Vet Requests ({revetRequests.length})
                  </h3>
                </div>
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Candidate</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Sections</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Status</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Requested</th>
                    </tr>
                  </thead>
                  <tbody>
                    {revetRequests.map((rr) => (
                      <tr key={rr.id as string} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                        <td className="px-4 py-3 text-sm text-white">{rr.candidate_name as string}</td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-1">
                            {(rr.sections as string[])?.map((sec: string) => (
                              <span key={sec} className="text-xs bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-full">
                                {sec.replace(/_/g, " ")}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-4 py-3"><StatusBadge status={rr.status as string} /></td>
                        <td className="px-4 py-3 text-sm text-slate-400">{(rr.created_at as string)?.split("T")[0]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Invites Tab */}
        {tab === "invites" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Mail className="text-blue-400" size={22} /> Candidate Invites
            </h2>

            {/* Send Invite Form */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-md font-semibold text-white">Send New Invite</h3>
                <span className={`text-xs px-2 py-1 rounded-full border ${
                  billingMode === "online_payment" ? "bg-green-500/20 text-green-400 border-green-500/30" :
                  billingMode === "subscription" ? "bg-blue-500/20 text-blue-400 border-blue-500/30" :
                  "bg-slate-500/20 text-slate-400 border-slate-500/30"
                }`}>
                  {billingMode === "online_payment" ? "Pay-As-You-Go" :
                   billingMode === "subscription" ? "Subscription" : "Manual Invoice"}
                </span>
              </div>
              <p className="text-slate-400 text-sm mb-4">
                Enter a candidate's email to generate a unique invite link. They'll register using that link and be automatically assigned to your agency.
                {billingMode === "online_payment" && " You will be asked to confirm payment after sending."}
                {billingMode === "subscription" && " This will use your subscription credits."}
              </p>
              <div className="flex gap-3">
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="candidate@example.com"
                  className="flex-1 bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                  onKeyDown={(e) => e.key === "Enter" && openInviteCostModal()}
                />
                <button
                  onClick={openInviteCostModal}
                  disabled={inviteLoading || invitePricingLoading || !inviteEmail.trim()}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:opacity-50 text-white px-6 py-2.5 rounded-lg font-medium text-sm flex items-center gap-2 transition-colors"
                >
                  <Send size={16} /> {invitePricingLoading ? "Loading..." : "Send Invite"}
                </button>
              </div>
              {inviteSuccess && (
                <div className="mt-3 p-3 bg-green-500/20 border border-green-500/30 rounded-lg text-green-300 text-sm">
                  {inviteSuccess}
                </div>
              )}
              {inviteError && (
                <div className="mt-3 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-300 text-sm">
                  {inviteError}
                </div>
              )}
            </div>

            {/* Invites List */}
            {invites.length === 0 ? (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-12 text-center">
                <Mail className="text-slate-600 mx-auto mb-3" size={48} />
                <p className="text-slate-400">No invites sent yet</p>
                <p className="text-slate-500 text-sm mt-1">Send an invite above to start onboarding candidates</p>
              </div>
            ) : (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Candidate Email</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Invite Code</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Status</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Sent</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invites.map((inv) => (
                      <tr key={inv.id as string} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                        <td className="px-4 py-3 text-sm text-white">{inv.candidate_email as string}</td>
                        <td className="px-4 py-3">
                          <code className="text-xs bg-slate-700 text-blue-300 px-2 py-1 rounded">{inv.invite_code as string}</code>
                        </td>
                        <td className="px-4 py-3"><StatusBadge status={inv.status as string} /></td>
                        <td className="px-4 py-3 text-sm text-slate-400">{(inv.created_at as string)?.split("T")[0]}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => copyInviteLink(inv.invite_code as string)}
                              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                              title="Copy invite link"
                            >
                              <Copy size={14} /> {copiedCode === inv.invite_code ? "Copied!" : "Copy Link"}
                            </button>
                            {inv.status === "pending" && (
                              <button
                                onClick={() => revokeInvite(inv.id as string)}
                                className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1"
                                title="Revoke invite"
                              >
                                <Trash2 size={14} /> Revoke
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}


        {/* CQC Audit Tab */}
        {tab === "audit" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-white flex items-center gap-2"><FileText className="text-blue-400" size={22} /> CQC Audit Packs</h2>
              <div className="flex items-center gap-3">
                <button onClick={downloadAgencyAudit} disabled={downloadingAudit}
                  className="bg-green-600 hover:bg-green-700 disabled:bg-green-800 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
                  <Download size={16} /> {downloadingAudit ? "Generating..." : "Full Agency Audit"}
                </button>
                <button onClick={downloadBulkCandidateAudit} disabled={downloadingBulkAudit || selectedAuditCandidates.length === 0}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
                  <Download size={16} /> {downloadingBulkAudit ? "Generating..." : `Download Selected (${selectedAuditCandidates.length})`}
                </button>
              </div>
            </div>
            <p className="text-slate-400 text-sm">Select individual or multiple candidates to generate CQC audit packs. Use the checkboxes to select candidates, then download a combined audit PDF.</p>
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left px-4 py-3">
                      <input type="checkbox" checked={selectedAuditCandidates.length === candidatesWithStatus.length && candidatesWithStatus.length > 0}
                        onChange={toggleAllAuditCandidates} className="rounded border-slate-600 bg-slate-700" />
                    </th>
                    <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Name</th>
                    <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Profession</th>
                    <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Compliance</th>
                    <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Score</th>
                    <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {candidatesWithStatus.map((c) => {
                    const cId = String(c.id || c.candidate_id);
                    const isSelected = selectedAuditCandidates.includes(cId);
                    return (
                      <tr key={cId} className={`border-b border-slate-700/50 hover:bg-slate-700/30 ${isSelected ? "bg-blue-500/10" : ""}`}>
                        <td className="px-4 py-3">
                          <input type="checkbox" checked={isSelected} onChange={() => toggleAuditCandidate(cId)} className="rounded border-slate-600 bg-slate-700" />
                        </td>
                        <td className="px-4 py-3 text-sm text-white">{String(c.first_name)} {String(c.last_name)}</td>
                        <td className="px-4 py-3 text-sm text-slate-300">{String(c.profession || "N/A")}</td>
                        <td className="px-4 py-3"><StatusBadge status={String(c.compliance_status || "incomplete")} /></td>
                        <td className="px-4 py-3 text-sm font-medium text-white">{String(c.compliance_score || 0)}%</td>
                        <td className="px-4 py-3">
                          <button onClick={() => downloadCandidateAudit(cId)} disabled={downloadingSingleAudit === cId}
                            className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
                            <Download size={12} /> {downloadingSingleAudit === cId ? "Downloading..." : "Individual Audit"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  {candidatesWithStatus.length === 0 && (
                    <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500 text-sm">No candidates to audit</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Billing Tab */}
        {tab === "billing" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-white flex items-center gap-2"><CreditCard className="text-blue-400" size={22} /> Subscription & Billing</h2>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Billing Mode:</span>
                <span className={`text-xs px-3 py-1 rounded-full font-medium border ${
                  billingMode === "online_payment" ? "bg-green-500/20 text-green-400 border-green-500/30" :
                  billingMode === "subscription" ? "bg-blue-500/20 text-blue-400 border-blue-500/30" :
                  "bg-slate-500/20 text-slate-400 border-slate-500/30"
                }`}>
                  {billingMode === "online_payment" ? "Online Payment (PAYG)" :
                   billingMode === "subscription" ? "Subscription" : "Manual Invoicing"}
                </span>
              </div>
            </div>

            {/* Current Subscription */}
            {subscription && subscription.status !== "none" ? (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4">Current Subscription</h3>
                <div className="grid grid-cols-4 gap-4">
                  <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                    <p className="text-slate-400 text-xs mb-1">Plan</p>
                    <p className="text-xl font-bold text-white capitalize">{String(subscription.tier)}</p>
                  </div>
                  <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                    <p className="text-slate-400 text-xs mb-1">Monthly Amount</p>
                    <p className="text-xl font-bold text-green-400">£{Number(subscription.monthly_amount).toFixed(2)}</p>
                  </div>
                  <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                    <p className="text-slate-400 text-xs mb-1">Billing Method</p>
                    <p className="text-xl font-bold text-blue-400 capitalize">{String(subscription.billing_method)}</p>
                  </div>
                  <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                    <p className="text-slate-400 text-xs mb-1">Max Workers</p>
                    <p className="text-xl font-bold text-amber-400">{subscription.max_workers === -1 ? "Unlimited" : String(subscription.max_workers)}</p>
                  </div>
                </div>
                <div className="mt-4 flex items-center justify-between">
                  <p className="text-slate-400 text-sm">Next billing: {String(subscription.next_billing_date || "N/A")}</p>
                  <button onClick={cancelSubscription} className="text-xs bg-red-600/20 text-red-400 border border-red-600/30 px-4 py-2 rounded-full hover:bg-red-600/30">Cancel Subscription</button>
                </div>
              </div>
            ) : (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4">Choose a Plan</h3>
                <div className="grid grid-cols-4 gap-4 mb-6">
                  {[
                    { key: "starter", name: "Starter", price: "£299/mo", workers: "Up to 50 workers", color: "border-blue-500/30" },
                    { key: "growth", name: "Growth", price: "£799/mo", workers: "Up to 200 workers", color: "border-green-500/30" },
                    { key: "enterprise", name: "Enterprise", price: "£1,999/mo", workers: "Unlimited workers", color: "border-purple-500/30" },
                    { key: "per_worker", name: "Per Worker", price: "£5/worker/mo", workers: "Unlimited workers", color: "border-amber-500/30" },
                  ].map((tier) => (
                    <div key={tier.key} onClick={() => setSelectedTier(tier.key)}
                      className={`p-5 bg-slate-700/50 rounded-xl border cursor-pointer transition-all ${selectedTier === tier.key ? "border-blue-400 ring-2 ring-blue-400/30" : tier.color + " hover:border-slate-500"}`}>
                      <p className="text-white font-bold text-lg mb-1">{tier.name}</p>
                      <p className="text-blue-400 text-xl font-bold mb-2">{tier.price}</p>
                      <p className="text-slate-400 text-sm">{tier.workers}</p>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-4">
                  <select value={selectedBillingMethod} onChange={(e) => setSelectedBillingMethod(e.target.value)}
                    className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="stripe">Stripe (Card Payment)</option>
                    <option value="invoice">Recurring Invoice</option>
                  </select>
                  <button onClick={subscribeToPlan} disabled={subscribing}
                    className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-6 py-2.5 rounded-lg text-sm font-medium">
                    {subscribing ? "Subscribing..." : "Subscribe Now"}
                  </button>
                </div>
              </div>
            )}

            {/* Billing History */}
            {billingHistory.length > 0 && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4">Billing History</h3>
                <table className="w-full">
                  <thead><tr className="border-b border-slate-700">
                    {["Description", "Amount", "Status", "Date", "Actions"].map((h) => (
                      <th key={h} className="text-left text-xs text-slate-400 font-medium px-4 py-3">{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {billingHistory.map((item, i) => (
                      <tr key={i} className="border-b border-slate-700/50">
                        <td className="px-4 py-3 text-sm text-white">{String(item.description || item.tier || "Invoice")}</td>
                        <td className="px-4 py-3 text-sm text-green-400">£{Number(item.amount || item.sell_amount || item.monthly_amount || 0).toFixed(2)}</td>
                        <td className="px-4 py-3"><StatusBadge status={String(item.status || "pending")} /></td>
                        <td className="px-4 py-3 text-sm text-slate-400">{String(item.created_at || item.date || "").split("T")[0]}</td>
                        <td className="px-4 py-3">
                          {item.status === "pending" && item.id && billingMode !== "manual_invoicing" ? (
                            <button
                              onClick={() => handlePayInvoice(item.id as string)}
                              disabled={payingInvoice === item.id}
                              className="text-xs bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg font-medium flex items-center gap-1"
                            >
                              <CreditCard size={12} /> {payingInvoice === item.id ? "Processing..." : "Pay Now"}
                            </button>
                          ) : item.status === "pending" && item.id && billingMode === "manual_invoicing" ? (
                            <span className="text-xs text-slate-500">Awaiting Invoice</span>
                          ) : item.status === "paid" ? (
                            <span className="text-xs text-green-400">Paid</span>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Alerts Tab */}
        {tab === "alerts" && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <AlertTriangle className="text-amber-400" size={22} /> Active Alerts ({alerts.length})
            </h2>

            {alerts.length === 0 ? (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-12 text-center">
                <CheckCircle className="text-green-500 mx-auto mb-3" size={48} />
                <p className="text-slate-400">No active alerts</p>
              </div>
            ) : (
              <div className="space-y-2">
                {alerts.map((alert) => (
                  <div key={alert.id as string} className={`bg-slate-800/80 rounded-xl border p-4 ${
                    alert.severity === "critical" ? "border-red-500/30" :
                    alert.severity === "high" ? "border-orange-500/30" :
                    "border-yellow-500/30"}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <StatusBadge status={alert.severity as string} />
                        <span className="text-white text-sm">{alert.message as string}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-slate-500">{(alert.created_at as string)?.split("T")[0]}</span>
                        <button onClick={() => resolveAlert(alert.id as string)}
                          className="text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-3 py-1 rounded-full hover:bg-green-600/30">
                          Resolve
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Candidate Detail Tab */}
        {tab === "candidate-detail" && selectedCandidate && (
          <div className="space-y-6">
            <button onClick={() => setTab("candidates")} className="text-blue-400 hover:text-blue-300 text-sm">&larr; Back to Candidates</button>

            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-white">
                {selectedCandidate.first_name as string} {selectedCandidate.last_name as string}
              </h2>
              <div className="flex items-center gap-3">
                <StatusBadge status={selectedCandidate.compliance_status as string} />
                <StatusBadge status={(selectedCandidate.employment_status as string) || "vetting"} />
              </div>
            </div>

            {/* Candidate Info */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-3">Candidate Details</h3>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div><span className="text-slate-400">Email:</span> <span className="text-white">{selectedCandidate.email as string}</span></div>
                <div><span className="text-slate-400">Phone:</span> <span className="text-white">{(selectedCandidate.phone as string) || "N/A"}</span></div>
                <div><span className="text-slate-400">Profession:</span> <span className="text-white">{(selectedCandidate.profession as string) || "N/A"}</span></div>
                <div><span className="text-slate-400">Registration:</span> <span className="text-white">{selectedCandidate.registration_body as string} {selectedCandidate.registration_number as string}</span></div>
                <div><span className="text-slate-400">Score:</span> <span className="text-white font-bold">{selectedCandidate.compliance_score as number}%</span></div>
                <div><span className="text-slate-400">Joined:</span> <span className="text-white">{(selectedCandidate.created_at as string)?.split("T")[0]}</span></div>
              </div>
            </div>

            {/* Compliance Breakdown */}
            {candidateCompliance && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-3">Compliance Breakdown</h3>
                <div className="space-y-2">
                  {[
                    { label: "Identity Verification", key: "identity_verified" },
                    { label: "Enhanced DBS", key: "dbs_valid" },
                    { label: "Professional Registration", key: "registration_active" },
                    { label: "References (2+)", key: "references_verified" },
                    { label: "CV Validation", key: "cv_validated" },
                  ].map((item) => (
                    <div key={item.key} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <CheckIcon passed={candidateCompliance[item.key] as boolean} />
                        <span className="text-slate-200 text-sm">{item.label}</span>
                      </div>
                    </div>
                  ))}
                  {/* Right to Work - dual requirement: RTW check + Imposter Declaration */}
                  <div className="p-3 bg-slate-700/50 rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <CheckIcon passed={candidateCompliance.right_to_work_valid as boolean} />
                        <span className="text-slate-200 text-sm font-medium">Right to Work</span>
                      </div>
                      {candidateCompliance.right_to_work_valid
                        ? <span className="text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-2 py-0.5 rounded-full">Compliant</span>
                        : <span className="text-xs bg-amber-600/20 text-amber-400 border border-amber-600/30 px-2 py-0.5 rounded-full">Pending</span>
                      }
                    </div>
                    <div className="mt-2 ml-8 space-y-1 text-xs">
                      <div className="flex items-center gap-2">
                        {imposterDeclaration
                          ? <CheckCircle size={14} className="text-green-400" />
                          : <Clock size={14} className="text-amber-400" />
                        }
                        <span className={imposterDeclaration ? "text-green-300" : "text-amber-300"}>
                          Imposter Check Declaration: {imposterDeclaration ? "Confirmed" : "Pending"}
                        </span>
                      </div>
                      {imposterDeclaration && (
                        <div className="ml-5 text-slate-500">
                          Declared by {imposterDeclaration.declared_by_email as string} on {(imposterDeclaration.created_at as string)?.split("T")[0]}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                {candidateCompliance.flags ? (() => {
                  let flagList: string[] = [];
                  try {
                    const raw = candidateCompliance.flags;
                    if (Array.isArray(raw)) flagList = raw as string[];
                    else if (typeof raw === "string") flagList = JSON.parse(raw as string);
                  } catch { flagList = [String(candidateCompliance.flags)]; }
                  return flagList.length > 0 ? (
                    <div className="mt-4">
                      <p className="text-xs text-slate-400 mb-2">Flags:</p>
                      <ul className="space-y-1">
                        {flagList.map((f, i) => (
                          <li key={i} className="text-sm text-amber-300 flex items-start gap-2">
                            <span className="mt-1">•</span><span>{f}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null;
                })() : null}
                <div className="mt-3">
                  <span className={`text-sm font-medium ${candidateCompliance.cqc_ready ? "text-green-400" : "text-slate-400"}`}>
                    CQC Ready: {candidateCompliance.cqc_ready ? "Yes" : "No"}
                  </span>
                </div>
              </div>
            )}

            {/* Imposter Check Declaration Section */}
            {!imposterDeclaration && (
              <div className="bg-slate-800/80 rounded-xl border border-amber-600/40 p-6">
                <h3 className="text-md font-semibold text-white mb-2 flex items-center gap-2">
                  <Shield className="text-amber-400" size={18} /> Imposter Check Declaration Required
                </h3>
                <p className="text-slate-400 text-sm mb-4">
                  Before Right to Work can be marked as <span className="text-green-400 font-medium">Compliant</span>, you must confirm that an in-person or video imposter check has been conducted.
                </p>

                <div className="bg-slate-900/60 rounded-lg p-4 mb-4 border border-slate-700">
                  <p className="text-slate-300 text-sm mb-3 font-medium">Documents verified during imposter check:</p>
                  <div className="grid grid-cols-2 gap-2">
                    {["Passport", "BRP/BRC", "Driving Licence", "Birth Certificate", "Visa Document", "Other ID"].map(doc => (
                      <label key={doc} className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={imposterDocsVerified.includes(doc)}
                          onChange={() => toggleImposterDoc(doc)}
                          className="rounded border-slate-600 bg-slate-700 text-blue-500"
                        />
                        {doc}
                      </label>
                    ))}
                  </div>
                </div>

                <label className="flex items-start gap-3 p-4 bg-slate-900/60 rounded-lg border border-slate-700 cursor-pointer mb-4">
                  <input
                    type="checkbox"
                    checked={imposterDeclConfirmed}
                    onChange={(e) => setImposterDeclConfirmed(e.target.checked)}
                    className="mt-1 rounded border-slate-600 bg-slate-700 text-blue-500"
                  />
                  <span className="text-sm text-slate-200">
                    I confirm that I have conducted an in-person (or compliant video) imposter check and confirm the individual matches the documentation.
                  </span>
                </label>

                <button
                  onClick={submitImposterDeclaration}
                  disabled={!imposterDeclConfirmed || imposterDeclLoading}
                  className={`w-full py-2.5 rounded-lg text-sm font-medium transition-all ${
                    imposterDeclConfirmed
                      ? "bg-blue-600 hover:bg-blue-700 text-white"
                      : "bg-slate-700 text-slate-500 cursor-not-allowed"
                  }`}
                >
                  {imposterDeclLoading ? "Submitting..." : "Submit Imposter Check Declaration"}
                </button>

                {imposterDeclError && (
                  <p className="text-xs text-red-400 mt-2 text-center bg-red-900/20 border border-red-600/30 rounded p-2">
                    {imposterDeclError}
                  </p>
                )}

                <p className="text-xs text-slate-500 mt-2 text-center">
                  This declaration is non-editable once submitted. It will be timestamped and logged in the audit trail.
                </p>
              </div>
            )}

            {/* Imposter Declaration Confirmed */}
            {imposterDeclaration && (
              <div className="bg-slate-800/80 rounded-xl border border-green-600/30 p-6">
                <h3 className="text-md font-semibold text-white mb-2 flex items-center gap-2">
                  <CheckCircle className="text-green-400" size={18} /> Imposter Check Declaration Confirmed
                </h3>
                <div className="grid grid-cols-2 gap-3 text-sm mt-3">
                  <div><span className="text-slate-400">Declared by:</span> <span className="text-white">{imposterDeclaration.declared_by_email as string}</span></div>
                  <div><span className="text-slate-400">Date:</span> <span className="text-white">{(imposterDeclaration.created_at as string)?.replace("T", " ").split(".")[0]} UTC</span></div>
                  <div><span className="text-slate-400">IP Address:</span> <span className="text-white">{imposterDeclaration.ip_address as string}</span></div>
                  {imposterDeclaration.documents_verified ? (
                    <div><span className="text-slate-400">Documents:</span> <span className="text-white">{String((() => { try { return JSON.parse(imposterDeclaration.documents_verified as string).join(", "); } catch { return String(imposterDeclaration.documents_verified); } })())}</span></div>
                  ) : null}
                </div>
                <p className="text-xs text-slate-500 mt-3 italic">This declaration is immutable and cannot be edited.</p>
              </div>
            )}

            {/* Candidate Alerts */}
            {candidateAlerts.length > 0 && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-3 flex items-center gap-2">
                  <AlertTriangle className="text-amber-400" size={18} /> Alerts ({candidateAlerts.length})
                </h3>
                <div className="space-y-2">
                  {candidateAlerts.map((alert) => (
                    <div key={alert.id as string} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={alert.severity as string} />
                        <span className="text-slate-200 text-sm">{alert.message as string}</span>
                      </div>
                      <button onClick={() => resolveAlert(alert.id as string)}
                        className="text-xs text-green-400 hover:text-green-300">Resolve</button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Invite Cost Confirmation Modal */}
        {inviteCostModalOpen && invitePricing && (
          <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
            <div className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-md">
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    {remainingChecks && (remainingChecks.has_subscription as boolean)
                      ? <><CreditCard className="text-blue-400" size={20} /> Subscription Check</>
                      : <><DollarSign className="text-green-400" size={20} /> Confirm Vetting Cost</>}
                  </h3>
                  <button onClick={() => setInviteCostModalOpen(false)} className="text-slate-400 hover:text-white text-xl bg-transparent border-none cursor-pointer">&times;</button>
                </div>
                <p className="text-slate-300 text-sm mb-1">
                  Candidate: <span className="font-semibold text-white">{inviteEmail}</span>
                </p>

                {/* Subscription agency view — show remaining checks */}
                {remainingChecks && (remainingChecks.has_subscription as boolean) ? (
                  <div className="space-y-4 mt-4">
                    {/* Credit status */}
                    <div className="flex justify-between items-center p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                      <div>
                        <p className="text-white font-medium text-sm">Monthly Check Credit</p>
                        <p className="text-blue-300 text-xs mt-0.5">{remainingChecks.tier_name as string} Plan</p>
                      </div>
                      <div className="text-right">
                        <span className="text-blue-400 font-bold text-2xl">{(remainingChecks.checks_remaining as number) >= 999999 ? "\u221E" : remainingChecks.checks_remaining as number}</span>
                        <p className="text-blue-300 text-xs">remaining</p>
                      </div>
                    </div>

                    {/* Progress bar */}
                    {(remainingChecks.monthly_checks as number) < 999999 && (
                      <div>
                        <div className="flex justify-between text-xs text-slate-400 mb-1">
                          <span>{remainingChecks.checks_used as number} used</span>
                          <span>{remainingChecks.monthly_checks as number} total</span>
                        </div>
                        <div className="w-full bg-slate-700 rounded-full h-2.5">
                          <div className="h-2.5 rounded-full transition-all" style={{
                            width: `${Math.min(100, ((remainingChecks.checks_used as number) / (remainingChecks.monthly_checks as number)) * 100)}%`,
                            backgroundColor: (remainingChecks.checks_remaining as number) > 5 ? '#22c55e' : (remainingChecks.checks_remaining as number) > 0 ? '#f59e0b' : '#ef4444'
                          }} />
                        </div>
                      </div>
                    )}

                    {/* Within credit */}
                    {(remainingChecks.checks_remaining as number) > 0 ? (
                      <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                        <p className="text-green-300 font-medium text-sm flex items-center gap-2">
                          <CheckCircle size={16} /> This check is covered by your subscription
                        </p>
                        <p className="text-green-200/70 text-xs mt-1">Auto-billed against your monthly credit. No additional charge.</p>
                      </div>
                    ) : (
                      <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                        <p className="text-red-300 font-medium text-sm flex items-center gap-2">
                          <AlertTriangle size={16} /> Monthly credit exceeded
                        </p>
                        <p className="text-red-200/70 text-xs mt-1">This check will be invoiced separately at £{invitePricing.vetting_total.toFixed(2)}.</p>
                      </div>
                    )}

                    {/* Optional annual monitoring */}
                    <label className="flex items-center justify-between p-4 bg-slate-700/50 rounded-lg border border-slate-600 cursor-pointer hover:bg-slate-700/70 transition-colors">
                      <div className="flex items-center gap-3">
                        <input type="checkbox" checked={includeMonitoring} onChange={(e) => setIncludeMonitoring(e.target.checked)} className="w-5 h-5 rounded accent-blue-500" />
                        <div>
                          <p className="text-white font-medium text-sm">Annual Monitoring Service</p>
                          <p className="text-slate-400 text-xs mt-0.5">Continuous compliance monitoring for 12 months</p>
                        </div>
                      </div>
                      <span className="text-blue-400 font-bold text-lg">£{invitePricing.monitoring_annual_price.toFixed(2)}</span>
                    </label>

                    {/* Action buttons */}
                    <div className="flex gap-3">
                      <button onClick={() => setInviteCostModalOpen(false)} className="flex-1 bg-slate-600 hover:bg-slate-500 text-white rounded-lg py-2.5 text-sm font-medium border-none cursor-pointer">Cancel</button>
                      <button onClick={confirmAndSendInvite} disabled={inviteLoading}
                        className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:opacity-50 text-white rounded-lg py-2.5 text-sm font-medium flex items-center justify-center gap-2 border-none cursor-pointer">
                        <Send size={14} /> {inviteLoading ? "Sending..." : (remainingChecks.checks_remaining as number) > 0 ? "Use Credit & Send Invite" : "Accept & Send Invite"}
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Non-subscription agency view — show charge amount */
                  <div className="space-y-4 mt-4">
                    <p className="text-slate-400 text-xs mb-1">Please confirm the vetting cost before sending the invite.</p>

                    {/* Total vetting cost */}
                    <div className="flex justify-between items-center p-4 bg-slate-700/50 rounded-lg border border-slate-600">
                      <div>
                        <p className="text-white font-medium text-sm">Full Automated Vetting</p>
                        <p className="text-slate-400 text-xs mt-0.5">All compliance checks included</p>
                      </div>
                      <span className="text-green-400 font-bold text-xl">£{invitePricing.vetting_total.toFixed(2)}</span>
                    </div>

                    {/* Optional annual monitoring */}
                    <label className="flex items-center justify-between p-4 bg-slate-700/50 rounded-lg border border-slate-600 cursor-pointer hover:bg-slate-700/70 transition-colors">
                      <div className="flex items-center gap-3">
                        <input type="checkbox" checked={includeMonitoring} onChange={(e) => setIncludeMonitoring(e.target.checked)} className="w-5 h-5 rounded accent-blue-500" />
                        <div>
                          <p className="text-white font-medium text-sm">Annual Monitoring Service</p>
                          <p className="text-slate-400 text-xs mt-0.5">Continuous compliance monitoring for 12 months</p>
                        </div>
                      </div>
                      <span className="text-blue-400 font-bold text-lg">£{invitePricing.monitoring_annual_price.toFixed(2)}</span>
                    </label>

                    {/* Total */}
                    <div className="flex justify-between items-center p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                      <span className="text-green-300 font-semibold text-sm">Total Cost</span>
                      <span className="text-green-400 font-bold text-2xl">
                        £{(invitePricing.vetting_total + (includeMonitoring ? invitePricing.monitoring_annual_price : 0)).toFixed(2)}
                      </span>
                    </div>

                    {/* Action buttons */}
                    <div className="flex gap-3">
                      <button onClick={() => setInviteCostModalOpen(false)} className="flex-1 bg-slate-600 hover:bg-slate-500 text-white rounded-lg py-2.5 text-sm font-medium border-none cursor-pointer">Cancel</button>
                      <button onClick={confirmAndSendInvite} disabled={inviteLoading}
                        className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:opacity-50 text-white rounded-lg py-2.5 text-sm font-medium flex items-center justify-center gap-2 border-none cursor-pointer">
                        <Send size={14} /> {inviteLoading ? "Sending..." : "Accept & Send Invite"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Re-Vet Modal */}
        {revetModalOpen && revetCandidate && (
          <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
            <div className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-lg max-h-[90vh] overflow-y-auto">
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <RefreshCw className="text-amber-400" size={20} /> Request Re-Vet
                  </h3>
                  <button onClick={() => setRevetModalOpen(false)} className="text-slate-400 hover:text-white text-xl bg-transparent border-none cursor-pointer">&times;</button>
                </div>
                <p className="text-slate-300 text-sm mb-1">
                  Candidate: <span className="font-semibold text-white">{revetCandidate.first_name as string} {revetCandidate.last_name as string}</span>
                </p>
                <p className="text-slate-400 text-xs mb-4">Select the sections to re-vet. Each section will be billed separately.</p>

                {revetResult ? (
                  <div className="space-y-3">
                    <div className="p-4 bg-green-500/20 border border-green-500/30 rounded-lg">
                      <p className="text-green-300 font-semibold mb-1">Re-vet request submitted successfully</p>
                      <p className="text-green-200 text-sm">Token: <code className="bg-slate-700 px-2 py-0.5 rounded text-xs">{revetResult.token as string}</code></p>
                      <p className="text-green-200 text-sm mt-1">Link will be emailed to {revetResult.candidate_email as string}</p>
                      <p className="text-green-200 text-sm mt-1">Total cost: <span className="font-bold">£{(revetResult.total_cost as number)?.toFixed(2)}</span></p>
                    </div>
                    <div className="space-y-1">
                      {(revetResult.section_costs as {section: string; label: string; cost: number}[])?.map((sc) => (
                        <div key={sc.section} className="flex justify-between p-2 bg-slate-700/50 rounded text-sm">
                          <span className="text-slate-300">{sc.label}</span>
                          <span className="text-white font-medium">£{sc.cost.toFixed(2)}</span>
                        </div>
                      ))}
                    </div>
                    <button onClick={() => setRevetModalOpen(false)} className="w-full bg-slate-600 hover:bg-slate-500 text-white rounded-lg py-2 text-sm font-medium border-none cursor-pointer">
                      Close
                    </button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="space-y-2">
                      {REVET_SECTION_OPTIONS.map((opt) => (
                        <label key={opt.key} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg cursor-pointer hover:bg-slate-700/70 transition-colors">
                          <div className="flex items-center gap-3">
                            <input
                              type="checkbox"
                              checked={revetSections.includes(opt.key)}
                              onChange={() => toggleRevetSection(opt.key)}
                              className="w-4 h-4 rounded accent-amber-500"
                            />
                            <span className="text-slate-200 text-sm">{opt.label}</span>
                          </div>
                          <span className="text-amber-400 text-sm font-medium">£{opt.price.toFixed(2)}</span>
                        </label>
                      ))}
                    </div>

                    <div className="flex justify-between items-center p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                      <span className="text-amber-300 font-semibold text-sm">Estimated Total</span>
                      <span className="text-amber-400 font-bold text-lg">£{revetTotalCost.toFixed(2)}</span>
                    </div>

                    <button
                      onClick={submitRevetRequest}
                      disabled={revetSections.length === 0 || revetLoading}
                      className="w-full bg-amber-600 hover:bg-amber-700 disabled:bg-amber-800 disabled:opacity-50 text-white rounded-lg py-2.5 text-sm font-medium flex items-center justify-center gap-2 border-none cursor-pointer"
                    >
                      <RefreshCw size={14} /> {revetLoading ? "Submitting..." : `Submit Re-Vet Request (${revetSections.length} section${revetSections.length !== 1 ? "s" : ""})`}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
