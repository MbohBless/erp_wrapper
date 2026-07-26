"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import SupplierForm from "@/components/suppliers/SupplierForm";
import { useAuth } from "@/lib/auth";
import { listSuppliers } from "@/lib/suppliers";

export default function EditSupplierPage() {
  const { token } = useAuth();
  const params = useParams();
  const id = decodeURIComponent(String(params.id));

  const { data } = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => listSuppliers(token as string),
    enabled: !!token,
  });

  const record = (data ?? []).find((s) => s.id === id) ?? null;

  return (
    <AppShell>
      {record ? <SupplierForm initial={record} /> : <div className="eq-view muted">Loading…</div>}
    </AppShell>
  );
}
