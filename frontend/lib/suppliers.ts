import { type Paged, api, encodeId } from "@/lib/http";

export type SupplierType = "Company" | "Individual";

export type Supplier = {
  id: string;
  name: string;
  supplier_group: string;
  supplier_type: SupplierType;
  contact_person: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  lead_time_days: number | null;
  tax_id: string | null;
  disabled: boolean;
};

export type SupplierInput = {
  name: string;
  supplier_group?: string;
  supplier_type?: SupplierType;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  lead_time_days?: number | null;
  tax_id?: string | null;
  disabled?: boolean;
};

export const listSuppliers = (
  token: string,
  params: Paged & { search?: string; supplier_type?: string; disabled?: boolean } = {}
) => api.get<Supplier[]>(token, "/suppliers", { limit: 200, ...params });

export const createSupplier = (token: string, input: SupplierInput) =>
  api.post<Supplier>(token, "/suppliers", input);

export const updateSupplier = (token: string, id: string, input: SupplierInput) =>
  api.put<Supplier>(token, `/suppliers/${encodeId(id)}`, input);

export const deleteSupplier = (token: string, id: string) =>
  api.del(token, `/suppliers/${encodeId(id)}`);

/**
 * One record, by id.
 *
 * The edit pages used to fetch a page of the list and search it, which works
 * only while everything fits on one page — past that the record is absent and
 * the form waits forever for something that will never arrive.
 */
export const getSupplier = (token: string, id: string) =>
  api.get<Supplier>(token, `/suppliers/${encodeId(id)}`);
