"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import Shell from "@/components/Shell";
import StatusBadge from "@/components/StatusBadge";
import { useAuth } from "@/lib/auth";
import { listAudit, when } from "@/lib/plans";
import {
  type Tenant,
  addDomain,
  archiveTenant,
  getTenant,
  provisionTenant,
  purgeTenant,
  removeDomain,
  resumeTenant,
  suspendTenant,
  verifyDomain,
} from "@/lib/tenants";

export default function TenantDetailPage() {
  return (
    <Shell>
      <TenantDetail />
    </Shell>
  );
}

function TenantDetail() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const { token, can } = useAuth();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<string[]>([]);

  const tenantQ = useQuery({
    queryKey: ["tenant", id],
    queryFn: () => getTenant(token as string, id),
    enabled: !!token && !!id,
  });
  const auditQ = useQuery({
    queryKey: ["audit", id],
    queryFn: () => listAudit(token as string, { tenant_id: id, limit: 25 }),
    enabled: !!token && !!id,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["tenant", id] });
    qc.invalidateQueries({ queryKey: ["audit", id] });
    qc.invalidateQueries({ queryKey: ["tenants"] });
    qc.invalidateQueries({ queryKey: ["tenant-stats"] });
  };
  const onError = (e: unknown) =>
    setError(e instanceof Error ? e.message : "Action failed");
  const onDone = () => {
    setError(null);
    refresh();
  };

  const tenant = tenantQ.data;

  if (tenantQ.isLoading) return <div className="muted py-10">Loading…</div>;
  if (tenantQ.error)
    return <div className="text-err py-10">{(tenantQ.error as Error).message}</div>;
  if (!tenant) return null;

  return (
    <div>
      <Link href="/tenants" className="text-[13px] muted hover:text-ink">
        ← Workspaces
      </Link>

      <div className="flex items-start justify-between gap-4 flex-wrap mt-3 mb-6">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-[26px] font-heading font-semibold">{tenant.name}</h1>
            <StatusBadge status={tenant.status} />
          </div>
          <div className="font-mono text-[12px] muted-2 mt-1">
            {tenant.id} · {tenant.primary_host}
          </div>
        </div>
        <LifecycleActions
          tenant={tenant}
          canOperate={can("operate")}
          canOwn={can("own")}
          onError={onError}
          onDone={onDone}
          onMessages={setMessages}
        />
      </div>

      {error && (
        <div className="text-err bg-[color-mix(in_srgb,var(--err)_12%,transparent)] px-3 py-2.5 rounded-lg text-[13px] mb-4">
          {error}
        </div>
      )}
      {messages.length > 0 && (
        <div className="panel p-4 mb-4">
          <div className="text-[13px] font-medium mb-1.5">Provisioning output</div>
          <ul className="font-mono text-[12px] muted flex flex-col gap-0.5 m-0 p-0 list-none">
            {messages.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {tenant.status === "suspended" && tenant.suspended_reason && (
        <div className="panel p-4 mb-4 border-l-2 border-l-[var(--err)]">
          <div className="text-[13px]">
            <span className="text-err font-medium">Suspended</span>
            <span className="muted"> — {tenant.suspended_reason}</span>
          </div>
          <div className="text-[12px] muted-2 mt-0.5">{when(tenant.suspended_at)}</div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="panel p-5">
          <h2 className="font-heading font-semibold text-[15px] mb-3.5">Details</h2>
          <dl className="grid grid-cols-[130px_1fr] gap-y-2.5 text-[13px] m-0">
            <Row k="Plan" v={tenant.plan_code} />
            <Row k="Contact" v={tenant.contact_email || "—"} />
            <Row k="Country" v={tenant.country} />
            <Row k="Created" v={when(tenant.created_at)} />
            <Row k="Provisioned" v={when(tenant.provisioned_at)} />
          </dl>
        </section>

        <section className="panel p-5">
          <h2 className="font-heading font-semibold text-[15px] mb-3.5">ERPNext</h2>
          <dl className="grid grid-cols-[130px_1fr] gap-y-2.5 text-[13px] m-0">
            <Row k="URL" v={tenant.erpnext_url || "—"} mono />
            <Row k="Site" v={tenant.erpnext_site || "—"} mono />
            <Row k="API key" v={tenant.erpnext_api_key || "—"} mono />
            <Row
              k="API secret"
              v={tenant.has_erpnext_secret ? "set (encrypted)" : "not set"}
            />
          </dl>
        </section>

        <DomainsPanel
          tenant={tenant}
          canOperate={can("operate")}
          onError={onError}
          onDone={onDone}
        />

        <section className="panel p-5">
          <h2 className="font-heading font-semibold text-[15px] mb-3.5">Recent activity</h2>
          {auditQ.data?.length ? (
            <ul className="flex flex-col gap-2 m-0 p-0 list-none text-[13px]">
              {auditQ.data.map((e) => (
                <li key={e.id} className="flex items-baseline gap-2">
                  <span className="font-mono text-[11px] muted-2 shrink-0 w-[132px]">
                    {when(e.created_at)}
                  </span>
                  <span className="flex-1">
                    <span className="font-medium">{e.action}</span>
                    <span className="muted-2"> · {e.actor_email}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="muted-2 text-[13px]">No recorded actions yet.</div>
          )}
        </section>
      </div>
    </div>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <>
      <dt className="muted">{k}</dt>
      <dd className={`m-0 ${mono ? "font-mono text-[12px]" : ""}`}>{v}</dd>
    </>
  );
}

function LifecycleActions({
  tenant,
  canOperate,
  canOwn,
  onError,
  onDone,
  onMessages,
}: {
  tenant: Tenant;
  canOperate: boolean;
  canOwn: boolean;
  onError: (e: unknown) => void;
  onDone: () => void;
  onMessages: (m: string[]) => void;
}) {
  const { token } = useAuth();
  const [dialog, setDialog] = useState<null | "suspend" | "provision" | "purge">(null);

  const resumeMut = useMutation({
    mutationFn: () => resumeTenant(token as string, tenant.id),
    onSuccess: onDone,
    onError,
  });
  const archiveMut = useMutation({
    mutationFn: () => archiveTenant(token as string, tenant.id),
    onSuccess: onDone,
    onError,
  });

  if (!canOperate) return null;

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {(tenant.status === "pending" || tenant.status === "provisioning") && (
        <button type="button" className="btn btn-filled" onClick={() => setDialog("provision")}>
          Provision
        </button>
      )}
      {tenant.status === "active" && (
        <button type="button" className="btn btn-danger" onClick={() => setDialog("suspend")}>
          Suspend
        </button>
      )}
      {tenant.status === "suspended" && (
        <button
          type="button"
          className="btn btn-filled"
          disabled={resumeMut.isPending}
          onClick={() => resumeMut.mutate()}
        >
          Resume
        </button>
      )}
      {tenant.status !== "archived" && (
        <button
          type="button"
          className="btn btn-outlined"
          disabled={archiveMut.isPending}
          onClick={() => archiveMut.mutate()}
        >
          Archive
        </button>
      )}
      {tenant.status === "archived" && canOwn && (
        <button type="button" className="btn btn-danger" onClick={() => setDialog("purge")}>
          Purge permanently
        </button>
      )}

      {dialog === "suspend" && (
        <SuspendDialog
          tenant={tenant}
          onClose={() => setDialog(null)}
          onDone={onDone}
          onError={onError}
        />
      )}
      {dialog === "provision" && (
        <ProvisionDialog
          tenant={tenant}
          onClose={() => setDialog(null)}
          onDone={onDone}
          onError={onError}
          onMessages={onMessages}
        />
      )}
      {dialog === "purge" && (
        <PurgeDialog
          tenant={tenant}
          onClose={() => setDialog(null)}
          onError={onError}
        />
      )}
    </div>
  );
}

function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-6">
      <div className="panel w-full max-w-[460px] p-6">
        <h2 className="font-heading font-semibold text-lg mb-4">{title}</h2>
        {children}
      </div>
    </div>
  );
}

function SuspendDialog({
  tenant,
  onClose,
  onDone,
  onError,
}: {
  tenant: Tenant;
  onClose: () => void;
  onDone: () => void;
  onError: (e: unknown) => void;
}) {
  const { token } = useAuth();
  const [reason, setReason] = useState("");
  const mut = useMutation({
    mutationFn: () => suspendTenant(token as string, tenant.id, reason),
    onSuccess: () => {
      onDone();
      onClose();
    },
    onError: (e) => {
      onError(e);
      onClose();
    },
  });

  return (
    <Modal title={`Suspend ${tenant.name}`} onClose={onClose}>
      <p className="muted text-[13px] mb-4">
        Everyone in this workspace is locked out until it is resumed. Data is
        untouched. The reason is shown to them on the sign-in screen.
      </p>
      <label className="block text-[13px] muted mb-1.5">Reason</label>
      <input
        className="field mb-5"
        placeholder="Invoice 42 unpaid"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      <div className="flex justify-end gap-2.5">
        <button type="button" className="btn btn-outlined" onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-danger"
          disabled={mut.isPending || !reason.trim()}
          onClick={() => mut.mutate()}
        >
          {mut.isPending ? "Suspending…" : "Suspend workspace"}
        </button>
      </div>
    </Modal>
  );
}

function ProvisionDialog({
  tenant,
  onClose,
  onDone,
  onError,
  onMessages,
}: {
  tenant: Tenant;
  onClose: () => void;
  onDone: () => void;
  onError: (e: unknown) => void;
  onMessages: (m: string[]) => void;
}) {
  const { token } = useAuth();
  const [adminEmail, setAdminEmail] = useState(tenant.contact_email || "");
  const [adminPassword, setAdminPassword] = useState("");

  const mut = useMutation({
    mutationFn: () =>
      provisionTenant(token as string, tenant.id, {
        id: tenant.id,
        name: tenant.name,
        plan_code: tenant.plan_code,
        admin_email: adminEmail,
        admin_password: adminPassword,
        admin_name: "Administrator",
      }),
    onSuccess: (result) => {
      onMessages(result.messages);
      onDone();
      onClose();
    },
    onError: (e) => {
      onError(e);
      onClose();
    },
  });

  return (
    <Modal title={`Provision ${tenant.name}`} onClose={onClose}>
      <p className="muted text-[13px] mb-4">
        Creates the ERPNext site and the workspace&apos;s first administrator. Safe
        to re-run — both steps are idempotent.
      </p>
      <label className="block text-[13px] muted mb-1.5">Administrator email</label>
      <input
        className="field mb-3.5"
        value={adminEmail}
        onChange={(e) => setAdminEmail(e.target.value)}
      />
      <label className="block text-[13px] muted mb-1.5">Administrator password</label>
      <input
        className="field mb-5"
        type="password"
        value={adminPassword}
        onChange={(e) => setAdminPassword(e.target.value)}
      />
      <div className="flex justify-end gap-2.5">
        <button type="button" className="btn btn-outlined" onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-filled"
          disabled={mut.isPending || adminPassword.length < 8 || !adminEmail}
          onClick={() => mut.mutate()}
        >
          {mut.isPending ? "Provisioning…" : "Provision"}
        </button>
      </div>
    </Modal>
  );
}

function PurgeDialog({
  tenant,
  onClose,
  onError,
}: {
  tenant: Tenant;
  onClose: () => void;
  onError: (e: unknown) => void;
}) {
  const { token } = useAuth();
  const router = useRouter();
  const [confirm, setConfirm] = useState("");

  const mut = useMutation({
    mutationFn: () => purgeTenant(token as string, tenant.id, confirm),
    onSuccess: () => router.push("/tenants"),
    onError: (e) => {
      onError(e);
      onClose();
    },
  });

  return (
    <Modal title={`Purge ${tenant.name}`} onClose={onClose}>
      <p className="text-[13px] mb-4">
        <span className="text-err font-medium">This is irreversible.</span>
        <span className="muted">
          {" "}
          The ERPNext site is backed up, then dropped, and every app record for
          this workspace is deleted.
        </span>
      </p>
      <label className="block text-[13px] muted mb-1.5">
        Type <span className="font-mono text-ink">{tenant.id}</span> to confirm
      </label>
      <input
        className="field font-mono mb-5"
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
      />
      <div className="flex justify-end gap-2.5">
        <button type="button" className="btn btn-outlined" onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-danger"
          disabled={mut.isPending || confirm !== tenant.id}
          onClick={() => mut.mutate()}
        >
          {mut.isPending ? "Purging…" : "Purge permanently"}
        </button>
      </div>
    </Modal>
  );
}

function DomainsPanel({
  tenant,
  canOperate,
  onError,
  onDone,
}: {
  tenant: Tenant;
  canOperate: boolean;
  onError: (e: unknown) => void;
  onDone: () => void;
}) {
  const { token } = useAuth();
  const [host, setHost] = useState("");

  const addMut = useMutation({
    mutationFn: () => addDomain(token as string, tenant.id, host),
    onSuccess: () => {
      setHost("");
      onDone();
    },
    onError,
  });
  const verifyMut = useMutation({
    mutationFn: (h: string) => verifyDomain(token as string, tenant.id, h),
    onSuccess: onDone,
    onError,
  });
  const removeMut = useMutation({
    mutationFn: (h: string) => removeDomain(token as string, tenant.id, h),
    onSuccess: onDone,
    onError,
  });

  return (
    <section className="panel p-5">
      <h2 className="font-heading font-semibold text-[15px] mb-1">Domains</h2>
      <p className="muted-2 text-[12px] mb-3.5">
        A certificate is only issued once a domain is verified.
      </p>

      <ul className="flex flex-col gap-2 m-0 p-0 list-none">
        {tenant.domains.map((d) => (
          <li key={d.host} className="flex items-center gap-2 text-[13px] flex-wrap">
            <span className="font-mono text-[12px] flex-1 min-w-[160px]">{d.host}</span>
            {d.is_primary && (
              <span className="text-[10px] uppercase tracking-wide muted-2">primary</span>
            )}
            <span className={d.verified_at ? "text-ok text-[11px]" : "text-warn text-[11px]"}>
              {d.verified_at ? "verified" : "unverified"}
            </span>
            {canOperate && !d.verified_at && (
              <button
                type="button"
                className="text-[11px] muted hover:text-accent"
                onClick={() => verifyMut.mutate(d.host)}
              >
                verify
              </button>
            )}
            {canOperate && tenant.domains.length > 1 && (
              <button
                type="button"
                className="text-[11px] muted hover:text-err"
                onClick={() => removeMut.mutate(d.host)}
              >
                remove
              </button>
            )}
          </li>
        ))}
      </ul>

      {canOperate && (
        <div className="flex gap-2 mt-4">
          <input
            className="field font-mono text-[12px]"
            placeholder="erp.customer.cm"
            value={host}
            onChange={(e) => setHost(e.target.value)}
          />
          <button
            type="button"
            className="btn btn-outlined shrink-0"
            disabled={!host.trim() || addMut.isPending}
            onClick={() => addMut.mutate()}
          >
            Add
          </button>
        </div>
      )}
    </section>
  );
}
