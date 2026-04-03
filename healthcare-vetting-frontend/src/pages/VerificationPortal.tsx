import { useState } from "react";
import { apiRequest } from "../api/client";

// ── Types ────────────────────────────────────────────────────────────────────

interface LookupResponse {
  type: "employment" | "reference";
  status: string;
  already_completed: boolean;
  completed_at?: string;
  message?: string;
  form_data?: {
    candidate_name?: string;
    employer_name?: string;
    verifier_name?: string;
    job_title?: string;
    start_date?: string;
    end_date?: string;
    referee_name?: string;
    referee_organisation?: string;
  };
}

interface SubmitResponse {
  success: boolean;
  status: string;
  message: string;
}

// ── Main Component ───────────────────────────────────────────────────────────

export default function VerificationPortal() {
  const [step, setStep] = useState<"code" | "form" | "done">("code");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lookupData, setLookupData] = useState<LookupResponse | null>(null);
  const [submitResult, setSubmitResult] = useState<SubmitResponse | null>(null);

  // Employment form state
  const [empJobTitleConfirmed, setEmpJobTitleConfirmed] = useState<boolean | null>(null);
  const [empDatesConfirmed, setEmpDatesConfirmed] = useState<boolean | null>(null);
  const [empReasonForLeaving, setEmpReasonForLeaving] = useState("");
  const [empComments, setEmpComments] = useState("");
  const [empResponderName, setEmpResponderName] = useState("");
  const [empResponderTitle, setEmpResponderTitle] = useState("");

  // Reference form state
  const [refPerformance, setRefPerformance] = useState(0);
  const [refConduct, setRefConduct] = useState(0);
  const [refReliability, setRefReliability] = useState(0);
  const [refWouldRehire, setRefWouldRehire] = useState<boolean | null>(null);
  const [refRelationship, setRefRelationship] = useState("");
  const [refKnownSince, setRefKnownSince] = useState("");
  const [refStrengths, setRefStrengths] = useState("");
  const [refImprovements, setRefImprovements] = useState("");
  const [refComments, setRefComments] = useState("");
  const [refResponderName, setRefResponderName] = useState("");
  const [refResponderTitle, setRefResponderTitle] = useState("");

  // Format code as user types (HV-XXXX-XXXX)
  const handleCodeChange = (raw: string) => {
    const cleaned = raw.toUpperCase().replace(/[^A-Z0-9-]/g, "");
    setCode(cleaned);
  };

  const handleLookup = async () => {
    if (!code.trim()) {
      setError("Please enter your verification code");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest<LookupResponse>("/api/verify/lookup", {
        method: "POST",
        body: { code: code.trim() },
      });
      setLookupData(data);
      if (data.already_completed || data.status === "expired") {
        setStep("done");
        setSubmitResult({
          success: true,
          status: data.status,
          message: data.message || "This verification has already been completed.",
        });
      } else {
        setStep("form");
        // Pre-fill responder name if available
        if (data.type === "employment" && data.form_data?.verifier_name) {
          setEmpResponderName(data.form_data.verifier_name);
        }
        if (data.type === "reference" && data.form_data?.referee_name) {
          setRefResponderName(data.form_data.referee_name);
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Code not found";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitEmployment = async () => {
    if (empJobTitleConfirmed === null || empDatesConfirmed === null) {
      setError("Please confirm both the job title and dates of employment");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await apiRequest<SubmitResponse>("/api/verify/submit/employment", {
        method: "POST",
        body: {
          code: code.trim(),
          job_title_confirmed: empJobTitleConfirmed,
          dates_confirmed: empDatesConfirmed,
          reason_for_leaving_confirmed: empReasonForLeaving || null,
          additional_comments: empComments || null,
          responder_name: empResponderName || null,
          responder_job_title: empResponderTitle || null,
        },
      });
      setSubmitResult(result);
      setStep("done");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Submission failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitReference = async () => {
    if (refPerformance === 0 || refConduct === 0 || refReliability === 0) {
      setError("Please provide all three ratings");
      return;
    }
    if (refWouldRehire === null) {
      setError("Please indicate whether you would rehire this candidate");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await apiRequest<SubmitResponse>("/api/verify/submit/reference", {
        method: "POST",
        body: {
          code: code.trim(),
          performance_rating: refPerformance,
          conduct_rating: refConduct,
          reliability_rating: refReliability,
          would_rehire: refWouldRehire,
          relationship_to_candidate: refRelationship || null,
          known_since: refKnownSince || null,
          strengths: refStrengths || null,
          areas_for_improvement: refImprovements || null,
          additional_comments: refComments || null,
          responder_name: refResponderName || null,
          responder_job_title: refResponderTitle || null,
        },
      });
      setSubmitResult(result);
      setStep("done");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Submission failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* Header */}
      <header className="bg-slate-900 text-white py-6">
        <div className="max-w-2xl mx-auto px-4 text-center">
          <h1 className="text-2xl font-bold text-blue-400">HealthVet AI</h1>
          <p className="text-slate-400 text-sm mt-1">Secure Verification Portal</p>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8">
        {/* Step 1: Enter Code */}
        {step === "code" && (
          <div className="bg-white rounded-xl shadow-lg p-8">
            <div className="text-center mb-8">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-slate-900">Verification Request</h2>
              <p className="text-slate-600 mt-2">
                You've received an email asking you to verify employment or provide a professional reference.
                Enter the code from that email below.
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Verification Code</label>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => handleCodeChange(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleLookup()}
                  placeholder="HV-XXXX-XXXX"
                  className="w-full px-4 py-3 text-center text-2xl font-mono tracking-widest border-2 border-slate-200 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all"
                  maxLength={14}
                  autoFocus
                />
                <p className="text-xs text-slate-500 mt-1 text-center">
                  The code is in the format HV-XXXX-XXXX and can be found in the email you received
                </p>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                  {error}
                </div>
              )}

              <button
                onClick={handleLookup}
                disabled={loading || !code.trim()}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
              >
                {loading ? "Looking up..." : "Continue"}
              </button>
            </div>

            <div className="mt-8 pt-6 border-t border-slate-100">
              <div className="flex items-start gap-3 text-xs text-slate-500">
                <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <p>
                  This is a secure portal operated by HealthVet AI Ltd. Your responses are encrypted
                  and processed in accordance with UK GDPR. Data is retained for 6 years per regulatory requirements.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Form */}
        {step === "form" && lookupData && (
          <div className="bg-white rounded-xl shadow-lg p-8">
            {lookupData.type === "employment" ? (
              <EmploymentForm
                formData={lookupData.form_data!}
                jobTitleConfirmed={empJobTitleConfirmed}
                setJobTitleConfirmed={setEmpJobTitleConfirmed}
                datesConfirmed={empDatesConfirmed}
                setDatesConfirmed={setEmpDatesConfirmed}
                reasonForLeaving={empReasonForLeaving}
                setReasonForLeaving={setEmpReasonForLeaving}
                comments={empComments}
                setComments={setEmpComments}
                responderName={empResponderName}
                setResponderName={setEmpResponderName}
                responderTitle={empResponderTitle}
                setResponderTitle={setEmpResponderTitle}
                error={error}
                loading={loading}
                onSubmit={handleSubmitEmployment}
                onBack={() => { setStep("code"); setError(""); }}
              />
            ) : (
              <ReferenceForm
                formData={lookupData.form_data!}
                performance={refPerformance}
                setPerformance={setRefPerformance}
                conduct={refConduct}
                setConduct={setRefConduct}
                reliability={refReliability}
                setReliability={setRefReliability}
                wouldRehire={refWouldRehire}
                setWouldRehire={setRefWouldRehire}
                relationship={refRelationship}
                setRelationship={setRefRelationship}
                knownSince={refKnownSince}
                setKnownSince={setRefKnownSince}
                strengths={refStrengths}
                setStrengths={setRefStrengths}
                improvements={refImprovements}
                setImprovements={setRefImprovements}
                comments={refComments}
                setComments={setRefComments}
                responderName={refResponderName}
                setResponderName={setRefResponderName}
                responderTitle={refResponderTitle}
                setResponderTitle={setRefResponderTitle}
                error={error}
                loading={loading}
                onSubmit={handleSubmitReference}
                onBack={() => { setStep("code"); setError(""); }}
              />
            )}
          </div>
        )}

        {/* Step 3: Done */}
        {step === "done" && submitResult && (
          <div className="bg-white rounded-xl shadow-lg p-8 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center bg-green-100">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mb-2">
              {submitResult.status === "expired" ? "Code Expired" : "Response Recorded"}
            </h2>
            <p className="text-slate-600 mb-6">{submitResult.message}</p>
            {submitResult.status !== "expired" && (
              <p className="text-sm text-slate-500">
                You can safely close this page. No further action is required.
              </p>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="py-6 text-center text-xs text-slate-400">
        <p>HealthVet AI Ltd | Registered in England & Wales</p>
        <p className="mt-1">
          Questions? Contact{" "}
          <a href="mailto:verify@healthvet.ai" className="text-blue-500 hover:underline">
            verify@healthvet.ai
          </a>
        </p>
      </footer>
    </div>
  );
}

// ── Employment Verification Form ─────────────────────────────────────────────

function EmploymentForm({
  formData,
  jobTitleConfirmed,
  setJobTitleConfirmed,
  datesConfirmed,
  setDatesConfirmed,
  reasonForLeaving,
  setReasonForLeaving,
  comments,
  setComments,
  responderName,
  setResponderName,
  responderTitle,
  setResponderTitle,
  error,
  loading,
  onSubmit,
  onBack,
}: {
  formData: NonNullable<LookupResponse["form_data"]>;
  jobTitleConfirmed: boolean | null;
  setJobTitleConfirmed: (v: boolean) => void;
  datesConfirmed: boolean | null;
  setDatesConfirmed: (v: boolean) => void;
  reasonForLeaving: string;
  setReasonForLeaving: (v: string) => void;
  comments: string;
  setComments: (v: string) => void;
  responderName: string;
  setResponderName: (v: string) => void;
  responderTitle: string;
  setResponderTitle: (v: string) => void;
  error: string;
  loading: boolean;
  onSubmit: () => void;
  onBack: () => void;
}) {
  return (
    <>
      <div className="flex items-center gap-3 mb-6">
        <button onClick={onBack} className="text-slate-400 hover:text-slate-600">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div>
          <h2 className="text-xl font-bold text-slate-900">Employment Verification</h2>
          <p className="text-sm text-slate-500">
            Please confirm the employment details below for <strong>{formData.candidate_name}</strong>
          </p>
        </div>
      </div>

      {/* Pre-filled details */}
      <div className="bg-slate-50 rounded-lg p-4 mb-6">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Employment Details to Verify</h3>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-slate-500">Candidate:</span>
            <p className="font-medium">{formData.candidate_name}</p>
          </div>
          <div>
            <span className="text-slate-500">Employer:</span>
            <p className="font-medium">{formData.employer_name}</p>
          </div>
          <div>
            <span className="text-slate-500">Job Title:</span>
            <p className="font-medium">{formData.job_title}</p>
          </div>
          <div>
            <span className="text-slate-500">Period:</span>
            <p className="font-medium">{formData.start_date || "N/A"} — {formData.end_date || "Present"}</p>
          </div>
        </div>
      </div>

      <div className="space-y-6">
        {/* Job Title Confirmation */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Can you confirm the job title is correct? <span className="text-red-500">*</span>
          </label>
          <div className="flex gap-3">
            <button
              onClick={() => setJobTitleConfirmed(true)}
              className={`flex-1 py-2.5 px-4 rounded-lg border-2 font-medium text-sm transition-all ${
                jobTitleConfirmed === true
                  ? "border-green-500 bg-green-50 text-green-700"
                  : "border-slate-200 hover:border-slate-300 text-slate-600"
              }`}
            >
              Yes, correct
            </button>
            <button
              onClick={() => setJobTitleConfirmed(false)}
              className={`flex-1 py-2.5 px-4 rounded-lg border-2 font-medium text-sm transition-all ${
                jobTitleConfirmed === false
                  ? "border-red-500 bg-red-50 text-red-700"
                  : "border-slate-200 hover:border-slate-300 text-slate-600"
              }`}
            >
              No, incorrect
            </button>
          </div>
        </div>

        {/* Dates Confirmation */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Can you confirm the dates of employment are correct? <span className="text-red-500">*</span>
          </label>
          <div className="flex gap-3">
            <button
              onClick={() => setDatesConfirmed(true)}
              className={`flex-1 py-2.5 px-4 rounded-lg border-2 font-medium text-sm transition-all ${
                datesConfirmed === true
                  ? "border-green-500 bg-green-50 text-green-700"
                  : "border-slate-200 hover:border-slate-300 text-slate-600"
              }`}
            >
              Yes, correct
            </button>
            <button
              onClick={() => setDatesConfirmed(false)}
              className={`flex-1 py-2.5 px-4 rounded-lg border-2 font-medium text-sm transition-all ${
                datesConfirmed === false
                  ? "border-red-500 bg-red-50 text-red-700"
                  : "border-slate-200 hover:border-slate-300 text-slate-600"
              }`}
            >
              No, incorrect
            </button>
          </div>
        </div>

        {/* Reason for Leaving */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Reason for Leaving</label>
          <input
            type="text"
            value={reasonForLeaving}
            onChange={(e) => setReasonForLeaving(e.target.value)}
            placeholder="e.g. Career progression, end of contract, relocated"
            className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:border-blue-500 focus:ring-1 focus:ring-blue-200 outline-none text-sm"
          />
        </div>

        {/* Additional Comments */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Additional Comments</label>
          <textarea
            value={comments}
            onChange={(e) => setComments(e.target.value)}
            placeholder="Any additional information you'd like to share (optional)"
            rows={3}
            className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:border-blue-500 focus:ring-1 focus:ring-blue-200 outline-none text-sm resize-none"
          />
        </div>

        {/* Your Details */}
        <div className="border-t pt-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Your Details</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Your Name</label>
              <input
                type="text"
                value={responderName}
                onChange={(e) => setResponderName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-200 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Your Job Title</label>
              <input
                type="text"
                value={responderTitle}
                onChange={(e) => setResponderTitle(e.target.value)}
                placeholder="e.g. HR Manager"
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-200 outline-none"
              />
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        <button
          onClick={onSubmit}
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
        >
          {loading ? "Submitting..." : "Submit Verification"}
        </button>

        <p className="text-xs text-slate-400 text-center">
          By submitting, you confirm this information is accurate to the best of your knowledge.
          Your response will be retained for 6 years per regulatory requirements.
        </p>
      </div>
    </>
  );
}

// ── Reference Form ───────────────────────────────────────────────────────────

function StarRating({
  label,
  value,
  onChange,
  required,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  required?: boolean;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-2">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            onClick={() => onChange(star)}
            className="p-1 transition-transform hover:scale-110"
          >
            <svg
              className={`w-8 h-8 ${star <= value ? "text-yellow-400 fill-yellow-400" : "text-slate-300"}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
              />
            </svg>
          </button>
        ))}
        <span className="ml-2 text-sm text-slate-500 self-center">
          {value === 0 ? "Not rated" : ["", "Poor", "Below Average", "Average", "Good", "Excellent"][value]}
        </span>
      </div>
    </div>
  );
}

function ReferenceForm({
  formData,
  performance,
  setPerformance,
  conduct,
  setConduct,
  reliability,
  setReliability,
  wouldRehire,
  setWouldRehire,
  relationship,
  setRelationship,
  knownSince,
  setKnownSince,
  strengths,
  setStrengths,
  improvements,
  setImprovements,
  comments,
  setComments,
  responderName,
  setResponderName,
  responderTitle,
  setResponderTitle,
  error,
  loading,
  onSubmit,
  onBack,
}: {
  formData: NonNullable<LookupResponse["form_data"]>;
  performance: number;
  setPerformance: (v: number) => void;
  conduct: number;
  setConduct: (v: number) => void;
  reliability: number;
  setReliability: (v: number) => void;
  wouldRehire: boolean | null;
  setWouldRehire: (v: boolean) => void;
  relationship: string;
  setRelationship: (v: string) => void;
  knownSince: string;
  setKnownSince: (v: string) => void;
  strengths: string;
  setStrengths: (v: string) => void;
  improvements: string;
  setImprovements: (v: string) => void;
  comments: string;
  setComments: (v: string) => void;
  responderName: string;
  setResponderName: (v: string) => void;
  responderTitle: string;
  setResponderTitle: (v: string) => void;
  error: string;
  loading: boolean;
  onSubmit: () => void;
  onBack: () => void;
}) {
  return (
    <>
      <div className="flex items-center gap-3 mb-6">
        <button onClick={onBack} className="text-slate-400 hover:text-slate-600">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div>
          <h2 className="text-xl font-bold text-slate-900">Professional Reference</h2>
          <p className="text-sm text-slate-500">
            Please provide a reference for <strong>{formData.candidate_name}</strong>
          </p>
        </div>
      </div>

      <div className="space-y-6">
        {/* Ratings */}
        <StarRating label="Performance" value={performance} onChange={setPerformance} required />
        <StarRating label="Professional Conduct" value={conduct} onChange={setConduct} required />
        <StarRating label="Reliability & Attendance" value={reliability} onChange={setReliability} required />

        {/* Would Rehire */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Would you re-employ or recommend this candidate? <span className="text-red-500">*</span>
          </label>
          <div className="flex gap-3">
            <button
              onClick={() => setWouldRehire(true)}
              className={`flex-1 py-2.5 px-4 rounded-lg border-2 font-medium text-sm transition-all ${
                wouldRehire === true
                  ? "border-green-500 bg-green-50 text-green-700"
                  : "border-slate-200 hover:border-slate-300 text-slate-600"
              }`}
            >
              Yes
            </button>
            <button
              onClick={() => setWouldRehire(false)}
              className={`flex-1 py-2.5 px-4 rounded-lg border-2 font-medium text-sm transition-all ${
                wouldRehire === false
                  ? "border-red-500 bg-red-50 text-red-700"
                  : "border-slate-200 hover:border-slate-300 text-slate-600"
              }`}
            >
              No
            </button>
          </div>
        </div>

        {/* Relationship */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Your Relationship</label>
            <select
              value={relationship}
              onChange={(e) => setRelationship(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:border-blue-500 outline-none"
            >
              <option value="">Select...</option>
              <option value="line_manager">Line Manager</option>
              <option value="senior_colleague">Senior Colleague</option>
              <option value="hr_department">HR Department</option>
              <option value="peer">Peer / Colleague</option>
              <option value="mentor">Mentor / Supervisor</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Known Since</label>
            <input
              type="text"
              value={knownSince}
              onChange={(e) => setKnownSince(e.target.value)}
              placeholder="e.g. 2019"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-200 outline-none"
            />
          </div>
        </div>

        {/* Strengths */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Key Strengths</label>
          <textarea
            value={strengths}
            onChange={(e) => setStrengths(e.target.value)}
            placeholder="What are this person's main strengths?"
            rows={2}
            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-200 outline-none resize-none"
          />
        </div>

        {/* Areas for Improvement */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Areas for Improvement</label>
          <textarea
            value={improvements}
            onChange={(e) => setImprovements(e.target.value)}
            placeholder="Are there any areas where this person could develop further?"
            rows={2}
            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-200 outline-none resize-none"
          />
        </div>

        {/* Additional Comments */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Additional Comments</label>
          <textarea
            value={comments}
            onChange={(e) => setComments(e.target.value)}
            placeholder="Any other information you'd like to share (optional)"
            rows={2}
            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-200 outline-none resize-none"
          />
        </div>

        {/* Your Details */}
        <div className="border-t pt-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Your Details</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Your Name</label>
              <input
                type="text"
                value={responderName}
                onChange={(e) => setResponderName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-200 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Your Job Title</label>
              <input
                type="text"
                value={responderTitle}
                onChange={(e) => setResponderTitle(e.target.value)}
                placeholder="e.g. Ward Manager"
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-200 outline-none"
              />
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        <button
          onClick={onSubmit}
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
        >
          {loading ? "Submitting..." : "Submit Reference"}
        </button>

        <p className="text-xs text-slate-400 text-center">
          Your response will be treated in confidence and retained for 6 years per regulatory requirements.
        </p>
      </div>
    </>
  );
}
