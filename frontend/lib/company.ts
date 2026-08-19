"use client";

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { api } from "@/lib/http";

export type CompanyProfile = {
  display_name: string;
  legal_name: string;
  tagline: string;
  address_line: string;
  city: string;
  country: string;
  phone: string;
  email: string;
  website: string;
  rc_number: string;
  niu: string;
  currency: string;
  signatory_name: string;
  signatory_title: string;
  accent_color: string;
  logo_data_url: string;
};

export const getCompanyProfile = (token: string) =>
  api.get<CompanyProfile>(token, "/settings/company-profile");

export const updateCompanyProfile = (token: string, input: CompanyProfile) =>
  api.put<CompanyProfile>(token, "/settings/company-profile", input);

/**
 * The tenant's ERPNext Company name, for report/statement filters.
 *
 * This is business data, not branding: it must never fall back to the product
 * name, or a white-label tenant would query the ledger for a company that does
 * not exist. Empty until the profile loads.
 */
export function useCompanyName(): string {
  const { token } = useAuth();
  const { data } = useQuery({
    queryKey: ["company-profile"],
    queryFn: () => getCompanyProfile(token as string),
    enabled: !!token,
    staleTime: 5 * 60_000,
  });
  return data?.legal_name || data?.display_name || "";
}
