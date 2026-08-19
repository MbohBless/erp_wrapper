import { api } from "@/lib/http";

export type Role =
  | "Administrator"
  | "Manager"
  | "Sales"
  | "Store Keeper"
  | "Accountant"
  | "Biomedical Engineer";

/**
 * Every role the product defines.
 *
 * Not the same as the roles a given workspace hands out — a deployment can
 * retire one it does not use (DISABLED_ROLES). Use `getAssignableRoles` when
 * offering a choice; this list is the fallback for when that call has not
 * returned yet, and the type's full domain for reading a user back.
 */
export const ROLES: Role[] = [
  "Administrator",
  "Manager",
  "Sales",
  "Store Keeper",
  "Accountant",
  "Biomedical Engineer",
];

/** The roles this deployment will actually assign. Administrator only. */
export const getAssignableRoles = (token: string) =>
  api.get<Role[]>(token, "/users/roles");

export type User = {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type UserCreate = {
  email: string;
  full_name: string;
  role: Role;
  password: string;
};

export type UserUpdate = {
  full_name?: string;
  role?: Role;
  is_active?: boolean;
  password?: string;
};

export const getMe = (token: string) => api.get<User>(token, "/auth/me");

export const listUsers = (token: string) =>
  api.get<User[]>(token, "/users", { limit: 200 });

export const createUser = (token: string, input: UserCreate) =>
  api.post<User>(token, "/users", input);

export const updateUser = (token: string, id: number, input: UserUpdate) =>
  api.put<User>(token, `/users/${id}`, input);

export const deleteUser = (token: string, id: number) =>
  api.del(token, `/users/${id}`);
