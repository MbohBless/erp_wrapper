import { api, encodeId } from "@/lib/http";

export type InvoiceLine = {
  item_code: string;
  /** The item's name as billed. Null on list rows — an ERPNext list query
   *  returns no child table at all — so always fall back to the code. */
  item_name: string | null;
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
  update_stock: boolean;
  taxes_and_charges: string | null;
  amended_from: string | null;
  is_cancelled: boolean;
  is_opening: boolean;
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

/**
 * Correct a posted invoice.
 *
 * ERPNext cannot edit a submitted document, so the API cancels this one and
 * posts the correction in its place. The invoice **number changes** — the
 * response carries the new id, and the id passed in now names a cancelled
 * document. Callers must read the id back rather than reuse the one they sent.
 *
 * The whole document is replaced, so `input` has to carry every field the
 * invoice should keep, not just the changed ones.
 */
export const updateSale = (token: string, id: string, input: SalesInvoiceInput) =>
  api.put<SalesInvoice>(token, `/sales/${encodeId(id)}`, input);

/**
 * Why this invoice cannot be corrected, or null if it can.
 *
 * Mirrors `SalesService._ensure_amendable`. Nothing here is a control — the API
 * refuses independently — it only decides whether offering the action would end
 * in a refusal.
 */
export function amendBlockedReason(
  invoice: SalesInvoice
): "opening" | "settled" | null {
  if (invoice.is_opening) return "opening";
  // A cancelled invoice reads as fully settled because ERPNext zeroes the
  // outstanding amount when it reverses one; that is not a payment.
  if (invoice.is_cancelled) return null;
  if (invoice.grand_total - invoice.outstanding_amount > 0.005) return "settled";
  return null;
}
