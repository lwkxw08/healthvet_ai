import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { leadGenerationApi } from "../api/client";
import {
  Search, Play, RefreshCw, Trash2, Download, Eye, Globe, Mail, Phone,
  Building2, MapPin, Clock, CheckCircle, XCircle, Filter,
} from "lucide-react";

export default function LeadGenerationPanel() {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState<"scrape" | "leads" | "jobs">("scrape");
  const [message, setMessage] = useState("");

  // Scrape form state
  const [scrapeSource, setScrapeSource] = useState("agencycentral");
  const [scrapeIndustry, setScrapeIndustry] = useState("healthcare");
  const [scrapeLocation, setScrapeLocation] = useState("");
  const [scrapePages, setScrapePages] = useState("3");
  const [scrapingInProgress, setScrapingInProgress] = useState(false);

  // Jobs state
  const [jobs, setJobs] = useState<Record<string, unknown>[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);

  // Leads state
  const [leads, setLeads] = useState<Record<string, unknown>[]>([]);
  const [leadStats, setLeadStats] = useState<Record<string, unknown> | null>(null);
  const [leadsLoading, setLeadsLoading] = useState(false);
  const [leadFilter, setLeadFilter] = useState({ source: "", industry: "", status: "", search: "" });
  const [selectedLead, setSelectedLead] = useState<Record<string, unknown> | null>(null);

  // Sources info
  const [sources, setSources] = useState<Record<string, unknown> | null>(null);

  const showMessage = (msg: string) => { setMessage(msg); setTimeout(() => setMessage(""), 4000); };

  const loadSources = useCallback(async () => {
    if (!token) return;
    try { const s = await leadGenerationApi.getSources(token); setSources(s); } catch { /* ignore */ }
  }, [token]);

  const loadJobs = useCallback(async () => {
    if (!token) return;
    setJobsLoading(true);
    try { const j = await leadGenerationApi.getJobs(token); setJobs(j); } catch { /* ignore */ }
    finally { setJobsLoading(false); }
  }, [token]);

  const loadLeads = useCallback(async () => {
    if (!token) return;
    setLeadsLoading(true);
    try {
      const params: Record<string, string> = {};
      if (leadFilter.source) params.source = leadFilter.source;
      if (leadFilter.industry) params.industry = leadFilter.industry;
      if (leadFilter.status) params.status = leadFilter.status;
      if (leadFilter.search) params.search = leadFilter.search;
      const result = await leadGenerationApi.getLeads(token, params);
      setLeads((result as Record<string, unknown>).leads as Record<string, unknown>[] || []);
    } catch { /* ignore */ }
    finally { setLeadsLoading(false); }
  }, [token, leadFilter]);

  const loadLeadStats = useCallback(async () => {
    if (!token) return;
    try { const s = await leadGenerationApi.getLeadStats(token); setLeadStats(s); } catch { /* ignore */ }
  }, [token]);

  useEffect(() => { loadSources(); }, [loadSources]);
  useEffect(() => { if (activeTab === "jobs") loadJobs(); }, [activeTab, loadJobs]);
  useEffect(() => { if (activeTab === "leads") { loadLeads(); loadLeadStats(); } }, [activeTab, loadLeads, loadLeadStats]);

  const triggerScrape = async () => {
    if (!token) return;
    setScrapingInProgress(true);
    try {
      const data: Record<string, unknown> = {
        source: scrapeSource,
        industry: scrapeIndustry,
        config: { location: scrapeLocation, max_pages: parseInt(scrapePages) || 3 },
      };
      await leadGenerationApi.triggerScrape(token, data as { source: string; industry?: string; config?: Record<string, unknown> });
      showMessage("Scrape job started successfully! Check the Jobs tab for progress.");
      setActiveTab("jobs");
      loadJobs();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed to start scrape"}`); }
    finally { setScrapingInProgress(false); }
  };

  const updateLeadStatus = async (leadId: string, status: string) => {
    if (!token) return;
    try {
      await leadGenerationApi.updateLead(token, leadId, { status });
      showMessage(`Lead status updated to ${status}`);
      loadLeads();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const deleteLead = async (leadId: string) => {
    if (!token) return;
    try {
      await leadGenerationApi.deleteLead(token, leadId);
      showMessage("Lead deleted");
      loadLeads();
      loadLeadStats();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const exportLeads = async () => {
    if (!token) return;
    try {
      const params: Record<string, string> = {};
      if (leadFilter.source) params.source = leadFilter.source;
      if (leadFilter.industry) params.industry = leadFilter.industry;
      await leadGenerationApi.exportLeads(token, params);
      showMessage("Leads exported as Excel");
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const sourceOptions = [
    { value: "agencycentral", label: "AgencyCentral", desc: "UK recruitment agency directory" },
    { value: "indeed", label: "Indeed", desc: "Job board - all industries" },
    { value: "cqc", label: "CQC API", desc: "Healthcare providers (UK)" },
    { value: "nhs_jobs", label: "NHS Jobs", desc: "NHS recruitment (healthcare)" },
  ];

  const industryOptions = [
    { value: "healthcare", label: "Healthcare (CQC)" },
    { value: "education", label: "Education" },
    { value: "construction", label: "Construction" },
    { value: "social_care", label: "Social Care" },
    { value: "finance", label: "Finance" },
    { value: "logistics", label: "Logistics" },
    { value: "retail_hospitality", label: "Retail & Hospitality" },
  ];

  return (
    <div className="space-y-6">
      {message && (
        <div className={`p-3 rounded-lg text-sm ${message.startsWith("Error") ? "bg-red-500/20 text-red-300 border border-red-500/30" : "bg-green-500/20 text-green-300 border border-green-500/30"}`}>{message}</div>
      )}

      {/* Sub-tabs */}
      <div className="flex gap-2 border-b border-slate-700 pb-2">
        {[
          { key: "scrape" as const, label: "New Scrape", icon: <Play size={14} /> },
          { key: "jobs" as const, label: "Scrape Jobs", icon: <Clock size={14} /> },
          { key: "leads" as const, label: "Leads", icon: <Building2 size={14} /> },
        ].map((t) => (
          <button key={t.key} onClick={() => setActiveTab(t.key)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === t.key ? "bg-blue-600 text-white" : "bg-slate-700/50 text-slate-300 hover:bg-slate-700"}`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* New Scrape Tab */}
      {activeTab === "scrape" && (
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Search size={20} className="text-blue-400" /> Configure Scrape Job
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-slate-400 text-xs mb-1">Source</label>
                <select value={scrapeSource} onChange={(e) => setScrapeSource(e.target.value)}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm">
                  {sourceOptions.map((s) => (
                    <option key={s.value} value={s.value}>{s.label} - {s.desc}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-slate-400 text-xs mb-1">Industry</label>
                <select value={scrapeIndustry} onChange={(e) => setScrapeIndustry(e.target.value)}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm"
                  disabled={scrapeSource === "cqc" || scrapeSource === "nhs_jobs"}>
                  {industryOptions.map((i) => (
                    <option key={i.value} value={i.value}>{i.label}</option>
                  ))}
                </select>
                {(scrapeSource === "cqc" || scrapeSource === "nhs_jobs") && (
                  <p className="text-xs text-amber-400 mt-1">This source is healthcare-only</p>
                )}
              </div>
              <div>
                <label className="block text-slate-400 text-xs mb-1">Location (optional)</label>
                <input type="text" value={scrapeLocation} onChange={(e) => setScrapeLocation(e.target.value)}
                  placeholder="e.g. London, Manchester, UK-wide"
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
              </div>
              <div>
                <label className="block text-slate-400 text-xs mb-1">Max Pages</label>
                <input type="number" value={scrapePages} onChange={(e) => setScrapePages(e.target.value)}
                  min="1" max="20"
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm" />
              </div>
              <button onClick={triggerScrape} disabled={scrapingInProgress}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg flex items-center justify-center gap-2">
                {scrapingInProgress ? <><RefreshCw size={16} className="animate-spin" /> Starting...</> : <><Play size={16} /> Start Scrape</>}
              </button>
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
              <h3 className="text-lg font-semibold text-white mb-3">Available Sources</h3>
              <div className="space-y-3">
                {sourceOptions.map((s) => (
                  <div key={s.value} className="flex items-center gap-3 p-3 bg-slate-700/30 rounded-lg border border-slate-600/50">
                    <Globe size={18} className="text-blue-400" />
                    <div>
                      <p className="text-white text-sm font-medium">{s.label}</p>
                      <p className="text-slate-400 text-xs">{s.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {sources && (
              <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-6">
                <h3 className="text-md font-semibold text-white mb-3">Registration Bodies</h3>
                <div className="space-y-2">
                  {((sources as Record<string, unknown>).registration_bodies as Record<string, unknown>[] || []).map((body: Record<string, unknown>) => (
                    <div key={String(body.id)} className="flex items-center gap-2 p-2 bg-slate-700/30 rounded-lg">
                      <CheckCircle size={14} className="text-green-400" />
                      <div>
                        <span className="text-slate-300 text-xs font-medium">{String(body.id)}</span>
                        <span className="text-slate-500 text-xs ml-2">{String(body.name)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Scrape Jobs Tab */}
      {activeTab === "jobs" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-white">Scrape Jobs</h3>
            <button onClick={loadJobs} className="text-slate-400 hover:text-white flex items-center gap-1 text-sm">
              <RefreshCw size={14} className={jobsLoading ? "animate-spin" : ""} /> Refresh
            </button>
          </div>
          {jobs.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <Clock size={40} className="mx-auto mb-3 opacity-50" />
              <p className="text-sm">No scrape jobs yet. Start a new scrape from the New Scrape tab.</p>
            </div>
          ) : (
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-700/50">
                  <tr>
                    <th className="py-3 px-4 text-left text-slate-400 text-xs">Source</th>
                    <th className="py-3 px-4 text-left text-slate-400 text-xs">Industry</th>
                    <th className="py-3 px-4 text-center text-slate-400 text-xs">Status</th>
                    <th className="py-3 px-4 text-center text-slate-400 text-xs">Results</th>
                    <th className="py-3 px-4 text-left text-slate-400 text-xs">Started</th>
                    <th className="py-3 px-4 text-left text-slate-400 text-xs">Completed</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {jobs.map((job) => (
                    <tr key={String(job.id)} className="hover:bg-slate-700/20">
                      <td className="py-3 px-4 text-white font-medium">{String(job.source || "").toUpperCase()}</td>
                      <td className="py-3 px-4 text-slate-300">{String(job.industry || "-")}</td>
                      <td className="py-3 px-4 text-center">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          job.status === "completed" ? "bg-green-500/20 text-green-400" :
                          job.status === "running" ? "bg-blue-500/20 text-blue-400" :
                          job.status === "failed" ? "bg-red-500/20 text-red-400" :
                          "bg-slate-500/20 text-slate-400"
                        }`}>{String(job.status)}</span>
                      </td>
                      <td className="py-3 px-4 text-center text-emerald-400 font-medium">{String(job.results_count || 0)}</td>
                      <td className="py-3 px-4 text-slate-400 text-xs">{job.started_at ? new Date(String(job.started_at)).toLocaleString() : "-"}</td>
                      <td className="py-3 px-4 text-slate-400 text-xs">{job.completed_at ? new Date(String(job.completed_at)).toLocaleString() : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Leads Tab */}
      {activeTab === "leads" && (
        <div className="space-y-4">
          {/* Stats */}
          {leadStats && (
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: "Total Leads", value: String((leadStats as Record<string, unknown>).total || 0), icon: <Building2 className="text-blue-400" size={18} /> },
                { label: "With Email", value: String((leadStats as Record<string, unknown>).with_email || 0), icon: <Mail className="text-green-400" size={18} /> },
                { label: "With Phone", value: String((leadStats as Record<string, unknown>).with_phone || 0), icon: <Phone className="text-purple-400" size={18} /> },
                { label: "Contacted", value: String((leadStats as Record<string, unknown>).contacted || 0), icon: <CheckCircle className="text-emerald-400" size={18} /> },
              ].map((s) => (
                <div key={s.label} className="bg-slate-800/80 rounded-xl border border-slate-700 p-4">
                  <div className="flex items-center justify-between mb-1"><p className="text-slate-400 text-xs">{s.label}</p>{s.icon}</div>
                  <p className="text-2xl font-bold text-white">{s.value}</p>
                </div>
              ))}
            </div>
          )}

          {/* Filters */}
          <div className="flex items-center gap-3 flex-wrap">
            <Filter size={16} className="text-slate-400" />
            <select value={leadFilter.source} onChange={(e) => setLeadFilter((p) => ({ ...p, source: e.target.value }))}
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-1.5 text-white text-xs">
              <option value="">All Sources</option>
              {sourceOptions.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
            <select value={leadFilter.industry} onChange={(e) => setLeadFilter((p) => ({ ...p, industry: e.target.value }))}
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-1.5 text-white text-xs">
              <option value="">All Industries</option>
              {industryOptions.map((i) => <option key={i.value} value={i.value}>{i.label}</option>)}
            </select>
            <select value={leadFilter.status} onChange={(e) => setLeadFilter((p) => ({ ...p, status: e.target.value }))}
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-1.5 text-white text-xs">
              <option value="">All Statuses</option>
              <option value="new">New</option>
              <option value="contacted">Contacted</option>
              <option value="qualified">Qualified</option>
              <option value="converted">Converted</option>
              <option value="rejected">Rejected</option>
            </select>
            <input type="text" value={leadFilter.search} onChange={(e) => setLeadFilter((p) => ({ ...p, search: e.target.value }))}
              placeholder="Search agencies..."
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-1.5 text-white text-xs flex-1 min-w-48" />
            <button onClick={exportLeads} className="bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1.5 rounded-lg text-xs flex items-center gap-1">
              <Download size={12} /> Export
            </button>
          </div>

          {/* Leads table */}
          {leadsLoading ? (
            <div className="text-center py-8"><RefreshCw size={24} className="animate-spin mx-auto text-slate-400" /></div>
          ) : leads.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <Building2 size={40} className="mx-auto mb-3 opacity-50" />
              <p className="text-sm">No leads found. Run a scrape job to generate leads.</p>
            </div>
          ) : (
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-700/50">
                  <tr>
                    <th className="py-3 px-3 text-left text-slate-400 text-xs">Agency</th>
                    <th className="py-3 px-3 text-left text-slate-400 text-xs">Source</th>
                    <th className="py-3 px-3 text-left text-slate-400 text-xs">Industry</th>
                    <th className="py-3 px-3 text-left text-slate-400 text-xs">Contact</th>
                    <th className="py-3 px-3 text-left text-slate-400 text-xs">Location</th>
                    <th className="py-3 px-3 text-center text-slate-400 text-xs">Status</th>
                    <th className="py-3 px-3 text-center text-slate-400 text-xs">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {leads.map((lead) => (
                    <tr key={String(lead.id)} className="hover:bg-slate-700/20">
                      <td className="py-3 px-3">
                        <div className="text-white font-medium text-sm">{String(lead.agency_name)}</div>
                        {lead.website ? <a href={String(lead.website)} target="_blank" rel="noopener noreferrer" className="text-blue-400 text-xs hover:underline">{String(lead.website).replace(/^https?:\/\//, "").slice(0, 30)}</a> : null}
                      </td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded-full text-xs bg-slate-600/50 text-slate-300">{String(lead.source || "").toUpperCase()}</span>
                      </td>
                      <td className="py-3 px-3 text-slate-300 text-xs">{String(lead.industry || "-")}</td>
                      <td className="py-3 px-3">
                        <div className="space-y-0.5">
                          {lead.email ? <div className="flex items-center gap-1 text-xs text-green-400"><Mail size={10} />{String(lead.email)}</div> : null}
                          {lead.phone ? <div className="flex items-center gap-1 text-xs text-purple-400"><Phone size={10} />{String(lead.phone)}</div> : null}
                          {!lead.email && !lead.phone && <span className="text-xs text-slate-500">No contact</span>}
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        {lead.location ? <div className="flex items-center gap-1 text-xs text-slate-300"><MapPin size={10} />{String(lead.location)}</div> : null}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <select value={String(lead.status || "new")}
                          onChange={(e) => updateLeadStatus(String(lead.id), e.target.value)}
                          className={`text-xs rounded-full px-2 py-0.5 border-0 ${
                            lead.status === "converted" ? "bg-green-500/20 text-green-400" :
                            lead.status === "contacted" ? "bg-blue-500/20 text-blue-400" :
                            lead.status === "qualified" ? "bg-purple-500/20 text-purple-400" :
                            lead.status === "rejected" ? "bg-red-500/20 text-red-400" :
                            "bg-slate-500/20 text-slate-400"
                          }`}>
                          <option value="new">New</option>
                          <option value="contacted">Contacted</option>
                          <option value="qualified">Qualified</option>
                          <option value="converted">Converted</option>
                          <option value="rejected">Rejected</option>
                        </select>
                      </td>
                      <td className="py-3 px-3 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <button onClick={() => setSelectedLead(lead)} className="text-slate-400 hover:text-blue-400" title="View"><Eye size={14} /></button>
                          <button onClick={() => deleteLead(String(lead.id))} className="text-slate-400 hover:text-red-400" title="Delete"><Trash2 size={14} /></button>
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

      {/* Lead Detail Modal */}
      {selectedLead && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setSelectedLead(null)}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-lg w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">{String(selectedLead.agency_name)}</h3>
              <button onClick={() => setSelectedLead(null)} className="text-slate-400 hover:text-white">
                <XCircle size={20} />
              </button>
            </div>
            <div className="space-y-3">
              {selectedLead.website ? (
                <div className="flex items-center gap-2"><Globe size={14} className="text-blue-400" /><a href={String(selectedLead.website)} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline text-sm">{String(selectedLead.website)}</a></div>
              ) : null}
              {selectedLead.email ? (
                <div className="flex items-center gap-2"><Mail size={14} className="text-green-400" /><span className="text-white text-sm">{String(selectedLead.email)}</span></div>
              ) : null}
              {selectedLead.phone ? (
                <div className="flex items-center gap-2"><Phone size={14} className="text-purple-400" /><span className="text-white text-sm">{String(selectedLead.phone)}</span></div>
              ) : null}
              {selectedLead.location ? (
                <div className="flex items-center gap-2"><MapPin size={14} className="text-amber-400" /><span className="text-white text-sm">{String(selectedLead.location)}</span></div>
              ) : null}
              {selectedLead.description ? (
                <div className="mt-3"><p className="text-slate-400 text-xs mb-1">Description</p><p className="text-slate-300 text-sm">{String(selectedLead.description)}</p></div>
              ) : null}
              <div className="flex gap-4 mt-3">
                <div><p className="text-slate-400 text-xs">Source</p><p className="text-white text-sm">{String(selectedLead.source || "").toUpperCase()}</p></div>
                <div><p className="text-slate-400 text-xs">Industry</p><p className="text-white text-sm">{String(selectedLead.industry || "-")}</p></div>
                <div><p className="text-slate-400 text-xs">Status</p><p className="text-white text-sm">{String(selectedLead.status || "new")}</p></div>
              </div>
              {selectedLead.notes ? (
                <div className="mt-2"><p className="text-slate-400 text-xs">Notes</p><p className="text-slate-300 text-sm">{String(selectedLead.notes)}</p></div>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
