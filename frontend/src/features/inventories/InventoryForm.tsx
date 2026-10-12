import { useRef, useState, type FormEvent } from "react";
import { post, errorMessage, type Product } from "../../api";
import { Button, Field, Notice, ResourceState, useResource } from "../../ui";
export default function InventoryForm({
  onSaved,
}: {
  onSaved: (id: number) => void;
}) {
  const products = useResource<{ items: Product[] }>("/products");
  const [selected, setSelected] = useState<number[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const pending = useRef<{ payload: string; key: string } | null>(null);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    const body = {
      title: String(new FormData(e.currentTarget).get("title")),
      product_ids: selected,
    };
    const payload = JSON.stringify(body);
    if (pending.current?.payload !== payload)
      pending.current = { payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    try {
      const r = await post<{ id: number }>("/inventories", {
        ...body,
        idempotency_key: pending.current.key,
      });
      onSaved(r.id);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <ResourceState {...products} />
      <Field
        label="Nom de la campagne"
        name="title"
        required
        maxLength={180}
        disabled={busy}
      />
      <p>
        Sélectionnez jusqu’à 500 références à compter. La création ne modifie
        pas le stock.
      </p>
      <Button
        type="button"
        variant="secondary"
        disabled={busy || !products.data || products.data.items.length > 500}
        onClick={() => setSelected(products.data?.items.map((p) => p.id) ?? [])}
      >
        Sélectionner tous les produits
      </Button>
      <fieldset className="inventory-selection" disabled={busy}>
        <legend>Produits à compter ({selected.length})</legend>
        {products.data?.items.map((p) => (
          <label key={p.id} className="commercial-check">
            <input
              type="checkbox"
              checked={selected.includes(p.id)}
              onChange={(e) =>
                setSelected((ids) =>
                  e.target.checked
                    ? [...ids, p.id]
                    : ids.filter((id) => id !== p.id),
                )
              }
            />
            {p.sku} · {p.name}
          </label>
        ))}
      </fieldset>
      {error && <Notice>{error}</Notice>}
      <Button
        type="submit"
        disabled={
          busy || !selected.length || selected.length > 500 || !!products.error
        }
      >
        Ouvrir le comptage
      </Button>
    </form>
  );
}
