"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import SignIn from "@/components/SignIn";
import { useAuth } from "@/lib/auth";

const NAV = [
  { href: "/tenants", label: "Workspaces" },
  { href: "/plans", label: "Plans" },
  { href: "/audit", label: "Audit log" },
];

export default function Shell({ children }: { children: ReactNode }) {
  const { token, operator, ready, logout } = useAuth();
  const pathname = usePathname();

  if (!ready) {
    return (
      <div className="min-h-screen grid place-items-center muted">Loading…</div>
    );
  }
  if (!token) return <SignIn />;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-divider">
        <div className="max-w-content mx-auto px-6 h-14 flex items-center gap-6">
          <Link href="/tenants" className="flex items-center gap-2.5 shrink-0">
            <span className="w-7 h-7 rounded-md bg-accent text-[#0e1116] grid place-items-center font-bold text-[13px]">
              EQ
            </span>
            <span className="font-heading font-semibold text-[15px]">
              Control Plane
            </span>
          </Link>

          <nav className="flex items-center gap-1 flex-1">
            {NAV.map((item) => {
              const active = pathname?.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                    active
                      ? "bg-[color-mix(in_srgb,var(--color-text)_10%,transparent)] text-ink"
                      : "muted hover:text-ink"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center gap-3 text-sm">
            <span className="muted hidden sm:inline">
              {operator?.full_name}
              <span className="muted-2"> · {operator?.role}</span>
            </span>
            <button type="button" onClick={logout} className="btn btn-outlined">
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <div className="max-w-content mx-auto px-6 py-7">{children}</div>
      </main>
    </div>
  );
}
