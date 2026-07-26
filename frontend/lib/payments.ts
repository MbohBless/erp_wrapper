import { api } from "@/lib/http";

export type Payment = {
  id: string;
  payment_type: string | null;
  party_type: string | null;
  party: string | null;
  paid_amount: number;
  posting_date: string | null;
  mode_of_payment: string | null;
  reference_no: string | null;
};

export type ReceiptInput = {
  invoice_id: string;
  amount?: number | null;
  mode_of_payment?: string | null;
  posting_date?: string | null;
  reference_no?: string | null;
};
export type PayInput = {
  bill_id: string;
  amount?: number | null;
  mode_of_payment?: string | null;
  posting_date?: string | null;
  reference_no?: string | null;
};

export const MODES = ["Cash", "Cheque", "Wire Transfer", "Bank Draft", "Credit Card"];

export const listPayments = (token: string) =>
  api.get<Payment[]>(token, "/payments", { limit: 200 });

export const recordReceipt = (token: string, input: ReceiptInput) =>
  api.post<Payment>(token, "/payments/receive", input);

export const recordPayment = (token: string, input: PayInput) =>
  api.post<Payment>(token, "/payments/pay", input);
