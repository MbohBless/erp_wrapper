"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import CustomerForm from "@/components/customers/CustomerForm";
import { useAuth } from "@/lib/auth";
import { listCustomers } from "@/lib/customers";

export default function EditCustomerPage() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);
  const { token } = useAuth();

  const { data } = useQuery({
    queryKey: ["customers"],
    queryFn: () => listCustomers(token as string),
    enabled: !!token,
  });

  const record = (data ?? []).find((c) => c.id === id);

  return (
    <AppShell>
      {record ? (
        <CustomerForm initial={record} />
      ) : (
        <div className="eq-view muted">Loading…</div>
      )}
    </AppShell>
  );
}
