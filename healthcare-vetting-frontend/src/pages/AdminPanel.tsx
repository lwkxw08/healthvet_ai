import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { candidatesApi, complianceApi, monitoringApi, dashboardApi } from "../api/client";
import {
  Shield, CheckCircle, XCircle, Clock, AlertTriangle, Users,
  BarChart3, Bell, LogOut, RefreshCw, Eye, Play, Settings,
} from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

type Tab = "overview" | "candidates" | "alerts" | "monitoring" | "candidate-detail";

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

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      const [s, c, a] = await Promise.all([
        dashboardApi.getStats(token),
        candidatesApi.list(token).catch(() => []),
        monitoringApi.getAlerts(token).catch(() => []),
      ]);
      setStats(s);
      setCandidates(c);
      setAlerts(a);
    } catch (err) {
      console.error("Failed to load data", err);
    }
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);

  const showMessage = (msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(""), 4000);
  };

  const viewCandidate = async (candidate: Record<string, unknown>) => {
    setSelectedCandidate(candidate);
    setTab("candidate-detail");
    if (token) {
      try {
        const comp = await complianceApi.get(token, candidate.id as string).catch(() => null);
        setCandidateCompliance(comp);
      } catch { /* ignore */ }
    }
  };

  const evaluateCandidate = async (candidateId: string) => {
    if (!token) return;
    try {
      await complianceApi.evaluate(token, candidateId);
      showMessage("Compliance re-evaluated successfully");
      await loadData();
      if (selectedCandidate && selectedCandidate.id === candidateId) {
        const comp = await complianceApi.get(token, candidateId).catch(() => null);
        setCandidateCompliance(comp);
      }
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    }
  };

  const resolveAlert = async (alertId: string) => {
    if (!token) return;
    try {
      await monitoringApi.resolveAlert(token, alertId);
      showMessage("Alert resolved");
      await loadData();
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    }
  };

  const runMonitoringChecks = async () => {
    if (!token) return;
    setRunningMonitoring(true);
    try {
      const results = await monitoringApi.runChecks(token);
      setMonitoringResults(results);
      showMessage("Monitoring checks completed");
      await loadData();
    } catch (err) {
      showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally {
      setRunningMonitoring(false);
    }
  };

  const StatusBadge = ({ status }: { status: string }) => {
    const colors: Record<string, string> = {
      compliant: "bg-green-500/20 text-green-400 border-green-500/30",
      clear: "bg-green-500/20 text-green-400 border-green-500/30",
      active: "bg-green-500/20 text-green-400 border-green-500/30",
      valid: "bg-green-500/20 text-green-400 border-green-500/30",
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

      {/* Navigation */}
      <div className="bg-slate-800/50 border-b border-slate-700 px-6">
        <div className="flex gap-1">
          {[
            { key: "overview" as Tab, label: "Overview", icon: <BarChart3 size={16} /> },
            { key: "candidates" as Tab, label: "All Candidates", icon: <Users size={16} /> },
            { key: "alerts" as Tab, label: `Alerts (${alerts.length})`, icon: <Bell size={16} /> },
            { key: "monitoring" as Tab, label: "Monitoring", icon: <Settings size={16} /> },
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
        {/* Overview */}
        {tab === "overview" && stats && (
          <div className="space-y-6">
            {/* Stats Row */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: "Total Candidates", value: stats.total_candidates, icon: <Users className="text-blue-400" size={20} /> },
                { label: "Compliant", value: stats.compliant, icon: <CheckCircle className="text-green-400" size={20} /> },
                { label: "Active Alerts", value: stats.active_alerts, icon: <AlertTriangle className="text-amber-400" size={20} /> },
                { label: "Compliance Rate", value: `${stats.compliance_rate}%`, icon: <BarChart3 className="text-purple-400" size={20} /> },
              ].map((stat) => (
                <div key={stat.label} className="bg-slate-800/80 rounded-xl border border-slate-700 p-5">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-slate-400 text-xs">{stat.label}</p>
                    {stat.icon}
                  </div>
                  <p className="text-3xl font-bold text-white">{stat.value as string | number}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-6">
              {/* Compliance Distribution */}
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4">Compliance Distribution</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                      {pieData.map((entry, index) => (
                        <Cell key={index} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", color: "white" }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Critical Alerts */}
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4 flex items-center gap-2">
                  <AlertTriangle className="text-red-400" size={18} /> Critical Alerts ({criticalAlerts.length})
                </h3>
                {criticalAlerts.length === 0 ? (
                  <p className="text-slate-400 text-sm">No critical alerts</p>
                ) : (
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {criticalAlerts.slice(0, 5).map((alert) => (
                      <div key={alert.id as string} className="p-2 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center justify-between">
                        <span className="text-red-200 text-xs">{alert.message as string}</span>
                        <button onClick={() => resolveAlert(alert.id as string)}
                          className="text-xs text-green-400 hover:text-green-300 shrink-0 ml-2">Resolve</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Flagged Candidates */}
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
                        <button onClick={() => evaluateCandidate(c.id as string)}
                          className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-3 py-1 rounded-full hover:bg-blue-600/30">
                          Re-evaluate
                        </button>
                        <button onClick={() => viewCandidate(c)}
                          className="text-xs bg-slate-600/20 text-slate-300 border border-slate-600/30 px-3 py-1 rounded-full hover:bg-slate-600/30">
                          <Eye size={12} className="inline mr-1" /> View
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* All Candidates */}
        {tab === "candidates" && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-white">All Candidates ({candidates.length})</h2>
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Name</th>
                    <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Email</th>
                    <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Profession</th>
                    <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Registration</th>
                    <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Score</th>
                    <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Status</th>
                    <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c) => (
                    <tr key={c.id as string} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                      <td className="px-4 py-3 text-sm text-white">{c.first_name as string} {c.last_name as string}</td>
                      <td className="px-4 py-3 text-sm text-slate-300">{c.email as string}</td>
                      <td className="px-4 py-3 text-sm text-slate-300">{(c.profession as string) || "N/A"}</td>
                      <td className="px-4 py-3 text-sm text-slate-300">{c.registration_body as string} {c.registration_number as string}</td>
                      <td className="px-4 py-3">
                        <span className={`text-sm font-bold ${
                          (c.compliance_score as number) >= 95 ? "text-green-400" :
                          (c.compliance_score as number) >= 60 ? "text-amber-400" : "text-red-400"
                        }`}>{c.compliance_score as number}%</span>
                      </td>
                      <td className="px-4 py-3"><StatusBadge status={c.compliance_status as string} /></td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <button onClick={() => viewCandidate(c)} className="text-blue-400 hover:text-blue-300 text-xs flex items-center gap-1">
                            <Eye size={12} /> View
                          </button>
                          <button onClick={() => evaluateCandidate(c.id as string)} className="text-purple-400 hover:text-purple-300 text-xs flex items-center gap-1">
                            <RefreshCw size={12} /> Eval
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Alerts */}
        {tab === "alerts" && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <AlertTriangle className="text-amber-400" size={22} /> All Alerts ({alerts.length})
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
                    "border-yellow-500/30"
                  }`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <StatusBadge status={alert.severity as string} />
                        <StatusBadge status={alert.alert_type as string} />
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

        {/* Monitoring */}
        {tab === "monitoring" && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white">Continuous Monitoring</h2>
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <p className="text-slate-300 text-sm mb-4">
                Run all monitoring checks: DBS Update Service, visa expiry alerts, registration renewal tracking,
                sanction monitoring, and fraud pattern detection. In production, these run automatically on a schedule.
              </p>
              <div className="grid grid-cols-2 gap-4 mb-6">
                {[
                  { label: "DBS Update Service", desc: "Check for changes since certificate issue" },
                  { label: "Visa Expiry Alerts", desc: "30/60/90 day warnings + expired checks" },
                  { label: "Registration Renewals", desc: "NMC/GMC/HCPC renewal tracking" },
                  { label: "Sanction Alerts", desc: "New sanctions on registered professionals" },
                ].map((item) => (
                  <div key={item.label} className="p-4 bg-slate-700/50 rounded-lg">
                    <p className="text-white text-sm font-medium">{item.label}</p>
                    <p className="text-slate-400 text-xs mt-1">{item.desc}</p>
                  </div>
                ))}
              </div>
              <button onClick={runMonitoringChecks} disabled={runningMonitoring}
                className="bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 text-white px-6 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2">
                <Play size={16} /> {runningMonitoring ? "Running checks..." : "Run All Monitoring Checks"}
              </button>
            </div>

            {monitoringResults && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-3">Monitoring Results</h3>
                <pre className="text-slate-300 text-sm bg-slate-700/50 p-4 rounded-lg overflow-x-auto">
                  {JSON.stringify(monitoringResults, null, 2)}
                </pre>
              </div>
            )}

            {/* SaaS Revenue Info */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-4">Monitoring Revenue Model</h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                  <p className="text-slate-400 text-xs mb-1">Per Candidate/Year</p>
                  <p className="text-xl font-bold text-green-400">£90-£140</p>
                </div>
                <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                  <p className="text-slate-400 text-xs mb-1">Agency SaaS License</p>
                  <p className="text-xl font-bold text-blue-400">£300-£2,000/mo</p>
                </div>
                <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                  <p className="text-slate-400 text-xs mb-1">Gross Margin</p>
                  <p className="text-xl font-bold text-emerald-400">30-50%</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Candidate Detail */}
        {tab === "candidate-detail" && selectedCandidate && (
          <div className="space-y-6">
            <button onClick={() => setTab("candidates")} className="text-blue-400 hover:text-blue-300 text-sm">&larr; Back</button>
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-white">
                {selectedCandidate.first_name as string} {selectedCandidate.last_name as string}
              </h2>
              <div className="flex items-center gap-3">
                <StatusBadge status={selectedCandidate.compliance_status as string} />
                <button onClick={() => evaluateCandidate(selectedCandidate.id as string)}
                  className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-3 py-1 rounded-full hover:bg-blue-600/30">
                  Re-evaluate
                </button>
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
                    {[
                      { label: "Identity", key: "identity_verified" },
                      { label: "Right to Work", key: "right_to_work_valid" },
                      { label: "DBS Check", key: "dbs_valid" },
                      { label: "Registration", key: "registration_active" },
                      { label: "References", key: "references_verified" },
                      { label: "CV Validated", key: "cv_validated" },
                    ].map((item) => (
                      <div key={item.key} className="flex items-center gap-2 p-2 bg-slate-700/50 rounded">
                        <CheckIcon passed={candidateCompliance[item.key] as boolean} />
                        <span className="text-slate-200 text-sm">{item.label}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-3">
                    <span className={`text-sm font-medium ${candidateCompliance.cqc_ready ? "text-green-400" : "text-red-400"}`}>
                      CQC Ready: {candidateCompliance.cqc_ready ? "YES" : "NO"}
                    </span>
                  </div>
                  {candidateCompliance.flags ? (
                    <div className="mt-2 p-2 bg-amber-500/10 border border-amber-500/20 rounded text-xs text-amber-300">
                      {String(candidateCompliance.flags)}
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
