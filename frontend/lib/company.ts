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
