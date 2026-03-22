import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { candidatesApi, complianceApi, monitoringApi, dashboardApi, adminApi, adminExtendedApi, fraudApi, schedulerApi, reportsApi, billingApi } from "../api/client";
import {
  Shield, CheckCircle, XCircle, Clock, AlertTriangle, Users,
  BarChart3, Bell, LogOut, RefreshCw, Eye, Play, Settings,
  DollarSign, FileText, TrendingUp, ShieldAlert, Zap, Download, CreditCard,
  Edit, Trash2, UserPlus, Ban, History, Send, PlusCircle,
} from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend, BarChart, Bar, XAxis, YAxis } from "recharts";

type Tab = "overview" | "candidates" | "alerts" | "monitoring" | "candidate-detail" | "settings" | "analytics" | "fraud" | "scheduler" | "subscriptions" | "overrides" | "user-management" | "audit-logs" | "agencies" | "invoicing";

export default function AdminPanel() {
  const { token, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("overview");
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [candidates, setCandidates] = useState<Record<string, unknown>[]>([]);
  const [alerts, setAlerts] = useState<Record<string, unknown>[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<Record<string, unknown> | null>(null);
  const [candidateCompliance, setCandidateCompliance] = useState<Record<string, unknown> | null>(null);
  const [monitoringResults, setMonitoringResults] = useState<Record<string, unknown> | null>(null);
  const [runningMonitoring, setRunningMonitoring] = useState(false);
  const [message, setMessage] = useState("");

  // Settings state
  const [pricing, setPricing] = useState<Record<string, unknown>[]>([]);
  const [editingPricing, setEditingPricing] = useState<Record<string, { cost_price: string; sell_price: string }>>({});
  const [savingPricing, setSavingPricing] = useState("");

  // Analytics state
  const [revenuePeriod, setRevenuePeriod] = useState("ytd");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [revenueData, setRevenueData] = useState<Record<string, unknown> | null>(null);
  const [opsData, setOpsData] = useState<Record<string, unknown> | null>(null);
  const [agencyData, setAgencyData] = useState<Record<string, unknown>[]>([]);
  const [invoices, setInvoices] = useState<Record<string, unknown>[]>([]);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [generatingInvoices, setGeneratingInvoices] = useState("");

  // Fraud detection state
  const [fraudFlags, setFraudFlags] = useState<Record<string, unknown>[]>([]);
  const [fraudSummary, setFraudSummary] = useState<Record<string, unknown> | null>(null);
  const [runningFraudScan, setRunningFraudScan] = useState(false);

  // Scheduler state
  const [schedulerStatus, setSchedulerStatus] = useState<Record<string, unknown> | null>(null);
  const [triggeringJob, setTriggeringJob] = useState("");

  // Override state
  const [overrideCandId, setOverrideCandId] = useState("");
  const [overrideCheckType, setOverrideCheckType] = useState("identity");
  const [overrideStatus, setOverrideStatus] = useState("completed");
  const [overrideNotes, setOverrideNotes] = useState("");
  const [overriding, setOverriding] = useState(false);

  // User management state
  const [agencies, setAgencies] = useState<Record<string, unknown>[]>([]);
  const [newAgency, setNewAgency] = useState({ name: "", email: "", password: "", contact_name: "", phone: "" });
  const [newCandidate, setNewCandidate] = useState({ email: "", password: "", first_name: "", last_name: "", profession: "" });
  const [creatingUser, setCreatingUser] = useState(false);
  const [deletingId, setDeletingId] = useState("");

  // Agency suspension state
  const [suspendReason, setSuspendReason] = useState("");

  // Candidate editing state
  const [editingCandidate, setEditingCandidate] = useState<Record<string, unknown> | null>(null);
  const [editFields, setEditFields] = useState<Record<string, string>>({});
  const [savingEdit, setSavingEdit] = useState(false);

  // Alert settings state
  const [alertSettings, setAlertSettings] = useState<Record<string, unknown>>({});
  const [editAlertSettings, setEditAlertSettings] = useState<Record<string, string>>({});
  const [savingAlertSettings, setSavingAlertSettings] = useState(false);

  // Audit logs state
  const [auditLogs, setAuditLogs] = useState<Record<string, unknown>[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditFilter, setAuditFilter] = useState({ entity_type: "", action: "" });
  const [auditPage, setAuditPage] = useState(0);


  // Subscription tier editing state
  const [subTiers, setSubTiers] = useState<Record<string, {name: string; monthly_price: number; per_worker_price: number; max_workers: number; features: string[]}>>({});
  const [editingTier, setEditingTier] = useState<string | null>(null);
  const [tierEditData, setTierEditData] = useState<{name: string; monthly_price: string; per_worker_price: string; max_workers: string; features: string}>({name: "", monthly_price: "", per_worker_price: "", max_workers: "", features: ""});
  const [savingTier, setSavingTier] = useState(false);

  // Agency discount editing state
  const [editingDiscount, setEditingDiscount] = useState<string | null>(null);
  const [discountValue, setDiscountValue] = useState("");
  const [savingDiscount, setSavingDiscount] = useState(false);

  // Admin invoicing state
  const [adminInvoices, setAdminInvoices] = useState<Record<string, unknown>[]>([]);
  const [adjustingInvoice, setAdjustingInvoice] = useState<string | null>(null);
  const [adjustAmount, setAdjustAmount] = useState("");
  const [adjustNotes, setAdjustNotes] = useState("");
  const [savingAdjust, setSavingAdjust] = useState(false);
  const [invoiceFilter, setInvoiceFilter] = useState("all");

  // Monitoring candidates state
  const [monitoringCandidates, setMonitoringCandidates] = useState<Record<string, unknown>[]>([]);
  const [monitoringFilter, setMonitoringFilter] = useState("all");

  // Candidate full detail state (for overrides/editing check data)
  const [candidateDetail, setCandidateDetail] = useState<Record<string, unknown> | null>(null);
  const [retriggeringId, setRetriggeringId] = useState("");


  // Monitoring revenue state
  const [monRevenuePeriod, setMonRevenuePeriod] = useState("ytd");
  const [monCustomFrom, setMonCustomFrom] = useState("");
  const [monCustomTo, setMonCustomTo] = useState("");
  const [monRevenueData, setMonRevenueData] = useState<Record<string, unknown> | null>(null);

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      const [s, c, a] = await Promise.all([
        dashboardApi.getStats(token),
        candidatesApi.list(token).catch(() => []),
        monitoringApi.getAlerts(token).catch(() => []),
      ]);
      setStats(s); setCandidates(c); setAlerts(a);
    } catch (err) { console.error("Failed to load data", err); }
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);

  const loadPricing = useCallback(async () => {
    if (!token) return;
    try { const p = await adminApi.getPricing(token); setPricing(p); } catch { /* ignore */ }
  }, [token]);

  const loadMonitoringRevenue = useCallback(async () => {
    if (!token) return;
    try {
      const params: Record<string, string> = { period: monRevenuePeriod };
      if (monRevenuePeriod === "custom") { params.date_from = monCustomFrom; params.date_to = monCustomTo; }
      const rev = await adminApi.getRevenueAnalytics(token, params);
      setMonRevenueData(rev);
    } catch { /* ignore */ }
  }, [token, monRevenuePeriod, monCustomFrom, monCustomTo]);

  const loadAnalytics = useCallback(async () => {
    if (!token) return;
    setAnalyticsLoading(true);
    try {
      const params: Record<string, string> = { period: revenuePeriod };
      if (revenuePeriod === "custom") { params.date_from = customFrom; params.date_to = customTo; }
      const [rev, ops, agencies, inv] = await Promise.all([
        adminApi.getRevenueAnalytics(token, params),
        adminApi.getOperationsAnalytics(token, params),
        adminApi.getAgencyAnalytics(token, params),
        adminApi.getInvoices(token, params),
      ]);
      setRevenueData(rev); setOpsData(ops); setAgencyData(agencies); setInvoices(inv);
    } catch (err) { console.error("Failed to load analytics", err); }
    finally { setAnalyticsLoading(false); }
  }, [token, revenuePeriod, customFrom, customTo]);

  const loadFraudData = useCallback(async () => {
    if (!token) return;
    try {
      const [flags, summary] = await Promise.all([
        fraudApi.getFlags(token).catch(() => []),
        fraudApi.getSummary(token).catch(() => null),
      ]);
      setFraudFlags(flags); setFraudSummary(summary);
    } catch { /* ignore */ }
  }, [token]);

  const loadSchedulerStatus = useCallback(async () => {
    if (!token) return;
    try { const s = await schedulerApi.getStatus(token); setSchedulerStatus(s); } catch { /* ignore */ }
  }, [token]);

  const loadAgencies = useCallback(async () => {
    if (!token) return;
    try { const a = await adminExtendedApi.listAgencies(token); setAgencies(a); } catch { /* ignore */ }
  }, [token]);

  const loadAuditLogs = useCallback(async () => {
    if (!token) return;
    try {
      const params: Record<string, unknown> = { limit: 50, offset: auditPage * 50 };
      if (auditFilter.entity_type) params.entity_type = auditFilter.entity_type;
      if (auditFilter.action) params.action = auditFilter.action;
      const result = await adminExtendedApi.getAuditLogs(token, params as Record<string, string>);
      setAuditLogs(result.logs); setAuditTotal(result.total);
    } catch { /* ignore */ }
  }, [token, auditPage, auditFilter]);

  const loadAlertSettings = useCallback(async () => {
    if (!token) return;
    try { const s = await adminExtendedApi.getAlertSettings(token); setAlertSettings(s); } catch { /* ignore */ }
  }, [token]);


  const loadSubscriptionTiers = async () => {
    if (!token) return;
    try {
      const tiers = await billingApi.getTiers(token);
      setSubTiers(tiers as Record<string, {name: string; monthly_price: number; per_worker_price: number; max_workers: number; features: string[]}>);
    } catch { /* ignore */ }
  };

  const loadCandidateDetail = async (candidateId: string) => {
    if (!token) return;
    try { const d = await adminExtendedApi.getCandidateFullDetail(token, candidateId); setCandidateDetail(d); } catch { /* ignore */ }
  };

  const loadAdminInvoices = useCallback(async () => {
    if (!token) return;
    try { const inv = await adminExtendedApi.listInvoices(token); setAdminInvoices(inv); } catch { /* ignore */ }
  }, [token]);

  const loadMonitoringCandidates = useCallback(async () => {
    if (!token) return;
    try { const mc = await adminExtendedApi.getCandidatesMonitoring(token); setMonitoringCandidates(mc); } catch { /* ignore */ }
  }, [token]);

  useEffect(() => { if (tab === "fraud") loadFraudData(); }, [tab, loadFraudData]);
  useEffect(() => { if (tab === "scheduler") loadSchedulerStatus(); }, [tab, loadSchedulerStatus]);
  useEffect(() => { if (tab === "settings") { loadPricing(); loadAlertSettings(); } }, [tab, loadPricing, loadAlertSettings]);
  useEffect(() => { if (tab === "analytics") loadAnalytics(); }, [tab, loadAnalytics]);
  useEffect(() => { if (tab === "monitoring") { loadMonitoringRevenue(); loadMonitoringCandidates(); } }, [tab, loadMonitoringRevenue, loadMonitoringCandidates]);
  useEffect(() => { if (tab === "agencies" || tab === "user-management") loadAgencies(); }, [tab, loadAgencies]);
  useEffect(() => { if (tab === "audit-logs") loadAuditLogs(); }, [tab, loadAuditLogs]);
  useEffect(() => { if (tab === "invoicing") loadAdminInvoices(); }, [tab, loadAdminInvoices]);

  const showMessage = (msg: string) => { setMessage(msg); setTimeout(() => setMessage(""), 4000); };

  const viewCandidate = async (candidate: Record<string, unknown>) => {
    setSelectedCandidate(candidate); setTab("candidate-detail");
    if (token) {
      try { const comp = await complianceApi.get(token, candidate.id as string).catch(() => null); setCandidateCompliance(comp); } catch { /* ignore */ }
      loadCandidateDetail(candidate.id as string);
    }
  };

  const evaluateCandidate = async (candidateId: string) => {
    if (!token) return;
    try {
      await complianceApi.evaluate(token, candidateId); showMessage("Compliance re-evaluated successfully"); await loadData();
      if (selectedCandidate && selectedCandidate.id === candidateId) { const comp = await complianceApi.get(token, candidateId).catch(() => null); setCandidateCompliance(comp); }
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const resolveAlert = async (alertId: string) => {
    if (!token) return;
    try { await monitoringApi.resolveAlert(token, alertId); showMessage("Alert resolved"); await loadData(); }
    catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const runMonitoringChecks = async () => {
    if (!token) return; setRunningMonitoring(true);
    try { const results = await monitoringApi.runChecks(token); setMonitoringResults(results); showMessage("Monitoring checks completed"); await loadData(); }
    catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setRunningMonitoring(false); }
  };

  const savePricingItem = async (checkType: string) => {
    if (!token) return; const edit = editingPricing[checkType]; if (!edit) return;
    setSavingPricing(checkType);
    try {
      await adminApi.updatePricing(token, checkType, { cost_price: parseFloat(edit.cost_price), sell_price: parseFloat(edit.sell_price) });
      showMessage(`Pricing updated for ${checkType}`); await loadPricing();
      setEditingPricing((prev) => { const next = { ...prev }; delete next[checkType]; return next; });
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setSavingPricing(""); }
  };

  const generateInvoicesForAgency = async (agencyId: string) => {
    if (!token) return; setGeneratingInvoices(agencyId);
    try {
      const result = await adminApi.generateInvoices(token, agencyId);
      showMessage(`Generated ${(result as Record<string, unknown>).generated} invoices`);
      await loadAnalytics();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setGeneratingInvoices(""); }
  };

  const runFraudScan = async () => {
    if (!token) return;
    setRunningFraudScan(true);
    try {
      await fraudApi.runScan(token);
      showMessage("Fraud scan completed");
      loadFraudData();
    } catch (err) { showMessage("Error: " + (err instanceof Error ? err.message : "Failed")); }
    finally { setRunningFraudScan(false); }
  };

  const resolveFraudFlag = async (flagId: string) => {
    if (!token) return;
    try { await fraudApi.resolveFlag(token, flagId); showMessage("Flag resolved"); loadFraudData(); } catch { /* ignore */ }
  };

  const triggerJob = async (jobName: string) => {
    if (!token) return;
    setTriggeringJob(jobName);
    try { await schedulerApi.triggerJob(token, jobName); showMessage(`Job '${jobName}' completed`); loadSchedulerStatus(); } catch (err) { showMessage("Error: " + (err instanceof Error ? err.message : "Failed")); }
    finally { setTriggeringJob(""); }
  };

  const downloadFinancialReport = async () => {
    if (!token) return;
    try {
      const resp = await reportsApi.downloadFinancialReport(token, revenuePeriod, customFrom, customTo);
      if (!resp.ok) throw new Error("Failed");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "financial_report.pdf"; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { showMessage("Error: " + (err instanceof Error ? err.message : "Download failed")); }
  };

  const downloadComplianceReport = async () => {
    if (!token) return;
    try {
      const resp = await reportsApi.downloadComplianceReport(token);
      if (!resp.ok) throw new Error("Failed");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "compliance_report.pdf"; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { showMessage("Error: " + (err instanceof Error ? err.message : "Download failed")); }
  };

  const markInvoicePaid = async (invoiceId: string) => {
    if (!token) return;
    try { await adminApi.markInvoicePaid(token, invoiceId); showMessage("Invoice marked as paid"); await loadAnalytics(); }
    catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  // Override a check result
  const handleOverride = async () => {
    if (!token || !overrideCandId) return;
    setOverriding(true);
    try {
      await adminExtendedApi.overrideCheck(token, overrideCandId, { check_type: overrideCheckType, status: overrideStatus, notes: overrideNotes });
      showMessage("Check result overridden successfully");
      setOverrideNotes("");
      await loadData();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setOverriding(false); }
  };

  // Suspend/activate agency
  const handleAgencyStatus = async (agencyId: string, status: string) => {
    if (!token) return;
    try {
      await adminExtendedApi.updateAgencyStatus(token, agencyId, { status, reason: suspendReason });
      showMessage(`Agency ${status === "suspended" ? "suspended" : "activated"} successfully`);
      setSuspendReason("");
      await loadAgencies();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  // Create agency
  const handleCreateAgency = async () => {
    if (!token) return;
    setCreatingUser(true);
    try {
      await adminExtendedApi.createAgency(token, newAgency);
      showMessage("Agency created successfully");
      setNewAgency({ name: "", email: "", password: "", contact_name: "", phone: "" });
      await loadAgencies();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setCreatingUser(false); }
  };

  // Create candidate
  const handleCreateCandidate = async () => {
    if (!token) return;
    setCreatingUser(true);
    try {
      await adminExtendedApi.createCandidate(token, newCandidate);
      showMessage("Candidate created successfully");
      setNewCandidate({ email: "", password: "", first_name: "", last_name: "", profession: "" });
      await loadData();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setCreatingUser(false); }
  };

  // Delete agency
  const handleDeleteAgency = async (agencyId: string) => {
    if (!token || !confirm("Delete this agency and all associated data?")) return;
    setDeletingId(agencyId);
    try {
      await adminExtendedApi.deleteAgency(token, agencyId);
      showMessage("Agency deleted"); await loadAgencies();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setDeletingId(""); }
  };

  // Delete candidate
  const handleDeleteCandidate = async (candidateId: string) => {
    if (!token || !confirm("Delete this candidate and all associated data?")) return;
    setDeletingId(candidateId);
    try {
      await adminExtendedApi.deleteCandidate(token, candidateId);
      showMessage("Candidate deleted"); await loadData();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setDeletingId(""); }
  };

  // Save candidate profile edit
  const handleSaveCandidateEdit = async () => {
    if (!token || !editingCandidate) return;
    setSavingEdit(true);
    try {
      await adminExtendedApi.editCandidate(token, editingCandidate.id as string, editFields);
      showMessage("Candidate profile updated");
      setEditingCandidate(null);
      setEditFields({});
      await loadData();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setSavingEdit(false); }
  };

  // Save alert settings
  const handleSaveAlertSettings = async () => {
    if (!token) return;
    setSavingAlertSettings(true);
    try {
      const settings: Record<string, number> = {};
      Object.entries(editAlertSettings).forEach(([k, v]) => { settings[k] = parseInt(v) || 0; });
      await adminExtendedApi.updateAlertSettings(token, { settings });
      showMessage("Alert settings saved");
      await loadAlertSettings();
      setEditAlertSettings({});
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setSavingAlertSettings(false); }
  };

  // Re-trigger verification
  const handleRetriggerReference = async (candidateId: string, refId: string) => {
    if (!token) return;
    setRetriggeringId(refId);
    try {
      await adminExtendedApi.retriggerReference(token, candidateId, refId);
      showMessage("Reference verification re-triggered");
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setRetriggeringId(""); }
  };


  const saveTier = async (tierKey: string) => {
    if (!token) return;
    setSavingTier(true);
    try {
      const features = tierEditData.features.split("\n").map(f => f.trim()).filter(f => f.length > 0);
      await billingApi.updateTier(token, tierKey, {
        name: tierEditData.name,
        monthly_price: parseFloat(tierEditData.monthly_price) || 0,
        per_worker_price: parseFloat(tierEditData.per_worker_price) || 0,
        max_workers: parseInt(tierEditData.max_workers) || 0,
        features,
      });
      setEditingTier(null);
      await loadSubscriptionTiers();
      setMessage("Tier pricing updated successfully");
      setTimeout(() => setMessage(""), 3000);
    } catch (err) {
      console.error("Failed to save tier", err);
    } finally {
      setSavingTier(false);
    }
  };

  const startEditTier = (tierKey: string) => {
    const tier = subTiers[tierKey];
    if (!tier) return;
    setEditingTier(tierKey);
    setTierEditData({
      name: tier.name,
      monthly_price: tier.monthly_price.toString(),
      per_worker_price: tier.per_worker_price.toString(),
      max_workers: tier.max_workers.toString(),
      features: tier.features.join("\n"),
    });
  };

  const handleRetriggerEmployment = async (candidateId: string, verId: string) => {
    if (!token) return;
    setRetriggeringId(verId);
    try {
      await adminExtendedApi.retriggerEmployment(token, candidateId, verId);
      showMessage("Employment verification re-triggered");
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setRetriggeringId(""); }
  };

  const handleSaveDiscount = async (agencyId: string) => {
    if (!token) return;
    setSavingDiscount(true);
    try {
      const val = parseFloat(discountValue);
      if (isNaN(val) || val < 0 || val > 100) { showMessage("Error: Discount must be between 0 and 100"); setSavingDiscount(false); return; }
      await adminExtendedApi.updateAgencyDiscount(token, agencyId, val);
      showMessage(`Discount set to ${val}%`);
      setEditingDiscount(null);
      loadAgencies();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setSavingDiscount(false); }
  };

  const handleAdjustInvoice = async (invoiceId: string) => {
    if (!token) return;
    setSavingAdjust(true);
    try {
      const amt = parseFloat(adjustAmount);
      if (isNaN(amt) || amt < 0) { showMessage("Error: Invalid amount"); setSavingAdjust(false); return; }
      await adminExtendedApi.adjustInvoice(token, invoiceId, amt, adjustNotes || undefined);
      showMessage("Invoice adjusted successfully");
      setAdjustingInvoice(null);
      loadAdminInvoices();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setSavingAdjust(false); }
  };

  const handleMarkInvoicePaid = async (invoiceId: string) => {
    if (!token) return;
    try {
      await adminExtendedApi.markInvoicePaid(token, invoiceId);
      showMessage("Invoice marked as paid");
      loadAdminInvoices();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const StatusBadge = ({ status }: { status: string }) => {
    const colors: Record<string, string> = {
      compliant: "bg-green-500/20 text-green-400 border-green-500/30",
      clear: "bg-green-500/20 text-green-400 border-green-500/30",
      active: "bg-green-500/20 text-green-400 border-green-500/30",
      valid: "bg-green-500/20 text-green-400 border-green-500/30",
      verified: "bg-green-500/20 text-green-400 border-green-500/30",
      completed: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      paid: "bg-green-500/20 text-green-400 border-green-500/30",
      sent: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      processing: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      pending: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      in_progress: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      pending_review: "bg-orange-500/20 text-orange-400 border-orange-500/30",
      disputed: "bg-orange-500/20 text-orange-400 border-orange-500/30",
      has_information: "bg-amber-500/20 text-amber-400 border-amber-500/30",
      consider: "bg-red-500/20 text-red-400 border-red-500/30",
      flagged: "bg-red-500/20 text-red-400 border-red-500/30",
      failed: "bg-red-500/20 text-red-400 border-red-500/30",
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

  const criticalAlerts = alerts.filter((a) => a.severity === "critical");
  const flaggedCandidates = candidates.filter((c) => c.compliance_status === "incomplete" || c.compliance_status === "flagged");

  /* Period filter buttons */
  const PeriodFilter = ({ period, setPeriodFn, cFrom, setCFrom, cTo, setCTo, onApply }: {
    period: string; setPeriodFn: (p: string) => void;
    cFrom: string; setCFrom: (v: string) => void; cTo: string; setCTo: (v: string) => void; onApply?: () => void;
  }) => (
    <div className="flex flex-wrap items-center gap-2">
      {[{ key: "ytd", label: "YTD" }, { key: "mtd", label: "MTD" }, { key: "fytd", label: "FYTD" }, { key: "all", label: "All Time" }, { key: "custom", label: "Custom" }].map((p) => (
        <button key={p.key} onClick={() => setPeriodFn(p.key)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${period === p.key ? "bg-blue-600 text-white" : "bg-slate-700/50 text-slate-300 hover:bg-slate-700"}`}>{p.label}</button>
      ))}
      {period === "custom" && (<>
        <input type="date" value={cFrom} onChange={(e) => setCFrom(e.target.value)} className="bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1 text-white text-xs" />
        <span className="text-slate-400 text-xs">to</span>
        <input type="date" value={cTo} onChange={(e) => setCTo(e.target.value)} className="bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1 text-white text-xs" />
        {onApply && <button onClick={onApply} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-green-600 text-white hover:bg-green-700">Apply</button>}
      </>)}
    </div>
  );

  /* Structured monitoring results display */
  const MonitoringResultsDisplay = ({ results }: { results: Record<string, unknown> }) => {
    const sections = [
      { key: "dbs_updates", label: "DBS Update Service", icon: <Shield className="text-blue-400" size={16} />, emptyMsg: "No DBS updates found" },
      { key: "visa_expiries", label: "Visa Expiry Alerts", icon: <AlertTriangle className="text-amber-400" size={16} />, emptyMsg: "No visa expiries detected" },
      { key: "registration_renewals", label: "Registration Renewals", icon: <RefreshCw className="text-purple-400" size={16} />, emptyMsg: "No registration renewals due" },
      { key: "sanction_alerts", label: "Sanction Alerts", icon: <XCircle className="text-red-400" size={16} />, emptyMsg: "No sanction alerts" },
    ];
    return (
      <div className="grid grid-cols-2 gap-4">
        {sections.map((section) => {
          const items = results[section.key]; const arr = Array.isArray(items) ? items : [];
          return (
            <div key={section.key} className="bg-slate-700/30 rounded-lg p-4 border border-slate-600/50">
              <div className="flex items-center gap-2 mb-3">
                {section.icon}
                <h4 className="text-white text-sm font-medium">{section.label}</h4>
                <span className={`ml-auto text-xs px-2 py-0.5 rounded-full ${arr.length > 0 ? "bg-amber-500/20 text-amber-400" : "bg-green-500/20 text-green-400"}`}>
                  {arr.length > 0 ? `${arr.length} found` : "Clear"}
                </span>
              </div>
              {arr.length === 0 ? <p className="text-slate-400 text-xs">{section.emptyMsg}</p> : (
                <div className="space-y-1.5 max-h-32 overflow-y-auto">
                  {arr.map((item: Record<string, unknown>, idx: number) => (
                    <div key={idx} className="p-2 bg-slate-800/50 rounded text-xs text-slate-300 border border-slate-600/30">
                      {typeof item === "object" && item !== null ? (
                        <div className="space-y-0.5">{Object.entries(item).map(([k, v]) => (<div key={k}><span className="text-slate-500">{k}:</span> <span className="text-white">{String(v)}</span></div>))}</div>
                      ) : <span>{String(item)}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-900">
      <header className="bg-slate-800/80 border-b border-slate-700 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="text-blue-400" size={28} />
          <h1 className="text-xl font-bold text-white">HealthVet AI</h1>
          <span className="text-xs bg-purple-600/30 text-purple-300 px-2 py-0.5 rounded-full">Admin Panel</span>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={loadData} className="text-slate-400 hover:text-white"><RefreshCw size={18} /></button>
          <button onClick={logout} className="text-slate-400 hover:text-red-400 flex items-center gap-1 text-sm"><LogOut size={16} /> Sign Out</button>
        </div>
      </header>

      {message && (
        <div className={`mx-6 mt-4 p-3 rounded-lg text-sm ${message.startsWith("Error") ? "bg-red-500/20 text-red-300 border border-red-500/30" : "bg-green-500/20 text-green-300 border border-green-500/30"}`}>{message}</div>
      )}

      <div className="bg-slate-800/50 border-b border-slate-700 px-6">
        <div className="flex gap-1 overflow-x-auto">
          {([
            { key: "overview" as Tab, label: "Overview", icon: <BarChart3 size={16} /> },
            { key: "candidates" as Tab, label: "All Candidates", icon: <Users size={16} /> },
            { key: "alerts" as Tab, label: `Alerts (${alerts.length})`, icon: <Bell size={16} /> },
            { key: "monitoring" as Tab, label: "Monitoring", icon: <Eye size={16} /> },
            { key: "analytics" as Tab, label: "Analytics", icon: <TrendingUp size={16} /> },
            { key: "fraud" as Tab, label: "Fraud Detection", icon: <ShieldAlert size={16} /> },
            { key: "scheduler" as Tab, label: "Scheduler", icon: <Zap size={16} /> },
            { key: "overrides" as Tab, label: "Overrides", icon: <Edit size={16} /> },
            { key: "agencies" as Tab, label: "Agencies", icon: <Ban size={16} /> },
            { key: "user-management" as Tab, label: "User Mgmt", icon: <UserPlus size={16} /> },
            { key: "audit-logs" as Tab, label: "Audit Logs", icon: <History size={16} /> },
            { key: "invoicing" as Tab, label: "Invoicing", icon: <FileText size={16} /> },
            { key: "subscriptions" as Tab, label: "Subscriptions", icon: <CreditCard size={16} /> },
            { key: "settings" as Tab, label: "Settings", icon: <Settings size={16} /> },
          ]).map((item) => (
            <button key={item.key} onClick={() => setTab(item.key)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-all whitespace-nowrap ${tab === item.key ? "text-blue-400 border-blue-400" : "text-slate-400 border-transparent hover:text-white"}`}>
              {item.icon} {item.label}
            </button>
          ))}
        </div>
      </div>

      <main className="p-6">
        {/* Overview Tab */}
        {tab === "overview" && stats && (
          <div className="space-y-6">
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: "Total Candidates", value: stats.total_candidates, icon: <Users className="text-blue-400" size={20} /> },
                { label: "Compliant", value: stats.compliant, icon: <CheckCircle className="text-green-400" size={20} /> },
                { label: "Active Alerts", value: stats.active_alerts, icon: <AlertTriangle className="text-amber-400" size={20} /> },
                { label: "Compliance Rate", value: `${stats.compliance_rate}%`, icon: <BarChart3 className="text-purple-400" size={20} /> },
              ].map((stat) => (
                <div key={stat.label} className="bg-slate-800/80 rounded-xl border border-slate-700 p-5">
                  <div className="flex items-center justify-between mb-2"><p className="text-slate-400 text-xs">{stat.label}</p>{stat.icon}</div>
                  <p className="text-3xl font-bold text-white">{stat.value as string | number}</p>
                </div>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-6">
              {/* Fixed pie chart - height 320, donut with legend */}
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4">Compliance Distribution</h3>
                <ResponsiveContainer width="100%" height={320}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="45%" outerRadius={100} innerRadius={50} dataKey="value" paddingAngle={2}>
                      {pieData.map((entry, index) => (<Cell key={index} fill={entry.color} />))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", color: "white" }} />
                    <Legend verticalAlign="bottom" height={36}
                      formatter={(value: string, entry: Record<string, unknown>) => {
                        const payload = entry.payload as Record<string, unknown> | undefined;
                        return <span style={{ color: "#cbd5e1", fontSize: "13px" }}>{value}: {String(payload?.value ?? "")}</span>;
                      }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4 flex items-center gap-2"><AlertTriangle className="text-red-400" size={18} /> Critical Alerts ({criticalAlerts.length})</h3>
                {criticalAlerts.length === 0 ? <p className="text-slate-400 text-sm">No critical alerts</p> : (
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {criticalAlerts.slice(0, 10).map((alert) => (
                      <div key={alert.id as string} className="p-2 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center justify-between">
                        <span className="text-red-200 text-xs">{alert.message as string}</span>
                        <button onClick={() => resolveAlert(alert.id as string)} className="text-xs text-green-400 hover:text-green-300 shrink-0 ml-2">Resolve</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            {flaggedCandidates.length > 0 && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4">Candidates Requiring Review ({flaggedCandidates.length})</h3>
                <div className="space-y-2">
                  {flaggedCandidates.map((c) => (
                    <div key={c.id as string} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <span className="text-white text-sm">{c.first_name as string} {c.last_name as string}</span>
                        <span className="text-slate-400 text-xs">{c.profession as string}</span>
                        <StatusBadge status={c.compliance_status as string} />
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => evaluateCandidate(c.id as string)} className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-3 py-1 rounded-full hover:bg-blue-600/30">Re-evaluate</button>
                        <button onClick={() => viewCandidate(c)} className="text-xs bg-slate-600/20 text-slate-300 border border-slate-600/30 px-3 py-1 rounded-full hover:bg-slate-600/30"><Eye size={12} className="inline mr-1" /> View</button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Candidates Tab */}
        {tab === "candidates" && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-white">All Candidates ({candidates.length})</h2>

            {/* Inline Edit Panel */}
            {editingCandidate && (
              <div className="bg-slate-800/80 rounded-xl border border-blue-500/30 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-md font-semibold text-white flex items-center gap-2"><Edit size={16} className="text-blue-400" /> Editing: {String(editingCandidate.first_name)} {String(editingCandidate.last_name)}</h3>
                  <button onClick={() => setEditingCandidate(null)} className="text-slate-400 hover:text-white text-xs">Cancel</button>
                </div>
                <div className="grid grid-cols-3 gap-4 mb-4">
                  {[
                    { key: "first_name", label: "First Name" },
                    { key: "last_name", label: "Last Name" },
                    { key: "email", label: "Email" },
                    { key: "profession", label: "Profession" },
                    { key: "registration_body", label: "Registration Body" },
                    { key: "registration_number", label: "Registration Number" },
                  ].map((field) => (
                    <div key={field.key}>
                      <label className="block text-xs text-slate-400 mb-1">{field.label}</label>
                      <input
                        value={editFields[field.key] || ""}
                        onChange={(e) => setEditFields((prev) => ({ ...prev, [field.key]: e.target.value }))}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
                      />
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => handleSaveCandidateEdit()}
                  disabled={savingEdit}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:opacity-50 text-white px-6 py-2 rounded-lg text-sm font-medium flex items-center gap-2"
                >
                  <CheckCircle size={14} /> {savingEdit ? "Saving..." : "Save Changes"}
                </button>
              </div>
            )}

            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full">
                <thead><tr className="border-b border-slate-700">
                  {["Name","Email","Profession","Registration","Score","Status","Actions"].map(h => <th key={h} className="text-left text-xs text-slate-400 font-medium px-4 py-3">{h}</th>)}
                </tr></thead>
                <tbody>
                  {candidates.map((c) => (
                    <tr key={c.id as string} className={`border-b border-slate-700/50 hover:bg-slate-700/30 ${editingCandidate && String(editingCandidate.id) === String(c.id) ? "bg-blue-500/10" : ""}`}>
                      <td className="px-4 py-3 text-sm text-white">{c.first_name as string} {c.last_name as string}</td>
                      <td className="px-4 py-3 text-sm text-slate-300">{c.email as string}</td>
                      <td className="px-4 py-3 text-sm text-slate-300">{(c.profession as string) || "N/A"}</td>
                      <td className="px-4 py-3 text-sm text-slate-300">{c.registration_body as string} {c.registration_number as string}</td>
                      <td className="px-4 py-3"><span className={`text-sm font-bold ${(c.compliance_score as number) >= 95 ? "text-green-400" : (c.compliance_score as number) >= 60 ? "text-amber-400" : "text-red-400"}`}>{c.compliance_score as number}%</span></td>
                      <td className="px-4 py-3"><StatusBadge status={c.compliance_status as string} /></td>
                      <td className="px-4 py-3"><div className="flex gap-2">
                        <button onClick={() => viewCandidate(c)} className="text-blue-400 hover:text-blue-300 text-xs flex items-center gap-1"><Eye size={12} /> View</button>
                        <button onClick={() => {
                          setEditingCandidate(c);
                          setEditFields({
                            first_name: String(c.first_name || ""),
                            last_name: String(c.last_name || ""),
                            email: String(c.email || ""),
                            profession: String(c.profession || ""),
                            registration_body: String(c.registration_body || ""),
                            registration_number: String(c.registration_number || ""),
                          });
                        }} className="text-amber-400 hover:text-amber-300 text-xs flex items-center gap-1"><Edit size={12} /> Edit</button>
                        <button onClick={() => evaluateCandidate(c.id as string)} className="text-purple-400 hover:text-purple-300 text-xs flex items-center gap-1"><RefreshCw size={12} /> Eval</button>
                      </div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Alerts Tab */}
        {tab === "alerts" && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-white flex items-center gap-2"><AlertTriangle className="text-amber-400" size={22} /> All Alerts ({alerts.length})</h2>
            {alerts.length === 0 ? (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-12 text-center"><CheckCircle className="text-green-500 mx-auto mb-3" size={48} /><p className="text-slate-400">No active alerts</p></div>
            ) : (
              <div className="space-y-2">
                {alerts.map((alert) => (
                  <div key={alert.id as string} className={`bg-slate-800/80 rounded-xl border p-4 ${alert.severity === "critical" ? "border-red-500/30" : alert.severity === "high" ? "border-orange-500/30" : "border-yellow-500/30"}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3"><StatusBadge status={alert.severity as string} /><StatusBadge status={alert.alert_type as string} /><span className="text-white text-sm">{alert.message as string}</span></div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-slate-500">{(alert.created_at as string)?.split("T")[0]}</span>
                        <button onClick={() => resolveAlert(alert.id as string)} className="text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-3 py-1 rounded-full hover:bg-green-600/30">Resolve</button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Monitoring Tab */}
        {tab === "monitoring" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white">Continuous Monitoring</h2>
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <p className="text-slate-300 text-sm mb-4">Run all monitoring checks: DBS Update Service, visa expiry alerts, registration renewal tracking, sanction monitoring, and fraud pattern detection.</p>
              <div className="grid grid-cols-2 gap-4 mb-6">
                {[{ label: "DBS Update Service", desc: "Check for changes since certificate issue" },{ label: "Visa Expiry Alerts", desc: "30/60/90 day warnings + expired checks" },{ label: "Registration Renewals", desc: "NMC/GMC/HCPC renewal tracking" },{ label: "Sanction Alerts", desc: "New sanctions on registered professionals" }].map((item) => (
                  <div key={item.label} className="p-4 bg-slate-700/50 rounded-lg"><p className="text-white text-sm font-medium">{item.label}</p><p className="text-slate-400 text-xs mt-1">{item.desc}</p></div>
                ))}
              </div>
              <button onClick={runMonitoringChecks} disabled={runningMonitoring} className="bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 text-white px-6 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2">
                <Play size={16} /> {runningMonitoring ? "Running checks..." : "Run All Monitoring Checks"}
              </button>
            </div>
            {monitoringResults && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4">Monitoring Results</h3>
                <MonitoringResultsDisplay results={monitoringResults} />
              </div>
            )}
            {/* Revenue Overview with date filters */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-md font-semibold text-white flex items-center gap-2"><DollarSign className="text-green-400" size={18} /> Revenue Overview</h3>
                <PeriodFilter period={monRevenuePeriod} setPeriodFn={setMonRevenuePeriod} cFrom={monCustomFrom} setCFrom={setMonCustomFrom} cTo={monCustomTo} setCTo={setMonCustomTo} onApply={loadMonitoringRevenue} />
              </div>
              {monRevenueData ? (
                <div className="grid grid-cols-4 gap-4">
                  {[{ label: "Total Revenue", key: "total_revenue", color: "text-green-400" },{ label: "Total Cost", key: "total_cost", color: "text-amber-400" },{ label: "Margin", key: "total_margin", color: "text-emerald-400" }].map(m => (
                    <div key={m.key} className="p-4 bg-slate-700/50 rounded-lg text-center">
                      <p className="text-slate-400 text-xs mb-1">{m.label}</p>
                      <p className={`text-xl font-bold ${m.color}`}>£{((monRevenueData[m.key] as number) || 0).toLocaleString("en-GB", { minimumFractionDigits: 2 })}</p>
                    </div>
                  ))}
                  <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                    <p className="text-slate-400 text-xs mb-1">Margin %</p>
                    <p className="text-xl font-bold text-blue-400">{(monRevenueData.margin_percentage as number) || 0}%</p>
                  </div>
                </div>
              ) : <p className="text-slate-400 text-sm">Loading revenue data...</p>}
            </div>

            {/* Annual Monitoring Subscriptions */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-md font-semibold text-white flex items-center gap-2"><Eye className="text-purple-400" size={18} /> Annual Monitoring Subscriptions</h3>
                <div className="flex items-center gap-2">
                  <span className="text-slate-400 text-xs">Filter:</span>
                  {["all", "active", "inactive"].map((f) => (
                    <button key={f} onClick={() => setMonitoringFilter(f)}
                      className={`px-2 py-0.5 rounded text-xs font-medium border ${monitoringFilter === f ? "bg-purple-600/30 text-purple-300 border-purple-500/50" : "bg-slate-700/50 text-slate-400 border-slate-600/30 hover:bg-slate-700"}`}>
                      {f.charAt(0).toUpperCase() + f.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
              <p className="text-slate-400 text-xs mb-4">Candidates with active annual monitoring subscriptions will receive continuous compliance updates. Do NOT send monitoring updates to candidates without paid monitoring.</p>
              {monitoringCandidates.length > 0 ? (
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {monitoringCandidates
                    .filter((mc) => {
                      if (monitoringFilter === "all") return true;
                      const hasMonitoring = Number(mc.annual_monitoring) === 1;
                      return monitoringFilter === "active" ? hasMonitoring : !hasMonitoring;
                    })
                    .map((mc, idx) => {
                      const hasMonitoring = Number(mc.annual_monitoring) === 1;
                      return (
                        <div key={idx} className={`flex items-center justify-between p-3 rounded-lg border ${hasMonitoring ? "bg-green-500/10 border-green-500/20" : "bg-slate-700/30 border-slate-600/30"}`}>
                          <div className="flex items-center gap-3">
                            <div className={`w-2.5 h-2.5 rounded-full ${hasMonitoring ? "bg-green-400" : "bg-slate-500"}`} />
                            <div>
                              <p className="text-white text-sm font-medium">{String(mc.candidate_name || mc.candidate_email || "Unknown")}</p>
                              <p className="text-slate-400 text-xs">{String(mc.candidate_email || "")}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-slate-400 text-xs">{String(mc.agency_name || "N/A")}</span>
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${hasMonitoring ? "bg-green-500/20 text-green-400 border border-green-500/30" : "bg-slate-600/30 text-slate-400 border border-slate-500/30"}`}>
                              {hasMonitoring ? "Monitoring Active" : "No Monitoring"}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                </div>
              ) : <p className="text-slate-500 text-sm">No candidate monitoring data available yet. Candidates will appear here once agencies send invites with monitoring enabled.</p>}
              <div className="mt-3 flex items-center gap-4 text-xs">
                <span className="text-green-400">Active: {monitoringCandidates.filter((mc) => Number(mc.annual_monitoring) === 1).length}</span>
                <span className="text-slate-400">Inactive: {monitoringCandidates.filter((mc) => Number(mc.annual_monitoring) !== 1).length}</span>
                <span className="text-slate-500">Total: {monitoringCandidates.length}</span>
              </div>
            </div>
          </div>
        )}

        {/* Analytics Tab */}
        {tab === "analytics" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-white flex items-center gap-2"><TrendingUp className="text-blue-400" size={22} /> Analytics & Reports</h2>
              <div className="flex gap-2">
                <button onClick={downloadFinancialReport} className="bg-green-600/20 text-green-400 border border-green-600/30 px-3 py-1.5 rounded-lg text-xs hover:bg-green-600/30 flex items-center gap-1"><Download size={14} /> Financial PDF</button>
                <button onClick={downloadComplianceReport} className="bg-blue-600/20 text-blue-400 border border-blue-600/30 px-3 py-1.5 rounded-lg text-xs hover:bg-blue-600/30 flex items-center gap-1"><Download size={14} /> Compliance PDF</button>
              </div>
              <PeriodFilter period={revenuePeriod} setPeriodFn={setRevenuePeriod} cFrom={customFrom} setCFrom={setCustomFrom} cTo={customTo} setCTo={setCustomTo} onApply={loadAnalytics} />
            </div>
            {analyticsLoading && <p className="text-slate-400 text-sm">Loading analytics...</p>}

            {/* Financial Summary */}
            {revenueData && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4 flex items-center gap-2"><DollarSign className="text-green-400" size={18} /> Financial Summary</h3>
                <div className="grid grid-cols-5 gap-4 mb-6">
                  {[{ l: "Total Revenue", k: "total_revenue", c: "text-green-400" },{ l: "Total Cost", k: "total_cost", c: "text-amber-400" },{ l: "Gross Margin", k: "total_margin", c: "text-emerald-400" }].map(m => (
                    <div key={m.k} className="p-4 bg-slate-700/50 rounded-lg text-center"><p className="text-slate-400 text-xs mb-1">{m.l}</p><p className={`text-2xl font-bold ${m.c}`}>£{((revenueData[m.k] as number) || 0).toLocaleString("en-GB", { minimumFractionDigits: 2 })}</p></div>
                  ))}
                  <div className="p-4 bg-slate-700/50 rounded-lg text-center"><p className="text-slate-400 text-xs mb-1">Margin %</p><p className="text-2xl font-bold text-blue-400">{(revenueData.margin_percentage as number) || 0}%</p></div>
                  <div className="p-4 bg-slate-700/50 rounded-lg text-center"><p className="text-slate-400 text-xs mb-1">Invoices</p><p className="text-2xl font-bold text-purple-400">{(revenueData.invoice_count as number) || 0}</p></div>
                </div>
                {Boolean(revenueData.by_check_type) && Object.keys(revenueData.by_check_type as Record<string, Record<string, unknown>>).length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-slate-300 mb-3">Revenue by Service Type</h4>
                    <ResponsiveContainer width="100%" height={250}>
                      <BarChart data={Object.entries(revenueData.by_check_type as Record<string, Record<string, unknown>>).map(([key, val]) => ({ name: (val.label as string) || key, revenue: val.revenue as number, cost: val.cost as number }))}>
                        <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} angle={-20} textAnchor="end" height={60} />
                        <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
                        <Tooltip contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", color: "white" }} />
                        <Bar dataKey="revenue" fill="#22c55e" name="Revenue" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="cost" fill="#f59e0b" name="Cost" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            )}

            {/* Operations Summary */}
            {opsData && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4 flex items-center gap-2"><BarChart3 className="text-blue-400" size={18} /> Operations Summary</h3>
                <div className="grid grid-cols-5 gap-4 mb-6">
                  {[{ l: "Total Candidates", k: "total_candidates", c: "text-white" },{ l: "Compliant", k: "compliant", c: "text-green-400" },{ l: "Success Rate", k: "success_rate", c: "text-emerald-400", s: "%" },{ l: "Avg Completion", k: "avg_completion_hours", c: "text-blue-400", s: "h" },{ l: "Flagged", k: "flagged", c: "text-red-400" }].map(m => (
                    <div key={m.k} className="p-4 bg-slate-700/50 rounded-lg text-center"><p className="text-slate-400 text-xs mb-1">{m.l}</p><p className={`text-2xl font-bold ${m.c}`}>{(opsData[m.k] as number) || 0}{m.s || ""}</p></div>
                  ))}
                </div>
                {Boolean(opsData.checks_completed) && typeof opsData.checks_completed === "object" && (
                  <div><h4 className="text-sm font-medium text-slate-300 mb-3">Checks Completed</h4>
                    <div className="grid grid-cols-4 gap-3">
                      {Object.entries(opsData.checks_completed as Record<string, number>).map(([key, val]) => (
                        <div key={key} className="p-3 bg-slate-700/30 rounded-lg text-center"><p className="text-slate-400 text-xs mb-1 capitalize">{key.replace(/_/g, " ")}</p><p className="text-lg font-bold text-white">{val}</p></div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Agency Breakdown */}
            {agencyData.length > 0 && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4 flex items-center gap-2"><Users className="text-purple-400" size={18} /> Agency Breakdown</h3>
                <div className="overflow-x-auto"><table className="w-full"><thead><tr className="border-b border-slate-700">
                  {["Agency","Candidates","Compliant","Revenue","Cost","Margin","Actions"].map(h => <th key={h} className="text-left text-xs text-slate-400 font-medium px-4 py-2">{h}</th>)}
                </tr></thead><tbody>
                  {agencyData.map((a) => (
                    <tr key={a.agency_id as string} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                      <td className="px-4 py-3 text-sm text-white">{a.agency_name as string}</td>
                      <td className="px-4 py-3 text-sm text-white">{a.total_candidates as number}</td>
                      <td className="px-4 py-3 text-sm text-green-400">{a.compliant_candidates as number}</td>
                      <td className="px-4 py-3 text-sm text-green-400">£{((a.revenue as number) || 0).toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-amber-400">£{((a.cost as number) || 0).toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-emerald-400">£{((a.margin as number) || 0).toFixed(2)}</td>
                      <td className="px-4 py-3">
                        <button onClick={() => generateInvoicesForAgency(a.agency_id as string)} disabled={generatingInvoices === a.agency_id}
                          className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-3 py-1 rounded-full hover:bg-blue-600/30 disabled:opacity-50 flex items-center gap-1">
                          <FileText size={12} /> {generatingInvoices === a.agency_id ? "Generating..." : "Generate Invoices"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody></table></div>
              </div>
            )}

            {/* Invoices */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-4 flex items-center gap-2"><FileText className="text-amber-400" size={18} /> Invoices ({invoices.length})</h3>
              {invoices.length === 0 ? <p className="text-slate-400 text-sm">No invoices found. Use "Generate Invoices" on an agency to create invoices from completed checks.</p> : (
                <div className="overflow-x-auto max-h-96 overflow-y-auto"><table className="w-full"><thead className="sticky top-0 bg-slate-800"><tr className="border-b border-slate-700">
                  {["Description","Type","Amount","Status","Date","Actions"].map(h => <th key={h} className="text-left text-xs text-slate-400 font-medium px-3 py-2">{h}</th>)}
                </tr></thead><tbody>
                  {invoices.map((inv) => (
                    <tr key={inv.id as string} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                      <td className="px-3 py-2 text-sm text-slate-300 max-w-xs truncate">{inv.description as string}</td>
                      <td className="px-3 py-2 text-xs text-slate-400 capitalize">{((inv.check_type as string) || "").replace(/_/g, " ")}</td>
                      <td className="px-3 py-2 text-sm text-green-400 font-medium">£{((inv.sell_amount as number) || 0).toFixed(2)}</td>
                      <td className="px-3 py-2"><StatusBadge status={inv.status as string} /></td>
                      <td className="px-3 py-2 text-xs text-slate-400">{(inv.created_at as string)?.split("T")[0]}</td>
                      <td className="px-3 py-2">{inv.status === "pending" && <button onClick={() => markInvoicePaid(inv.id as string)} className="text-xs text-green-400 hover:text-green-300">Mark Paid</button>}</td>
                    </tr>
                  ))}
                </tbody></table></div>
              )}
            </div>
          </div>
        )}

        {/* Fraud Detection Tab */}
        {tab === "fraud" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-white flex items-center gap-2"><ShieldAlert className="text-red-400" size={22} /> Cross-Candidate Fraud Detection</h2>
              <button onClick={runFraudScan} disabled={runningFraudScan}
                className="bg-red-600 hover:bg-red-700 disabled:bg-red-800 text-white px-6 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2">
                <Play size={16} /> {runningFraudScan ? "Scanning..." : "Run Full Scan"}
              </button>
            </div>
            {fraudSummary && (
              <div className="grid grid-cols-5 gap-4">
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-5 text-center"><p className="text-slate-400 text-xs mb-1">Total Flags</p><p className="text-2xl font-bold text-white">{fraudSummary.total_flags as number}</p></div>
                <div className="bg-slate-800/80 rounded-xl border border-red-500/30 p-5 text-center"><p className="text-slate-400 text-xs mb-1">Critical</p><p className="text-2xl font-bold text-red-400">{(fraudSummary.by_severity as Record<string, number>)?.critical || 0}</p></div>
                <div className="bg-slate-800/80 rounded-xl border border-orange-500/30 p-5 text-center"><p className="text-slate-400 text-xs mb-1">High</p><p className="text-2xl font-bold text-orange-400">{(fraudSummary.by_severity as Record<string, number>)?.high || 0}</p></div>
                <div className="bg-slate-800/80 rounded-xl border border-yellow-500/30 p-5 text-center"><p className="text-slate-400 text-xs mb-1">Medium</p><p className="text-2xl font-bold text-yellow-400">{(fraudSummary.by_severity as Record<string, number>)?.medium || 0}</p></div>
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-5 text-center"><p className="text-slate-400 text-xs mb-1">Unresolved</p><p className="text-2xl font-bold text-amber-400">{fraudSummary.unresolved as number}</p></div>
              </div>
            )}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-4">Fraud Flags ({fraudFlags.length})</h3>
              {fraudFlags.length === 0 ? <p className="text-slate-400 text-sm">No fraud flags detected. Run a scan to check.</p> : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {fraudFlags.map((flag) => (
                    <div key={flag.id as string} className={`p-4 rounded-lg border ${flag.severity === "critical" ? "bg-red-500/10 border-red-500/30" : flag.severity === "high" ? "bg-orange-500/10 border-orange-500/30" : "bg-yellow-500/10 border-yellow-500/30"}`}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <StatusBadge status={flag.severity as string} />
                          <span className="text-xs text-slate-400 bg-slate-700/50 px-2 py-0.5 rounded">{String(flag.flag_type)}</span>
                          {flag.is_resolved ? <span className="text-xs text-green-400">Resolved</span> : null}
                        </div>
                        {!flag.is_resolved && <button onClick={() => resolveFraudFlag(flag.id as string)} className="text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-3 py-1 rounded-full hover:bg-green-600/30">Resolve</button>}
                      </div>
                      <p className="text-white text-sm">{String(flag.message)}</p>
                      {flag.details ? <p className="text-slate-400 text-xs mt-1">{String(flag.details)}</p> : null}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Scheduler Tab */}
        {tab === "scheduler" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-2"><Zap className="text-yellow-400" size={22} /> Background Scheduler</h2>
            {schedulerStatus && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <div className="flex items-center gap-3 mb-4">
                  <span className={`w-3 h-3 rounded-full ${schedulerStatus.running ? "bg-green-400" : "bg-red-400"}`} />
                  <span className="text-white text-sm font-medium">{schedulerStatus.running ? "Scheduler Running" : "Scheduler Stopped"}</span>
                </div>
                <h3 className="text-md font-semibold text-white mb-3">Scheduled Jobs</h3>
                <div className="space-y-2">
                  {(schedulerStatus.jobs as Record<string, unknown>[])?.map((job) => (
                    <div key={job.id as string} className="p-4 bg-slate-700/50 rounded-lg flex items-center justify-between">
                      <div>
                        <p className="text-white text-sm font-medium">{job.name as string}</p>
                        <p className="text-slate-400 text-xs">Trigger: {job.trigger as string}</p>
                        <p className="text-slate-400 text-xs">Next run: {job.next_run ? (job.next_run as string).split(".")[0] : "N/A"}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-4">Manual Triggers</h3>
              <p className="text-slate-400 text-sm mb-4">Run scheduled jobs manually for immediate results.</p>
              <div className="grid grid-cols-3 gap-4">
                {[
                  { key: "monitoring", label: "Run Monitoring Checks", desc: "DBS updates, visa expiry, registration renewal, sanctions" },
                  { key: "expiry_warnings", label: "Send Expiry Warnings", desc: "Email notifications for expiring documents/registrations" },
                  { key: "fraud_scan", label: "Run Fraud Scan", desc: "Cross-candidate duplicate detection and pattern analysis" },
                ].map((job) => (
                  <div key={job.key} className="p-4 bg-slate-700/50 rounded-lg">
                    <p className="text-white text-sm font-medium mb-1">{job.label}</p>
                    <p className="text-slate-400 text-xs mb-3">{job.desc}</p>
                    <button onClick={() => triggerJob(job.key)} disabled={triggeringJob === job.key}
                      className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-4 py-2 rounded-lg text-xs font-medium flex items-center gap-2 w-full justify-center">
                      <Play size={14} /> {triggeringJob === job.key ? "Running..." : "Run Now"}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Subscriptions Tab */}
        {tab === "subscriptions" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-2"><CreditCard className="text-blue-400" size={22} /> Agency Subscriptions & Pricing</h2>
            <p className="text-slate-400 text-sm">Manage agency subscription tiers, pricing models, and billing methods. Click Edit on any tier to update its pricing.</p>

            {/* Editable Subscription Tiers */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-4">Subscription Plan Pricing</h3>
              <div className="grid grid-cols-2 gap-4">
                {Object.entries(subTiers).length > 0 ? Object.entries(subTiers).map(([tierKey, tier]) => {
                  const colors: Record<string, string> = { starter: "border-blue-500/30", growth: "border-green-500/30", enterprise: "border-purple-500/30", per_worker: "border-amber-500/30" };
                  const isEditing = editingTier === tierKey;
                  return (
                    <div key={tierKey} className={`p-5 bg-slate-700/50 rounded-xl border ${colors[tierKey] || "border-slate-600"}`}>
                      {isEditing ? (
                        <div className="space-y-3">
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Tier Name</label>
                            <input value={tierEditData.name} onChange={(e) => setTierEditData(prev => ({...prev, name: e.target.value}))}
                              className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="block text-xs text-slate-400 mb-1">Monthly Price (£)</label>
                              <input type="number" step="0.01" value={tierEditData.monthly_price} onChange={(e) => setTierEditData(prev => ({...prev, monthly_price: e.target.value}))}
                                className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                            </div>
                            <div>
                              <label className="block text-xs text-slate-400 mb-1">Per Worker Price (£)</label>
                              <input type="number" step="0.01" value={tierEditData.per_worker_price} onChange={(e) => setTierEditData(prev => ({...prev, per_worker_price: e.target.value}))}
                                className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                            </div>
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Max Workers</label>
                            <input type="number" value={tierEditData.max_workers} onChange={(e) => setTierEditData(prev => ({...prev, max_workers: e.target.value}))}
                              className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Features (one per line)</label>
                            <textarea value={tierEditData.features} onChange={(e) => setTierEditData(prev => ({...prev, features: e.target.value}))} rows={4}
                              className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm resize-none" />
                          </div>
                          <div className="flex gap-2">
                            <button onClick={() => saveTier(tierKey)} disabled={savingTier}
                              className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white rounded-lg py-2 text-xs font-medium border-none cursor-pointer">
                              {savingTier ? "Saving..." : "Save Changes"}
                            </button>
                            <button onClick={() => setEditingTier(null)}
                              className="flex-1 bg-slate-600 hover:bg-slate-500 text-white rounded-lg py-2 text-xs font-medium border-none cursor-pointer">
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <p className="text-white font-bold text-lg">{tier.name}</p>
                            <button onClick={() => startEditTier(tierKey)}
                              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 bg-transparent border-none cursor-pointer">
                              <Edit size={12} /> Edit
                            </button>
                          </div>
                          <p className="text-blue-400 text-xl font-bold mb-1">
                            {tier.per_worker_price > 0 ? `£${tier.per_worker_price}/worker/mo` : `£${tier.monthly_price.toLocaleString()}/mo`}
                          </p>
                          <p className="text-slate-400 text-sm mb-3">
                            {tier.max_workers >= 99999 ? "Unlimited workers" : `Up to ${tier.max_workers} workers`}
                          </p>
                          <div className="space-y-1">
                            {tier.features.map((f: string, i: number) => (
                              <p key={i} className="text-slate-300 text-xs flex items-center gap-1.5">
                                <CheckCircle size={12} className="text-green-400" /> {f}
                              </p>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                }) : (
                  <div className="col-span-2 text-center py-8 text-slate-400">
                    <p>Loading subscription tiers...</p>
                  </div>
                )}
              </div>
            </div>

            {/* Billing Methods */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-4">Billing Methods</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-slate-700/50 rounded-lg">
                  <p className="text-white font-medium mb-1">Stripe Card Payment</p>
                  <p className="text-slate-400 text-sm">Automatic monthly billing via Stripe. Agencies add a payment method and are charged automatically each billing cycle.</p>
                </div>
                <div className="p-4 bg-slate-700/50 rounded-lg">
                  <p className="text-white font-medium mb-1">Recurring Invoice</p>
                  <p className="text-slate-400 text-sm">Monthly invoices generated automatically. Agencies receive email notifications and can pay by bank transfer or other methods.</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Overrides Tab */}
        {tab === "overrides" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-2"><Edit className="text-blue-400" size={22} /> Override Check Results</h2>
            <p className="text-slate-400 text-sm">Force-pass or force-fail a candidate&apos;s individual check result. This overrides the automated result and triggers compliance re-evaluation.</p>
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-4">Override a Check</h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Candidate</label>
                  <select value={overrideCandId} onChange={(e) => { setOverrideCandId(e.target.value); if (e.target.value) loadCandidateDetail(e.target.value); }}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm">
                    <option value="">Select candidate...</option>
                    {candidates.map((c) => <option key={String(c.id)} value={String(c.id)}>{String(c.first_name)} {String(c.last_name)} ({String(c.email)})</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Check Type</label>
                  <select value={overrideCheckType} onChange={(e) => setOverrideCheckType(e.target.value)}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm">
                    {["identity","right_to_work","dbs","cv_analysis","employment","registration","references"].map((t) => <option key={t} value={t}>{t.replace(/_/g, " ").toUpperCase()}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Override Status</label>
                  <select value={overrideStatus} onChange={(e) => setOverrideStatus(e.target.value)}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm">
                    <option value="completed">Force PASS (completed)</option>
                    <option value="failed">Force FAIL (failed)</option>
                    <option value="pending">Reset to PENDING</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Notes (reason)</label>
                  <input value={overrideNotes} onChange={(e) => setOverrideNotes(e.target.value)} placeholder="Reason for override..."
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
                </div>
              </div>
              <button onClick={handleOverride} disabled={!overrideCandId || overriding}
                className="bg-amber-600 hover:bg-amber-700 disabled:bg-amber-800 disabled:opacity-50 text-white px-6 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
                <Edit size={14} /> {overriding ? "Overriding..." : "Apply Override"}
              </button>
            </div>

            {overrideCandId && candidateDetail && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4">Candidate Check Data &amp; Re-trigger Verifications</h3>
                <div className="space-y-4">
                  {candidateDetail.references && Array.isArray(candidateDetail.references) && (candidateDetail.references as Record<string, unknown>[]).length > 0 ? (
                    <div>
                      <h4 className="text-sm font-medium text-slate-300 mb-2">References</h4>
                      <div className="space-y-2">
                        {(candidateDetail.references as Record<string, unknown>[]).map((ref) => (
                          <div key={String(ref.id)} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                            <div><span className="text-white text-sm">{String(ref.referee_name)}</span> <span className="text-slate-400 text-xs">({String(ref.referee_email)})</span> <StatusBadge status={String(ref.status)} /></div>
                            <button onClick={() => handleRetriggerReference(overrideCandId, String(ref.id))} disabled={retriggeringId === String(ref.id)}
                              className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-3 py-1 rounded-full hover:bg-blue-600/30 flex items-center gap-1">
                              <Send size={12} /> {retriggeringId === String(ref.id) ? "Sending..." : "Re-trigger"}
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {candidateDetail.employment_verifications && Array.isArray(candidateDetail.employment_verifications) && (candidateDetail.employment_verifications as Record<string, unknown>[]).length > 0 ? (
                    <div>
                      <h4 className="text-sm font-medium text-slate-300 mb-2">Employment Verifications</h4>
                      <div className="space-y-2">
                        {(candidateDetail.employment_verifications as Record<string, unknown>[]).map((ver) => (
                          <div key={String(ver.id)} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                            <div><span className="text-white text-sm">{String(ver.verifier_name)}</span> <span className="text-slate-400 text-xs">({String(ver.verifier_email)})</span> <StatusBadge status={String(ver.status)} /></div>
                            <button onClick={() => handleRetriggerEmployment(overrideCandId, String(ver.id))} disabled={retriggeringId === String(ver.id)}
                              className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-3 py-1 rounded-full hover:bg-blue-600/30 flex items-center gap-1">
                              <Send size={12} /> {retriggeringId === String(ver.id) ? "Sending..." : "Re-trigger"}
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Agencies Tab - suspend/activate + discount */}
        {tab === "agencies" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-2"><Ban className="text-blue-400" size={22} /> Agency Management</h2>
            <p className="text-slate-400 text-sm">View, suspend, or reactivate agency accounts. Set per-agency discounts on vetting/monitoring costs.</p>
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full"><thead><tr className="border-b border-slate-700">
                {["Agency Name","Email","Contact","Discount","Status","Actions"].map(h => <th key={h} className="text-left text-xs text-slate-400 font-medium px-4 py-3">{h}</th>)}
              </tr></thead><tbody>
                {agencies.map((a) => (
                  <tr key={String(a.id)} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-sm text-white font-medium">{String(a.name)}</td>
                    <td className="px-4 py-3 text-sm text-slate-300">{String(a.email)}</td>
                    <td className="px-4 py-3 text-sm text-slate-300">{String(a.contact_name || "N/A")}</td>
                    <td className="px-4 py-3">
                      {editingDiscount === String(a.id) ? (
                        <div className="flex items-center gap-1">
                          <input type="number" min="0" max="100" step="0.5" value={discountValue}
                            onChange={(e) => setDiscountValue(e.target.value)}
                            className="w-16 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-xs" />
                          <span className="text-slate-400 text-xs">%</span>
                          <button onClick={() => handleSaveDiscount(String(a.id))} disabled={savingDiscount}
                            className="text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-2 py-1 rounded hover:bg-green-600/30">
                            {savingDiscount ? "..." : "Save"}
                          </button>
                          <button onClick={() => setEditingDiscount(null)}
                            className="text-xs bg-slate-600/20 text-slate-400 border border-slate-600/30 px-2 py-1 rounded hover:bg-slate-600/30">Cancel</button>
                        </div>
                      ) : (
                        <button onClick={() => { setEditingDiscount(String(a.id)); setDiscountValue(String(Number(a.discount_percent) || 0)); }}
                          className="text-xs bg-purple-600/20 text-purple-300 border border-purple-600/30 px-2 py-1 rounded hover:bg-purple-600/30">
                          {Number(a.discount_percent) > 0 ? `${Number(a.discount_percent)}%` : "Set Discount"}
                        </button>
                      )}
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={String(a.status || "active")} /></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {String(a.status) === "suspended" ? (
                          <button onClick={() => handleAgencyStatus(String(a.id), "active")} className="text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-3 py-1 rounded-full hover:bg-green-600/30">Reactivate</button>
                        ) : (
                          <button onClick={() => { const reason = prompt("Reason for suspension:"); if (reason) { setSuspendReason(reason); handleAgencyStatus(String(a.id), "suspended"); } }}
                            className="text-xs bg-red-600/20 text-red-400 border border-red-600/30 px-3 py-1 rounded-full hover:bg-red-600/30">Suspend</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {agencies.length === 0 && <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-500 text-sm">No agencies found</td></tr>}
              </tbody></table>
            </div>
          </div>
        )}

        {/* User Management Tab */}
        {tab === "user-management" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-2"><UserPlus className="text-blue-400" size={22} /> User Management</h2>
            <p className="text-slate-400 text-sm">Create and delete agency or candidate accounts. Edit candidate profiles directly.</p>

            <div className="grid grid-cols-2 gap-6">
              {/* Create Agency */}
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4 flex items-center gap-2"><PlusCircle size={16} className="text-green-400" /> Create Agency</h3>
                <div className="space-y-3">
                  <input placeholder="Agency Name" value={newAgency.name} onChange={(e) => setNewAgency({ ...newAgency, name: e.target.value })}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
                  <input placeholder="Email" value={newAgency.email} onChange={(e) => setNewAgency({ ...newAgency, email: e.target.value })}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
                  <input placeholder="Password" type="password" value={newAgency.password} onChange={(e) => setNewAgency({ ...newAgency, password: e.target.value })}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
                  <input placeholder="Contact Name" value={newAgency.contact_name} onChange={(e) => setNewAgency({ ...newAgency, contact_name: e.target.value })}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
                  <input placeholder="Phone" value={newAgency.phone} onChange={(e) => setNewAgency({ ...newAgency, phone: e.target.value })}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
                  <button onClick={handleCreateAgency} disabled={creatingUser || !newAgency.name || !newAgency.email || !newAgency.password}
                    className="w-full bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium">
                    {creatingUser ? "Creating..." : "Create Agency"}
                  </button>
                </div>
              </div>

              {/* Create Candidate */}
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4 flex items-center gap-2"><PlusCircle size={16} className="text-green-400" /> Create Candidate</h3>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <input placeholder="First Name" value={newCandidate.first_name} onChange={(e) => setNewCandidate({ ...newCandidate, first_name: e.target.value })}
                      className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
                    <input placeholder="Last Name" value={newCandidate.last_name} onChange={(e) => setNewCandidate({ ...newCandidate, last_name: e.target.value })}
                      className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
                  </div>
                  <input placeholder="Email" value={newCandidate.email} onChange={(e) => setNewCandidate({ ...newCandidate, email: e.target.value })}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
                  <input placeholder="Password" type="password" value={newCandidate.password} onChange={(e) => setNewCandidate({ ...newCandidate, password: e.target.value })}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
                  <input placeholder="Profession (e.g. Nurse, Care Worker)" value={newCandidate.profession} onChange={(e) => setNewCandidate({ ...newCandidate, profession: e.target.value })}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
                  <button onClick={handleCreateCandidate} disabled={creatingUser || !newCandidate.email || !newCandidate.password}
                    className="w-full bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium">
                    {creatingUser ? "Creating..." : "Create Candidate"}
                  </button>
                </div>
              </div>
            </div>

            {/* Existing Candidates List with Edit/Delete */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <div className="p-4 border-b border-slate-700"><h3 className="text-md font-semibold text-white">All Candidates</h3></div>
              <table className="w-full"><thead><tr className="border-b border-slate-700">
                {["Name","Email","Profession","Score","Status","Actions"].map(h => <th key={h} className="text-left text-xs text-slate-400 font-medium px-4 py-3">{h}</th>)}
              </tr></thead><tbody>
                {candidates.map((c) => (
                  <tr key={String(c.id)} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-sm text-white">{String(c.first_name)} {String(c.last_name)}</td>
                    <td className="px-4 py-3 text-sm text-slate-300">{String(c.email)}</td>
                    <td className="px-4 py-3 text-sm text-slate-300">{String(c.profession || "N/A")}</td>
                    <td className="px-4 py-3 text-sm text-white font-medium">{String(c.compliance_score || 0)}%</td>
                    <td className="px-4 py-3"><StatusBadge status={String(c.compliance_status || "incomplete")} /></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button onClick={() => { setEditingCandidate(c); setEditFields({ first_name: String(c.first_name || ""), last_name: String(c.last_name || ""), email: String(c.email || ""), phone: String(c.phone || ""), profession: String(c.profession || ""), registration_body: String(c.registration_body || ""), registration_number: String(c.registration_number || ""), date_of_birth: String(c.date_of_birth || ""), address: String(c.address || "") }); }}
                          className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"><Edit size={12} /> Edit</button>
                        <button onClick={() => handleDeleteCandidate(String(c.id))} disabled={deletingId === String(c.id)}
                          className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1"><Trash2 size={12} /> {deletingId === String(c.id) ? "..." : "Delete"}</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody></table>
            </div>

            {/* Edit Candidate Modal */}
            {editingCandidate && (
              <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
                <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
                  <h3 className="text-lg font-semibold text-white mb-4">Edit Candidate: {String(editingCandidate.first_name)} {String(editingCandidate.last_name)}</h3>
                  <div className="space-y-3">
                    {Object.entries(editFields).map(([key, val]) => (
                      <div key={key}>
                        <label className="block text-xs text-slate-400 mb-1">{key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}</label>
                        <input value={val} onChange={(e) => setEditFields({ ...editFields, [key]: e.target.value })}
                          className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
                      </div>
                    ))}
                  </div>
                  <div className="flex justify-end gap-3 mt-6">
                    <button onClick={() => { setEditingCandidate(null); setEditFields({}); }} className="px-4 py-2 text-sm text-slate-400 hover:text-white">Cancel</button>
                    <button onClick={handleSaveCandidateEdit} disabled={savingEdit}
                      className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-6 py-2 rounded-lg text-sm font-medium">
                      {savingEdit ? "Saving..." : "Save Changes"}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Existing Agencies List with Delete */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <div className="p-4 border-b border-slate-700"><h3 className="text-md font-semibold text-white">All Agencies</h3></div>
              <table className="w-full"><thead><tr className="border-b border-slate-700">
                {["Agency Name","Email","Contact","Phone","Actions"].map(h => <th key={h} className="text-left text-xs text-slate-400 font-medium px-4 py-3">{h}</th>)}
              </tr></thead><tbody>
                {agencies.map((a) => (
                  <tr key={String(a.id)} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-sm text-white font-medium">{String(a.name)}</td>
                    <td className="px-4 py-3 text-sm text-slate-300">{String(a.email)}</td>
                    <td className="px-4 py-3 text-sm text-slate-300">{String(a.contact_name || "N/A")}</td>
                    <td className="px-4 py-3 text-sm text-slate-300">{String(a.phone || "N/A")}</td>
                    <td className="px-4 py-3">
                      <button onClick={() => handleDeleteAgency(String(a.id))} disabled={deletingId === String(a.id)}
                        className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1"><Trash2 size={12} /> {deletingId === String(a.id) ? "..." : "Delete"}</button>
                    </td>
                  </tr>
                ))}
                {agencies.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500 text-sm">No agencies found</td></tr>}
              </tbody></table>
            </div>
          </div>
        )}

        {/* Audit Logs Tab */}
        {tab === "audit-logs" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-2"><History className="text-blue-400" size={22} /> Audit Log Viewer</h2>
            <p className="text-slate-400 text-sm">View all system audit logs for compliance tracking. Filter by entity type or action. Total: {auditTotal} entries.</p>
            <div className="flex items-center gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Entity Type</label>
                <select value={auditFilter.entity_type} onChange={(e) => { setAuditFilter({ ...auditFilter, entity_type: e.target.value }); setAuditPage(0); }}
                  className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm">
                  <option value="">All</option>
                  {["candidate","agency","check","compliance","alert","invoice","subscription","fraud","system"].map((t) => <option key={t} value={t}>{t.toUpperCase()}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Action</label>
                <input value={auditFilter.action} onChange={(e) => { setAuditFilter({ ...auditFilter, action: e.target.value }); setAuditPage(0); }}
                  placeholder="Filter by action..." className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
              </div>
              <div className="ml-auto flex items-center gap-2 mt-4">
                <button onClick={() => setAuditPage(Math.max(0, auditPage - 1))} disabled={auditPage === 0}
                  className="px-3 py-1.5 rounded-lg text-xs bg-slate-700/50 text-slate-300 hover:bg-slate-700 disabled:opacity-50">Prev</button>
                <span className="text-xs text-slate-400">Page {auditPage + 1}</span>
                <button onClick={() => setAuditPage(auditPage + 1)} disabled={(auditPage + 1) * 50 >= auditTotal}
                  className="px-3 py-1.5 rounded-lg text-xs bg-slate-700/50 text-slate-300 hover:bg-slate-700 disabled:opacity-50">Next</button>
              </div>
            </div>
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full"><thead><tr className="border-b border-slate-700">
                {["Timestamp","Entity Type","Entity ID","Action","Actor","Details"].map(h => <th key={h} className="text-left text-xs text-slate-400 font-medium px-4 py-3">{h}</th>)}
              </tr></thead><tbody>
                {auditLogs.map((log, idx) => (
                  <tr key={idx} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-4 py-2 text-xs text-slate-400 whitespace-nowrap">{String(log.created_at || "")}</td>
                    <td className="px-4 py-2"><span className="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded">{String(log.entity_type)}</span></td>
                    <td className="px-4 py-2 text-xs text-slate-300 font-mono">{String(log.entity_id || "").substring(0, 8)}...</td>
                    <td className="px-4 py-2 text-xs text-white">{String(log.action)}</td>
                    <td className="px-4 py-2 text-xs text-slate-300">{String(log.actor || "system")}</td>
                    <td className="px-4 py-2 text-xs text-slate-400 max-w-xs truncate">{String(log.details || "")}</td>
                  </tr>
                ))}
                {auditLogs.length === 0 && <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-500 text-sm">No audit logs found</td></tr>}
              </tbody></table>
            </div>
          </div>
        )}

        {/* Invoicing Tab */}
        {tab === "invoicing" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-2"><FileText className="text-blue-400" size={22} /> Invoice Management</h2>
            <p className="text-slate-400 text-sm">View all invoices, adjust amounts for partial completion (charge only for completed checks), and mark invoices as paid.</p>

            {/* Filter */}
            <div className="flex items-center gap-3">
              <span className="text-slate-400 text-sm">Filter:</span>
              {["all", "pending", "paid"].map((f) => (
                <button key={f} onClick={() => setInvoiceFilter(f)}
                  className={`px-3 py-1 rounded-full text-xs font-medium border ${invoiceFilter === f ? "bg-blue-600/30 text-blue-300 border-blue-500/50" : "bg-slate-700/50 text-slate-400 border-slate-600/30 hover:bg-slate-700"}`}>
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>

            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full"><thead><tr className="border-b border-slate-700">
                {["Invoice ID","Agency","Candidate","Type","Original Amount","Adjusted","Discount","Status","Actions"].map(h => <th key={h} className="text-left text-xs text-slate-400 font-medium px-3 py-3">{h}</th>)}
              </tr></thead><tbody>
                {adminInvoices
                  .filter((inv) => invoiceFilter === "all" || String(inv.status) === invoiceFilter)
                  .map((inv) => {
                    const invId = String(inv.id);
                    const originalAmt = Number(inv.sell_amount) || 0;
                    const adjustedAmt = inv.adjusted_amount != null ? Number(inv.adjusted_amount) : null;
                    const discount = Number(inv.discount_percent) || 0;
                    const isAdjusting = adjustingInvoice === invId;
                    return (
                      <tr key={invId} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                        <td className="px-3 py-3 text-xs text-slate-300 font-mono">{invId.substring(0, 8)}...</td>
                        <td className="px-3 py-3 text-sm text-white">{String(inv.agency_name || "N/A")}</td>
                        <td className="px-3 py-3 text-sm text-slate-300">{String(inv.candidate_email || "N/A")}</td>
                        <td className="px-3 py-3"><span className="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded">{String(inv.check_type || "vetting")}</span></td>
                        <td className="px-3 py-3 text-sm text-green-400 font-medium">{"\u00A3"}{originalAmt.toFixed(2)}</td>
                        <td className="px-3 py-3">
                          {isAdjusting ? (
                            <div className="space-y-1">
                              <input type="number" step="0.01" min="0" max={originalAmt} value={adjustAmount}
                                onChange={(e) => setAdjustAmount(e.target.value)}
                                className="w-24 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-xs" placeholder="Amount" />
                              <input value={adjustNotes} onChange={(e) => setAdjustNotes(e.target.value)}
                                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-xs" placeholder="Reason (e.g. 5/7 checks completed)" />
                              <div className="flex gap-1">
                                <button onClick={() => handleAdjustInvoice(invId)} disabled={savingAdjust}
                                  className="text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-2 py-1 rounded hover:bg-green-600/30">
                                  {savingAdjust ? "..." : "Save"}
                                </button>
                                <button onClick={() => setAdjustingInvoice(null)}
                                  className="text-xs bg-slate-600/20 text-slate-400 border border-slate-600/30 px-2 py-1 rounded hover:bg-slate-600/30">Cancel</button>
                              </div>
                            </div>
                          ) : adjustedAmt != null ? (
                            <div>
                              <span className="text-amber-400 text-sm font-medium">{"\u00A3"}{adjustedAmt.toFixed(2)}</span>
                              {inv.adjustment_notes ? <p className="text-slate-500 text-xs mt-0.5">{String(inv.adjustment_notes)}</p> : null}
                            </div>
                          ) : <span className="text-slate-500 text-xs">-</span>}
                        </td>
                        <td className="px-3 py-3">
                          {discount > 0 ? <span className="text-purple-300 text-xs font-medium">{discount}%</span> : <span className="text-slate-500 text-xs">-</span>}
                        </td>
                        <td className="px-3 py-3"><StatusBadge status={String(inv.status || "pending")} /></td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-1">
                            {String(inv.status) !== "paid" && (
                              <>
                                <button onClick={() => { setAdjustingInvoice(invId); setAdjustAmount(adjustedAmt != null ? String(adjustedAmt) : String(originalAmt)); setAdjustNotes(String(inv.adjustment_notes || "")); }}
                                  className="text-xs bg-amber-600/20 text-amber-400 border border-amber-600/30 px-2 py-1 rounded hover:bg-amber-600/30">Adjust</button>
                                <button onClick={() => handleMarkInvoicePaid(invId)}
                                  className="text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-2 py-1 rounded hover:bg-green-600/30">Mark Paid</button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                {adminInvoices.filter((inv) => invoiceFilter === "all" || String(inv.status) === invoiceFilter).length === 0 && (
                  <tr><td colSpan={9} className="px-4 py-6 text-center text-slate-500 text-sm">No invoices found</td></tr>
                )}
              </tbody></table>
            </div>

            {/* Summary */}
            {adminInvoices.length > 0 && (
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-4 text-center">
                  <p className="text-slate-400 text-xs mb-1">Total Invoiced</p>
                  <p className="text-green-400 font-bold text-xl">{"\u00A3"}{adminInvoices.reduce((sum, inv) => sum + (Number(inv.sell_amount) || 0), 0).toFixed(2)}</p>
                </div>
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-4 text-center">
                  <p className="text-slate-400 text-xs mb-1">Adjusted Total</p>
                  <p className="text-amber-400 font-bold text-xl">{"\u00A3"}{adminInvoices.reduce((sum, inv) => sum + (inv.adjusted_amount != null ? Number(inv.adjusted_amount) : (Number(inv.sell_amount) || 0)), 0).toFixed(2)}</p>
                </div>
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-4 text-center">
                  <p className="text-slate-400 text-xs mb-1">Paid</p>
                  <p className="text-blue-400 font-bold text-xl">{"\u00A3"}{adminInvoices.filter((inv) => String(inv.status) === "paid").reduce((sum, inv) => sum + (inv.adjusted_amount != null ? Number(inv.adjusted_amount) : (Number(inv.sell_amount) || 0)), 0).toFixed(2)}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Settings Tab */}
        {tab === "settings" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-2"><Settings className="text-blue-400" size={22} /> Pricing Configuration</h2>
            <p className="text-slate-400 text-sm">Set cost prices (what you pay) and sell prices (what agencies are charged) for each check type. Changes here affect all future invoices and revenue calculations.</p>
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full"><thead><tr className="border-b border-slate-700">
                {["Check Type","Label","Cost Price (£)","Sell Price (£)","Margin","Actions"].map(h => <th key={h} className="text-left text-xs text-slate-400 font-medium px-4 py-3">{h}</th>)}
              </tr></thead><tbody>
                {pricing.map((p) => {
                  const ct = p.check_type as string;
                  const isE = ct in editingPricing;
                  const cost = isE ? parseFloat(editingPricing[ct].cost_price) || 0 : (p.cost_price as number);
                  const sell = isE ? parseFloat(editingPricing[ct].sell_price) || 0 : (p.sell_price as number);
                  const margin = sell - cost;
                  const marginPct = sell > 0 ? Math.round((margin / sell) * 100) : 0;
                  return (
                    <tr key={ct} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                      <td className="px-4 py-3 text-sm text-slate-300 font-mono">{ct}</td>
                      <td className="px-4 py-3 text-sm text-white">{p.label as string}</td>
                      <td className="px-4 py-3">{isE ? <input type="number" step="0.01" value={editingPricing[ct].cost_price} onChange={(e) => setEditingPricing((prev) => ({ ...prev, [ct]: { ...prev[ct], cost_price: e.target.value } }))} className="w-24 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-sm" /> : <span className="text-amber-400 text-sm font-medium">£{(p.cost_price as number).toFixed(2)}</span>}</td>
                      <td className="px-4 py-3">{isE ? <input type="number" step="0.01" value={editingPricing[ct].sell_price} onChange={(e) => setEditingPricing((prev) => ({ ...prev, [ct]: { ...prev[ct], sell_price: e.target.value } }))} className="w-24 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-sm" /> : <span className="text-green-400 text-sm font-medium">£{(p.sell_price as number).toFixed(2)}</span>}</td>
                      <td className="px-4 py-3"><span className={`text-sm font-medium ${margin >= 0 ? "text-emerald-400" : "text-red-400"}`}>£{margin.toFixed(2)} ({marginPct}%)</span></td>
                      <td className="px-4 py-3">{isE ? (
                        <div className="flex gap-2">
                          <button onClick={() => savePricingItem(ct)} disabled={savingPricing === ct} className="text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-3 py-1 rounded-full hover:bg-green-600/30 disabled:opacity-50">{savingPricing === ct ? "Saving..." : "Save"}</button>
                          <button onClick={() => setEditingPricing((prev) => { const next = { ...prev }; delete next[ct]; return next; })} className="text-xs text-slate-400 hover:text-white">Cancel</button>
                        </div>
                      ) : <button onClick={() => setEditingPricing((prev) => ({ ...prev, [ct]: { cost_price: String(p.cost_price), sell_price: String(p.sell_price) } }))} className="text-xs text-blue-400 hover:text-blue-300">Edit</button>}</td>
                    </tr>
                  );
                })}
              </tbody></table>
            </div>

            {/* Alert Settings */}
            <h2 className="text-xl font-bold text-white flex items-center gap-2 mt-8"><Bell className="text-amber-400" size={22} /> Alert &amp; Expiry Warning Settings</h2>
            <p className="text-slate-400 text-sm">Configure the number of days before expiry that triggers a warning notification for each document type.</p>
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <div className="grid grid-cols-2 gap-4 mb-4">
                {[
                  { key: "visa_expiry_days", label: "Visa Expiry Warning (days)", defaultVal: 30 },
                  { key: "dbs_renewal_days", label: "DBS Renewal Warning (days)", defaultVal: 60 },
                  { key: "registration_renewal_days", label: "Registration Renewal Warning (days)", defaultVal: 30 },
                  { key: "training_expiry_days", label: "Training Certificate Expiry Warning (days)", defaultVal: 30 },
                ].map((setting) => {
                  const currentVal = alertSettings[setting.key] !== undefined ? String(alertSettings[setting.key]) : String(setting.defaultVal);
                  const isEditing = setting.key in editAlertSettings;
                  return (
                    <div key={setting.key} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                      <div>
                        <p className="text-white text-sm font-medium">{setting.label}</p>
                        <p className="text-slate-400 text-xs">Default: {setting.defaultVal} days</p>
                      </div>
                      {isEditing ? (
                        <input type="number" value={editAlertSettings[setting.key]} onChange={(e) => setEditAlertSettings({ ...editAlertSettings, [setting.key]: e.target.value })}
                          className="w-20 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-sm text-center" />
                      ) : (
                        <button onClick={() => setEditAlertSettings({ ...editAlertSettings, [setting.key]: currentVal })}
                          className="text-blue-400 hover:text-blue-300 text-sm font-medium">{currentVal} days <Edit size={12} className="inline ml-1" /></button>
                      )}
                    </div>
                  );
                })}
              </div>
              {Object.keys(editAlertSettings).length > 0 && (
                <div className="flex gap-3">
                  <button onClick={handleSaveAlertSettings} disabled={savingAlertSettings}
                    className="bg-green-600 hover:bg-green-700 disabled:bg-green-800 text-white px-6 py-2 rounded-lg text-sm font-medium">
                    {savingAlertSettings ? "Saving..." : "Save Alert Settings"}
                  </button>
                  <button onClick={() => setEditAlertSettings({})} className="text-slate-400 hover:text-white text-sm">Cancel</button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Candidate Detail */}
        {tab === "candidate-detail" && selectedCandidate && (() => {
          const detail = candidateDetail || {} as Record<string, unknown>;
          const idChecks = (detail.identity_checks || []) as Record<string, unknown>[];
          const rtwChecks = (detail.right_to_work_checks || []) as Record<string, unknown>[];
          const dbsChecks = (detail.dbs_checks || []) as Record<string, unknown>[];
          const cvAnalyses = (detail.cv_analyses || []) as Record<string, unknown>[];
          const regChecks = (detail.registration_checks || []) as Record<string, unknown>[];
          const detailRefs = (detail.references || []) as Record<string, unknown>[];
          const empHistory = (detail.employment_history || []) as Record<string, unknown>[];
          const empVerifications = (detail.employment_verifications || []) as Record<string, unknown>[];
          const trainingCerts = (detail.training_certificates || []) as Record<string, unknown>[];

          return (
          <div className="space-y-6">
            <button onClick={() => setTab("candidates")} className="text-blue-400 hover:text-blue-300 text-sm">&larr; Back</button>
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-white">{selectedCandidate.first_name as string} {selectedCandidate.last_name as string}</h2>
              <div className="flex items-center gap-3">
                <StatusBadge status={selectedCandidate.compliance_status as string} />
                <button onClick={() => evaluateCandidate(selectedCandidate.id as string)} className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-3 py-1 rounded-full hover:bg-blue-600/30">Re-evaluate</button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-6">
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-3">Details</h3>
                <div className="space-y-2 text-sm">
                  <div><span className="text-slate-400">Email:</span> <span className="text-white">{selectedCandidate.email as string}</span></div>
                  <div><span className="text-slate-400">Phone:</span> <span className="text-white">{(selectedCandidate.phone as string) || "N/A"}</span></div>
                  <div><span className="text-slate-400">Profession:</span> <span className="text-white">{(selectedCandidate.profession as string) || "N/A"}</span></div>
                  <div><span className="text-slate-400">Registration:</span> <span className="text-white">{selectedCandidate.registration_body as string} {selectedCandidate.registration_number as string}</span></div>
                  <div><span className="text-slate-400">Score:</span> <span className="text-white font-bold">{selectedCandidate.compliance_score as number}%</span></div>
                </div>
              </div>
              {candidateCompliance && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-md font-semibold text-white mb-3">Compliance Breakdown</h3>
                  <div className="space-y-2">
                    {[{ label: "Identity", key: "identity_verified" },{ label: "Right to Work", key: "right_to_work_valid" },{ label: "DBS Check", key: "dbs_valid" },{ label: "Registration", key: "registration_active" },{ label: "Employment", key: "employment_verified" },{ label: "References", key: "references_verified" },{ label: "CV Validated", key: "cv_validated" }].map((item) => (
                      <div key={item.key} className="flex items-center gap-2 p-2 bg-slate-700/50 rounded"><CheckIcon passed={candidateCompliance[item.key] as boolean} /><span className="text-slate-200 text-sm">{item.label}</span></div>
                    ))}
                  </div>
                  <div className="mt-3"><span className={`text-sm font-medium ${candidateCompliance.cqc_ready ? "text-green-400" : "text-red-400"}`}>CQC Ready: {candidateCompliance.cqc_ready ? "YES" : "NO"}</span></div>
                  {candidateCompliance.flags ? (() => {
                    let flagList: string[] = [];
                    try {
                      const raw = candidateCompliance.flags;
                      if (Array.isArray(raw)) { flagList = raw as string[]; }
                      else if (typeof raw === "string") { const parsed = JSON.parse(raw as string); flagList = Array.isArray(parsed) ? parsed : [String(raw)]; }
                      else { flagList = [String(raw)]; }
                    } catch { flagList = [String(candidateCompliance.flags)]; }
                    return flagList.length > 0 ? <div className="mt-2 p-2 bg-amber-500/10 border border-amber-500/20 rounded text-xs text-amber-300">
                      {flagList.map((flag, i) => <div key={i} className="py-0.5">• {flag}</div>)}
                    </div> : null;
                  })() : null}
                </div>
              )}
            </div>

            {/* ── Identity Verification History ── */}
            {idChecks.length > 0 && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-3">Verification History</h3>
                {idChecks.map((check) => {
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
                              {(details.document_type_label as string) || (check.document_type as string).replace(/_/g, " ")}
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

            {/* ── Right to Work History ── */}
            {rtwChecks.length > 0 && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-3">Right to Work History</h3>
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

            {/* ── DBS Check History ── */}
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

            {/* ── CV Analysis Results ── */}
            {cvAnalyses.length > 0 && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-3">CV Analysis Results</h3>
                {cvAnalyses.map((analysis) => {
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
                    <div key={analysis.id as string} className="p-4 bg-slate-700/50 rounded-lg mb-3">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <span className="text-slate-200 text-sm font-medium">Fraud Risk Score:</span>
                          <span className={`text-lg font-bold ${
                            (analysis.fraud_risk_score as number) < 0.3 ? "text-green-400" :
                            (analysis.fraud_risk_score as number) < 0.6 ? "text-amber-400" : "text-red-400"
                          }`}>{((analysis.fraud_risk_score as number) * 100).toFixed(0)}%</span>
                        </div>
                        <span className="text-xs text-slate-500">{analysis.analysed_at as string}</span>
                      </div>
                      <p className="text-slate-300 text-sm mb-3">{analysis.ai_summary as string}</p>
                      <div className="grid grid-cols-1 gap-2 text-sm">
                        <div className="p-2 bg-slate-600/50 rounded"><span className="text-slate-400">Gaps:</span> <span className="text-slate-200">{gapDisplay}</span></div>
                        <div className="p-2 bg-slate-600/50 rounded"><span className="text-slate-400">Qualifications:</span> <span className="text-slate-200">{qualDisplay}</span></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* ── Employment History ── */}
            {empHistory.length > 0 && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-3">Employment History ({empHistory.length})</h3>
                {empHistory.map((entry) => {
                  const entryId = entry.id as string;
                  const verification = empVerifications.find((v) => v.employment_id === entryId);
                  return (
                    <div key={entryId} className="p-4 bg-slate-700/50 rounded-lg mb-3">
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h4 className="text-white font-semibold text-sm">{entry.employer_name as string}</h4>
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
                        {verification && <StatusBadge status={verification.status as string} />}
                      </div>

                      {verification && (
                        <div className="mt-3 p-3 bg-slate-600/30 rounded-lg text-sm">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-slate-400">Verified by:</span>
                            <span className="text-white font-medium">{verification.verifier_name as string}</span>
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
                          <div className="mt-2">
                            <button onClick={() => handleRetriggerEmployment(selectedCandidate.id as string, verification.id as string)}
                              disabled={retriggeringId === (verification.id as string)}
                              className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-2 py-0.5 rounded hover:bg-blue-600/30">
                              {retriggeringId === (verification.id as string) ? "Re-triggering..." : "Re-trigger Verification"}
                            </button>
                          </div>
                        </div>
                      )}

                      {!verification && (
                        <div className="mt-2 p-2 bg-yellow-500/10 border border-yellow-500/20 rounded text-xs text-yellow-300">
                          No verification request sent yet
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* ── Registration Check History ── */}
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

            {/* ── References ── */}
            {detailRefs.length > 0 && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-3">References ({detailRefs.length})</h3>
                {detailRefs.map((ref) => (
                  <div key={ref.id as string} className="p-4 bg-slate-700/50 rounded-lg mb-2">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-white text-sm font-medium">{ref.referee_name as string}</span>
                      <StatusBadge status={ref.status as string} />
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div><span className="text-slate-400">Email:</span> <span className="text-slate-300">{ref.referee_email as string}</span></div>
                      <div><span className="text-slate-400">Domain Verified:</span> <span className="text-slate-300">{ref.domain_verified ? "Yes" : "No"}</span></div>
                      <div><span className="text-slate-400">Reminders:</span> <span className="text-slate-300">{ref.reminder_count as number}</span></div>
                      {ref.sentiment_score !== null && ref.sentiment_score !== undefined && (
                        <div><span className="text-slate-400">Sentiment:</span> <span className={`font-medium ${(ref.sentiment_score as number) > 0.7 ? "text-green-400" : (ref.sentiment_score as number) > 0.4 ? "text-amber-400" : "text-red-400"}`}>{((ref.sentiment_score as number) * 100).toFixed(0)}%</span></div>
                      )}
                    </div>
                    <div className="mt-2">
                      <button onClick={() => handleRetriggerReference(selectedCandidate.id as string, ref.id as string)}
                        disabled={retriggeringId === (ref.id as string)}
                        className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-2 py-0.5 rounded hover:bg-blue-600/30">
                        {retriggeringId === (ref.id as string) ? "Re-triggering..." : "Re-trigger Verification"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ── Training Certificates ── */}
            {trainingCerts.length > 0 && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-3">Training Certificates ({trainingCerts.length})</h3>
                {trainingCerts.map((cert) => (
                  <div key={cert.id as string} className="p-4 bg-slate-700/50 rounded-lg mb-2">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-white text-sm font-medium">{cert.certificate_name as string}</span>
                      <StatusBadge status={cert.status as string || "pending"} />
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div><span className="text-slate-400">Category:</span> <span className="text-slate-300">{(cert.category as string) || "N/A"}</span></div>
                      <div><span className="text-slate-400">Provider:</span> <span className="text-slate-300">{(cert.provider as string) || "N/A"}</span></div>
                      <div><span className="text-slate-400">Issued:</span> <span className="text-slate-300">{(cert.issue_date as string) || "N/A"}</span></div>
                      <div><span className="text-slate-400">Expires:</span> <span className={`${cert.expiry_date ? "text-slate-300" : "text-slate-500"}`}>{(cert.expiry_date as string) || "No expiry"}</span></div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          );
        })()}
      </main>
    </div>
  );
}
