"use client";

import { useState } from "react";

import Blueprint from "@/components/Blueprint";
import { Icon } from "@/components/icons";
import { useAuth } from "@/lib/auth";

export default function SignIn() {
  const { login } = useAuth();
  const [email, setEmail] = useState("admin@equimed.cm");
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
          <div className="w-9 h-9 rounded-lg grid place-items-center bg-accent text-bg mb-3.5">
            <Icon name="flask" size={20} sw={2} />
          </div>
          <h1 className="font-heading font-bold text-[26px] mb-1">Sign in to EquiMed</h1>
          <p className="muted text-sm mb-6">Medical equipment distribution suite</p>

          {error && (
            <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-lg text-[13px] mb-3.5">
              {error}
            </div>
          )}

          <label className="block text-xs muted mb-1.5" htmlFor="email">
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

          <label className="block text-xs muted mb-1.5" htmlFor="password">
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
            className="w-full h-10 rounded-lg bg-accent text-bg font-heading font-semibold text-sm hover:bg-accent-600 disabled:opacity-50"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </Blueprint>
    </div>
  );
}
