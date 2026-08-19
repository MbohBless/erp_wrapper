"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import Shell from "@/components/Shell";
import { useAuth } from "@/lib/auth";
import { listAudit, when } from "@/lib/plans";

export default function AuditPage() {
  return (
    <Shell>
      <AuditContent />
    </Shell>
  );
}

function AuditContent() {
  const { token } = useAuth();
  const [tenantId, setTenantId] = useState("");

  const auditQ = useQuery({
    queryKey: ["audit", tenantId],
    queryFn: () => listAudit(token as string, { tenant_id: tenantId, limit: 200 }),
    enabled: !!token,
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-[26px] font-heading font-semibold">Audit log</h1>
        <p className="muted text-sm mt-1">
          Every workspace transition, and who caused it. Append-only.
        </p>
      </div>

      <input
        className="field max-w-[280px] font-mono text-[12px] mb-4"
        placeholder="Filter by workspace id…"
        value={tenantId}
        onChange={(e) => setTenantId(e.target.value)}
      />

      <div className="panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse min-w-[760px]">
            <thead>
              <tr className="muted-2">
                {["When", "Action", "Workspace", "Operator", "Detail"].map((h) => (
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
              {auditQ.isLoading && (
                <tr>
                  <td colSpan={5} className="py-10 text-center muted-2">
                    Loading…
                  </td>
                </tr>
              )}
              {auditQ.data?.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-10 text-center muted-2">
                    Nothing recorded yet.
                  </td>
                </tr>
              )}
              {auditQ.data?.map((e) => (
                <tr key={e.id} className="border-b border-divider last:border-0">
                  <td className="py-2.5 px-4 font-mono text-[11px] muted-2 whitespace-nowrap">
                    {when(e.created_at)}
                  </td>
                  <td className="py-2.5 px-4 font-medium whitespace-nowrap">{e.action}</td>
                  <td className="py-2.5 px-4 font-mono text-[12px]">
                    {e.tenant_id ? (
                      <Link href={`/tenants/${e.tenant_id}`} className="hover:text-accent">
                        {e.tenant_id}
                      </Link>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="py-2.5 px-4 muted text-[12px]">{e.actor_email}</td>
                  <td className="py-2.5 px-4 font-mono text-[11px] muted-2 max-w-[320px] truncate">
                    {e.detail}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
