import { type Paged, api, encodeId } from "@/lib/http";

export type CustomerType = "Company" | "Individual";

export type Customer = {
  id: string;
  name: string;
  customer_group: string;
  customer_type: CustomerType;
  territory: string;
  contact_person: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  tax_id: string | null;
  outstanding_balance: number | null;
  disabled: boolean;
};

export type CustomerInput = {
  name: string;
  customer_group?: string;
  customer_type?: CustomerType;
  territory?: string;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  tax_id?: string | null;
  disabled?: boolean;
};

export const listCustomers = (
  token: string,
  params: Paged & { search?: string; customer_type?: string; disabled?: boolean } = {}
) => api.get<Customer[]>(token, "/customers", { limit: 200, ...params });

export const createCustomer = (token: string, input: CustomerInput) =>
  api.post<Customer>(token, "/customers", input);

export const updateCustomer = (token: string, id: string, input: CustomerInput) =>
  api.put<Customer>(token, `/customers/${encodeId(id)}`, input);

export const deleteCustomer = (token: string, id: string) =>
  api.del(token, `/customers/${encodeId(id)}`);

/**
 * One record, by id.
 *
 * The edit pages used to fetch a page of the list and search it, which works
 * only while everything fits on one page — past that the record is absent and
 * the form waits forever for something that will never arrive.
 */
export const getCustomer = (token: string, id: string) =>
  api.get<Customer>(token, `/customers/${encodeId(id)}`);
