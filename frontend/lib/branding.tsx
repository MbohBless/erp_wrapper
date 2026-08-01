"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/**
 * Runtime white-labelling.
 *
 * The design system in `app/globals.css` is entirely CSS custom properties, so
 * re-skinning the product is a matter of overriding a handful of them at
 * runtime. This provider fetches the tenant's branding from the *public*
 * endpoint — before sign-in, so the login screen is already branded — and
 * injects the overrides as a `<style>` block.
 *
 * Values arrive validated by `schemas/branding.py` (hex colours and safe font
 * names only). They are re-checked here before being written into CSS: the API
 * is the security boundary, but a second gate costs nothing and this string is
 * concatenated straight into a stylesheet.
 */

export type ThemeTokens = Record<string, string>;

export type Branding = {
  tenant: string;
  app_name: string;
  short_name: string;
  tagline: string;
  logo_light_data_url: string;
  logo_dark_data_url: string;
  favicon_data_url: string;
  light_tokens: ThemeTokens;
  dark_tokens: ThemeTokens;
  font_heading: string;
  font_body: string;
  default_theme: "light" | "dark" | "system";
};

export const DEFAULT_BRANDING: Branding = {
  tenant: "default",
  app_name: "EquiMed",
  short_name: "EquiMed",
  tagline: "Distribution Suite",
  logo_light_data_url: "",
  logo_dark_data_url: "",
  favicon_data_url: "",
  light_tokens: {},
  dark_tokens: {},
  font_heading: "",
  font_body: "",
  default_theme: "system",
};

// Mirrors THEME_TOKENS in backend/schemas/branding.py. Keep the two in step.
const ALLOWED_TOKENS = new Set([
  "--color-bg",
  "--color-surface",
  "--color-text",
  "--color-accent",
  "--color-accent-600",
  "--color-accent-700",
  "--ok",
  "--warn",
  "--err",
  "--ok-raw",
  "--warn-raw",
  "--err-raw",
]);

const HEX = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;
const FONT = /^[A-Za-z0-9][A-Za-z0-9 -]{0,48}$/;

function declarations(tokens: ThemeTokens): string {
  return Object.entries(tokens ?? {})
    .filter(([name, value]) => ALLOWED_TOKENS.has(name) && HEX.test(String(value)))
    .map(([name, value]) => `${name}:${value};`)
    .join("");
}

/** Build the override stylesheet. Returns "" when nothing is customised. */
export function brandingCss(branding: Branding): string {
  const blocks: string[] = [];

  const light = declarations(branding.light_tokens);
  const dark = declarations(branding.dark_tokens);
  const fonts: string[] = [];
  if (FONT.test(branding.font_heading)) {
    fonts.push(`--font-heading:"${branding.font_heading}",system-ui,sans-serif;`);
  }
  if (FONT.test(branding.font_body)) {
    fonts.push(`--font-body:"${branding.font_body}",system-ui,sans-serif;`);
  }

  if (light || fonts.length) blocks.push(`:root{${light}${fonts.join("")}}`);
  // Scoped to the dark attribute so it wins over the base dark block, which
  // globals.css declares at the same specificity.
  if (dark) blocks.push(`:root[data-theme="dark"]{${dark}}`);
  return blocks.join("");
}

type BrandingState = {
  branding: Branding;
  ready: boolean;
  /** Re-fetch after the tenant edits their branding in Settings. */
  refresh: () => void;
};

const BrandingContext = createContext<BrandingState | null>(null);

export function BrandingProvider({ children }: { children: ReactNode }) {
  const [branding, setBranding] = useState<Branding>(DEFAULT_BRANDING);
  const [ready, setReady] = useState(false);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/public/branding")
      .then((r) => (r.ok ? r.json() : null))
      .then((data: Branding | null) => {
        if (cancelled || !data) return;
        setBranding({ ...DEFAULT_BRANDING, ...data });
      })
      // A branding failure must never block the app — fall back to defaults.
      .catch(() => undefined)
      .finally(() => !cancelled && setReady(true));
    return () => {
      cancelled = true;
    };
  }, [nonce]);

  const css = useMemo(() => brandingCss(branding), [branding]);

  useEffect(() => {
    document.title = `${branding.app_name} — ${branding.tagline}`;
  }, [branding.app_name, branding.tagline]);

  useEffect(() => {
    if (!branding.favicon_data_url.startsWith("data:image/")) return;
    let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
    if (!link) {
      link = document.createElement("link");
      link.rel = "icon";
      document.head.appendChild(link);
    }
    link.href = branding.favicon_data_url;
  }, [branding.favicon_data_url]);

  const value = useMemo<BrandingState>(
    () => ({ branding, ready, refresh: () => setNonce((n) => n + 1) }),
    [branding, ready]
  );

  return (
    <BrandingContext.Provider value={value}>
      {css ? <style id="eq-branding" dangerouslySetInnerHTML={{ __html: css }} /> : null}
      {children}
    </BrandingContext.Provider>
  );
}

export function useBranding(): BrandingState {
  const ctx = useContext(BrandingContext);
  if (!ctx) throw new Error("useBranding must be used within BrandingProvider");
  return ctx;
}

/** Convenience: the tenant's product name, for headings and breadcrumbs. */
export function useAppName(): string {
  return useBranding().branding.app_name;
}
