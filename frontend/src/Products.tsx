import { useCallback, useState } from "react";
import { Plus, Search, ArrowUpRight } from "lucide-react";
import { number, money, type Product } from "./api";
import { Button, Empty, Modal, ResourceState, useResource } from "./ui";
import { StockBadge } from "./features/products/StockBadge";
import { ProductForm } from "./features/products/ProductForm";
import { ProductDetail } from "./features/products/ProductDetail";
export default function ProductsPage({
  write,
  revision,
  refresh,
}: {
  write: boolean;
  revision: number;
  refresh: () => void;
}) {
  const resource = useResource<{ items: Product[] }>("/products", revision);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("name");
  const [selected, setSelected] = useState<number | null>(null);
  const [create, setCreate] = useState(false);
  const close = useCallback(() => setCreate(false), []);
  if (selected !== null)
    return (
      <ProductDetail
        id={selected}
        write={write}
        revision={revision}
        refresh={refresh}
        back={() => setSelected(null)}
      />
    );
  const products = (resource.data?.items ?? [])
    .filter(
      (p) =>
        `${p.name} ${p.sku} ${p.category ?? ""}`
          .toLocaleLowerCase("fr")
          .includes(query.toLocaleLowerCase("fr")) &&
        (filter === "all" ||
          (filter === "low"
            ? p.current_stock < p.threshold_min
            : filter === "over"
              ? p.threshold_max !== null && p.current_stock > p.threshold_max
              : p.current_stock === 0)),
    )
    .sort((a, b) =>
      sort === "stock"
        ? a.current_stock - b.current_stock
        : sort === "sku"
          ? a.sku.localeCompare(b.sku)
          : a.name.localeCompare(b.name),
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">CATALOGUE & DISPONIBILITÉ</span>
          <h1>Produits et stock</h1>
          <p>Retrouvez vos produits et gardez le stock à jour.</p>
        </div>
        {write && (
          <Button onClick={() => setCreate(true)}>
            <Plus size={18} /> Ajouter un produit
          </Button>
        )}
      </div>
      <section className="panel">
        <div className="toolbar">
          <label className="search">
            <Search size={18} />
            <input
              aria-label="Rechercher par nom, référence ou catégorie"
              placeholder="Nom, référence ou catégorie…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <label className="compact-field">
            <span>État du stock</span>
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">Tous les états</option>
              <option value="low">Stock bas</option>
              <option value="over">Surstock</option>
              <option value="zero">Stock nul</option>
            </select>
          </label>
          <label className="compact-field">
            <span>Trier par</span>
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="name">Nom du produit</option>
              <option value="sku">Référence</option>
              <option value="stock">Stock croissant</option>
            </select>
          </label>
        </div>
        <ResourceState {...resource} />
        {!resource.loading &&
          !resource.error &&
          (products.length ? (
            <>
              <div className="list-caption">
                {number(products.length)} produit
                {products.length > 1 ? "s" : ""}
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Produit</th>
                      <th>Stock disponible</th>
                      <th>État</th>
                      <th>Prix actuel</th>
                      <th>
                        <span className="sr-only">Action</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {products.map((p) => (
                      <tr key={p.id}>
                        <td>
                          <button
                            className="product-link"
                            onClick={() => setSelected(p.id)}
                          >
                            {p.name}
                          </button>
                          <small>
                            {p.sku} {p.category && `· ${p.category}`}
                          </small>
                        </td>
                        <td>
                          <strong className="numeric">
                            {number(p.current_stock)}
                          </strong>
                          <small>
                            {p.unit || "unités"} · seuil min.{" "}
                            {number(p.threshold_min)}
                          </small>
                        </td>
                        <td>
                          <StockBadge product={p} />
                        </td>
                        <td className="numeric">{money(p.current_price)}</td>
                        <td>
                          <Button
                            variant="ghost"
                            aria-label={`Voir ${p.name}`}
                            onClick={() => setSelected(p.id)}
                          >
                            <ArrowUpRight size={18} />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="product-cards">
                {products.map((p) => (
                  <button
                    className="product-card"
                    key={p.id}
                    onClick={() => setSelected(p.id)}
                  >
                    <div>
                      <strong>{p.name}</strong>
                      <small>
                        {p.sku} {p.category && `· ${p.category}`}
                      </small>
                    </div>
                    <StockBadge product={p} />
                    <div className="card-metrics">
                      <span>
                        Stock{" "}
                        <b>
                          {number(p.current_stock)}{" "}
                          <small>{p.unit || "unités"}</small>
                        </b>
                      </span>
                      <span>
                        Prix actuel <b>{money(p.current_price)}</b>
                      </span>
                    </div>
                    <span className="card-action">
                      Ouvrir la fiche <ArrowUpRight size={16} />
                    </span>
                  </button>
                ))}
              </div>
            </>
          ) : (
            <Empty
              title={
                query || filter !== "all"
                  ? "Aucun produit correspondant"
                  : "Votre catalogue commence ici"
              }
              action={
                write && !query && filter === "all" ? (
                  <Button onClick={() => setCreate(true)}>
                    <Plus size={18} />
                    Ajouter un produit
                  </Button>
                ) : undefined
              }
            >
              {query || filter !== "all"
                ? "Modifiez la recherche ou les filtres pour retrouver un produit."
                : "Ajoutez votre premier produit, puis enregistrez une entrée de stock."}
            </Empty>
          ))}
      </section>
      {create && (
        <Modal title="Ajouter un produit" onClose={close}>
          <ProductForm
            onSuccess={() => {
              close();
              refresh();
            }}
          />
        </Modal>
      )}
    </>
  );
}
