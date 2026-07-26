"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import ProductForm from "@/components/products/ProductForm";
import { useAuth } from "@/lib/auth";
import { listProducts } from "@/lib/products";

export default function EditProductPage() {
  const params = useParams();
  const id = decodeURIComponent(String(params.id));
  const { token } = useAuth();

  const { data } = useQuery({
    queryKey: ["products"],
    queryFn: () => listProducts(token as string),
    enabled: !!token,
  });

  const record = (data ?? []).find((p) => p.id === id);

  return (
    <AppShell>
      {record ? <ProductForm initial={record} /> : <div className="eq-view muted">Loading…</div>}
    </AppShell>
  );
}
