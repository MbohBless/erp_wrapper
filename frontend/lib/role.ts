"use client";

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { getMe, type Role } from "@/lib/users";

/**
 * The signed-in user's role.
 *
 * Read from `/auth/me` rather than decoded from the JWT: a client-side decode
 * would trust a token the user can edit in localStorage. Nothing here is a
 * security control anyway — the API enforces every rule independently — this
 * only decides what is worth *showing*.
 */
export function useRole(): { role: Role | null; ready: boolean } {
  const { token, ready: authReady } = useAuth();
  const { data, isLoading } = useQuery({
    queryKey: ["me", token],
    queryFn: () => getMe(token as string),
    enabled: !!token,
    staleTime: 5 * 60 * 1000,
  });
  return { role: data?.role ?? null, ready: authReady && !isLoading };
}

/**
 * Which roles may open each navigation destination.
 *
 * Mirrors the backend RBAC matrix (`backend/tests/test_rbac_matrix.py`, and the
 * table in `docs/api.md`) for the *read* endpoint behind each page. Keep the two
 * in step: showing a link the API refuses produces a dead end, and hiding one it
 * allows quietly removes a feature the customer is paying for.
 *
 * Administrator is allowed everywhere and is therefore omitted from the sets.
 */
export const NAV_ROLES: Record<string, readonly Role[] | "all"> = {
  dashboard: "all",
  products: "all",
  settings: "all",
  sales: ["Manager", "Sales", "Accountant"],
  customers: ["Manager", "Sales", "Accountant"],
  purchases: ["Manager", "Store Keeper", "Accountant"],
  suppliers: ["Manager", "Store Keeper", "Accountant"],
  inventory: ["Manager", "Sales", "Store Keeper", "Accountant"],
  equipment: ["Manager", "Sales", "Store Keeper", "Biomedical Engineer"],
  maintenance: ["Manager", "Sales", "Biomedical Engineer"],
  finance: ["Manager", "Accountant"],
  budget: ["Manager", "Accountant"],
  reports: ["Manager", "Accountant"],
};

export function canSee(key: string, role: Role | null): boolean {
  // Until the role is known, show nothing rather than flashing the full menu
  // and then retracting half of it.
  if (!role) return false;
  if (role === "Administrator") return true;
  const allowed = NAV_ROLES[key];
  if (allowed === undefined) return false; // unknown destination: fail closed
  return allowed === "all" || allowed.includes(role);
}
