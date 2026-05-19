import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import { candidatesApi, complianceApi, monitoringApi, dashboardApi, agencyInvitesApi, agencyServicesApi, billingApi, reportsApi, agencyRevetApi, checksApi, notificationsApi, bulkImportApi, shiftReadinessApi, subAccountsApi, trainingApi, gdprApi } from "../api/client";
import NotificationBell from "../components/NotificationBell";
import { fmtDate } from "../lib/utils";
import {
  Shield, CheckCircle, CheckCircle2, XCircle, Clock, AlertTriangle, Users,
  BarChart3, Bell, LogOut, RefreshCw, Eye, Mail, Send, Copy, Trash2,
  DollarSign, FileText, Briefcase, CreditCard, Download, Upload, UserPlus, Activity,
  Menu, X as XIcon, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Loader2,
} from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend, BarChart, Bar, XAxis, YAxis } from "recharts";

type Tab = "dashboard" | "candidates" | "alerts" | "candidate-detail" | "invites" | "billing" | "audit" | "bulk-import" | "sub-accounts" | "notifications";

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

  // Expandable compliance section state
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [sectionData, setSectionData] = useState<Record<string, Record<string, unknown>[]>>({});
  const [sectionLoading, setSectionLoading] = useState<Set<string>>(new Set());

  // Mobile nav state
  const [agencyMobileMenuOpen, setAgencyMobileMenuOpen] = useState(false);
  const agencyNavScrollRef = useRef<HTMLDivElement>(null);
  const [agencyCanScrollLeft, setAgencyCanScrollLeft] = useState(false);
  const [agencyCanScrollRight, setAgencyCanScrollRight] = useState(false);

  const checkAgencyNavScroll = useCallback(() => {
    const el = agencyNavScrollRef.current;
    if (!el) return;
    setAgencyCanScrollLeft(el.scrollLeft > 4);
    setAgencyCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  useEffect(() => {
    const el = agencyNavScrollRef.current;
    if (!el) return;
    checkAgencyNavScroll();
    el.addEventListener("scroll", checkAgencyNavScroll, { passive: true });
    const ro = new ResizeObserver(checkAgencyNavScroll);
    ro.observe(el);
    return () => { el.removeEventListener("scroll", checkAgencyNavScroll); ro.disconnect(); };
  }, [checkAgencyNavScroll]);

  const scrollAgencyNav = (dir: "left" | "right") => {
    const el = agencyNavScrollRef.current;
    if (!el) return;
    el.scrollBy({ left: dir === "left" ? -200 : 200, behavior: "smooth" });
  };
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
  const [, setSubscription] = useState<Record<string, unknown> | null>(null);
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
  const [includeMonitoring] = useState(true);
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
  const [revetPricing, setRevetPricing] = useState<{ key: string; label: string; price: number }[]>([]);
  const [revetBillingMode, setRevetBillingMode] = useState("");
  const [revetCreditInfo, setRevetCreditInfo] = useState<Record<string, unknown> | null>(null);

  // Bulk Import state
  const [bulkCsvText, setBulkCsvText] = useState("");
  const [bulkSendInvites, setBulkSendInvites] = useState(true);
  const [bulkImporting, setBulkImporting] = useState(false);
  const [bulkResult, setBulkResult] = useState<Record<string, unknown> | null>(null);
  const [bulkError, setBulkError] = useState("");

  // Sub-Accounts state
  const [subAccounts, setSubAccounts] = useState<Record<string, unknown>[]>([]);
  const [newSubAccount, setNewSubAccount] = useState({ email: "", password: "", first_name: "", last_name: "", role: "recruiter", industry_template_id: "" });
  const [creatingSubAccount, setCreatingSubAccount] = useState(false);
  const [subAccountError, setSubAccountError] = useState("");
  const [subAccountSuccess, setSubAccountSuccess] = useState("");
  const [availableTemplates, setAvailableTemplates] = useState<Record<string, unknown>[]>([]);

  // Notifications state
  const [notifications, setNotifications] = useState<Record<string, unknown>[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifCategoryFilter, setNotifCategoryFilter] = useState("all");
  const [seedingNotifs, setSeedingNotifs] = useState(false);

  // Shift Readiness state
  const [shiftOverview, setShiftOverview] = useState<Record<string, unknown> | null>(null);

  // Monitoring renewal state
  const [renewingMonitoring, setRenewingMonitoring] = useState<string | null>(null);

  // Credit pack tiers from DB
  const [creditPackTiers, setCreditPackTiers] = useState<Record<string, unknown>[]>([]);

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
      // Load notifications unread count
      try {
        const nc = await notificationsApi.getUnreadCount(token);
        setUnreadCount(nc.unread_count);
      } catch { /* ignore */ }
      // Load shift readiness overview
      try {
        const sr = await shiftReadinessApi.getAgencyOverview(token);
        setShiftOverview(sr);
      } catch { /* ignore */ }
      // Load credit pack tier config from DB
      try {
        const tiers = await billingApi.getTiers(token);
        const tiersArr = (tiers as Record<string, unknown>).tiers as Record<string, unknown>[] || [];
        if (tiersArr.length > 0) setCreditPackTiers(tiersArr);
      } catch { /* ignore */ }
    } catch (err) {
      console.error("Failed to load data", err);
    }
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);

  const viewCandidate = async (candidate: Record<string, unknown>) => {
    setSelectedCandidate(candidate);
    setTab("candidate-detail");
    setExpandedSections(new Set());
    setSectionData({});
    setSectionLoading(new Set());
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

  const toggleComplianceSection = async (sectionKey: string) => {
    const next = new Set(expandedSections);
    if (next.has(sectionKey)) {
      next.delete(sectionKey);
      setExpandedSections(next);
      return;
    }
    next.add(sectionKey);
    setExpandedSections(next);

    if (sectionData[sectionKey] || !token || !selectedCandidate) return;

    const loading = new Set(sectionLoading);
    loading.add(sectionKey);
    setSectionLoading(loading);

    const cid = selectedCandidate.id as string;
    try {
      let data: Record<string, unknown>[] = [];
      switch (sectionKey) {
        case "identity_verified":
          data = await checksApi.getIdentityChecks(token, cid).catch(() => []);
          break;
        case "dbs_valid":
          data = await checksApi.getDBSChecks(token, cid).catch(() => []);
          break;
        case "registration_active":
          data = await checksApi.getRegistrationChecks(token, cid).catch(() => []);
          break;
        case "references_verified":
          data = await checksApi.getReferences(token, cid).catch(() => []);
          break;
        case "cv_validated":
          data = await checksApi.getCVAnalyses(token, cid).catch(() => []);
          break;
        case "employment_verified": {
          const [history, verifications] = await Promise.all([
            checksApi.getEmploymentHistory(token, cid).catch(() => []),
            checksApi.getEmploymentVerifications(token, cid).catch(() => []),
          ]);
          data = history.map((entry: Record<string, unknown>) => ({
            ...entry,
            _verification: verifications.find((v: Record<string, unknown>) => v.employment_id === entry.id),
          }));
          break;
        }
        case "training_compliant":
          data = await trainingApi.getCertificates(token, cid).catch(() => []);
          break;
        case "right_to_work_valid":
          data = await checksApi.getRightToWorkChecks(token, cid).catch(() => []);
          break;
      }
      setSectionData(prev => ({ ...prev, [sectionKey]: data }));
    } catch { /* ignore */ }
    setSectionLoading(prev => {
      const s = new Set(prev);
      s.delete(sectionKey);
      return s;
    });
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

  const openRevetModal = async (candidate: Record<string, unknown>) => {
    setRevetCandidate(candidate);
    setRevetSections([]);
    setRevetResult(null);
    setRevetModalOpen(true);
    // Fetch industry-specific pricing
    if (token) {
      try {
        const pricing = await agencyRevetApi.getRevetPricing(token);
        const sections = pricing.sections as { key: string; label: string; price: number }[] || [];
        setRevetPricing(sections);
        setRevetBillingMode((pricing.billing_mode as string) || "");
        setRevetCreditInfo((pricing.credit_info as Record<string, unknown>) || null);
      } catch { /* fallback to empty */ }
    }
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

  const renewMonitoring = async (candidateId: string) => {
    if (!token) return;
    setRenewingMonitoring(candidateId);
    try {
      const result = await monitoringApi.renewMonitoring(token, candidateId);
      const payment = result.payment as Record<string, unknown> | undefined;
      if (payment?.status === "paid_by_subscription") {
        alert(`Monitoring renewed! Credits remaining: ${payment.credits_remaining}`);
      } else if (payment?.payment_required) {
        alert(`Monitoring renewal invoice created (£${(result.sell_price as number)?.toFixed(2)}). Check Billing History to pay.`);
      } else {
        alert(`Monitoring renewed successfully. Expires: ${fmtDate(result.monitoring_expires_at, { dateOnly: true })}`);
      }
      await loadData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to renew monitoring");
    } finally {
      setRenewingMonitoring(null);
    }
  };

  const openInviteCostModal = async () => {
    if (!token || !inviteEmail.trim()) return;
    setInvitePricingLoading(true);
    setInviteError("");
    try {
      const pricing = await agencyInvitesApi.getVettingPricing(token);
      setInvitePricing(pricing);
      // Monitoring is always included (first year free with full vetting)
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

  const [resendingInvite, setResendingInvite] = useState<string | null>(null);
  const resendInvite = async (inviteId: string) => {
    if (!token) return;
    setResendingInvite(inviteId);
    try {
      await agencyInvitesApi.resendInvite(token, inviteId);
      setInviteSuccess("Invite email resent successfully");
      setTimeout(() => setInviteSuccess(""), 3000);
    } catch (err) {
      console.error("Failed to resend invite", err);
      setInviteError(err instanceof Error ? err.message : "Failed to resend invite");
    } finally {
      setResendingInvite(null);
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
    } catch (err) { console.error("Failed to purchase credit pack", err); }
    finally { setSubscribing(false); }
  };

  const topupCredits = async (tier: string) => {
    if (!token) return;
    setSubscribing(true);
    try {
      await billingApi.topup(token, { agency_id: "me", tier });
      loadData();
    } catch (err) { console.error("Failed to top up credits", err); }
    finally { setSubscribing(false); }
  };

  const toggleAutoTopup = async (enabled: boolean, tier?: string) => {
    if (!token) return;
    try {
      await billingApi.updateAutoTopup(token, { agency_id: "me", enabled, tier });
      loadData();
    } catch (err) { console.error("Failed to update auto top-up", err); }
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
      if (!resp.ok) { const e = await resp.json().catch(() => null); throw new Error(e?.detail || "Failed to generate audit"); }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "agency_audit_pack.pdf"; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { alert(err instanceof Error ? err.message : "Download failed"); }
    finally { setDownloadingAudit(false); }
  };

  const downloadCandidateAudit = async (candidateId: string) => {
    if (!token) return;
    setDownloadingSingleAudit(candidateId);
    try {
      const resp = await reportsApi.downloadCandidateAudit(token, candidateId);
      if (!resp.ok) { const e = await resp.json().catch(() => null); throw new Error(e?.detail || "Failed to generate audit"); }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = `candidate_audit_${candidateId}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { alert(err instanceof Error ? err.message : "Download failed"); }
    finally { setDownloadingSingleAudit(""); }
  };

  const downloadBulkCandidateAudit = async () => {
    if (!token || selectedAuditCandidates.length === 0) return;
    setDownloadingBulkAudit(true);
    try {
      const resp = await reportsApi.downloadBulkCandidateAudit(token, selectedAuditCandidates);
      if (!resp.ok) { const e = await resp.json().catch(() => null); throw new Error(e?.detail || "Failed to generate audit"); }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "bulk_candidate_audit.pdf"; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { alert(err instanceof Error ? err.message : "Download failed"); }
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
      cancelled: "bg-slate-500/20 text-slate-400 border-slate-500/30 line-through",
      refunded: "bg-slate-500/20 text-slate-400 border-slate-500/30",
      pending_admin_approval: "bg-amber-500/20 text-amber-400 border-amber-500/30",
      paid: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
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

  // Use dynamically fetched pricing from the industry matrix, with fallback defaults
  const REVET_SECTION_OPTIONS = revetPricing.length > 0 ? revetPricing : [
    { key: "identity", label: "Identity Verification", price: 15.00 },
    { key: "rtw", label: "Right to Work", price: 10.00 },
    { key: "dbs", label: "DBS Check", price: 25.00 },
    { key: "cv", label: "CV Analysis", price: 8.00 },
    { key: "registration", label: "Professional Registration", price: 12.00 },
    { key: "references", label: "References", price: 10.00 },
    { key: "training", label: "Training Certificates", price: 8.00 },
    { key: "monitoring", label: "12 Month Continuous Monitoring", price: 50.00 },
  ];

  const revetTotalCost = revetSections.reduce((sum, sec) => {
    const opt = REVET_SECTION_OPTIONS.find(o => o.key === sec);
    return sum + (opt?.price || 0);
  }, 0);

  // ── Bulk Import Handlers ──
  const handleBulkImport = async () => {
    if (!token || !bulkCsvText.trim()) return;
    setBulkImporting(true);
    setBulkError("");
    setBulkResult(null);
    try {
      const result = await bulkImportApi.importCandidates(token, bulkCsvText, bulkSendInvites);
      setBulkResult(result);
      setBulkCsvText("");
      await loadData();
    } catch (err) {
      setBulkError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBulkImporting(false);
    }
  };

  const handleCsvFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => { setBulkCsvText(ev.target?.result as string || ""); };
    reader.readAsText(file);
  };

  // ── Sub-Account Handlers ──
  const loadSubAccounts = async () => {
    if (!token) return;
    try { const sa = await subAccountsApi.list(token); setSubAccounts(sa); } catch { /* ignore */ }
  };

  const loadAvailableTemplates = async () => {
    if (!token) return;
    try { const tpls = await subAccountsApi.listTemplates(token); setAvailableTemplates(tpls); } catch { /* ignore */ }
  };

  const createSubAccount = async () => {
    if (!token) return;
    setCreatingSubAccount(true);
    setSubAccountError("");
    setSubAccountSuccess("");
    try {
      await subAccountsApi.create(token, newSubAccount.industry_template_id ? newSubAccount : { ...newSubAccount, industry_template_id: undefined });
      setSubAccountSuccess(`Sub-account created for ${newSubAccount.email}`);
      setNewSubAccount({ email: "", password: "", first_name: "", last_name: "", role: "recruiter", industry_template_id: "" });
      await loadSubAccounts();
    } catch (err) {
      setSubAccountError(err instanceof Error ? err.message : "Failed to create sub-account");
    } finally {
      setCreatingSubAccount(false);
    }
  };

  const deleteSubAccount = async (accountId: string) => {
    if (!token) return;
    try { await subAccountsApi.remove(token, accountId); await loadSubAccounts(); } catch { /* ignore */ }
  };

  const updateSubAccountRole = async (accountId: string, role: string) => {
    if (!token) return;
    try { await subAccountsApi.update(token, accountId, { role }); await loadSubAccounts(); } catch { /* ignore */ }
  };

  const updateSubAccountTemplate = async (accountId: string, templateId: string) => {
    if (!token) return;
    try { await subAccountsApi.update(token, accountId, { industry_template_id: templateId || "" }); await loadSubAccounts(); } catch { /* ignore */ }
  };

  // ── Notification Handlers ──
  const loadNotifications = async () => {
    if (!token) return;
    try {
      const params: { category?: string } = {};
      if (notifCategoryFilter !== "all") params.category = notifCategoryFilter;
      const result = await notificationsApi.getNotifications(token, params);
      setNotifications(result.notifications || []);
      setUnreadCount(result.unread_count || 0);
    } catch { /* ignore */ }
  };

  const markNotificationRead = async (notifId: string) => {
    if (!token) return;
    try { await notificationsApi.markRead(token, notifId); await loadNotifications(); } catch { /* ignore */ }
  };

  const markAllNotificationsRead = async () => {
    if (!token) return;
    try { await notificationsApi.markAllRead(token); await loadNotifications(); } catch { /* ignore */ }
  };

  const deleteNotification = async (notifId: string) => {
    if (!token) return;
    try { await notificationsApi.deleteNotification(token, notifId); await loadNotifications(); } catch { /* ignore */ }
  };

  const seedNotifications = async () => {
    if (!token) return;
    setSeedingNotifs(true);
    try { await notificationsApi.seedNotifications(token); await loadNotifications(); } catch { /* ignore */ }
    finally { setSeedingNotifs(false); }
  };

  // Load data for specific tabs
  useEffect(() => { if (tab === "sub-accounts") { loadSubAccounts(); loadAvailableTemplates(); } }, [tab]);
  useEffect(() => { if (tab === "notifications") loadNotifications(); }, [tab, notifCategoryFilter]);

  // Auto-refresh notifications every 30 seconds when on the notifications tab
  useEffect(() => {
    if (tab !== "notifications") return;
    const interval = setInterval(() => { loadNotifications(); }, 30000);
    return () => clearInterval(interval);
  }, [tab, notifCategoryFilter]);

  // Poll unread notification count every 60 seconds (all tabs)
  useEffect(() => {
    if (!token) return;
    const interval = setInterval(async () => {
      try {
        const nc = await notificationsApi.getUnreadCount(token);
        setUnreadCount(nc.unread_count);
      } catch { /* ignore */ }
    }, 60000);
    return () => clearInterval(interval);
  }, [token]);

  // Shift readiness badge helper
  const getShiftBadge = (candidate: Record<string, unknown>) => {
    const rag = getRagStatus(candidate);
    const status = String(candidate.compliance_status || "incomplete");
    const score = Number(candidate.compliance_score || 0);
    // READY: compliant status OR GREEN RAG with high score
    if ((status === "compliant" && score >= 80) || (rag.label === "GREEN" && score >= 90)) return { label: "READY", color: "bg-green-500/20 text-green-400 border-green-500/30" };
    // CONDITIONAL: GREEN or AMBER RAG (reasonable compliance but not fully ready)
    if (rag.label === "GREEN" || rag.label === "AMBER") return { label: "CONDITIONAL", color: "bg-amber-500/20 text-amber-400 border-amber-500/30" };
    // NOT READY: RED RAG or very low compliance
    return { label: "NOT READY", color: "bg-red-500/20 text-red-400 border-red-500/30" };
  };

  const filteredCandidates = candidatesWithStatus.filter((c) => {
    const empStatus = (c.employment_status as string) || "vetting";
    const passesStatus = statusFilter === "all" || empStatus === statusFilter;
    const rag = getRagStatus(c);
    const passesRag = ragFilter === "all" || rag.label === ragFilter;
    return passesStatus && passesRag;
  });

  return (
    <div className="min-h-screen bg-slate-900">
      <header className="bg-slate-800/80 border-b border-slate-700 px-4 sm:px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <img src="/viper-logo.png" alt="Viper AI" className="h-8 sm:h-12" />
          <h1 className="text-lg sm:text-xl font-bold text-white truncate">Viper AI</h1>
          <span className="hidden sm:inline text-xs bg-emerald-600/30 text-emerald-300 px-2 py-0.5 rounded-full">Agency Dashboard</span>
        </div>
        <div className="flex items-center gap-2 sm:gap-4 shrink-0">
          <button onClick={loadData} className="text-slate-400 hover:text-white"><RefreshCw size={18} /></button>
          {token && <span className="text-slate-300"><NotificationBell token={token} /></span>}
          <button onClick={logout} className="text-slate-400 hover:text-red-400 flex items-center gap-1 text-sm">
            <LogOut size={16} /> <span className="hidden sm:inline">Sign Out</span>
          </button>
        </div>
      </header>

      {/* Navigation Tabs — responsive */}
      {(() => {
        const agencyNavItems = [
          { key: "dashboard" as Tab, label: "Dashboard", icon: <BarChart3 size={16} /> },
          { key: "candidates" as Tab, label: "Candidates", icon: <Users size={16} /> },
          { key: "invites" as Tab, label: `Invites (${invites.length})`, icon: <Mail size={16} /> },
          { key: "bulk-import" as Tab, label: "Bulk Import", icon: <Upload size={16} /> },
          { key: "sub-accounts" as Tab, label: "Team", icon: <UserPlus size={16} /> },
          { key: "notifications" as Tab, label: `Notifications${unreadCount > 0 ? ` (${unreadCount})` : ""}`, icon: <Activity size={16} /> },
          { key: "alerts" as Tab, label: `Alerts (${alerts.length})`, icon: <Bell size={16} /> },
          { key: "audit" as Tab, label: "CQC Audit", icon: <FileText size={16} /> },
          { key: "billing" as Tab, label: "Billing", icon: <CreditCard size={16} /> },
        ];
        const activeAgencyItem = agencyNavItems.find(i => i.key === tab);
        return (
          <div className="bg-slate-800/50 border-b border-slate-700">
            {/* Mobile: current tab + hamburger */}
            <div className="flex md:hidden items-center justify-between px-4 py-2">
              <button onClick={() => setAgencyMobileMenuOpen(!agencyMobileMenuOpen)}
                className="flex items-center gap-2 text-sm font-medium text-blue-400">
                {activeAgencyItem?.icon} {activeAgencyItem?.label}
              </button>
              <button onClick={() => setAgencyMobileMenuOpen(!agencyMobileMenuOpen)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/50 transition-colors">
                {agencyMobileMenuOpen ? <XIcon size={20} /> : <Menu size={20} />}
              </button>
            </div>
            {/* Mobile dropdown */}
            {agencyMobileMenuOpen && (
              <div className="md:hidden border-t border-slate-700/50 bg-slate-800/90 backdrop-blur-sm max-h-80 overflow-y-auto">
                {agencyNavItems.map((item) => (
                  <button key={item.key} onClick={() => { setTab(item.key); setAgencyMobileMenuOpen(false); }}
                    className={`flex items-center gap-3 w-full px-5 py-3 text-sm font-medium transition-colors ${tab === item.key ? "text-blue-400 bg-blue-500/10" : "text-slate-400 hover:text-white hover:bg-slate-700/30"}`}>
                    {item.icon} {item.label}
                  </button>
                ))}
              </div>
            )}
            {/* Desktop: scrollable tabs with arrow indicators */}
            <div className="hidden md:flex items-center relative px-4 sm:px-6">
              {agencyCanScrollLeft && (
                <button onClick={() => scrollAgencyNav("left")}
                  className="absolute left-0 z-10 h-full px-1 bg-gradient-to-r from-slate-800 via-slate-800/90 to-transparent text-slate-400 hover:text-white">
                  <ChevronLeft size={18} />
                </button>
              )}
              <div ref={agencyNavScrollRef} className="flex gap-1 overflow-x-auto scrollbar-hide">
                {agencyNavItems.map((item) => (
                  <button key={item.key} onClick={() => setTab(item.key)}
                    className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-all whitespace-nowrap ${
                      tab === item.key ? "text-blue-400 border-blue-400" : "text-slate-400 border-transparent hover:text-white"
                    }`}>
                    {item.icon} {item.label}
                  </button>
                ))}
              </div>
              {agencyCanScrollRight && (
                <button onClick={() => scrollAgencyNav("right")}
                  className="absolute right-0 z-10 h-full px-1 bg-gradient-to-l from-slate-800 via-slate-800/90 to-transparent text-slate-400 hover:text-white">
                  <ChevronRight size={18} />
                </button>
              )}
            </div>
          </div>
        );
      })()}

      <main className="p-4 sm:p-6">
        {/* Dashboard Tab */}
        {tab === "dashboard" && stats && (
          <div className="space-y-6">
            {/* Risk Flags Panel */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-5">
              <h3 className="text-md font-semibold text-white mb-3 flex items-center gap-2"><AlertTriangle className="text-amber-400" size={18} /> Candidate Risk Overview</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
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
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
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
            <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-5">
                <p className="text-slate-400 text-xs mb-1">Compliance Rate</p>
                <p className="text-3xl font-bold text-green-400">{Number(stats.compliance_rate ?? 0).toFixed(1)}%</p>
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
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
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
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-x-auto">
                <table className="w-full min-w-[700px]">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Name</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Profession</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Registration</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Score</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">RAG</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Shift Ready</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Compliance</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Employment Status</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Monitoring</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCandidates.map((c) => {
                      const cId = (c.id as string) || (c.candidate_id as string);
                      const empStatus = (c.employment_status as string) || "vetting";
                      const monActive = c.monitoring_active as number;
                      const monExpiry = c.monitoring_expires_at as string | null;
                      const monDaysLeft = monExpiry ? Math.ceil((new Date(monExpiry).getTime() - Date.now()) / 86400000) : null;
                      return (
                        <tr key={cId} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                          <td className="px-4 py-3 text-sm text-white">{c.first_name as string} {c.last_name as string}</td>
                          <td className="px-4 py-3 text-sm text-slate-300">{(c.profession as string) || "N/A"}</td>
                          <td className="px-4 py-3 text-sm text-slate-300">{(c.registration_body as string) || "N/A"} {(c.registration_number as string) || ""}</td>
                                                    <td className="px-4 py-3 text-sm font-medium text-white">{Number(c.compliance_score ?? 0).toFixed(1)}%</td>
                                                    <td className="px-4 py-3"><RagBadge candidate={c} /></td>
                          <td className="px-4 py-3"><span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-bold border ${getShiftBadge(c).color}`}>{getShiftBadge(c).label}</span></td>
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
                            {monActive ? (
                              <div className="text-xs">
                                {monDaysLeft !== null && monDaysLeft <= 30 ? (
                                  <span className="text-amber-400 flex items-center gap-1">
                                    <Clock size={12} /> {monDaysLeft}d left
                                  </span>
                                ) : (
                                  <span className="text-green-400 flex items-center gap-1">
                                    <Shield size={12} /> Active
                                  </span>
                                )}
                                {monExpiry && <p className="text-slate-500 text-[10px] mt-0.5">Exp: {fmtDate(monExpiry, { dateOnly: true })}</p>}
                              </div>
                            ) : monExpiry ? (
                              <div className="text-xs">
                                <span className="text-red-400 flex items-center gap-1 mb-1">
                                  <XCircle size={12} /> Expired
                                </span>
                                <button
                                  onClick={() => renewMonitoring(cId)}
                                  disabled={renewingMonitoring === cId}
                                  className="text-[10px] bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded px-2 py-0.5 border-none cursor-pointer"
                                >
                                  {renewingMonitoring === cId ? "..." : "Renew"}
                                </button>
                              </div>
                            ) : (
                              <span className="text-slate-500 text-xs">N/A</span>
                            )}
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
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-x-auto">
                <div className="px-6 py-4 border-b border-slate-700">
                  <h3 className="text-md font-semibold text-white flex items-center gap-2">
                    <RefreshCw className="text-amber-400" size={18} /> Re-Vet Requests ({revetRequests.length})
                  </h3>
                </div>
                <table className="w-full min-w-[600px]">
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
                        <td className="px-4 py-3 text-sm text-slate-400">{fmtDate(rr.created_at)}</td>
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
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-x-auto">
                <table className="w-full min-w-[600px]">
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
                        <td className="px-4 py-3 text-sm text-slate-400">{fmtDate(inv.created_at)}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => copyInviteLink(inv.invite_code as string)}
                              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                              title="Copy invite link"
                            >
                              <Copy size={14} /> {copiedCode === inv.invite_code ? "Copied!" : "Copy Link"}
                            </button>
                            {(inv.status === "pending" || inv.status === "sent") && (
                              <button
                                onClick={() => resendInvite(inv.id as string)}
                                disabled={resendingInvite === inv.id}
                                className="text-xs text-green-400 hover:text-green-300 flex items-center gap-1 disabled:opacity-50"
                                title="Resend invite email"
                              >
                                <Send size={14} /> {resendingInvite === inv.id ? "Sending..." : "Resend"}
                              </button>
                            )}
                            {inv.status !== "revoked" && inv.status !== "accepted" && (
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
            {/* Data Processing Agreement */}
            <DPAAcceptancePanel />

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
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-x-auto">
              <table className="w-full min-w-[700px]">
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
                        <td className="px-4 py-3 text-sm font-medium text-white">{Number(c.compliance_score || 0).toFixed(1)}%</td>
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
              <h2 className="text-xl font-bold text-white flex items-center gap-2"><CreditCard className="text-blue-400" size={22} /> Credit Packs & Billing</h2>
              <span className={`text-xs px-3 py-1 rounded-full font-medium border ${
                billingMode === "manual_invoicing" ? "bg-slate-500/20 text-slate-400 border-slate-500/30" :
                billingMode === "online_payment" ? "bg-green-500/20 text-green-400 border-green-500/30" :
                "bg-blue-500/20 text-blue-400 border-blue-500/30"
              }`}>{
                billingMode === "manual_invoicing" ? "Manual Invoicing" :
                billingMode === "online_payment" ? "Pay-As-You-Go" :
                billingMode === "subscription" || billingMode === "credit_pack" ? "12-Month Credit Pack Model" :
                billingMode.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())
              }</span>
            </div>

            {/* Active Credit Pack */}
            {remainingChecks && (remainingChecks.has_credit_pack as boolean) ? (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-md font-semibold text-white">Active Credit Pack</h3>
                  <span className="text-xs px-3 py-1 rounded-full bg-green-500/20 text-green-400 border border-green-500/30">{remainingChecks.pack_name as string || remainingChecks.tier_name as string}</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-4">
                  <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                    <p className="text-slate-400 text-xs mb-1">Credits Remaining</p>
                    <p className="text-2xl font-bold text-green-400">{typeof remainingChecks.credits_remaining === "number" ? (remainingChecks.credits_remaining as number).toFixed(1) : "0"}</p>
                  </div>
                  <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                    <p className="text-slate-400 text-xs mb-1">Credits Used</p>
                    <p className="text-2xl font-bold text-amber-400">{typeof remainingChecks.credits_used === "number" ? (remainingChecks.credits_used as number).toFixed(1) : "0"}</p>
                  </div>
                  <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                    <p className="text-slate-400 text-xs mb-1">Total Credits</p>
                    <p className="text-2xl font-bold text-blue-400">{typeof remainingChecks.credits_total === "number" ? (remainingChecks.credits_total as number).toFixed(1) : "0"}</p>
                  </div>
                  <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                    <p className="text-slate-400 text-xs mb-1">Expires</p>
                    <p className="text-lg font-bold text-white">{remainingChecks.expires_at ? fmtDate(remainingChecks.expires_at, { dateOnly: true }) : "N/A"}</p>
                  </div>
                  <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                    <p className="text-slate-400 text-xs mb-1">Days Left</p>
                    <p className={`text-2xl font-bold ${(remainingChecks.days_remaining as number) <= 30 ? "text-red-400" : (remainingChecks.days_remaining as number) <= 90 ? "text-amber-400" : "text-green-400"}`}>{remainingChecks.days_remaining as number}</p>
                  </div>
                </div>

                {/* Credit usage progress bar */}
                {typeof remainingChecks.credits_total === "number" && (remainingChecks.credits_total as number) > 0 && (
                  <div className="mb-4">
                    <div className="flex justify-between text-xs text-slate-400 mb-1">
                      <span>{typeof remainingChecks.credits_used === "number" ? (remainingChecks.credits_used as number).toFixed(1) : 0} used of {(remainingChecks.credits_total as number).toFixed(1)} total</span>
                      <span>{typeof remainingChecks.credits_remaining === "number" ? (remainingChecks.credits_remaining as number).toFixed(1) : 0} remaining</span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-2.5">
                      <div className="bg-blue-500 h-2.5 rounded-full transition-all"
                        style={{ width: `${Math.min(100, ((typeof remainingChecks.credits_used === "number" ? remainingChecks.credits_used as number : 0) / (remainingChecks.credits_total as number)) * 100)}%` }} />
                    </div>
                  </div>
                )}

                {/* Low credits warning */}
                {typeof remainingChecks.credits_remaining === "number" && (remainingChecks.credits_remaining as number) <= 5 && (
                  <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg mb-4">
                    <p className="text-amber-400 text-sm font-medium">Credits running low! Top up to avoid service interruption.</p>
                  </div>
                )}

                {/* Auto Top-Up Toggle */}
                <div className="flex items-center justify-between p-4 bg-slate-700/30 rounded-lg">
                  <div>
                    <p className="text-white text-sm font-medium">Auto Top-Up</p>
                    <p className="text-slate-400 text-xs">Automatically purchase a new credit pack when your credits expire</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {(remainingChecks.auto_topup as boolean) && (
                      <select
                        value={String(remainingChecks.auto_topup_tier || remainingChecks.tier || "starter")}
                        onChange={(e) => toggleAutoTopup(true, e.target.value)}
                        className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <option value="starter">Starter (5 credits)</option>
                        <option value="growth">Growth (10 credits)</option>
                        <option value="enterprise">Professional (20 credits)</option>
                        <option value="per_worker">Enterprise (50 credits)</option>
                      </select>
                    )}
                    <button
                      onClick={() => toggleAutoTopup(!remainingChecks.auto_topup)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        remainingChecks.auto_topup ? "bg-blue-600" : "bg-slate-600"
                      }`}>
                      <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        remainingChecks.auto_topup ? "translate-x-6" : "translate-x-1"
                      }`} />
                    </button>
                  </div>
                </div>

                {/* Top-Up & Cancel buttons */}
                <div className="mt-4 flex items-center gap-3">
                  <button onClick={() => setSelectedTier(String(remainingChecks.tier || "starter"))}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium"
                    data-action="show-topup"
                  >Top Up Credits</button>
                  <button onClick={cancelSubscription}
                    className="text-xs bg-red-600/20 text-red-400 border border-red-600/30 px-4 py-2 rounded-full hover:bg-red-600/30">Cancel Pack</button>
                </div>
              </div>
            ) : null}

            {/* Purchase / Top-Up Credit Pack */}
            {(!remainingChecks || !(remainingChecks.has_credit_pack as boolean) || tab === "billing") && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-2">{remainingChecks && (remainingChecks.has_credit_pack as boolean) ? "Top Up Credits" : "Purchase a Credit Pack"}</h3>
                <p className="text-slate-400 text-sm mb-4">Credits are valid for 12 months from purchase. Unused credits from your current pack carry over.</p>
                <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                  {(creditPackTiers.length > 0 ? creditPackTiers.map((t) => {
                    const credits = Number(t.credits_included || 0);
                    const price = Number(t.monthly_price || 0);
                    const perCredit = credits > 0 ? (price / credits).toFixed(2) : "0.00";
                    const colorMap: Record<string, string> = { starter: "border-blue-500/30", standard: "border-green-500/30", professional: "border-purple-500/30", enterprise: "border-amber-500/30" };
                    return { key: String(t.tier_key), name: String(t.name), credits, price, perCredit, saving: "", color: colorMap[String(t.tier_key)] || "border-slate-500/30" };
                  }) : [
                    { key: "starter", name: "Starter Pack", credits: 25, price: 125, perCredit: "5.00", saving: "", color: "border-blue-500/30" },
                    { key: "standard", name: "Standard Pack", credits: 50, price: 225, perCredit: "4.50", saving: "10% saving", color: "border-green-500/30" },
                    { key: "professional", name: "Professional Pack", credits: 100, price: 400, perCredit: "4.00", saving: "20% saving", color: "border-purple-500/30" },
                    { key: "enterprise", name: "Enterprise Pack", credits: 250, price: 875, perCredit: "3.50", saving: "30% saving", color: "border-amber-500/30" },
                  ]).map((pack) => (
                    <div key={pack.key} onClick={() => setSelectedTier(pack.key)}
                      className={`p-5 bg-slate-700/50 rounded-xl border cursor-pointer transition-all ${selectedTier === pack.key ? "border-blue-400 ring-2 ring-blue-400/30" : pack.color + " hover:border-slate-500"}`}>
                      <p className="text-white font-bold text-lg mb-1">{pack.name}</p>
                      <p className="text-blue-400 text-2xl font-bold mb-1">£{Number(pack.price).toFixed(2)}</p>
                      <p className="text-slate-300 text-sm mb-1">{pack.credits} credits</p>
                      <p className="text-slate-400 text-xs">£{pack.perCredit} per credit</p>
                      {pack.saving && <p className="text-green-400 text-xs mt-1 font-medium">{pack.saving}</p>}
                      <p className="text-slate-500 text-xs mt-1">Valid for 12 months</p>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-4">
                  <select value={selectedBillingMethod} onChange={(e) => setSelectedBillingMethod(e.target.value)}
                    className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="stripe">Card Payment</option>
                    <option value="invoice">Invoice</option>
                  </select>
                  <button onClick={remainingChecks && (remainingChecks.has_credit_pack as boolean) ? () => topupCredits(selectedTier) : subscribeToPlan} disabled={subscribing}
                    className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-6 py-2.5 rounded-lg text-sm font-medium">
                    {subscribing ? "Processing..." : remainingChecks && (remainingChecks.has_credit_pack as boolean) ? "Top Up Now" : "Purchase Credit Pack"}
                  </button>
                </div>
              </div>
            )}

            {/* Billing History */}
            {billingHistory.length > 0 && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4">Billing History</h3>
                <div className="overflow-x-auto"><table className="w-full min-w-[600px]">
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
                        <td className="px-4 py-3 text-sm text-slate-400">{fmtDate(item.created_at || item.date)}</td>
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
                </table></div>
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
                        <span className="text-xs text-slate-500">{fmtDate(alert.created_at)}</span>
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
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
                <div><span className="text-slate-400">Email:</span> <span className="text-white">{selectedCandidate.email as string}</span></div>
                <div><span className="text-slate-400">Phone:</span> <span className="text-white">{(selectedCandidate.phone as string) || "N/A"}</span></div>
                <div><span className="text-slate-400">Profession:</span> <span className="text-white">{(selectedCandidate.profession as string) || "N/A"}</span></div>
                <div><span className="text-slate-400">Registration:</span> <span className="text-white">{selectedCandidate.registration_body as string} {selectedCandidate.registration_number as string}</span></div>
                <div><span className="text-slate-400">Score:</span> <span className="text-white font-bold">{Number(selectedCandidate.compliance_score ?? 0).toFixed(1)}%</span></div>
                <div><span className="text-slate-400">Joined:</span> <span className="text-white">{fmtDate(selectedCandidate.created_at)}</span></div>
              </div>
            </div>

            {/* Compliance Breakdown — Expandable Sections */}
            {candidateCompliance && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-3">Compliance Breakdown</h3>
                <p className="text-xs text-slate-500 mb-3">Click any section to view detailed check information</p>
                <div className="space-y-2">
                  {[
                    { label: "Identity Verification", key: "identity_verified" },
                    { label: "Enhanced DBS", key: "dbs_valid" },
                    { label: "Professional Registration", key: "registration_active" },
                    { label: "References (2+)", key: "references_verified" },
                    { label: "CV Validation", key: "cv_validated" },
                    { label: "Employment Verification", key: "employment_verified" },
                    { label: "Mandatory Training", key: "training_compliant" },
                  ].map((item) => {
                    const isExpanded = expandedSections.has(item.key);
                    const isLoading = sectionLoading.has(item.key);
                    const data = sectionData[item.key];
                    return (
                      <div key={item.key} className="bg-slate-700/50 rounded-lg overflow-hidden">
                        <button
                          onClick={() => toggleComplianceSection(item.key)}
                          className="w-full flex items-center justify-between p-3 hover:bg-slate-700/70 transition-colors cursor-pointer"
                        >
                          <div className="flex items-center gap-3">
                            <CheckIcon passed={candidateCompliance[item.key] as boolean} />
                            <span className="text-slate-200 text-sm">{item.label}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            {isLoading && <Loader2 size={14} className="text-blue-400 animate-spin" />}
                            {isExpanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                          </div>
                        </button>
                        {isExpanded && (
                          <div className="px-3 pb-3 border-t border-slate-600/50">
                            {isLoading && !data && (
                              <div className="py-4 text-center text-slate-500 text-sm">Loading details...</div>
                            )}
                            {data && data.length === 0 && (
                              <div className="py-3 text-slate-500 text-sm">No records found</div>
                            )}

                            {/* Identity Verification Details */}
                            {item.key === "identity_verified" && data && data.length > 0 && data.map((check) => {
                              let details: Record<string, unknown> = {};
                              try { details = JSON.parse(check.details as string || "{}"); } catch { /* ignore */ }
                              const reports = details.reports as Record<string, Record<string, unknown>> | undefined;
                              return (
                                <div key={check.id as string} className="mt-3 p-3 bg-slate-800/60 rounded-lg">
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                      <StatusBadge status={check.result as string} />
                                      {typeof check.document_type === "string" && check.document_type && (
                                        <span className="text-xs bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded-full border border-blue-500/30">
                                          {(details.document_type_label as string) || (check.document_type as string).replace(/_/g, " ")}
                                        </span>
                                      )}
                                    </div>
                                    <span className="text-xs text-slate-500">{fmtDate(check.started_at)}</span>
                                  </div>
                                  <div className="grid grid-cols-2 gap-2 text-sm">
                                    <div><span className="text-slate-400">Document:</span> <span className="text-white">{check.document_authenticity as string || "N/A"}</span></div>
                                    <div><span className="text-slate-400">Facial Match:</span> <span className="text-white">{check.facial_match_score != null ? `${((check.facial_match_score as number) * 100).toFixed(0)}%` : "N/A"}</span></div>
                                    <div><span className="text-slate-400">Liveness:</span> <span className="text-white">{check.liveness_check as string || "N/A"}</span></div>
                                    <div><span className="text-slate-400">Address:</span> <span className="text-white">{check.address_verified ? "Verified" : "Not Verified"}</span></div>
                                  </div>
                                  {reports && (
                                    <div className="mt-2 pt-2 border-t border-slate-600/30 grid grid-cols-3 gap-2 text-xs">
                                      {reports.document && (
                                        <div className="bg-slate-700/50 rounded p-2">
                                          <span className="text-slate-400 block mb-1">Document</span>
                                          <span className={`font-medium ${(reports.document as Record<string, unknown>).mrz_check === "clear" ? "text-green-400" : "text-amber-400"}`}>
                                            MRZ: {(reports.document as Record<string, unknown>).mrz_check as string}
                                          </span>
                                        </div>
                                      )}
                                      {reports.facial_similarity && (
                                        <div className="bg-slate-700/50 rounded p-2">
                                          <span className="text-slate-400 block mb-1">Facial</span>
                                          <span className={`font-medium ${(reports.facial_similarity as Record<string, unknown>).face_match_result === "clear" ? "text-green-400" : "text-amber-400"}`}>
                                            {(reports.facial_similarity as Record<string, unknown>).face_match_result as string}
                                          </span>
                                        </div>
                                      )}
                                      {reports.liveness && (
                                        <div className="bg-slate-700/50 rounded p-2">
                                          <span className="text-slate-400 block mb-1">Liveness</span>
                                          <span className={`font-medium ${(reports.liveness as Record<string, unknown>).liveness_result === "clear" ? "text-green-400" : "text-amber-400"}`}>
                                            {(reports.liveness as Record<string, unknown>).liveness_result as string}
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              );
                            })}

                            {/* DBS Check Details */}
                            {item.key === "dbs_valid" && data && data.length > 0 && data.map((check) => (
                              <div key={check.id as string} className="mt-3 p-3 bg-slate-800/60 rounded-lg">
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center gap-2">
                                    <StatusBadge status={check.result as string} />
                                    {check.dbs_mode === "candidate_supplied" && (
                                      <span className="text-xs bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded-full border border-blue-500/30">Candidate Supplied</span>
                                    )}
                                  </div>
                                  <span className="text-xs text-slate-500">{fmtDate(check.submitted_at)}</span>
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-sm">
                                  <div><span className="text-slate-400">Certificate:</span> <span className="text-white">{(check.certificate_number as string) || "Pending"}</span></div>
                                  <div><span className="text-slate-400">Ref:</span> <span className="text-white">{(check.application_ref as string) || (check.dbs_mode === "candidate_supplied" ? "Candidate Supplied" : "N/A")}</span></div>
                                  <div><span className="text-slate-400">Type:</span> <span className="text-white">{check.check_type as string}</span></div>
                                  <div><span className="text-slate-400">Renewal:</span> <span className="text-white">{fmtDate(check.next_renewal, { dateOnly: true }) || "N/A"}</span></div>
                                  {check.dbs_mode === "candidate_supplied" && (
                                    <>
                                      <div><span className="text-slate-400">Validation:</span> <span className={`font-medium ${check.validation_status === "validated" ? "text-green-400" : check.validation_status === "review_required" ? "text-amber-400" : "text-slate-400"}`}>{String(check.validation_status || "pending").replace(/_/g, " ")}</span></div>
                                      <div><span className="text-slate-400">Issue Date:</span> <span className="text-white">{fmtDate(check.candidate_issue_date, { dateOnly: true }) || "N/A"}</span></div>
                                    </>
                                  )}
                                </div>
                                {check.dbs_mode === "candidate_supplied" && (
                                  <div className="mt-2 pt-2 border-t border-slate-700/50">
                                    <span className="text-xs text-green-400 flex items-center gap-1">
                                      <CheckCircle2 size={12} /> Consent/Authority Recorded — {fmtDate(check.submitted_at)}
                                    </span>
                                  </div>
                                )}
                              </div>
                            ))}

                            {/* Registration Check Details */}
                            {item.key === "registration_active" && data && data.length > 0 && data.map((check) => (
                              <div key={check.id as string} className="mt-3 p-3 bg-slate-800/60 rounded-lg">
                                <div className="flex items-center justify-between mb-2">
                                  <StatusBadge status={check.result as string} />
                                  <span className="text-xs text-slate-500">{fmtDate(check.last_checked)}</span>
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-sm">
                                  <div><span className="text-slate-400">Body:</span> <span className="text-white">{check.body as string}</span></div>
                                  <div><span className="text-slate-400">Active:</span> <span className="text-white">{check.is_active ? "Yes" : "No"}</span></div>
                                  <div><span className="text-slate-400">Sanctions:</span> <span className="text-white">{(check.sanctions as string) || "None"}</span></div>
                                  <div><span className="text-slate-400">Next Check:</span> <span className="text-white">{fmtDate(check.next_check, { dateOnly: true }) || "N/A"}</span></div>
                                </div>
                              </div>
                            ))}

                            {/* References Details */}
                            {item.key === "references_verified" && data && data.length > 0 && data.map((ref) => (
                              <div key={ref.id as string} className="mt-3 p-3 bg-slate-800/60 rounded-lg">
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-white text-sm font-medium">{ref.referee_name as string}</span>
                                  <StatusBadge status={ref.status as string} />
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-sm">
                                  <div><span className="text-slate-400">Email:</span> <span className="text-slate-300">{ref.referee_email as string}</span></div>
                                  <div><span className="text-slate-400">Domain Verified:</span> <span className={ref.domain_verified ? "text-green-400" : "text-red-400"}>{ref.domain_verified ? "Yes" : "No"}</span></div>
                                  <div><span className="text-slate-400">Reminders Sent:</span> <span className="text-slate-300">{String(ref.reminder_count ?? 0)}</span></div>
                                  {ref.sentiment_score != null && (
                                    <div><span className="text-slate-400">Sentiment:</span> <span className={`font-medium ${(ref.sentiment_score as number) > 0.7 ? "text-green-400" : (ref.sentiment_score as number) > 0.4 ? "text-amber-400" : "text-red-400"}`}>{((ref.sentiment_score as number) * 100).toFixed(0)}%</span></div>
                                  )}
                                </div>
                              </div>
                            ))}

                            {/* CV Analysis Details */}
                            {item.key === "cv_validated" && data && data.length > 0 && data.map((analysis) => {
                              let gapDisplay = analysis.gap_analysis as string;
                              let qualDisplay = analysis.qualification_flags as string;
                              try {
                                const gapParsed = typeof gapDisplay === "string" ? JSON.parse(gapDisplay) : gapDisplay;
                                if (Array.isArray(gapParsed)) {
                                  gapDisplay = gapParsed.length === 0 ? "No gaps detected" : gapParsed.map((g: Record<string, unknown>) =>
                                    `${g.from_year || "?"}-${g.to_year || "?"}: ${g.gap_months || "?"}mo gap${g.note ? ` (${g.note})` : ""}`
                                  ).join("; ");
                                }
                              } catch { /* keep as-is */ }
                              try {
                                const qualParsed = typeof qualDisplay === "string" ? JSON.parse(qualDisplay) : qualDisplay;
                                if (Array.isArray(qualParsed)) {
                                  qualDisplay = qualParsed.map((q: Record<string, unknown>) =>
                                    `${q.qualification || q.note || "Unknown"} (${q.status || q.severity || "unknown"})`
                                  ).join("; ");
                                }
                              } catch { /* keep as-is */ }
                              return (
                                <div key={analysis.id as string} className="mt-3 p-3 bg-slate-800/60 rounded-lg">
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                      <span className="text-slate-300 text-sm">Fraud Risk:</span>
                                      <span className={`text-sm font-bold ${
                                        (analysis.fraud_risk_score as number) < 0.3 ? "text-green-400" :
                                        (analysis.fraud_risk_score as number) < 0.6 ? "text-amber-400" : "text-red-400"
                                      }`}>{((analysis.fraud_risk_score as number) * 100).toFixed(0)}%</span>
                                    </div>
                                    <span className="text-xs text-slate-500">{fmtDate(analysis.analysed_at)}</span>
                                  </div>
                                  {typeof analysis.ai_summary === "string" && analysis.ai_summary && <p className="text-slate-300 text-sm mb-2">{analysis.ai_summary}</p>}
                                  <div className="space-y-1 text-sm">
                                    <div className="p-2 bg-slate-700/50 rounded"><span className="text-slate-400">Gaps:</span> <span className="text-slate-200">{gapDisplay || "None"}</span></div>
                                    <div className="p-2 bg-slate-700/50 rounded"><span className="text-slate-400">Qualifications:</span> <span className="text-slate-200">{qualDisplay || "None"}</span></div>
                                  </div>
                                </div>
                              );
                            })}

                            {/* Employment Verification Details */}
                            {item.key === "employment_verified" && data && data.length > 0 && data.map((entry) => {
                              const ver = entry._verification as Record<string, unknown> | undefined;
                              return (
                                <div key={entry.id as string} className="mt-3 p-3 bg-slate-800/60 rounded-lg">
                                  <div className="flex items-start justify-between mb-1">
                                    <div>
                                      <h4 className="text-white font-medium text-sm">{entry.employer_name as string}</h4>
                                      <p className="text-blue-400 text-sm">{entry.job_title as string}</p>
                                      <p className="text-slate-400 text-xs">
                                        {entry.start_date as string || "?"} — {entry.is_current ? "Present" : (entry.end_date as string || "?")}
                                        {entry.source === "cv_extracted" && (
                                          <span className="ml-2 bg-purple-500/20 text-purple-400 border border-purple-500/30 px-1.5 py-0 rounded text-xs">CV Extracted</span>
                                        )}
                                      </p>
                                    </div>
                                    {ver && <StatusBadge status={ver.status as string} />}
                                  </div>
                                  {ver && (
                                    <div className="mt-2 pt-2 border-t border-slate-600/30">
                                      <div className="flex items-center gap-2 mb-1 text-sm">
                                        <span className="text-slate-400">Verified by:</span>
                                        <span className="text-white">{ver.verifier_name as string}</span>
                                        {ver.domain_verified
                                          ? <span className="text-xs bg-green-500/20 text-green-400 border border-green-500/30 px-1.5 py-0 rounded">Domain OK</span>
                                          : <span className="text-xs bg-red-500/20 text-red-400 border border-red-500/30 px-1.5 py-0 rounded">Domain Mismatch</span>
                                        }
                                      </div>
                                      <div className="grid grid-cols-2 gap-1 text-xs">
                                        <div><span className="text-slate-400">Job Title:</span> <span className={ver.job_title_confirmed ? "text-green-400" : "text-red-400"}>{ver.job_title_confirmed ? "Confirmed" : "Not confirmed"}</span></div>
                                        <div><span className="text-slate-400">Dates:</span> <span className={ver.dates_confirmed ? "text-green-400" : "text-red-400"}>{ver.dates_confirmed ? "Confirmed" : "Not confirmed"}</span></div>
                                      </div>
                                    </div>
                                  )}
                                  {!ver && <p className="text-slate-500 text-xs mt-1">Verification not yet completed</p>}
                                </div>
                              );
                            })}

                            {/* Training Certificate Details */}
                            {item.key === "training_compliant" && data && data.length > 0 && data.map((cert) => (
                              <div key={cert.id as string} className="mt-3 p-3 bg-slate-800/60 rounded-lg">
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-white text-sm font-medium">{cert.certificate_name as string}</span>
                                  <StatusBadge status={cert.status as string || "pending"} />
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-sm">
                                  <div><span className="text-slate-400">Category:</span> <span className="text-slate-300">{(cert.category as string) || "N/A"}</span></div>
                                  <div><span className="text-slate-400">Provider:</span> <span className="text-slate-300">{(cert.provider as string) || "N/A"}</span></div>
                                  <div><span className="text-slate-400">Issued:</span> <span className="text-slate-300">{(cert.issue_date as string) || "N/A"}</span></div>
                                  <div><span className="text-slate-400">Expires:</span> <span className={cert.expiry_date ? "text-slate-300" : "text-slate-500"}>{(cert.expiry_date as string) || "No expiry"}</span></div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {/* Right to Work - dual requirement: RTW check + Imposter Declaration */}
                  {(() => {
                    const rtwKey = "right_to_work_valid";
                    const isRtwExpanded = expandedSections.has(rtwKey);
                    const isRtwLoading = sectionLoading.has(rtwKey);
                    const rtwData = sectionData[rtwKey];
                    return (
                      <div className="bg-slate-700/50 rounded-lg overflow-hidden">
                        <button
                          onClick={() => toggleComplianceSection(rtwKey)}
                          className="w-full p-3 hover:bg-slate-700/70 transition-colors cursor-pointer"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <CheckIcon passed={candidateCompliance.right_to_work_valid as boolean} />
                              <span className="text-slate-200 text-sm font-medium">Right to Work</span>
                            </div>
                            <div className="flex items-center gap-2">
                              {candidateCompliance.right_to_work_valid
                                ? <span className="text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-2 py-0.5 rounded-full">Compliant</span>
                                : <span className="text-xs bg-amber-600/20 text-amber-400 border border-amber-600/30 px-2 py-0.5 rounded-full">Pending</span>
                              }
                              {isRtwLoading && <Loader2 size={14} className="text-blue-400 animate-spin" />}
                              {isRtwExpanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                            </div>
                          </div>
                          <div className="mt-2 ml-8 space-y-1 text-xs text-left">
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
                                Declared by {imposterDeclaration.declared_by_email as string} on {fmtDate(imposterDeclaration.created_at)}
                              </div>
                            )}
                          </div>
                        </button>
                        {isRtwExpanded && (
                          <div className="px-3 pb-3 border-t border-slate-600/50">
                            {isRtwLoading && !rtwData && (
                              <div className="py-4 text-center text-slate-500 text-sm">Loading details...</div>
                            )}
                            {rtwData && rtwData.length === 0 && (
                              <div className="py-3 text-slate-500 text-sm">No right to work checks found</div>
                            )}
                            {rtwData && rtwData.length > 0 && rtwData.map((check) => (
                              <div key={check.id as string} className="mt-3 p-3 bg-slate-800/60 rounded-lg">
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
                                  <span className="text-xs text-slate-500">{fmtDate(check.checked_at)}</span>
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-sm">
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
                    );
                  })()}
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
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
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
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm mt-3">
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

                    {/* First year monitoring included */}
                    <div className="flex items-center justify-between p-4 bg-slate-700/30 rounded-lg border border-slate-600/50">
                      <div className="flex items-center gap-3">
                        <CheckCircle className="text-green-400" size={18} />
                        <div>
                          <p className="text-white font-medium text-sm">12 Months Continuous Monitoring</p>
                          <p className="text-slate-400 text-xs mt-0.5">Included with full vetting — no extra charge</p>
                        </div>
                      </div>
                      <span className="text-green-400 font-semibold text-sm">Included</span>
                    </div>

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

                    {/* First year monitoring included */}
                    <div className="flex items-center justify-between p-4 bg-slate-700/30 rounded-lg border border-slate-600/50">
                      <div className="flex items-center gap-3">
                        <CheckCircle className="text-green-400" size={18} />
                        <div>
                          <p className="text-white font-medium text-sm">12 Months Continuous Monitoring</p>
                          <p className="text-slate-400 text-xs mt-0.5">Included with full vetting — no extra charge</p>
                        </div>
                      </div>
                      <span className="text-green-400 font-semibold text-sm">Included</span>
                    </div>

                    {/* Total */}
                    <div className="flex justify-between items-center p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                      <span className="text-green-300 font-semibold text-sm">Total Cost</span>
                      <span className="text-green-400 font-bold text-2xl">
                        £{invitePricing.vetting_total.toFixed(2)}
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
                <p className="text-slate-400 text-xs mb-4">Select the sections to re-vet. Each section will be billed via your payment method.</p>

                {revetResult ? (
                  <div className="space-y-3">
                    <div className="p-4 bg-green-500/20 border border-green-500/30 rounded-lg">
                      <p className="text-green-300 font-semibold mb-1">Re-vet request submitted successfully</p>
                      <p className="text-green-200 text-sm mt-1">Total cost: <span className="font-bold">£{(revetResult.total_cost as number)?.toFixed(2)}</span></p>
                      {(() => {
                        const payment = revetResult.payment as Record<string, unknown> | undefined;
                        if (!payment) return null;
                        if (payment.status === "paid_by_subscription") return (
                          <p className="text-green-200 text-sm mt-1">Deducted from credit balance. Credits remaining: <span className="font-bold">{String(payment.credits_remaining)}</span></p>
                        );
                        if (payment.status === "awaiting_payment") return (
                          <p className="text-green-200 text-sm mt-1">Invoice created (£{(payment.amount as number)?.toFixed(2)}). Go to Billing to pay.</p>
                        );
                        if (payment.status === "invoice_created") return (
                          <p className="text-green-200 text-sm mt-1">Manual invoice created for £{(payment.amount as number)?.toFixed(2)}.</p>
                        );
                        return null;
                      })()}
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

                    {/* Billing method notification */}
                    <div className="p-3 bg-slate-700/40 border border-slate-600/50 rounded-lg text-xs">
                      {revetBillingMode === "subscription" || revetBillingMode === "credit_pack" ? (
                        <div>
                          <p className="text-blue-300 font-medium flex items-center gap-1"><CreditCard size={12} /> Will be deducted from your credit balance</p>
                          {revetCreditInfo && (
                            <p className="text-slate-400 mt-1">Current balance: <span className="text-white font-semibold">{String(revetCreditInfo.remaining_checks ?? revetCreditInfo.credits_remaining ?? 0)} credits</span></p>
                          )}
                        </div>
                      ) : revetBillingMode === "online_payment" ? (
                        <p className="text-green-300 font-medium flex items-center gap-1"><CreditCard size={12} /> An invoice will be created for online payment</p>
                      ) : (
                        <p className="text-slate-300 font-medium flex items-center gap-1"><FileText size={12} /> A manual invoice will be raised</p>
                      )}
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

        {/* ── Bulk Import Tab ── */}
        {tab === "bulk-import" && (
          <div className="space-y-6">
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-lg font-semibold text-white mb-2 flex items-center gap-2"><Upload className="text-blue-400" size={20} /> Bulk Candidate Import</h3>
              <p className="text-slate-400 text-sm mb-4">Upload a CSV file or paste CSV data to import multiple candidates at once. Required columns: <span className="text-blue-300">email, first_name, last_name</span>. Optional: <span className="text-slate-300">phone, profession</span>.</p>

              <div className="mb-4">
                <label className="block text-sm font-medium text-slate-300 mb-2">Upload CSV File</label>
                <input type="file" accept=".csv" onChange={handleCsvFileUpload} className="block w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-600 file:text-white hover:file:bg-blue-700 file:cursor-pointer" />
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-slate-300 mb-2">Or Paste CSV Data</label>
                <textarea value={bulkCsvText} onChange={(e) => setBulkCsvText(e.target.value)} rows={8} placeholder={"email,first_name,last_name,phone,profession\njohn@example.com,John,Doe,07700900001,Nurse\njane@example.com,Jane,Smith,07700900002,Healthcare Assistant"} className="w-full bg-slate-700/50 border border-slate-600 rounded-lg p-3 text-slate-200 text-sm font-mono placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>

              <label className="flex items-center gap-2 mb-4 cursor-pointer">
                <input type="checkbox" checked={bulkSendInvites} onChange={(e) => setBulkSendInvites(e.target.checked)} className="w-4 h-4 rounded accent-blue-500" />
                <span className="text-sm text-slate-300">Send invite emails to imported candidates</span>
              </label>

              {bulkError && <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">{bulkError}</div>}

              {bulkResult && (
                <div className="mb-4 p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                  <div className="text-green-400 font-semibold text-sm mb-2">Import Complete</div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                    <div className="text-center"><div className="text-2xl font-bold text-green-400">{String(bulkResult.created || 0)}</div><div className="text-slate-400">Created</div></div>
                    <div className="text-center"><div className="text-2xl font-bold text-amber-400">{String(bulkResult.skipped || 0)}</div><div className="text-slate-400">Skipped</div></div>
                    <div className="text-center"><div className="text-2xl font-bold text-red-400">{String(bulkResult.errors_count || 0)}</div><div className="text-slate-400">Errors</div></div>
                  </div>
                  {(() => {
                    const errs = bulkResult.errors as Array<{row: number; error: string}> | undefined;
                    if (!errs || !Array.isArray(errs) || errs.length === 0) return null;
                    return (
                      <div className="mt-3 space-y-1">
                        {errs.map((err, i) => (
                          <div key={i} className="text-xs text-red-300">Row {err.row}: {err.error}</div>
                        ))}
                      </div>
                    );
                  })()}
                </div>
              )}

              <button onClick={handleBulkImport} disabled={bulkImporting || !bulkCsvText.trim()} className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:opacity-50 text-white rounded-lg px-6 py-2.5 text-sm font-medium flex items-center gap-2 border-none cursor-pointer">
                <Upload size={16} /> {bulkImporting ? "Importing..." : "Import Candidates"}
              </button>
            </div>

            {/* Shift Readiness Overview */}
            {shiftOverview && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2"><Shield className="text-emerald-400" size={20} /> Shift Readiness Overview</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-center">
                    <div className="text-3xl font-bold text-green-400">{String((shiftOverview.summary as Record<string, unknown>)?.ready || 0)}</div>
                    <div className="text-xs text-green-300 mt-1 font-bold">READY TO WORK</div>
                  </div>
                  <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg text-center">
                    <div className="text-3xl font-bold text-amber-400">{String((shiftOverview.summary as Record<string, unknown>)?.conditional || 0)}</div>
                    <div className="text-xs text-amber-300 mt-1 font-bold">CONDITIONAL</div>
                  </div>
                  <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-center">
                    <div className="text-3xl font-bold text-red-400">{String((shiftOverview.summary as Record<string, unknown>)?.not_ready || 0)}</div>
                    <div className="text-xs text-red-300 mt-1 font-bold">NOT READY</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Sub-Accounts Tab ── */}
        {tab === "sub-accounts" && (
          <div className="space-y-6">
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2"><UserPlus className="text-purple-400" size={20} /> Team Sub-Accounts</h3>
              <p className="text-slate-400 text-sm mb-4">Create sub-accounts for your team with role-based access. Roles: <span className="text-purple-300">Owner</span> (full access), <span className="text-blue-300">Manager</span> (manage candidates &amp; view reports), <span className="text-emerald-300">Compliance Officer</span> (view compliance &amp; reports), <span className="text-amber-300">Recruiter</span> (view &amp; invite candidates).</p>

              {subAccountError && <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">{subAccountError}</div>}
              {subAccountSuccess && <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">{subAccountSuccess}</div>}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                <input type="text" placeholder="First Name" value={newSubAccount.first_name} onChange={(e) => setNewSubAccount({ ...newSubAccount, first_name: e.target.value })} className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500" />
                <input type="text" placeholder="Last Name" value={newSubAccount.last_name} onChange={(e) => setNewSubAccount({ ...newSubAccount, last_name: e.target.value })} className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500" />
                <input type="email" placeholder="Email" value={newSubAccount.email} onChange={(e) => setNewSubAccount({ ...newSubAccount, email: e.target.value })} className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500" />
                <input type="password" placeholder="Password" value={newSubAccount.password} onChange={(e) => setNewSubAccount({ ...newSubAccount, password: e.target.value })} className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500" />
              </div>
              <div className="flex items-center gap-3 mb-4 flex-wrap">
                <select value={newSubAccount.role} onChange={(e) => setNewSubAccount({ ...newSubAccount, role: e.target.value })} className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500">
                  <option value="recruiter">Recruiter</option>
                  <option value="compliance_officer">Compliance Officer</option>
                  <option value="manager">Manager</option>
                  <option value="owner">Owner</option>
                </select>
                <select value={newSubAccount.industry_template_id} onChange={(e) => setNewSubAccount({ ...newSubAccount, industry_template_id: e.target.value })} className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500">
                  <option value="">Industry: Inherit from Agency</option>
                  {availableTemplates.map((t) => <option key={String(t.id)} value={String(t.id)}>{String(t.name)}</option>)}
                </select>
                <button onClick={createSubAccount} disabled={creatingSubAccount || !newSubAccount.email || !newSubAccount.password || !newSubAccount.first_name || !newSubAccount.last_name} className="bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium flex items-center gap-2 border-none cursor-pointer">
                  <UserPlus size={14} /> {creatingSubAccount ? "Creating..." : "Create Sub-Account"}
                </button>
              </div>
            </div>

            {subAccounts.length > 0 && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h4 className="text-md font-semibold text-white mb-3">Existing Sub-Accounts ({subAccounts.length})</h4>
                <div className="space-y-2">
                  {subAccounts.map((sa) => (
                    <div key={String(sa.id)} className="flex items-center justify-between p-3 bg-slate-700/30 rounded-lg border border-slate-600/50">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400 text-xs font-bold">{String(sa.first_name || "").charAt(0)}{String(sa.last_name || "").charAt(0)}</div>
                        <div>
                          <div className="text-sm text-white font-medium">{String(sa.first_name)} {String(sa.last_name)}</div>
                          <div className="text-xs text-slate-400">{String(sa.email)}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 flex-wrap">
                        <select value={String(sa.role)} onChange={(e) => updateSubAccountRole(String(sa.id), e.target.value)} className="bg-slate-700/50 border border-slate-600 rounded px-2 py-1 text-xs text-white">
                          <option value="recruiter">Recruiter</option>
                          <option value="compliance_officer">Compliance Officer</option>
                          <option value="manager">Manager</option>
                          <option value="owner">Owner</option>
                        </select>
                        <select value={String(sa.industry_template_id || "")} onChange={(e) => updateSubAccountTemplate(String(sa.id), e.target.value)} className="bg-slate-700/50 border border-slate-600 rounded px-2 py-1 text-xs text-white" title="Industry template for candidates invited by this sub-account">
                          <option value="">Industry: Inherit</option>
                          {availableTemplates.map((t) => <option key={String(t.id)} value={String(t.id)}>{String(t.name)}</option>)}
                        </select>
                        {sa.industry_template_name ? <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">{String(sa.industry_template_name)}</span> : null}
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${sa.is_active ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>{sa.is_active ? "Active" : "Inactive"}</span>
                        <button onClick={() => deleteSubAccount(String(sa.id))} className="text-red-400 hover:text-red-300 text-xs border-none bg-transparent cursor-pointer"><Trash2 size={14} /></button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Notifications Tab ── */}
        {tab === "notifications" && (
          <div className="space-y-6">
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white flex items-center gap-2"><Activity className="text-cyan-400" size={20} /> Notification Centre</h3>
                <div className="flex items-center gap-2">
                  <button onClick={seedNotifications} disabled={seedingNotifs} className="bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg px-3 py-1.5 text-xs font-medium border border-slate-600 cursor-pointer">{seedingNotifs ? "Generating..." : "Generate Notifications"}</button>
                  {unreadCount > 0 && (
                    <button onClick={markAllNotificationsRead} className="bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 rounded-lg px-3 py-1.5 text-xs font-medium border border-blue-500/30 cursor-pointer">Mark All Read</button>
                  )}
                </div>
              </div>

              <div className="flex gap-2 mb-4">
                {["all", "expiry_warning", "completion", "action_required", "payment"].map((cat) => (
                  <button key={cat} onClick={() => setNotifCategoryFilter(cat)} className={`px-3 py-1 rounded-full text-xs font-medium border cursor-pointer ${notifCategoryFilter === cat ? "bg-cyan-600/20 text-cyan-400 border-cyan-500/30" : "bg-slate-700/50 text-slate-400 border-slate-600 hover:text-white"}`}>
                    {cat === "all" ? "All" : cat.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                  </button>
                ))}
              </div>

              {(notifications || []).length === 0 ? (
                <div className="text-center py-12 text-slate-500">
                  <Activity size={40} className="mx-auto mb-3 opacity-50" />
                  <p className="text-sm">No notifications yet. Click &quot;Generate Notifications&quot; to create activity-based alerts.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {(notifications || []).map((n) => {
                    const severityColors: Record<string, string> = {
                      success: "border-l-green-500 bg-green-500/5",
                      warning: "border-l-amber-500 bg-amber-500/5",
                      error: "border-l-red-500 bg-red-500/5",
                      info: "border-l-blue-500 bg-blue-500/5",
                    };
                    const severity = String(n.severity || "info");
                    return (
                      <div key={String(n.id)} className={`p-3 rounded-lg border border-slate-700 border-l-4 ${severityColors[severity] || severityColors.info} ${n.is_read ? "opacity-60" : ""}`}>
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-semibold text-white">{String(n.title)}</span>
                              {!n.is_read && <span className="w-2 h-2 rounded-full bg-cyan-400" />}
                            </div>
                            <p className="text-xs text-slate-400 mt-1">{String(n.message)}</p>
                            <div className="flex items-center gap-3 mt-2">
                              <span className="text-xs text-slate-500">{fmtDate(n.created_at)}</span>
                              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700/50 text-slate-400">{String(n.category || "general").replace(/_/g, " ")}</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-1 ml-2">
                            {!n.is_read && (
                              <button onClick={() => markNotificationRead(String(n.id))} className="text-slate-400 hover:text-blue-400 text-xs border-none bg-transparent cursor-pointer p-1" title="Mark read"><Eye size={14} /></button>
                            )}
                            <button onClick={() => deleteNotification(String(n.id))} className="text-slate-400 hover:text-red-400 text-xs border-none bg-transparent cursor-pointer p-1" title="Delete"><Trash2 size={14} /></button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function DPAAcceptancePanel() {
  const { token, userId } = useAuth();
  const [dpaStatus, setDpaStatus] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [sigName, setSigName] = useState("");
  const [sigRole, setSigRole] = useState("");
  const [accepting, setAccepting] = useState(false);

  useEffect(() => {
    if (!token || !userId) return;
    gdprApi.getAgencyDPAStatus(token, userId)
      .then(setDpaStatus)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, userId]);

  const handleAccept = async () => {
    if (!token || !userId || !sigName || !sigRole) return;
    setAccepting(true);
    try {
      await gdprApi.acceptAgencyDPA(token, {
        agency_id: userId,
        signatory_name: sigName,
        signatory_role: sigRole,
      });
      setDpaStatus({ dpa_accepted: true, accepted_at: new Date().toISOString() });
    } catch (_e) { /* handled by API */ }
    setAccepting(false);
  };

  if (loading) return null;

  if (dpaStatus?.dpa_accepted) {
    return (
      <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-4 flex items-center gap-3">
        <CheckCircle2 size={20} className="text-green-400" />
        <div>
          <span className="text-sm text-green-300 font-medium">Data Processing Agreement accepted</span>
          <span className="text-xs text-slate-400 ml-2">{dpaStatus.accepted_at ? new Date(dpaStatus.accepted_at as string).toLocaleDateString("en-GB") : ""}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6 space-y-4">
      <h3 className="text-md font-semibold text-amber-300 flex items-center gap-2">
        <AlertTriangle size={18} /> Data Processing Agreement Required
      </h3>
      <div className="text-xs text-slate-300 leading-relaxed space-y-2 max-h-40 overflow-y-auto bg-slate-800/50 rounded-lg p-4 border border-slate-700">
        <p><strong className="text-white">Data Processing Agreement — Version 1.0</strong></p>
        <p>As the Data Controller, the undersigned agency confirms that:</p>
        <p>1. They have a lawful basis under UK GDPR for instructing Viper AI Ltd (Data Processor) to process candidate personal data for the purposes of pre-employment vetting and continuous compliance monitoring.</p>
        <p>2. They accept responsibility for ensuring all data subjects (candidates) are appropriately informed about the processing of their personal data, including the retention period and their rights under UK GDPR.</p>
        <p>3. Candidate vetting data will be retained for a maximum of 12 months from the date of the candidate&apos;s last active placement for the purpose of continuous compliance monitoring. After 12 months of inactivity, personal data will be anonymised.</p>
        <p>4. DBS certificate numbers will be automatically purged 6 months after the recruitment decision, in accordance with the DBS Code of Practice.</p>
        <p>5. The agency may request data export or deletion at any time by contacting enquiries@viperai.io or via the platform&apos;s GDPR tools.</p>
        <p>6. Both parties shall comply with the UK General Data Protection Regulation (UK GDPR) and the Data Protection Act 2018 at all times.</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-slate-400 block mb-1">Signatory Name <span className="text-red-400">*</span></label>
          <input type="text" value={sigName} onChange={(e) => setSigName(e.target.value)}
            placeholder="Full name of authorised signatory"
            className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm" />
        </div>
        <div>
          <label className="text-xs text-slate-400 block mb-1">Signatory Role <span className="text-red-400">*</span></label>
          <input type="text" value={sigRole} onChange={(e) => setSigRole(e.target.value)}
            placeholder="e.g. Director, Compliance Manager"
            className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm" />
        </div>
      </div>
      <button onClick={handleAccept} disabled={accepting || !sigName || !sigRole}
        className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-6 py-2.5 rounded-lg text-sm font-medium">
        {accepting ? "Accepting..." : "Accept Data Processing Agreement"}
      </button>
    </div>
  );
}
