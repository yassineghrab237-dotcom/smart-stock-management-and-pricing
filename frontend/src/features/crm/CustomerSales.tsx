import { money } from "../../api";
import { ResourceState, useResource } from "../../ui";
import type { SalesReport } from "../insights/types";
export default function CustomerSales({
  id,
  revision,
}: {
  id: number;
  revision: number;
}) {
  const resource = useResource<SalesReport>(
    `/insights/sales?customer_id=${id}`,
    revision,
  );
  const r = resource.data;
  return (
    <section>
      <h3>Achats du client · 90 derniers jours</h3>
      <ResourceState {...resource} />
      {r && (
        <>
          <p>
            {r.sales_count} vente(s) · net après retours :{" "}
            <strong>{money(r.totals.net_ttc)} TND TTC</strong>
          </p>
          {r.sales.map((s) => (
            <p key={s.id}>
              {s.reference} · {s.sold_on} · {money(s.net_ttc)} TND TTC
            </p>
          ))}
          {!r.sales.length && (
            <p>Aucune vente confirmée associée sur cette période.</p>
          )}
        </>
      )}
    </section>
  );
}
