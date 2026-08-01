"use client";

import { useState } from "react";

import Blueprint from "@/components/Blueprint";
import { Icon } from "@/components/icons";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";
import { useTheme } from "@/lib/theme";

export default function SignIn() {
  const { login } = useAuth();
  const { branding } = useBranding();
  const { theme } = useTheme();
  const logo =
    theme === "dark"
      ? branding.logo_dark_data_url || branding.logo_light_data_url
      : branding.logo_light_data_url || branding.logo_dark_data_url;
  // No pre-filled address: on a shared SaaS plane a seeded demo email is both
  // wrong for the tenant and a hint about the platform's default credentials.
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center p-6 bg-bg text-ink">
      <Blueprint className="w-full max-w-[380px] p-8">
        <form onSubmit={onSubmit}>
          {logo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={logo}
              alt={branding.app_name}
              className="w-9 h-9 rounded-lg object-contain mb-3.5"
            />
          ) : (
            <div className="w-9 h-9 rounded-lg grid place-items-center bg-accent text-bg mb-3.5">
              <Icon name="flask" size={20} sw={2} />
            </div>
          )}
          <h1 className="font-heading font-bold text-[26px] mb-1">
            Sign in to {branding.app_name}
          </h1>
          <p className="muted text-sm mb-6">{branding.tagline}</p>

          {error && (
            <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-lg text-[13px] mb-3.5">
              {error}
            </div>
          )}

          <label className="block text-[13px] muted mb-2" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="eq-field w-full px-3 py-2.5 text-sm mb-3.5"
            required
          />

          <label className="block text-[13px] muted mb-2" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="eq-field w-full px-3 py-2.5 text-sm mb-5"
            required
          />

          <button
            type="submit"
            disabled={busy}
            className="btn btn-filled w-full"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </Blueprint>
    </div>
  );
}
