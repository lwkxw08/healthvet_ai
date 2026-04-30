/**
 * Shows a fixed banner when an admin is viewing the platform as another user.
 * Provides a button to exit impersonation and return to the admin panel.
 */
import { useEffect, useState } from "react";
import { adminExtendedApi } from "../api/client";

interface ImpersonationState {
  originalToken: string;
  impersonator: string;
}

export default function ImpersonationBanner() {
  const [impersonation, setImpersonation] = useState<ImpersonationState | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("viperai_impersonation");
    if (stored) {
      try {
        setImpersonation(JSON.parse(stored));
      } catch {
        // ignore
      }
    }
  }, []);

  if (!impersonation) return null;

  const exitImpersonation = async () => {
    try {
      const auth = localStorage.getItem("viperai_auth");
      if (auth) {
        const { token } = JSON.parse(auth);
        await adminExtendedApi.endImpersonation(token).catch(() => {});
      }
    } finally {
      // Restore admin session
      localStorage.setItem(
        "viperai_auth",
        JSON.stringify({ token: impersonation.originalToken, userType: "admin", userId: impersonation.impersonator }),
      );
      localStorage.removeItem("viperai_impersonation");
      window.location.href = "/";
    }
  };

  return (
    <div className="fixed top-0 left-0 right-0 z-[9999] bg-amber-600 text-white text-center py-2 px-4 text-sm font-medium flex items-center justify-center gap-4 shadow-lg">
      <span>You are viewing as another user (admin impersonation mode)</span>
      <button
        onClick={exitImpersonation}
        className="bg-white text-amber-700 px-3 py-1 rounded text-xs font-semibold hover:bg-amber-50"
      >
        Exit Impersonation
      </button>
    </div>
  );
}
