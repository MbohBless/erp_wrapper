"use client";

import { useQuery } from "@tanstack/react-query";

import Shell from "@/components/Shell";
import { useAuth } from "@/lib/auth";
import { listFeatures, listPlans, xaf } from "@/lib/plans";

export default function PlansPage() {
  return (
    <Shell>
      <PlansContent />
    </Shell>
  );
}

function PlansContent() {
  const { token } = useAuth();
  const plansQ = useQuery({
    queryKey: ["plans"],
    queryFn: () => listPlans(token as string),
    enabled: !!token,
  });
  const featuresQ = useQuery({
    queryKey: ["features"],
    queryFn: () => listFeatures(token as string),
    enabled: !!token,
  });

  const allFeatures = featuresQ.data?.features ?? [];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-[26px] font-heading font-semibold">Plans</h1>
        <p className="muted text-sm mt-1">
          A plan&apos;s feature list is the contract the tenant app enforces — selling a
          capability is a change here, not a deploy.
        </p>
      </div>

      {plansQ.isLoading && <div className="muted py-10">Loading…</div>}
      {plansQ.error && (
        <div className="text-err py-10">{(plansQ.error as Error).message}</div>
      )}

      <div className="panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse min-w-[820px]">
            <thead>
              <tr className="muted-2">
                {["Plan", "Price / month", "Max users", "Workspaces", "Features"].map((h) => (
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
              {plansQ.data?.map((p) => (
                <tr key={p.code} className="border-b border-divider last:border-0 align-top">
                  <td className="py-3.5 px-4">
                    <div className="font-medium">{p.name}</div>
                    <div className="font-mono text-[11px] muted-2">{p.code}</div>
                    {!p.is_active && (
                      <div className="text-[11px] text-warn mt-0.5">inactive</div>
                    )}
                  </td>
                  <td className="py-3.5 px-4 tabular-nums">{xaf(p.price_xaf)}</td>
                  <td className="py-3.5 px-4 tabular-nums muted">{p.max_users}</td>
                  <td className="py-3.5 px-4 tabular-nums muted">{p.tenant_count}</td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-wrap gap-1.5">
                      {allFeatures.map((f) => {
                        const on = p.features.includes(f);
                        return (
                          <span
                            key={f}
                            className={`text-[11px] px-1.5 py-0.5 rounded font-mono ${
                              on
                                ? "bg-[color-mix(in_srgb,var(--color-accent)_18%,transparent)] text-accent"
                                : "muted-2 opacity-45 line-through"
                            }`}
                          >
                            {f}
                          </span>
                        );
                      })}
                    </div>
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
