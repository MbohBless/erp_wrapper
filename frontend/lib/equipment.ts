import { type Paged, api, encodeId } from "@/lib/http";

export type EquipmentStatus =
  | "In Store"
  | "Installed"
  | "Under Repair"
  | "Decommissioned";

export type Equipment = {
  id: string;
  serial_no: string;
  item_code: string;
  item_name: string | null;
  customer: string | null;
  installation_date: string | null;
  warranty_expiry_date: string | null;
  status: EquipmentStatus;
};

export type EquipmentInput = {
  serial_no: string;
  item_code: string;
  customer?: string | null;
  installation_date?: string | null;
  warranty_expiry_date?: string | null;
  status?: EquipmentStatus;
};

export const listEquipment = (
  token: string,
  params: Paged & { search?: string; status?: string } = {}
) => api.get<Equipment[]>(token, "/equipment", { limit: 200, ...params });

export const createEquipment = (token: string, input: EquipmentInput) =>
  api.post<Equipment>(token, "/equipment", input);

export const updateEquipment = (token: string, id: string, input: EquipmentInput) =>
  api.put<Equipment>(token, `/equipment/${encodeId(id)}`, input);

export const deleteEquipment = (token: string, id: string) =>
  api.del(token, `/equipment/${encodeId(id)}`);

export const installEquipment = (
  token: string,
  id: string,
  body: { customer?: string | null; installation_date?: string | null } = {}
) => api.post<Equipment>(token, `/equipment/${encodeId(id)}/install`, body);

/**
 * One record, by id.
 *
 * The edit pages used to fetch a page of the list and search it, which works
 * only while everything fits on one page — past that the record is absent and
 * the form waits forever for something that will never arrive.
 */
export const getEquipment = (token: string, id: string) =>
  api.get<Equipment>(token, `/equipment/${encodeId(id)}`);
