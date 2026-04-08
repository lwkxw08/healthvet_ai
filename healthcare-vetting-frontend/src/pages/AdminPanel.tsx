import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { candidatesApi, complianceApi, monitoringApi, dashboardApi, adminApi, adminExtendedApi, fraudApi, schedulerApi, reportsApi, billingApi, benchmarkingApi, industryTemplatesApi, trustidApi, checksApi } from "../api/client";
import LeadGenerationPanel from "./LeadGenerationPanel";
import SubscriptionPlansPanel from "./SubscriptionPlansPanel";
import EmailTemplatesPanel from "./EmailTemplatesPanel";
import EmailRulesPanel from "./EmailRulesPanel";
import EmailConfigPanel from "./EmailConfigPanel";
import AnalyticsDashboard from "./AnalyticsDashboard";
import WebhookDeliveryDashboard from "./WebhookDeliveryDashboard";
import AuditReportingPanel from "./AuditReportingPanel";
import BackgroundJobsMonitor from "./BackgroundJobsMonitor";
import PaymentProvidersPanel from "./PaymentProvidersPanel";
import AIInsightsPanel from "./AIInsightsPanel";
import {
  Shield, CheckCircle, XCircle, Clock, AlertTriangle, Users,
  BarChart3, Bell, LogOut, RefreshCw, Eye, Play, Settings,
  DollarSign, FileText, TrendingUp, ShieldAlert, Zap, Download, CreditCard,
  Edit, Trash2, UserPlus, Ban, History, Send, PlusCircle, Building2,
} from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend, BarChart, Bar, XAxis, YAxis } from "recharts";

type MainTab = "overview" | "candidates" | "agencies" | "compliance" | "user-management" | "audit-logs" | "settings" | "lead-generation" | "operations";
type SubTab = string;

export default function AdminPanel() {
  const { token, logout } = useAuth();
  const [mainTab, setMainTab] = useState<MainTab>("overview");
  const [subTab, setSubTab] = useState<SubTab>("dashboard");

  // Keep legacy tab variable for content rendering compatibility
  const tab = (() => {
    if (mainTab === "overview") {
      if (subTab === "analytics") return "analytics";
      if (subTab === "benchmarking") return "benchmarking";
      return "overview";
    }
    if (mainTab === "candidates") {
      if (subTab === "candidate-detail") return "candidate-detail";
      return "candidates";
    }
    if (mainTab === "agencies") {
      if (subTab === "invoicing") return "invoicing";
      if (subTab === "subscriptions") return "subscriptions";
      return "agencies";
    }
    if (mainTab === "compliance") {
      if (subTab === "monitoring") return "monitoring";
      if (subTab === "fraud") return "fraud";
      if (subTab === "scheduler") return "scheduler";
      return "alerts";
    }
    if (mainTab === "user-management") {
      if (subTab === "overrides") return "overrides";
      return "user-management";
    }
    if (mainTab === "lead-generation") return "lead-generation";
    if (mainTab === "operations") {
      if (subTab === "analytics-dashboard") return "analytics-dashboard";
      if (subTab === "webhook-dashboard") return "webhook-dashboard";
      if (subTab === "audit-reporting") return "audit-reporting";
      if (subTab === "jobs-monitor") return "jobs-monitor";
      return "analytics-dashboard";
    }
    return mainTab;
  })();

  const switchMainTab = (mt: MainTab) => {
    setMainTab(mt);
    // Set default sub-tab for each main tab
    const defaults: Record<MainTab, string> = {
      "overview": "dashboard",
      "candidates": "list",
      "agencies": "list",
      "compliance": "alerts",
      "user-management": "users",
      "audit-logs": "logs",
      "settings": "pricing",
      "lead-generation": "scrape",
      "operations": "analytics-dashboard",
    };
    setSubTab(defaults[mt]);
  };
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
  const [pushToIndustriesPrompt, setPushToIndustriesPrompt] = useState<string | null>(null);
  const [pushingToIndustries, setPushingToIndustries] = useState(false);

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
  const [subTiers, setSubTiers] = useState<Record<string, {name: string; monthly_price: number; per_worker_price: number; max_workers: number; monthly_checks: number; overage_rate: number; allow_rollover: boolean; features: string[]}>>({});
  const [editingTier, setEditingTier] = useState<string | null>(null);
  const [tierEditData, setTierEditData] = useState<{name: string; monthly_price: string; per_worker_price: string; max_workers: string; monthly_checks: string; overage_rate: string; allow_rollover: boolean; features: string}>({name: "", monthly_price: "", per_worker_price: "", max_workers: "", monthly_checks: "", overage_rate: "", allow_rollover: false, features: ""});
  const [savingTier, setSavingTier] = useState(false);
  const [creatingTier, setCreatingTier] = useState(false);
  const [newTierData, setNewTierData] = useState<{tier_key: string; name: string; monthly_price: string; per_worker_price: string; max_workers: string; monthly_checks: string; overage_rate: string; allow_rollover: boolean; features: string}>({tier_key: "", name: "", monthly_price: "", per_worker_price: "0", max_workers: "999", monthly_checks: "", overage_rate: "", allow_rollover: false, features: ""});
  // Partial credit rates state
  const [creditRates, setCreditRates] = useState<Record<string, unknown>[]>([]);
  const [editingRate, setEditingRate] = useState<string | null>(null);
  const [rateEditData, setRateEditData] = useState<{label: string; credit_value: string; third_party_cost: string}>({label: "", credit_value: "", third_party_cost: ""});

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
  const [invoiceAgencyFilter, setInvoiceAgencyFilter] = useState("");
  const [invoiceTypeFilter, setInvoiceTypeFilter] = useState("");
  const [invoiceSearch, setInvoiceSearch] = useState("");

  // Grouped invoice generation state
  const [groupedAgencyId, setGroupedAgencyId] = useState("");
  const [groupedDateFrom, setGroupedDateFrom] = useState("");
  const [groupedDateTo, setGroupedDateTo] = useState("");
  const [generatingGrouped, setGeneratingGrouped] = useState(false);
  const [groupedResult, setGroupedResult] = useState<Record<string, unknown> | null>(null);

  // Invoicing tab generate state
  const [invTabAgencyId, setInvTabAgencyId] = useState("");
  const [invTabDateFrom, setInvTabDateFrom] = useState("");
  const [invTabDateTo, setInvTabDateTo] = useState("");
  const [invTabGenerating, setInvTabGenerating] = useState(false);

  // Send invoice email state
  const [sendingInvoiceEmail, setSendingInvoiceEmail] = useState(false);
  const [selectedInvoiceIds, setSelectedInvoiceIds] = useState<string[]>([]);

  // Invoice settings state
  const [invoiceSettings, setInvoiceSettings] = useState<Record<string, string>>({});
  const [editInvoiceSettings, setEditInvoiceSettings] = useState<Record<string, string>>({});
  const [savingInvoiceSettings, setSavingInvoiceSettings] = useState(false);
  const [invoiceSettingsLoaded, setInvoiceSettingsLoaded] = useState(false);

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

  // Benchmarking state
  const [benchmarkData, setBenchmarkData] = useState<Record<string, unknown> | null>(null);
  const [, setBenchmarkTrends] = useState<Record<string, unknown> | null>(null);
  const [loadingBenchmark, setLoadingBenchmark] = useState(false);

  // Industry Templates state
  const [indTemplates, setIndTemplates] = useState<Record<string, unknown>[]>([]);
  const [editingTemplate, setEditingTemplate] = useState<Record<string, unknown> | null>(null);
  const [templateChecks, setTemplateChecks] = useState<Record<string, unknown>[]>([]);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [cloningTemplate, setCloningTemplate] = useState("");
  const [assigningAgency, setAssigningAgency] = useState<string | null>(null);
  const [assignTemplateId, setAssignTemplateId] = useState("");

  // TrustID state
  const [trustidConfig, setTrustidConfig] = useState<Record<string, Record<string, unknown>>>({});
  const [trustidTasks, setTrustidTasks] = useState<Record<string, unknown>[]>([]);
  const [trustidSummary, setTrustidSummary] = useState<Record<string, unknown>>({});
  const [trustidMarkingId, setTrustidMarkingId] = useState<string | null>(null);
  const [trustidMarkRef, setTrustidMarkRef] = useState("");
  const [trustidMarkNotes, setTrustidMarkNotes] = useState("");
  const [trustidResultId, setTrustidResultId] = useState<string | null>(null);
  const [trustidResultValue, setTrustidResultValue] = useState("pass");
  const [trustidResultRef, setTrustidResultRef] = useState("");
  const [trustidResultNotes, setTrustidResultNotes] = useState("");
  const [savingTrustid, setSavingTrustid] = useState(false);
  const [trustidTaskFilter, setTrustidTaskFilter] = useState("");

  const loadBenchmarkData = useCallback(async () => {
    if (!token) return;
    setLoadingBenchmark(true);
    try {
      const [agencies, trends] = await Promise.all([
        benchmarkingApi.getAgencyBenchmarks(token),
        benchmarkingApi.getTrends(token),
      ]);
      setBenchmarkData(agencies);
      setBenchmarkTrends(trends);
    } catch { /* ignore */ }
    finally { setLoadingBenchmark(false); }
  }, [token]);

  useEffect(() => { if (tab === "benchmarking") loadBenchmarkData(); }, [tab, loadBenchmarkData]);

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
      setSubTiers(tiers as Record<string, {name: string; monthly_price: number; per_worker_price: number; max_workers: number; monthly_checks: number; overage_rate: number; allow_rollover: boolean; features: string[]}>);
    } catch { /* ignore */ }
  };

  const loadCreditRates = async () => {
    if (!token) return;
    try { const rates = await billingApi.getPartialCreditRates(token); setCreditRates(rates); } catch { /* ignore */ }
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

  const loadIndustryTemplates = useCallback(async () => {
    if (!token) return;
    try { const data = await industryTemplatesApi.list(token); setIndTemplates(data); } catch { /* ignore */ }
  }, [token]);

  const loadTrustidData = useCallback(async () => {
    if (!token) return;
    try {
      const [config, tasks, summary] = await Promise.all([
        trustidApi.getConfig(token),
        trustidApi.getAdminTasks(token, trustidTaskFilter || undefined).catch(() => []),
        trustidApi.getTaskSummary(token).catch(() => ({})),
      ]);
      setTrustidConfig(config);
      setTrustidTasks(tasks);
      setTrustidSummary(summary);
    } catch { /* ignore */ }
  }, [token, trustidTaskFilter]);

  const handleTrustidMarkSubmitted = async () => {
    if (!token || !trustidMarkingId) return;
    setSavingTrustid(true);
    try {
      await trustidApi.adminMarkSubmitted(token, { check_id: trustidMarkingId, trustid_reference: trustidMarkRef || undefined, notes: trustidMarkNotes || undefined });
      showMessage("Check marked as submitted to TrustID");
      setTrustidMarkingId(null); setTrustidMarkRef(""); setTrustidMarkNotes("");
      await loadTrustidData();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setSavingTrustid(false); }
  };

  const handleTrustidRecordResult = async () => {
    if (!token || !trustidResultId) return;
    setSavingTrustid(true);
    try {
      await trustidApi.adminRecordResult(token, { check_id: trustidResultId, result: trustidResultValue, trustid_reference: trustidResultRef || undefined, notes: trustidResultNotes || undefined });
      showMessage("TrustID result recorded successfully");
      setTrustidResultId(null); setTrustidResultValue("pass"); setTrustidResultRef(""); setTrustidResultNotes("");
      await loadTrustidData();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setSavingTrustid(false); }
  };

  const handleTrustidModeToggle = async (checkType: string, newMode: string) => {
    if (!token) return;
    try {
      await trustidApi.updateConfig(token, { check_type: checkType, submission_mode: newMode });
      showMessage(`${checkType.replace(/_/g, " ")} switched to ${newMode} mode`);
      await loadTrustidData();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  useEffect(() => { if (tab === "fraud") loadFraudData(); }, [tab, loadFraudData]);
  useEffect(() => { if (tab === "scheduler") loadSchedulerStatus(); }, [tab, loadSchedulerStatus]);
  useEffect(() => { if (tab === "settings") { loadPricing(); loadAlertSettings(); loadIndustryTemplates(); } }, [tab, loadPricing, loadAlertSettings, loadIndustryTemplates]);
  useEffect(() => { if (tab === "analytics") loadAnalytics(); }, [tab, loadAnalytics]);
  useEffect(() => { if (tab === "monitoring") { loadMonitoringRevenue(); loadMonitoringCandidates(); } }, [tab, loadMonitoringRevenue, loadMonitoringCandidates]);
  useEffect(() => { if (tab === "agencies" || tab === "user-management" || tab === "invoicing") { loadAgencies(); loadIndustryTemplates(); } }, [tab, loadAgencies, loadIndustryTemplates]);
  useEffect(() => { if (tab === "audit-logs") loadAuditLogs(); }, [tab, loadAuditLogs]);
  useEffect(() => { if (tab === "invoicing") loadAdminInvoices(); }, [tab, loadAdminInvoices]);
  useEffect(() => { if (tab === "subscriptions") { loadSubscriptionTiers(); loadCreditRates(); } }, [tab]);
  useEffect(() => { if (mainTab === "settings" && subTab === "trustid") loadTrustidData(); }, [mainTab, subTab, loadTrustidData]);
  const showMessage = (msg: string) => { setMessage(msg); setTimeout(() => setMessage(""), 4000); };

  const viewCandidate = async (candidate: Record<string, unknown>) => {
    setSelectedCandidate(candidate); setMainTab("candidates"); setSubTab("candidate-detail");
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
      setPushToIndustriesPrompt(checkType);
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setSavingPricing(""); }
  };

  const pushToAllIndustries = async (checkType: string) => {
    if (!token) return;
    setPushingToIndustries(true);
    try {
      const result = await adminApi.pushPricingToIndustries(token, checkType);
      const updated = (result as Record<string, unknown>).updated || 0;
      showMessage(`Updated ${updated} industry pricing row${updated !== 1 ? "s" : ""} for ${checkType}`);
      setPushToIndustriesPrompt(null);
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setPushingToIndustries(false); }
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
        monthly_checks: parseInt(tierEditData.monthly_checks) || 0,
        overage_rate: parseFloat(tierEditData.overage_rate) || 0,
        allow_rollover: tierEditData.allow_rollover,
        features,
      });
      setEditingTier(null);
      await loadSubscriptionTiers();
      showMessage("Tier pricing updated successfully");
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed to save tier"}`);
    } finally {
      setSavingTier(false);
    }
  };

  const createNewTier = async () => {
    if (!token) return;
    setSavingTier(true);
    try {
      const features = newTierData.features.split("\n").map(f => f.trim()).filter(f => f.length > 0);
      await billingApi.createTier(token, {
        tier_key: newTierData.tier_key,
        name: newTierData.name,
        monthly_price: parseFloat(newTierData.monthly_price) || 0,
        per_worker_price: parseFloat(newTierData.per_worker_price) || 0,
        max_workers: parseInt(newTierData.max_workers) || 999,
        monthly_checks: parseInt(newTierData.monthly_checks) || 0,
        overage_rate: parseFloat(newTierData.overage_rate) || 0,
        allow_rollover: newTierData.allow_rollover,
        features,
      });
      setCreatingTier(false);
      setNewTierData({tier_key: "", name: "", monthly_price: "", per_worker_price: "0", max_workers: "999", monthly_checks: "", overage_rate: "", allow_rollover: false, features: ""});
      await loadSubscriptionTiers();
      showMessage("New tier created successfully");
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed to create tier"}`);
    } finally {
      setSavingTier(false);
    }
  };

  const deleteTier = async (tierKey: string) => {
    if (!token || !confirm(`Delete tier "${tierKey}"? This will deactivate it.`)) return;
    try {
      await billingApi.deleteTier(token, tierKey);
      await loadSubscriptionTiers();
      showMessage("Tier deactivated successfully");
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed to delete tier"}`);
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
      monthly_checks: (tier.monthly_checks || 0).toString(),
      overage_rate: (tier.overage_rate || 0).toString(),
      allow_rollover: tier.allow_rollover || false,
      features: tier.features.join("\n"),
    });
  };

  const saveCreditRate = async (checkType: string) => {
    if (!token) return;
    try {
      await billingApi.updatePartialCreditRate(token, checkType, {
        label: rateEditData.label,
        credit_value: parseFloat(rateEditData.credit_value) || 0,
        third_party_cost: parseFloat(rateEditData.third_party_cost) || 0,
      });
      setEditingRate(null);
      await loadCreditRates();
      showMessage("Credit rate updated");
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed to save rate"}`);
    }
  };

  const handleRetriggerEmployment = async (candidateId: string, verId: string) => {
    if (!token) return;
    setRetriggeringId(verId);
    try {
      await adminExtendedApi.retriggerEmployment(token, candidateId, verId);
      showMessage("Employment verification re-triggered");
      loadCandidateDetail(candidateId);
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setRetriggeringId(""); }
  };

  const handleSendEmploymentVerification = async (candidateId: string, employmentId: string, verifierName: string, verifierEmail: string, verifierJobTitle?: string) => {
    if (!token) return;
    setRetriggeringId(employmentId);
    try {
      await checksApi.sendEmploymentVerification(token, {
        candidate_id: candidateId,
        employment_id: employmentId,
        verifier_name: verifierName,
        verifier_email: verifierEmail,
        verifier_job_title: verifierJobTitle,
      });
      showMessage("Employment verification request sent");
      loadCandidateDetail(candidateId);
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed to send verification"}`); }
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

  const handleBillingModeChange = async (agencyId: string, newMode: string) => {
    if (!token) return;
    try {
      await adminExtendedApi.updateAgencyBillingMode(token, agencyId, newMode);
      showMessage(`Billing mode updated to ${newMode.replace(/_/g, " ")}`);
      loadAgencies();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const handleSendReminders = async () => {
    if (!token) return;
    try {
      const result = await adminExtendedApi.sendPaymentReminders(token);
      const count = (result as Record<string, unknown>).reminders_sent as number;
      showMessage(`${count} payment reminder(s) sent`);
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
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

  const handleSaveTemplate = async () => {
    if (!token || !editingTemplate) return;
    setSavingTemplate(true);
    try {
      const payload = {
        name: editingTemplate.name,
        description: editingTemplate.description,
        compliance_label: editingTemplate.compliance_label || "Compliant",
        compliance_threshold: Number(editingTemplate.compliance_threshold) || 95,
        checks: templateChecks.map((c) => ({
          check_key: c.check_key,
          check_label: c.check_label,
          is_required: c.is_required ?? true,
          is_enabled: c.is_enabled ?? true,
          weight: Number(c.weight) || 10,
          config: typeof c.config === "string" ? JSON.parse(c.config as string || "{}") : (c.config || {}),
          sort_order: Number(c.sort_order) || 0,
        })),
      };
      if (editingTemplate.id) {
        await industryTemplatesApi.update(token, editingTemplate.id as string, payload);
        showMessage("Template updated");
      } else {
        await industryTemplatesApi.create(token, payload);
        showMessage("Template created");
      }
      setEditingTemplate(null);
      setTemplateChecks([]);
      loadIndustryTemplates();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setSavingTemplate(false); }
  };

  const handleCloneTemplate = async (templateId: string) => {
    if (!token) return;
    setCloningTemplate(templateId);
    try {
      await industryTemplatesApi.clone(token, templateId);
      showMessage("Template cloned");
      loadIndustryTemplates();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setCloningTemplate(""); }
  };

  const handleDeleteTemplate = async (templateId: string) => {
    if (!token) return;
    if (!confirm("Delete this template? Only possible if no agencies are using it.")) return;
    try {
      await industryTemplatesApi.remove(token, templateId);
      showMessage("Template deleted");
      loadIndustryTemplates();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const handleAssignTemplate = async (agencyId: string, templateId: string) => {
    if (!token || !agencyId || !templateId) return;
    try {
      await industryTemplatesApi.assignToAgency(token, agencyId, templateId);
      showMessage("Industry template assigned to agency");
      setAssigningAgency(null);
      loadAgencies();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const startEditTemplate = (tmpl: Record<string, unknown>) => {
    setEditingTemplate({ ...tmpl });
    const checks = (tmpl.checks || []) as Record<string, unknown>[];
    setTemplateChecks(checks.map((c) => ({ ...c })));
  };

  const startNewTemplate = () => {
    setEditingTemplate({ name: "", description: "", compliance_label: "Compliant", compliance_threshold: 95 });
    setTemplateChecks([
      { check_key: "identity_verified", check_label: "Identity Verification", is_required: true, is_enabled: true, weight: 13, config: {}, sort_order: 1 },
      { check_key: "right_to_work_valid", check_label: "Right to Work", is_required: true, is_enabled: true, weight: 13, config: {}, sort_order: 2 },
      { check_key: "dbs_valid", check_label: "DBS Check", is_required: true, is_enabled: true, weight: 17, config: {}, sort_order: 3 },
      { check_key: "dbs_standard", check_label: "Standard DBS Check", is_required: false, is_enabled: false, weight: 5, config: {}, sort_order: 4 },
      { check_key: "dbs_enhanced", check_label: "Enhanced DBS Check", is_required: false, is_enabled: false, weight: 5, config: {}, sort_order: 5 },
      { check_key: "dbs_enhanced_barred", check_label: "Enhanced DBS + Barred List", is_required: false, is_enabled: false, weight: 5, config: {}, sort_order: 6 },
      { check_key: "employment_verified", check_label: "Employment Verification", is_required: true, is_enabled: true, weight: 13, config: {}, sort_order: 7 },
      { check_key: "references_verified", check_label: "References", is_required: true, is_enabled: true, weight: 13, config: {}, sort_order: 8 },
      { check_key: "registration_active", check_label: "Professional Registration", is_required: false, is_enabled: true, weight: 9, config: {}, sort_order: 9 },
      { check_key: "cv_validated", check_label: "CV Validation", is_required: false, is_enabled: true, weight: 5, config: {}, sort_order: 10 },
      { check_key: "training_compliant", check_label: "Training Compliance", is_required: true, is_enabled: true, weight: 12, config: {}, sort_order: 11 },
      { check_key: "overseas_criminal_check", check_label: "Overseas Criminal Record Check", is_required: false, is_enabled: false, weight: 5, config: {}, sort_order: 12 },
      { check_key: "professional_registration_check", check_label: "Professional Registration (NMC/GMC/HCPC)", is_required: false, is_enabled: false, weight: 5, config: {}, sort_order: 13 },
      { check_key: "occupational_health_check", check_label: "Occupational Health Check", is_required: false, is_enabled: false, weight: 5, config: {}, sort_order: 14 },
      { check_key: "training_verification", check_label: "Training Certificate Verification", is_required: false, is_enabled: false, weight: 5, config: {}, sort_order: 15 },
      { check_key: "sanctions_check", check_label: "Sanctions & Barred List Check", is_required: false, is_enabled: false, weight: 5, config: {}, sort_order: 16 },
      { check_key: "credit_check", check_label: "Credit Check", is_required: false, is_enabled: false, weight: 3, config: {}, sort_order: 17 },
      { check_key: "social_media_check", check_label: "Social Media Check", is_required: false, is_enabled: false, weight: 3, config: {}, sort_order: 18 },
      { check_key: "counterterrorism_check", check_label: "Counter-Terrorism Check", is_required: false, is_enabled: false, weight: 5, config: {}, sort_order: 19 },
    ]);
  };

  const loadInvoiceSettings = useCallback(async () => {
    if (!token) return;
    try {
      const s = await adminApi.getInvoiceSettings(token);
      setInvoiceSettings(s);
      setEditInvoiceSettings(s);
      setInvoiceSettingsLoaded(true);
    } catch { /* ignore */ }
  }, [token]);

  const handleSaveInvoiceSettings = async () => {
    if (!token) return;
    setSavingInvoiceSettings(true);
    try {
      const updated = await adminApi.updateInvoiceSettings(token, editInvoiceSettings);
      setInvoiceSettings(updated);
      setEditInvoiceSettings(updated);
      showMessage("Invoice settings saved successfully");
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed to save"}`); }
    finally { setSavingInvoiceSettings(false); }
  };

  const handleSendInvoiceEmail = async (invoiceIds: string[]) => {
    if (!token || invoiceIds.length === 0) return;
    setSendingInvoiceEmail(true);
    try {
      const result = await adminApi.sendInvoiceEmail(token, invoiceIds);
      showMessage(`Invoice email sent to agency (${(result as Record<string, unknown>).invoice_ref} — ${(result as Record<string, unknown>).total_due})`);
      setSelectedInvoiceIds([]);
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed to send invoice email"}`); }
    finally { setSendingInvoiceEmail(false); }
  };

  const toggleInvoiceSelection = (invId: string) => {
    setSelectedInvoiceIds(prev => prev.includes(invId) ? prev.filter(id => id !== invId) : [...prev, invId]);
  };

  useEffect(() => { if (mainTab === "settings" && subTab === "invoice-settings" && !invoiceSettingsLoaded) loadInvoiceSettings(); }, [mainTab, subTab, invoiceSettingsLoaded, loadInvoiceSettings]);

  const handleGenerateGroupedInvoice = async (agencyId: string, dateFrom: string, dateTo: string, setLoading: (v: boolean) => void) => {
    if (!token || !agencyId || !dateFrom || !dateTo) { showMessage("Error: Please select an agency and date range"); return; }
    setLoading(true);
    try {
      const result = await adminApi.generateGroupedInvoices(token, agencyId, dateFrom, dateTo);
      const gen = (result as Record<string, unknown>).generated as number;
      setGroupedResult(result as Record<string, unknown>);
      showMessage(`Generated ${gen} itemised invoice line items for ${(result as Record<string, unknown>).agency}`);
      await Promise.all([loadAnalytics(), loadAdminInvoices()]);
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
    finally { setLoading(false); }
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

      {/* Main Navigation — 7 tabs */}
      <div className="bg-slate-800/50 border-b border-slate-700 px-6">
        <div className="flex gap-1 overflow-x-auto">
          {([
            { key: "overview" as MainTab, label: "Overview", icon: <BarChart3 size={16} /> },
            { key: "candidates" as MainTab, label: "Candidates", icon: <Users size={16} /> },
            { key: "agencies" as MainTab, label: "Agencies & Billing", icon: <DollarSign size={16} /> },
            { key: "compliance" as MainTab, label: "Compliance", icon: <ShieldAlert size={16} /> },
            { key: "user-management" as MainTab, label: "User Management", icon: <UserPlus size={16} /> },
            { key: "audit-logs" as MainTab, label: "Audit Logs", icon: <History size={16} /> },
            { key: "operations" as MainTab, label: "Operations", icon: <Play size={16} /> },
            { key: "lead-generation" as MainTab, label: "Lead Generation", icon: <Zap size={16} /> },
            { key: "settings" as MainTab, label: "Settings", icon: <Settings size={16} /> },
          ]).map((item) => (
            <button key={item.key} onClick={() => switchMainTab(item.key)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-all whitespace-nowrap ${mainTab === item.key ? "text-blue-400 border-blue-400" : "text-slate-400 border-transparent hover:text-white"}`}>
              {item.icon} {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Sub-tab navigation — contextual per main tab */}
      {mainTab === "overview" && (
        <div className="bg-slate-800/30 border-b border-slate-700/50 px-6">
          <div className="flex gap-1">
            {[{ key: "dashboard", label: "Dashboard" }, { key: "analytics", label: "Analytics" }, { key: "benchmarking", label: "Benchmarking" }].map((s) => (
              <button key={s.key} onClick={() => setSubTab(s.key)}
                className={`px-4 py-2 text-xs font-medium border-b-2 transition-all ${subTab === s.key ? "text-blue-300 border-blue-400" : "text-slate-500 border-transparent hover:text-slate-300"}`}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}
      {mainTab === "agencies" && (
        <div className="bg-slate-800/30 border-b border-slate-700/50 px-6">
          <div className="flex gap-1">
            {[{ key: "list", label: "Agency List" }, { key: "invoicing", label: "Invoicing" }, { key: "subscriptions", label: "Credit Packs" }].map((s) => (
              <button key={s.key} onClick={() => setSubTab(s.key)}
                className={`px-4 py-2 text-xs font-medium border-b-2 transition-all ${subTab === s.key ? "text-blue-300 border-blue-400" : "text-slate-500 border-transparent hover:text-slate-300"}`}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}
      {mainTab === "compliance" && (
        <div className="bg-slate-800/30 border-b border-slate-700/50 px-6">
          <div className="flex gap-1">
            {[{ key: "alerts", label: `Alerts (${alerts.length})` }, { key: "monitoring", label: "Monitoring" }, { key: "fraud", label: "Fraud Detection" }, { key: "scheduler", label: "Scheduler" }].map((s) => (
              <button key={s.key} onClick={() => setSubTab(s.key)}
                className={`px-4 py-2 text-xs font-medium border-b-2 transition-all ${subTab === s.key ? "text-blue-300 border-blue-400" : "text-slate-500 border-transparent hover:text-slate-300"}`}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}
      {mainTab === "settings" && (
        <div className="bg-slate-800/30 border-b border-slate-700/50 px-6">
          <div className="flex gap-1">
            {[{ key: "pricing", label: "Pricing" }, { key: "templates", label: "Industry Templates" }, { key: "industry-plans", label: "Industry Plans" }, { key: "trustid", label: "TrustID" }, { key: "alerts-config", label: "Alert Settings" }, { key: "invoice-settings", label: "Invoice Settings" }, { key: "email-templates", label: "Email Templates" }, { key: "email-rules", label: "Email Rules" }, { key: "email-config", label: "Email Provider" }, { key: "payment-providers", label: "Payment Providers" }].map((s) => (
              <button key={s.key} onClick={() => setSubTab(s.key)}
                className={`px-4 py-2 text-xs font-medium border-b-2 transition-all ${subTab === s.key ? "text-blue-300 border-blue-400" : "text-slate-500 border-transparent hover:text-slate-300"}`}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}
      {mainTab === "user-management" && (
        <div className="bg-slate-800/30 border-b border-slate-700/50 px-6">
          <div className="flex gap-1">
            {[{ key: "users", label: "Users" }, { key: "overrides", label: "Overrides" }].map((s) => (
              <button key={s.key} onClick={() => setSubTab(s.key)}
                className={`px-4 py-2 text-xs font-medium border-b-2 transition-all ${subTab === s.key ? "text-blue-300 border-blue-400" : "text-slate-500 border-transparent hover:text-slate-300"}`}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}
      {mainTab === "operations" && (
        <div className="bg-slate-800/30 border-b border-slate-700/50 px-6">
          <div className="flex gap-1">
            {[{ key: "analytics-dashboard", label: "Analytics & Reporting" }, { key: "webhook-dashboard", label: "Webhook Delivery" }, { key: "audit-reporting", label: "Audit Trail & Compliance" }, { key: "jobs-monitor", label: "Background Jobs" }, { key: "ai-insights", label: "AI Insights" }].map((s) => (
              <button key={s.key} onClick={() => setSubTab(s.key)}
                className={`px-4 py-2 text-xs font-medium border-b-2 transition-all ${subTab === s.key ? "text-blue-300 border-blue-400" : "text-slate-500 border-transparent hover:text-slate-300"}`}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <main className="p-6">
        {/* Lead Generation Tab */}
        {tab === "lead-generation" && <LeadGenerationPanel />}

        {/* Industry Plans Sub-tab under Settings */}
        {mainTab === "settings" && subTab === "industry-plans" && <SubscriptionPlansPanel />}

        {/* Email Templates Sub-tab under Settings */}
        {mainTab === "settings" && subTab === "email-templates" && <EmailTemplatesPanel />}

        {/* Email Rules Sub-tab under Settings */}
        {mainTab === "settings" && subTab === "email-rules" && <EmailRulesPanel />}

        {/* Email Config Sub-tab under Settings */}
        {mainTab === "settings" && subTab === "email-config" && <EmailConfigPanel />}

        {/* Payment Providers Sub-tab under Settings */}
        {mainTab === "settings" && subTab === "payment-providers" && <PaymentProvidersPanel />}

        {/* TrustID Sub-tab under Settings */}
        {mainTab === "settings" && subTab === "trustid" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-white">TrustID Integration</h2>
              <button onClick={loadTrustidData} className="text-slate-400 hover:text-white"><RefreshCw size={16} /></button>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-5 gap-4">
              {[
                { label: "Pending Admin", value: trustidSummary.pending_admin ?? 0, color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/30" },
                { label: "Awaiting Candidate", value: trustidSummary.awaiting_candidate ?? 0, color: "text-yellow-400", bg: "bg-yellow-500/10 border-yellow-500/30" },
                { label: "Submitted to TrustID", value: trustidSummary.submitted_to_trustid ?? 0, color: "text-blue-400", bg: "bg-blue-500/10 border-blue-500/30" },
                { label: "Completed", value: trustidSummary.completed ?? 0, color: "text-green-400", bg: "bg-green-500/10 border-green-500/30" },
                { label: "Overdue (>24h)", value: trustidSummary.overdue ?? 0, color: "text-red-400", bg: "bg-red-500/10 border-red-500/30" },
              ].map((card) => (
                <div key={card.label} className={`rounded-xl border p-4 ${card.bg}`}>
                  <p className="text-xs text-slate-400 mb-1">{card.label}</p>
                  <p className={`text-2xl font-bold ${card.color}`}>{String(card.value)}</p>
                </div>
              ))}
            </div>

            {/* Mode Toggle Per Check Type */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-lg font-semibold text-white mb-4">Submission Mode per Check Type</h3>
              <p className="text-slate-400 text-sm mb-4">Toggle between manual (admin submits via TrustID portal) and API (automated) mode for each check type.</p>
              <div className="space-y-3">
                {Object.entries(trustidConfig).map(([checkType, cfg]) => (
                  <div key={checkType} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                    <div>
                      <span className="text-white font-medium">{(cfg.label as string) || checkType.replace(/_/g, " ")}</span>
                      <span className={`ml-3 text-xs px-2 py-0.5 rounded-full ${cfg.submission_mode === "manual" ? "bg-orange-500/20 text-orange-400 border border-orange-500/30" : "bg-green-500/20 text-green-400 border border-green-500/30"}`}>
                        {(cfg.submission_mode as string)?.toUpperCase()}
                      </span>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => handleTrustidModeToggle(checkType, "manual")}
                        className={`px-3 py-1.5 rounded text-xs font-medium ${cfg.submission_mode === "manual" ? "bg-orange-600 text-white" : "bg-slate-600 text-slate-400 hover:text-white"}`}>
                        Manual
                      </button>
                      <button onClick={() => handleTrustidModeToggle(checkType, "api")}
                        className={`px-3 py-1.5 rounded text-xs font-medium ${cfg.submission_mode === "api" ? "bg-green-600 text-white" : "bg-slate-600 text-slate-400 hover:text-white"}`}>
                        API
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Task Queue */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Task Queue</h3>
                <div className="flex gap-2">
                  {["", "pending_admin", "awaiting_candidate", "submitted_to_trustid"].map((f) => (
                    <button key={f} onClick={() => setTrustidTaskFilter(f)}
                      className={`px-3 py-1 rounded text-xs font-medium ${trustidTaskFilter === f ? "bg-blue-600 text-white" : "bg-slate-700 text-slate-400 hover:text-white"}`}>
                      {f ? f.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()) : "All"}
                    </button>
                  ))}
                </div>
              </div>

              {trustidTasks.length === 0 ? (
                <p className="text-slate-500 text-sm text-center py-8">No pending tasks</p>
              ) : (
                <div className="space-y-3">
                  {trustidTasks.map((task) => (
                    <div key={task.id as string} className="p-4 bg-slate-700/50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <StatusBadge status={task.status as string} />
                          <span className="text-white font-medium text-sm">{(task.check_type as string)?.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}</span>
                        </div>
                        <span className="text-xs text-slate-500">{(task.created_at as string)?.split("T")[0]}</span>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs mb-3">
                        <div><span className="text-slate-400">Candidate:</span> <span className="text-white">{task.candidate_name as string || `${task.first_name || ""} ${task.last_name || ""}`.trim() || "N/A"}</span></div>
                        <div><span className="text-slate-400">Email:</span> <span className="text-white">{task.candidate_email as string || task.candidate_email_lookup as string || "N/A"}</span></div>
                        <div><span className="text-slate-400">DOB:</span> <span className="text-white">{task.candidate_dob as string || "N/A"}</span></div>
                      </div>
                      {Boolean(task.trustid_reference) && (
                        <div className="text-xs mb-2"><span className="text-slate-400">TrustID Ref:</span> <span className="text-blue-300">{String(task.trustid_reference)}</span></div>
                      )}

                      {/* Actions */}
                      <div className="flex gap-2 mt-2">
                        {task.status === "pending_admin" && (
                          <>
                            {trustidMarkingId === (task.id as string) ? (
                              <div className="flex-1 flex gap-2 items-end">
                                <div className="flex-1">
                                  <label className="block text-slate-400 text-xs mb-1">TrustID Reference</label>
                                  <input type="text" value={trustidMarkRef} onChange={(e) => setTrustidMarkRef(e.target.value)} placeholder="e.g. TID-12345"
                                    className="w-full bg-slate-600 border border-slate-500 rounded px-2 py-1 text-white text-xs" />
                                </div>
                                <div className="flex-1">
                                  <label className="block text-slate-400 text-xs mb-1">Notes</label>
                                  <input type="text" value={trustidMarkNotes} onChange={(e) => setTrustidMarkNotes(e.target.value)} placeholder="Optional notes"
                                    className="w-full bg-slate-600 border border-slate-500 rounded px-2 py-1 text-white text-xs" />
                                </div>
                                <button onClick={handleTrustidMarkSubmitted} disabled={savingTrustid}
                                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-3 py-1 rounded text-xs font-medium">
                                  {savingTrustid ? "Saving..." : "Confirm"}
                                </button>
                                <button onClick={() => setTrustidMarkingId(null)} className="text-slate-400 hover:text-white text-xs px-2 py-1">Cancel</button>
                              </div>
                            ) : (
                              <button onClick={() => setTrustidMarkingId(task.id as string)}
                                className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-xs font-medium flex items-center gap-1">
                                <Send size={12} /> Mark Submitted to TrustID
                              </button>
                            )}
                          </>
                        )}
                        {(task.status === "awaiting_candidate" || task.status === "submitted_to_trustid") && (
                          <>
                            {trustidResultId === (task.id as string) ? (
                              <div className="flex-1 flex gap-2 items-end flex-wrap">
                                <div>
                                  <label className="block text-slate-400 text-xs mb-1">Result</label>
                                  <select value={trustidResultValue} onChange={(e) => setTrustidResultValue(e.target.value)}
                                    className="bg-slate-600 border border-slate-500 rounded px-2 py-1 text-white text-xs">
                                    <option value="pass">Pass</option>
                                    <option value="fail">Fail</option>
                                    <option value="inconclusive">Inconclusive</option>
                                    <option value="intervention_required">Intervention Required</option>
                                  </select>
                                </div>
                                <div className="flex-1">
                                  <label className="block text-slate-400 text-xs mb-1">TrustID Ref</label>
                                  <input type="text" value={trustidResultRef} onChange={(e) => setTrustidResultRef(e.target.value)} placeholder="Reference"
                                    className="w-full bg-slate-600 border border-slate-500 rounded px-2 py-1 text-white text-xs" />
                                </div>
                                <div className="flex-1">
                                  <label className="block text-slate-400 text-xs mb-1">Notes</label>
                                  <input type="text" value={trustidResultNotes} onChange={(e) => setTrustidResultNotes(e.target.value)} placeholder="Notes"
                                    className="w-full bg-slate-600 border border-slate-500 rounded px-2 py-1 text-white text-xs" />
                                </div>
                                <button onClick={handleTrustidRecordResult} disabled={savingTrustid}
                                  className="bg-green-600 hover:bg-green-700 disabled:bg-green-800 text-white px-3 py-1 rounded text-xs font-medium">
                                  {savingTrustid ? "Saving..." : "Record Result"}
                                </button>
                                <button onClick={() => setTrustidResultId(null)} className="text-slate-400 hover:text-white text-xs px-2 py-1">Cancel</button>
                              </div>
                            ) : (
                              <button onClick={() => setTrustidResultId(task.id as string)}
                                className="bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded text-xs font-medium flex items-center gap-1">
                                <CheckCircle size={12} /> Record Result
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Operations Tab — 3.2, 3.3, 3.4, 3.5 */}
        {mainTab === "operations" && subTab === "analytics-dashboard" && <AnalyticsDashboard />}
        {mainTab === "operations" && subTab === "webhook-dashboard" && <WebhookDeliveryDashboard />}
        {mainTab === "operations" && subTab === "audit-reporting" && <AuditReportingPanel />}
        {mainTab === "operations" && subTab === "jobs-monitor" && <BackgroundJobsMonitor />}
        {mainTab === "operations" && subTab === "ai-insights" && <AIInsightsPanel />}

        {/* Overview Tab */}
        {tab === "overview" && stats && (
          <div className="space-y-6">
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: "Total Candidates", value: stats.total_candidates, icon: <Users className="text-blue-400" size={20} /> },
                { label: "Compliant", value: stats.compliant, icon: <CheckCircle className="text-green-400" size={20} /> },
                { label: "Active Alerts", value: stats.active_alerts, icon: <AlertTriangle className="text-amber-400" size={20} /> },
                { label: "Compliance Rate", value: `${Number(stats.compliance_rate ?? 0).toFixed(1)}%`, icon: <BarChart3 className="text-purple-400" size={20} /> },
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
                      <td className="px-4 py-3"><span className={`text-sm font-bold ${(c.compliance_score as number) >= 95 ? "text-green-400" : (c.compliance_score as number) >= 60 ? "text-amber-400" : "text-red-400"}`}>{Number(c.compliance_score ?? 0).toFixed(1)}%</span></td>
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
                      <td className="px-4 py-3 text-sm text-green-400">{"\u00A3"}{((a.revenue as number) || 0).toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-amber-400">{"\u00A3"}{((a.cost as number) || 0).toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-emerald-400">{"\u00A3"}{((a.margin as number) || 0).toFixed(2)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <button onClick={() => generateInvoicesForAgency(a.agency_id as string)} disabled={generatingInvoices === a.agency_id}
                            className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-3 py-1 rounded-full hover:bg-blue-600/30 disabled:opacity-50 flex items-center gap-1">
                            <FileText size={12} /> {generatingInvoices === a.agency_id ? "Generating..." : "Generate All"}
                          </button>
                          <button onClick={() => { setGroupedAgencyId(a.agency_id as string); setGroupedResult(null); }}
                            className="text-xs bg-purple-600/20 text-purple-400 border border-purple-600/30 px-3 py-1 rounded-full hover:bg-purple-600/30 flex items-center gap-1">
                            <CreditCard size={12} /> Periodic Invoice
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody></table></div>

                {/* Grouped/Periodic Invoice Generation */}
                {groupedAgencyId && (
                  <div className="mt-4 p-4 bg-slate-700/50 rounded-lg border border-purple-500/30">
                    <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2"><CreditCard className="text-purple-400" size={16} /> Generate Periodic Invoice — {agencyData.find(a => a.agency_id === groupedAgencyId)?.agency_name as string}</h4>
                    <p className="text-slate-400 text-xs mb-3">Select a date range to group all completed checks into a single itemised invoice for this agency.</p>
                    <div className="flex items-end gap-3 mb-3">
                      <div><label className="text-xs text-slate-400 block mb-1">From</label><input type="date" value={groupedDateFrom} onChange={(e) => setGroupedDateFrom(e.target.value)} className="bg-slate-800 border border-slate-600 rounded px-3 py-1.5 text-white text-sm" /></div>
                      <div><label className="text-xs text-slate-400 block mb-1">To</label><input type="date" value={groupedDateTo} onChange={(e) => setGroupedDateTo(e.target.value)} className="bg-slate-800 border border-slate-600 rounded px-3 py-1.5 text-white text-sm" /></div>
                      <button onClick={() => handleGenerateGroupedInvoice(groupedAgencyId, groupedDateFrom, groupedDateTo, setGeneratingGrouped)} disabled={generatingGrouped || !groupedDateFrom || !groupedDateTo}
                        className="bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 disabled:opacity-50 text-white px-4 py-1.5 rounded text-sm font-medium flex items-center gap-1">
                        <FileText size={14} /> {generatingGrouped ? "Generating..." : "Generate Itemised Invoice"}
                      </button>
                      <button onClick={() => { setGroupedAgencyId(""); setGroupedResult(null); }} className="text-xs text-slate-400 hover:text-slate-300 px-2 py-1.5">Cancel</button>
                    </div>
                    {groupedResult && (
                      <div className="mt-3 bg-slate-800/80 rounded-lg p-4 border border-slate-600">
                        <div className="flex items-center justify-between mb-3">
                          <h5 className="text-sm font-medium text-white">Invoice Summary: {groupedResult.agency as string}</h5>
                          <span className="text-xs text-slate-400">{groupedResult.date_from as string} — {groupedResult.date_to as string}</span>
                        </div>
                        {(groupedResult.discount_percent as number) > 0 && <p className="text-xs text-purple-300 mb-2">Agency discount: {groupedResult.discount_percent as number}% applied</p>}
                        {(groupedResult.line_items as Record<string, unknown>[])?.length > 0 ? (
                          <table className="w-full text-sm"><thead><tr className="border-b border-slate-700">
                            {["Candidate","Check","Description","Cost","Sell"].map(h => <th key={h} className="text-left text-xs text-slate-400 px-2 py-1">{h}</th>)}
                          </tr></thead><tbody>
                            {(groupedResult.line_items as Record<string, unknown>[]).map((li, idx) => (
                              <tr key={idx} className="border-b border-slate-700/30">
                                <td className="px-2 py-1 text-slate-300 text-xs">{li.candidate as string}</td>
                                <td className="px-2 py-1 text-xs"><span className="bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded text-xs">{(li.check_type as string).replace(/_/g, " ")}</span></td>
                                <td className="px-2 py-1 text-slate-300 text-xs">{li.description as string}</td>
                                <td className="px-2 py-1 text-amber-400 text-xs">{"\u00A3"}{(Number(li.cost) || 0).toFixed(2)}</td>
                                <td className="px-2 py-1 text-green-400 text-xs">{"\u00A3"}{(Number(li.sell) || 0).toFixed(2)}</td>
                              </tr>
                            ))}
                          </tbody><tfoot><tr className="border-t border-slate-600">
                            <td colSpan={3} className="px-2 py-2 text-white text-sm font-medium">Total ({groupedResult.generated as number} items)</td>
                            <td className="px-2 py-2 text-amber-400 font-medium">{"\u00A3"}{(Number(groupedResult.total_cost) || 0).toFixed(2)}</td>
                            <td className="px-2 py-2 text-green-400 font-medium">{"\u00A3"}{(Number(groupedResult.total_sell) || 0).toFixed(2)}</td>
                          </tr></tfoot></table>
                        ) : <p className="text-slate-400 text-sm">No new invoiceable items found in this date range.</p>}
                      </div>
                    )}
                  </div>
                )}
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
                      <td className="px-3 py-2 text-sm font-medium">{inv.adjusted_amount != null ? (<><span className="text-amber-400">{"\u00A3"}{(Number(inv.adjusted_amount) || 0).toFixed(2)}</span><span className="text-slate-500 text-xs ml-1 line-through">{"\u00A3"}{(Number(inv.sell_amount) || 0).toFixed(2)}</span></>) : (<span className="text-green-400">{"\u00A3"}{(Number(inv.sell_amount) || 0).toFixed(2)}</span>)}</td>
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
                        <h2 className="text-xl font-bold text-white flex items-center gap-2"><CreditCard className="text-blue-400" size={22} /> Credit Packs & Pricing</h2>
                        <p className="text-slate-400 text-sm">Manage credit pack tiers, pack pricing, credit allowances, per-check credit rates, and rollover settings.</p>

            {/* Editable Subscription Tiers */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-md font-semibold text-white">Credit Packs</h3>
                <button onClick={() => setCreatingTier(true)} className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-xs font-medium border-none cursor-pointer flex items-center gap-1">
                  + New Pack
                </button>
              </div>

              {/* Create New Tier Form */}
              {creatingTier && (
                <div className="mb-4 p-5 bg-slate-700/80 rounded-xl border border-green-500/30">
                  <h4 className="text-white font-medium mb-3">Create New Credit Pack</h4>
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Plan Key (e.g. premium)</label>
                        <input value={newTierData.tier_key} onChange={(e) => setNewTierData(prev => ({...prev, tier_key: e.target.value}))}
                          className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Plan Name</label>
                        <input value={newTierData.name} onChange={(e) => setNewTierData(prev => ({...prev, name: e.target.value}))}
                          className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Pack Price (£)</label>
                        <input type="number" step="0.01" value={newTierData.monthly_price} onChange={(e) => setNewTierData(prev => ({...prev, monthly_price: e.target.value}))}
                          className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Pack Credits</label>
                        <input type="number" value={newTierData.monthly_checks} onChange={(e) => setNewTierData(prev => ({...prev, monthly_checks: e.target.value}))}
                          className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Overage Rate (£/credit)</label>
                        <input type="number" step="0.01" value={newTierData.overage_rate} onChange={(e) => setNewTierData(prev => ({...prev, overage_rate: e.target.value}))}
                          className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <label className="flex items-center gap-2 text-sm text-white cursor-pointer">
                        <input type="checkbox" checked={newTierData.allow_rollover} onChange={(e) => setNewTierData(prev => ({...prev, allow_rollover: e.target.checked}))}
                          className="rounded" />
                        Allow unused credits to roll over on top-up/renewal (50% cap of new pack)
                      </label>
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Features (one per line)</label>
                      <textarea value={newTierData.features} onChange={(e) => setNewTierData(prev => ({...prev, features: e.target.value}))} rows={3}
                        className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm resize-none" />
                    </div>
                    <div className="flex gap-2">
                      <button onClick={createNewTier} disabled={savingTier || !newTierData.tier_key || !newTierData.name}
                        className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-green-800 text-white rounded-lg py-2 text-xs font-medium border-none cursor-pointer">
                        {savingTier ? "Creating..." : "Create Plan"}
                      </button>
                      <button onClick={() => setCreatingTier(false)}
                        className="flex-1 bg-slate-600 hover:bg-slate-500 text-white rounded-lg py-2 text-xs font-medium border-none cursor-pointer">
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                {Object.entries(subTiers).length > 0 ? Object.entries(subTiers).map(([tierKey, tier]) => {
                  const colors: Record<string, string> = { starter: "border-blue-500/30", growth: "border-green-500/30", professional: "border-cyan-500/30", enterprise: "border-purple-500/30" };
                  const isEditing = editingTier === tierKey;
                  return (
                    <div key={tierKey} className={`p-5 bg-slate-700/50 rounded-xl border ${colors[tierKey] || "border-slate-600"}`}>
                      {isEditing ? (
                        <div className="space-y-3">
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Plan Name</label>
                            <input value={tierEditData.name} onChange={(e) => setTierEditData(prev => ({...prev, name: e.target.value}))}
                              className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="block text-xs text-slate-400 mb-1">Pack Price (£)</label>
                              <input type="number" step="0.01" value={tierEditData.monthly_price} onChange={(e) => setTierEditData(prev => ({...prev, monthly_price: e.target.value}))}
                                className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                            </div>
                            <div>
                              <label className="block text-xs text-slate-400 mb-1">Pack Credits</label>
                              <input type="number" value={tierEditData.monthly_checks} onChange={(e) => setTierEditData(prev => ({...prev, monthly_checks: e.target.value}))}
                                className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                            </div>
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="block text-xs text-slate-400 mb-1">Overage Rate (£/credit)</label>
                              <input type="number" step="0.01" value={tierEditData.overage_rate} onChange={(e) => setTierEditData(prev => ({...prev, overage_rate: e.target.value}))}
                                className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                            </div>
                            <div>
                              <label className="block text-xs text-slate-400 mb-1">Per Worker Price (£)</label>
                              <input type="number" step="0.01" value={tierEditData.per_worker_price} onChange={(e) => setTierEditData(prev => ({...prev, per_worker_price: e.target.value}))}
                                className="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white text-sm" />
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            <label className="flex items-center gap-2 text-sm text-white cursor-pointer">
                              <input type="checkbox" checked={tierEditData.allow_rollover} onChange={(e) => setTierEditData(prev => ({...prev, allow_rollover: e.target.checked}))}
                                className="rounded" />
                              Allow unused credits to roll over on top-up/renewal (50% cap of new pack)
                            </label>
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Features (one per line)</label>
                            <textarea value={tierEditData.features} onChange={(e) => setTierEditData(prev => ({...prev, features: e.target.value}))} rows={3}
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
                            <div className="flex items-center gap-2">
                              <button onClick={() => startEditTier(tierKey)}
                                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 bg-transparent border-none cursor-pointer">
                                <Edit size={12} /> Edit
                              </button>
                              <button onClick={() => deleteTier(tierKey)}
                                className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1 bg-transparent border-none cursor-pointer">
                                <Trash2 size={12} /> Delete
                              </button>
                            </div>
                          </div>
                          <p className="text-blue-400 text-xl font-bold mb-1">
                            £{tier.monthly_price.toLocaleString()} per pack
                          </p>
                          <p className="text-green-400 text-sm font-medium mb-1">
                            {(tier.monthly_checks || 0) >= 999999 ? "Unlimited credits" : `${tier.monthly_checks || 0} credits per pack`}
                          </p>
                          {(tier.overage_rate || 0) > 0 && (
                            <p className="text-amber-400 text-xs mb-1">Overage: £{tier.overage_rate}/credit</p>
                          )}
                          <p className="text-slate-400 text-xs mb-3">
                            {tier.allow_rollover ? "Unused credits roll over on top-up (50% cap)" : "Credits valid for 12 months from purchase"}
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
                    <p>Loading credit packs...</p>
                  </div>
                )}
              </div>
            </div>

            {/* Partial Credit Rates */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-2">Partial Credit Rates</h3>
              <p className="text-slate-400 text-xs mb-4">Configure how many credits each check type consumes. 1.0 = full credit, 0.5 = half credit, etc.</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-600">
                      <th className="text-left py-2 text-slate-400 font-medium">Check Type</th>
                      <th className="text-left py-2 text-slate-400 font-medium">Label</th>
                      <th className="text-right py-2 text-slate-400 font-medium">Credit Value</th>
                      <th className="text-right py-2 text-slate-400 font-medium">Third Party Cost (£)</th>
                      <th className="text-right py-2 text-slate-400 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {creditRates.map((rate) => {
                      const isEditingRate = editingRate === (rate.check_type as string);
                      return (
                        <tr key={rate.check_type as string} className="border-b border-slate-700/50">
                          <td className="py-2 text-white font-mono text-xs">{rate.check_type as string}</td>
                          {isEditingRate ? (
                            <>
                              <td className="py-2"><input value={rateEditData.label} onChange={(e) => setRateEditData(prev => ({...prev, label: e.target.value}))}
                                className="bg-slate-600 border border-slate-500 rounded px-2 py-1 text-white text-xs w-full" /></td>
                              <td className="py-2"><input type="number" step="0.01" value={rateEditData.credit_value} onChange={(e) => setRateEditData(prev => ({...prev, credit_value: e.target.value}))}
                                className="bg-slate-600 border border-slate-500 rounded px-2 py-1 text-white text-xs w-20 text-right" /></td>
                              <td className="py-2"><input type="number" step="0.01" value={rateEditData.third_party_cost} onChange={(e) => setRateEditData(prev => ({...prev, third_party_cost: e.target.value}))}
                                className="bg-slate-600 border border-slate-500 rounded px-2 py-1 text-white text-xs w-20 text-right" /></td>
                              <td className="py-2 text-right">
                                <button onClick={() => saveCreditRate(rate.check_type as string)} className="text-xs text-green-400 hover:text-green-300 mr-2 bg-transparent border-none cursor-pointer">Save</button>
                                <button onClick={() => setEditingRate(null)} className="text-xs text-slate-400 hover:text-slate-300 bg-transparent border-none cursor-pointer">Cancel</button>
                              </td>
                            </>
                          ) : (
                            <>
                              <td className="py-2 text-slate-300">{rate.label as string}</td>
                              <td className="py-2 text-right text-cyan-400 font-medium">{(rate.credit_value as number).toFixed(2)}</td>
                              <td className="py-2 text-right text-slate-300">£{(rate.third_party_cost as number).toFixed(2)}</td>
                              <td className="py-2 text-right">
                                <button onClick={() => { setEditingRate(rate.check_type as string); setRateEditData({ label: rate.label as string, credit_value: (rate.credit_value as number).toString(), third_party_cost: (rate.third_party_cost as number).toString() }); }}
                                  className="text-xs text-blue-400 hover:text-blue-300 bg-transparent border-none cursor-pointer">Edit</button>
                              </td>
                            </>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
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

        {/* Agencies Tab - suspend/activate + discount + billing mode */}
        {tab === "agencies" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2"><Ban className="text-blue-400" size={22} /> Agency Management</h2>
                <p className="text-slate-400 text-sm mt-1">View, suspend, or reactivate agency accounts. Set per-agency discounts and billing modes.</p>
              </div>
              <button onClick={handleSendReminders}
                className="bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
                <Bell size={14} /> Send Payment Reminders
              </button>
            </div>
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full"><thead><tr className="border-b border-slate-700">
                {["Agency Name","Email","Industry","Discount","Billing Mode","Status","Actions"].map(h => <th key={h} className="text-left text-xs text-slate-400 font-medium px-4 py-3">{h}</th>)}
              </tr></thead><tbody>
                {agencies.map((a) => {
                  const currentTemplateId = String(a.industry_template_id || "");
                  const currentTemplateName = indTemplates.find((t) => String(t.id) === currentTemplateId)?.name;
                  return (
                  <tr key={String(a.id)} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-sm text-white font-medium">{String(a.name)}</td>
                    <td className="px-4 py-3 text-sm text-slate-300">{String(a.email)}</td>
                    <td className="px-4 py-3">
                      {assigningAgency === String(a.id) ? (
                        <div className="flex items-center gap-1">
                          <select value={assignTemplateId} onChange={(e) => setAssignTemplateId(e.target.value)}
                            className="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-xs">
                            <option value="">Select Industry...</option>
                            {indTemplates.map((t) => <option key={String(t.id)} value={String(t.id)}>{String(t.name)}</option>)}
                          </select>
                          <button onClick={() => handleAssignTemplate(String(a.id), assignTemplateId)} disabled={!assignTemplateId}
                            className="text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-2 py-1 rounded hover:bg-green-600/30 disabled:opacity-50">Save</button>
                          <button onClick={() => setAssigningAgency(null)}
                            className="text-xs text-slate-400 hover:text-white">Cancel</button>
                        </div>
                      ) : (
                        <button onClick={() => { setAssigningAgency(String(a.id)); setAssignTemplateId(currentTemplateId); loadIndustryTemplates(); }}
                          className={`text-xs px-2 py-1 rounded border ${currentTemplateName ? "bg-purple-600/20 text-purple-300 border-purple-600/30" : "bg-slate-600/20 text-slate-400 border-slate-600/30"} hover:opacity-80`}>
                          {currentTemplateName ? String(currentTemplateName) : "Assign Industry"}
                        </button>
                      )}
                    </td>
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
                    <td className="px-4 py-3">
                      <select
                        value={String(a.billing_mode || "manual_invoicing")}
                        onChange={(e) => handleBillingModeChange(String(a.id), e.target.value)}
                        className="bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="manual_invoicing">Manual Invoicing</option>
                        <option value="online_payment">Online Payment (PAYG)</option>
                        <option value="credit_pack">Credit Pack</option>
                      </select>
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
                  );
                })}
                {agencies.length === 0 && <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-500 text-sm">No agencies found</td></tr>}
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
                    <td className="px-4 py-3 text-sm text-white font-medium">{Number(c.compliance_score || 0).toFixed(1)}%</td>
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

            {/* Generate Invoice Section */}
            <div className="bg-slate-800/80 rounded-xl border border-purple-500/30 p-5">
              <h3 className="text-md font-semibold text-white mb-3 flex items-center gap-2"><PlusCircle className="text-purple-400" size={18} /> Generate Invoices</h3>
              <p className="text-slate-400 text-xs mb-3">Generate itemised invoices for an agency. Select a date range for periodic invoicing, or leave blank to generate for all completed checks.</p>
              <div className="flex items-end gap-3 flex-wrap">
                <div><label className="text-xs text-slate-400 block mb-1">Agency</label>
                  <select value={invTabAgencyId} onChange={(e) => setInvTabAgencyId(e.target.value)}
                    className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-white text-sm min-w-48">
                    <option value="">Select agency...</option>
                    {agencies.map((ag) => <option key={ag.id as string} value={ag.id as string}>{ag.name as string}</option>)}
                  </select>
                </div>
                <div><label className="text-xs text-slate-400 block mb-1">From (optional)</label><input type="date" value={invTabDateFrom} onChange={(e) => setInvTabDateFrom(e.target.value)} className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-white text-sm" /></div>
                <div><label className="text-xs text-slate-400 block mb-1">To (optional)</label><input type="date" value={invTabDateTo} onChange={(e) => setInvTabDateTo(e.target.value)} className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-white text-sm" /></div>
                <button onClick={() => {
                  if (!invTabAgencyId) { showMessage("Error: Please select an agency"); return; }
                  if (invTabDateFrom && invTabDateTo) {
                    handleGenerateGroupedInvoice(invTabAgencyId, invTabDateFrom, invTabDateTo, setInvTabGenerating);
                  } else {
                    generateInvoicesForAgency(invTabAgencyId);
                  }
                }} disabled={invTabGenerating || generatingInvoices === invTabAgencyId || !invTabAgencyId}
                  className="bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 disabled:opacity-50 text-white px-5 py-1.5 rounded text-sm font-medium flex items-center gap-1">
                  <FileText size={14} /> {invTabGenerating || generatingInvoices === invTabAgencyId ? "Generating..." : "Generate Invoices"}
                </button>
              </div>
            </div>

            {/* Filters & Search */}
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-slate-400 text-sm">Status:</span>
              {["all", "pending", "paid"].map((f) => (
                <button key={f} onClick={() => setInvoiceFilter(f)}
                  className={`px-3 py-1 rounded-full text-xs font-medium border ${invoiceFilter === f ? "bg-blue-600/30 text-blue-300 border-blue-500/50" : "bg-slate-700/50 text-slate-400 border-slate-600/30 hover:bg-slate-700"}`}>
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
              <span className="text-slate-600">|</span>
              <select value={invoiceAgencyFilter} onChange={(e) => setInvoiceAgencyFilter(e.target.value)}
                className="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-xs">
                <option value="">All Agencies</option>
                {[...new Set(adminInvoices.map((inv) => String(inv.agency_name || "")))].filter(Boolean).map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
              <select value={invoiceTypeFilter} onChange={(e) => setInvoiceTypeFilter(e.target.value)}
                className="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-xs">
                <option value="">All Types</option>
                {[...new Set(adminInvoices.map((inv) => String(inv.check_type || "")))].filter(Boolean).map((ct) => (
                  <option key={ct} value={ct}>{ct.replace(/_/g, " ")}</option>
                ))}
              </select>
              <span className="text-slate-600">|</span>
              <input value={invoiceSearch} onChange={(e) => setInvoiceSearch(e.target.value)}
                placeholder="Search invoice ID, candidate, agency..."
                className="bg-slate-700 border border-slate-600 rounded px-3 py-1 text-white text-xs w-64" />
              {(invoiceAgencyFilter || invoiceTypeFilter || invoiceSearch || invoiceFilter !== "all") && (
                <button onClick={() => { setInvoiceFilter("all"); setInvoiceAgencyFilter(""); setInvoiceTypeFilter(""); setInvoiceSearch(""); }}
                  className="text-xs text-slate-400 hover:text-slate-300 underline">Clear filters</button>
              )}
            </div>

            {/* Send Invoice Email Bar */}
            {selectedInvoiceIds.length > 0 && (
              <div className="bg-blue-900/30 border border-blue-600/40 rounded-xl p-4 flex items-center justify-between">
                <p className="text-blue-300 text-sm">{selectedInvoiceIds.length} invoice(s) selected for emailing</p>
                <div className="flex gap-2">
                  <button onClick={() => setSelectedInvoiceIds([])} className="text-xs bg-slate-600/20 text-slate-400 border border-slate-600/30 px-3 py-1.5 rounded hover:bg-slate-600/30">Clear Selection</button>
                  <button onClick={() => handleSendInvoiceEmail(selectedInvoiceIds)} disabled={sendingInvoiceEmail}
                    className="bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:opacity-50 text-white px-5 py-1.5 rounded text-sm font-medium flex items-center gap-1">
                    <Send size={14} /> {sendingInvoiceEmail ? "Sending..." : "Send Invoice Email"}
                  </button>
                </div>
              </div>
            )}

            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full"><thead><tr className="border-b border-slate-700">
                <th className="text-left text-xs text-slate-400 font-medium px-3 py-3 w-8"><input type="checkbox" className="rounded" onChange={(e) => { if (e.target.checked) { setSelectedInvoiceIds(adminInvoices.filter(inv => String(inv.status) === "pending").map(inv => String(inv.id))); } else { setSelectedInvoiceIds([]); } }} checked={selectedInvoiceIds.length > 0 && selectedInvoiceIds.length === adminInvoices.filter(inv => String(inv.status) === "pending").length} /></th>
                {["Invoice ID","Agency","Candidate","Type","Original Amount","Adjusted","Discount","Status","Actions"].map(h => <th key={h} className="text-left text-xs text-slate-400 font-medium px-3 py-3">{h}</th>)}
              </tr></thead><tbody>
                {adminInvoices
                  .filter((inv) => {
                    if (invoiceFilter !== "all" && String(inv.status) !== invoiceFilter) return false;
                    if (invoiceAgencyFilter && String(inv.agency_name || "") !== invoiceAgencyFilter) return false;
                    if (invoiceTypeFilter && String(inv.check_type || "") !== invoiceTypeFilter) return false;
                    if (invoiceSearch) {
                      const q = invoiceSearch.toLowerCase();
                      const searchable = `${String(inv.id || "")} ${String(inv.agency_name || "")} ${String(inv.candidate_email || "")} ${String(inv.check_type || "")} ${String(inv.description || "")}`.toLowerCase();
                      if (!searchable.includes(q)) return false;
                    }
                    return true;
                  })
                  .map((inv) => {
                    const invId = String(inv.id);
                    const originalAmt = Number(inv.sell_amount) || 0;
                    const adjustedAmt = inv.adjusted_amount != null ? Number(inv.adjusted_amount) : null;
                    const discount = Number(inv.discount_percent) || 0;
                    const isAdjusting = adjustingInvoice === invId;
                    return (
                      <tr key={invId} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                        <td className="px-3 py-3"><input type="checkbox" className="rounded" checked={selectedInvoiceIds.includes(invId)} onChange={() => toggleInvoiceSelection(invId)} /></td>
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
                                <button onClick={() => handleSendInvoiceEmail([invId])} disabled={sendingInvoiceEmail}
                                  className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-2 py-1 rounded hover:bg-blue-600/30">Send</button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                {adminInvoices.filter((inv) => {
                  if (invoiceFilter !== "all" && String(inv.status) !== invoiceFilter) return false;
                  if (invoiceAgencyFilter && String(inv.agency_name || "") !== invoiceAgencyFilter) return false;
                  if (invoiceTypeFilter && String(inv.check_type || "") !== invoiceTypeFilter) return false;
                  if (invoiceSearch) { const q = invoiceSearch.toLowerCase(); const s = `${String(inv.id || "")} ${String(inv.agency_name || "")} ${String(inv.candidate_email || "")} ${String(inv.check_type || "")} ${String(inv.description || "")}`.toLowerCase(); if (!s.includes(q)) return false; }
                  return true;
                }).length === 0 && (
                  <tr><td colSpan={10} className="px-4 py-6 text-center text-slate-500 text-sm">No invoices found matching filters</td></tr>
                )}
              </tbody></table>
            </div>

            {/* Summary */}
            {adminInvoices.length > 0 && (
              <div className="grid grid-cols-4 gap-4">
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
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-4 text-center">
                  <p className="text-slate-400 text-xs mb-1">Outstanding</p>
                  <p className="text-red-400 font-bold text-xl">{"\u00A3"}{adminInvoices.filter((inv) => String(inv.status) === "pending").reduce((sum, inv) => sum + (inv.adjusted_amount != null ? Number(inv.adjusted_amount) : (Number(inv.sell_amount) || 0)), 0).toFixed(2)}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Settings Tab — Pricing sub-tab */}
        {tab === "settings" && subTab === "pricing" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-2"><Settings className="text-blue-400" size={22} /> Per-Element Pricing Configuration</h2>
            <p className="text-slate-400 text-sm">Set cost prices (what you pay) and sell prices (what agencies are charged) for each individual check element. This includes DBS variants (Standard, Enhanced, Enhanced + Barred), training verification, and imposter checks.</p>

            {/* Push to All Industries confirmation banner */}
            {pushToIndustriesPrompt && (
              <div className="bg-blue-900/30 border border-blue-600/40 rounded-xl p-4 flex items-center justify-between">
                <div>
                  <p className="text-blue-300 text-sm font-medium">Push updated pricing to all industry templates?</p>
                  <p className="text-slate-400 text-xs mt-1">This will update the cost and sell price for <span className="text-white font-mono">{pushToIndustriesPrompt}</span> across all industry per-check pricing matrices. Industries with custom pricing will also be overwritten.</p>
                </div>
                <div className="flex gap-2 ml-4 shrink-0">
                  <button onClick={() => pushToAllIndustries(pushToIndustriesPrompt)} disabled={pushingToIndustries}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-xs font-medium disabled:opacity-50">
                    {pushingToIndustries ? "Pushing..." : "Yes, Push to All"}
                  </button>
                  <button onClick={() => setPushToIndustriesPrompt(null)}
                    className="bg-slate-600 hover:bg-slate-700 text-white px-4 py-2 rounded-lg text-xs font-medium">
                    No, Keep As Is
                  </button>
                </div>
              </div>
            )}

            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full"><thead><tr className="border-b border-slate-700">
                {["Check Type","Label","Cost Price (\u00A3)","Sell Price (\u00A3)","Margin","Actions"].map(h => <th key={h} className="text-left text-xs text-slate-400 font-medium px-4 py-3">{h}</th>)}
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
                      <td className="px-4 py-3">{isE ? <input type="number" step="0.01" value={editingPricing[ct].cost_price} onChange={(e) => setEditingPricing((prev) => ({ ...prev, [ct]: { ...prev[ct], cost_price: e.target.value } }))} className="w-24 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-sm" /> : <span className="text-amber-400 text-sm font-medium">{"\u00A3"}{(p.cost_price as number).toFixed(2)}</span>}</td>
                      <td className="px-4 py-3">{isE ? <input type="number" step="0.01" value={editingPricing[ct].sell_price} onChange={(e) => setEditingPricing((prev) => ({ ...prev, [ct]: { ...prev[ct], sell_price: e.target.value } }))} className="w-24 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-sm" /> : <span className="text-green-400 text-sm font-medium">{"\u00A3"}{(p.sell_price as number).toFixed(2)}</span>}</td>
                      <td className="px-4 py-3"><span className={`text-sm font-medium ${margin >= 0 ? "text-emerald-400" : "text-red-400"}`}>{"\u00A3"}{margin.toFixed(2)} ({marginPct}%)</span></td>
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
          </div>
        )}

        {/* Settings Tab — Industry Templates sub-tab */}
        {tab === "settings" && subTab === "templates" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2"><ShieldAlert className="text-purple-400" size={22} /> Industry Compliance Templates</h2>
                <p className="text-slate-400 text-sm mt-1">Configure which compliance checks are required for each industry. Agencies are assigned a template that determines their compliance requirements.</p>
              </div>
              <button onClick={startNewTemplate} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2"><PlusCircle size={16} /> New Template</button>
            </div>

            {/* Template Editor Modal */}
            {editingTemplate && (
              <div className="bg-slate-800/90 rounded-xl border border-blue-500/30 p-6 space-y-4">
                <h3 className="text-lg font-bold text-white">{editingTemplate.id ? "Edit Template" : "Create New Template"}</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-slate-400 block mb-1">Template Name</label>
                    <input value={String(editingTemplate.name || "")} onChange={(e) => setEditingTemplate({ ...editingTemplate, name: e.target.value })}
                      className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm" placeholder="e.g. Healthcare (CQC)" />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 block mb-1">Compliance Label</label>
                    <input value={String(editingTemplate.compliance_label || "")} onChange={(e) => setEditingTemplate({ ...editingTemplate, compliance_label: e.target.value })}
                      className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm" placeholder="e.g. CQC Ready" />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 block mb-1">Description</label>
                    <input value={String(editingTemplate.description || "")} onChange={(e) => setEditingTemplate({ ...editingTemplate, description: e.target.value })}
                      className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm" placeholder="Description of this template" />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 block mb-1">Compliance Threshold (%)</label>
                    <input type="number" min={0} max={100} value={String(editingTemplate.compliance_threshold || 95)} onChange={(e) => setEditingTemplate({ ...editingTemplate, compliance_threshold: Number(e.target.value) })}
                      className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm" />
                  </div>
                </div>

                <h4 className="text-sm font-semibold text-white mt-4">Check Configuration</h4>
                <p className="text-xs text-slate-400">Toggle checks on/off, set required status, and configure weights for each compliance check.</p>
                {(() => {
                  const ALL_TEMPLATE_CHECKS = [
                    { check_key: "identity_verified", check_label: "Identity Verification" },
                    { check_key: "right_to_work_valid", check_label: "Right to Work" },
                    { check_key: "dbs_valid", check_label: "DBS Check" },
                    { check_key: "dbs_standard", check_label: "Standard DBS Check" },
                    { check_key: "dbs_enhanced", check_label: "Enhanced DBS Check" },
                    { check_key: "dbs_enhanced_barred", check_label: "Enhanced DBS + Barred List" },
                    { check_key: "employment_verified", check_label: "Employment Verification" },
                    { check_key: "references_verified", check_label: "References" },
                    { check_key: "registration_active", check_label: "Professional Registration" },
                    { check_key: "cv_validated", check_label: "CV Validation" },
                    { check_key: "training_compliant", check_label: "Training Compliance" },
                    { check_key: "overseas_criminal_check", check_label: "Overseas Criminal Record Check" },
                    { check_key: "professional_registration_check", check_label: "Professional Registration (NMC/GMC/HCPC)" },
                    { check_key: "occupational_health_check", check_label: "Occupational Health Check" },
                    { check_key: "training_verification", check_label: "Training Certificate Verification" },
                    { check_key: "sanctions_check", check_label: "Sanctions & Barred List Check" },
                    { check_key: "credit_check", check_label: "Credit Check" },
                    { check_key: "social_media_check", check_label: "Social Media Check" },
                    { check_key: "counterterrorism_check", check_label: "Counter-Terrorism Check" },
                  ];
                  const existingKeys = new Set(templateChecks.map((c) => String(c.check_key)));
                  const available = ALL_TEMPLATE_CHECKS.filter((c) => !existingKeys.has(c.check_key));
                  return available.length > 0 ? (
                    <div className="flex items-center gap-2 mb-2">
                      <select id="add-check-select" className="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-xs">
                        {available.map((c) => <option key={c.check_key} value={c.check_key}>{c.check_label}</option>)}
                      </select>
                      <button onClick={() => {
                        const sel = (document.getElementById("add-check-select") as HTMLSelectElement)?.value;
                        const match = ALL_TEMPLATE_CHECKS.find((c) => c.check_key === sel);
                        if (match) {
                          const nextOrder = templateChecks.length + 1;
                          setTemplateChecks([...templateChecks, { check_key: match.check_key, check_label: match.check_label, is_required: false, is_enabled: false, weight: 5, config: {}, sort_order: nextOrder }]);
                        }
                      }} className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-3 py-1 rounded hover:bg-blue-600/30">+ Add Check</button>
                    </div>
                  ) : <p className="text-xs text-slate-500 mb-2">All available check types are already included.</p>;
                })()}
                <div className="space-y-2">
                  {templateChecks.map((check, idx) => (
                    <div key={idx} className="flex items-center gap-3 p-3 bg-slate-700/50 rounded-lg border border-slate-600/30">
                      <div className="flex items-center gap-2 w-8">
                        <input type="checkbox" checked={Boolean(check.is_enabled)} onChange={(e) => {
                          const updated = [...templateChecks]; updated[idx] = { ...updated[idx], is_enabled: e.target.checked }; setTemplateChecks(updated);
                        }} className="rounded" />
                      </div>
                      <div className="flex-1">
                        <input value={String(check.check_label || "")} onChange={(e) => {
                          const updated = [...templateChecks]; updated[idx] = { ...updated[idx], check_label: e.target.value }; setTemplateChecks(updated);
                        }} className="bg-transparent text-white text-sm font-medium w-full outline-none" />
                        <span className="text-xs text-slate-500 font-mono">{String(check.check_key)}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-slate-400">Required</label>
                        <input type="checkbox" checked={Boolean(check.is_required)} onChange={(e) => {
                          const updated = [...templateChecks]; updated[idx] = { ...updated[idx], is_required: e.target.checked }; setTemplateChecks(updated);
                        }} className="rounded" />
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-slate-400">Weight</label>
                        <input type="number" min={0} max={100} value={String(check.weight || 0)} onChange={(e) => {
                          const updated = [...templateChecks]; updated[idx] = { ...updated[idx], weight: Number(e.target.value) }; setTemplateChecks(updated);
                        }} className="w-16 bg-slate-600 border border-slate-500 rounded px-2 py-1 text-white text-xs text-center" />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="flex gap-3 mt-4">
                  <button onClick={handleSaveTemplate} disabled={savingTemplate}
                    className="bg-green-600 hover:bg-green-700 disabled:bg-green-800 text-white px-6 py-2 rounded-lg text-sm font-medium">
                    {savingTemplate ? "Saving..." : (editingTemplate.id ? "Update Template" : "Create Template")}
                  </button>
                  <button onClick={() => { setEditingTemplate(null); setTemplateChecks([]); }} className="text-slate-400 hover:text-white text-sm px-4 py-2">Cancel</button>
                </div>
              </div>
            )}

            {/* Templates List */}
            <div className="grid grid-cols-1 gap-4">
              {indTemplates.map((tmpl) => {
                const checks = (tmpl.checks || []) as Record<string, unknown>[];
                const enabledChecks = checks.filter((c) => c.is_enabled);
                const requiredChecks = checks.filter((c) => c.is_required && c.is_enabled);
                const agencyCount = (tmpl.agency_count as number) || 0;
                return (
                  <div key={tmpl.id as string} className="bg-slate-800/80 rounded-xl border border-slate-700 p-5">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <h3 className="text-white font-semibold">{tmpl.name as string}</h3>
                        {tmpl.is_default ? <span className="text-xs bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded-full border border-blue-500/30">Default</span> : null}
                        <span className="text-xs bg-slate-600/50 text-slate-300 px-2 py-0.5 rounded-full">{agencyCount} {agencyCount === 1 ? "agency" : "agencies"}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => startEditTemplate(tmpl)} className="text-xs text-blue-400 hover:text-blue-300 px-2 py-1"><Edit size={14} className="inline mr-1" />Edit</button>
                        <button onClick={() => handleCloneTemplate(tmpl.id as string)} disabled={cloningTemplate === (tmpl.id as string)}
                          className="text-xs text-purple-400 hover:text-purple-300 px-2 py-1">{cloningTemplate === (tmpl.id as string) ? "Cloning..." : "Clone"}</button>
                        {!tmpl.is_default && agencyCount === 0 && (
                          <button onClick={() => handleDeleteTemplate(tmpl.id as string)} className="text-xs text-red-400 hover:text-red-300 px-2 py-1"><Trash2 size={14} className="inline mr-1" />Delete</button>
                        )}
                      </div>
                    </div>
                    <p className="text-slate-400 text-xs mb-3">{tmpl.description as string}</p>
                    <div className="flex items-center gap-4 mb-2">
                      <span className="text-xs text-slate-400">Label: <span className="text-white font-medium">{tmpl.compliance_label as string}</span></span>
                      <span className="text-xs text-slate-400">Threshold: <span className="text-white font-medium">{tmpl.compliance_threshold as number}%</span></span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {enabledChecks.map((c) => (
                        <span key={c.check_key as string} className={`text-xs px-2 py-1 rounded-full border ${c.is_required ? "bg-green-500/10 text-green-400 border-green-500/30" : "bg-slate-600/30 text-slate-300 border-slate-500/30"}`}>
                          {c.check_label as string} <span className="text-slate-500">({c.weight as number}%)</span>
                        </span>
                      ))}
                    </div>
                    <div className="mt-2 text-xs text-slate-500">{enabledChecks.length} checks enabled, {requiredChecks.length} required</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Settings Tab — Alert Settings sub-tab */}
        {tab === "settings" && subTab === "alerts-config" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-2"><Bell className="text-amber-400" size={22} /> Alert &amp; Expiry Warning Settings</h2>
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

        {/* Settings Tab — Invoice Settings sub-tab */}
        {tab === "settings" && subTab === "invoice-settings" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-2"><FileText className="text-green-400" size={22} /> Invoice Settings</h2>
            <p className="text-slate-400 text-sm">Configure company details, bank account information, VAT rate, and payment terms that appear on invoice emails sent to agencies.</p>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Company Information */}
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-white font-semibold mb-4 flex items-center gap-2"><Building2 size={16} className="text-blue-400" /> Company Information</h3>
                <div className="space-y-3">
                  {[
                    { key: "invoice_company_name", label: "Company Name", placeholder: "Your Company Ltd" },
                    { key: "invoice_company_address", label: "Address", placeholder: "123 Business Street, City, Postcode" },
                    { key: "invoice_company_email", label: "Email", placeholder: "accounts@company.com" },
                    { key: "invoice_company_phone", label: "Phone", placeholder: "+44 20 1234 5678" },
                    { key: "invoice_company_registration", label: "Company Registration No.", placeholder: "12345678" },
                    { key: "invoice_company_vat_number", label: "VAT Number", placeholder: "GB123456789" },
                  ].map((field) => (
                    <div key={field.key}>
                      <label className="text-slate-400 text-xs font-medium block mb-1">{field.label}</label>
                      <input type="text" value={editInvoiceSettings[field.key] || ""} onChange={(e) => setEditInvoiceSettings({ ...editInvoiceSettings, [field.key]: e.target.value })}
                        placeholder={field.placeholder} className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-blue-500 focus:outline-none" />
                    </div>
                  ))}
                </div>
              </div>

              {/* Bank Details */}
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-white font-semibold mb-4 flex items-center gap-2"><CreditCard size={16} className="text-green-400" /> Bank Account Details</h3>
                <div className="space-y-3">
                  {[
                    { key: "invoice_bank_account_name", label: "Account Name", placeholder: "Your Company Ltd" },
                    { key: "invoice_bank_sort_code", label: "Sort Code", placeholder: "12-34-56" },
                    { key: "invoice_bank_account_number", label: "Account Number", placeholder: "12345678" },
                    { key: "invoice_bank_iban", label: "IBAN (optional)", placeholder: "GB00XXXX00000012345678" },
                    { key: "invoice_bank_swift", label: "SWIFT/BIC (optional)", placeholder: "XXXXGB2L" },
                  ].map((field) => (
                    <div key={field.key}>
                      <label className="text-slate-400 text-xs font-medium block mb-1">{field.label}</label>
                      <input type="text" value={editInvoiceSettings[field.key] || ""} onChange={(e) => setEditInvoiceSettings({ ...editInvoiceSettings, [field.key]: e.target.value })}
                        placeholder={field.placeholder} className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-blue-500 focus:outline-none" />
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Billing Configuration */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-white font-semibold mb-4">Billing Configuration</h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="text-slate-400 text-xs font-medium block mb-1">VAT Rate (%)</label>
                  <input type="text" value={editInvoiceSettings["invoice_vat_rate"] || ""} onChange={(e) => setEditInvoiceSettings({ ...editInvoiceSettings, invoice_vat_rate: e.target.value })}
                    placeholder="20" className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-blue-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-slate-400 text-xs font-medium block mb-1">Payment Terms</label>
                  <input type="text" value={editInvoiceSettings["invoice_payment_terms"] || ""} onChange={(e) => setEditInvoiceSettings({ ...editInvoiceSettings, invoice_payment_terms: e.target.value })}
                    placeholder="Net 30" className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-blue-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-slate-400 text-xs font-medium block mb-1">Currency Symbol</label>
                  <input type="text" value={editInvoiceSettings["invoice_currency_symbol"] || ""} onChange={(e) => setEditInvoiceSettings({ ...editInvoiceSettings, invoice_currency_symbol: e.target.value })}
                    placeholder="£" className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-blue-500 focus:outline-none" />
                </div>
              </div>
            </div>

            {/* Additional Info */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-white font-semibold mb-4">Additional Invoice Information</h3>
              <div className="space-y-3">
                <div>
                  <label className="text-slate-400 text-xs font-medium block mb-1">ICO Registration</label>
                  <input type="text" value={editInvoiceSettings["invoice_ico_registration"] || ""} onChange={(e) => setEditInvoiceSettings({ ...editInvoiceSettings, invoice_ico_registration: e.target.value })}
                    placeholder="ICO Registration: ZA123456" className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-blue-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-slate-400 text-xs font-medium block mb-1">Invoice Footer Note</label>
                  <textarea value={editInvoiceSettings["invoice_footer_note"] || ""} onChange={(e) => setEditInvoiceSettings({ ...editInvoiceSettings, invoice_footer_note: e.target.value })}
                    placeholder="Thank you for your business. Please quote your invoice number when making payment."
                    rows={2} className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-blue-500 focus:outline-none resize-none" />
                </div>
              </div>
            </div>

            {/* Save Button */}
            <div className="flex gap-3">
              <button onClick={handleSaveInvoiceSettings} disabled={savingInvoiceSettings}
                className="bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:opacity-50 text-white px-8 py-2.5 rounded-lg text-sm font-medium">
                {savingInvoiceSettings ? "Saving..." : "Save Invoice Settings"}
              </button>
              <button onClick={() => setEditInvoiceSettings(invoiceSettings)} className="text-slate-400 hover:text-white text-sm px-4 py-2.5">Reset to Saved</button>
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
            <button onClick={() => { setMainTab("candidates"); setSubTab("list"); }} className="text-blue-400 hover:text-blue-300 text-sm">&larr; Back</button>
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
                  <div><span className="text-slate-400">Score:</span> <span className="text-white font-bold">{Number(selectedCandidate.compliance_score ?? 0).toFixed(1)}%</span></div>
                </div>
              </div>
              {candidateCompliance && (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-md font-semibold text-white mb-3">Compliance Breakdown</h3>
                  <div className="space-y-2">
                    {[{ label: "Identity", key: "identity_verified" },{ label: "Right to Work", key: "right_to_work_valid" },{ label: "DBS Check", key: "dbs_valid" },{ label: "Registration", key: "registration_active" },{ label: "Employment", key: "employment_verified" },{ label: "References", key: "references_verified" },{ label: "CV Validated", key: "cv_validated" },{ label: "Training", key: "training_compliant" }].map((item) => (
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
                <h3 className="text-md font-semibold text-white mb-3">Identity Verification History</h3>
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

            {/* ── Employment Verification History ── */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-3">Employment Verification History ({empVerifications.length})</h3>
              {empVerifications.length > 0 ? (
                <div className="space-y-2">
                  {empVerifications.map((ver) => (
                    <div key={ver.id as string} className="p-3 bg-slate-700/50 rounded-lg flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-white text-sm font-medium">{ver.verifier_name as string} ({ver.verifier_email as string})</span>
                        <span className="text-slate-500 text-xs">{ver.employer_name as string}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={ver.status as string} />
                        <span className="text-xs text-slate-500">{(ver.sent_at as string || "")}</span>
                        <button onClick={() => handleRetriggerEmployment(selectedCandidate.id as string, ver.id as string)}
                          disabled={retriggeringId === (ver.id as string)}
                          className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-2 py-0.5 rounded hover:bg-blue-600/30 ml-2">
                          {retriggeringId === (ver.id as string) ? "Re-triggering..." : "Re-trigger"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-500 text-sm">No employment verification requests sent yet</p>
              )}
            </div>

            {/* ── CV Analysis Results ── */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-3">CV Analysis Results</h3>
            {cvAnalyses.length > 0 ? (
              <div>
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
            ) : (
              <p className="text-slate-500 text-sm">No CV analyses completed yet</p>
            )}
            </div>

            {/* ── Employment History ── */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-3">Employment History ({empHistory.length})</h3>
              {empHistory.length > 0 ? empHistory.map((entry) => {
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

                      {!verification && typeof entry.verifier_name === "string" && typeof entry.verifier_email === "string" && (
                        <div className="mt-2 flex items-center gap-2">
                          <div className="p-2 bg-yellow-500/10 border border-yellow-500/20 rounded text-xs text-yellow-300 flex-1">
                            Verification not yet sent — verifier: {String(entry.verifier_name)} ({String(entry.verifier_email)})
                          </div>
                          <button onClick={() => handleSendEmploymentVerification(
                            selectedCandidate.id as string,
                            entry.id as string,
                            entry.verifier_name as string,
                            entry.verifier_email as string,
                            entry.verifier_job_title as string | undefined,
                          )}
                            disabled={retriggeringId === (entry.id as string)}
                            className="text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-3 py-1.5 rounded hover:bg-green-600/30 whitespace-nowrap">
                            {retriggeringId === (entry.id as string) ? "Sending..." : "Send Verification Request"}
                          </button>
                        </div>
                      )}
                      {!verification && !(entry.verifier_name && entry.verifier_email) && (
                        <div className="mt-2 p-2 bg-slate-600/30 border border-slate-600/50 rounded text-xs text-slate-400">
                          No verifier contact details provided by candidate
                        </div>
                      )}
                    </div>
                  );
                }) : (
                  <p className="text-slate-500 text-sm">No employment history entries yet</p>
                )}
            </div>

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
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-3">Training Certificates ({trainingCerts.length})</h3>
              {trainingCerts.length > 0 ? trainingCerts.map((cert) => (
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
              )) : (
                <p className="text-slate-500 text-sm">No training certificates recorded yet</p>
              )}
            </div>
          </div>
          );
        })()}

        {/* ── Benchmarking Tab ── */}
        {tab === "benchmarking" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2"><TrendingUp className="text-cyan-400" size={20} /> Agency Benchmarking</h2>
              <button onClick={loadBenchmarkData} disabled={loadingBenchmark} className="bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg px-3 py-1.5 text-xs font-medium border border-slate-600 cursor-pointer flex items-center gap-1">
                <RefreshCw size={14} className={loadingBenchmark ? "animate-spin" : ""} /> {loadingBenchmark ? "Loading..." : "Refresh"}
              </button>
            </div>

            {benchmarkData && Array.isArray((benchmarkData as Record<string, unknown>).agencies) && (
              <div className="space-y-4">
                {/* Summary Cards */}
                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-5 text-center">
                    <div className="text-3xl font-bold text-blue-400">{((benchmarkData as Record<string, unknown>).agencies as Record<string, unknown>[]).length}</div>
                    <div className="text-xs text-slate-400 mt-1">Total Agencies</div>
                  </div>
                  <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-5 text-center">
                    <div className="text-3xl font-bold text-green-400">{((benchmarkData as Record<string, unknown>).agencies as Record<string, unknown>[]).filter((a) => Number(a.compliance_rate || 0) >= 80).length}</div>
                    <div className="text-xs text-slate-400 mt-1">High Compliance (&ge;80%)</div>
                  </div>
                  <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-5 text-center">
                    <div className="text-3xl font-bold text-amber-400">{((benchmarkData as Record<string, unknown>).agencies as Record<string, unknown>[]).filter((a) => Number(a.compliance_rate || 0) >= 50 && Number(a.compliance_rate || 0) < 80).length}</div>
                    <div className="text-xs text-slate-400 mt-1">Medium (50-79%)</div>
                  </div>
                  <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-5 text-center">
                    <div className="text-3xl font-bold text-red-400">{((benchmarkData as Record<string, unknown>).agencies as Record<string, unknown>[]).filter((a) => Number(a.compliance_rate || 0) < 50).length}</div>
                    <div className="text-xs text-slate-400 mt-1">Low Compliance (&lt;50%)</div>
                  </div>
                </div>

                {/* Agency Table */}
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-md font-semibold text-white mb-4">Agency Comparison</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-700">
                          <th className="text-left text-slate-400 py-2 px-3 font-medium">Agency</th>
                          <th className="text-center text-slate-400 py-2 px-3 font-medium">Candidates</th>
                          <th className="text-center text-slate-400 py-2 px-3 font-medium">Compliance Rate</th>
                          <th className="text-center text-slate-400 py-2 px-3 font-medium">Avg Vetting Time</th>
                          <th className="text-center text-slate-400 py-2 px-3 font-medium">Revenue</th>
                          <th className="text-center text-slate-400 py-2 px-3 font-medium">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {((benchmarkData as Record<string, unknown>).agencies as Record<string, unknown>[]).map((agency) => (
                          <tr key={String(agency.agency_id)} className="border-b border-slate-700/50 hover:bg-slate-700/20">
                            <td className="py-3 px-3 text-white font-medium">{String(agency.agency_name || agency.agency_id)}</td>
                            <td className="py-3 px-3 text-center text-slate-300">{String(agency.total_candidates || 0)}</td>
                            <td className="py-3 px-3 text-center">
                              <span className={`font-bold ${Number(agency.compliance_rate || 0) >= 80 ? "text-green-400" : Number(agency.compliance_rate || 0) >= 50 ? "text-amber-400" : "text-red-400"}`}>
                                {Number(agency.compliance_rate || 0).toFixed(1)}%
                              </span>
                            </td>
                            <td className="py-3 px-3 text-center text-slate-300">{Number(agency.avg_vetting_hours || 0).toFixed(1)}h</td>
                            <td className="py-3 px-3 text-center text-emerald-400 font-medium">£{Number(agency.total_revenue || 0).toFixed(2)}</td>
                            <td className="py-3 px-3 text-center">
                              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${agency.status === "active" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>{String(agency.status || "active")}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Bar Chart */}
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-md font-semibold text-white mb-4">Compliance Rate by Agency</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={((benchmarkData as Record<string, unknown>).agencies as Record<string, unknown>[]).map((a) => ({ name: String(a.agency_name || "").slice(0, 15), rate: Number(a.compliance_rate || 0) }))}>
                      <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                      <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} domain={[0, 100]} />
                      <Tooltip contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", color: "white" }} />
                      <Bar dataKey="rate" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {!benchmarkData && !loadingBenchmark && (
              <div className="text-center py-12 text-slate-500">
                <TrendingUp size={40} className="mx-auto mb-3 opacity-50" />
                <p className="text-sm">No benchmarking data available. Click Refresh to load.</p>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
