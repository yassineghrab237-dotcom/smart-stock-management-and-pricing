import { useState, type FormEvent } from "react";
import {
  patch,
  errorMessage,
  money,
  date,
  type Product,
  type PriceEntry,
  type Recommendation,
} from "../../api";
import {
  Badge,
  Button,
  Empty,
  Field,
  Notice,
  ResourceState,
  useResource,
} from "../../ui";
export function PricePanel({
  product,
  write,
  refresh,
  refreshing = false,
}: {
  product: Product;
  write: boolean;
  refresh: () => void;
  refreshing?: boolean;
}) {
  const prices = useResource<{ items: PriceEntry[] }>(
    `/products/${product.id}/prices`,
    product.version,
  );
  const rec = useResource<Recommendation>(
    `/pricing/recommendations/${product.id}`,
    product.version,
  );
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [key, setKey] = useState(() => crypto.randomUUID());
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || refreshing) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await patch(`/products/${product.id}/price`, {
        price: value,
        reason,
        expected_version: product.version,
        idempotency_key: key,
      });
      setSuccess("Nouveau prix enregistré.");
      setValue("");
      setReason("");
      setKey(crypto.randomUUID());
      refresh();
    } catch (err) {
      setError(
        err instanceof TypeError
          ? `${errorMessage(err)} Le prix a peut-être été enregistré. Réessayez sans modifier la saisie ou consultez l’historique.`
          : errorMessage(err),
      );
      if (err instanceof Error && "status" in err && err.status === 409) {
        refresh();
        setKey(crypto.randomUUID());
        setError(
          "Le produit a changé. Les données sont actualisées; vérifiez le prix et confirmez à nouveau.",
        );
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="detail-grid">
        <section className="panel padded">
          <h2>Prix du produit</h2>
          <div className="price-current">
            {money(product.current_price)}
            <small>Prix actuel · aucune devise présumée</small>
          </div>
          <div className="meta-line">
            Coût : {money(product.cost_price)} · Minimum :{" "}
            {money(product.min_price)}
          </div>
          {write && (
            <form onSubmit={submit}>
              <Field
                label="Nouveau prix"
                type="number"
                min={product.min_price ?? "0"}
                step="0.0001"
                required
                value={value}
                onChange={(e) => {
                  setValue(e.target.value);
                  setKey(crypto.randomUUID());
                }}
              />
              <Field
                label="Motif du changement"
                required
                minLength={1}
                maxLength={500}
                value={reason}
                onChange={(e) => {
                  setReason(e.target.value);
                  setKey(crypto.randomUUID());
                }}
              />
              {error && <Notice>{error}</Notice>}
              {success && <Notice success>{success}</Notice>}
              <Button disabled={busy || refreshing} type="submit">
                {busy ? "Application…" : "Appliquer ce prix"}
              </Button>
            </form>
          )}
        </section>
        <section className="panel padded">
          <h2>Recommandation</h2>
          <ResourceState {...rec} />
          {rec.data && !rec.error && !rec.loading && (
            <>
              <Badge
                tone={rec.data.status === "available" ? "success" : "neutral"}
              >
                {rec.data.status === "available"
                  ? "Disponible"
                  : "Indisponible"}
              </Badge>
              <p>
                {rec.data.detail ??
                  "Aucune recommandation vérifiée disponible pour ce produit."}
              </p>
              {rec.data.method && (
                <p>
                  <strong>Méthode :</strong> {rec.data.method}
                </p>
              )}
              {rec.data.source && (
                <p>
                  <strong>Source :</strong> {rec.data.source}
                </p>
              )}
              {rec.data.freshness !== undefined && (
                <p>
                  <strong>Fraîcheur :</strong>{" "}
                  {typeof rec.data.freshness === "string"
                    ? rec.data.freshness
                    : JSON.stringify(rec.data.freshness)}
                </p>
              )}
              {rec.data.status === "available" &&
                rec.data.data !== undefined && (
                  <pre className="recommendation-data">
                    {JSON.stringify(rec.data.data, null, 2)}
                  </pre>
                )}
              <small>
                Une recommandation ne modifie jamais automatiquement le prix
                actuel.
              </small>
            </>
          )}
        </section>
      </div>
      <section className="panel padded">
        <h2>Historique des prix</h2>
        <ResourceState {...prices} />
        {prices.data &&
          !prices.error &&
          !prices.loading &&
          (prices.data.items.length ? (
            <div className="history-list">
              {prices.data.items.map((p) => (
                <article key={p.id} className="history-item">
                  <div>
                    <strong>
                      {money(p.old_price)} → {money(p.new_price)}
                    </strong>
                    <p>{p.reason}</p>
                    <small>
                      {date(p.created_at)} · {p.actor_name}
                    </small>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <Empty title="Pas encore de changement de prix">
              Le premier changement confirmé apparaîtra ici.
            </Empty>
          ))}
      </section>
    </>
  );
}
