import { useRef, useState, type FormEvent } from "react";
import { date, errorMessage, post } from "../../api";
import {
  Badge,
  Button,
  Field,
  Notice,
  ResourceState,
  useResource,
} from "../../ui";
import { type Inventory, type InventoryLine, statuses } from "./types";
export default function InventoryWorkspace({
  id,
  revision,
  write,
  onSaved,
}: {
  id: number;
  revision: number;
  write: boolean;
  onSaved: () => void;
}) {
  const resource = useResource<Inventory>(`/inventories/${id}`, revision),
    r = resource.data;
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const pending = useRef<{ payload: string; key: string } | null>(null);
  async function close(
    e: FormEvent<HTMLFormElement>,
    action: "apply" | "cancel",
  ) {
    e.preventDefault();
    if (busy || !r) return;
    const body = {
      expected_version: r.version,
      reason: String(new FormData(e.currentTarget).get("reason")),
    };
    const payload = JSON.stringify({ action, ...body });
    if (pending.current?.payload !== payload)
      pending.current = { payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await post(`/inventories/${id}/${action}`, {
        ...body,
        idempotency_key: pending.current.key,
      });
      setMessage(
        action === "apply"
          ? "Inventaire validé, écarts appliqués."
          : "Campagne annulée, stock conservé.",
      );
      onSaved();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="commercial-panel">
      <ResourceState {...resource} />
      {r && (
        <>
          <h2>{r.title}</h2>
          <Badge>{statuses[r.status]}</Badge>
          <p>
            {r.lines.filter((l) => l.counted !== null).length}/{r.lines.length}{" "}
            produits comptés. Les écarts ne sont appliqués qu’à la validation
            finale.
          </p>
          {error && (
            <Notice>
              {error}{" "}
              <Button variant="secondary" onClick={resource.reload}>
                Actualiser la campagne
              </Button>
            </Notice>
          )}
          {message && <Notice success>{message}</Notice>}
          {r.lines.map((l) => (
            <article className="commercial-item" key={l.id}>
              <h3>
                {l.sku} · {l.name}
              </h3>
              <p>
                Théorique au comptage : {l.expected_stock} · compté :{" "}
                {l.counted ?? "À renseigner"}
                {l.counted !== null &&
                  ` · écart : ${l.counted - l.expected_stock}`}
              </p>
              <p>Stock actuel : {l.current_stock}</p>
              {r.status === "OPEN" &&
                l.counted !== null &&
                l.product_version !== l.current_product_version && (
                  <Notice>
                    Produit modifié depuis le comptage. Recomptez cette
                    référence avant validation.
                  </Notice>
                )}
              {write && r.status === "OPEN" && (
                <CountForm
                  key={l.version}
                  inventoryId={id}
                  line={l}
                  disabled={busy}
                  onSaved={onSaved}
                />
              )}
            </article>
          ))}
          {write && r.status === "OPEN" && (
            <>
              <form onSubmit={(e) => close(e, "apply")}>
                <h3>Valider les écarts</h3>
                <Field
                  label="Motif de validation de l’inventaire"
                  name="reason"
                  required
                  maxLength={1000}
                  disabled={busy}
                />
                <label className="commercial-check">
                  <input type="checkbox" required disabled={busy} />
                  J’ai vérifié tous les comptages et les écarts à appliquer au
                  stock.
                </label>
                <Button
                  type="submit"
                  disabled={
                    busy ||
                    resource.loading ||
                    r.lines.some(
                      (l) =>
                        l.counted === null ||
                        l.product_version !== l.current_product_version,
                    )
                  }
                >
                  Valider et ajuster les stocks
                </Button>
              </form>
              <details className="commercial-cancel">
                <summary>Annuler cette campagne sans ajustement</summary>
                <form onSubmit={(e) => close(e, "cancel")}>
                  <Field
                    label="Motif d’annulation de campagne"
                    name="reason"
                    required
                    maxLength={1000}
                    disabled={busy}
                  />
                  <Button type="submit" variant="secondary" disabled={busy}>
                    Annuler la campagne
                  </Button>
                </form>
              </details>
            </>
          )}
          <h3>Historique de comptage</h3>
          {r.events.map((e) => (
            <p key={e.id}>
              {date(e.created_at)} · {e.actor_name} · {eventText(e.detail)}
            </p>
          ))}
        </>
      )}
    </section>
  );
}
function eventText(text: string) {
  try {
    const e: Record<string, unknown> = JSON.parse(text);
    return [
      e.action,
      e.sku,
      e.compté !== undefined ? `compté ${e.compté}` : "",
      e.motif,
    ]
      .filter((v) => typeof v === "string" && v)
      .join(" · ");
  } catch {
    return "Événement de campagne";
  }
}
function CountForm({
  inventoryId,
  line,
  disabled,
  onSaved,
}: {
  inventoryId: number;
  line: InventoryLine;
  disabled: boolean;
  onSaved: () => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const pending = useRef<{ payload: string; key: string } | null>(null);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy || disabled) return;
    const d = new FormData(e.currentTarget),
      body = {
        quantity: Number(d.get("quantity")),
        reason: String(d.get("reason")),
        expected_version: line.version,
        expected_product_version: line.current_product_version,
      };
    const payload = JSON.stringify(body);
    if (pending.current?.payload !== payload)
      pending.current = { payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    try {
      await post(`/inventories/${inventoryId}/lines/${line.id}/count`, {
        ...body,
        idempotency_key: pending.current.key,
      });
      onSaved();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <fieldset className="commercial-fields" disabled={busy || disabled}>
        <legend className="sr-only">Comptage {line.sku}</legend>
        <Field
          label={`Quantité comptée ${line.sku}`}
          name="quantity"
          required
          type="number"
          min={0}
          max={2147483647}
        />
        <Field
          label={`Motif du comptage ${line.sku}`}
          name="reason"
          required
          maxLength={1000}
        />
      </fieldset>
      {error && <Notice>{error}</Notice>}
      <Button type="submit" variant="secondary" disabled={busy || disabled}>
        Enregistrer le comptage {line.sku}
      </Button>
    </form>
  );
}
