import { api, encodeId } from "@/lib/http";

export type InvoiceLine = {
  item_code: string;
  qty: number;
  rate: number;
  amount: number;
};

export type SalesInvoice = {
  id: string;
  customer: string;
  posting_date: string | null;
  due_date: string | null;
  grand_total: number;
  outstanding_amount: number;
  status: string;
  remarks: string | null;
  items: InvoiceLine[];
};

export type SalesInvoiceInput = {
  customer: string;
  items: { item_code: string; qty: number; rate: number; description?: string | null }[];
  posting_date?: string | null;
  due_date?: string | null;
  remarks?: string | null;
  update_stock?: boolean;
  taxes_and_charges?: string | null;
};

export const listSales = (
  token: string,
  params: { search?: string; status?: string } = {}
) => api.get<SalesInvoice[]>(token, "/sales", { ...params, limit: 200 });

export const getSale = (token: string, id: string) =>
  api.get<SalesInvoice>(token, `/sales/${encodeId(id)}`);

export const createSale = (token: string, input: SalesInvoiceInput) =>
  api.post<SalesInvoice>(token, "/sales", input);
