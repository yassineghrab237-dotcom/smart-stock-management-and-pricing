export interface Policy {
  product_id: number;
  supplier_id: number;
  unit_cost_ht: string;
  lead_days: number;
  min_quantity: number;
  pack_size: number;
  enabled: number;
  version: number;
}
export interface PlanItem {
  id: number;
  sku: string;
  name: string;
  current_stock: number;
  threshold_min: number;
  threshold_max: number | null;
  supplier_id: number | null;
  supplier_name: string | null;
  unit_cost_ht: string | null;
  draft_units: number;
  incoming: number;
  overdue: number;
  position: number;
  needed: number;
  quantity: number;
  total_ht: string;
  reason: string;
}
export interface Plan {
  items: PlanItem[];
  total_ht: string;
  budget: string | null;
  remaining_budget: string | null;
  expected_on: string;
  fingerprint: string;
  supplier_id: number | null;
}
