"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import MaintenanceForm from "@/components/maintenance/MaintenanceForm";
import { useAuth } from "@/lib/auth";
import { listTickets } from "@/lib/maintenance";

export default function EditMaintenancePage() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);
  const { token } = useAuth();

  const { data } = useQuery({
    queryKey: ["maintenance", "", ""],
    queryFn: () => listTickets(token as string, {}),
    enabled: !!token,
  });

  const record = (data ?? []).find((t) => t.id === id);

  return (
    <AppShell>
      {record ? (
        <MaintenanceForm initial={record} />
      ) : (
        <div className="eq-view muted">Loading…</div>
      )}
    </AppShell>
  );
}
