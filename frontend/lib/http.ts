// Shared HTTP layer for all API calls: auth headers, query building, error
// handling and JSON parsing in one place.

import { getAccessToken, refreshAccessToken } from "@/lib/session";

export class UnauthorizedError extends Error {}

type QueryParams = Record<string, string | number | boolean | undefined | null>;

function buildQuery(params?: QueryParams): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      sp.set(key, String(value));
    }
  }
  const query = sp.toString();
  return query ? `?${query}` : "";
}

async function parse<T>(res: Response): Promise<T> {
  if (res.status === 401) throw new UnauthorizedError("Session expired");
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body?.detail || "Request failed");
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

const authHeader = (token: string) => ({ Authorization: `Bearer ${token}` });
const jsonHeaders = (token: string) => ({
  ...authHeader(token),
  "Content-Type": "application/json",
});

/**
 * Send the request; on a 401, renew the session once and send it again.
 *
 * Callers pass the token they were rendered with, which is exactly the one that
 * just expired — so the retry deliberately uses the freshly minted token rather
 * than the argument. The refresh itself is single-flighted in lib/session, so a
 * page issuing ten parallel requests renews once, not ten times.
 *
 * Only one retry. If the second attempt is also refused the session is
 * genuinely over, and looping would just delay saying so.
 */
async function send<T>(
  attempt: (token: string) => Promise<Response>,
  token: string
): Promise<T> {
  let res = await attempt(token);
  if (res.status === 401) {
    const fresh = await refreshAccessToken();
    if (fresh) res = await attempt(fresh);
  }
  return parse<T>(res);
}

export const api = {
  get<T>(token: string, path: string, params?: QueryParams): Promise<T> {
    return send<T>(
      (t) => fetch(`/api${path}${buildQuery(params)}`, { headers: authHeader(t) }),
      token || getAccessToken() || ""
    );
  },
  post<T>(token: string, path: string, body: unknown): Promise<T> {
    return send<T>(
      (t) =>
        fetch(`/api${path}`, {
          method: "POST",
          headers: jsonHeaders(t),
          body: JSON.stringify(body),
        }),
      token || getAccessToken() || ""
    );
  },
  put<T>(token: string, path: string, body: unknown): Promise<T> {
    return send<T>(
      (t) =>
        fetch(`/api${path}`, {
          method: "PUT",
          headers: jsonHeaders(t),
          body: JSON.stringify(body),
        }),
      token || getAccessToken() || ""
    );
  },
  del(token: string, path: string): Promise<void> {
    return send<void>(
      (t) => fetch(`/api${path}`, { method: "DELETE", headers: authHeader(t) }),
      token || getAccessToken() || ""
    );
  },
};

export const encodeId = (id: string | number) => encodeURIComponent(String(id));
