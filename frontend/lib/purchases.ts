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
  amended_from: string | null;
  is_cancelled: boolean;
  is_opening: boolean;
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

/**
 * Correct a posted supplier bill — cancel-then-amend, so the bill number
 * changes. See `updateSale` in lib/sales.ts; the semantics are identical.
 */
export const updatePurchase = (token: string, id: string, input: PurchaseInput) =>
  api.put<PurchaseInvoice>(token, `/purchases/${encodeId(id)}`, input);

/** Why this bill cannot be corrected, or null if it can. Mirrors
 * `PurchaseService._ensure_amendable`; the API refuses independently. */
export function amendBlockedReason(
  bill: PurchaseInvoice
): "opening" | "settled" | null {
  if (bill.is_opening) return "opening";
  if (bill.is_cancelled) return null;
  if (bill.grand_total - bill.outstanding_amount > 0.005) return "settled";
  return null;
}
