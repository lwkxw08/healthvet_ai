import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { webhookManagementApi } from "../api/client";
import {
  Webhook, RefreshCw, AlertTriangle, CheckCircle, XCircle, Clock,
  RotateCcw, Play, Zap,
} from "lucide-react";

export default function WebhookDeliveryDashboard() {
  const { token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);
  const [failedDeliveries, setFailedDeliveries] = useState<Record<string, unknown> | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "failed">("overview");
  const [retrying, setRetrying] = useState("");
  const [processingRetries, setProcessingRetries] = useState(false);

  const loadDashboard = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await webhookManagementApi.getDashboard(token);
      setDashboard(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token]);

  const loadFailed = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await webhookManagementApi.getFailed(token);
      setFailedDeliveries(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => {
    if (activeTab === "overview") loadDashboard();
    else loadFailed();
  }, [activeTab, loadDashboard, loadFailed]);

  const handleRetry = async (deliveryId: string) => {
    if (!token) return;
    setRetrying(deliveryId);
    try {
      await webhookManagementApi.retryDelivery(token, deliveryId);
      if (activeTab === "overview") loadDashboard();
      else loadFailed();
    } catch { /* ignore */ }
    finally { setRetrying(""); }
  };

  const handleReplay = async (deliveryId: string) => {
    if (!token) return;
    setRetrying(deliveryId);
    try {
      await webhookManagementApi.replayDelivery(token, deliveryId);
      if (activeTab === "overview") loadDashboard();
      else loadFailed();
    } catch { /* ignore */ }
    finally { setRetrying(""); }
  };

  const handleProcessRetries = async () => {
    if (!token) return;
    setProcessingRetries(true);
    try {
      await webhookManagementApi.processRetries(token);
      loadDashboard();
    } catch { /* ignore */ }
    finally { setProcessingRetries(false); }
  };

  const stats = dashboard?.stats as Record<string, unknown> | undefined;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Webhook className="w-5 h-5" /> Webhook Delivery Dashboard
        </h2>
        <button onClick={handleProcessRetries} disabled={processingRetries}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
          <Zap className="w-4 h-4" /> {processingRetries ? "Processing..." : "Process Pending Retries"}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 overflow-x-auto scrollbar-hide">
        <button onClick={() => setActiveTab("overview")}
          className={`px-4 py-2 text-sm border-b-2 ${activeTab === "overview" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
          All Deliveries
        </button>
        <button onClick={() => setActiveTab("failed")}
          className={`px-4 py-2 text-sm border-b-2 ${activeTab === "failed" ? "border-red-600 text-red-600" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
          Failed Deliveries
        </button>
      </div>

      {loading && <div className="text-center py-8 text-gray-500"><RefreshCw className="w-5 h-5 animate-spin inline-block mr-2" />Loading...</div>}

      {/* Stats Cards */}
      {stats && !loading && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-white border rounded-lg p-3">
            <div className="text-xs text-gray-500">Total</div>
            <div className="text-xl font-bold text-gray-900">{String(stats.total ?? 0)}</div>
          </div>
          <div className="bg-white border rounded-lg p-3">
            <div className="text-xs text-gray-500 flex items-center gap-1"><CheckCircle className="w-3 h-3 text-green-500" /> Delivered</div>
            <div className="text-xl font-bold text-green-600">{String(stats.delivered ?? 0)}</div>
          </div>
          <div className="bg-white border rounded-lg p-3">
            <div className="text-xs text-gray-500 flex items-center gap-1"><XCircle className="w-3 h-3 text-red-500" /> Failed</div>
            <div className="text-xl font-bold text-red-600">{String(stats.failed ?? 0)}</div>
          </div>
          <div className="bg-white border rounded-lg p-3">
            <div className="text-xs text-gray-500 flex items-center gap-1"><Clock className="w-3 h-3 text-yellow-500" /> Pending</div>
            <div className="text-xl font-bold text-yellow-600">{String(stats.pending ?? 0)}</div>
          </div>
          <div className="bg-white border rounded-lg p-3">
            <div className="text-xs text-gray-500">Success Rate</div>
            <div className="text-xl font-bold text-blue-600">{Number(stats.success_rate ?? 0).toFixed(1)}%</div>
          </div>
        </div>
      )}

      {/* Deliveries Table */}
      {!loading && (
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-3 py-2">ID</th>
                <th className="text-left px-3 py-2">Event</th>
                <th className="text-left px-3 py-2">Status</th>
                <th className="text-left px-3 py-2">Attempts</th>
                <th className="text-left px-3 py-2">Last Attempt</th>
                <th className="text-left px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {(activeTab === "overview"
                ? (dashboard?.deliveries as Record<string, unknown>[]) || []
                : (failedDeliveries?.deliveries as Record<string, unknown>[]) || []
              ).map((d: Record<string, unknown>) => (
                <tr key={String(d.id)} className="hover:bg-gray-50">
                  <td className="px-3 py-2 font-mono text-xs">{String(d.id ?? "").slice(0, 8)}</td>
                  <td className="px-3 py-2">{String(d.event_type ?? "")}</td>
                  <td className="px-3 py-2">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium
                      ${d.status === "delivered" ? "bg-green-100 text-green-700" :
                        d.status === "failed" ? "bg-red-100 text-red-700" :
                        d.status === "dead_letter" ? "bg-gray-100 text-gray-700" :
                        "bg-yellow-100 text-yellow-700"}`}>
                      {d.status === "delivered" ? <CheckCircle className="w-3 h-3" /> :
                       d.status === "failed" ? <XCircle className="w-3 h-3" /> :
                       <AlertTriangle className="w-3 h-3" />}
                      {String(d.status ?? "")}
                    </span>
                  </td>
                  <td className="px-3 py-2">{String(d.attempt ?? 0)}/{String(d.max_retries ?? 6)}</td>
                  <td className="px-3 py-2 text-xs text-gray-500">{String(d.last_attempt_at ?? d.created_at ?? "")}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1">
                      {(d.status === "failed" || d.status === "pending_retry") && (
                        <button onClick={() => handleRetry(String(d.id))} disabled={retrying === String(d.id)}
                          className="p-1 text-blue-600 hover:text-blue-800 disabled:opacity-50" title="Retry">
                          <RotateCcw className="w-4 h-4" />
                        </button>
                      )}
                      <button onClick={() => handleReplay(String(d.id))} disabled={retrying === String(d.id)}
                        className="p-1 text-purple-600 hover:text-purple-800 disabled:opacity-50" title="Replay">
                        <Play className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {((activeTab === "overview" ? (dashboard?.deliveries as Record<string, unknown>[]) : (failedDeliveries?.deliveries as Record<string, unknown>[])) || []).length === 0 && (
                <tr><td colSpan={6} className="px-3 py-8 text-center text-gray-400">No webhook deliveries found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
