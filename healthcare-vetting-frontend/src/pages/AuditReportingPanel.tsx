import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { auditTrailApi } from "../api/client";
import {
  Shield, RefreshCw, CheckCircle, XCircle, Download, Search,
  FileText, Lock, Clock, Database,
} from "lucide-react";

export default function AuditReportingPanel() {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState<"audit-log" | "integrity" | "data-access" | "cqc" | "sar" | "retention">("audit-log");
  const [loading, setLoading] = useState(false);

  // Audit log state
  const [auditLog, setAuditLog] = useState<Record<string, unknown> | null>(null);
  const [auditFilters, setAuditFilters] = useState({ entity_type: "", action: "", actor: "", limit: "50", offset: "0" });

  // Integrity state
  const [integrityResult, setIntegrityResult] = useState<Record<string, unknown> | null>(null);

  // Data access log state
  const [dataAccessLog, setDataAccessLog] = useState<Record<string, unknown> | null>(null);

  // CQC export state
  const [cqcReport, setCqcReport] = useState<Record<string, unknown> | null>(null);
  const [cqcDateFrom, setCqcDateFrom] = useState("");
  const [cqcDateTo, setCqcDateTo] = useState("");

  // SAR state
  const [sarEmail, setSarEmail] = useState("");
  const [sarReport, setSarReport] = useState<Record<string, unknown> | null>(null);

  // Retention state
  const [retentionReport, setRetentionReport] = useState<Record<string, unknown> | null>(null);

  const loadAuditLog = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (auditFilters.entity_type) params.entity_type = auditFilters.entity_type;
      if (auditFilters.action) params.action = auditFilters.action;
      if (auditFilters.actor) params.actor = auditFilters.actor;
      params.limit = auditFilters.limit;
      params.offset = auditFilters.offset;
      const data = await auditTrailApi.getLog(token, params);
      setAuditLog(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token, auditFilters]);

  const loadIntegrity = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await auditTrailApi.verifyIntegrity(token);
      setIntegrityResult(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token]);

  const loadDataAccess = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await auditTrailApi.getDataAccessLog(token);
      setDataAccessLog(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token]);

  const loadRetention = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await auditTrailApi.getRetentionReport(token);
      setRetentionReport(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => {
    if (activeTab === "audit-log") loadAuditLog();
    else if (activeTab === "integrity") loadIntegrity();
    else if (activeTab === "data-access") loadDataAccess();
    else if (activeTab === "retention") loadRetention();
  }, [activeTab, loadAuditLog, loadIntegrity, loadDataAccess, loadRetention]);

  const handleCqcExport = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (cqcDateFrom) params.date_from = cqcDateFrom;
      if (cqcDateTo) params.date_to = cqcDateTo;
      const data = await auditTrailApi.exportCqc(token, params);
      setCqcReport(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  const handleSarSearch = async () => {
    if (!token || !sarEmail) return;
    setLoading(true);
    try {
      const data = await auditTrailApi.getSarReport(token, sarEmail);
      setSarReport(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  const tabs = [
    { id: "audit-log" as const, label: "Audit Log", icon: FileText },
    { id: "integrity" as const, label: "Chain Integrity", icon: Lock },
    { id: "data-access" as const, label: "Data Access Log", icon: Database },
    { id: "cqc" as const, label: "CQC Export", icon: Download },
    { id: "sar" as const, label: "SAR Reports", icon: Search },
    { id: "retention" as const, label: "Retention", icon: Clock },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Shield className="w-5 h-5" /> Audit Trail & Compliance
        </h2>
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

      {/* Audit Log */}
      {activeTab === "audit-log" && !loading && (
        <div className="space-y-3">
          <div className="bg-white border rounded-lg p-3">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <input type="text" placeholder="Entity type" value={auditFilters.entity_type}
                onChange={e => setAuditFilters(f => ({ ...f, entity_type: e.target.value }))}
                className="border rounded px-2 py-1.5 text-sm" />
              <input type="text" placeholder="Action (create, update, delete)" value={auditFilters.action}
                onChange={e => setAuditFilters(f => ({ ...f, action: e.target.value }))}
                className="border rounded px-2 py-1.5 text-sm" />
              <input type="text" placeholder="Actor" value={auditFilters.actor}
                onChange={e => setAuditFilters(f => ({ ...f, actor: e.target.value }))}
                className="border rounded px-2 py-1.5 text-sm" />
              <button onClick={loadAuditLog} className="bg-blue-600 text-white rounded px-3 py-1.5 text-sm hover:bg-blue-700">
                Search
              </button>
            </div>
          </div>

          {auditLog && (
            <>
              <div className="text-sm text-gray-500">Showing {String(((auditLog.items ?? auditLog.logs) as Record<string, unknown>[])?.length ?? 0)} of {String(auditLog.total ?? 0)} entries</div>
              <div className="bg-white border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left px-3 py-2">Timestamp</th>
                      <th className="text-left px-3 py-2">Entity</th>
                      <th className="text-left px-3 py-2">Action</th>
                      <th className="text-left px-3 py-2">Actor</th>
                      <th className="text-left px-3 py-2">IP</th>
                      <th className="text-left px-3 py-2">Hash</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {(((auditLog.items ?? auditLog.logs) as Record<string, unknown>[]) || []).map((log: Record<string, unknown>) => (
                      <tr key={String(log.id)} className="hover:bg-gray-50">
                        <td className="px-3 py-2 text-xs text-gray-500">{String(log.created_at ?? "")}</td>
                        <td className="px-3 py-2">
                          <span className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{String(log.entity_type ?? "")}</span>
                          <span className="text-xs text-gray-400 ml-1">{String(log.entity_id ?? "").slice(0, 8)}</span>
                        </td>
                        <td className="px-3 py-2">
                          <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium
                            ${log.action === "create" ? "bg-green-100 text-green-700" :
                              log.action === "update" ? "bg-blue-100 text-blue-700" :
                              log.action === "delete" ? "bg-red-100 text-red-700" :
                              "bg-gray-100 text-gray-700"}`}>
                            {String(log.action ?? "")}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-xs">{String(log.actor ?? "")}<span className="text-gray-400 ml-1">({String(log.actor_type ?? "")})</span></td>
                        <td className="px-3 py-2 text-xs text-gray-400">{String(log.ip_address ?? "N/A")}</td>
                        <td className="px-3 py-2 font-mono text-xs text-gray-400">{String(log.chain_hash ?? "").slice(0, 12)}...</td>
                      </tr>
                    ))}
                    {(((auditLog.items ?? auditLog.logs) as Record<string, unknown>[]) || []).length === 0 && (
                      <tr><td colSpan={6} className="px-3 py-8 text-center text-gray-400">No audit logs found</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* Chain Integrity */}
      {activeTab === "integrity" && !loading && integrityResult && (
        <div className="bg-white border rounded-lg p-6 text-center">
          {integrityResult.status === "intact" ? (
            <>
              <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-green-700 mb-2">Audit Chain Intact</h3>
              <p className="text-gray-500">All {String(integrityResult.verified ?? 0)} log entries verified. No tampering detected.</p>
            </>
          ) : integrityResult.status === "empty" ? (
            <>
              <Shield className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-gray-600 mb-2">Audit Trail Empty</h3>
              <p className="text-gray-500">No audit log entries have been recorded yet. The chain integrity check will verify entries once audit events are generated.</p>
            </>
          ) : (
            <>
              <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-red-700 mb-2">Chain Integrity Broken</h3>
              <p className="text-gray-500">
                Integrity broken at entry {String(integrityResult.broken_at ?? "unknown")}.
                {String(integrityResult.verified ?? 0)} entries verified before break.
              </p>
            </>
          )}
          <button onClick={loadIntegrity} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
            <RefreshCw className="w-4 h-4 inline mr-1" /> Re-verify
          </button>
        </div>
      )}

      {/* Data Access Log */}
      {activeTab === "data-access" && !loading && dataAccessLog && (
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-3 py-2">Timestamp</th>
                <th className="text-left px-3 py-2">Entity</th>
                <th className="text-left px-3 py-2">Accessor</th>
                <th className="text-left px-3 py-2">Purpose</th>
                <th className="text-left px-3 py-2">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {(((dataAccessLog.items ?? dataAccessLog.logs) as Record<string, unknown>[]) || []).map((log: Record<string, unknown>) => (
                <tr key={String(log.id)} className="hover:bg-gray-50">
                  <td className="px-3 py-2 text-xs text-gray-500">{String(log.created_at ?? "")}</td>
                  <td className="px-3 py-2">
                    <span className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{String(log.entity_type ?? "")}</span>
                    <span className="text-xs text-gray-400 ml-1">{String(log.entity_id ?? "").slice(0, 8)}</span>
                  </td>
                  <td className="px-3 py-2 text-xs">{String(log.accessor ?? "")}<span className="text-gray-400 ml-1">({String(log.accessor_type ?? "")})</span></td>
                  <td className="px-3 py-2 text-xs">{String(log.purpose ?? "N/A")}</td>
                  <td className="px-3 py-2 text-xs text-gray-400">{String(log.ip_address ?? "N/A")}</td>
                </tr>
              ))}
              {(((dataAccessLog.items ?? dataAccessLog.logs) as Record<string, unknown>[]) || []).length === 0 && (
                <tr><td colSpan={5} className="px-3 py-8 text-center text-gray-400">No data access logs found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* CQC Export */}
      {activeTab === "cqc" && !loading && (
        <div className="space-y-4">
          <div className="bg-white border rounded-lg p-4">
            <h3 className="font-medium text-gray-900 mb-3">Generate CQC Audit Export</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-gray-500">From Date</label>
                <input type="date" value={cqcDateFrom} onChange={e => setCqcDateFrom(e.target.value)} className="w-full border rounded px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="text-xs text-gray-500">To Date</label>
                <input type="date" value={cqcDateTo} onChange={e => setCqcDateTo(e.target.value)} className="w-full border rounded px-2 py-1.5 text-sm" />
              </div>
              <div className="flex items-end">
                <button onClick={handleCqcExport} className="flex items-center gap-1 bg-blue-600 text-white rounded px-4 py-1.5 text-sm hover:bg-blue-700">
                  <Download className="w-4 h-4" /> Generate Report
                </button>
              </div>
            </div>
          </div>
          {cqcReport && (
            <div className="bg-white border rounded-lg p-4">
              <h4 className="font-medium text-gray-900 mb-2">CQC Audit Report</h4>
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="text-center p-3 bg-gray-50 rounded">
                  <div className="text-xs text-gray-500">Total Mutations</div>
                  <div className="text-xl font-bold">{String(cqcReport.total_mutations ?? 0)}</div>
                </div>
                <div className="text-center p-3 bg-gray-50 rounded">
                  <div className="text-xs text-gray-500">Total Access</div>
                  <div className="text-xl font-bold">{String(cqcReport.total_data_access ?? 0)}</div>
                </div>
                <div className="text-center p-3 bg-gray-50 rounded">
                  <div className="text-xs text-gray-500">Chain Integrity</div>
                  <div className={`text-xl font-bold ${cqcReport.chain_integrity === "intact" ? "text-green-600" : "text-red-600"}`}>
                    {String(cqcReport.chain_integrity ?? "unknown")}
                  </div>
                </div>
              </div>
              <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-64">{JSON.stringify(cqcReport, null, 2)}</pre>
            </div>
          )}
        </div>
      )}

      {/* SAR Reports */}
      {activeTab === "sar" && !loading && (
        <div className="space-y-4">
          <div className="bg-white border rounded-lg p-4">
            <h3 className="font-medium text-gray-900 mb-3">Subject Access Request (GDPR)</h3>
            <div className="flex gap-3">
              <input type="email" placeholder="Candidate email address" value={sarEmail}
                onChange={e => setSarEmail(e.target.value)} className="flex-1 border rounded px-3 py-1.5 text-sm" />
              <button onClick={handleSarSearch} className="flex items-center gap-1 bg-blue-600 text-white rounded px-4 py-1.5 text-sm hover:bg-blue-700">
                <Search className="w-4 h-4" /> Generate SAR
              </button>
            </div>
          </div>
          {sarReport && (
            <div className="bg-white border rounded-lg p-4">
              <h4 className="font-medium text-gray-900 mb-2">SAR Report for {String(sarReport.candidate_email ?? sarEmail)}</h4>
              <div className="space-y-3">
                <div>
                  <h5 className="text-sm font-medium text-gray-700 mb-1">Personal Data</h5>
                  <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-40">{JSON.stringify(sarReport.personal_data ?? {}, null, 2)}</pre>
                </div>
                <div>
                  <h5 className="text-sm font-medium text-gray-700 mb-1">Processing Activities ({String((sarReport.processing_activities as Record<string, unknown>[])?.length ?? 0)})</h5>
                  <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-40">{JSON.stringify(sarReport.processing_activities ?? [], null, 2)}</pre>
                </div>
                <div>
                  <h5 className="text-sm font-medium text-gray-700 mb-1">Data Access History ({String((sarReport.data_access_history as Record<string, unknown>[])?.length ?? 0)})</h5>
                  <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-40">{JSON.stringify(sarReport.data_access_history ?? [], null, 2)}</pre>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Retention Report */}
      {activeTab === "retention" && !loading && retentionReport && (
        <div className="bg-white border rounded-lg p-4 space-y-4">
          <h3 className="font-medium text-gray-900">Retention Policy Report</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="text-center p-3 bg-gray-50 rounded">
              <div className="text-xs text-gray-500">Total Audit Entries</div>
              <div className="text-xl font-bold">{String(retentionReport.total_audit_entries ?? 0)}</div>
            </div>
            <div className="text-center p-3 bg-gray-50 rounded">
              <div className="text-xs text-gray-500">Oldest Entry</div>
              <div className="text-sm font-semibold">{String(retentionReport.oldest_entry ?? "N/A")}</div>
            </div>
            <div className="text-center p-3 bg-gray-50 rounded">
              <div className="text-xs text-gray-500">Data Access Entries</div>
              <div className="text-xl font-bold">{String(retentionReport.total_data_access_entries ?? 0)}</div>
            </div>
            <div className="text-center p-3 bg-gray-50 rounded">
              <div className="text-xs text-gray-500">Retention Period</div>
              <div className="text-sm font-semibold">{String(retentionReport.retention_period ?? "7 years")}</div>
            </div>
          </div>
          {retentionReport.age_distribution ? (
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Age Distribution</h4>
              <div className="grid grid-cols-3 gap-2">
                {Object.entries(retentionReport.age_distribution as Record<string, unknown>).map(([period, count]) => (
                  <div key={period} className="bg-gray-50 rounded p-2 text-center">
                    <div className="text-xs text-gray-500">{period}</div>
                    <div className="font-semibold">{String(count)}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
