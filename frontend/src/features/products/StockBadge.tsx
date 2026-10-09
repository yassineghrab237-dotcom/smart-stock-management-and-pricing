import { type Product } from "../../api";
import { Badge } from "../../ui";
export function StockBadge({ product }: { product: Product }) {
  return product.current_stock < product.threshold_min ? (
    <Badge tone="danger">Stock bas</Badge>
  ) : product.threshold_max !== null &&
    product.current_stock > product.threshold_max ? (
    <Badge tone="warning">Surstock</Badge>
  ) : (
    <Badge tone="success">Dans les seuils</Badge>
  );
}
