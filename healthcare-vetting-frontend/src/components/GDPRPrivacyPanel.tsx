/**
 * GDPR self-serve privacy panel for the candidate portal.
 * Provides "Download My Data" and "Delete My Data" functionality.
 */
import { useState } from "react";
import { gdprApi } from "../api/client";
import { Download, Trash2, Shield, AlertTriangle, CheckCircle } from "lucide-react";

interface Props {
  token: string;
  userId: string;
}

export default function GDPRPrivacyPanel({ token, userId }: Props) {
  const [exportStatus, setExportStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [exportData, setExportData] = useState<Record<string, unknown> | null>(null);
  const [deleteStatus, setDeleteStatus] = useState<"idle" | "confirming" | "loading" | "done" | "error">("idle");
  const [deleteReason, setDeleteReason] = useState("");
  const [message, setMessage] = useState("");

  const handleExport = async () => {
    setExportStatus("loading");
    setMessage("");
    try {
      const data = await gdprApi.requestDataExport(token, userId);
      setExportData(data);
      setExportStatus("done");

      // Trigger download as JSON file
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `viperai-my-data-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setMessage("Your data has been exported and downloaded.");
    } catch (err) {
      setExportStatus("error");
      setMessage(err instanceof Error ? err.message : "Failed to export data");
    }
  };

  const handleDelete = async () => {
    if (!deleteReason.trim() || deleteReason.length < 5) {
      setMessage("Please provide a reason (minimum 5 characters)");
      return;
    }
    setDeleteStatus("loading");
    setMessage("");
    try {
      await gdprApi.requestErasure(token, userId, deleteReason);
      setDeleteStatus("done");
      setMessage("Your data deletion request has been processed. Your personal information has been anonymised.");
    } catch (err) {
      setDeleteStatus("error");
      setMessage(err instanceof Error ? err.message : "Failed to process deletion request");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-4">
        <Shield size={24} className="text-blue-400" />
        <div>
          <h2 className="text-lg font-bold text-white">Your Privacy & Data Rights</h2>
          <p className="text-xs text-slate-400">Under UK GDPR, you have the right to access and delete your personal data.</p>
        </div>
      </div>

      {/* Download My Data */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <div className="flex items-start gap-3">
          <Download size={20} className="text-blue-400 mt-0.5 shrink-0" />
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-white">Download My Data</h3>
            <p className="text-xs text-slate-400 mt-1">
              Request a copy of all personal data we hold about you. This includes your profile information,
              vetting records, compliance history, and consent logs. The data will be downloaded as a JSON file.
            </p>
            <button
              onClick={handleExport}
              disabled={exportStatus === "loading"}
              className="mt-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:opacity-50 text-white text-xs px-4 py-2 rounded-lg font-medium flex items-center gap-2"
            >
              {exportStatus === "loading" ? (
                <><span className="animate-spin">&#8987;</span> Exporting...</>
              ) : (
                <><Download size={14} /> Download My Data</>
              )}
            </button>
            {exportStatus === "done" && exportData && (
              <div className="mt-2 flex items-center gap-2 text-green-400 text-xs">
                <CheckCircle size={14} /> Data exported successfully
                — {Object.keys((exportData as Record<string, unknown>).sections || {}).length} sections included
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Delete My Data */}
      <div className="bg-slate-800/50 border border-red-500/30 rounded-xl p-5">
        <div className="flex items-start gap-3">
          <Trash2 size={20} className="text-red-400 mt-0.5 shrink-0" />
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-white">Delete My Data</h3>
            <p className="text-xs text-slate-400 mt-1">
              Request the deletion of your personal data. Your profile will be anonymised and personal identifiers removed.
              Some data may be retained where required by law (e.g., DBS records within the regulatory retention period).
            </p>

            {deleteStatus === "done" ? (
              <div className="mt-3 flex items-center gap-2 text-green-400 text-xs">
                <CheckCircle size={14} /> Your data has been anonymised. You will be signed out.
              </div>
            ) : deleteStatus === "confirming" ? (
              <div className="mt-3 space-y-3">
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-red-300 text-xs font-semibold mb-2">
                    <AlertTriangle size={14} /> This action cannot be undone
                  </div>
                  <p className="text-xs text-slate-300">
                    Your personal information will be permanently removed. Any active vetting processes will be cancelled.
                    Data required for legal compliance will be anonymised but retained.
                  </p>
                </div>
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Reason for deletion request:</label>
                  <input
                    type="text"
                    value={deleteReason}
                    onChange={(e) => setDeleteReason(e.target.value)}
                    placeholder="e.g., No longer using the service"
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleDelete}
                    disabled={deleteReason.length < 5}
                    className="bg-red-600 hover:bg-red-700 disabled:bg-red-800 disabled:opacity-50 text-white text-xs px-4 py-2 rounded-lg font-medium"
                  >
                    Confirm Deletion
                  </button>
                  <button
                    onClick={() => { setDeleteStatus("idle"); setDeleteReason(""); }}
                    className="bg-slate-600 hover:bg-slate-500 text-white text-xs px-4 py-2 rounded-lg font-medium"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setDeleteStatus("confirming")}
                className="mt-3 bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 text-xs px-4 py-2 rounded-lg font-medium flex items-center gap-2"
              >
                <Trash2 size={14} /> Request Data Deletion
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Status message */}
      {message && (
        <div className={`text-xs px-4 py-2 rounded-lg ${
          exportStatus === "error" || deleteStatus === "error"
            ? "bg-red-500/10 text-red-400 border border-red-500/30"
            : "bg-green-500/10 text-green-400 border border-green-500/30"
        }`}>
          {message}
        </div>
      )}

      {/* Privacy Notice Link */}
      <div className="text-xs text-slate-500 border-t border-slate-700 pt-4">
        For more information about how we handle your data, see our{" "}
        <a href="#" className="text-blue-400 hover:text-blue-300 underline">Privacy Policy</a>.
        If you have any questions, contact our Data Protection Officer at{" "}
        <span className="text-slate-300">privacy@viperai.io</span>.
      </div>
    </div>
  );
}
