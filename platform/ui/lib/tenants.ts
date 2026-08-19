import { api } from "@/lib/http";

export type TenantStatus =
  | "pending"
  | "provisioning"
  | "active"
  | "suspended"
  | "archived";

export type TenantDomain = {
  host: string;
  is_primary: boolean;
  verified_at: string | null;
};

export type TenantSummary = {
  id: string;
  name: string;
  status: TenantStatus;
  plan_code: string;
  primary_host: string;
  contact_email: string;
  created_at: string;
};

export type Tenant = TenantSummary & {
  contact_name: string;
  country: string;
  notes: string;
  erpnext_url: string;
  erpnext_site: string;
  erpnext_api_key: string;
  has_erpnext_secret: boolean;
  suspended_reason: string;
  suspended_at: string | null;
  provisioned_at: string | null;
  updated_at: string;
  domains: TenantDomain[];
};

export type TenantStats = {
  total: number;
  active: number;
  suspended: number;
  by_status: Record<string, number>;
};

export type ProvisionResult = {
  tenant: Tenant;
  provisioned: boolean;
  bootstrapped: boolean;
  messages: string[];
};

export type TenantCreateInput = {
  id: string;
  name: string;
  plan_code: string;
  contact_name?: string;
  contact_email?: string | null;
  country?: string;
  notes?: string;
  erpnext_url?: string;
  erpnext_site?: string;
  erpnext_api_key?: string;
  erpnext_api_secret?: string;
  admin_email: string;
  admin_password: string;
  admin_name?: string;
};

export const listTenants = (
  token: string,
  params?: { status?: string; plan_code?: string; search?: string }
) => api.get<TenantSummary[]>(token, "/tenants", params);

export const getTenantStats = (token: string) =>
  api.get<TenantStats>(token, "/tenants/stats");

export const getTenant = (token: string, id: string) =>
  api.get<Tenant>(token, `/tenants/${encodeURIComponent(id)}`);

export const createTenant = (token: string, input: TenantCreateInput) =>
  api.post<Tenant>(token, "/tenants", input);

export const updateTenant = (
  token: string,
  id: string,
  input: Partial<TenantCreateInput>
) => api.patch<Tenant>(token, `/tenants/${encodeURIComponent(id)}`, input);

export const provisionTenant = (
  token: string,
  id: string,
  input: TenantCreateInput
) =>
  api.post<ProvisionResult>(
    token,
    `/tenants/${encodeURIComponent(id)}/provision`,
    input
  );

export const suspendTenant = (token: string, id: string, reason: string) =>
  api.post<Tenant>(token, `/tenants/${encodeURIComponent(id)}/suspend`, { reason });

export const resumeTenant = (token: string, id: string) =>
  api.post<Tenant>(token, `/tenants/${encodeURIComponent(id)}/resume`, {});

export const archiveTenant = (token: string, id: string) =>
  api.post<Tenant>(token, `/tenants/${encodeURIComponent(id)}/archive`, {});

export const purgeTenant = (token: string, id: string, confirm: string) =>
  api.del<{ tenant_id: string; messages: string[] }>(
    token,
    `/tenants/${encodeURIComponent(id)}`,
    { confirm }
  );

export const addDomain = (
  token: string,
  id: string,
  host: string,
  is_primary = false
) =>
  api.post<Tenant>(token, `/tenants/${encodeURIComponent(id)}/domains`, {
    host,
    is_primary,
  });

export const verifyDomain = (token: string, id: string, host: string) =>
  api.post<Tenant>(
    token,
    `/tenants/${encodeURIComponent(id)}/domains/${encodeURIComponent(host)}/verify`,
    {}
  );

export const removeDomain = (token: string, id: string, host: string) =>
  api.del<Tenant>(
    token,
    `/tenants/${encodeURIComponent(id)}/domains/${encodeURIComponent(host)}`
  );
