import { useState, type FormEvent } from "react";
import { post, errorMessage, type Product } from "../../api";
import { Button, Field, Notice, ResourceState, useResource } from "../../ui";
import type { Contact } from "../crm/types";
export default function PurchaseForm({
  onSaved,
}: {
  onSaved: (id: number) => void;
}) {
  const products = useResource<{ items: Product[] }>("/products"),
    contacts = useResource<{ items: Contact[] }>("/crm/contacts");
  const [lines, setLines] = useState([crypto.randomUUID()]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [key, setKey] = useState(() => crypto.randomUUID());
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const result = await post<{ id: number }>("/purchases/orders", {
        reference: data.get("reference"),
        supplier_id: Number(data.get("supplier_id")),
        expected_on: data.get("expected_on"),
        note: data.get("note"),
        idempotency_key: key,
        lines: lines.map((id) => ({
          product_id: Number(data.get(`product-${id}`)),
          quantity: Number(data.get(`quantity-${id}`)),
          unit_cost_ht: data.get(`cost-${id}`),
        })),
      });
      onSaved(result.id);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} onChange={() => setKey(crypto.randomUUID())}>
      <ResourceState {...products} />
      <ResourceState {...contacts} />
      <p>
        Commande en TND, coûts HT. La confirmation reste interne : aucun message
        n’est envoyé au fournisseur. Le stock augmente lors de la réception.
      </p>
      <fieldset className="commercial-fields" disabled={busy}>
        <legend className="sr-only">Commande fournisseur</legend>
        <Field
          label="Référence de commande"
          name="reference"
          required
          maxLength={100}
        />
        <div className="field">
          <label htmlFor="purchase-supplier">Fournisseur</label>
          <select
            id="purchase-supplier"
            name="supplier_id"
            required
            defaultValue=""
          >
            <option value="">Choisir une fiche fournisseur</option>
            {contacts.data?.items
              .filter((c) => c.kind !== "CUSTOMER" && c.stage !== "INACTIVE")
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
          </select>
        </div>
        <Field
          label="Date de réception prévue"
          name="expected_on"
          type="date"
          required
        />
        <Field label="Note d’achat" name="note" maxLength={2000} />
      </fieldset>
      {lines.map((id, index) => (
        <fieldset className="commercial-line" key={id} disabled={busy}>
          <legend>Ligne {index + 1}</legend>
          <div className="commercial-fields">
            <div className="field">
              <label htmlFor={`purchase-product-${id}`}>
                Produit à commander ligne {index + 1}
              </label>
              <select
                id={`purchase-product-${id}`}
                name={`product-${id}`}
                required
                defaultValue=""
              >
                <option value="">Choisir un produit</option>
                {products.data?.items.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.sku} — {p.name}
                  </option>
                ))}
              </select>
            </div>
            <Field
              label={`Quantité commandée ligne ${index + 1}`}
              name={`quantity-${id}`}
              type="number"
              required
              min={1}
              max={2147483647}
              defaultValue={1}
            />
            <Field
              label={`Coût HT ligne ${index + 1}`}
              name={`cost-${id}`}
              required
              inputMode="decimal"
              pattern="[0-9]+([.][0-9]{1,4})?"
            />
          </div>
          {lines.length > 1 && (
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setLines((v) => v.filter((x) => x !== id));
                setKey(crypto.randomUUID());
              }}
            >
              Retirer cette ligne du brouillon
            </Button>
          )}
        </fieldset>
      ))}
      {error && <Notice>{error}</Notice>}
      <div className="commercial-actions">
        <Button
          type="button"
          variant="secondary"
          disabled={busy || lines.length >= 100}
          onClick={() => {
            setLines((v) => [...v, crypto.randomUUID()]);
            setKey(crypto.randomUUID());
          }}
        >
          Ajouter une ligne d’achat
        </Button>
        <Button
          type="submit"
          disabled={
            busy ||
            !products.data?.items.length ||
            !contacts.data ||
            !!products.error ||
            !!contacts.error
          }
        >
          {busy ? "Enregistrement…" : "Créer la commande brouillon"}
        </Button>
      </div>
    </form>
  );
}
