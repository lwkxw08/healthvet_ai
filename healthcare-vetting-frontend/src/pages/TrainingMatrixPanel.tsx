import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import {
  trainingCatalogueApi,
  industryTemplatesApi,
  type TrainingCourse,
} from "../api/client";
import {
  Plus,
  Edit2,
  Trash2,
  Save,
  X,
  Upload,
  Download,
  RefreshCw,
  ShieldAlert,
  Info,
} from "lucide-react";

interface IndustryTemplate {
  id: string;
  name: string;
  description?: string;
  is_default?: boolean;
}

interface CourseDraft {
  name: string;
  aliases: string;
  category: string;
  description: string;
  default_validity_months: number;
  is_mandatory: boolean;
  is_active: boolean;
  sort_order: number;
}

const EMPTY_DRAFT: CourseDraft = {
  name: "",
  aliases: "",
  category: "mandatory",
  description: "",
  default_validity_months: 12,
  is_mandatory: true,
  is_active: true,
  sort_order: 0,
};

export default function TrainingMatrixPanel() {
  const { token } = useAuth();
  const [templates, setTemplates] = useState<IndustryTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
  const [policy, setPolicy] = useState<"pass_fail" | "informational">("pass_fail");
  const [courses, setCourses] = useState<TrainingCourse[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ kind: "info" | "error" | "success"; text: string } | null>(null);

  const [draft, setDraft] = useState<CourseDraft>(EMPTY_DRAFT);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingDraft, setEditingDraft] = useState<CourseDraft>(EMPTY_DRAFT);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);

  const loadTemplates = useCallback(async () => {
    if (!token) return;
    try {
      const res = await industryTemplatesApi.list(token);
      const list = (res as unknown as IndustryTemplate[]) ?? [];
      setTemplates(list);
      if (!selectedTemplateId && list.length > 0) {
        const def = list.find(t => t.is_default) ?? list[0];
        setSelectedTemplateId(def.id);
      }
    } catch (e) {
      setMessage({ kind: "error", text: `Failed to load industry templates: ${(e as Error).message}` });
    }
  }, [token, selectedTemplateId]);

  const loadCatalogue = useCallback(async () => {
    if (!token || !selectedTemplateId) return;
    setLoading(true);
    try {
      const [coursesRes, policyRes] = await Promise.all([
        trainingCatalogueApi.list(token, selectedTemplateId, true),
        trainingCatalogueApi.getPolicy(token, selectedTemplateId),
      ]);
      setCourses(coursesRes.courses || []);
      setPolicy(policyRes.training_policy);
    } catch (e) {
      setMessage({ kind: "error", text: `Failed to load courses: ${(e as Error).message}` });
    } finally {
      setLoading(false);
    }
  }, [token, selectedTemplateId]);

  useEffect(() => { loadTemplates(); }, [loadTemplates]);
  useEffect(() => { loadCatalogue(); }, [loadCatalogue]);

  const onPolicyChange = async (next: "pass_fail" | "informational") => {
    if (!token || !selectedTemplateId) return;
    try {
      await trainingCatalogueApi.setPolicy(token, selectedTemplateId, next);
      setPolicy(next);
      setMessage({ kind: "success", text: `Training policy set to ${next === "pass_fail" ? "Pass / Fail" : "Informational only"}` });
    } catch (e) {
      setMessage({ kind: "error", text: `Failed to update policy: ${(e as Error).message}` });
    }
  };

  const addCourse = async () => {
    if (!token || !selectedTemplateId || !draft.name.trim()) return;
    setSaving(true);
    try {
      await trainingCatalogueApi.create(token, {
        industry_template_id: selectedTemplateId,
        name: draft.name.trim(),
        aliases: draft.aliases.split(";").map(a => a.trim()).filter(Boolean),
        category: draft.category,
        description: draft.description || undefined,
        default_validity_months: Number(draft.default_validity_months) || 12,
        is_mandatory: draft.is_mandatory,
        is_active: draft.is_active,
        sort_order: Number(draft.sort_order) || 0,
      });
      setDraft(EMPTY_DRAFT);
      setMessage({ kind: "success", text: "Course added" });
      await loadCatalogue();
    } catch (e) {
      setMessage({ kind: "error", text: `Failed to add course: ${(e as Error).message}` });
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (course: TrainingCourse) => {
    setEditingId(course.id);
    setEditingDraft({
      name: course.name,
      aliases: (course.aliases || []).join("; "),
      category: course.category,
      description: course.description || "",
      default_validity_months: course.default_validity_months,
      is_mandatory: course.is_mandatory,
      is_active: course.is_active,
      sort_order: course.sort_order,
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditingDraft(EMPTY_DRAFT);
  };

  const saveEdit = async () => {
    if (!token || !editingId) return;
    setSaving(true);
    try {
      await trainingCatalogueApi.update(token, editingId, {
        name: editingDraft.name,
        aliases: editingDraft.aliases.split(";").map(a => a.trim()).filter(Boolean),
        category: editingDraft.category,
        description: editingDraft.description || undefined,
        default_validity_months: Number(editingDraft.default_validity_months) || 12,
        is_mandatory: editingDraft.is_mandatory,
        is_active: editingDraft.is_active,
        sort_order: Number(editingDraft.sort_order) || 0,
      });
      setMessage({ kind: "success", text: "Course updated" });
      cancelEdit();
      await loadCatalogue();
    } catch (e) {
      setMessage({ kind: "error", text: `Failed to update course: ${(e as Error).message}` });
    } finally {
      setSaving(false);
    }
  };

  const deleteCourse = async (id: string) => {
    if (!token) return;
    if (!window.confirm("Delete this course? Candidates who've submitted it will keep their records but the course will no longer appear in the dropdown.")) return;
    try {
      await trainingCatalogueApi.remove(token, id);
      setMessage({ kind: "success", text: "Course deleted" });
      await loadCatalogue();
    } catch (e) {
      setMessage({ kind: "error", text: `Failed to delete course: ${(e as Error).message}` });
    }
  };

  const handleCsvImport = async (file: File) => {
    if (!token || !selectedTemplateId) return;
    setImporting(true);
    try {
      const res = await trainingCatalogueApi.importCsv(token, selectedTemplateId, file);
      const errs = res.errors && res.errors.length > 0 ? ` (${res.errors.length} error(s))` : "";
      setMessage({
        kind: res.errors && res.errors.length > 0 ? "error" : "success",
        text: `Imported: ${res.created} created, ${res.updated} updated${errs}`,
      });
      await loadCatalogue();
    } catch (e) {
      setMessage({ kind: "error", text: `Import failed: ${(e as Error).message}` });
    } finally {
      setImporting(false);
    }
  };

  const downloadCsvTemplate = () => {
    const csv = "name,aliases,category,default_validity_months,is_mandatory,description\nManual Handling,Moving and Handling;Moving & Handling,mandatory,12,true,Safe moving and handling of people and loads\nBasic Life Support (BLS),BLS;CPR;Life Support,mandatory,12,true,Resuscitation at the level expected for healthcare workers\n";
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "training_courses_template.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const inputClass = "w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:ring-2 focus:ring-blue-500";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <ShieldAlert size={20} className="text-blue-400" /> Training Matrix
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Manage the per-industry training courses candidates can choose from, and whether training is a pass/fail check.
          </p>
        </div>
        <button onClick={loadCatalogue} className="flex items-center gap-1 text-xs text-slate-300 hover:text-white">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {message && (
        <div className={`px-4 py-2 rounded-lg text-xs ${
          message.kind === "error" ? "bg-red-500/10 border border-red-500/30 text-red-300"
          : message.kind === "success" ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-300"
          : "bg-blue-500/10 border border-blue-500/30 text-blue-300"
        }`}>
          {message.text}
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
          <label className="text-xs text-slate-400 block mb-2">Industry template</label>
          <select
            className={inputClass}
            value={selectedTemplateId}
            onChange={e => setSelectedTemplateId(e.target.value)}
          >
            <option value="">Select an industry template…</option>
            {templates.map(t => (
              <option key={t.id} value={t.id}>
                {t.name}{t.is_default ? " (default)" : ""}
              </option>
            ))}
          </select>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
          <label className="text-xs text-slate-400 block mb-2">Training policy for this industry</label>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPolicyChange("pass_fail")}
              disabled={!selectedTemplateId}
              className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium border transition-all ${
                policy === "pass_fail"
                  ? "bg-blue-500/20 border-blue-500/40 text-blue-300"
                  : "bg-slate-700/30 border-slate-600 text-slate-400 hover:text-slate-200"
              }`}
            >
              Pass / Fail
            </button>
            <button
              onClick={() => onPolicyChange("informational")}
              disabled={!selectedTemplateId}
              className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium border transition-all ${
                policy === "informational"
                  ? "bg-blue-500/20 border-blue-500/40 text-blue-300"
                  : "bg-slate-700/30 border-slate-600 text-slate-400 hover:text-slate-200"
              }`}
            >
              Informational only
            </button>
          </div>
          <p className="text-[11px] text-slate-500 mt-2 flex items-start gap-1">
            <Info size={12} className="mt-0.5 flex-shrink-0" />
            Pass / Fail blocks overall compliance if mandatory courses are missing or expired. Informational only records training but never fails the candidate.
          </p>
        </div>
      </div>

      {selectedTemplateId && (
        <>
          {/* Add course */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white">Add a course</h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={downloadCsvTemplate}
                  className="text-xs text-slate-300 hover:text-white flex items-center gap-1"
                >
                  <Download size={14} /> CSV template
                </button>
                <label className={`text-xs px-3 py-1.5 rounded-lg border border-slate-600 bg-slate-700/30 hover:bg-slate-700 cursor-pointer flex items-center gap-1 ${importing ? "opacity-60 cursor-wait" : ""}`}>
                  <Upload size={14} /> {importing ? "Importing…" : "Import CSV"}
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    className="hidden"
                    onChange={e => {
                      const f = e.target.files?.[0];
                      if (f) handleCsvImport(f);
                      e.target.value = "";
                    }}
                  />
                </label>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="sm:col-span-3">
                <label className="text-xs text-slate-400">Name *</label>
                <input className={inputClass} value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} placeholder="e.g. Manual Handling" />
              </div>
              <div className="sm:col-span-3">
                <label className="text-xs text-slate-400">Aliases <span className="text-slate-500">(semicolon-separated — used to match variant spellings)</span></label>
                <input className={inputClass} value={draft.aliases} onChange={e => setDraft({ ...draft, aliases: e.target.value })} placeholder="Moving and Handling; Moving & Handling" />
              </div>
              <div>
                <label className="text-xs text-slate-400">Category</label>
                <select className={inputClass} value={draft.category} onChange={e => setDraft({ ...draft, category: e.target.value })}>
                  <option value="mandatory">Mandatory</option>
                  <option value="specialist">Specialist</option>
                  <option value="cpd">CPD</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400">Validity (months)</label>
                <input type="number" min={1} className={inputClass} value={draft.default_validity_months} onChange={e => setDraft({ ...draft, default_validity_months: Number(e.target.value) })} />
              </div>
              <div>
                <label className="text-xs text-slate-400">Sort order</label>
                <input type="number" className={inputClass} value={draft.sort_order} onChange={e => setDraft({ ...draft, sort_order: Number(e.target.value) })} />
              </div>
              <div className="sm:col-span-3">
                <label className="text-xs text-slate-400">Description</label>
                <input className={inputClass} value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} />
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input type="checkbox" checked={draft.is_mandatory} onChange={e => setDraft({ ...draft, is_mandatory: e.target.checked })} />
                Mandatory (required for pass)
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input type="checkbox" checked={draft.is_active} onChange={e => setDraft({ ...draft, is_active: e.target.checked })} />
                Active (shown to candidates)
              </label>
              <div className="flex items-end">
                <button
                  onClick={addCourse}
                  disabled={saving || !draft.name.trim()}
                  className="w-full px-3 py-2 rounded-lg bg-blue-500/20 border border-blue-500/40 text-blue-300 hover:bg-blue-500/30 text-xs font-medium flex items-center justify-center gap-1 disabled:opacity-50"
                >
                  <Plus size={14} /> {saving ? "Saving…" : "Add course"}
                </button>
              </div>
            </div>
          </div>

          {/* Course list */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-white mb-3">
              Courses <span className="text-slate-500 font-normal">({courses.length})</span>
            </h3>
            {loading ? (
              <div className="text-slate-400 text-sm py-6 text-center">Loading…</div>
            ) : courses.length === 0 ? (
              <div className="text-slate-500 text-sm py-6 text-center">No courses configured yet. Add one above or import a CSV.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-400 border-b border-slate-700">
                      <th className="text-left p-2">Name</th>
                      <th className="text-left p-2">Aliases</th>
                      <th className="text-left p-2">Category</th>
                      <th className="text-center p-2">Validity</th>
                      <th className="text-center p-2">Mandatory</th>
                      <th className="text-center p-2">Active</th>
                      <th className="text-right p-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {courses.map(c => {
                      const editing = editingId === c.id;
                      return (
                        <tr key={c.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 align-top">
                          <td className="p-2 text-white">
                            {editing ? (
                              <input className={inputClass} value={editingDraft.name} onChange={e => setEditingDraft({ ...editingDraft, name: e.target.value })} />
                            ) : (
                              <div>
                                <div className="font-medium">{c.name}</div>
                                {c.description && <div className="text-slate-500 mt-0.5">{c.description}</div>}
                              </div>
                            )}
                          </td>
                          <td className="p-2 text-slate-300 max-w-xs">
                            {editing ? (
                              <input className={inputClass} value={editingDraft.aliases} onChange={e => setEditingDraft({ ...editingDraft, aliases: e.target.value })} />
                            ) : (
                              <div className="truncate">{(c.aliases || []).join("; ") || "—"}</div>
                            )}
                          </td>
                          <td className="p-2 text-slate-300">
                            {editing ? (
                              <select className={inputClass} value={editingDraft.category} onChange={e => setEditingDraft({ ...editingDraft, category: e.target.value })}>
                                <option value="mandatory">Mandatory</option>
                                <option value="specialist">Specialist</option>
                                <option value="cpd">CPD</option>
                                <option value="other">Other</option>
                              </select>
                            ) : c.category}
                          </td>
                          <td className="p-2 text-slate-300 text-center">
                            {editing ? (
                              <input type="number" min={1} className={inputClass} value={editingDraft.default_validity_months} onChange={e => setEditingDraft({ ...editingDraft, default_validity_months: Number(e.target.value) })} />
                            ) : `${c.default_validity_months}m`}
                          </td>
                          <td className="p-2 text-center">
                            {editing ? (
                              <input type="checkbox" checked={editingDraft.is_mandatory} onChange={e => setEditingDraft({ ...editingDraft, is_mandatory: e.target.checked })} />
                            ) : c.is_mandatory ? (
                              <span className="text-emerald-400">Yes</span>
                            ) : (
                              <span className="text-slate-500">No</span>
                            )}
                          </td>
                          <td className="p-2 text-center">
                            {editing ? (
                              <input type="checkbox" checked={editingDraft.is_active} onChange={e => setEditingDraft({ ...editingDraft, is_active: e.target.checked })} />
                            ) : c.is_active ? (
                              <span className="text-emerald-400">Yes</span>
                            ) : (
                              <span className="text-slate-500">No</span>
                            )}
                          </td>
                          <td className="p-2 text-right whitespace-nowrap">
                            {editing ? (
                              <div className="flex items-center justify-end gap-1">
                                <button onClick={saveEdit} disabled={saving} className="p-1.5 rounded bg-blue-500/20 text-blue-300 hover:bg-blue-500/30 disabled:opacity-50" title="Save"><Save size={14} /></button>
                                <button onClick={cancelEdit} className="p-1.5 rounded bg-slate-700 text-slate-300 hover:bg-slate-600" title="Cancel"><X size={14} /></button>
                              </div>
                            ) : (
                              <div className="flex items-center justify-end gap-1">
                                <button onClick={() => startEdit(c)} className="p-1.5 rounded bg-slate-700 text-slate-300 hover:bg-slate-600" title="Edit"><Edit2 size={14} /></button>
                                <button onClick={() => deleteCourse(c.id)} className="p-1.5 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20" title="Delete"><Trash2 size={14} /></button>
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
