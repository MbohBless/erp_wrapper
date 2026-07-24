// Shared HTTP layer for all API calls: auth headers, query building, error
// handling and JSON parsing in one place.

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

export const api = {
  get<T>(token: string, path: string, params?: QueryParams): Promise<T> {
    return fetch(`/api${path}${buildQuery(params)}`, {
      headers: authHeader(token),
    }).then((r) => parse<T>(r));
  },
  post<T>(token: string, path: string, body: unknown): Promise<T> {
    return fetch(`/api${path}`, {
      method: "POST",
      headers: jsonHeaders(token),
      body: JSON.stringify(body),
    }).then((r) => parse<T>(r));
  },
  put<T>(token: string, path: string, body: unknown): Promise<T> {
    return fetch(`/api${path}`, {
      method: "PUT",
      headers: jsonHeaders(token),
      body: JSON.stringify(body),
    }).then((r) => parse<T>(r));
  },
  del(token: string, path: string): Promise<void> {
    return fetch(`/api${path}`, {
      method: "DELETE",
      headers: authHeader(token),
    }).then((r) => parse<void>(r));
  },
};

export const encodeId = (id: string | number) => encodeURIComponent(String(id));
