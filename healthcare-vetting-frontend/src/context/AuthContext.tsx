import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";

interface AuthState {
  token: string | null;
  userType: string | null;
  userId: string | null;
}

interface AuthContextType extends AuthState {
  login: (token: string, userType: string, userId: string) => void;
  logout: () => void;
  isAuthenticated: boolean;
  refreshAccessToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>(() => {
    // Try memory first, then localStorage for backward compat
    const stored = localStorage.getItem("viperai_auth");
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch {
        return { token: null, userType: null, userId: null };
      }
    }
    return { token: null, userType: null, userId: null };
  });

  useEffect(() => {
    if (auth.token) {
      localStorage.setItem("viperai_auth", JSON.stringify(auth));
    } else {
      localStorage.removeItem("viperai_auth");
    }
  }, [auth]);

  // Listen for session-expired events from the API client (401 + refresh failed)
  useEffect(() => {
    const handleSessionExpired = () => {
      setAuth({ token: null, userType: null, userId: null });
    };
    const handleTokenRefreshed = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.access_token) {
        setAuth(prev => ({ ...prev, token: detail.access_token }));
      }
    };
    window.addEventListener("viperai:session-expired", handleSessionExpired);
    window.addEventListener("viperai:token-refreshed", handleTokenRefreshed);
    return () => {
      window.removeEventListener("viperai:session-expired", handleSessionExpired);
      window.removeEventListener("viperai:token-refreshed", handleTokenRefreshed);
    };
  }, []);

  const login = (token: string, userType: string, userId: string) => {
    setAuth({ token, userType, userId });
  };

  const logout = () => {
    setAuth({ token: null, userType: null, userId: null });
  };

  const refreshAccessToken = useCallback(async (): Promise<string | null> => {
    try {
      const csrfToken = getCookie("viperai_csrf");
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (csrfToken) headers["X-CSRF-Token"] = csrfToken;

      const res = await fetch("/api/auth/token/refresh-cookie", {
        method: "POST",
        credentials: "include",
        headers,
      });
      if (!res.ok) return null;
      const data = await res.json();
      if (data.access_token) {
        setAuth({ token: data.access_token, userType: data.user_type, userId: data.user_id });
        return data.access_token;
      }
      return null;
    } catch {
      return null;
    }
  }, []);

  return (
    <AuthContext.Provider value={{ ...auth, login, logout, isAuthenticated: !!auth.token, refreshAccessToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
