import { useCallback, useRef, useState, type FormEvent } from "react";
import { post, money, date, errorMessage, type Product } from "../../api";
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
import PurchaseForm from "./PurchaseForm";
import "../commerce/commerce.css";
interface Order {
  id: number;
  reference: string;
  supplier_name: string;
  status: keyof typeof statuses;
  expected_on: string;
  note: string;
  version: number;
  total_ht: string;
  remaining_ht: string;
  products: Product[];
  lines: {
    id: number;
    product_id: number;
    sku: string;
    name: string;
    quantity: number;
    received: number;
    unit_cost_ht: string;
  }[];
  receipts: {
    id: number;
    sku: string;
    quantity: number;
    reason: string;
    created_at: string;
  }[];
}
const statuses = {
  DRAFT: "Brouillon",
  ORDERED: "À réceptionner",
  PART_RECEIVED: "Réception partielle",
  RECEIVED: "Réception complète",
  CANCELLED: "Annulée",
  CLOSED: "Solde clôturé",
};
export default function PurchasesPage({
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
  const resource = useResource<{ items: Order[] }>(
    "/purchases/orders",
    revision,
  );
  const close = useCallback(() => setCreating(false), []);
  const saved = (id: number) => {
    setCreating(false);
    setSelected(id);
    setRevision((v) => v + 1);
    refresh();
  };
  return (
    <div className="commercial-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">COMMANDES · RÉCEPTIONS</span>
          <h1>Achats fournisseurs</h1>
          <p>
            Suivez les engagements et recevez les quantités réellement livrées.
          </p>
        </div>
        {write && (
          <Button onClick={() => setCreating(true)}>
            Nouvelle commande fournisseur
          </Button>
        )}
      </div>
      <Field
        label="Rechercher une commande"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <ResourceState {...resource} />
      <div className="commercial-layout">
        <section
          className="commercial-list"
          aria-label="Commandes fournisseurs"
        >
          {resource.data?.items
            .filter((o) =>
              `${o.reference} ${o.supplier_name}`
                .toLowerCase()
                .includes(search.toLowerCase()),
            )
            .map((o) => (
              <button
                key={o.id}
                className={`commercial-document ${selected === o.id ? "selected" : ""}`}
                aria-pressed={selected === o.id}
                onClick={() => setSelected(o.id)}
              >
                <strong>{o.reference}</strong>
                <span>{o.supplier_name}</span>
                <Badge>{statuses[o.status]}</Badge>
                <small>Prévue le {o.expected_on}</small>
              </button>
            ))}
          {resource.data?.items.length === 0 && (
            <Empty title="Aucune commande fournisseur">
              Créez une fiche fournisseur dans le CRM, puis préparez votre
              commande.
            </Empty>
          )}
        </section>
        {selected ? (
          <OrderWorkspace
            key={selected}
            id={selected}
            revision={revision}
            write={write}
            onSaved={saved}
          />
        ) : (
          <section className="commercial-panel">
            <Empty title="Sélectionnez une commande">
              Consultez les quantités attendues et l’historique des réceptions.
            </Empty>
          </section>
        )}
      </div>
      {creating && (
        <Modal title="Préparer une commande fournisseur" onClose={close}>
          <PurchaseForm onSaved={saved} />
        </Modal>
      )}
    </div>
  );
}
function OrderWorkspace({
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
  const resource = useResource<Order>(`/purchases/orders/${id}`, revision);
  const o = resource.data;
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const pending = useRef<{ payload: string; key: string } | null>(null);
  async function mutate(action: string, body: Record<string, unknown>) {
    if (busy) return false;
    const payload = JSON.stringify({ action, ...body });
    if (pending.current?.payload !== payload)
      pending.current = { payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await post(`/purchases/orders/${id}/${action}`, {
        ...body,
        idempotency_key: pending.current.key,
      });
      onSaved(id);
      setMessage("Opération enregistrée.");
      return true;
    } catch (e) {
      setError(errorMessage(e));
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function receive(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!o) return;
    const form = e.currentTarget,
      data = new FormData(form);
    const lines = o.lines
      .map((l) => ({
        line_id: l.id,
        quantity: Number(data.get(`receive-${l.id}`) || 0),
        expected_product_version: o.products.find((p) => p.id === l.product_id)
          ?.version,
      }))
      .filter((l) => l.quantity > 0);
    if (!lines.length) {
      setError("Renseignez au moins une quantité reçue.");
      return;
    }
    if (
      await mutate("receive", {
        lines,
        reason: data.get("reason"),
        expected_version: o.version,
      })
    )
      form.reset();
  }
  return (
    <section className="commercial-panel">
      <ResourceState {...resource} />
      {o && (
        <>
          <h2>{o.reference}</h2>
          <Badge>{statuses[o.status]}</Badge>
          <p>
            {o.supplier_name} · Réception prévue le {o.expected_on}
          </p>
          <div className="commercial-totals">
            <div>
              <small>Total commandé HT</small>
              <strong>{money(o.total_ht)} TND</strong>
            </div>
            <div>
              <small>
                {o.status === "CLOSED" || o.status === "CANCELLED"
                  ? "Montant non reçu et annulé HT"
                  : "Montant restant à recevoir HT"}
              </small>
              <strong>{money(o.remaining_ht)} TND</strong>
            </div>
          </div>
          <p>{o.note}</p>
          {o.lines.map((l) => (
            <article className="commercial-item" key={l.id}>
              <h3>
                {l.sku} · {l.name}
              </h3>
              <p>
                {l.received} reçue(s) / {l.quantity} commandée(s) · coût
                unitaire {money(l.unit_cost_ht)} TND HT
              </p>
            </article>
          ))}
          {error && (
            <Notice>
              {error}{" "}
              <Button variant="secondary" onClick={resource.reload}>
                Actualiser la commande
              </Button>
            </Notice>
          )}
          {message && <Notice success>{message}</Notice>}
          {write && o.status === "DRAFT" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void mutate("confirm", { expected_version: o.version });
              }}
            >
              <label className="commercial-check">
                <input type="checkbox" required /> Je confirme cette commande
                dans Precios. L’envoi au fournisseur reste à effectuer
                séparément.
              </label>
              <Button disabled={busy} type="submit">
                Confirmer la commande
              </Button>
            </form>
          )}
          {write && ["ORDERED", "PART_RECEIVED"].includes(o.status) && (
            <form onSubmit={receive}>
              <h3>Réceptionner la livraison</h3>
              <fieldset className="commercial-fields" disabled={busy}>
                <legend className="sr-only">
                  Quantités effectivement reçues
                </legend>
                {o.lines
                  .filter((l) => l.quantity > l.received)
                  .map((l) => (
                    <Field
                      key={l.id}
                      label={`Quantité reçue ${l.sku}`}
                      name={`receive-${l.id}`}
                      type="number"
                      min={0}
                      max={l.quantity - l.received}
                      defaultValue={0}
                      hint={`Restant : ${l.quantity - l.received}`}
                    />
                  ))}
                <Field
                  label="Référence du bon ou motif de réception"
                  name="reason"
                  required
                  maxLength={1000}
                />
              </fieldset>
              <Button type="submit" disabled={busy}>
                Enregistrer la réception et augmenter le stock
              </Button>
            </form>
          )}
          {write &&
            ["DRAFT", "ORDERED", "PART_RECEIVED"].includes(o.status) && (
              <details className="commercial-cancel">
                <summary>Annuler les quantités non reçues</summary>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void mutate("cancel", {
                      expected_version: o.version,
                      reason: new FormData(e.currentTarget).get("reason"),
                    });
                  }}
                >
                  <Field
                    label="Motif de clôture du solde"
                    name="reason"
                    required
                    maxLength={1000}
                  />
                  <Button type="submit" variant="secondary" disabled={busy}>
                    Clôturer le solde
                  </Button>
                </form>
              </details>
            )}
          <h3>Historique des réceptions</h3>
          {o.receipts.length ? (
            o.receipts.map((r) => (
              <p key={r.id}>
                {date(r.created_at)} · {r.sku} · {r.quantity} unité(s) ·{" "}
                {r.reason}
              </p>
            ))
          ) : (
            <p>Aucune réception enregistrée.</p>
          )}
        </>
      )}
    </section>
  );
}
