"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import EquipmentForm from "@/components/equipment/EquipmentForm";
import { useAuth } from "@/lib/auth";
import { listEquipment } from "@/lib/equipment";

export default function EditEquipmentPage() {
  const { token } = useAuth();
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);

  const { data } = useQuery({
    queryKey: ["equipment"],
    queryFn: () => listEquipment(token as string),
    enabled: !!token,
  });

  const record = (data ?? []).find((e) => e.id === id) ?? null;

  return (
    <AppShell>
      {record ? (
        <EquipmentForm initial={record} />
      ) : (
        <div className="eq-view muted">Loading…</div>
      )}
    </AppShell>
  );
}
