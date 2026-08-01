// HTTP layer for the operator console.
//
// Talks to the control plane at /papi, never to a tenant backend. Keeping the
// prefix distinct from the tenant app's /api means a misconfigured proxy fails
// loudly instead of silently pointing operator tooling at customer data.

export class UnauthorizedError extends Error {}

const BASE = "/papi";

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
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    const detail = body?.detail;
    if (typeof detail === "string") throw new Error(detail);
    // FastAPI validation errors arrive as a list of {loc, msg}.
    if (Array.isArray(detail) && detail.length) {
      throw new Error(
        detail
          .map((d) => {
            const field = Array.isArray(d?.loc) ? d.loc[d.loc.length - 1] : "";
            return field ? `${field}: ${d.msg}` : d.msg;
          })
          .join("; ")
      );
    }
    throw new Error(`Request failed (${res.status})`);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

const authHeader = (token: string) => ({ Authorization: `Bearer ${token}` });
const jsonHeaders = (token: string) => ({
  ...authHeader(token),
  "Content-Type": "application/json",
});

export const api = {
  get<T>(token: string, path: string, params?: QueryParams): Promise<T> {
    return fetch(`${BASE}${path}${buildQuery(params)}`, {
      headers: authHeader(token),
    }).then((r) => parse<T>(r));
  },
  post<T>(token: string, path: string, body: unknown, params?: QueryParams): Promise<T> {
    return fetch(`${BASE}${path}${buildQuery(params)}`, {
      method: "POST",
      headers: jsonHeaders(token),
      body: JSON.stringify(body ?? {}),
    }).then((r) => parse<T>(r));
  },
  patch<T>(token: string, path: string, body: unknown): Promise<T> {
    return fetch(`${BASE}${path}`, {
      method: "PATCH",
      headers: jsonHeaders(token),
      body: JSON.stringify(body),
    }).then((r) => parse<T>(r));
  },
  del<T>(token: string, path: string, params?: QueryParams): Promise<T> {
    return fetch(`${BASE}${path}${buildQuery(params)}`, {
      method: "DELETE",
      headers: authHeader(token),
    }).then((r) => parse<T>(r));
  },
};
