export interface Contact {
  id: number;
  name: string;
  kind: "CUSTOMER" | "SUPPLIER" | "BOTH";
  company: string;
  email: string;
  phone: string;
  address: string;
  stage: "PROSPECT" | "ACTIVE" | "INACTIVE";
  contact_permission: "UNKNOWN" | "ALLOWED" | "REFUSED";
  lead_days: number;
  min_order: number;
  version: number;
}
export interface ContactDetail extends Contact {
  events: {
    id: number;
    kind: string;
    detail: string;
    actor_name: string;
    created_at: string;
  }[];
  tasks: {
    id: number;
    title: string;
    due_on: string;
    status: "TODO" | "DONE" | "CANCELLED";
    version: number;
  }[];
}
export const kinds = {
  CUSTOMER: "Client",
  SUPPLIER: "Fournisseur",
  BOTH: "Client et fournisseur",
};
export const stages = {
  PROSPECT: "Prospect",
  ACTIVE: "Actif",
  INACTIVE: "Inactif",
};
