"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import Shell from "@/components/Shell";
import StatusBadge from "@/components/StatusBadge";
import { useAuth } from "@/lib/auth";
import { listPlans } from "@/lib/plans";
import {
  type TenantCreateInput,
  createTenant,
  getTenantStats,
  listTenants,
} from "@/lib/tenants";

const STATUSES = ["", "active", "pending", "provisioning", "suspended", "archived"];

export default function TenantsPage() {
  return (
    <Shell>
      <TenantsContent />
    </Shell>
  );
}

function TenantsContent() {
  const { token, can } = useAuth();
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);

  const tenantsQ = useQuery({
    queryKey: ["tenants", status, search],
    queryFn: () => listTenants(token as string, { status, search }),
    enabled: !!token,
  });
  const statsQ = useQuery({
    queryKey: ["tenant-stats"],
    queryFn: () => getTenantStats(token as string),
    enabled: !!token,
  });

  return (
    <div>
      <div className="flex items-end justify-between gap-4 flex-wrap mb-6">
        <div>
          <h1 className="text-[26px] font-heading font-semibold">Workspaces</h1>
          <p className="muted text-sm mt-1">
            Every customer tenant, and whether it is currently serving traffic.
          </p>
        </div>
        {can("operate") && (
          <button type="button" className="btn btn-filled" onClick={() => setCreating(true)}>
            New workspace
          </button>
        )}
      </div>

      {statsQ.data && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <Stat label="Total" value={statsQ.data.total} />
          <Stat label="Active" value={statsQ.data.active} tone="ok" />
          <Stat label="Suspended" value={statsQ.data.suspended} tone="err" />
          <Stat
            label="Pending setup"
            value={
              (statsQ.data.by_status.pending ?? 0) +
              (statsQ.data.by_status.provisioning ?? 0)
            }
            tone="warn"
          />
        </div>
      )}

      <div className="flex items-center gap-2.5 mb-4 flex-wrap">
        <input
          className="field max-w-[280px]"
          placeholder="Search id, name or contact…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="field max-w-[170px]"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s === "" ? "All statuses" : s}
            </option>
          ))}
        </select>
      </div>

      <div className="panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse min-w-[760px]">
            <thead>
              <tr className="muted-2">
                {["Workspace", "Host", "Plan", "Status", "Contact", "Created"].map((h) => (
                  <th
                    key={h}
                    className="text-left text-[11px] tracking-[0.08em] uppercase font-semibold py-3 px-4 border-b border-divider"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tenantsQ.isLoading && (
                <tr>
                  <td colSpan={6} className="py-10 text-center muted-2">
                    Loading…
                  </td>
                </tr>
              )}
              {tenantsQ.error && (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-err">
                    {(tenantsQ.error as Error).message}
                  </td>
                </tr>
              )}
              {tenantsQ.data?.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-10 text-center muted-2">
                    No workspaces match this filter.
                  </td>
                </tr>
              )}
              {tenantsQ.data?.map((t) => (
                <tr key={t.id} className="border-b border-divider last:border-0">
                  <td className="py-3 px-4">
                    <Link href={`/tenants/${t.id}`} className="font-medium hover:text-accent">
                      {t.name}
                    </Link>
                    <div className="font-mono text-[11px] muted-2">{t.id}</div>
                  </td>
                  <td className="py-3 px-4 font-mono text-[12px] muted">{t.primary_host}</td>
                  <td className="py-3 px-4 muted">{t.plan_code}</td>
                  <td className="py-3 px-4">
                    <StatusBadge status={t.status} />
                  </td>
                  <td className="py-3 px-4 muted text-[12px]">{t.contact_email || "—"}</td>
                  <td className="py-3 px-4 muted-2 text-[12px]">
                    {new Date(t.created_at).toLocaleDateString("en-GB")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {creating && <CreateDialog onClose={() => setCreating(false)} />}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "ok" | "err" | "warn";
}) {
  const color = tone ? `text-${tone}` : "";
  return (
    <div className="panel px-4 py-3">
      <div className="text-[11px] tracking-[0.08em] uppercase muted-2">{label}</div>
      <div className={`text-[26px] font-heading font-semibold mt-0.5 ${color}`}>{value}</div>
    </div>
  );
}

/**
 * Registering a workspace and provisioning it are separate steps on purpose:
 * creating the record is cheap and reversible, creating an ERPNext site is
 * neither. The dialog does the first and links to the second.
 */
function CreateDialog({ onClose }: { onClose: () => void }) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<TenantCreateInput>({
    id: "",
    name: "",
    plan_code: "",
    contact_email: "",
    admin_email: "",
    admin_password: "",
    admin_name: "Administrator",
  });

  const plansQ = useQuery({
    queryKey: ["plans"],
    queryFn: () => listPlans(token as string),
    enabled: !!token,
  });

  const mut = useMutation({
    mutationFn: () =>
      createTenant(token as string, {
        ...form,
        plan_code: form.plan_code || plansQ.data?.[0]?.code || "",
        contact_email: form.contact_email || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenants"] });
      qc.invalidateQueries({ queryKey: ["tenant-stats"] });
      onClose();
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not create workspace"),
  });

  const set = <K extends keyof TenantCreateInput>(k: K, v: TenantCreateInput[K]) =>
    setForm({ ...form, [k]: v });

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-6">
      <div className="panel w-full max-w-[520px] p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="font-heading font-semibold text-lg mb-1">New workspace</h2>
        <p className="muted text-[13px] mb-5">
          Creates the registry record only. Provision it from its detail page to
          create the ERPNext site and the first administrator.
        </p>

        {error && (
          <div className="text-err bg-[color-mix(in_srgb,var(--err)_12%,transparent)] px-3 py-2.5 rounded-lg text-[13px] mb-4">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          <Field label="Workspace id" hint="Becomes the subdomain">
            <input
              className="field font-mono"
              placeholder="acme"
              value={form.id}
              onChange={(e) => set("id", e.target.value)}
            />
          </Field>
          <Field label="Display name">
            <input
              className="field"
              placeholder="Acme Medical"
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
            />
          </Field>
          <Field label="Plan">
            <select
              className="field"
              value={form.plan_code}
              onChange={(e) => set("plan_code", e.target.value)}
            >
              <option value="">Select a plan…</option>
              {plansQ.data?.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Contact email">
            <input
              className="field"
              value={form.contact_email ?? ""}
              onChange={(e) => set("contact_email", e.target.value)}
            />
          </Field>
          <Field label="Admin email" hint="First user of the workspace">
            <input
              className="field"
              value={form.admin_email}
              onChange={(e) => set("admin_email", e.target.value)}
            />
          </Field>
          <Field label="Admin password" hint="At least 8 characters">
            <input
              className="field"
              type="password"
              value={form.admin_password}
              onChange={(e) => set("admin_password", e.target.value)}
            />
          </Field>
        </div>

        <div className="flex justify-end gap-2.5 mt-6">
          <button type="button" className="btn btn-outlined" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-filled"
            disabled={mut.isPending}
            onClick={() => {
              setError(null);
              mut.mutate();
            }}
          >
            {mut.isPending ? "Creating…" : "Create workspace"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-[13px] muted mb-1.5">{label}</label>
      {children}
      {hint && <div className="text-[11px] muted-2 mt-1">{hint}</div>}
    </div>
  );
}
