"use client";

/**
 * The session: access token, refresh token, and renewal.
 *
 * The access token lasts an hour. Before this existed there was nothing to
 * renew it with, so anyone working for longer than that was signed out
 * mid-task — usually mid-form.
 *
 * Kept outside React on purpose. The HTTP layer needs the current token while
 * handling a 401, which happens outside any component's render, and a value
 * read from a hook would be the stale one that just failed.
 */

const ACCESS_KEY = "equimed_token";
const REFRESH_KEY = "equimed_refresh";
const USER_KEY = "equimed_user";

type Listener = (accessToken: string | null) => void;
const listeners = new Set<Listener>();

export function subscribe(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function announce(token: string | null) {
  for (const fn of listeners) fn(token);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function getUser(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USER_KEY);
}

export function setSession(
  accessToken: string,
  refreshToken: string | null,
  email?: string
) {
  localStorage.setItem(ACCESS_KEY, accessToken);
  if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken);
  if (email) localStorage.setItem(USER_KEY, email);
  announce(accessToken);
}

export function clearSession() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
  announce(null);
}

// One renewal at a time. When a token expires, every in-flight request fails at
// once; without this each would start its own refresh, and since refresh tokens
// are single-use the first to land would invalidate the rest — the server would
// read that as token reuse and revoke the whole session. The bug would look
// like "opening a busy page logs me out".
let inFlight: Promise<string | null> | null = null;

export function refreshAccessToken(): Promise<string | null> {
  if (inFlight) return inFlight;

  inFlight = (async () => {
    const refresh = getRefreshToken();
    if (!refresh) return null;
    try {
      const res = await fetch("/api/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) {
        // The refresh token is spent, revoked or expired: this session is over.
        clearSession();
        return null;
      }
      const data = await res.json();
      setSession(data.access_token, data.refresh_token ?? null);
      return data.access_token as string;
    } catch {
      // A network blip is not an expired session — keep the tokens so the next
      // attempt can succeed, and just report failure for this one.
      return null;
    } finally {
      inFlight = null;
    }
  })();

  return inFlight;
}

export async function endSession(): Promise<void> {
  const access = getAccessToken();
  const refresh = getRefreshToken();
  // Tell the server, so the refresh token is revoked rather than left valid for
  // weeks after the user believes they signed out. Best effort: the local
  // session is cleared regardless.
  if (access) {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${access}`,
        },
        body: JSON.stringify({ refresh_token: refresh }),
      });
    } catch {
      /* offline sign-out still clears the client */
    }
  }
  clearSession();
}
