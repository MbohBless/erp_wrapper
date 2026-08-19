"use client";

import { useState } from "react";

import Modal from "@/components/ui/Modal";
import { groupNum, parseNum, xaf } from "@/lib/api";
import { MODES } from "@/lib/payments";

const FIELD = "eq-field w-full px-4 py-3 text-[15px]";
const LABEL = "block text-[13px] muted mb-2";

export type PaymentValue = {
  amount: number | null;
  mode_of_payment: string | null;
  posting_date: string | null;
  reference_no: string | null;
};

export default function PaymentDialog({
  mode,
  party,
  reference,
  outstanding,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  mode: "receive" | "pay";
  party: string;
  reference: string;
  outstanding: number;
  busy: boolean;
  error: string | null;
  onSubmit: (v: PaymentValue) => void;
  onCancel: () => void;
}) {
  const receiving = mode === "receive";
  const [amount, setAmount] = useState(outstanding ? groupNum(String(outstanding)) : "");
  const [modeOfPayment, setModeOfPayment] = useState("");
  const [postingDate, setPostingDate] = useState("");
  const [referenceNo, setReferenceNo] = useState("");

  return (
    <Modal onClose={onCancel} className="max-w-[460px]">
      <form
        className="p-6"
        onSubmit={(e) => {
          e.preventDefault();
          const n = parseNum(amount);
          onSubmit({
            amount: Number.isNaN(n) ? null : n,
            mode_of_payment: modeOfPayment || null,
            posting_date: postingDate || null,
            reference_no: referenceNo || null,
          });
        }}
      >
        <h3 className="font-heading font-semibold text-2xl mb-1">
          {receiving ? "Record receipt" : "Record payment"}
        </h3>
        <p className="muted text-[13px] mb-5">
          {receiving ? "From" : "To"} <span className="text-ink">{party}</span> ·{" "}
          {reference} · outstanding{" "}
          <span className="text-ink">{xaf(outstanding)}</span>
        </p>

        {error && (
          <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px] mb-4">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          <div>
            <label className={LABEL}>Amount (XAF) *</label>
            <input
              className={`${FIELD} num text-right`}
              inputMode="numeric"
              value={amount}
              onChange={(e) => setAmount(groupNum(e.target.value))}
              required
            />
          </div>
          <div>
            <label className={LABEL}>Mode of payment</label>
            <select
              className={FIELD}
              value={modeOfPayment}
              onChange={(e) => setModeOfPayment(e.target.value)}
            >
              <option value="">Default</option>
              {MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={LABEL}>Date</label>
            <input
              className={FIELD}
              type="date"
              value={postingDate}
              onChange={(e) => setPostingDate(e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Reference no.</label>
            <input
              className={FIELD}
              value={referenceNo}
              onChange={(e) => setReferenceNo(e.target.value)}
              placeholder="Cheque / transfer ref"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2.5 mt-6">
          <button type="button" onClick={onCancel} className="btn btn-text">
            Cancel
          </button>
          <button type="submit" disabled={busy} className="btn btn-filled">
            {busy ? "Posting…" : receiving ? "Record receipt" : "Record payment"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
