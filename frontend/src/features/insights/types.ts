export interface Totals {
  net_ttc: string;
  net_ht: string;
  known_contribution_ht: string;
  contribution_ht: string | null;
  sold_units: number;
  returned_units: number;
  net_units: number;
  known_cost_lines: number;
  line_count: number;
}
export interface SalesReport {
  start: string;
  end: string;
  as_of: string;
  sales_count: number;
  active_baskets: number;
  totals: Totals;
  products: (Totals & {
    id: number;
    sku: string;
    name: string;
    current_stock: number;
    baskets: number;
  })[];
  associations: {
    product_a: string;
    product_b: string;
    baskets: number;
    total_baskets: number;
    a_baskets: number;
    b_baskets: number;
  }[];
  sales: {
    id: number;
    reference: string;
    customer_name: string | null;
    sold_on: string;
    net_ttc: string;
  }[];
}
