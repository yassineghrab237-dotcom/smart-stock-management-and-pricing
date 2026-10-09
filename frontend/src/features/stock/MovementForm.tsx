import { useState, type FormEvent } from "react";
import { ArrowDownLeft, ArrowUpRight, SlidersHorizontal } from "lucide-react";
import {
  api,
  post,
  errorMessage,
  number,
  type Product,
  type Movement,
} from "../../api";
import { Button, Field, Notice } from "../../ui";
export function MovementForm({
  products,
  initialId,
  onSuccess,
}: {
  products: Product[];
  initialId?: number;
  onSuccess: () => void;
}) {
  const [id, setId] = useState(String(initialId ?? products[0]?.id ?? ""));
  const [type, setType] = useState<Movement["type"]>("IN");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [freshProduct, setFreshProduct] = useState<Product | null>(null);
  const product =
    freshProduct && String(freshProduct.id) === id
      ? freshProduct
      : products.find((p) => String(p.id) === id);
  const qty = Number(quantity);
  const after = product
    ? type === "IN"
      ? product.current_stock + qty
      : type === "OUT"
        ? product.current_stock - qty
        : qty
    : 0;
  function edit(action: () => void) {
    action();
    setConfirm(false);
    setKey(crypto.randomUUID());
    setError("");
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || !product) return;
    if (!confirm) {
      setConfirm(true);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await post("/movements", {
        product_id: product.id,
        type,
        quantity: qty,
        reason,
        idempotency_key: key,
        expected_version: product.version,
      });
      onSuccess();
    } catch (err) {
      setError(
        err instanceof TypeError
          ? `${errorMessage(err)} L’opération a peut-être été enregistrée. Réessayez sans modifier la saisie ou consultez l’historique.`
          : errorMessage(err),
      );
      if (err instanceof Error && "status" in err && err.status === 409) {
        try {
          const fresh = await api<Product>(`/products/${product.id}`);
          setFreshProduct(fresh);
          setConfirm(false);
          setKey(crypto.randomUUID());
        } catch {
          /* Original conflict remains visible. */
        }
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <label className="field">
        <span>Produit</span>
        <select
          required
          value={id}
          onChange={(e) => edit(() => setId(e.target.value))}
        >
          {products.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} · {p.sku}
            </option>
          ))}
        </select>
      </label>
      <div className="operation-types">
        {(
          [
            { value: "IN", label: "Entrée", icon: ArrowDownLeft },
            { value: "OUT", label: "Sortie", icon: ArrowUpRight },
            {
              value: "ADJUSTMENT",
              label: "Ajustement",
              icon: SlidersHorizontal,
            },
          ] as const
        ).map((t) => (
          <button
            type="button"
            key={t.value}
            className={type === t.value ? "selected" : ""}
            aria-pressed={type === t.value}
            onClick={() => edit(() => setType(t.value))}
          >
            <t.icon size={20} />
            {t.label}
          </button>
        ))}
      </div>
      <Field
        label={
          type === "ADJUSTMENT" ? "Stock cible après ajustement" : "Quantité"
        }
        type="number"
        min={type === "ADJUSTMENT" ? 0 : 1}
        step="1"
        required
        value={quantity}
        onChange={(e) => edit(() => setQuantity(e.target.value))}
      />
      <Field
        label="Motif de l’opération"
        required
        minLength={1}
        maxLength={500}
        value={reason}
        onChange={(e) => edit(() => setReason(e.target.value))}
        placeholder="Ex. Réception fournisseur, inventaire…"
      />
      {product && (
        <div className="stock-preview">
          <span>
            Stock actuel <b>{number(product.current_stock)}</b>
          </span>
          <span aria-hidden="true">→</span>
          <span>
            Stock après opération <b>{quantity !== "" ? number(after) : "—"}</b>
          </span>
        </div>
      )}
      {after < 0 && (
        <Notice>
          Cette sortie dépasse le stock disponible. Réduisez la quantité.
        </Notice>
      )}
      {confirm && (
        <Notice success>
          Vérifiez le produit, le motif et le stock final avant confirmation.{" "}
          {type === "ADJUSTMENT" &&
            "L’ajustement remplace le stock courant par la quantité cible et sera historisé."}
        </Notice>
      )}
      {error && <Notice>{error}</Notice>}
      <div className="form-actions">
        <Button type="submit" disabled={busy || after < 0 || !product}>
          {busy
            ? "Enregistrement…"
            : confirm
              ? "Confirmer le mouvement"
              : "Vérifier le mouvement"}
        </Button>
        {confirm && (
          <Button
            variant="secondary"
            type="button"
            disabled={busy}
            onClick={() => setConfirm(false)}
          >
            Modifier
          </Button>
        )}
      </div>
    </form>
  );
}
