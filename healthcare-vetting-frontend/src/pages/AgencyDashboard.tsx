import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { candidatesApi, complianceApi, monitoringApi, dashboardApi, agencyInvitesApi } from "../api/client";
import {
  Shield, CheckCircle, XCircle, Clock, AlertTriangle, Users,
  BarChart3, Bell, LogOut, RefreshCw, Eye, Mail, Send, Copy, Trash2,
} from "lucide-react";
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

type Tab = "dashboard" | "candidates" | "alerts" | "candidate-detail" | "invites";

export default function AgencyDashboard() {
  const { token, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("dashboard");
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [candidates, setCandidates] = useState<Record<string, unknown>[]>([]);
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
      } catch {
        // ignore
      }
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

  const sendInvite = async () => {
    if (!token || !inviteEmail.trim()) return;
    setInviteLoading(true);
    setInviteError("");
    setInviteSuccess("");
    try {
      const result = await agencyInvitesApi.createInvite(token, inviteEmail.trim());
      setInviteSuccess(`Invite sent to ${inviteEmail}. Code: ${result.invite_code as string}`);
      setInviteEmail("");
      await loadData();
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : "Failed to send invite");
    } finally {
      setInviteLoading(false);
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

  const barData = [
    { name: "ID Check", cost: 2 },
    { name: "DBS", cost: 49 },
    { name: "RTW", cost: 0 },
    { name: "CV Scan", cost: 1 },
    { name: "Reg Check", cost: 0 },
    { name: "References", cost: 0 },
  ];

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

            {/* Charts */}
            <div className="grid grid-cols-2 gap-6">
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4">Compliance Distribution</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" outerRadius={90} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                      {pieData.map((entry, index) => (
                        <Cell key={index} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", color: "white" }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-4">Per-Check Cost (GBP)</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={barData}>
                    <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                    <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
                    <Tooltip contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", color: "white" }} />
                    <Bar dataKey="cost" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Unit Economics */}
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-4">Unit Economics (Per Candidate)</h3>
              <div className="grid grid-cols-4 gap-4">
                <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                  <p className="text-slate-400 text-xs mb-1">ID Verification</p>
                  <p className="text-xl font-bold text-white">£2</p>
                </div>
                <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                  <p className="text-slate-400 text-xs mb-1">Enhanced DBS</p>
                  <p className="text-xl font-bold text-white">£49</p>
                </div>
                <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                  <p className="text-slate-400 text-xs mb-1">Total Cost</p>
                  <p className="text-xl font-bold text-amber-400">~£54</p>
                </div>
                <div className="p-4 bg-slate-700/50 rounded-lg text-center">
                  <p className="text-slate-400 text-xs mb-1">You Charge</p>
                  <p className="text-xl font-bold text-green-400">£90-£140</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Candidates Tab */}
        {tab === "candidates" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-white">Candidates ({candidates.length})</h2>
            </div>

            {candidates.length === 0 ? (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-12 text-center">
                <Users className="text-slate-600 mx-auto mb-3" size={48} />
                <p className="text-slate-400">No candidates assigned yet</p>
                <p className="text-slate-500 text-sm mt-1">Candidates will appear here once assigned to your agency</p>
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
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Status</th>
                      <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((c) => (
                      <tr key={c.id as string} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                        <td className="px-4 py-3 text-sm text-white">{c.first_name as string} {c.last_name as string}</td>
                        <td className="px-4 py-3 text-sm text-slate-300">{(c.profession as string) || "N/A"}</td>
                        <td className="px-4 py-3 text-sm text-slate-300">{(c.registration_body as string) || "N/A"} {(c.registration_number as string) || ""}</td>
                        <td className="px-4 py-3 text-sm font-medium text-white">{c.compliance_score as number}%</td>
                        <td className="px-4 py-3"><StatusBadge status={c.compliance_status as string} /></td>
                        <td className="px-4 py-3">
                          <button onClick={() => viewCandidate(c)} className="text-blue-400 hover:text-blue-300 text-sm flex items-center gap-1">
                            <Eye size={14} /> View
                          </button>
                        </td>
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
              <h3 className="text-md font-semibold text-white mb-4">Send New Invite</h3>
              <p className="text-slate-400 text-sm mb-4">
                Enter a candidate's email to generate a unique invite link. They'll register using that link and be automatically assigned to your agency.
              </p>
              <div className="flex gap-3">
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="candidate@example.com"
                  className="flex-1 bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                  onKeyDown={(e) => e.key === "Enter" && sendInvite()}
                />
                <button
                  onClick={sendInvite}
                  disabled={inviteLoading || !inviteEmail.trim()}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:opacity-50 text-white px-6 py-2.5 rounded-lg font-medium text-sm flex items-center gap-2 transition-colors"
                >
                  <Send size={16} /> {inviteLoading ? "Sending..." : "Send Invite"}
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
              <StatusBadge status={selectedCandidate.compliance_status as string} />
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
                    { label: "Right to Work", key: "right_to_work_valid" },
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
                </div>
                {candidateCompliance.flags ? (
                  <div className="mt-4">
                    <p className="text-xs text-slate-400 mb-2">Flags:</p>
                    <div className="text-sm text-amber-300">{String(candidateCompliance.flags)}</div>
                  </div>
                ) : null}
                <div className="mt-3">
                  <span className={`text-sm font-medium ${candidateCompliance.cqc_ready ? "text-green-400" : "text-slate-400"}`}>
                    CQC Ready: {candidateCompliance.cqc_ready ? "Yes" : "No"}
                  </span>
                </div>
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
      </main>
    </div>
  );
}
