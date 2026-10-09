import { useCallback, useState } from "react";
import { ArrowLeft, Plus } from "lucide-react";
import { number, type Product, type Movement } from "../../api";
import { Button, Modal, Notice, ResourceState, useResource } from "../../ui";
import { StockBadge } from "./StockBadge";
import { ProductForm } from "./ProductForm";
import { MovementForm } from "../stock/MovementForm";
import { MovementHistory } from "../stock/MovementHistory";
import { PricePanel } from "../pricing/PricePanel";
export function ProductDetail({
  id,
  write,
  revision,
  refresh,
  back,
}: {
  id: number;
  write: boolean;
  revision: number;
  refresh: () => void;
  back: () => void;
}) {
  const r = useResource<Product>(`/products/${id}`, revision);
  const movements = useResource<{ items: Movement[] }>(
    `/movements?product_id=${id}`,
    revision,
  );
  const [action, setAction] = useState<"move" | "edit" | null>(null);
  const [tab, setTab] = useState("stock");
  const [success, setSuccess] = useState("");
  const close = useCallback(() => setAction(null), []);
  return (
    <>
      <Button variant="ghost" onClick={back}>
        <ArrowLeft size={17} /> Retour aux produits
      </Button>
      <ResourceState {...r} />
      {r.data && (
        <>
          <div className="page-heading">
            <div>
              <span className="eyebrow">{r.data.sku}</span>
              <h1>{r.data.name}</h1>
              <p>
                {r.data.category || "Sans catégorie"} ·{" "}
                {r.data.unit || "Unité non renseignée"}
              </p>
            </div>
            {write && (
              <div className="actions">
                <Button
                  disabled={r.loading || !!r.error}
                  variant="secondary"
                  onClick={() => setAction("edit")}
                >
                  Modifier les informations
                </Button>
                <Button
                  disabled={r.loading || !!r.error}
                  onClick={() => setAction("move")}
                >
                  <Plus size={18} /> Enregistrer un mouvement
                </Button>
              </div>
            )}
          </div>
          {success && <Notice success>{success}</Notice>}
          <div className="tabs">
            <button
              className={tab === "stock" ? "active" : ""}
              onClick={() => setTab("stock")}
            >
              Stock et historique
            </button>
            <button
              className={tab === "price" ? "active" : ""}
              onClick={() => setTab("price")}
            >
              Prix et recommandations
            </button>
          </div>
          {tab === "stock" ? (
            <>
              <div className="stats-grid three">
                <div className="stat">
                  <span>Stock disponible</span>
                  <strong>{number(r.data.current_stock)}</strong>
                  <StockBadge product={r.data} />
                </div>
                <div className="stat">
                  <span>Seuil minimum</span>
                  <strong>{number(r.data.threshold_min)}</strong>
                  <small>Alerte en dessous du seuil</small>
                </div>
                <div className="stat">
                  <span>Seuil maximum</span>
                  <strong>
                    {r.data.threshold_max === null
                      ? "—"
                      : number(r.data.threshold_max)}
                  </strong>
                  <small>
                    {r.data.threshold_max === null
                      ? "Aucun seuil défini"
                      : "Alerte au-dessus du seuil"}
                  </small>
                </div>
              </div>
              <section className="panel padded">
                <h2>Historique des mouvements</h2>
                <ResourceState {...movements} />
                {movements.data && !movements.loading && !movements.error && (
                  <MovementHistory items={movements.data.items} />
                )}
              </section>
            </>
          ) : (
            <PricePanel
              product={r.data}
              write={write}
              refresh={refresh}
              refreshing={r.loading || !!r.error}
            />
          )}{" "}
          {action && (
            <Modal
              title={
                action === "move"
                  ? "Enregistrer un mouvement"
                  : "Modifier le produit"
              }
              onClose={close}
            >
              {action === "move" ? (
                <MovementForm
                  products={[r.data]}
                  initialId={id}
                  onSuccess={() => {
                    close();
                    refresh();
                    setSuccess(
                      "Mouvement enregistré. Le stock et l’historique ont été actualisés.",
                    );
                  }}
                />
              ) : (
                <ProductForm
                  product={r.data}
                  onSuccess={() => {
                    close();
                    refresh();
                    setSuccess("Informations du produit enregistrées.");
                  }}
                />
              )}
            </Modal>
          )}
        </>
      )}
    </>
  );
}
