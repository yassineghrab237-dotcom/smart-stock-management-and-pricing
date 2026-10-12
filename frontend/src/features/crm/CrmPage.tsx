import { useCallback, useState, type FormEvent } from "react";
import { date, errorMessage, patch, post } from "../../api";
import {
  Badge,
  Button,
  Empty,
  Field,
  Modal,
  Notice,
  ResourceState,
  useResource,
} from "../../ui";
import Opportunities from "./Opportunities";
import CustomerSales from "./CustomerSales";
import ContactForm from "./ContactForm";
import { type Contact, type ContactDetail, kinds, stages } from "./types";
import "./crm.css";
export default function CrmPage({ write }: { write: boolean }) {
  const [revision, setRevision] = useState(0),
    [selected, setSelected] = useState<number | null>(null),
    [search, setSearch] = useState("");
  const [kind, setKind] = useState("ALL"),
    [creating, setCreating] = useState(false);
  const resource = useResource<{ items: Contact[] }>("/crm/contacts", revision);
  const close = useCallback(() => setCreating(false), []);
  const items = (resource.data?.items ?? []).filter(
    (c) =>
      (kind === "ALL" || c.kind === kind || c.kind === "BOTH") &&
      `${c.name} ${c.company} ${c.email} ${c.phone}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()),
  );
  return (
    <div className="crm-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">RELATIONS COMMERCIALES</span>
          <h1>Clients et fournisseurs</h1>
          <p>Vos contacts, leurs demandes et les prochaines actions à mener.</p>
        </div>
        {write && (
          <Button onClick={() => setCreating(true)}>Nouveau contact</Button>
        )}
      </div>
      <div className="crm-filters">
        <Field
          label="Rechercher un contact"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="field">
          <label htmlFor="crm-kind-filter">Relations</label>
          <select
            id="crm-kind-filter"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            <option value="ALL">Toutes</option>
            <option value="CUSTOMER">Clients</option>
            <option value="SUPPLIER">Fournisseurs</option>
          </select>
        </div>
      </div>
      <ResourceState {...resource} />
      <div className="crm-layout">
        <section className="crm-list" aria-label="Contacts">
          {resource.data && items.length === 0 && (
            <Empty title="Aucun contact trouvé">
              Créez une fiche ou adaptez votre recherche.
            </Empty>
          )}
          {items.map((c) => (
            <button
              className={`crm-contact ${selected === c.id ? "selected" : ""}`}
              key={c.id}
              onClick={() => setSelected(c.id)}
              aria-pressed={selected === c.id}
            >
              <strong>{c.name}</strong>
              <span>{c.company || kinds[c.kind]}</span>
              <Badge>{stages[c.stage]}</Badge>
            </button>
          ))}
        </section>
        {selected ? (
          <ContactWorkspace
            key={selected}
            id={selected}
            write={write}
            onChanged={() => setRevision((v) => v + 1)}
          />
        ) : (
          <section className="crm-panel">
            <Empty title="Sélectionnez une fiche">
              Retrouvez ici ses coordonnées, ses interactions et ses tâches de
              suivi.
            </Empty>
          </section>
        )}
      </div>
      {creating && (
        <Modal title="Créer un contact" onClose={close}>
          <ContactForm
            onSaved={(c) => {
              setCreating(false);
              setSelected(c.id);
              setRevision((v) => v + 1);
            }}
          />
        </Modal>
      )}
    </div>
  );
}
function ContactWorkspace({
  id,
  write,
  onChanged,
}: {
  id: number;
  write: boolean;
  onChanged: () => void;
}) {
  const [revision, setRevision] = useState(0),
    [editing, setEditing] = useState(false),
    [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [keys] = useState<Record<string, string>>({});
  const resource = useResource<ContactDetail>(`/crm/contacts/${id}`, revision);
  const c = resource.data;
  const close = useCallback(() => setEditing(false), []);
  const refresh = () => {
    setRevision((v) => v + 1);
    onChanged();
  };
  async function taskStatus(
    task: ContactDetail["tasks"][number],
    status: string,
  ) {
    if (busy) return;
    setBusy(true);
    setError("");
    const key = `${task.id}:${task.version}:${status}`;
    keys[key] ??= crypto.randomUUID();
    try {
      await patch(`/crm/tasks/${task.id}`, {
        status,
        expected_version: task.version,
        idempotency_key: keys[key],
      });
      refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="crm-panel">
      <ResourceState {...resource} />
      {c && (
        <>
          <header className="crm-header">
            <div>
              <h2>{c.name}</h2>
              <Badge>{kinds[c.kind]}</Badge> <Badge>{stages[c.stage]}</Badge>
            </div>
            {write && (
              <Button variant="secondary" onClick={() => setEditing(true)}>
                Modifier la fiche
              </Button>
            )}
          </header>
          <dl className="crm-details">
            <dt>Entreprise</dt>
            <dd>{c.company || "Non renseignée"}</dd>
            <dt>E-mail</dt>
            <dd>{c.email || "Non renseigné"}</dd>
            <dt>Téléphone</dt>
            <dd>{c.phone || "Non renseigné"}</dd>
            <dt>Adresse</dt>
            <dd>{c.address || "Non renseignée"}</dd>
            <dt>Contact commercial</dt>
            <dd>
              {c.contact_permission === "REFUSED"
                ? "Ne pas contacter"
                : c.contact_permission === "ALLOWED"
                  ? "Autorisé"
                  : "Préférence non renseignée"}
            </dd>
            {c.kind !== "CUSTOMER" && (
              <>
                <dt>Délai indicatif</dt>
                <dd>
                  {c.lead_days ? `${c.lead_days} jours` : "Non renseigné"}
                </dd>
                <dt>Minimum indicatif</dt>
                <dd>{c.min_order} unité(s)</dd>
              </>
            )}
          </dl>
          {c.kind !== "SUPPLIER" && (
            <CustomerSales id={id} revision={revision} />
          )}
          {c.kind !== "SUPPLIER" && (
            <Opportunities
              id={id}
              revision={revision}
              write={write}
              onSaved={refresh}
            />
          )}
          <h3>Actions de suivi</h3>
          {error && <Notice>{error}</Notice>}
          {c.tasks.length === 0 && <p>Aucune tâche pour ce contact.</p>}
          {c.tasks.map((t) => (
            <div className="crm-task" key={t.id}>
              <div>
                <strong>{t.title}</strong>
                <small>
                  Échéance : {t.due_on} ·{" "}
                  {t.status === "DONE"
                    ? "Terminée"
                    : t.status === "CANCELLED"
                      ? "Annulée"
                      : "À faire"}
                </small>
              </div>
              {write && (
                <div className="crm-task-actions">
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() =>
                      taskStatus(t, t.status === "TODO" ? "DONE" : "TODO")
                    }
                  >
                    {t.status === "TODO" ? "Terminer" : "Rouvrir"}
                  </Button>
                  {t.status === "TODO" && (
                    <Button
                      variant="ghost"
                      disabled={busy}
                      onClick={() => taskStatus(t, "CANCELLED")}
                    >
                      Annuler la tâche
                    </Button>
                  )}
                </div>
              )}
            </div>
          ))}
          {write && <ActivityForm id={id} kind="tasks" onSaved={refresh} />}
          <h3>Interactions et historique</h3>
          {write && <ActivityForm id={id} kind="notes" onSaved={refresh} />}
          <ol className="crm-timeline">
            {c.events.map((e) => (
              <li key={e.id}>
                <strong>
                  {e.kind === "NOTE"
                    ? "Note"
                    : e.kind === "CREATED"
                      ? "Création"
                      : e.kind === "UPDATED"
                        ? "Modification"
                        : e.kind === "COMMERCIAL"
                          ? "Document commercial"
                          : e.kind === "PURCHASE"
                            ? "Commande fournisseur"
                            : e.kind === "RECEIPT"
                              ? "Réception"
                              : e.kind === "OPPORTUNITY"
                                ? "Opportunité"
                                : "Suivi de tâche"}
                </strong>
                <p>{eventText(e.detail)}</p>
                <small>
                  {date(e.created_at)} · {e.actor_name}
                </small>
              </li>
            ))}
          </ol>
          {editing && (
            <Modal title="Modifier le contact" onClose={close}>
              <ContactForm
                contact={c}
                onSaved={() => {
                  setEditing(false);
                  refresh();
                }}
              />
            </Modal>
          )}
        </>
      )}
    </section>
  );
}
function eventText(detail: string) {
  try {
    const value: unknown = JSON.parse(detail);
    if (
      value &&
      typeof value === "object" &&
      "motif" in value &&
      typeof value.motif === "string"
    )
      return value.motif;
  } catch {
    /* Notes are plain text. */
  }
  return detail;
}
function ActivityForm({
  id,
  kind,
  onSaved,
}: {
  id: number;
  kind: "tasks" | "notes";
  onSaved: () => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const [key, setKey] = useState(() => crypto.randomUUID());
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    const form = e.currentTarget;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await post(`/crm/contacts/${id}/${kind}`, {
        ...Object.fromEntries(new FormData(form)),
        idempotency_key: key,
      });
      form.reset();
      setKey(crypto.randomUUID());
      setMessage(kind === "tasks" ? "Tâche créée." : "Note enregistrée.");
      onSaved();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form
      className="crm-activity"
      onSubmit={submit}
      onChange={() => {
        setKey(crypto.randomUUID());
        setMessage("");
      }}
    >
      <fieldset disabled={busy} className="crm-fields">
        <legend className="sr-only">
          {kind === "tasks" ? "Nouvelle tâche" : "Nouvelle interaction"}
        </legend>
        {kind === "tasks" ? (
          <>
            <Field
              label="Action à prévoir"
              name="title"
              required
              maxLength={300}
            />
            <Field label="Échéance" name="due_on" type="date" required />
          </>
        ) : (
          <Field
            label="Note de suivi"
            name="detail"
            required
            maxLength={4000}
          />
        )}
      </fieldset>
      {error && <Notice>{error}</Notice>}
      {message && <Notice success>{message}</Notice>}
      <Button type="submit" disabled={busy} variant="secondary">
        {busy
          ? "Enregistrement…"
          : kind === "tasks"
            ? "Ajouter la tâche"
            : "Ajouter la note"}
      </Button>
    </form>
  );
}
