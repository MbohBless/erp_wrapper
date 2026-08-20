import { type Paged, api, encodeId } from "@/lib/http";

export type Product = {
  id: string;
  name: string;
  sku: string;
  barcode: string | null;
  /** ERPNext requires an item group in practice, but the API no longer
   *  substitutes the tree root when none was chosen, so this can be null. */
  category: string | null;
  manufacturer: string | null;
  purchase_price: number | null;
  selling_price: number | null;
  track_batches?: boolean;
  unit: string;
  image: string | null;
  disabled: boolean;
};

export type ProductInput = {
  name: string;
  sku: string;
  barcode?: string | null;
  category?: string;
  manufacturer?: string | null;
  purchase_price?: number | null;
  selling_price?: number | null;
  track_batches?: boolean;
  unit?: string;
  image?: string | null;
  disabled?: boolean;
};

export const listProducts = (
  token: string,
  params: Paged & { search?: string; category?: string; disabled?: boolean } = {}
) => api.get<Product[]>(token, "/products", { limit: 200, ...params });

export const createProduct = (token: string, input: ProductInput) =>
  api.post<Product>(token, "/products", input);

export const updateProduct = (token: string, id: string, input: ProductInput) =>
  api.put<Product>(token, `/products/${encodeId(id)}`, input);

export const deleteProduct = (token: string, id: string) =>
  api.del(token, `/products/${encodeId(id)}`);

/**
 * One record, by id.
 *
 * The edit pages used to fetch a page of the list and search it, which works
 * only while everything fits on one page — past that the record is absent and
 * the form waits forever for something that will never arrive.
 */
export const getProduct = (token: string, id: string) =>
  api.get<Product>(token, `/products/${encodeId(id)}`);
