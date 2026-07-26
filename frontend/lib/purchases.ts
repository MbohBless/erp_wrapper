import { api, encodeId } from "@/lib/http";

export type BillLine = {
  item_code: string;
  qty: number;
  rate: number;
  amount: number;
};

export type PurchaseInvoice = {
  id: string;
  supplier: string;
  posting_date: string | null;
  due_date: string | null;
  bill_no: string | null;
  grand_total: number;
  outstanding_amount: number;
  status: string;
  remarks: string | null;
  items: BillLine[];
};

export type PurchaseInput = {
  supplier: string;
  items: { item_code: string; qty: number; rate: number }[];
  bill_no?: string | null;
  posting_date?: string | null;
  remarks?: string | null;
};

export const listPurchases = (
  token: string,
  params: { search?: string; status?: string } = {}
) => api.get<PurchaseInvoice[]>(token, "/purchases", { ...params, limit: 200 });

export const getPurchase = (token: string, id: string) =>
  api.get<PurchaseInvoice>(token, `/purchases/${encodeId(id)}`);

export const createPurchase = (token: string, input: PurchaseInput) =>
  api.post<PurchaseInvoice>(token, "/purchases", input);
