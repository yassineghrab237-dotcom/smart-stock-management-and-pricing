import { useState, type FormEvent } from "react";
import { money } from "../../api";
import {
  Button,
  Empty,
  Field,
  Notice,
  ResourceState,
  useResource,
} from "../../ui";
import type { SalesReport } from "./types";
import "../commerce/commerce.css";
import "./insights.css";
export default function InsightsPage() {
  const [query, setQuery] = useState("");
  const resource = useResource<SalesReport>(`/insights/sales${query}`);
  const r = resource.data;
  function filter(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    setQuery(
      `?${new URLSearchParams({ start: String(d.get("start")), end: String(d.get("end")) })}`,
    );
  }
  return (
    <div className="commercial-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">VENTES · MARGES · ASSORTIMENT</span>
          <h1>Rentabilité et paniers</h1>
          <p>
            Repérez vos références contributrices et les produits achetés
            ensemble.
          </p>
        </div>
        <Button variant="secondary" onClick={resource.reload}>
          Actualiser les indicateurs
        </Button>
      </div>
      <form className="insights-filter" onSubmit={filter}>
        <Field label="Ventes depuis le" name="start" type="date" required />
        <Field label="Ventes jusqu’au" name="end" type="date" required />
        <Button type="submit">Appliquer la période</Button>
      </form>
      <ResourceState {...resource} />
      {r && (
        <>
          <p>
            Ventes confirmées du {r.start} au {r.end} · dates de Tunis. Tous les
            retours connus de ces ventes sont déduits, même s’ils sont
            postérieurs à la période.
          </p>
          <div className="insights-metrics">
            <article>
              <span>Ventes confirmées</span>
              <strong>{r.sales_count}</strong>
              <small>
                {r.active_baskets} panier(s) avec articles conservés
              </small>
            </article>
            <article>
              <span>Ventes nettes TTC</span>
              <strong>{money(r.totals.net_ttc)} TND</strong>
              <small>{r.totals.net_units} unité(s) après retours</small>
            </article>
            <article>
              <span>Ventes nettes HT</span>
              <strong>{money(r.totals.net_ht)} TND</strong>
              <small>{r.totals.returned_units} unité(s) retournée(s)</small>
            </article>
            <article>
              <span>Contribution HT</span>
              <strong>
                {r.totals.contribution_ht === null
                  ? "Coûts incomplets"
                  : `${money(r.totals.contribution_ht)} TND`}
              </strong>
              <small>
                {r.totals.known_cost_lines}/{r.totals.line_count} lignes avec
                coût
              </small>
            </article>
          </div>
          {r.totals.contribution_ht === null && (
            <Notice>
              Contribution calculable sur les seules lignes avec coût :{" "}
              {money(r.totals.known_contribution_ht)} TND. Ce montant ne
              représente pas la contribution totale.
            </Notice>
          )}
          <p className="commercial-footnote">
            Contribution = ventes HT après remises et retours − coûts HT des
            articles, y compris les retours non revendables. Les frais de
            livraison, paiement et structure restent à déduire. Les imports
            historiques sans base fiscale connue sont exclus.
          </p>
          <section className="commercial-panel">
            <h2>Produits phares par contribution</h2>
            <p>
              Classement descriptif sur la période. Les références aux coûts
              incomplets figurent en fin de liste ; aucun prix n’est modifié.
            </p>
            {!r.products.length ? (
              <Empty title="Aucune vente confirmée">
                Confirmez une vente dans Ventes et devis pour alimenter ces
                indicateurs.
              </Empty>
            ) : (
              <div className="insights-products">
                {r.products.map((p, i) => (
                  <article className="insights-product" key={p.id}>
                    <header>
                      <span className="insights-rank">{i + 1}</span>
                      <div>
                        <h3>{p.name}</h3>
                        <small>
                          {p.sku} · stock actuel {p.current_stock}
                        </small>
                      </div>
                    </header>
                    <dl>
                      <dt>Ventes nettes HT</dt>
                      <dd>{money(p.net_ht)} TND</dd>
                      <dt>Contribution HT</dt>
                      <dd>
                        {p.contribution_ht === null
                          ? "Coût incomplet"
                          : `${money(p.contribution_ht)} TND`}
                      </dd>
                      <dt>Unités conservées / retours</dt>
                      <dd>
                        {p.net_units} / {p.returned_units}
                      </dd>
                      <dt>Paniers avec ce produit</dt>
                      <dd>{p.baskets}</dd>
                    </dl>
                  </article>
                ))}
              </div>
            )}
          </section>
          <section className="commercial-panel">
            <h2>Associations et produits d’appel à étudier</h2>
            <p>
              Un achat conjoint indique une association, pas que l’un des
              produits déclenche la visite. Validez un produit d’appel avec le
              trafic, la conversion et un test de promotion mesuré.
            </p>
            {!r.associations.length ? (
              <Empty title="Pas encore d’association répétée">
                Deux paniers distincts au minimum doivent contenir la même paire
                de produits.
              </Empty>
            ) : (
              r.associations.map((p) => (
                <article
                  className="commercial-item"
                  key={`${p.product_a}:${p.product_b}`}
                >
                  <h3>
                    {p.product_a} + {p.product_b}
                  </h3>
                  <p>
                    Ensemble dans {p.baskets} panier(s) sur {p.total_baskets}.{" "}
                    {p.product_a} apparaît dans {p.a_baskets} panier(s),{" "}
                    {p.product_b} dans {p.b_baskets}.
                  </p>
                </article>
              ))
            )}
          </section>
          <section className="commercial-panel">
            <h2>Dernières ventes de la période</h2>
            {r.sales.map((s) => (
              <p key={s.id}>
                <strong>{s.reference}</strong> · {s.sold_on} ·{" "}
                {s.customer_name ?? "Sans fiche client"} · net{" "}
                {money(s.net_ttc)} TND TTC
              </p>
            ))}
            {!r.sales.length && <p>Aucune vente pour cette période.</p>}
          </section>
        </>
      )}
    </div>
  );
}
