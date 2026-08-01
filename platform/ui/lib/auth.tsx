"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type PlatformRole = "Owner" | "Operator" | "Support" | "Billing";

export type Operator = {
  id: number;
  email: string;
  full_name: string;
  role: PlatformRole;
  is_active: boolean;
};

type AuthState = {
  token: string | null;
  operator: Operator | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  /** Capability check mirroring the API's RBAC, for hiding dead controls. */
  can: (action: "read" | "operate" | "bill" | "own") => boolean;
};

const AuthContext = createContext<AuthState | null>(null);
// Distinct from the tenant app's key: both may be open in one browser.
const TOKEN_KEY = "equimed_platform_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [operator, setOperator] = useState<Operator | null>(null);
  const [ready, setReady] = useState(false);

  const loadMe = useCallback(async (t: string) => {
    const res = await fetch("/papi/auth/me", {
      headers: { Authorization: `Bearer ${t}` },
    });
    if (!res.ok) throw new Error("session expired");
    setOperator((await res.json()) as Operator);
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      setReady(true);
      return;
    }
    setToken(stored);
    loadMe(stored)
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
      })
      .finally(() => setReady(true));
  }, [loadMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      const body = new URLSearchParams({ username: email, password });
      const res = await fetch("/papi/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail?.detail || "Incorrect email or password");
      }
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      await loadMe(data.access_token);
    },
    [loadMe]
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setOperator(null);
  }, []);

  const can = useCallback(
    (action: "read" | "operate" | "bill" | "own") => {
      const role = operator?.role;
      if (!role) return false;
      switch (action) {
        case "read":
          return true;
        case "operate":
          return role === "Owner" || role === "Operator";
        case "bill":
          return role === "Owner" || role === "Billing";
        case "own":
          return role === "Owner";
      }
    },
    [operator]
  );

  return (
    <AuthContext.Provider value={{ token, operator, ready, login, logout, can }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
