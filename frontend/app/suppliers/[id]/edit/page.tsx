"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import SupplierForm from "@/components/suppliers/SupplierForm";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { getSupplier } from "@/lib/suppliers";

export default function EditSupplierPage() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(String(params.id));
  const { token } = useAuth();
  const { t } = useI18n();

  // Fetched by id, not searched for in a page of the list. The list is paged,
  // so a record past the first page was simply absent and the form waited
  // forever for something that was never coming.
  const { data, isLoading } = useQuery({
    queryKey: ["suppliers", id],
    queryFn: () => getSupplier(token as string, id),
    enabled: !!token,
    retry: false,
  });

  return (
    <AppShell>
      {data ? (
        <SupplierForm initial={data} />
      ) : (
        <div className="eq-view muted">
          {isLoading ? t("common.loading") : t("common.recordNotFound")}
        </div>
      )}
    </AppShell>
  );
}
