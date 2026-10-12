import { useCallback, useRef, useState, type FormEvent } from "react";
import { errorMessage, money, patch, post } from "../../api";
import {
  Badge,
  Button,
  Field,
  Modal,
  Notice,
  ResourceState,
  useResource,
} from "../../ui";
interface Opportunity {
  id: number;
  title: string;
  stage: keyof typeof stages;
  expected_ttc: string | null;
  close_on: string;
  quote_id: number | null;
  quote_reference: string | null;
  version: number;
}
const stages = {
  NEW: "Nouveau besoin",
  QUALIFIED: "Besoin qualifié",
  PROPOSAL: "Proposition envoyée",
  WON: "Gagnée",
  LOST: "Perdue",
};
export default function Opportunities({
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
  const resource = useResource<{ items: Opportunity[] }>(
    `/crm/contacts/${id}/opportunities`,
    revision,
  );
  const [editing, setEditing] = useState<Opportunity | null | undefined>(
    undefined,
  );
  const close = useCallback(() => setEditing(undefined), []);
  return (
    <section>
      <div className="crm-header">
        <h3>Opportunités commerciales</h3>
        {write && (
          <Button variant="secondary" onClick={() => setEditing(null)}>
            Nouvelle opportunité
          </Button>
        )}
      </div>
      <p>
        Les montants potentiels ne sont pas des ventes. Seule une vente
        confirmée alimente le chiffre d’affaires et le stock.
      </p>
      <ResourceState {...resource} />
      {resource.data?.items.length === 0 && <p>Aucune opportunité suivie.</p>}
      {resource.data?.items.map((o) => (
        <article className="commercial-item" key={o.id}>
          <h4>{o.title}</h4>
          <Badge>{stages[o.stage]}</Badge>
          <p>
            Objectif : {o.close_on} · potentiel{" "}
            {o.expected_ttc === null
              ? "non renseigné"
              : `${money(o.expected_ttc)} TND TTC`}
            {o.quote_reference && ` · devis ${o.quote_reference}`}
          </p>
          {write && (
            <Button variant="secondary" onClick={() => setEditing(o)}>
              Modifier l’opportunité
            </Button>
          )}
        </article>
      ))}
      {editing !== undefined && (
        <Modal
          title={editing ? "Modifier l’opportunité" : "Créer une opportunité"}
          onClose={close}
        >
          <OpportunityForm
            contactId={id}
            value={editing}
            onSaved={() => {
              setEditing(undefined);
              onSaved();
            }}
          />
        </Modal>
      )}
    </section>
  );
}
function OpportunityForm({
  contactId,
  value,
  onSaved,
}: {
  contactId: number;
  value: Opportunity | null;
  onSaved: () => void;
}) {
  const quotes = useResource<{
    items: {
      id: number;
      reference: string;
      customer_id: number | null;
      kind: string;
      status: string;
    }[];
  }>("/commerce/documents");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const pending = useRef<{ payload: string; key: string } | null>(null);
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    const d = new FormData(e.currentTarget),
      body = {
        title: String(d.get("title")),
        stage: String(d.get("stage")),
        expected_ttc: d.get("expected_ttc") || null,
        close_on: String(d.get("close_on")),
        quote_id: d.get("quote_id") ? Number(d.get("quote_id")) : null,
        reason: String(d.get("reason")),
        ...(value ? { expected_version: value.version } : {}),
      };
    const payload = JSON.stringify(body);
    if (pending.current?.payload !== payload)
      pending.current = { payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    try {
      const data = { ...body, idempotency_key: pending.current.key };
      if (value) await patch(`/crm/opportunities/${value.id}`, data);
      else await post(`/crm/contacts/${contactId}/opportunities`, data);
      onSaved();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={save}>
      <ResourceState {...quotes} />
      <fieldset className="commercial-fields" disabled={busy}>
        <legend className="sr-only">Détails de l’opportunité</legend>
        <Field
          label="Besoin commercial"
          name="title"
          required
          maxLength={180}
          defaultValue={value?.title ?? ""}
        />
        <div className="field">
          <label htmlFor="opportunity-stage">Étape commerciale</label>
          <select
            id="opportunity-stage"
            name="stage"
            defaultValue={value?.stage ?? "NEW"}
          >
            {Object.entries(stages).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <Field
          label="Montant potentiel TND TTC"
          name="expected_ttc"
          inputMode="decimal"
          pattern="[0-9]+([.][0-9]{1,4})?"
          defaultValue={value?.expected_ttc ?? ""}
        />
        <Field
          label="Date de décision visée"
          name="close_on"
          type="date"
          required
          defaultValue={value?.close_on ?? ""}
        />
        <div className="field">
          <label htmlFor="opportunity-quote">Devis lié au client</label>
          <select
            id="opportunity-quote"
            name="quote_id"
            defaultValue={value?.quote_id ?? ""}
          >
            <option value="">Sans devis lié</option>
            {quotes.data?.items
              .filter(
                (q) =>
                  q.kind === "QUOTE" &&
                  q.customer_id === contactId &&
                  q.status !== "CANCELLED",
              )
              .map((q) => (
                <option key={q.id} value={q.id}>
                  {q.reference}
                </option>
              ))}
          </select>
        </div>
        <Field
          label="Motif ou résultat commercial"
          name="reason"
          required
          maxLength={1000}
        />
      </fieldset>
      {error && <Notice>{error}</Notice>}
      <Button type="submit" disabled={busy || !quotes.data || !!quotes.error}>
        Enregistrer l’opportunité
      </Button>
    </form>
  );
}
