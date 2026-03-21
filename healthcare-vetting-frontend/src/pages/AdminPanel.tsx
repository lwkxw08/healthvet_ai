import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { candidatesApi, complianceApi, monitoringApi, dashboardApi, adminApi, fraudApi, schedulerApi, reportsApi } from "../api/client";
import {
  Shield, CheckCircle, XCircle, Clock, AlertTriangle, Users,
  BarChart3, Bell, LogOut, RefreshCw, Eye, Play, Settings,
  DollarSign, FileText, TrendingUp, ShieldAlert, Zap, Download, CreditCard,
} from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend, BarChart, Bar, XAxis, YAxis } from "recharts";

type Tab = "overview" | "candidates" | "alerts" | "monitoring" | "candidate-detail" | "settings" | "analytics" | "fraud" | "scheduler" | "subscriptions";

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

  useEffect(() => { if (tab === "fraud") loadFraudData(); }, [tab, loadFraudData]);
  useEffect(() => { if (tab === "scheduler") loadSchedulerStatus(); }, [tab, loadSchedulerStatus]);
  useEffect(() => { if (tab === "settings") loadPricing(); }, [tab, loadPricing]);
  useEffect(() => { if (tab === "analytics") loadAnalytics(); }, [tab, loadAnalytics]);
  useEffect(() => { if (tab === "monitoring") loadMonitoringRevenue(); }, [tab, loadMonitoringRevenue]);

  const showMessage = (msg: string) => { setMessage(msg); setTimeout(() => setMessage(""), 4000); };

  const viewCandidate = async (candidate: Record<string, unknown>) => {
    setSelectedCandidate(candidate); setTab("candidate-detail");
    if (token) { try { const comp = await complianceApi.get(token, candidate.id as string).catch(() => null); setCandidateCompliance(comp); } catch { /* ignore */ } }
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

  const StatusBadge = ({ status }: { status: string }) => {
    const colors: Record<string, string> = {
      compliant: "bg-green-500/20 text-green-400 border-green-500/30",
      clear: "bg-green-500/20 text-green-400 border-green-500/30",
      active: "bg-green-500/20 text-green-400 border-green-500/30",
      valid: "bg-green-500/20 text-green-400 border-green-500/30",
      paid: "bg-green-500/20 text-green-400 border-green-500/30",
      pending: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      in_progress: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      pending_review: "bg-orange-500/20 text-orange-400 border-orange-500/30",
      flagged: "bg-red-500/20 text-red-400 border-red-500/30",
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
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full">
                <thead><tr className="border-b border-slate-700">
                  {["Name","Email","Profession","Registration","Score","Status","Actions"].map(h => <th key={h} className="text-left text-xs text-slate-400 font-medium px-4 py-3">{h}</th>)}
                </tr></thead>
                <tbody>
                  {candidates.map((c) => (
                    <tr key={c.id as string} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                      <td className="px-4 py-3 text-sm text-white">{c.first_name as string} {c.last_name as string}</td>
                      <td className="px-4 py-3 text-sm text-slate-300">{c.email as string}</td>
                      <td className="px-4 py-3 text-sm text-slate-300">{(c.profession as string) || "N/A"}</td>
                      <td className="px-4 py-3 text-sm text-slate-300">{c.registration_body as string} {c.registration_number as string}</td>
                      <td className="px-4 py-3"><span className={`text-sm font-bold ${(c.compliance_score as number) >= 95 ? "text-green-400" : (c.compliance_score as number) >= 60 ? "text-amber-400" : "text-red-400"}`}>{c.compliance_score as number}%</span></td>
                      <td className="px-4 py-3"><StatusBadge status={c.compliance_status as string} /></td>
                      <td className="px-4 py-3"><div className="flex gap-2">
                        <button onClick={() => viewCandidate(c)} className="text-blue-400 hover:text-blue-300 text-xs flex items-center gap-1"><Eye size={12} /> View</button>
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
            <h2 className="text-xl font-bold text-white flex items-center gap-2"><CreditCard className="text-blue-400" size={22} /> Agency Subscriptions</h2>
            <p className="text-slate-400 text-sm">Manage agency subscription tiers and billing methods. Agencies can subscribe via Stripe card payment or recurring invoice.</p>
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-4">Available Tiers</h3>
              <div className="grid grid-cols-4 gap-4">
                {[
                  { name: "Starter", price: "\u00a3299/mo", workers: "Up to 50", color: "border-blue-500/30" },
                  { name: "Growth", price: "\u00a3799/mo", workers: "Up to 200", color: "border-green-500/30" },
                  { name: "Enterprise", price: "\u00a31,999/mo", workers: "Unlimited", color: "border-purple-500/30" },
                  { name: "Per Worker", price: "\u00a35/worker/mo", workers: "Unlimited", color: "border-amber-500/30" },
                ].map((tier) => (
                  <div key={tier.name} className={`p-5 bg-slate-700/50 rounded-xl border ${tier.color}`}>
                    <p className="text-white font-bold text-lg mb-1">{tier.name}</p>
                    <p className="text-blue-400 text-xl font-bold mb-2">{tier.price}</p>
                    <p className="text-slate-400 text-sm">{tier.workers}</p>
                  </div>
                ))}
              </div>
            </div>
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
          </div>
        )}

        {/* Candidate Detail */}
        {tab === "candidate-detail" && selectedCandidate && (
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
                  {candidateCompliance.flags ? <div className="mt-2 p-2 bg-amber-500/10 border border-amber-500/20 rounded text-xs text-amber-300">{String(candidateCompliance.flags)}</div> : null}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
