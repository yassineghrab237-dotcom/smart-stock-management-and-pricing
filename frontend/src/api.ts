export interface User {
  active?: boolean;
  id: number;
  name: string;
  email: string;
  role: "ADMIN" | "MANAGER" | "VIEWER";
}
export interface Product {
  id: number;
  sku: string;
  name: string;
  category: string | null;
  unit: string | null;
  cost_price: string | null;
  current_price: string | null;
  min_price: string | null;
  threshold_min: number;
  threshold_max: number | null;
  current_stock: number;
  version: number;
  created_at: string;
  updated_at: string;
}
export interface Movement {
  id: number;
  product_id: number;
  product_name: string;
  sku: string;
  type: "IN" | "OUT" | "ADJUSTMENT";
  quantity: number;
  reason: string;
  stock_before: number;
  stock_after: number;
  created_at: string;
  actor_name: string;
}
export interface Alert {
  id: string;
  product_id: number;
  product_name: string;
  sku: string;
  type: "LOW_STOCK" | "OVERSTOCK";
  severity: string;
  message: string;
  current_stock: number;
  threshold: number;
}
export interface Dashboard {
  product_count: number;
  total_units: number;
  low_stock_count: number;
  overstock_count: number;
  recent_movements: Movement[];
}
export interface PriceEntry {
  id: number;
  old_price: string | null;
  new_price: string;
  reason: string;
  actor_name: string;
  created_at: string;
}
export interface Recommendation {
  status: "available" | "unavailable";
  method?: string;
  source?: string;
  detail?: string;
  data?: unknown;
  freshness?: unknown;
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    credentials: "same-origin",
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && !["/auth/login", "/auth/me"].includes(path))
      window.dispatchEvent(new Event("session-expired"));
    const detail =
      body && typeof body === "object" && "detail" in body ? body.detail : null;
    const message =
      typeof detail === "string"
        ? detail
        : response.status === 422
          ? "Vérifiez les champs du formulaire."
          : response.status === 403
            ? "Vous ne disposez pas des droits nécessaires."
            : response.status === 409
              ? "Les données ont changé. Actualisez la fiche avant de réessayer."
              : response.status === 401
                ? "Votre session a expiré. Connectez-vous à nouveau."
                : "Le serveur ne peut pas traiter cette demande.";
    throw new ApiError(message, response.status);
  }
  return body as T;
}
export const post = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export const patch = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
export const errorMessage = (error: unknown) =>
  error instanceof Error
    ? error instanceof TypeError
      ? "Connexion impossible. Vérifiez que le service est démarré puis réessayez."
      : error.message
    : "Une erreur est survenue.";
export const number = (value: number) =>
  new Intl.NumberFormat("fr-FR").format(value);
export const money = (value: string | null) => {
  if (value === null) return "Non renseigné";
  const [integer, fraction = ""] = value.split(".");
  const decimal = fraction.replace(/0+$/, "").padEnd(2, "0");
  return `${new Intl.NumberFormat("fr-FR").format(BigInt(integer)) === "0" && integer.startsWith("-") ? "-0" : new Intl.NumberFormat("fr-FR").format(BigInt(integer))},${decimal}`;
};
export const date = (value: string) =>
  new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
