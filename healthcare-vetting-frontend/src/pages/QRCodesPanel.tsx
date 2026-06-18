/**
 * QR Codes & Expo Lead Generation Panel
 *
 * Admin can create QR codes, view scan analytics, and manage expo leads.
 */
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { qrApi } from "../api/client";
import {
  QrCode, Plus, Trash2, BarChart3, Users, Eye,
  Copy, ExternalLink, TrendingUp, Download, X,
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "https://api.viperai.io";

const MARKETING_URL = import.meta.env.VITE_MARKETING_URL || "https://viperai.io";

export default function QRCodesPanel() {
  const { token } = useAuth();
  const [codes, setCodes] = useState<Record<string, unknown>[]>([]);
  const [analytics, setAnalytics] = useState<Record<string, unknown> | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCampaign, setNewCampaign] = useState("");
  const [newEvent, setNewEvent] = useState("");
  const [creating, setCreating] = useState(false);
  const [activeView, setActiveView] = useState<"codes" | "analytics" | "leads">("codes");
  const [showQrImage, setShowQrImage] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      const [codesData, analyticsData] = await Promise.all([
        qrApi.listCodes(token),
        qrApi.getAnalytics(token),
      ]);
      setCodes(codesData);
      setAnalytics(analyticsData);
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);

  const createCode = async () => {
    if (!token || !newName.trim()) return;
    setCreating(true);
    try {
      await qrApi.createCode(token, {
        name: newName.trim(),
        campaign: newCampaign.trim() || undefined,
        event_name: newEvent.trim() || undefined,
      });
      setNewName("");
      setNewCampaign("");
      setNewEvent("");
      setShowCreate(false);
      loadData();
    } catch { /* ignore */ }
    finally { setCreating(false); }
  };

  const deleteCode = async (qrId: string) => {
    if (!token || !confirm("Delete this QR code?")) return;
    try {
      await qrApi.deleteCode(token, qrId);
      loadData();
    } catch { /* ignore */ }
  };

  const copyUrl = (code: string) => {
    const url = `${MARKETING_URL}/expo?qr=${code}`;
    navigator.clipboard.writeText(url);
  };

  const downloadQrImage = (code: string, name: string) => {
    const url = `${API_URL}/api/qr/codes/${code}/qr-image`;
    const a = document.createElement("a");
    a.href = url;
    a.download = `QR-${name.replace(/\s+/g, "-")}-${code}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const recentLeads = (analytics?.recent_leads ?? []) as Record<string, unknown>[];
  const recentScans = (analytics?.recent_scans ?? []) as Record<string, unknown>[];
  const dailyScans = (analytics?.daily_scans ?? []) as Record<string, unknown>[];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <QrCode className="text-blue-400" size={22} /> QR Codes & Expo Leads
        </h2>
        <button onClick={() => setShowCreate(!showCreate)}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
          <Plus size={16} /> Create QR Code
        </button>
      </div>

      {/* Stats Cards */}
      {analytics && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-4 text-center">
            <QrCode size={20} className="text-blue-400 mx-auto mb-2" />
            <p className="text-2xl font-bold text-white">{Number(analytics.total_codes || 0)}</p>
            <p className="text-xs text-slate-400">QR Codes</p>
          </div>
          <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-4 text-center">
            <Eye size={20} className="text-emerald-400 mx-auto mb-2" />
            <p className="text-2xl font-bold text-emerald-400">{Number(analytics.total_scans || 0)}</p>
            <p className="text-xs text-slate-400">Total Scans</p>
          </div>
          <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-4 text-center">
            <Users size={20} className="text-purple-400 mx-auto mb-2" />
            <p className="text-2xl font-bold text-purple-400">{Number(analytics.total_leads || 0)}</p>
            <p className="text-xs text-slate-400">Leads Captured</p>
          </div>
          <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-4 text-center">
            <TrendingUp size={20} className="text-amber-400 mx-auto mb-2" />
            <p className="text-2xl font-bold text-amber-400">{Number(analytics.conversion_rate || 0)}%</p>
            <p className="text-xs text-slate-400">Conversion Rate</p>
          </div>
        </div>
      )}

      {/* Create QR Code Form */}
      {showCreate && (
        <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
          <h3 className="text-md font-semibold text-white mb-4">Create New QR Code</h3>
          <div className="grid sm:grid-cols-3 gap-4 mb-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Name *</label>
              <input value={newName} onChange={e => setNewName(e.target.value)}
                placeholder="e.g. London Expo 2026"
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Campaign</label>
              <input value={newCampaign} onChange={e => setNewCampaign(e.target.value)}
                placeholder="e.g. Q3 Healthcare Events"
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Event Name</label>
              <input value={newEvent} onChange={e => setNewEvent(e.target.value)}
                placeholder="e.g. NHS Innovation Expo"
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm" />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={createCode} disabled={creating || !newName.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium">
              {creating ? "Creating..." : "Create"}
            </button>
            <button onClick={() => setShowCreate(false)}
              className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* View Tabs */}
      <div className="flex gap-2">
        {(["codes", "analytics", "leads"] as const).map(v => (
          <button key={v} onClick={() => setActiveView(v)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeView === v ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"
            }`}>
            {v === "codes" ? "QR Codes" : v === "analytics" ? "Scan Analytics" : "Expo Leads"}
          </button>
        ))}
      </div>

      {/* QR Codes List */}
      {activeView === "codes" && (
        <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-x-auto">
          <table className="w-full min-w-[700px]">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Name</th>
                <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Code</th>
                <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Campaign</th>
                <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Event</th>
                <th className="text-center text-xs text-slate-400 font-medium px-4 py-3">Scans</th>
                <th className="text-center text-xs text-slate-400 font-medium px-4 py-3">Leads</th>
                <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Created</th>
                <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {codes.map(c => {
                const code = String(c.code || "");
                const landingUrl = `${MARKETING_URL}/expo?qr=${code}`;
                return (
                  <tr key={String(c.id)} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-sm text-white font-medium">{String(c.name || "")}</td>
                    <td className="px-4 py-3">
                      <code className="text-xs bg-slate-700 text-blue-300 px-2 py-1 rounded">{code}</code>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-300">{String(c.campaign || "-")}</td>
                    <td className="px-4 py-3 text-sm text-slate-300">{String(c.event_name || "-")}</td>
                    <td className="px-4 py-3 text-sm text-center font-medium text-emerald-400">{Number(c.scan_count || 0)}</td>
                    <td className="px-4 py-3 text-sm text-center font-medium text-purple-400">{Number(c.lead_count || 0)}</td>
                    <td className="px-4 py-3 text-xs text-slate-400">{String(c.created_at || "").slice(0, 10)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button onClick={() => setShowQrImage(code)} title="View QR Code"
                          className="text-slate-400 hover:text-white"><QrCode size={14} /></button>
                        <button onClick={() => downloadQrImage(code, String(c.name || ""))} title="Download QR Code"
                          className="text-slate-400 hover:text-green-400"><Download size={14} /></button>
                        <button onClick={() => copyUrl(code)} title="Copy landing page URL"
                          className="text-slate-400 hover:text-blue-400"><Copy size={14} /></button>
                        <a href={landingUrl} target="_blank" rel="noopener noreferrer" title="Open landing page"
                          className="text-slate-400 hover:text-emerald-400"><ExternalLink size={14} /></a>
                        <button onClick={() => deleteCode(String(c.id))} title="Delete"
                          className="text-slate-400 hover:text-red-400"><Trash2 size={14} /></button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {codes.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-500 text-sm">No QR codes created yet. Click "Create QR Code" to get started.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Scan Analytics */}
      {activeView === "analytics" && (
        <div className="space-y-6">
          {/* Daily Scan Chart (simple bar representation) */}
          {dailyScans.length > 0 && (
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-md font-semibold text-white mb-4 flex items-center gap-2">
                <BarChart3 size={18} className="text-blue-400" /> Daily Scans (Last 30 Days)
              </h3>
              <div className="flex items-end gap-1" style={{ height: 128 }}>
                {dailyScans.slice(0, 30).reverse().map((d, i) => {
                  const count = Number(d.count || 0);
                  const maxCount = Math.max(...dailyScans.map(x => Number(x.count || 0)), 1);
                  const barH = Math.max(6, Math.round((count / maxCount) * 120));
                  return (
                    <div key={i} className="flex-1 min-w-[8px] group relative flex items-end" style={{ height: 128 }}>
                      <div className="w-full bg-blue-500 hover:bg-blue-400 rounded-t transition-all"
                        style={{ height: barH }} />
                      <div className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 bg-slate-700 text-white text-xs px-2 py-1 rounded mb-1 whitespace-nowrap z-10">
                        {String(d.scan_date || "")}: {count} scan{count !== 1 ? "s" : ""}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Recent Scans */}
          <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
            <h3 className="text-md font-semibold text-white mb-4">Recent Scans</h3>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {recentScans.map((scan, i) => (
                <div key={i} className="flex items-center justify-between bg-slate-700/50 rounded-lg px-3 py-2">
                  <div>
                    <span className="text-sm text-white font-medium">{String(scan.qr_name || "Unknown")}</span>
                    <span className="text-xs text-slate-400 ml-2">({String(scan.code || "")})</span>
                  </div>
                  <div className="text-xs text-slate-400">
                    {String(scan.scanned_at || "").replace("T", " ").slice(0, 19)}
                  </div>
                </div>
              ))}
              {recentScans.length === 0 && <p className="text-sm text-slate-500">No scans recorded yet.</p>}
            </div>
          </div>
        </div>
      )}

      {/* Expo Leads */}
      {/* QR Code Image Modal */}
      {showQrImage && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" onClick={() => setShowQrImage(null)}>
          <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 max-w-sm w-full mx-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-md font-semibold text-white">QR Code: {showQrImage}</h3>
              <button onClick={() => setShowQrImage(null)} className="text-slate-400 hover:text-white"><X size={18} /></button>
            </div>
            <div className="bg-white rounded-lg p-4 flex justify-center">
              <img src={`${API_URL}/api/qr/codes/${showQrImage}/qr-image`} alt="QR Code" className="w-64 h-64" />
            </div>
            <p className="text-xs text-slate-400 text-center mt-3">
              Scan this QR code with a phone camera to open the expo landing page
            </p>
            <div className="flex gap-2 mt-4">
              <button onClick={() => downloadQrImage(showQrImage, showQrImage)}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2">
                <Download size={14} /> Download PNG
              </button>
              <button onClick={() => { copyUrl(showQrImage); }}
                className="flex-1 bg-slate-700 hover:bg-slate-600 text-white px-3 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2">
                <Copy size={14} /> Copy URL
              </button>
            </div>
          </div>
        </div>
      )}

      {activeView === "leads" && (
        <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-x-auto">
          <table className="w-full min-w-[800px]">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Name</th>
                <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Email</th>
                <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Company</th>
                <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Industry</th>
                <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Checks/Month</th>
                <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">QR Source</th>
                <th className="text-left text-xs text-slate-400 font-medium px-4 py-3">Date</th>
              </tr>
            </thead>
            <tbody>
              {recentLeads.map((lead, i) => (
                <tr key={i} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                  <td className="px-4 py-3 text-sm text-white">{String(lead.name || "")}</td>
                  <td className="px-4 py-3 text-sm text-blue-400">{String(lead.email || "")}</td>
                  <td className="px-4 py-3 text-sm text-slate-300">{String(lead.company || "")}</td>
                  <td className="px-4 py-3 text-sm text-slate-300">{String(lead.industry || "-")}</td>
                  <td className="px-4 py-3 text-sm text-slate-300">{String(lead.team_size || "-")}</td>
                  <td className="px-4 py-3 text-sm text-slate-400">{String(lead.qr_name || "Direct")}</td>
                  <td className="px-4 py-3 text-xs text-slate-400">{String(lead.created_at || "").slice(0, 10)}</td>
                </tr>
              ))}
              {recentLeads.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-500 text-sm">No leads captured yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
