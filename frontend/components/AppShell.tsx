"use client";

import { useState, type ReactNode } from "react";

import Sidebar from "@/components/Sidebar";
import SignIn from "@/components/SignIn";
import TopBar from "@/components/TopBar";
import { useAuth } from "@/lib/auth";

/** Authenticated app shell: sidebar + header + scrollable content area. */
export default function AppShell({ children }: { children: ReactNode }) {
  const { token, ready, user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  if (!ready)
    return (
      <div className="min-h-screen grid place-items-center bg-bg text-ink">
        Loading…
      </div>
    );
  if (!token) return <SignIn />;

  return (
    <div className="flex h-screen w-full bg-bg text-ink">
      <Sidebar collapsed={collapsed} user={user} onLogout={logout} />
      <div className="flex-1 min-w-0 h-full flex flex-col">
        <TopBar
          user={user}
          onToggleCollapse={() => setCollapsed((v) => !v)}
          onLogout={logout}
        />
        <main className="flex-1 overflow-y-auto eq-scroll bg-bg">
          <div className="max-w-content mx-auto px-6 md:px-8 py-7 pb-16">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
