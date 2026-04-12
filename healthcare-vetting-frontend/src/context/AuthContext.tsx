import { createContext, useContext, useState, useEffect, ReactNode } from "react";

interface AuthState {
  token: string | null;
  userType: string | null;
  userId: string | null;
}

interface AuthContextType extends AuthState {
  login: (token: string, userType: string, userId: string) => void;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>(() => {
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

  const login = (token: string, userType: string, userId: string) => {
    setAuth({ token, userType, userId });
  };

  const logout = () => {
    setAuth({ token: null, userType: null, userId: null });
  };

  return (
    <AuthContext.Provider value={{ ...auth, login, logout, isAuthenticated: !!auth.token }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
