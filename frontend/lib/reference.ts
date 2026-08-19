"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/http";
import { useAuth } from "@/lib/auth";

/**
 * Selectable values for form pickers.
 *
 * Only leaf nodes. ERPNext organises this master data as trees whose roots
 * ("All Customer Groups") exist to hold branches and are refused on a
 * transaction — offering them offers failure, which is exactly how customer
 * creation broke.
 */
export type ReferenceOptions = {
  customer_groups: string[];
  supplier_groups: string[];
  territories: string[];
  item_groups: string[];
  warehouses: string[];
  uoms: string[];
};

export const getReferenceOptions = (token: string) =>
  api.get<ReferenceOptions>(token, "/reference/options");

export function useReferenceOptions() {
  const { token } = useAuth();
  const { data, isLoading } = useQuery({
    queryKey: ["reference-options"],
    queryFn: () => getReferenceOptions(token as string),
    enabled: !!token,
    // Master data changes rarely; refetching it on every form open is waste.
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
  return { options: data, loading: isLoading };
}
