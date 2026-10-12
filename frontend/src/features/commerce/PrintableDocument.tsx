import { createPortal } from "react-dom";
import { money, date } from "../../api";
import type { Document } from "./types";
import { statuses } from "./types";
import "./print.css";
export default function PrintableDocument({
  document: d,
}: {
  document: Document;
}) {
  return createPortal(
    <article className="document-print">
      <header>
        <strong>PRECIOS</strong>
        <p>Document commercial interne · TND</p>
        <h1>
          {d.kind === "QUOTE" ? "Devis" : "Vente"} {d.reference}
        </h1>
        <p>
          {statuses[d.status]} · Enregistré le {date(d.created_at)}
          {d.sold_on && ` · Vente du ${d.sold_on}`}
        </p>
        <p>Client : {d.customer_name ?? "Non renseigné"}</p>
      </header>
      <table>
        <thead>
          <tr>
            <th>Produit</th>
            <th>Qté</th>
            <th>PU TTC</th>
            <th>Remise/unité TTC</th>
            <th>Taxe %</th>
            <th>Total TTC</th>
          </tr>
        </thead>
        <tbody>
          {d.lines.map((l) => (
            <tr key={l.id}>
              <td>
                {l.name}
                <br />
                <small>{l.sku}</small>
              </td>
              <td>{l.quantity}</td>
              <td>{money(l.unit_price_ttc)}</td>
              <td>{money(l.discount_ttc)}</td>
              <td>{money(l.tax_rate)}</td>
              <td>{money(l.total_ttc)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <section>
        <p>
          Total HT : <strong>{money(d.totals.total_ht)} TND</strong>
        </p>
        <p>
          Taxes : <strong>{money(d.totals.tax)} TND</strong>
        </p>
        <p>
          Total TTC : <strong>{money(d.totals.total_ttc)} TND</strong>
        </p>
        {d.returns.length > 0 && (
          <p>
            Après retours : <strong>{money(d.net_total_ttc)} TND TTC</strong>
          </p>
        )}
      </section>
      <p className="document-print-note">{d.note}</p>
      <footer>
        Ce document interne ne constitue pas une facture fiscale. Vérifiez les
        coordonnées du vendeur, les conditions de validité, de paiement et de
        livraison avant utilisation commerciale. Les coûts d’achat et la
        contribution ne sont pas imprimés.
      </footer>
    </article>,
    document.body,
  );
}
