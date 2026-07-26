"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { DICT } from "@/lib/locales";

export type Lang = "fr" | "en";

const KEY = "equimed_lang";

export const LANGS: Lang[] = ["fr", "en"];

type I18nState = { lang: Lang; setLang: (l: Lang) => void; t: (key: string) => string };

const I18nContext = createContext<I18nState | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("fr");

  useEffect(() => {
    const stored = localStorage.getItem(KEY) as Lang | null;
    if (stored === "fr" || stored === "en") setLangState(stored);
    else if (navigator.language?.toLowerCase().startsWith("en")) setLangState("en");
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("lang", lang);
    localStorage.setItem(KEY, lang);
  }, [lang]);

  const setLang = useCallback((l: Lang) => setLangState(l), []);
  const t = useCallback(
    (key: string) => DICT[lang][key] ?? DICT.en[key] ?? key,
    [lang]
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nState {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
