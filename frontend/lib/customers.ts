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
  params: Paged & { search?: string; customer_type?: string } = {}
) => api.get<Customer[]>(token, "/customers", { limit: 200, ...params });

export const createCustomer = (token: string, input: CustomerInput) =>
  api.post<Customer>(token, "/customers", input);

export const updateCustomer = (token: string, id: string, input: CustomerInput) =>
  api.put<Customer>(token, `/customers/${encodeId(id)}`, input);

export const deleteCustomer = (token: string, id: string) =>
  api.del(token, `/customers/${encodeId(id)}`);
