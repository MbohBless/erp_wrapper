import { type Paged, api, encodeId } from "@/lib/http";

export type MaintenanceStatus =
  | "Open"
  | "Scheduled"
  | "In Progress"
  | "Completed"
  | "Cancelled";

export type Ticket = {
  id: string;
  customer: string;
  equipment: string | null;
  engineer: string | null;
  visit_date: string | null;
  description: string | null;
  parts_used: string | null;
  status: MaintenanceStatus;
  customer_signed: boolean;
};

export type TicketInput = {
  customer: string;
  equipment?: string | null;
  engineer?: string | null;
  visit_date?: string | null;
  description?: string | null;
  parts_used?: string | null;
  status?: MaintenanceStatus;
};

export const listTickets = (
  token: string,
  params: Paged & { search?: string; status?: string } = {}
) => api.get<Ticket[]>(token, "/maintenance", { limit: 200, ...params });

export const createTicket = (token: string, input: TicketInput) =>
  api.post<Ticket>(token, "/maintenance", input);

export const updateTicket = (token: string, id: string, input: TicketInput) =>
  api.put<Ticket>(token, `/maintenance/${encodeId(id)}`, input);

export const deleteTicket = (token: string, id: string) =>
  api.del(token, `/maintenance/${encodeId(id)}`);

export const completeTicket = (
  token: string,
  id: string,
  body: { parts_used?: string | null; signed?: boolean } = {}
) => api.post<Ticket>(token, `/maintenance/${encodeId(id)}/complete`, body);

/**
 * One record, by id.
 *
 * The edit pages used to fetch a page of the list and search it, which works
 * only while everything fits on one page — past that the record is absent and
 * the form waits forever for something that will never arrive.
 */
export const getTicket = (token: string, id: string) =>
  api.get<Ticket>(token, `/maintenance/${encodeId(id)}`);
