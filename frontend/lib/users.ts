import { api } from "@/lib/http";

export type Role =
  | "Administrator"
  | "Manager"
  | "Sales"
  | "Store Keeper"
  | "Accountant"
  | "Biomedical Engineer";

export const ROLES: Role[] = [
  "Administrator",
  "Manager",
  "Sales",
  "Store Keeper",
  "Accountant",
  "Biomedical Engineer",
];

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
