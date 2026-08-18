"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import InvoiceForm from "@/components/sales/InvoiceForm";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { getSale } from "@/lib/sales";

export default function EditInvoicePage() {
  const params = useParams();
  const id = decodeURIComponent(String(params.id));
  const { token } = useAuth();
  const { t } = useI18n();

  // Fetched by id, not taken from the list: an ERPNext list query cannot
  // return child tables, so a list row has no line items — and a correction
  // seeded from one would re-post the invoice with nothing on it.
  const { data, isLoading, error } = useQuery({
    queryKey: ["sale", id],
    queryFn: () => getSale(token as string, id),
    enabled: !!token,
  });

  return (
    <AppShell>
      {data ? (
        <InvoiceForm amending={data} />
      ) : (
        <div className="eq-view muted">
          {isLoading ? t("common.loading") : error ? t("sales.loadError") : null}
        </div>
      )}
    </AppShell>
  );
}
