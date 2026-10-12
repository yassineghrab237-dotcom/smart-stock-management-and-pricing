import CollectionPanel from "./CollectionPanel";
import { useState, type FormEvent } from "react";
import { date, money, post, errorMessage, type Product } from "../../api";
import {
  Badge,
  Button,
  Empty,
  Field,
  Notice,
  ResourceState,
  useResource,
} from "../../ui";
import "./market.css";
interface Observation {
  id: number;
  retailer: string;
  source_url: string;
  manufacturer_ref: string;
  variant: string;
  price: string;
  currency: string;
  tax_basis: string;
  delivery: string | null;
  availability: string;
  confirmed: boolean;
  note: string;
  observed_at: string;
  actor_name: string;
  stale: boolean;
  current: boolean;
  total: string | null;
  delta_to_lowest: string | null;
}
const availability: Record<string, string> = {
  IN_STOCK: "En stock annoncé",
  OUT_OF_STOCK: "Rupture annoncée",
  UNKNOWN: "Disponibilité inconnue",
};
export default function MarketPage({ write }: { write: boolean }) {
  const products = useResource<{ items: Product[] }>("/products");
  const [selected, setSelected] = useState("");
  return (
    <div className="market-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">TUNISIANET · MYTEK · SPACENET</span>
          <h1>Veille concurrentielle</h1>
          <p>
            Comparez les mêmes références et gardez une trace de chaque offre.
          </p>
        </div>
      </div>
      <div className="market-intro">
        <Badge>Collecte et validation</Badge>
        <p>
          Activez la surveillance des fiches publiques ou saisissez un relevé. Vérifiez la référence, la variante et la livraison.
        </p>
      </div>
      <ResourceState {...products} />
      {products.data &&
        (products.data.items.length ? (
          <div className="field">
            <label htmlFor="market-product">Produit à surveiller</label>
            <select
              id="market-product"
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              <option value="">Choisir un produit du catalogue</option>
              {products.data.items.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.sku} — {p.name}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <Empty title="Votre catalogue est vide">
            Ajoutez un produit dans Produits et stock pour commencer la veille.
          </Empty>
        ))}
      {selected && (
        <ProductMarket
          key={selected}
          productId={Number(selected)}
          write={write}
        />
      )}
    </div>
  );
}
function ProductMarket({
  productId,
  write,
}: {
  productId: number;
  write: boolean;
}) {
  const [revision, setRevision] = useState(0);
  const resource = useResource<{ items: Observation[] }>(
    `/market/products/${productId}`,
    revision,
  );
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState(() => crypto.randomUUID());
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await post("/market/observations", {
        ...Object.fromEntries(data),
        product_id: productId,
        confirmed: data.get("confirmed") === "on",
        delivery: data.get("delivery") || null,
        observed_at: new Date(String(data.get("observed_at"))).toISOString(),
        idempotency_key: key,
      });
      setSuccess(
        "Relevé enregistré. Le prix et le stock internes sont conservés.",
      );
      setKey(crypto.randomUUID());
      setRevision((v) => v + 1);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <CollectionPanel
        productId={productId}
        write={write}
        onObservation={() => setRevision((v) => v + 1)}
      />
      {write && (
        <section className="market-card">
          <h2>Ajouter un relevé</h2>
          <p>
            Pour corriger ou confirmer une observation, saisissez un nouveau
            relevé de la même URL. L’historique reste conservé.
          </p>
          <form
            onSubmit={submit}
            onChange={() => {
              setKey(crypto.randomUUID());
              setSuccess("");
            }}
          >
            <fieldset disabled={busy} className="market-fields">
              <legend className="sr-only">Détails du relevé</legend>
              <div className="field">
                <label htmlFor="retailer">Enseigne</label>
                <select id="retailer" name="retailer">
                  <option>Tunisianet</option>
                  <option>Mytek</option>
                  <option>Spacenet</option>
                </select>
              </div>
              <Field
                label="URL de la fiche produit"
                name="source_url"
                type="url"
                required
                maxLength={2000}
                placeholder="https://www.tunisianet.com.tn/…"
              />
              <Field
                label="Référence fabricant"
                name="manufacturer_ref"
                required
                maxLength={160}
                hint="Utilisez la référence exacte, pas le code propre au vendeur."
              />
              <Field
                label="Variante et garantie"
                name="variant"
                required
                maxLength={400}
                hint="Même description pour comparer : RAM, capacité, état, garantie, accessoires."
              />
              <Field
                label="Prix affiché"
                name="price"
                required
                inputMode="decimal"
                pattern="[0-9]+([.][0-9]{1,4})?"
                placeholder="1299.000"
              />
              <div className="field">
                <label htmlFor="currency">Devise du relevé</label>
                <select id="currency" name="currency">
                  <option>TND</option>
                  <option>EUR</option>
                  <option>USD</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="tax_basis">Base du prix</label>
                <select id="tax_basis" name="tax_basis" defaultValue="UNKNOWN">
                  <option value="UNKNOWN">À vérifier</option>
                  <option>TTC</option>
                  <option>HT</option>
                </select>
              </div>
              <Field
                label="Livraison pour une unité"
                name="delivery"
                inputMode="decimal"
                pattern="[0-9]+([.][0-9]{1,4})?"
                hint="Vide si inconnue. 0 uniquement si gratuite pour cette commande."
              />
              <div className="field">
                <label htmlFor="availability">Disponibilité affichée</label>
                <select
                  id="availability"
                  name="availability"
                  defaultValue="UNKNOWN"
                >
                  {Object.entries(availability).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <Field
                label="Date et heure du relevé"
                type="datetime-local"
                name="observed_at"
                required
              />
              <Field
                label="Conditions et justification"
                name="note"
                required
                maxLength={1000}
                hint="Promotion éventuelle, garantie et éléments vérifiés pour la correspondance."
              />
              <label className="market-check">
                <input name="confirmed" type="checkbox" /> J’ai vérifié qu’il
                s’agit du même produit et de la même variante que mon produit
                interne.
              </label>
            </fieldset>
            {error && <Notice>{error}</Notice>}
            {success && <Notice success>{success}</Notice>}
            <Button type="submit" disabled={busy}>
              {busy ? "Enregistrement…" : "Enregistrer le relevé"}
            </Button>
          </form>
        </section>
      )}
      <section className="market-card">
        <h2>Offres et historique</h2>
        <p>
          L’écart au minimum inclut la livraison connue. Il exige deux
          enseignes, une correspondance confirmée, une variante identique, une
          même devise et base de taxe, et un relevé de moins de 24 h en stock.
        </p>
        <Button variant="secondary" onClick={resource.reload}>
          Actualiser les relevés
        </Button>
        <ResourceState {...resource} />
        {resource.data?.items.length === 0 && (
          <Empty title="Aucune offre relevée">
            Les observations apparaîtront ici après leur enregistrement.
          </Empty>
        )}
        <div className="market-offers">
          {resource.data?.items.map((o) => (
            <article className="market-offer" key={o.id}>
              <header>
                <h3>{o.retailer}</h3>
                <Badge tone={o.stale || !o.confirmed ? "warning" : "neutral"}>
                  {!o.current
                    ? "Historique"
                    : o.stale
                      ? "À actualiser"
                      : o.confirmed
                        ? "Correspondance confirmée"
                        : "À vérifier"}
                </Badge>
              </header>
              <strong className="market-price">
                {money(o.price)} {o.currency}{" "}
                <small>
                  {o.tax_basis === "UNKNOWN" ? "Taxes à vérifier" : o.tax_basis}
                </small>
              </strong>
              <p>
                {o.manufacturer_ref} · {o.variant}
              </p>
              <p>
                {availability[o.availability]} · Livraison :{" "}
                {o.delivery === null
                  ? "inconnue"
                  : `${money(o.delivery)} ${o.currency}`}
              </p>
              <p>
                <strong>
                  Écart au minimum :{" "}
                  {o.delta_to_lowest === null
                    ? "comparaison indisponible"
                    : `+${money(o.delta_to_lowest)} ${o.currency}`}
                </strong>
              </p>
              <p>{o.note}</p>
              <small>
                Observé le {date(o.observed_at)} · {o.actor_name}
              </small>
              <a href={o.source_url} target="_blank" rel="noreferrer">
                Consulter la source
              </a>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
