"use client";

import { useState } from "react";

import Modal from "@/components/ui/Modal";
import { type Role, ROLES, type User } from "@/lib/users";

const FIELD = "eq-field w-full px-4 py-3 text-[15px]";
const LABEL = "block text-[13px] muted mb-2";

export type UserFormValue = {
  email: string;
  full_name: string;
  role: Role;
  password: string;
  is_active: boolean;
};

export default function UserDialog({
  initial,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: User | null;
  busy: boolean;
  error: string | null;
  onSubmit: (value: UserFormValue) => void;
  onCancel: () => void;
}) {
  const editing = !!initial;
  const [form, setForm] = useState<UserFormValue>({
    email: initial?.email ?? "",
    full_name: initial?.full_name ?? "",
    role: initial?.role ?? "Sales",
    password: "",
    is_active: initial?.is_active ?? true,
  });
  const set = (k: keyof UserFormValue, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <Modal onClose={onCancel} className="max-w-[460px]">
      <form className="p-6" onSubmit={(e) => { e.preventDefault(); onSubmit(form); }}>
        <h3 className="font-heading font-semibold text-xl mb-4">{editing ? "Edit user" : "New user"}</h3>
        {error && <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2 rounded-lg text-[13px] mb-4">{error}</div>}
        <div className="grid grid-cols-1 gap-3.5">
          <div>
            <label className={LABEL}>Email *</label>
            <input className={FIELD} type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required disabled={editing} />
          </div>
          <div>
            <label className={LABEL}>Full name *</label>
            <input className={FIELD} value={form.full_name} onChange={(e) => set("full_name", e.target.value)} required />
          </div>
          <div>
            <label className={LABEL}>Role</label>
            <select className={FIELD} value={form.role} onChange={(e) => set("role", e.target.value as Role)}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div>
            <label className={LABEL}>{editing ? "New password (leave blank to keep)" : "Password *"}</label>
            <input className={FIELD} type="password" value={form.password} onChange={(e) => set("password", e.target.value)} required={!editing} minLength={8} />
          </div>
          {editing && (
            <label className="flex items-center gap-2.5 text-sm cursor-pointer">
              <input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} />
              Active
            </label>
          )}
        </div>
        <div className="flex justify-end gap-2.5 mt-6">
          <button type="button" onClick={onCancel} className="btn btn-text">Cancel</button>
          <button type="submit" disabled={busy} className="btn btn-filled">
            {busy ? "Saving…" : editing ? "Save" : "Create user"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
