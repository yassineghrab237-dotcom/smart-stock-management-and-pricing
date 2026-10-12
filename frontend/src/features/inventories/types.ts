export interface InventoryLine {
  id: number;
  product_id: number;
  sku: string;
  name: string;
  expected_stock: number;
  product_version: number;
  current_product_version: number;
  current_stock: number;
  counted: number | null;
  version: number;
}
export interface Inventory {
  id: number;
  title: string;
  status: "OPEN" | "APPLIED" | "CANCELLED";
  version: number;
  created_at: string;
  line_count: number;
  lines: InventoryLine[];
  events: {
    id: number;
    detail: string;
    actor_name: string;
    created_at: string;
  }[];
}
export const statuses = {
  OPEN: "Comptage ouvert",
  APPLIED: "Écarts appliqués",
  CANCELLED: "Annulée",
};
