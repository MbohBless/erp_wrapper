"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import BillForm from "@/components/purchases/BillForm";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { getPurchase } from "@/lib/purchases";

export default function EditBillPage() {
  const params = useParams();
  const id = decodeURIComponent(String(params.id));
  const { token } = useAuth();
  const { t } = useI18n();

  // By id, not from the list: list queries omit child tables, so a list row
  // carries no line items.
  const { data, isLoading, error } = useQuery({
    queryKey: ["purchase", id],
    queryFn: () => getPurchase(token as string, id),
    enabled: !!token,
  });

  return (
    <AppShell>
      {data ? (
        <BillForm amending={data} />
      ) : (
        <div className="eq-view muted">
          {isLoading ? t("common.loading") : error ? t("purchases.loadError") : null}
        </div>
      )}
    </AppShell>
  );
}
