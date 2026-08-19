"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  endSession,
  getAccessToken,
  getUser,
  setSession,
  subscribe,
} from "@/lib/session";

type AuthState = {
  token: string | null;
  user: string | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setToken(getAccessToken());
    setUser(getUser());
    setReady(true);
    // The session can change outside React — a background refresh after a 401,
    // or the refresh token being rejected. Without this the context would keep
    // handing out the dead token, and a rejected session would leave the app
    // sitting on a page it can no longer load.
    return subscribe((next) => {
      setToken(next);
      if (!next) setUser(null);
    });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail?.detail || "Incorrect email or password");
    }
    const data = await res.json();
    setSession(data.access_token, data.refresh_token ?? null, email);
    setToken(data.access_token);
    setUser(email);
  }, []);

  const logout = useCallback(() => {
    // Clear locally first so the UI responds immediately, then tell the server
    // to revoke the refresh token — otherwise signing out leaves a credential
    // valid for weeks.
    setToken(null);
    setUser(null);
    void endSession();
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, ready, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
