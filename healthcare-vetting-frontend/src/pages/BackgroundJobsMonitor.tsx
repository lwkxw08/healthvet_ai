import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { jobMonitorApi } from "../api/client";
import {
  Cpu, RefreshCw, CheckCircle, XCircle, Clock, AlertTriangle,
  RotateCcw, Trash2, Play, StopCircle, Server,
} from "lucide-react";

export default function BackgroundJobsMonitor() {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState<"dashboard" | "dead-letter" | "workers">("dashboard");
  const [loading, setLoading] = useState(false);

  // Dashboard state
  const [jobDashboard, setJobDashboard] = useState<Record<string, unknown> | null>(null);
  const [statusFilter, setStatusFilter] = useState("");

  // Dead letter state
  const [deadLetter, setDeadLetter] = useState<Record<string, unknown> | null>(null);

  // Workers state
  const [workers, setWorkers] = useState<Record<string, unknown> | null>(null);

  // Action states
  const [actionId, setActionId] = useState("");
  const [cleaningUp, setCleaningUp] = useState(false);

  const loadDashboard = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      const data = await jobMonitorApi.getDashboard(token, params);
      setJobDashboard(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token, statusFilter]);

  const loadDeadLetter = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await jobMonitorApi.getDeadLetter(token);
      setDeadLetter(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token]);

  const loadWorkers = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await jobMonitorApi.getWorkers(token);
      setWorkers(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => {
    if (activeTab === "dashboard") loadDashboard();
    else if (activeTab === "dead-letter") loadDeadLetter();
    else if (activeTab === "workers") loadWorkers();
  }, [activeTab, loadDashboard, loadDeadLetter, loadWorkers]);

  const handleCancel = async (jobId: string) => {
    if (!token) return;
    setActionId(jobId);
    try {
      await jobMonitorApi.cancelJob(token, jobId);
      loadDashboard();
    } catch { /* ignore */ }
    finally { setActionId(""); }
  };

  const handleRetryDeadLetter = async (jobId: string) => {
    if (!token) return;
    setActionId(jobId);
    try {
      await jobMonitorApi.retryDeadLetter(token, jobId);
      loadDeadLetter();
    } catch { /* ignore */ }
    finally { setActionId(""); }
  };

  const handleCleanup = async () => {
    if (!token) return;
    setCleaningUp(true);
    try {
      await jobMonitorApi.cleanup(token, 30);
      loadDashboard();
    } catch { /* ignore */ }
    finally { setCleaningUp(false); }
  };

  const summary = (jobDashboard?.stats ?? jobDashboard?.summary) as Record<string, unknown> | undefined;

  const statusColors: Record<string, string> = {
    queued: "bg-gray-100 text-gray-700",
    running: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
    dead_letter: "bg-purple-100 text-purple-700",
    cancelled: "bg-yellow-100 text-yellow-700",
  };

  const statusIcons: Record<string, typeof CheckCircle> = {
    queued: Clock,
    running: RefreshCw,
    completed: CheckCircle,
    failed: XCircle,
    dead_letter: AlertTriangle,
    cancelled: StopCircle,
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Cpu className="w-5 h-5" /> Background Jobs Monitor
        </h2>
        <button onClick={handleCleanup} disabled={cleaningUp}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-gray-600 text-white rounded hover:bg-gray-700 disabled:opacity-50">
          <Trash2 className="w-4 h-4" /> {cleaningUp ? "Cleaning..." : "Cleanup Old Jobs"}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 overflow-x-auto scrollbar-hide">
        <button onClick={() => setActiveTab("dashboard")}
          className={`flex items-center gap-1.5 px-4 py-2 text-sm border-b-2 ${activeTab === "dashboard" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
          <Cpu className="w-4 h-4" /> Job Queue
        </button>
        <button onClick={() => setActiveTab("dead-letter")}
          className={`flex items-center gap-1.5 px-4 py-2 text-sm border-b-2 ${activeTab === "dead-letter" ? "border-red-600 text-red-600" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
          <AlertTriangle className="w-4 h-4" /> Dead Letter Queue
        </button>
        <button onClick={() => setActiveTab("workers")}
          className={`flex items-center gap-1.5 px-4 py-2 text-sm border-b-2 ${activeTab === "workers" ? "border-green-600 text-green-600" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
          <Server className="w-4 h-4" /> Workers
        </button>
      </div>

      {loading && <div className="text-center py-8 text-gray-500"><RefreshCw className="w-5 h-5 animate-spin inline-block mr-2" />Loading...</div>}

      {/* Dashboard */}
      {activeTab === "dashboard" && !loading && (
        <div className="space-y-4">
          {/* Summary Cards */}
          {summary && (
            <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
              {["queued", "running", "completed", "failed", "dead_letter", "cancelled"].map(status => {
                const Icon = statusIcons[status] || Clock;
                return (
                  <div key={status} className="bg-white border rounded-lg p-3 cursor-pointer hover:border-blue-300"
                    onClick={() => setStatusFilter(statusFilter === status ? "" : status)}>
                    <div className="flex items-center gap-1 text-xs text-gray-500 mb-1">
                      <Icon className="w-3 h-3" /> {status.replace(/_/g, " ")}
                    </div>
                    <div className="text-xl font-bold">{String(summary[status] ?? 0)}</div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Status filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Filter:</span>
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="border rounded px-2 py-1 text-sm">
              <option value="">All</option>
              <option value="queued">Queued</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="dead_letter">Dead Letter</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <button onClick={loadDashboard} className="p-1 text-gray-500 hover:text-gray-700">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>

          {/* Jobs Table */}
          <div className="bg-white border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2">ID</th>
                  <th className="text-left px-3 py-2">Task</th>
                  <th className="text-left px-3 py-2">Status</th>
                  <th className="text-left px-3 py-2">Priority</th>
                  <th className="text-left px-3 py-2">Attempt</th>
                  <th className="text-left px-3 py-2">Created</th>
                  <th className="text-left px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {((jobDashboard?.jobs as Record<string, unknown>[]) || []).map((job: Record<string, unknown>) => {
                  const Icon = statusIcons[String(job.status)] || Clock;
                  return (
                    <tr key={String(job.id)} className="hover:bg-gray-50">
                      <td className="px-3 py-2 font-mono text-xs">{String(job.id ?? "").slice(0, 8)}</td>
                      <td className="px-3 py-2 text-xs">{String(job.task_name ?? "")}</td>
                      <td className="px-3 py-2">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[String(job.status)] || "bg-gray-100 text-gray-700"}`}>
                          <Icon className="w-3 h-3" /> {String(job.status ?? "")}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-center">{String(job.priority ?? 5)}</td>
                      <td className="px-3 py-2 text-center">{String(job.attempt ?? 0)}/{String(job.max_retries ?? 3)}</td>
                      <td className="px-3 py-2 text-xs text-gray-500">{String(job.created_at ?? "")}</td>
                      <td className="px-3 py-2">
                        {(job.status === "queued" || job.status === "running") && (
                          <button onClick={() => handleCancel(String(job.id))} disabled={actionId === String(job.id)}
                            className="p-1 text-red-600 hover:text-red-800 disabled:opacity-50" title="Cancel">
                            <StopCircle className="w-4 h-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {((jobDashboard?.jobs as Record<string, unknown>[]) || []).length === 0 && (
                  <tr><td colSpan={7} className="px-3 py-8 text-center text-gray-400">No jobs found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Dead Letter Queue */}
      {activeTab === "dead-letter" && !loading && (
        <div className="space-y-3">
          <div className="text-sm text-gray-500">{String((deadLetter?.jobs as Record<string, unknown>[])?.length ?? 0)} permanently failed jobs</div>
          <div className="bg-white border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2">ID</th>
                  <th className="text-left px-3 py-2">Task</th>
                  <th className="text-left px-3 py-2">Error</th>
                  <th className="text-left px-3 py-2">Attempts</th>
                  <th className="text-left px-3 py-2">Failed At</th>
                  <th className="text-left px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {((deadLetter?.jobs as Record<string, unknown>[]) || []).map((job: Record<string, unknown>) => (
                  <tr key={String(job.id)} className="hover:bg-gray-50">
                    <td className="px-3 py-2 font-mono text-xs">{String(job.id ?? "").slice(0, 8)}</td>
                    <td className="px-3 py-2 text-xs">{String(job.task_name ?? "")}</td>
                    <td className="px-3 py-2 text-xs text-red-600 max-w-xs truncate">{String(job.error ?? "Unknown error")}</td>
                    <td className="px-3 py-2 text-center">{String(job.attempt ?? 0)}</td>
                    <td className="px-3 py-2 text-xs text-gray-500">{String(job.completed_at ?? job.created_at ?? "")}</td>
                    <td className="px-3 py-2">
                      <button onClick={() => handleRetryDeadLetter(String(job.id))} disabled={actionId === String(job.id)}
                        className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
                        <RotateCcw className="w-3 h-3" /> Retry
                      </button>
                    </td>
                  </tr>
                ))}
                {((deadLetter?.jobs as Record<string, unknown>[]) || []).length === 0 && (
                  <tr><td colSpan={6} className="px-3 py-8 text-center text-gray-400">Dead letter queue is empty</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Workers Status */}
      {activeTab === "workers" && !loading && workers && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-white border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Server className="w-5 h-5 text-blue-500" />
                <span className="font-medium text-gray-900">Broker</span>
              </div>
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${workers.broker === "celery" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>
                {workers.broker === "celery" ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                {String(workers.broker ?? "in-process")}
              </span>
            </div>
            <div className="bg-white border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Play className="w-5 h-5 text-green-500" />
                <span className="font-medium text-gray-900">Active Workers</span>
              </div>
              <div className="text-2xl font-bold">{String(workers.active_workers ?? 0)}</div>
            </div>
            <div className="bg-white border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Cpu className="w-5 h-5 text-purple-500" />
                <span className="font-medium text-gray-900">Flower Dashboard</span>
              </div>
              {workers.flower_url ? (
                <a href={String(workers.flower_url)} target="_blank" rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:underline">{String(workers.flower_url)}</a>
              ) : (
                <span className="text-sm text-gray-400">Not configured</span>
              )}
            </div>
          </div>

          {workers.workers && Array.isArray(workers.workers) && (workers.workers as Record<string, unknown>[]).length > 0 ? (
            <div className="bg-white border rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="text-left px-3 py-2">Worker</th>
                    <th className="text-left px-3 py-2">Status</th>
                    <th className="text-left px-3 py-2">Active Tasks</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {(workers.workers as Record<string, unknown>[]).map((w: Record<string, unknown>, i: number) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-3 py-2">{String(w.name ?? `Worker ${i + 1}`)}</td>
                      <td className="px-3 py-2">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                          <CheckCircle className="w-3 h-3" /> Active
                        </span>
                      </td>
                      <td className="px-3 py-2">{String(w.active_tasks ?? 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
