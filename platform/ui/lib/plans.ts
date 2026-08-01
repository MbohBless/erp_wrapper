import { api } from "@/lib/http";

export type Plan = {
  code: string;
  name: string;
  description: string;
  features: string[];
  max_users: number;
  price_xaf: number;
  is_active: boolean;
  created_at: string;
  tenant_count: number;
};

export type AuditEntry = {
  id: number;
  actor_email: string;
  action: string;
  tenant_id: string;
  detail: string;
  created_at: string;
};

export const listPlans = (token: string) => api.get<Plan[]>(token, "/plans");

export const listFeatures = (token: string) =>
  api.get<{ features: string[] }>(token, "/plans/features");

export const createPlan = (
  token: string,
  input: Omit<Plan, "created_at" | "tenant_count">
) => api.post<Plan>(token, "/plans", input);

export const updatePlan = (
  token: string,
  code: string,
  input: Partial<Omit<Plan, "code" | "created_at" | "tenant_count">>
) => api.patch<Plan>(token, `/plans/${encodeURIComponent(code)}`, input);

export const listAudit = (
  token: string,
  params?: { tenant_id?: string; action?: string; limit?: number }
) => api.get<AuditEntry[]>(token, "/audit", params);

export const xaf = (n: number) =>
  new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n) + " XAF";

export const when = (iso: string | null) =>
  iso
    ? new Date(iso).toLocaleString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
