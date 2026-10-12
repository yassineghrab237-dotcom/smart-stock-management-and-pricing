import { useRef, useState, type FormEvent } from "react";
import { date, errorMessage, post } from "../../api";
import { Button, Field, Notice, ResourceState, useResource } from "../../ui";
import type { Contact } from "../crm/types";
import type { Policy } from "./types";
export default function PolicyForm({
  id,
  write,
  onSaved,
}: {
  id: number;
  write: boolean;
  onSaved: () => void;
}) {
  const [revision, setRevision] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const resource = useResource<{
    policy: Policy | null;
    events: {
      id: number;
      detail: string;
      actor_name: string;
      created_at: string;
    }[];
  }>(`/replenishment/policies/${id}`, revision);
  const contacts = useResource<{ items: Contact[] }>("/crm/contacts");
  const pending = useRef<{ payload: string; key: string } | null>(null);
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy || !resource.data) return;
    const data = new FormData(e.currentTarget);
    const body = {
      supplier_id: Number(data.get("supplier_id")),
      unit_cost_ht: String(data.get("unit_cost_ht")),
      lead_days: Number(data.get("lead_days")),
      min_quantity: Number(data.get("min_quantity")),
      pack_size: Number(data.get("pack_size")),
      enabled: data.get("enabled") === "on",
      expected_version: resource.data.policy?.version ?? 0,
      reason: String(data.get("reason")),
    };
    const payload = JSON.stringify(body);
    if (pending.current?.payload !== payload)
      pending.current = { payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await post(`/replenishment/policies/${id}`, {
        ...body,
        idempotency_key: pending.current.key,
      });
      setRevision((v) => v + 1);
      setMessage("Conditions enregistrées.");
      onSaved();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  const p = resource.data?.policy;
  return (
    <>
      <ResourceState {...resource} />
      <ResourceState {...contacts} />
      {resource.data && (
        <form onSubmit={save}>
          <p>
            Renseignez les conditions de cette référence en TND HT. Les anciens
            coûts du catalogue ne sont pas convertis. Les seuils min/max se
            règlent dans Produits et stock.
          </p>
          <fieldset
            key={p?.version ?? 0}
            className="commercial-fields"
            disabled={busy || !write}
          >
            <legend className="sr-only">
              Conditions fournisseur par produit
            </legend>
            <div className="field">
              <label htmlFor="policy-supplier">
                Fournisseur de réapprovisionnement
              </label>
              <select
                id="policy-supplier"
                name="supplier_id"
                required
                defaultValue={p?.supplier_id ?? ""}
              >
                <option value="">Choisir un fournisseur</option>
                {contacts.data?.items
                  .filter(
                    (c) => c.kind !== "CUSTOMER" && c.stage !== "INACTIVE",
                  )
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
              </select>
            </div>
            <Field
              label="Coût fournisseur TND HT"
              name="unit_cost_ht"
              inputMode="decimal"
              required
              pattern="[0-9]+([.][0-9]{1,4})?"
              defaultValue={p?.unit_cost_ht ?? ""}
            />
            <Field
              label="Délai en jours"
              name="lead_days"
              type="number"
              min={1}
              max={365}
              required
              defaultValue={p?.lead_days ?? ""}
            />
            <Field
              label="Minimum par commande de ce produit"
              name="min_quantity"
              type="number"
              min={1}
              max={1000000}
              required
              defaultValue={p?.min_quantity ?? 1}
            />
            <Field
              label="Unités par colis"
              name="pack_size"
              type="number"
              min={1}
              max={1000000}
              required
              defaultValue={p?.pack_size ?? 1}
            />
            <label className="commercial-check">
              <input
                type="checkbox"
                name="enabled"
                defaultChecked={p ? !!p.enabled : true}
              />
              Propositions actives pour ce produit
            </label>
            {write && (
              <Field
                label="Motif des conditions"
                name="reason"
                required
                maxLength={1000}
              />
            )}
          </fieldset>
          {error && (
            <Notice>
              {error}{" "}
              <Button variant="secondary" onClick={resource.reload}>
                Actualiser les conditions
              </Button>
            </Notice>
          )}
          {message && <Notice success>{message}</Notice>}
          {write && (
            <Button
              type="submit"
              disabled={busy || !contacts.data || !!contacts.error}
            >
              Enregistrer les conditions
            </Button>
          )}
        </form>
      )}
      {resource.data && (
        <details className="commercial-cancel">
          <summary>Historique des conditions</summary>
          {resource.data.events.length ? (
            resource.data.events.map((e) => (
              <article className="commercial-item" key={e.id}>
                <p>
                  {date(e.created_at)} · {e.actor_name}
                </p>
                <pre className="policy-history">{historyReason(e.detail)}</pre>
              </article>
            ))
          ) : (
            <p>Aucune condition enregistrée.</p>
          )}
        </details>
      )}
    </>
  );
}

function historyReason(text: string) {
  try {
    const v: unknown = JSON.parse(text);
    return v &&
      typeof v === "object" &&
      "reason" in v &&
      typeof v.reason === "string"
      ? v.reason
      : "Conditions modifiées";
  } catch {
    return "Conditions modifiées";
  }
}
