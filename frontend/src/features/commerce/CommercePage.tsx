import { useCallback, useRef, useState, type FormEvent } from "react";
import { post, money, date, errorMessage } from "../../api";
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
import DocumentForm from "./DocumentForm";
import { type Document, type DocumentSummary, statuses } from "./types";
import PrintableDocument from "./PrintableDocument";
import "./commerce.css";
export default function CommercePage({
  write,
  refresh,
}: {
  write: boolean;
  refresh: () => void;
}) {
  const [revision, setRevision] = useState(0),
    [selected, setSelected] = useState<number | null>(null),
    [creating, setCreating] = useState(false),
    [search, setSearch] = useState("");
  const resource = useResource<{ items: DocumentSummary[] }>(
    "/commerce/documents",
    revision,
  );
  const close = useCallback(() => setCreating(false), []);
  const saved = (id: number) => {
    setSelected(id);
    setRevision((v) => v + 1);
    refresh();
  };
  return (
    <div className="commercial-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">VENTES · DEVIS · RETOURS</span>
          <h1>Activité commerciale</h1>
          <p>
            Des paniers traçables, des montants explicites et un stock mis à
            jour à la confirmation.
          </p>
        </div>
        {write && (
          <Button onClick={() => setCreating(true)}>Nouveau document</Button>
        )}
      </div>
      <Field
        label="Rechercher un document"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <ResourceState {...resource} />
      <div className="commercial-layout">
        <section className="commercial-list" aria-label="Documents commerciaux">
          {resource.data?.items
            .filter((d) =>
              `${d.reference} ${d.customer_name ?? ""}`
                .toLowerCase()
                .includes(search.toLowerCase()),
            )
            .map((d) => (
              <button
                className={`commercial-document ${selected === d.id ? "selected" : ""}`}
                key={d.id}
                onClick={() => setSelected(d.id)}
                aria-pressed={selected === d.id}
              >
                <strong>{d.reference}</strong>
                <span>
                  {d.kind === "QUOTE" ? "Devis" : "Vente"} ·{" "}
                  {d.customer_name ?? "Sans fiche client"}
                </span>
                <Badge>{statuses[d.status]}</Badge>
              </button>
            ))}
          {resource.data?.items.length === 0 && (
            <Empty title="Aucun document">
              Créez votre premier devis ou brouillon de vente.
            </Empty>
          )}
        </section>
        {selected ? (
          <DocumentWorkspace
            key={selected}
            id={selected}
            revision={revision}
            write={write}
            onSaved={saved}
          />
        ) : (
          <section className="commercial-panel">
            <Empty title="Sélectionnez un document">
              Vérifiez les lignes, confirmez une vente ou enregistrez un retour.
            </Empty>
          </section>
        )}
      </div>
      {creating && (
        <Modal title="Créer un document commercial" onClose={close}>
          <DocumentForm
            onSaved={(d) => {
              setCreating(false);
              saved(d.id);
            }}
          />
        </Modal>
      )}
    </div>
  );
}
function DocumentWorkspace({
  id,
  revision,
  write,
  onSaved,
}: {
  id: number;
  revision: number;
  write: boolean;
  onSaved: (id: number) => void;
}) {
  const resource = useResource<Document>(`/commerce/documents/${id}`, revision);
  const d = resource.data;
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const pending = useRef<{ payload: string; key: string } | null>(null);
  async function mutate(path: string, body: Record<string, unknown>) {
    if (busy) return false;
    const payload = JSON.stringify({ path, ...body });
    if (pending.current?.payload !== payload)
      pending.current = { payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await post<Document>(path, {
        ...body,
        idempotency_key: pending.current.key,
      });
      setMessage("Opération enregistrée.");
      onSaved(result.id);
      return true;
    } catch (e) {
      setError(errorMessage(e));
      return false;
    } finally {
      setBusy(false);
    }
  }
  function confirm(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!d) return;
    const data = new FormData(e.currentTarget);
    void mutate(`/commerce/documents/${id}/confirm`, {
      expected_version: d.version,
      product_versions: Object.fromEntries(
        d.products.map((p) => [String(p.id), p.version]),
      ),
      sale_reference: data.get("sale_reference") || null,
    });
  }
  function cancel(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!d) return;
    void mutate(`/commerce/documents/${id}/cancel`, {
      expected_version: d.version,
      reason: new FormData(e.currentTarget).get("reason"),
    });
  }
  async function returned(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!d) return;
    const form = e.currentTarget;
    const data = new FormData(form),
      line = d.lines.find((l) => l.id === Number(data.get("line_id")));
    if (!line) return;
    const product = d.products.find((p) => p.id === line.product_id);
    if (
      await mutate(`/commerce/lines/${line.id}/returns`, {
        quantity: Number(data.get("quantity")),
        restock: data.get("restock") === "yes",
        reason: data.get("reason"),
        expected_product_version: product?.version,
      })
    )
      form.reset();
  }
  return (
    <section className="commercial-panel">
      <ResourceState {...resource} />
      {d && (
        <>
          <PrintableDocument document={d} />
          <Button
            variant="secondary"
            disabled={resource.loading || !!resource.error}
            onClick={() => window.print()}
          >
            Imprimer le document
          </Button>
          <header>
            <h2>{d.reference}</h2>
            <Badge>{statuses[d.status]}</Badge>
            <p>
              {d.customer_name ?? "Sans fiche client"} · Enregistré le{" "}
              {date(d.created_at)}
              {d.sold_on && <> · Vente du {d.sold_on}</>}
            </p>
          </header>
          <div className="commercial-totals">
            <div>
              <small>Total TTC</small>
              <strong>{money(d.totals.total_ttc)} TND</strong>
            </div>
            <div>
              <small>Total HT</small>
              <strong>{money(d.totals.total_ht)} TND</strong>
            </div>
            <div>
              <small>Taxe</small>
              <strong>{money(d.totals.tax)} TND</strong>
            </div>
            <div>
              <small>Contribution HT avant frais et retours</small>
              <strong>
                {d.totals.contribution_ht === null
                  ? "Coûts incomplets"
                  : `${money(d.totals.contribution_ht)} TND`}
              </strong>
            </div>
          </div>
          <p>{d.note}</p>
          {d.lines.map((l) => (
            <article className="commercial-item" key={l.id}>
              <h3>
                {l.sku} · {l.name}
              </h3>
              <p>
                {l.quantity} unité(s) à {money(l.unit_price_ttc)} TND TTC ·
                remise unitaire {money(l.discount_ttc)} · taxe{" "}
                {money(l.tax_rate)} %
              </p>
              <strong>Total : {money(l.total_ttc)} TND TTC</strong>
              {l.returned > 0 && (
                <p>
                  {l.returned} unité(s) retournée(s) · net{" "}
                  {money(l.net.total_ttc)} TND TTC · contribution nette avant
                  frais :{" "}
                  {l.net.contribution_ht === null
                    ? "inconnue"
                    : `${money(l.net.contribution_ht)} TND`}
                </p>
              )}
            </article>
          ))}
          {error && (
            <Notice>
              {error}{" "}
              <Button variant="secondary" onClick={resource.reload}>
                Actualiser le document
              </Button>
            </Notice>
          )}
          {message && <Notice success>{message}</Notice>}
          {write && d.status === "DRAFT" && (
            <>
              <form onSubmit={confirm}>
                <fieldset disabled={busy} className="commercial-fields">
                  <legend>Confirmation</legend>
                  {d.kind === "QUOTE" && (
                    <Field
                      label="Référence de la vente issue du devis"
                      name="sale_reference"
                      required
                      maxLength={100}
                    />
                  )}
                  <label className="commercial-check">
                    <input type="checkbox" required /> J’ai vérifié les montants
                    et je confirme la sortie du stock pour cette vente.
                  </label>
                </fieldset>
                <Button disabled={busy} type="submit">
                  {d.kind === "QUOTE"
                    ? "Convertir en vente et retirer le stock"
                    : "Confirmer la vente et retirer le stock"}
                </Button>
              </form>
              <details className="commercial-cancel">
                <summary>Annuler ce brouillon</summary>
                <form onSubmit={cancel}>
                  <Field
                    label="Motif d’annulation"
                    name="reason"
                    required
                    maxLength={1000}
                  />
                  <Button variant="secondary" type="submit" disabled={busy}>
                    Confirmer l’annulation
                  </Button>
                </form>
              </details>
            </>
          )}
          {write &&
            d.status === "CONFIRMED" &&
            d.lines.some((l) => l.returned < l.quantity) && (
              <form onSubmit={returned}>
                <h3>Enregistrer un retour</h3>
                <fieldset disabled={busy} className="commercial-fields">
                  <legend className="sr-only">Retour de vente</legend>
                  <div className="field">
                    <label htmlFor="return-line">Ligne retournée</label>
                    <select id="return-line" name="line_id" required>
                      {d.lines
                        .filter((l) => l.returned < l.quantity)
                        .map((l) => (
                          <option key={l.id} value={l.id}>
                            {l.sku} — reste {l.quantity - l.returned}
                          </option>
                        ))}
                    </select>
                  </div>
                  <Field
                    label="Quantité retournée"
                    name="quantity"
                    type="number"
                    min={1}
                    required
                  />
                  <div className="field">
                    <label htmlFor="return-restock">
                      État du produit retourné
                    </label>
                    <select
                      id="return-restock"
                      name="restock"
                      required
                      defaultValue=""
                    >
                      <option value="">Choisir</option>
                      <option value="yes">
                        Revendable : remettre en stock
                      </option>
                      <option value="no">
                        Non revendable : conserver la perte de coût
                      </option>
                    </select>
                  </div>
                  <Field
                    label="Motif du retour"
                    name="reason"
                    required
                    maxLength={1000}
                  />
                </fieldset>
                <Button disabled={busy} type="submit">
                  Confirmer le retour
                </Button>
              </form>
            )}
          {d.returns.length > 0 && (
            <section>
              <h3>Historique des retours</h3>
              <p>
                Ventes nettes après retours : {money(d.net_total_ttc)} TND TTC
              </p>
              {d.returns.map((r) => (
                <p key={r.id}>
                  {date(r.created_at)} · {r.quantity} unité(s) ·{" "}
                  {r.restock ? "remise en stock" : "non revendable"} ·{" "}
                  {r.reason}
                </p>
              ))}
            </section>
          )}
          <p className="commercial-footnote">
            Document de gestion interne en TND. Les taxes sont celles saisies
            par l’utilisateur. La contribution affichée ne comprend pas les
            frais de paiement, de livraison ou de structure.
          </p>
        </>
      )}
    </section>
  );
}
