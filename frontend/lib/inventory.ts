import { api, encodeId } from "@/lib/http";

// ---- Types ----
export type Warehouse = {
  id: string;
  name: string;
  parent_warehouse: string | null;
  is_group: boolean;
  disabled: boolean;
};
export type WarehouseInput = {
  name: string;
  parent_warehouse?: string | null;
  is_group?: boolean;
  disabled?: boolean;
};

export type Batch = {
  id: string;
  batch_id: string;
  item_code: string;
  expiry_date: string | null;
  manufacturing_date: string | null;
  qty: number | null;
};
export type BatchInput = {
  batch_id: string;
  item_code: string;
  expiry_date?: string | null;
  manufacturing_date?: string | null;
};

export type StockLevel = {
  item_code: string;
  warehouse: string;
  actual_qty: number;
  reserved_qty: number | null;
  projected_qty: number | null;
};

export type MovementLine = {
  item_code: string;
  qty: number;
  batch_no?: string | null;
  rate?: number | null;
};
export type MovementInput = { warehouse: string; items: MovementLine[] };

export type StockEntry = {
  id: string;
  stock_entry_type: string;
  items: {
    item_code: string;
    qty: number;
    warehouse: string | null;
    batch_no: string | null;
  }[];
};

// ---- Warehouses ----
export const listWarehouses = (token: string) =>
  api.get<Warehouse[]>(token, "/inventory/warehouses", { limit: 200 });

export const createWarehouse = (token: string, input: WarehouseInput) =>
  api.post<Warehouse>(token, "/inventory/warehouses", input);

export const updateWarehouse = (token: string, id: string, input: WarehouseInput) =>
  api.put<Warehouse>(token, `/inventory/warehouses/${encodeId(id)}`, input);

export const deleteWarehouse = (token: string, id: string) =>
  api.del(token, `/inventory/warehouses/${encodeId(id)}`);

// ---- Batches ----
export const listBatches = (token: string) =>
  api.get<Batch[]>(token, "/inventory/batches", { limit: 200 });

export const createBatch = (token: string, input: BatchInput) =>
  api.post<Batch>(token, "/inventory/batches", input);

// ---- Stock ----
export const listStock = (
  token: string,
  params: { item_code?: string; warehouse?: string } = {}
) => api.get<StockLevel[]>(token, "/inventory/stock", { ...params, limit: 500 });

// ---- Goods movements ----
export const receiveGoods = (token: string, input: MovementInput) =>
  api.post<StockEntry>(token, "/inventory/receive", input);

export const issueGoods = (token: string, input: MovementInput) =>
  api.post<StockEntry>(token, "/inventory/issue", input);
