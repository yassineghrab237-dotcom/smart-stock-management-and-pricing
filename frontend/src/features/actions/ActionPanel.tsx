import { useRef, useState, type FormEvent } from "react";
import { post, errorMessage, date } from "../../api";
import {
  Badge,
  Button,
  Empty,
  Field,
  Notice,
  ResourceState,
  useResource,
} from "../../ui";
interface Action {
  key: string;
  title: string;
  detail: string;
  page: string;
  priority: number;
  status: string;
  decision: { id: number; reason: string } | null;
}
const status: Record<string, string> = {
  TODO: "À traiter",
  IN_PROGRESS: "En cours",
  ACKNOWLEDGED: "Pris en compte",
};
export default function ActionPanel({
  write,
  navigate,
}: {
  write: boolean;
  navigate: (page: string) => void;
}) {
  const [revision, setRevision] = useState(0);
  const r = useResource<{
    items: Action[];
    events: {
      id: number;
      status: string;
      reason: string;
      created_at: string;
      actor_name: string;
    }[];
  }>("/actions", revision);
  const refresh = () => setRevision((v) => v + 1);
  return (
    <section className="panel padded">
      <div className="collection-heading">
        <div>
          <span className="eyebrow">SUIVI COMMERCIAL</span>
          <h2>Décisions à suivre</h2>
        </div>
        <Button variant="secondary" onClick={refresh}>
          Actualiser les décisions
        </Button>
      </div>
      <p>
        La prise en compte conserve la condition visible. Une nouvelle situation
        crée un nouveau suivi.
      </p>
      <ResourceState {...r} />
      {r.data && (
        <>
          {!r.data.items.length ? (
            <Empty title="Aucune décision en attente">
              Les retards, échéances et contrôles de veille apparaîtront ici.
            </Empty>
          ) : (
            <div className="collection-list">
              {r.data.items.map((a) => (
                <article key={a.key}>
                  <div className="collection-heading">
                    <h3>{a.title}</h3>
                    <Badge tone={a.priority === 1 ? "danger" : "warning"}>
                      {status[a.status]}
                    </Badge>
                  </div>
                  <p>{a.detail}</p>
                  {a.decision && <p>Dernière décision : {a.decision.reason}</p>}
                  <Button variant="secondary" onClick={() => navigate(a.page)}>
                    Ouvrir le module concerné
                  </Button>
                  {write && (
                    <details className="collection-details">
                      <summary>Mettre à jour le suivi</summary>
                      <DecisionForm action={a} onSaved={refresh} />
                    </details>
                  )}
                </article>
              ))}
            </div>
          )}
          <details className="collection-details">
            <summary>Historique des prises en charge</summary>
            {r.data.events.map((e) => (
              <p key={e.id}>
                {date(e.created_at)} · {e.actor_name} · {status[e.status]} :{" "}
                {e.reason}
              </p>
            ))}
          </details>
        </>
      )}
    </section>
  );
}
function DecisionForm({
  action,
  onSaved,
}: {
  action: Action;
  onSaved: () => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const pending = useRef<{ payload: string; key: string } | null>(null);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    const d = new FormData(e.currentTarget);
    const body = {
      action_key: action.key,
      expected_event_id: action.decision?.id ?? 0,
      status: d.get("status"),
      reason: d.get("reason"),
    };
    const payload = JSON.stringify(body);
    if (pending.current?.payload !== payload)
      pending.current = { payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    try {
      await post("/actions/decisions", {
        ...body,
        idempotency_key: pending.current.key,
      });
      pending.current = null;
      onSaved();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <fieldset disabled={busy} className="collection-fields">
        <legend className="sr-only">Décision</legend>
        <label className="field">
          État du suivi
          <select name="status" defaultValue={action.status}>
            {Object.entries(status).map(([k, v]) => (
              <option value={k} key={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <Field
          label="Motif de prise en charge"
          name="reason"
          required
          maxLength={1000}
        />
        <Button type="submit">Enregistrer le suivi</Button>
      </fieldset>
      {error && <Notice>{error}</Notice>}
    </form>
  );
}
