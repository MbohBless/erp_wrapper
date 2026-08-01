import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import { Providers } from "./providers";

// Static fallback only. The real title/favicon are applied client-side by
// BrandingProvider once the tenant's branding resolves — a build-time value
// cannot know which workspace is being served.
export const metadata: Metadata = {
  title: "Distribution Suite",
  description: "Medical equipment distribution management platform",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
