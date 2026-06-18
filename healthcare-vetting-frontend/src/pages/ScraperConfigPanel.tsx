import { useEffect, useState } from "react";
import { scraperConfigApi } from "../api/client";
import { Save, CheckCircle2, AlertCircle, Loader2, ExternalLink } from "lucide-react";

/**
 * Admin panel for lead-generation scraper API keys.
 * Currently only the CQC Syndication API subscription key.
 */
export default function ScraperConfigPanel() {
  const token = localStorage.getItem("adminToken") || localStorage.getItem("token") || "";

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [cqcKey, setCqcKey] = useState("");
  const [cqcKeySet, setCqcKeySet] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const cfg = await scraperConfigApi.get(token);
        setCqcKey((cfg.cqc_api_subscription_key as string) || "");
        setCqcKeySet(Boolean(cfg.cqc_api_subscription_key_set));
      } catch (e) {
        setMessage({ type: "error", text: `Failed to load scraper config: ${(e as Error).message}` });
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  const save = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await scraperConfigApi.update(token, {
        // Don't send back a masked value (starts with *) — server skips those,
        // but also avoid sending the placeholder on the wire.
        cqc_api_subscription_key: cqcKey.startsWith("*") ? "" : cqcKey,
      });
      setMessage({ type: "success", text: "Scraper configuration saved" });
      // Reload to pick up the freshly-masked value
      const cfg = await scraperConfigApi.get(token);
      setCqcKey((cfg.cqc_api_subscription_key as string) || "");
      setCqcKeySet(Boolean(cfg.cqc_api_subscription_key_set));
    } catch (e) {
      setMessage({ type: "error", text: `Save failed: ${(e as Error).message}` });
    } finally {
      setSaving(false);
    }
  };

  const testCqc = async () => {
    setTesting(true);
    setMessage(null);
    try {
      const res = await scraperConfigApi.testCqc(token) as { status?: string; message?: string };
      if (res.status === "ok") {
        setMessage({ type: "success", text: res.message || "CQC API connectivity OK" });
      } else {
        setMessage({ type: "error", text: res.message || `CQC test failed (${res.status})` });
      }
    } catch (e) {
      setMessage({ type: "error", text: `Test failed: ${(e as Error).message}` });
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-slate-400 p-6">
        <Loader2 size={16} className="animate-spin" /> Loading scraper configuration…
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h2 className="text-xl font-bold text-white">Scraper Configuration</h2>
        <p className="text-sm text-slate-400 mt-1">
          API keys for lead-generation scrapers. Stored encrypted at rest and masked in the UI.
        </p>
      </div>

      {message && (
        <div
          className={`flex items-start gap-2 rounded-lg border px-4 py-3 text-sm ${
            message.type === "success"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : message.type === "error"
              ? "border-red-500/30 bg-red-500/10 text-red-300"
              : "border-blue-500/30 bg-blue-500/10 text-blue-300"
          }`}
        >
          {message.type === "success" ? <CheckCircle2 size={16} className="mt-0.5 flex-shrink-0" /> : <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />}
          <span>{message.text}</span>
        </div>
      )}

      <section className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-5 space-y-4">
        <div>
          <h3 className="text-white font-semibold">CQC Syndication API</h3>
          <p className="text-xs text-slate-400 mt-1">
            Required for CQC provider lead generation. Request a free subscription key from{" "}
            <a
              href="https://www.cqc.org.uk/about-us/transparency/using-cqc-data"
              target="_blank"
              rel="noreferrer"
              className="text-blue-300 hover:underline inline-flex items-center gap-1"
            >
              CQC “Using CQC data” page <ExternalLink size={12} />
            </a>
            . Click “Request API Subscription Key”, sign up, then paste the issued key here.
          </p>
        </div>

        <label className="block">
          <span className="text-xs font-medium text-slate-300">Subscription Key</span>
          <input
            type="text"
            value={cqcKey}
            onChange={(e) => setCqcKey(e.target.value)}
            placeholder={cqcKeySet ? "(key is set — enter a new one to replace it)" : "Paste your CQC subscription key"}
            className="mt-1 block w-full rounded-md bg-slate-900 border border-slate-700 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
            spellCheck={false}
            autoComplete="off"
          />
        </label>

        <div className="flex items-center gap-3">
          <button
            onClick={save}
            disabled={saving}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-md"
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            Save
          </button>
          <button
            onClick={testCqc}
            disabled={testing || !cqcKeySet}
            title={cqcKeySet ? "" : "Save a key first"}
            className="inline-flex items-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-md"
          >
            {testing ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
            Test CQC connectivity
          </button>
          {cqcKeySet && (
            <span className="text-xs text-emerald-400">Key is configured</span>
          )}
        </div>
      </section>
    </div>
  );
}
