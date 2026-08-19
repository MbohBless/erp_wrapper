"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { AuthProvider } from "@/lib/auth";
import { BrandingProvider } from "@/lib/branding";
import { I18nProvider } from "@/lib/i18n";
import { ThemeProvider } from "@/lib/theme";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: false, staleTime: 30_000 } },
      })
  );
  return (
    <QueryClientProvider client={queryClient}>
      {/* Branding wraps Theme: the tenant's default light/dark preference is
          part of their brand, so it has to be known before the theme resolves. */}
      <BrandingProvider>
        <ThemeProvider>
          <I18nProvider>
            <AuthProvider>{children}</AuthProvider>
          </I18nProvider>
        </ThemeProvider>
      </BrandingProvider>
    </QueryClientProvider>
  );
}
