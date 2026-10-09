import { ArrowDownLeft, ArrowUpRight, SlidersHorizontal } from "lucide-react";
import { number, date, type Movement } from "../../api";
import { Empty } from "../../ui";
export function MovementHistory({ items }: { items: Movement[] }) {
  return items.length ? (
    <div className="history-list">
      {items.map((m) => (
        <article key={m.id} className="history-item">
          <span className={`movement-icon ${m.type === "OUT" ? "out" : ""}`}>
            {m.type === "IN" ? (
              <ArrowDownLeft size={18} />
            ) : m.type === "OUT" ? (
              <ArrowUpRight size={18} />
            ) : (
              <SlidersHorizontal size={18} />
            )}
          </span>
          <div>
            <strong>
              {m.type === "IN"
                ? "Entrée"
                : m.type === "OUT"
                  ? "Sortie"
                  : "Ajustement"}{" "}
              · {number(m.quantity)}
            </strong>
            <p>
              {m.product_name} · {m.reason}
            </p>
            <small>
              {date(m.created_at)} · {m.actor_name}
            </small>
          </div>
          <span className="history-stock">
            {number(m.stock_before)} → <b>{number(m.stock_after)}</b>
          </span>
        </article>
      ))}
    </div>
  ) : (
    <Empty title="Aucun mouvement">
      Les opérations enregistrées apparaîtront ici avec leur motif et leur
      auteur.
    </Empty>
  );
}
