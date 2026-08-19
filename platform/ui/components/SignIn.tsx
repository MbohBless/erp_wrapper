"use client";

import { useState } from "react";

import { useAuth } from "@/lib/auth";

export default function SignIn() {
  const { login } = useAuth();
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
    <div className="min-h-screen grid place-items-center p-6">
      <form onSubmit={onSubmit} className="panel w-full max-w-[380px] p-8">
        <span className="w-9 h-9 rounded-lg bg-accent text-[#0e1116] grid place-items-center font-bold text-sm mb-4">
          EQ
        </span>
        <h1 className="font-heading font-bold text-[24px] mb-1">
          EquiMed Control Plane
        </h1>
        <p className="muted text-sm mb-6">Platform operators only.</p>

        {error && (
          <div className="text-err bg-[color-mix(in_srgb,var(--err)_12%,transparent)] px-3 py-2.5 rounded-lg text-[13px] mb-4">
            {error}
          </div>
        )}

        <label className="block text-[13px] muted mb-2" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          required
          autoComplete="username"
          className="field mb-4"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <label className="block text-[13px] muted mb-2" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          type="password"
          required
          autoComplete="current-password"
          className="field mb-6"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <button type="submit" className="btn btn-filled w-full justify-center" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
