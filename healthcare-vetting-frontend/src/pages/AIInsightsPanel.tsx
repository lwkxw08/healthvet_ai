import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { aiInsightsApi } from "../api/client";
import {
  Brain, Search, AlertTriangle, Clock, Shield, CheckCircle,
  XCircle, Activity, TrendingUp, RefreshCw, ChevronDown, ChevronUp,
  FileText, Users, Zap, Calendar,
} from "lucide-react";

type AISubTab = "cv-analysis" | "reference-sentiment" | "anomaly-detection" | "smart-scheduling";

export default function AIInsightsPanel() {
  const { token } = useAuth();
  const [subTab, setSubTab] = useState<AISubTab>("cv-analysis");
  const [aiStatus, setAiStatus] = useState<Record<string, unknown> | null>(null);

  // CV Analysis state
  const [cvCandidateId, setCvCandidateId] = useState("");
  const [cvText, setCvText] = useState("");
  const [cvResult, setCvResult] = useState<Record<string, unknown> | null>(null);
  const [cvHistory, setCvHistory] = useState<Record<string, unknown>[]>([]);
  const [cvLoading, setCvLoading] = useState(false);
  const [cvHistoryId, setCvHistoryId] = useState("");

  // Reference Sentiment state
  const [refId, setRefId] = useState("");
  const [refData, setRefData] = useState("");
  const [refResult, setRefResult] = useState<Record<string, unknown> | null>(null);
  const [refLoading, setRefLoading] = useState(false);
  const [refHistory, setRefHistory] = useState<Record<string, unknown>[]>([]);

  // Anomaly Detection state
  const [anomalyResult, setAnomalyResult] = useState<Record<string, unknown> | null>(null);
  const [anomalyLoading, setAnomalyLoading] = useState(false);
  const [anomalyHistory, setAnomalyHistory] = useState<Record<string, unknown>[]>([]);
  const [expandedAnomaly, setExpandedAnomaly] = useState<string | null>(null);

  // Smart Scheduling state
  const [scheduleResult, setScheduleResult] = useState<Record<string, unknown> | null>(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);

  const loadStatus = useCallback(async () => {
    if (!token) return;
    try {
      const s = await aiInsightsApi.getStatus(token);
      setAiStatus(s);
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  // CV Gap Analysis handlers
  const runCvAnalysis = async () => {
    if (!token || !cvCandidateId || !cvText) return;
    setCvLoading(true);
    try {
      const result = await aiInsightsApi.runCvGapAnalysis(token, {
        candidate_id: cvCandidateId,
        cv_text: cvText,
      });
      setCvResult(result);
    } catch (e) {
      setCvResult({ error: String(e) });
    } finally {
      setCvLoading(false);
    }
  };

  const loadCvHistory = async () => {
    if (!token || !cvHistoryId) return;
    try {
      const r = await aiInsightsApi.getCvGapAnalyses(token, cvHistoryId);
      setCvHistory(r.analyses || []);
    } catch { setCvHistory([]); }
  };

  // Reference Sentiment handlers
  const runRefAnalysis = async () => {
    if (!token || !refId) return;
    setRefLoading(true);
    try {
      let parsedData: Record<string, unknown> = {};
      try { parsedData = JSON.parse(refData); } catch { parsedData = { text: refData }; }
      const result = await aiInsightsApi.runReferenceSentiment(token, {
        reference_id: refId,
        reference_data: parsedData,
      });
      setRefResult(result);
    } catch (e) {
      setRefResult({ error: String(e) });
    } finally {
      setRefLoading(false);
    }
  };

  const loadRefHistory = async () => {
    if (!token) return;
    try {
      const r = await aiInsightsApi.getReferenceSentiments(token);
      setRefHistory(r.analyses || []);
    } catch { setRefHistory([]); }
  };

  // Anomaly Detection handlers
  const runAnomalyScan = async () => {
    if (!token) return;
    setAnomalyLoading(true);
    try {
      const result = await aiInsightsApi.runAnomalyScan(token);
      setAnomalyResult(result);
    } catch (e) {
      setAnomalyResult({ error: String(e) });
    } finally {
      setAnomalyLoading(false);
    }
  };

  const loadAnomalyHistory = async () => {
    if (!token) return;
    try {
      const r = await aiInsightsApi.getAnomalyHistory(token);
      setAnomalyHistory(r.scans || []);
    } catch { setAnomalyHistory([]); }
  };

  // Smart Scheduling handlers
  const loadSmartSchedule = async () => {
    if (!token) return;
    setScheduleLoading(true);
    try {
      const result = await aiInsightsApi.getSmartScheduling(token);
      setScheduleResult(result);
    } catch (e) {
      setScheduleResult({ error: String(e) });
    } finally {
      setScheduleLoading(false);
    }
  };

  useEffect(() => {
    if (subTab === "anomaly-detection") loadAnomalyHistory();
    if (subTab === "reference-sentiment") loadRefHistory();
    if (subTab === "smart-scheduling") loadSmartSchedule();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subTab, token]);

  const features = aiStatus?.features as Record<string, Record<string, unknown>> | undefined;

  const SeverityBadge = ({ severity }: { severity: string }) => {
    const colors: Record<string, string> = {
      high: "bg-red-100 text-red-800",
      medium: "bg-yellow-100 text-yellow-800",
      low: "bg-blue-100 text-blue-800",
    };
    return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[severity] || "bg-gray-100 text-gray-600"}`}>{severity}</span>;
  };

  const RiskBadge = ({ risk }: { risk: string }) => {
    const colors: Record<string, string> = {
      high: "bg-red-600 text-white",
      medium: "bg-orange-500 text-white",
      low: "bg-green-600 text-white",
    };
    return <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${colors[risk] || "bg-gray-500 text-white"}`}>{risk} risk</span>;
  };

  return (
    <div className="space-y-4">
      {/* AI Status Bar */}
      {aiStatus && (
        <div className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-500/30 rounded-lg p-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Brain className="w-5 h-5 text-purple-400" />
            <span className="text-sm text-purple-200">
              AI Engine: <strong>{aiStatus.openai_configured ? "OpenAI GPT-4o-mini" : "Rule-Based (No API Key)"}</strong>
            </span>
          </div>
          <div className="flex gap-3 text-xs">
            {features && Object.entries(features).map(([key, val]) => (
              <span key={key} className={`px-2 py-1 rounded ${val.method === "openai" ? "bg-purple-800/50 text-purple-200" : "bg-gray-700/50 text-gray-300"}`}>
                {key.replace(/_/g, " ")}: {String(val.method)}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Sub-tab navigation */}
      <div className="flex gap-2 border-b border-gray-700 pb-2">
        {([
          { id: "cv-analysis", label: "CV Gap Analysis", icon: FileText },
          { id: "reference-sentiment", label: "Reference Sentiment", icon: Users },
          { id: "anomaly-detection", label: "Anomaly Detection", icon: Shield },
          { id: "smart-scheduling", label: "Smart Scheduling", icon: Calendar },
        ] as const).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setSubTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-t text-sm font-medium transition-colors ${
              subTab === id ? "bg-purple-600 text-white" : "text-gray-400 hover:text-white hover:bg-gray-800"
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* ============ CV Gap Analysis ============ */}
      {subTab === "cv-analysis" && (
        <div className="space-y-4">
          <div className="bg-gray-800 rounded-lg p-4 space-y-3">
            <h3 className="text-lg font-semibold flex items-center gap-2"><FileText className="w-5 h-5 text-purple-400" /> Run CV Gap Analysis</h3>
            <p className="text-sm text-gray-400">Paste CV text to analyse for employment gaps, date overlaps, role progression issues, and red flags.</p>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <input
                className="bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm"
                placeholder="Candidate ID"
                value={cvCandidateId}
                onChange={(e) => setCvCandidateId(e.target.value)}
              />
              <div className="md:col-span-3">
                <textarea
                  className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm h-32"
                  placeholder="Paste CV text here..."
                  value={cvText}
                  onChange={(e) => setCvText(e.target.value)}
                />
              </div>
            </div>
            <button
              onClick={runCvAnalysis}
              disabled={cvLoading || !cvCandidateId || !cvText}
              className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white px-4 py-2 rounded text-sm flex items-center gap-2"
            >
              {cvLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
              {cvLoading ? "Analysing..." : "Analyse CV"}
            </button>
          </div>

          {/* CV Analysis Result */}
          {cvResult && !("error" in cvResult && typeof cvResult.error === "string" && !cvResult.method) && (
            <div className="bg-gray-800 rounded-lg p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <Activity className="w-5 h-5 text-purple-400" /> Analysis Result
                </h3>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400">Method: {String(cvResult.method)}</span>
                  <RiskBadge risk={String(cvResult.overall_risk || "unknown")} />
                </div>
              </div>

              {cvResult.summary ? (
                <div className="bg-gray-900 rounded p-3 text-sm text-gray-300">{String(cvResult.summary)}</div>
              ) : null}

              {/* Gaps */}
              {Array.isArray(cvResult.gaps) && (cvResult.gaps as Record<string, unknown>[]).length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-red-400 mb-2">Employment Gaps ({(cvResult.gaps as unknown[]).length})</h4>
                  <div className="space-y-2">
                    {(cvResult.gaps as Record<string, unknown>[]).map((g, i) => (
                      <div key={i} className="bg-red-900/20 border border-red-800/30 rounded p-3 flex items-center justify-between">
                        <div>
                          <span className="text-sm">{String(g.from)} → {String(g.to)}</span>
                          <span className="text-xs text-gray-400 ml-2">({String(g.gap_months)} months)</span>
                          {g.possible_explanation ? <p className="text-xs text-gray-400 mt-1">{String(g.possible_explanation)}</p> : null}
                        </div>
                        <SeverityBadge severity={String(g.severity)} />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Overlaps */}
              {Array.isArray(cvResult.overlaps) && (cvResult.overlaps as Record<string, unknown>[]).length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-yellow-400 mb-2">Date Overlaps ({(cvResult.overlaps as unknown[]).length})</h4>
                  <div className="space-y-2">
                    {(cvResult.overlaps as Record<string, unknown>[]).map((o, i) => (
                      <div key={i} className="bg-yellow-900/20 border border-yellow-800/30 rounded p-3 text-sm">
                        {String(o.period_1 || o.period_1_end)} ↔ {String(o.period_2 || o.period_2_start)}
                        <span className="text-xs text-gray-400 ml-2">({String(o.overlap_months)} months overlap)</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Red Flags / Risk Flags */}
              {(() => {
                const flags = (cvResult.red_flags || cvResult.risk_flags) as Record<string, unknown>[] | undefined;
                if (!flags || !Array.isArray(flags) || flags.length === 0) return null;
                return (
                  <div>
                    <h4 className="text-sm font-medium text-orange-400 mb-2">Risk Flags ({flags.length})</h4>
                    <div className="space-y-2">
                      {flags.map((f, i) => (
                        <div key={i} className="bg-orange-900/20 border border-orange-800/30 rounded p-3 flex items-center justify-between">
                          <span className="text-sm">{String(f.type || f.concern || "").replace(/_/g, " ")}: {String(f.detail || f.count || "")}</span>
                          <SeverityBadge severity={String(f.severity)} />
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}

              {/* Recommendations */}
              {Array.isArray(cvResult.recommendations) && (
                <div>
                  <h4 className="text-sm font-medium text-blue-400 mb-2">Recommendations</h4>
                  <ul className="list-disc list-inside space-y-1 text-sm text-gray-300">
                    {(cvResult.recommendations as string[]).map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* CV History */}
          <div className="bg-gray-800 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-semibold text-gray-300">Past Analyses</h3>
            <div className="flex gap-2">
              <input
                className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm flex-1"
                placeholder="Candidate ID to load history"
                value={cvHistoryId}
                onChange={(e) => setCvHistoryId(e.target.value)}
              />
              <button onClick={loadCvHistory} className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1.5 rounded text-sm flex items-center gap-1">
                <Search className="w-3 h-3" /> Load
              </button>
            </div>
            {cvHistory.length > 0 && (
              <div className="space-y-2">
                {cvHistory.map((a, i) => (
                  <div key={i} className="bg-gray-900 rounded p-3 flex items-center justify-between text-sm">
                    <div>
                      <span className="text-gray-400">{String(a.created_at || "").slice(0, 19)}</span>
                      <span className="ml-2 text-gray-300">Method: {String(a.method)}</span>
                      <span className="ml-2">Gaps: {String(a.gaps_count)}</span>
                      <span className="ml-2">Red flags: {String(a.red_flags_count)}</span>
                    </div>
                    <RiskBadge risk={String(a.overall_risk || "unknown")} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ============ Reference Sentiment ============ */}
      {subTab === "reference-sentiment" && (
        <div className="space-y-4">
          <div className="bg-gray-800 rounded-lg p-4 space-y-3">
            <h3 className="text-lg font-semibold flex items-center gap-2"><Users className="w-5 h-5 text-purple-400" /> Analyse Reference</h3>
            <p className="text-sm text-gray-400">Enter a reference ID and the reference response data (JSON or text) to get deep sentiment analysis.</p>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <input
                className="bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm"
                placeholder="Reference ID"
                value={refId}
                onChange={(e) => setRefId(e.target.value)}
              />
              <div className="md:col-span-3">
                <textarea
                  className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm h-32"
                  placeholder='{"performance_rating": 4, "conduct_rating": 5, "reliability_rating": 3, "would_rehire": true, "strengths": "...", "improvements": "...", "additional_comments": "..."}'
                  value={refData}
                  onChange={(e) => setRefData(e.target.value)}
                />
              </div>
            </div>
            <button
              onClick={runRefAnalysis}
              disabled={refLoading || !refId}
              className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white px-4 py-2 rounded text-sm flex items-center gap-2"
            >
              {refLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
              {refLoading ? "Analysing..." : "Analyse Reference"}
            </button>
          </div>

          {/* Reference Result */}
          {refResult && !refResult.error && (
            <div className="bg-gray-800 rounded-lg p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">Sentiment Analysis</h3>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400">Method: {String(refResult.method)}</span>
                  <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${
                    refResult.assessment === "positive" ? "bg-green-600 text-white" :
                    refResult.assessment === "neutral" ? "bg-blue-600 text-white" :
                    refResult.assessment === "concerning" ? "bg-orange-600 text-white" :
                    "bg-red-600 text-white"
                  }`}>{String(refResult.assessment)}</span>
                </div>
              </div>

              {/* Sentiment Score Bar */}
              <div className="bg-gray-900 rounded p-3">
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-gray-400">Sentiment Score</span>
                  <span className="font-bold">{(Number(refResult.sentiment_score) * 100).toFixed(0) + "%"}</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-3">
                  <div
                    className={`h-3 rounded-full transition-all ${
                      Number(refResult.sentiment_score) >= 0.75 ? "bg-green-500" :
                      Number(refResult.sentiment_score) >= 0.5 ? "bg-blue-500" :
                      Number(refResult.sentiment_score) >= 0.3 ? "bg-orange-500" :
                      "bg-red-500"
                    }`}
                    style={{ width: `${Number(refResult.sentiment_score) * 100}%` }}
                  />
                </div>
              </div>

              {refResult.summary ? (
                <div className="bg-gray-900 rounded p-3 text-sm text-gray-300">{String(refResult.summary)}</div>
              ) : null}

              {/* Concerns */}
              {Array.isArray(refResult.concerns) && (refResult.concerns as Record<string, unknown>[]).length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-red-400 mb-2">Concerns ({(refResult.concerns as unknown[]).length})</h4>
                  <div className="space-y-2">
                    {(refResult.concerns as Record<string, unknown>[]).map((c, i) => (
                      <div key={i} className="bg-red-900/20 border border-red-800/30 rounded p-3 flex items-center justify-between">
                        <div>
                          <span className="text-xs font-medium text-red-300 capitalize">{String(c.type || "").replace(/_/g, " ")}</span>
                          <p className="text-sm text-gray-300 mt-1">{String(c.detail)}</p>
                        </div>
                        <SeverityBadge severity={String(c.severity)} />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {Array.isArray(refResult.recommendations) && (
                <div>
                  <h4 className="text-sm font-medium text-blue-400 mb-2">Recommendations</h4>
                  <ul className="list-disc list-inside space-y-1 text-sm text-gray-300">
                    {(refResult.recommendations as string[]).map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Reference History */}
          {refHistory.length > 0 && (
            <div className="bg-gray-800 rounded-lg p-4 space-y-3">
              <h3 className="text-sm font-semibold text-gray-300">Recent Analyses ({refHistory.length})</h3>
              <div className="space-y-2">
                {refHistory.slice(0, 10).map((a, i) => (
                  <div key={i} className="bg-gray-900 rounded p-3 flex items-center justify-between text-sm">
                    <div>
                      <span className="text-gray-400">{String(a.created_at || "").slice(0, 19)}</span>
                      <span className="ml-2 text-gray-300">Ref: {String(a.reference_id || "").slice(0, 12)}</span>
                      <span className="ml-2">Score: {(Number(a.sentiment_score) * 100).toFixed(0)}%</span>
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      a.assessment === "positive" ? "bg-green-800 text-green-200" :
                      a.assessment === "neutral" ? "bg-blue-800 text-blue-200" :
                      a.assessment === "concerning" ? "bg-orange-800 text-orange-200" :
                      "bg-red-800 text-red-200"
                    }`}>{String(a.assessment)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============ Anomaly Detection ============ */}
      {subTab === "anomaly-detection" && (
        <div className="space-y-4">
          <div className="bg-gray-800 rounded-lg p-4 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold flex items-center gap-2"><Shield className="w-5 h-5 text-purple-400" /> Verification Anomaly Scanner</h3>
              <p className="text-sm text-gray-400 mt-1">Scans all employment verifications and references for suspicious patterns: rapid responses, same-IP submissions, email domain mismatches, similar language, unusual times.</p>
            </div>
            <button
              onClick={runAnomalyScan}
              disabled={anomalyLoading}
              className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white px-4 py-2 rounded text-sm flex items-center gap-2"
            >
              {anomalyLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
              {anomalyLoading ? "Scanning..." : "Run Scan"}
            </button>
          </div>

          {/* Anomaly Results */}
          {anomalyResult && !anomalyResult.error && (
            <>
              {/* Stats cards */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {[
                  { label: "Verifications Scanned", value: (anomalyResult.stats as Record<string, unknown>)?.total_verifications_scanned, icon: FileText, color: "text-blue-400" },
                  { label: "References Scanned", value: (anomalyResult.stats as Record<string, unknown>)?.total_references_scanned, icon: Users, color: "text-blue-400" },
                  { label: "Anomalies Found", value: (anomalyResult.stats as Record<string, unknown>)?.anomalies_found, icon: AlertTriangle, color: "text-red-400" },
                  { label: "High Severity", value: (anomalyResult.by_severity as Record<string, unknown>)?.high, icon: XCircle, color: "text-red-500" },
                  { label: "Medium Severity", value: (anomalyResult.by_severity as Record<string, unknown>)?.medium, icon: AlertTriangle, color: "text-yellow-500" },
                ].map((s, i) => (
                  <div key={i} className="bg-gray-800 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
                      <s.icon className={`w-3 h-3 ${s.color}`} />
                      {s.label}
                    </div>
                    <div className={`text-2xl font-bold ${s.color}`}>{String(s.value ?? 0)}</div>
                  </div>
                ))}
              </div>

              {/* Anomaly list */}
              {Array.isArray(anomalyResult.anomalies) && (anomalyResult.anomalies as Record<string, unknown>[]).length > 0 && (
                <div className="bg-gray-800 rounded-lg p-4 space-y-3">
                  <h3 className="text-sm font-semibold text-gray-300">Detected Anomalies</h3>
                  <div className="space-y-2">
                    {(anomalyResult.anomalies as Record<string, unknown>[]).map((a, i) => {
                      const id = String(a.entity_id || a.type) + i;
                      const isExpanded = expandedAnomaly === id;
                      return (
                        <div key={i} className="bg-gray-900 rounded border border-gray-700">
                          <button
                            onClick={() => setExpandedAnomaly(isExpanded ? null : id)}
                            className="w-full p-3 flex items-center justify-between text-left"
                          >
                            <div className="flex items-center gap-3">
                              <SeverityBadge severity={String(a.severity)} />
                              <span className="text-sm font-medium capitalize">{String(a.type || "").replace(/_/g, " ")}</span>
                              {a.candidate_name ? <span className="text-xs text-gray-400">{"— " + String(a.candidate_name)}</span> : null}
                            </div>
                            {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                          </button>
                          {isExpanded && (
                            <div className="px-3 pb-3 text-sm text-gray-300 border-t border-gray-700 pt-2">
                              <p>{String(a.detail)}</p>
                              {a.verifier_email ? <p className="text-xs text-gray-400 mt-1">{"Verifier: " + String(a.verifier_email)}</p> : null}
                              {a.ip_address ? <p className="text-xs text-gray-400">{"IP: " + String(a.ip_address)}</p> : null}
                              {a.employer_name ? <p className="text-xs text-gray-400">{"Employer: " + String(a.employer_name)}</p> : null}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {Array.isArray(anomalyResult.anomalies) && (anomalyResult.anomalies as unknown[]).length === 0 && (
                <div className="bg-gray-800 rounded-lg p-8 text-center">
                  <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
                  <h3 className="text-lg font-semibold text-green-400">No Anomalies Detected</h3>
                  <p className="text-sm text-gray-400 mt-1">All verification patterns appear normal.</p>
                </div>
              )}
            </>
          )}

          {/* Scan History */}
          {anomalyHistory.length > 0 && (
            <div className="bg-gray-800 rounded-lg p-4 space-y-3">
              <h3 className="text-sm font-semibold text-gray-300">Scan History</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-gray-400 border-b border-gray-700">
                    <tr>
                      <th className="text-left py-2">Date</th>
                      <th className="text-right py-2">Scanned</th>
                      <th className="text-right py-2">Anomalies</th>
                      <th className="text-right py-2">High</th>
                      <th className="text-right py-2">Medium</th>
                      <th className="text-right py-2">Low</th>
                    </tr>
                  </thead>
                  <tbody>
                    {anomalyHistory.slice(0, 10).map((s, i) => (
                      <tr key={i} className="border-b border-gray-800">
                        <td className="py-2">{String(s.created_at || "").slice(0, 19)}</td>
                        <td className="text-right">{String(s.total_scanned)}</td>
                        <td className="text-right">{String(s.anomalies_found)}</td>
                        <td className="text-right text-red-400">{String(s.high_severity)}</td>
                        <td className="text-right text-yellow-400">{String(s.medium_severity)}</td>
                        <td className="text-right text-blue-400">{String(s.low_severity)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============ Smart Scheduling ============ */}
      {subTab === "smart-scheduling" && (
        <div className="space-y-4">
          <div className="bg-gray-800 rounded-lg p-4 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold flex items-center gap-2"><Calendar className="w-5 h-5 text-purple-400" /> Smart Follow-up Scheduling</h3>
              <p className="text-sm text-gray-400 mt-1">Analyses historical response patterns to determine optimal reminder timing for pending verifications.</p>
            </div>
            <button
              onClick={loadSmartSchedule}
              disabled={scheduleLoading}
              className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white px-4 py-2 rounded text-sm flex items-center gap-2"
            >
              {scheduleLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <TrendingUp className="w-4 h-4" />}
              {scheduleLoading ? "Analysing..." : "Refresh Analysis"}
            </button>
          </div>

          {scheduleResult && !scheduleResult.error && (
            <>
              {/* Summary cards */}
              {scheduleResult.summary && (() => {
                const sum = scheduleResult.summary as Record<string, unknown>;
                return (
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    {[
                      { label: "Total Pending", value: sum.total_pending, color: "text-blue-400" },
                      { label: "Need 1st Reminder", value: sum.need_first_reminder, color: "text-yellow-400" },
                      { label: "Need 2nd Reminder", value: sum.need_second_reminder, color: "text-orange-400" },
                      { label: "Need Escalation", value: sum.need_escalation, color: "text-red-400" },
                      { label: "On Track", value: sum.waiting, color: "text-green-400" },
                    ].map((s, i) => (
                      <div key={i} className="bg-gray-800 rounded-lg p-3">
                        <div className="text-xs text-gray-400 mb-1">{s.label}</div>
                        <div className={`text-2xl font-bold ${s.color}`}>{String(s.value ?? 0)}</div>
                      </div>
                    ))}
                  </div>
                );
              })()}

              {/* Optimal Timing */}
              {scheduleResult.optimal_timing && (() => {
                const timing = scheduleResult.optimal_timing as Record<string, unknown>;
                return (
                  <div className="bg-gray-800 rounded-lg p-4">
                    <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                      <Clock className="w-4 h-4 text-purple-400" />
                      Optimal Timing {timing.data_driven ? "(Data-Driven)" : "(Default — insufficient data)"}
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                      <div className="bg-gray-900 rounded p-3">
                        <div className="text-xs text-gray-400">1st Reminder After</div>
                        <div className="text-lg font-bold text-yellow-400">{String(timing.first_reminder_hours)}h</div>
                      </div>
                      <div className="bg-gray-900 rounded p-3">
                        <div className="text-xs text-gray-400">2nd Reminder After</div>
                        <div className="text-lg font-bold text-orange-400">{String(timing.second_reminder_hours)}h</div>
                      </div>
                      <div className="bg-gray-900 rounded p-3">
                        <div className="text-xs text-gray-400">Escalation After</div>
                        <div className="text-lg font-bold text-red-400">{String(timing.escalation_hours)}h</div>
                      </div>
                      <div className="bg-gray-900 rounded p-3">
                        <div className="text-xs text-gray-400">Best Send Time</div>
                        <div className="text-lg font-bold text-purple-400">{String(timing.optimal_send_day)} {String(timing.optimal_send_hour)}:00</div>
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* Response Patterns */}
              {scheduleResult.response_patterns && (() => {
                const patterns = scheduleResult.response_patterns as Record<string, unknown>;
                const empStats = patterns.employment_verifications as Record<string, unknown> | undefined;
                const refStats = patterns.references as Record<string, unknown> | undefined;
                return (
                  <div className="bg-gray-800 rounded-lg p-4 space-y-3">
                    <h3 className="text-sm font-semibold text-gray-300">Response Time Statistics</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {empStats && Number(empStats.count) > 0 && (
                        <div className="bg-gray-900 rounded p-3 space-y-2">
                          <h4 className="text-xs font-medium text-blue-400">Employment Verifications ({String(empStats.count)} completed)</h4>
                          <div className="grid grid-cols-3 gap-2 text-xs">
                            <div><span className="text-gray-400">Avg:</span> <span className="font-medium">{String(empStats.avg_hours)}h</span></div>
                            <div><span className="text-gray-400">Median:</span> <span className="font-medium">{String(empStats.median_hours)}h</span></div>
                            <div><span className="text-gray-400">Min:</span> <span className="font-medium">{String(empStats.min_hours)}h</span></div>
                          </div>
                        </div>
                      )}
                      {refStats && Number(refStats.count) > 0 && (
                        <div className="bg-gray-900 rounded p-3 space-y-2">
                          <h4 className="text-xs font-medium text-green-400">References ({String(refStats.count)} completed)</h4>
                          <div className="grid grid-cols-3 gap-2 text-xs">
                            <div><span className="text-gray-400">Avg:</span> <span className="font-medium">{String(refStats.avg_hours)}h</span></div>
                            <div><span className="text-gray-400">Median:</span> <span className="font-medium">{String(refStats.median_hours)}h</span></div>
                            <div><span className="text-gray-400">Min:</span> <span className="font-medium">{String(refStats.min_hours)}h</span></div>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Best response days */}
                    {Array.isArray(patterns.best_response_days) && (patterns.best_response_days as Record<string, unknown>[]).length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium text-gray-400 mt-2 mb-1">Fastest Response Days</h4>
                        <div className="flex gap-2">
                          {(patterns.best_response_days as Record<string, unknown>[]).map((d, i) => (
                            <span key={i} className="bg-gray-700 rounded px-2 py-1 text-xs">
                              {String(d.day)}: avg {String(d.avg_hours)}h ({String(d.responses)} responses)
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* Follow-up Queue */}
              {Array.isArray(scheduleResult.follow_ups) && (scheduleResult.follow_ups as Record<string, unknown>[]).length > 0 && (
                <div className="bg-gray-800 rounded-lg p-4 space-y-3">
                  <h3 className="text-sm font-semibold text-gray-300">Follow-up Queue</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-gray-400 border-b border-gray-700">
                        <tr>
                          <th className="text-left py-2">Type</th>
                          <th className="text-left py-2">Candidate</th>
                          <th className="text-left py-2">Verifier</th>
                          <th className="text-right py-2">Waiting</th>
                          <th className="text-right py-2">Reminders</th>
                          <th className="text-left py-2">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(scheduleResult.follow_ups as Record<string, unknown>[]).map((f, i) => (
                          <tr key={i} className="border-b border-gray-800">
                            <td className="py-2 capitalize">{String(f.type || "").replace(/_/g, " ")}</td>
                            <td className="py-2">{String(f.candidate_name || "").slice(0, 20)}</td>
                            <td className="py-2 text-xs">{String(f.verifier_email || "").slice(0, 25)}</td>
                            <td className="py-2 text-right">{String(f.hours_waiting)}h</td>
                            <td className="py-2 text-right">{String(f.reminders_sent)}</td>
                            <td className="py-2">
                              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                f.urgency === "high" ? "bg-red-900/50 text-red-300" :
                                f.urgency === "medium" ? "bg-yellow-900/50 text-yellow-300" :
                                "bg-green-900/50 text-green-300"
                              }`}>
                                {String(f.recommended_action || "").replace(/_/g, " ")}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {Array.isArray(scheduleResult.follow_ups) && (scheduleResult.follow_ups as unknown[]).length === 0 && (
                <div className="bg-gray-800 rounded-lg p-8 text-center">
                  <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
                  <h3 className="text-lg font-semibold text-green-400">No Pending Follow-ups</h3>
                  <p className="text-sm text-gray-400 mt-1">All verifications and references are either completed or on track.</p>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
