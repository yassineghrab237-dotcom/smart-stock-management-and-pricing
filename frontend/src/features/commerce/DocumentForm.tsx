import { useState, type FormEvent } from "react";
import { post, errorMessage, type Product } from "../../api";
import { Button, Field, Notice, ResourceState, useResource } from "../../ui";
import type { Contact } from "../crm/types";
import type { DocumentSummary } from "./types";
export default function DocumentForm({
  onSaved,
}: {
  onSaved: (d: DocumentSummary) => void;
}) {
  const products = useResource<{ items: Product[] }>("/products"),
    contacts = useResource<{ items: Contact[] }>("/crm/contacts");
  const [lines, setLines] = useState([crypto.randomUUID()]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [key, setKey] = useState(() => crypto.randomUUID());
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const result = await post<DocumentSummary>("/commerce/documents", {
        kind: data.get("kind"),
        reference: data.get("reference"),
        customer_id: data.get("customer_id")
          ? Number(data.get("customer_id"))
          : null,
        note: data.get("note"),
        idempotency_key: key,
        lines: lines.map((id) => ({
          product_id: Number(data.get(`product-${id}`)),
          quantity: Number(data.get(`quantity-${id}`)),
          unit_price_ttc: data.get(`price-${id}`),
          discount_ttc: data.get(`discount-${id}`),
          tax_rate: data.get(`tax-${id}`),
          unit_cost_ht: data.get(`cost-${id}`) || null,
        })),
      });
      onSaved(result);
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
        Les montants de ce document sont en TND. Renseignez les prix TTC et les
        coûts HT ; la taxe reste un choix explicite par ligne. Le brouillon ne
        retire aucun stock.
      </p>
      <fieldset disabled={busy} className="commercial-fields">
        <legend className="sr-only">Document commercial</legend>
        <div className="field">
          <label htmlFor="doc-kind">Document</label>
          <select id="doc-kind" name="kind">
            <option value="SALE">Vente</option>
            <option value="QUOTE">Devis</option>
          </select>
        </div>
        <Field
          label="Référence du document"
          name="reference"
          required
          maxLength={100}
        />
        <div className="field">
          <label htmlFor="doc-customer">Client</label>
          <select id="doc-customer" name="customer_id">
            <option value="">Vente sans fiche client</option>
            {contacts.data?.items
              .filter((c) => c.kind !== "SUPPLIER" && c.stage !== "INACTIVE")
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
          </select>
        </div>
        <Field label="Note du document" name="note" maxLength={2000} />
      </fieldset>
      {lines.map((id, index) => (
        <fieldset key={id} disabled={busy} className="commercial-line">
          <legend>Ligne {index + 1}</legend>
          <div className="commercial-fields">
            <div className="field">
              <label htmlFor={`product-${id}`}>Produit ligne {index + 1}</label>
              <select
                id={`product-${id}`}
                name={`product-${id}`}
                required
                defaultValue=""
              >
                <option value="">Choisir un produit</option>
                {products.data?.items.map((p) => (
                  <option value={p.id} key={p.id}>
                    {p.sku} — {p.name}
                  </option>
                ))}
              </select>
            </div>
            <Field
              label={`Quantité ligne ${index + 1}`}
              name={`quantity-${id}`}
              type="number"
              min={1}
              max={2147483647}
              defaultValue={1}
              required
            />
            <Field
              label={`Prix unitaire TTC ligne ${index + 1}`}
              name={`price-${id}`}
              required
              inputMode="decimal"
              pattern="[0-9]+([.][0-9]{1,4})?"
            />
            <Field
              label={`Remise unitaire TTC ligne ${index + 1}`}
              name={`discount-${id}`}
              required
              inputMode="decimal"
              defaultValue="0"
              pattern="[0-9]+([.][0-9]{1,4})?"
            />
            <Field
              label={`Taxe en % ligne ${index + 1}`}
              name={`tax-${id}`}
              required
              inputMode="decimal"
              pattern="[0-9]+([.][0-9]{1,4})?"
              hint="0 si exempté. Aucun taux n’est présumé."
            />
            <Field
              label={`Coût unitaire HT ligne ${index + 1}`}
              name={`cost-${id}`}
              inputMode="decimal"
              pattern="[0-9]+([.][0-9]{1,4})?"
              hint="Vide si inconnu : la contribution ne sera pas calculée."
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
          Ajouter une ligne
        </Button>
        <Button
          type="submit"
          disabled={
            busy ||
            !products.data?.items.length ||
            !!products.error ||
            !contacts.data ||
            !!contacts.error
          }
        >
          {busy ? "Enregistrement…" : "Créer le brouillon"}
        </Button>
      </div>
      {error && <Notice>{error}</Notice>}
    </form>
  );
}
