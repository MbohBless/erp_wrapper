"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import ConfirmDialog from "@/components/ConfirmDialog";
import UserDialog, { type UserFormValue } from "@/components/settings/UserDialog";
import { Icon } from "@/components/icons";
import { UnauthorizedError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import {
  type User,
  createUser,
  deleteUser,
  getMe,
  listUsers,
  updateUser,
} from "@/lib/users";

export default function SettingsPage() {
  return (
    <AppShell>
      <SettingsContent />
    </AppShell>
  );
}

function SettingsContent() {
  const { token, logout } = useAuth();
  const { theme, toggle } = useTheme();

  const meQ = useQuery({
    queryKey: ["me"],
    queryFn: () => getMe(token as string),
    enabled: !!token,
  });
  useEffect(() => {
    if (meQ.error instanceof UnauthorizedError) logout();
  }, [meQ.error, logout]);

  const isAdmin = meQ.data?.role === "Administrator";

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>EquiMed</span><span>›</span><span className="text-ink">Settings</span>
      </nav>
      <div className="mb-6">
        <h1 className="text-[32px] mb-1">Settings</h1>
        <p className="muted text-sm m-0">Profile, company, users, roles and preferences</p>
      </div>

      <div className="max-w-[1000px] flex flex-col gap-5">
        {/* Profile */}
        <Section title="Your profile">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <ReadOnly label="Full name" value={meQ.data?.full_name ?? "…"} />
            <ReadOnly label="Email" value={meQ.data?.email ?? "…"} />
            <ReadOnly label="Role" value={meQ.data?.role ?? "…"} />
          </div>
        </Section>

        {/* Company */}
        <Section title="Company information" note="Configured in ERPNext">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <ReadOnly label="Company name" value="EquiMed SA" />
            <ReadOnly label="Country" value="Cameroon" />
            <ReadOnly label="Chart of accounts" value="SYSCOHADA" />
            <ReadOnly label="Registered address" value="Bonanjo, Douala, Cameroon" />
          </div>
        </Section>

        {/* Regional */}
        <Section title="Regional & currency" note="Configured in ERPNext">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <ReadOnly label="Base currency" value="XAF — Central African CFA franc" />
            <ReadOnly label="Timezone" value="GMT+1 · Africa/Douala" />
          </div>
        </Section>

        {/* Preferences */}
        <Section title="Preferences">
          <div className="flex items-center justify-between py-1.5">
            <div>
              <div className="text-sm font-medium">Appearance</div>
              <div className="text-xs muted">Switch between light and dark across the app</div>
            </div>
            <button
              type="button"
              onClick={toggle}
              className="h-9 px-4 rounded-lg border border-divider text-sm font-heading font-semibold capitalize hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)]"
            >
              {theme}
            </button>
          </div>
        </Section>

        {isAdmin && token && <UsersSection token={token} meId={meQ.data?.id} />}
      </div>
    </div>
  );
}

function UsersSection({ token, meId }: { token: string; meId?: number }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["users"], queryFn: () => listUsers(token) });
  const [dialog, setDialog] = useState<{ kind: "create" } | { kind: "edit"; u: User } | { kind: "delete"; u: User } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["users"] });

  const createMut = useMutation({
    mutationFn: (v: UserFormValue) => createUser(token, { email: v.email, full_name: v.full_name, role: v.role, password: v.password }),
    onSuccess: () => { invalidate(); setDialog(null); },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, v }: { id: number; v: UserFormValue }) =>
      updateUser(token, id, { full_name: v.full_name, role: v.role, is_active: v.is_active, ...(v.password ? { password: v.password } : {}) }),
    onSuccess: () => { invalidate(); setDialog(null); },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteUser(token, id),
    onSuccess: () => { invalidate(); setDialog(null); },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <Blueprint className="p-0 overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-divider">
        <span className="font-heading font-semibold text-base">Users &amp; roles</span>
        <button type="button" onClick={() => { setError(null); setDialog({ kind: "create" }); }} className="h-9 px-3.5 inline-flex items-center gap-2 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600">
          <Icon name="plus" size={14} sw={1.8} />New user
        </button>
      </div>
      <div className="overflow-x-auto eq-scroll">
        <table className="w-full text-sm border-collapse min-w-[620px]">
          <thead>
            <tr className="muted">
              {["Name", "Email", "Role", "Status", ""].map((h, i) => (
                <th key={i} className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${i === 0 ? "text-left pl-6" : "text-left"}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={5} className="py-8 text-center muted-2">Loading…</td></tr>
            ) : (
              (data ?? []).map((u) => (
                <tr key={u.id} className="group border-b border-solid divide-soft">
                  <td className="pl-6 py-3 font-medium">{u.full_name}</td>
                  <td className="py-3 muted">{u.email}</td>
                  <td className="py-3 muted">{u.role}</td>
                  <td className="py-3">
                    <span className={`inline-flex items-center text-[11px] px-2.5 py-0.5 rounded-full ${u.is_active ? "bg-[color-mix(in_srgb,var(--ok-raw)_15%,transparent)] text-ok" : "bg-[color-mix(in_srgb,var(--color-text)_10%,transparent)] muted"}`}>
                      {u.is_active ? "Active" : "Disabled"}
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button type="button" title="Edit" onClick={() => { setError(null); setDialog({ kind: "edit", u }); }} className="icobtn grid place-items-center w-8 h-8 muted hover:text-accent"><Icon name="pencil" size={16} /></button>
                      {u.id !== meId && (
                        <button type="button" title="Delete" onClick={() => { setError(null); setDialog({ kind: "delete", u }); }} className="icobtn grid place-items-center w-8 h-8 muted hover:text-err"><Icon name="trash" size={16} /></button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {(dialog?.kind === "create" || dialog?.kind === "edit") && (
        <UserDialog
          initial={dialog.kind === "edit" ? dialog.u : null}
          busy={createMut.isPending || updateMut.isPending}
          error={error}
          onCancel={() => setDialog(null)}
          onSubmit={(v) => { setError(null); dialog.kind === "edit" ? updateMut.mutate({ id: dialog.u.id, v }) : createMut.mutate(v); }}
        />
      )}
      {dialog?.kind === "delete" && (
        <ConfirmDialog
          title="Delete user"
          message={`Delete “${dialog.u.full_name}”? This cannot be undone.`}
          confirmLabel="Delete"
          busy={deleteMut.isPending}
          error={error}
          onCancel={() => setDialog(null)}
          onConfirm={() => deleteMut.mutate(dialog.u.id)}
        />
      )}
    </Blueprint>
  );
}

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <Blueprint className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="font-heading font-semibold text-base">{title}</div>
        {note && <span className="text-[11px] muted-2">{note}</span>}
      </div>
      {children}
    </Blueprint>
  );
}

function ReadOnly({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <label className="block text-xs muted mb-1.5">{label}</label>
      <div className="eq-field w-full px-3 py-2.5 text-sm bg-[color-mix(in_srgb,var(--color-text)_3%,transparent)]">{value}</div>
    </div>
  );
}
