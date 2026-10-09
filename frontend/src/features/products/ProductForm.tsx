import { useState, type FormEvent } from "react";
import { post, patch, errorMessage, type Product } from "../../api";
import { Button, Field, Notice } from "../../ui";
export function ProductForm({
  product,
  onSuccess,
}: {
  product?: Product;
  onSuccess: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    const form = new FormData(e.currentTarget);
    const body: Record<string, unknown> = {};
    for (const [key, value] of form) {
      if (key === "threshold_min") body[key] = Number(value);
      else if (key === "threshold_max")
        body[key] = value === "" ? null : Number(value);
      else body[key] = value === "" ? null : value;
    }
    if (product) body.expected_version = product.version;
    try {
      if (product) await patch(`/products/${product.id}`, body);
      else await post("/products", body);
      onSuccess();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <div className="form-grid">
        <Field
          label="Nom du produit"
          name="name"
          required
          maxLength={180}
          defaultValue={product?.name}
        />
        <Field
          label="Référence / SKU"
          name="sku"
          required
          maxLength={80}
          defaultValue={product?.sku}
        />
        <Field
          label="Catégorie (facultatif)"
          name="category"
          maxLength={100}
          defaultValue={product?.category ?? ""}
        />
        <Field
          label="Unité (facultatif)"
          name="unit"
          maxLength={40}
          defaultValue={product?.unit ?? ""}
        />
        <Field
          label="Seuil minimum"
          name="threshold_min"
          type="number"
          min="0"
          step="1"
          required
          defaultValue={product?.threshold_min ?? 0}
        />
        <Field
          label="Seuil maximum (facultatif)"
          name="threshold_max"
          type="number"
          min="0"
          step="1"
          defaultValue={product?.threshold_max ?? ""}
        />
        {!product && (
          <>
            <Field
              label="Coût unitaire (facultatif)"
              name="cost_price"
              type="number"
              min="0"
              step="0.0001"
            />
            <Field
              label="Prix actuel (facultatif)"
              name="current_price"
              type="number"
              min="0"
              step="0.0001"
            />
            <Field
              label="Prix minimum (facultatif)"
              name="min_price"
              type="number"
              min="0"
              step="0.0001"
            />
          </>
        )}
      </div>
      <p className="form-note">
        Le stock est modifié uniquement par un mouvement traçable. Les montants
        n'impliquent aucune devise ou taxe.
      </p>
      {error && <Notice>{error}</Notice>}
      <div className="form-actions">
        <Button type="submit" disabled={busy}>
          {busy
            ? "Enregistrement…"
            : product
              ? "Enregistrer les informations"
              : "Créer le produit"}
        </Button>
      </div>
    </form>
  );
}
