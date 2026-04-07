import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { analyticsApi } from "../api/client";
import {
  BarChart3, TrendingUp, Clock, AlertTriangle, Download, Calendar,
  Users, CheckCircle, XCircle, RefreshCw, Plus, Trash2,
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from "recharts";

interface AnalyticsDashboardProps {
  agencyId?: string;
}

export default function AnalyticsDashboard({ agencyId }: AnalyticsDashboardProps) {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState<"kpis" | "time-to-clear" | "response-rates" | "expiry" | "volume" | "reports">("kpis");
  const [loading, setLoading] = useState(false);

  // KPI state
  const [kpis, setKpis] = useState<Record<string, unknown> | null>(null);

  // Time-to-clear state
  const [timeToClear, setTimeToClear] = useState<Record<string, unknown> | null>(null);

  // Response rates state
  const [responseRates, setResponseRates] = useState<Record<string, unknown> | null>(null);

  // Expiry forecast state
  const [expiryForecast, setExpiryForecast] = useState<Record<string, unknown> | null>(null);
  const [forecastDays, setForecastDays] = useState(90);

  // Volume trend state
  const [volumeTrend, setVolumeTrend] = useState<Record<string, unknown>[]>([]);

  // Scheduled reports state
  const [scheduledReports, setScheduledReports] = useState<Record<string, unknown>[]>([]);
  const [newReport, setNewReport] = useState({ report_type: "compliance_summary", frequency: "weekly", recipients: "" });
  const [creatingReport, setCreatingReport] = useState(false);

  const loadKpis = useCallback(async () => {
    if (!token || !agencyId) return;
    setLoading(true);
    try {
      const data = await analyticsApi.getKpis(token, agencyId);
      setKpis(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token, agencyId]);

  const loadTimeToClear = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await analyticsApi.getTimeToClear(token, agencyId);
      setTimeToClear(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token, agencyId]);

  const loadResponseRates = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await analyticsApi.getResponseRates(token, agencyId);
      setResponseRates(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token, agencyId]);

  const loadExpiryForecast = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await analyticsApi.getExpiryForecast(token, agencyId, forecastDays);
      setExpiryForecast(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token, agencyId, forecastDays]);

  const loadVolumeTrend = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await analyticsApi.getCheckVolumeTrend(token, agencyId);
      setVolumeTrend(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token, agencyId]);

  const loadScheduledReports = useCallback(async () => {
    if (!token) return;
    try {
      const data = await analyticsApi.getScheduledReports(token);
      setScheduledReports(data);
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => {
    if (activeTab === "kpis") loadKpis();
    else if (activeTab === "time-to-clear") loadTimeToClear();
    else if (activeTab === "response-rates") loadResponseRates();
    else if (activeTab === "expiry") loadExpiryForecast();
    else if (activeTab === "volume") loadVolumeTrend();
    else if (activeTab === "reports") loadScheduledReports();
  }, [activeTab, loadKpis, loadTimeToClear, loadResponseRates, loadExpiryForecast, loadVolumeTrend, loadScheduledReports]);

  const handleExportCsv = async () => {
    if (!token) return;
    try {
      const result = await analyticsApi.exportComplianceCsv(token, agencyId);
      const blob = new Blob([result.csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `compliance_report_${new Date().toISOString().split("T")[0]}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
  };

  const handleCreateReport = async () => {
    if (!token || !agencyId) return;
    setCreatingReport(true);
    try {
      await analyticsApi.createScheduledReport(token, {
        agency_id: agencyId,
        report_type: newReport.report_type,
        frequency: newReport.frequency,
        recipients: newReport.recipients.split(",").map(e => e.trim()).filter(Boolean),
      });
      setNewReport({ report_type: "compliance_summary", frequency: "weekly", recipients: "" });
      loadScheduledReports();
    } catch { /* ignore */ }
    finally { setCreatingReport(false); }
  };

  const handleDeleteReport = async (reportId: string) => {
    if (!token) return;
    try {
      await analyticsApi.deleteScheduledReport(token, reportId);
      loadScheduledReports();
    } catch { /* ignore */ }
  };

  const tabs = [
    { id: "kpis" as const, label: "KPI Dashboard", icon: BarChart3 },
    { id: "time-to-clear" as const, label: "Time to Clear", icon: Clock },
    { id: "response-rates" as const, label: "Response Rates", icon: TrendingUp },
    { id: "expiry" as const, label: "Expiry Forecast", icon: AlertTriangle },
    { id: "volume" as const, label: "Check Volume", icon: Calendar },
    { id: "reports" as const, label: "Scheduled Reports", icon: Download },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Analytics & Reporting</h2>
        <button onClick={handleExportCsv} className="flex items-center gap-1 px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700">
          <Download className="w-4 h-4" /> Export CSV
        </button>
      </div>

      {/* Sub-tabs */}
      <div className="flex gap-1 border-b border-gray-200 overflow-x-auto">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${activeTab === t.id ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {loading && <div className="text-center py-8 text-gray-500"><RefreshCw className="w-5 h-5 animate-spin inline-block mr-2" />Loading...</div>}

      {/* KPI Dashboard */}
      {activeTab === "kpis" && kpis && !loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white border rounded-lg p-4">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1"><Users className="w-4 h-4" /> Total Candidates</div>
              <div className="text-2xl font-bold text-gray-900">{String(kpis.total_candidates ?? 0)}</div>
            </div>
            <div className="bg-white border rounded-lg p-4">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1"><CheckCircle className="w-4 h-4 text-green-500" /> Compliant</div>
              <div className="text-2xl font-bold text-green-600">{String(kpis.compliant ?? 0)}</div>
            </div>
            <div className="bg-white border rounded-lg p-4">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1"><XCircle className="w-4 h-4 text-red-500" /> Non-Compliant</div>
              <div className="text-2xl font-bold text-red-600">{String(kpis.non_compliant ?? 0)}</div>
            </div>
            <div className="bg-white border rounded-lg p-4">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1"><Clock className="w-4 h-4 text-yellow-500" /> Pending</div>
              <div className="text-2xl font-bold text-yellow-600">{String(kpis.pending ?? 0)}</div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-white border rounded-lg p-4">
              <div className="text-sm text-gray-500 mb-1">Compliance Rate</div>
              <div className="text-3xl font-bold text-blue-600">{Number(kpis.compliance_rate ?? 0).toFixed(1)}%</div>
              <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden">
                <div className="h-full bg-blue-600 rounded-full" style={{ width: `${Number(kpis.compliance_rate ?? 0)}%` }} />
              </div>
            </div>
            <div className="bg-white border rounded-lg p-4">
              <div className="text-sm text-gray-500 mb-1">Avg Compliance Score</div>
              <div className="text-3xl font-bold text-purple-600">{Number(kpis.avg_compliance_score ?? 0).toFixed(1)}</div>
            </div>
            <div className="bg-white border rounded-lg p-4">
              <div className="text-sm text-gray-500 mb-1">Active Alerts</div>
              <div className="text-3xl font-bold text-orange-600">{String(kpis.active_alerts ?? 0)}</div>
            </div>
          </div>
        </div>
      )}

      {/* Time to Clear */}
      {activeTab === "time-to-clear" && timeToClear && !loading && (
        <div className="space-y-3">
          {Object.entries(timeToClear).map(([checkType, metrics]) => {
            const m = metrics as Record<string, unknown>;
            return (
              <div key={checkType} className="bg-white border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-medium text-gray-900 capitalize">{checkType.replace(/_/g, " ")}</h3>
                  <span className="text-xs text-gray-400">{String(m.total_completed ?? 0)} completed</span>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <div className="text-xs text-gray-500">Average</div>
                    <div className="text-lg font-semibold text-blue-600">{Number(m.avg_days ?? 0).toFixed(1)} days</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Minimum</div>
                    <div className="text-lg font-semibold text-green-600">{Number(m.min_days ?? 0).toFixed(1)} days</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Maximum</div>
                    <div className="text-lg font-semibold text-red-600">{Number(m.max_days ?? 0).toFixed(1)} days</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Response Rates */}
      {activeTab === "response-rates" && responseRates && !loading && (
        <div className="space-y-3">
          {Object.entries(responseRates).map(([type, data]) => {
            const d = data as Record<string, unknown>;
            const rate = Number(d.response_rate ?? 0);
            return (
              <div key={type} className="bg-white border rounded-lg p-4">
                <h3 className="font-medium text-gray-900 capitalize mb-3">{type.replace(/_/g, " ")}</h3>
                <div className="grid grid-cols-4 gap-3 text-center">
                  <div>
                    <div className="text-xs text-gray-500">Sent</div>
                    <div className="text-lg font-semibold">{String(d.total_sent ?? 0)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Completed</div>
                    <div className="text-lg font-semibold text-green-600">{String(d.completed ?? 0)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Pending</div>
                    <div className="text-lg font-semibold text-yellow-600">{String(d.pending ?? 0)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Rate</div>
                    <div className={`text-lg font-semibold ${rate >= 80 ? "text-green-600" : rate >= 50 ? "text-yellow-600" : "text-red-600"}`}>{rate.toFixed(0)}%</div>
                  </div>
                </div>
                <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${rate >= 80 ? "bg-green-500" : rate >= 50 ? "bg-yellow-500" : "bg-red-500"}`} style={{ width: `${rate}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Expiry Forecast */}
      {activeTab === "expiry" && !loading && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-600">Forecast window:</label>
            <select value={forecastDays} onChange={e => setForecastDays(Number(e.target.value))} className="border rounded px-2 py-1 text-sm">
              <option value={30}>30 days</option>
              <option value={60}>60 days</option>
              <option value={90}>90 days</option>
              <option value={180}>180 days</option>
            </select>
          </div>
          {expiryForecast && (() => {
            // summary can be an object {visa: N, dbs: N, ...} or an array
            const rawSummary = expiryForecast.summary;
            const summaryEntries: { type: string; count: number }[] = Array.isArray(rawSummary)
              ? (rawSummary as Record<string, unknown>[]).map(s => ({ type: String(s.type), count: Number(s.count ?? 0) }))
              : typeof rawSummary === "object" && rawSummary
                ? Object.entries(rawSummary as Record<string, unknown>)
                    .filter(([k]) => k !== "total")
                    .map(([k, v]) => ({ type: k, count: Number(v ?? 0) }))
                : [];

            // forecasts can be a flat array or an object grouped by type {visa: [...], dbs: [...]}
            const rawForecasts = expiryForecast.forecasts;
            const flatForecasts: Record<string, unknown>[] = Array.isArray(rawForecasts)
              ? rawForecasts
              : typeof rawForecasts === "object" && rawForecasts
                ? Object.entries(rawForecasts as Record<string, unknown[]>).flatMap(([type, items]) =>
                    (items || []).map((item: unknown) => ({ ...(item as Record<string, unknown>), type }))
                  )
                : [];

            return (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {summaryEntries.map(s => (
                    <div key={s.type} className="bg-white border rounded-lg p-4">
                      <div className="text-sm text-gray-500 capitalize">{s.type.replace(/_/g, " ")}</div>
                      <div className={`text-2xl font-bold ${s.count > 0 ? "text-orange-600" : "text-gray-400"}`}>{s.count}</div>
                      <div className="text-xs text-gray-400">expiring in {forecastDays} days</div>
                    </div>
                  ))}
                </div>
                {flatForecasts.length > 0 && (
                  <div className="bg-white border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="text-left px-3 py-2">Type</th>
                          <th className="text-left px-3 py-2">Candidate</th>
                          <th className="text-left px-3 py-2">Expires</th>
                          <th className="text-left px-3 py-2">Days Left</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {flatForecasts.map((f, i) => {
                          const expiryStr = String(f.expiry ?? f.expiry_date ?? "");
                          const daysLeft = f.days_until_expiry != null
                            ? Number(f.days_until_expiry)
                            : expiryStr ? Math.ceil((new Date(expiryStr).getTime() - Date.now()) / 86400000) : 0;
                          return (
                            <tr key={i} className="hover:bg-gray-50">
                              <td className="px-3 py-2 capitalize">{String(f.type ?? "").replace(/_/g, " ")}</td>
                              <td className="px-3 py-2">{String(f.name ?? f.candidate_id ?? "").slice(0, 30)}</td>
                              <td className="px-3 py-2">{expiryStr ? new Date(expiryStr).toLocaleDateString() : ""}</td>
                              <td className="px-3 py-2">
                                <span className={`font-medium ${daysLeft <= 14 ? "text-red-600" : daysLeft <= 30 ? "text-orange-600" : "text-green-600"}`}>
                                  {daysLeft}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
                {flatForecasts.length === 0 && summaryEntries.every(s => s.count === 0) && (
                  <div className="text-center py-8 text-gray-400">No upcoming expiries in the next {forecastDays} days</div>
                )}
              </>
            );
          })()}
        </div>
      )}

      {/* Check Volume Trend */}
      {activeTab === "volume" && !loading && (
        <div className="bg-white border rounded-lg p-4">
          <h3 className="font-medium text-gray-900 mb-4">Monthly Check Volume (Last 6 Months)</h3>
          {volumeTrend.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={volumeTrend}>
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="checks" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center py-8 text-gray-400">No volume data available</div>
          )}
          {volumeTrend.length > 0 && (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={volumeTrend}>
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="checks" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      {/* Scheduled Reports */}
      {activeTab === "reports" && !loading && (
        <div className="space-y-4">
          <div className="bg-white border rounded-lg p-4">
            <h3 className="font-medium text-gray-900 mb-3">Create Scheduled Report</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <select value={newReport.report_type} onChange={e => setNewReport(r => ({ ...r, report_type: e.target.value }))} className="border rounded px-2 py-1.5 text-sm">
                <option value="compliance_summary">Compliance Summary</option>
                <option value="expiry_forecast">Expiry Forecast</option>
                <option value="check_volume">Check Volume</option>
                <option value="full_audit">Full Audit Report</option>
              </select>
              <select value={newReport.frequency} onChange={e => setNewReport(r => ({ ...r, frequency: e.target.value }))} className="border rounded px-2 py-1.5 text-sm">
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
              <input type="text" placeholder="Recipients (comma-separated emails)" value={newReport.recipients}
                onChange={e => setNewReport(r => ({ ...r, recipients: e.target.value }))} className="border rounded px-2 py-1.5 text-sm" />
              <button onClick={handleCreateReport} disabled={creatingReport}
                className="flex items-center justify-center gap-1 bg-blue-600 text-white rounded px-3 py-1.5 text-sm hover:bg-blue-700 disabled:opacity-50">
                <Plus className="w-4 h-4" /> Create
              </button>
            </div>
          </div>

          <div className="bg-white border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2">Report Type</th>
                  <th className="text-left px-3 py-2">Frequency</th>
                  <th className="text-left px-3 py-2">Recipients</th>
                  <th className="text-left px-3 py-2">Next Send</th>
                  <th className="text-left px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {scheduledReports.map((r: Record<string, unknown>) => (
                  <tr key={String(r.id)} className="hover:bg-gray-50">
                    <td className="px-3 py-2 capitalize">{String(r.report_type ?? "").replace(/_/g, " ")}</td>
                    <td className="px-3 py-2 capitalize">{String(r.frequency ?? "")}</td>
                    <td className="px-3 py-2 text-xs">{JSON.stringify(r.recipients)}</td>
                    <td className="px-3 py-2 text-xs">{String(r.next_send_at ?? "N/A")}</td>
                    <td className="px-3 py-2">
                      <button onClick={() => handleDeleteReport(String(r.id))} className="text-red-600 hover:text-red-800">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
                {scheduledReports.length === 0 && (
                  <tr><td colSpan={5} className="px-3 py-4 text-center text-gray-400">No scheduled reports</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
