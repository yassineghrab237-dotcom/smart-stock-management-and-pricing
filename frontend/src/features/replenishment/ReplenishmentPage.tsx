import { useCallback, useRef, useState, type FormEvent } from "react";
import { errorMessage, money, post } from "../../api";
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
import type { Contact } from "../crm/types";
import type { Plan } from "./types";
import PolicyForm from "./PolicyForm";
import "../commerce/commerce.css";
import "../insights/insights.css";
import "./replenishment.css";
export default function ReplenishmentPage({
  write,
  navigate,
}: {
  write: boolean;
  navigate: (page: string) => void;
}) {
  const [revision, setRevision] = useState(0),
    [query, setQuery] = useState(""),
    [policyId, setPolicyId] = useState<number | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const resource = useResource<Plan>(`/replenishment/plan${query}`, revision),
    contacts = useResource<{ items: Contact[] }>("/crm/contacts");
  const close = useCallback(() => setPolicyId(null), []);
  const pending = useRef<{ payload: string; key: string } | null>(null);
  function filter(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget),
      params = new URLSearchParams();
    if (data.get("supplier"))
      params.set("supplier_id", String(data.get("supplier")));
    if (data.get("budget")) params.set("budget", String(data.get("budget")));
    setQuery(`?${params}`);
    setRevision((v) => v + 1);
    setError("");
    setMessage("");
  }
  async function draft(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!resource.data || busy) return;
    const body = {
      supplier_id: resource.data.supplier_id,
      budget: resource.data.budget,
      expected_fingerprint: resource.data.fingerprint,
      reference: String(new FormData(e.currentTarget).get("reference")),
    };
    const payload = JSON.stringify(body);
    if (pending.current?.payload !== payload)
      pending.current = { payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await post<{ reference: string }>("/replenishment/draft", {
        ...body,
        idempotency_key: pending.current.key,
      });
      setMessage(
        `Brouillon ${result.reference} créé. Retrouvez-le dans Achats fournisseurs pour le vérifier et le confirmer.`,
      );
      setRevision((v) => v + 1);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  const r = resource.data;
  return (
    <div className="commercial-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">STOCK · FOURNISSEURS · BUDGET</span>
          <h1>Réapprovisionnement</h1>
          <p>
            Préparez les quantités à commander, sans doubler les engagements en
            cours.
          </p>
        </div>
        <Button variant="secondary" onClick={resource.reload}>
          Actualiser les propositions
        </Button>
      </div>
      <section className="commercial-panel">
        <form className="insights-filter" onSubmit={filter}>
          <div className="field">
            <label htmlFor="plan-supplier">Fournisseur à planifier</label>
            <select id="plan-supplier" name="supplier" defaultValue="">
              <option value="">Tous les fournisseurs</option>
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
            label="Enveloppe pour ces propositions TND HT"
            name="budget"
            inputMode="decimal"
            pattern="[0-9]+([.][0-9]{1,4})?"
            hint="Vide : sans plafond ; hors frais fournisseur"
          />
          <Button type="submit">Calculer la proposition</Button>
        </form>
        <ResourceState {...contacts} />
      </section>
      <ResourceState {...resource} />
      {error && <Notice>{error}</Notice>}
      {message && (
        <Notice success>
          {message}{" "}
          <Button variant="secondary" onClick={() => navigate("purchases")}>
            Ouvrir les achats
          </Button>
        </Notice>
      )}
      {r && (
        <>
          <div className="commercial-totals">
            <div>
              <small>Achats proposés HT</small>
              <strong>{money(r.total_ht)} TND</strong>
            </div>
            <div>
              <small>Enveloppe restante HT</small>
              <strong>
                {r.remaining_budget === null
                  ? "Sans plafond"
                  : `${money(r.remaining_budget)} TND`}
              </strong>
            </div>
          </div>
          <p className="commercial-footnote">
            Règle min/max, sans prévision ML : stock actuel + commandes ouvertes
            + brouillons déjà préparés. Au seuil minimum, complément vers le
            maximum, arrondi au colis et au minimum fournisseur. L’enveloppe
            privilégie les ruptures puis les écarts aux seuils ; elle ne
            constitue pas une optimisation prouvée du bénéfice. Les arrondis
            peuvent dépasser le seuil maximum.
          </p>
          {!r.items.length && (
            <Empty title="Aucun produit pour cette sélection">
              Créez vos produits et renseignez leurs conditions fournisseur.
            </Empty>
          )}
          <div className="insights-products">
            {r.items.map((p) => (
              <article className="commercial-panel" key={p.id}>
                <h2>{p.name}</h2>
                <p>
                  {p.sku} · {p.supplier_name ?? "Fournisseur à renseigner"}
                </p>
                <dl className="replenishment-details">
                  <dt>Stock disponible</dt>
                  <dd>{p.current_stock}</dd>
                  <dt>Déjà commandé à recevoir</dt>
                  <dd>{p.incoming}</dd>
                  <dt>Déjà en brouillon</dt>
                  <dd>{p.draft_units}</dd>
                  <dt>Seuils min / max</dt>
                  <dd>
                    {p.threshold_min} / {p.threshold_max ?? "Non renseigné"}
                  </dd>
                  <dt>Besoin calculé</dt>
                  <dd>{p.needed}</dd>
                  <dt>Proposé avec l’enveloppe</dt>
                  <dd>
                    <strong>{p.quantity} unité(s)</strong>
                  </dd>
                  <dt>Montant proposé HT</dt>
                  <dd>{money(p.total_ht)} TND</dd>
                </dl>
                <p>{p.reason}</p>
                {p.overdue > 0 && (
                  <Notice>
                    {p.overdue} unité(s) attendue(s) en retard : contactez le
                    fournisseur avant de commander à nouveau.
                  </Notice>
                )}
                <Badge>
                  {p.quantity ? "À préparer" : "Aucune quantité proposée"}
                </Badge>
                <div className="commercial-actions">
                  <Button variant="secondary" onClick={() => setPolicyId(p.id)}>
                    {write
                      ? "Renseigner les conditions"
                      : "Voir les conditions"}
                  </Button>
                </div>
              </article>
            ))}
          </div>
          {write &&
            r.items.some((p) => p.quantity > 0) &&
            (r.supplier_id ? (
              <section className="commercial-panel">
                <h2>Préparer le brouillon proposé</h2>
                <p>
                  Réception indicative le {r.expected_on}, calculée depuis le
                  plus long délai des lignes. Vérifiez les prix et
                  disponibilités avec le fournisseur avant confirmation.
                </p>
                <form onSubmit={draft}>
                  <Field
                    label="Référence du brouillon d’achat"
                    name="reference"
                    required
                    maxLength={100}
                    disabled={busy}
                  />
                  <label className="commercial-check">
                    <input type="checkbox" required disabled={busy} />
                    J’ai vérifié les quantités et le montant proposés.
                  </label>
                  <Button
                    type="submit"
                    disabled={busy || resource.loading || !!resource.error}
                  >
                    Créer le brouillon d’achat proposé
                  </Button>
                </form>
              </section>
            ) : (
              <Notice>
                Sélectionnez un fournisseur puis calculez sa proposition pour
                créer un brouillon d’achat.
              </Notice>
            ))}
        </>
      )}
      {policyId && (
        <Modal title="Conditions de réapprovisionnement" onClose={close}>
          <PolicyForm
            key={policyId}
            id={policyId}
            write={write}
            onSaved={() => setRevision((v) => v + 1)}
          />
        </Modal>
      )}
    </div>
  );
}
