import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import { documentsApi } from "../api/client";
import {
  Upload, FileText, Image, Trash2, Download, Eye, RefreshCw,
  File, AlertTriangle, CheckCircle, Shield, Clock,
} from "lucide-react";

const CATEGORIES = [
  { value: "auto", label: "Auto-Detect" },
  { value: "cv", label: "CV / Resume" },
  { value: "identity_document", label: "Identity Document" },
  { value: "dbs_certificate", label: "DBS Certificate" },
  { value: "right_to_work", label: "Right to Work" },
  { value: "training_cert", label: "Training Certificate" },
  { value: "qualification", label: "Qualification" },
  { value: "reference_letter", label: "Reference Letter" },
  { value: "other", label: "Other" },
];

interface DocumentUploadPanelProps {
  candidateId?: string;
  viewMode?: "candidate" | "agency" | "admin";
}

export default function DocumentUploadPanel({ candidateId, viewMode = "candidate" }: DocumentUploadPanelProps) {
  const { token } = useAuth();
  const [documents, setDocuments] = useState<Record<string, unknown>[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [category, setCategory] = useState("auto");
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocuments = useCallback(async () => {
    if (!token) return;
    try {
      const r = await documentsApi.list(token, candidateId);
      setDocuments(r.documents || []);
    } catch { setDocuments([]); }
  }, [token, candidateId]);

  useEffect(() => { loadDocuments(); }, [loadDocuments]);

  const handleUpload = async (files: FileList | File[]) => {
    if (!token || files.length === 0) return;
    setUploading(true);
    setError("");

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setUploadProgress(`Uploading ${file.name} (${i + 1}/${files.length})...`);
      try {
        await documentsApi.upload(token, file, category === "auto" ? undefined : category, candidateId);
      } catch (e) {
        setError(`Failed to upload ${file.name}: ${e}`);
      }
    }

    setUploading(false);
    setUploadProgress(null);
    loadDocuments();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files.length > 0) {
      handleUpload(e.dataTransfer.files);
    }
  };

  const handleDelete = async (docId: string) => {
    if (!token) return;
    setDeletingId(docId);
    try {
      await documentsApi.delete(token, docId);
      loadDocuments();
    } catch (e) {
      setError(`Delete failed: ${e}`);
    } finally {
      setDeletingId("");
    }
  };

  const handleView = async (docId: string) => {
    if (!token) return;
    try {
      const r = await documentsApi.getSignedUrl(token, docId);
      window.open(r.signed_url, "_blank");
    } catch {
      setError("Could not generate download link");
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const categoryLabel = (cat: string) => CATEGORIES.find(c => c.value === cat)?.label || cat;

  const FileIcon = ({ contentType }: { contentType: string }) => {
    if (contentType.startsWith("image/")) return <Image className="w-5 h-5 text-blue-400" />;
    if (contentType === "application/pdf") return <FileText className="w-5 h-5 text-red-400" />;
    return <File className="w-5 h-5 text-gray-400" />;
  };

  const ScanBadge = ({ status }: { status: string }) => {
    if (status === "clean") return <span className="flex items-center gap-1 text-xs text-green-400"><CheckCircle className="w-3 h-3" /> Clean</span>;
    if (status === "infected") return <span className="flex items-center gap-1 text-xs text-red-400"><AlertTriangle className="w-3 h-3" /> Infected</span>;
    if (status === "skipped") return <span className="flex items-center gap-1 text-xs text-gray-500"><Shield className="w-3 h-3" /> Skipped</span>;
    return <span className="flex items-center gap-1 text-xs text-yellow-400"><Clock className="w-3 h-3" /> Pending</span>;
  };

  return (
    <div className="space-y-4">
      {/* Upload area */}
      <div
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
          dragActive ? "border-purple-400 bg-purple-900/20" : "border-gray-600 hover:border-gray-500"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
      >
        <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
        <p className="text-sm text-gray-300 mb-2">
          {dragActive ? "Drop files here..." : "Drag & drop files here, or click to browse"}
        </p>
        <p className="text-xs text-gray-500 mb-3">PDF, images, Word documents up to 20MB</p>

        <div className="flex items-center justify-center gap-3">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-300"
          >
            {CATEGORIES.map(c => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>

          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white px-4 py-1.5 rounded text-sm flex items-center gap-2"
          >
            {uploading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            {uploading ? "Uploading..." : "Choose Files"}
          </button>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.jpg,.jpeg,.png,.gif,.webp,.doc,.docx,.txt,.csv"
            className="hidden"
            onChange={(e) => e.target.files && handleUpload(e.target.files)}
          />
        </div>

        {uploadProgress && <p className="text-xs text-purple-400 mt-2">{uploadProgress}</p>}
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded p-3 text-sm text-red-300 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" /> {error}
          <button onClick={() => setError("")} className="ml-auto text-xs underline">Dismiss</button>
        </div>
      )}

      {/* Document List */}
      <div className="bg-gray-800 rounded-lg">
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h3 className="text-sm font-semibold text-gray-300">Documents ({documents.length})</h3>
          <button onClick={loadDocuments} className="text-xs text-gray-400 hover:text-white flex items-center gap-1">
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
        </div>

        {documents.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">No documents uploaded yet</div>
        ) : (
          <div className="divide-y divide-gray-700">
            {documents.map((doc) => (
              <div key={String(doc.id)} className="p-3 flex items-center gap-3 hover:bg-gray-700/30">
                <FileIcon contentType={String(doc.content_type)} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-200 truncate">{String(doc.file_name)}</p>
                  <div className="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
                    <span className="px-1.5 py-0.5 rounded bg-gray-700 text-gray-300">{categoryLabel(String(doc.category))}</span>
                    <span>{formatSize(Number(doc.file_size))}</span>
                    <span>{String(doc.created_at || "").slice(0, 10)}</span>
                    <ScanBadge status={String(doc.virus_scan_status)} />
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleView(String(doc.id))}
                    className="p-1.5 rounded hover:bg-gray-600 text-gray-400 hover:text-white"
                    title="View / Download"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                  {(viewMode === "admin" || viewMode === "candidate") && (
                    <button
                      onClick={() => handleDelete(String(doc.id))}
                      disabled={deletingId === String(doc.id)}
                      className="p-1.5 rounded hover:bg-red-900/50 text-gray-400 hover:text-red-400"
                      title="Delete"
                    >
                      {deletingId === String(doc.id) ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
