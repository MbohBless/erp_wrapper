"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { useBranding } from "@/lib/branding";

type Theme = "light" | "dark";
type ThemeState = { theme: Theme; toggle: () => void };

const ThemeContext = createContext<ThemeState | null>(null);
const KEY = "equimed_theme";

function systemTheme(): Theme {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { branding, ready } = useBranding();
  const [theme, setTheme] = useState<Theme>("light");
  // A stored value means the person chose for themselves; the tenant's default
  // must never override that, only fill in when they have not chosen.
  const [userChose, setUserChose] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(KEY) as Theme | null;
    if (stored === "light" || stored === "dark") {
      setUserChose(true);
      setTheme(stored);
    } else {
      setTheme(systemTheme());
    }
  }, []);

  useEffect(() => {
    if (!ready || userChose) return;
    const preferred = branding.default_theme;
    setTheme(preferred === "system" ? systemTheme() : preferred);
  }, [ready, userChose, branding.default_theme]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const toggle = useCallback(() => {
    setUserChose(true);
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      localStorage.setItem(KEY, next);
      return next;
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
