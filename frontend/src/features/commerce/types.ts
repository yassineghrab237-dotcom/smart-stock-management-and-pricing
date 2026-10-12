import type { Product } from "../../api";
export interface DocumentSummary {
  id: number;
  reference: string;
  kind: "SALE" | "QUOTE";
  status: "DRAFT" | "CONFIRMED" | "CONVERTED" | "CANCELLED";
  customer_name: string | null;
  version: number;
  created_at: string;
}
export interface CommercialLine {
  id: number;
  product_id: number;
  sku: string;
  name: string;
  quantity: number;
  returned: number;
  unit_price_ttc: string;
  discount_ttc: string;
  tax_rate: string;
  unit_cost_ht: string | null;
  total_ttc: string;
  total_ht: string;
  contribution_ht: string | null;
  net: { total_ttc: string; contribution_ht: string | null };
}
export interface Document extends DocumentSummary {
  sold_on: string | null;
  note: string;
  lines: CommercialLine[];
  products: Product[];
  totals: {
    total_ttc: string;
    total_ht: string;
    tax: string;
    contribution_ht: string | null;
  };
  net_total_ttc: string;
  returns: {
    id: number;
    line_id: number;
    quantity: number;
    restock: boolean;
    reason: string;
    created_at: string;
  }[];
}
export const statuses = {
  DRAFT: "Brouillon",
  CONFIRMED: "Vente confirmée",
  CONVERTED: "Devis converti",
  CANCELLED: "Annulé",
};
