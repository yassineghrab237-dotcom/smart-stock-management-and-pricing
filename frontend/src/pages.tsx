import { useCallback, useState, type FormEvent } from "react";
import {
  Package,
  Boxes,
  AlertTriangle,
  ArrowUpRight,
  Plus,
  Bell,
  ArrowLeftRight,
} from "lucide-react";
import {
  post,
  errorMessage,
  number,
  type Dashboard,
  type Movement,
  type Product,
  type Alert,
  type User,
} from "./api";
import {
  Badge,
  Button,
  Empty,
  Field,
  Modal,
  Notice,
  ResourceState,
  Loading,
  useResource,
} from "./ui";
import { MovementForm } from "./features/stock/MovementForm";
import { MovementHistory } from "./features/stock/MovementHistory";
import { PricePanel } from "./features/pricing/PricePanel";
import { AccountActions } from "./features/users/AccountActions";
export function DashboardPage({
  revision,
  navigate,
}: {
  revision: number;
  navigate: (page: string) => void;
}) {
  const r = useResource<Dashboard>("/dashboard", revision);
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">VUE D’ENSEMBLE</span>
          <h1>Votre stock, en un regard</h1>
          <p>Les informations essentielles pour organiser votre journée.</p>
        </div>
        <Button onClick={() => navigate("products")}>
          <Package size={18} />
          Consulter les produits
        </Button>
      </div>
      <ResourceState {...r} />
      {r.data && !r.error && !r.loading && (
        <>
          <div className="stats-grid">
            {r.data.product_count === 0 && (
              <section className="panel padded onboarding">
                <h2>Votre première action</h2>
                <p>
                  Créez un produit, puis enregistrez une entrée pour ajouter son
                  stock.
                </p>
                <Button onClick={() => navigate("products")}>
                  Commencer avec un produit
                </Button>
                <Button variant="secondary" onClick={() => navigate("help")}>
                  Lire le guide en 5 minutes
                </Button>
              </section>
            )}
            {[
              {
                label: "Produits au catalogue",
                value: r.data.product_count,
                icon: Package,
                page: "products",
                note: "Produits enregistrés",
              },
              {
                label: "Quantités cumulées",
                value: r.data.total_units,
                icon: Boxes,
                page: "products",
                note: "Somme des quantités, sans conversion des unités",
              },
              {
                label: "Produits en stock bas",
                value: r.data.low_stock_count,
                icon: AlertTriangle,
                page: "alerts",
                note: "Sous leur seuil minimum",
              },
              {
                label: "Produits en surstock",
                value: r.data.overstock_count,
                icon: ArrowUpRight,
                page: "alerts",
                note: "Au-dessus de leur seuil maximum",
              },
            ].map((s) => (
              <button
                className="stat stat-link"
                key={s.label}
                onClick={() => navigate(s.page)}
              >
                <div className="stat-top">
                  <span>{s.label}</span>
                  <s.icon size={20} />
                </div>
                <strong>{number(s.value)}</strong>
                <small>{s.note}</small>
              </button>
            ))}
          </div>
          <div className="dashboard-grid">
            <section className="panel padded">
              <h2>Actions utiles</h2>
              <div className="task-actions">
                <Button
                  variant="secondary"
                  onClick={() => navigate("movements")}
                >
                  Enregistrer ou consulter un mouvement
                </Button>
                <Button variant="secondary" onClick={() => navigate("imports")}>
                  Importer un catalogue ou des ventes
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => navigate("analysis")}
                >
                  Suivre une analyse de ventes
                </Button>
              </div>
              <p>
                Stock et prix manuels actifs. Les prévisions nécessitent un
                historique ; aucun prix n’est appliqué automatiquement.
              </p>
            </section>
            <section className="panel padded">
              <div className="section-heading">
                <h2>Derniers mouvements</h2>
                <Button variant="ghost" onClick={() => navigate("movements")}>
                  Tout voir <ArrowUpRight size={16} />
                </Button>
              </div>
              <MovementHistory items={r.data.recent_movements} />
            </section>
            <section className="panel padded attention">
              <span className="icon-box">
                <Bell size={24} />
              </span>
              <h2>À surveiller</h2>
              <p>
                {r.data.low_stock_count || r.data.overstock_count
                  ? "Certains produits ont dépassé leurs seuils de stock. Consultez les alertes pour choisir les opérations à réaliser."
                  : "Aucun seuil de stock dépassé. Vos alertes évoluent avec les mouvements enregistrés."}
              </p>
              <Button variant="secondary" onClick={() => navigate("alerts")}>
                Consulter les alertes <ArrowUpRight size={16} />
              </Button>
              <div className="quick-divider" />
              <h3>Une opération à enregistrer ?</h3>
              <p>Chaque entrée, sortie ou ajustement conserve une trace.</p>
              <Button variant="ghost" onClick={() => navigate("movements")}>
                <ArrowLeftRight size={17} /> Ouvrir les mouvements
              </Button>
            </section>
          </div>
          <p className="source-note">
            Source : produits et mouvements de votre base locale. Indicateurs
            recalculés côté serveur.
          </p>
        </>
      )}
    </>
  );
}
export function MovementsPage({
  write,
  revision,
  refresh,
}: {
  write: boolean;
  revision: number;
  refresh: () => void;
}) {
  const [filter, setFilter] = useState("");
  const r = useResource<{ items: Movement[] }>(
    `/movements${filter ? `?product_id=${filter}` : ""}`,
    revision,
  );
  const products = useResource<{ items: Product[] }>("/products", revision);
  const [open, setOpen] = useState(false);
  const [success, setSuccess] = useState("");
  const close = useCallback(() => setOpen(false), []);
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">TRAÇABILITÉ</span>
          <h1>Mouvements de stock</h1>
          <p>
            Les opérations confirmées, leur motif et leur impact sur le stock.
          </p>
        </div>
        {write && (
          <Button
            disabled={!products.data?.items.length}
            onClick={() => setOpen(true)}
          >
            <Plus size={18} />
            Enregistrer un mouvement
          </Button>
        )}
      </div>
      {success && <Notice success>{success}</Notice>}
      <ResourceState {...products} />
      <section className="panel padded">
        <label className="field filter-product">
          <span>Filtrer par produit</span>
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">Tous les produits</option>
            {products.data?.items.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {p.sku}
              </option>
            ))}
          </select>
        </label>
        <ResourceState {...r} />
        {r.data && !r.loading && !r.error && (
          <MovementHistory items={r.data.items} />
        )}
      </section>
      {open && products.data && (
        <Modal title="Enregistrer un mouvement" onClose={close}>
          <MovementForm
            products={products.data.items}
            initialId={filter ? Number(filter) : undefined}
            onSuccess={() => {
              close();
              refresh();
              setSuccess("Mouvement confirmé et stock actualisé.");
            }}
          />
        </Modal>
      )}
    </>
  );
}
export function AlertsPage({
  revision,
  navigate,
}: {
  revision: number;
  navigate: (page: string) => void;
}) {
  const r = useResource<{ items: Alert[] }>("/alerts", revision);
  const [filter, setFilter] = useState("all");
  const items = (r.data?.items ?? []).filter(
    (a) => filter === "all" || a.type === filter,
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">POINTS D’ATTENTION</span>
          <h1>Alertes de stock</h1>
          <p>Des alertes calculées à partir des seuils de vos produits.</p>
        </div>
      </div>
      <section className="panel padded">
        <div className="tabs">
          <button
            className={filter === "all" ? "active" : ""}
            onClick={() => setFilter("all")}
          >
            Toutes les alertes
          </button>
          <button
            className={filter === "LOW_STOCK" ? "active" : ""}
            onClick={() => setFilter("LOW_STOCK")}
          >
            Stock bas
          </button>
          <button
            className={filter === "OVERSTOCK" ? "active" : ""}
            onClick={() => setFilter("OVERSTOCK")}
          >
            Surstock
          </button>
        </div>
        <ResourceState {...r} />
        {!r.loading &&
          !r.error &&
          (items.length ? (
            <div className="alert-list">
              {items.map((a) => (
                <article className="alert-card" key={a.id}>
                  <span className="alert-symbol">
                    <AlertTriangle size={23} />
                  </span>
                  <div>
                    <Badge tone={a.type === "LOW_STOCK" ? "danger" : "warning"}>
                      {a.type === "LOW_STOCK" ? "Stock bas" : "Surstock"}
                    </Badge>
                    <h3>{a.product_name}</h3>
                    <small>{a.sku}</small>
                    <p>{a.message}</p>
                    <span>
                      Stock actuel : <strong>{number(a.current_stock)}</strong>{" "}
                      · seuil : <strong>{number(a.threshold)}</strong>
                    </span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <Empty title="Aucune alerte dans cette vue">
              Les alertes apparaissent en dessous du seuil minimum ou au-dessus
              du seuil maximum.
            </Empty>
          ))}
      </section>
      <div className="info-strip">
        Pour résoudre une alerte, enregistrez le mouvement approprié ou revoyez
        les seuils du produit.
        <Button variant="secondary" onClick={() => navigate("products")}>
          Ouvrir les produits
        </Button>
      </div>
    </>
  );
}
export function PricingPage({
  write,
  revision,
  refresh,
}: {
  write: boolean;
  revision: number;
  refresh: () => void;
}) {
  const r = useResource<{ items: Product[] }>("/products", revision);
  const [id, setId] = useState("");
  const product = r.data?.items.find((p) => String(p.id) === id);
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">TARIFICATION</span>
          <h1>Prix et recommandations</h1>
          <p>
            Consultez le prix actuel, les conseils disponibles et les
            changements appliqués.
          </p>
        </div>
      </div>
      <ResourceState {...r} />
      {r.data &&
        (r.data.items.length ? (
          <>
            <section className="panel padded product-selector">
              <label className="field">
                <span>Sélectionner un produit</span>
                <select value={id} onChange={(e) => setId(e.target.value)}>
                  <option value="">Choisir un produit…</option>
                  {r.data.items.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} · {p.sku}
                    </option>
                  ))}
                </select>
              </label>
            </section>
            {product ? (
              <PricePanel
                key={product.id}
                product={product}
                write={write}
                refresh={refresh}
                refreshing={r.loading || !!r.error}
              />
            ) : (
              <section className="panel">
                <Empty title="Choisissez le produit à consulter">
                  Le prix courant et l’historique sont issus de votre base. Les
                  recommandations nécessitent des données et modèles vérifiés.
                </Empty>
              </section>
            )}
          </>
        ) : (
          <section className="panel">
            <Empty title="Aucun produit à tarifer">
              Ajoutez un produit au catalogue pour consulter et modifier son
              prix.
            </Empty>
          </section>
        ))}
    </>
  );
}
export function UsersPage({ actorId }: { actorId: number }) {
  const r = useResource<{ items: User[] }>("/auth/users");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    const form = e.currentTarget;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await post("/auth/users", Object.fromEntries(new FormData(form)));
      form.reset();
      setSuccess("Collaborateur créé.");
      r.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ACCÈS & DROITS</span>
          <h1>Collaborateurs</h1>
          <p>Donnez à chacun les droits adaptés à son travail.</p>
        </div>
      </div>
      <div className="detail-grid">
        <section className="panel padded">
          <h2>Comptes existants</h2>
          <ResourceState {...r} />
          {r.data &&
            !r.loading &&
            !r.error &&
            r.data.items.map((u) => (
              <div className="user-row" key={u.id}>
                <div>
                  <strong>{u.name}</strong>
                  <small>{u.email}</small>
                </div>
                <Badge>
                  {u.role === "ADMIN"
                    ? "Administrateur"
                    : u.role === "MANAGER"
                      ? "Gestionnaire"
                      : "Lecture seule"}
                </Badge>
                <AccountActions user={u} actorId={actorId} refresh={r.reload} />
              </div>
            ))}
        </section>
        <section className="panel padded">
          <h2>Ajouter un collaborateur</h2>
          <form onSubmit={submit}>
            <Field name="name" label="Nom" required maxLength={120} />
            <Field
              name="email"
              label="Adresse e-mail"
              required
              type="email"
              autoComplete="off"
            />
            <Field
              name="password"
              label="Mot de passe initial"
              required
              type="password"
              minLength={12}
              autoComplete="new-password"
              hint="12 caractères minimum, avec une majuscule et un chiffre."
            />
            <label className="field">
              <span>Droits</span>
              <select name="role" defaultValue="VIEWER">
                <option value="VIEWER">Lecture seule · consulter</option>
                <option value="MANAGER">
                  Gestionnaire · produits, stock et prix
                </option>
                <option value="ADMIN">Administrateur · tous les accès</option>
              </select>
            </label>
            {error && <Notice>{error}</Notice>}
            {success && <Notice success>{success}</Notice>}
            <Button disabled={busy} type="submit">
              {busy ? "Création…" : "Créer le compte"}
            </Button>
          </form>
        </section>
      </div>
    </>
  );
}
export function DesignPage() {
  const [message, setMessage] = useState("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">DÉVELOPPEMENT UNIQUEMENT</span>
          <h1>Design system</h1>
          <p>Composants partagés par les écrans métier.</p>
        </div>
      </div>
      <section className="panel padded">
        <h2>Actions</h2>
        <div className="actions">
          <Button onClick={() => setOpen(true)}>Ouvrir le dialogue</Button>
          <Button
            variant="secondary"
            onClick={() =>
              setMessage(
                "Exemple de notification : l’action a été déclenchée dans le catalogue de développement.",
              )
            }
          >
            Afficher une notification
          </Button>
          <Button
            variant="ghost"
            onClick={() => setLoading((current) => !current)}
          >
            {loading ? "Masquer le chargement" : "Afficher le chargement"}
          </Button>
          <Button disabled>Indisponible</Button>
        </div>
        {message && <Notice success>{message}</Notice>}
        {loading && <Loading />}
        <h2>Champs</h2>
        <div className="form-grid">
          <Field label="Champ standard" placeholder="Votre saisie" />
          <Field label="Champ désactivé" disabled value="Lecture seule" />
        </div>
        <h2>Statuts et messages</h2>
        <div className="actions">
          <Badge>Information</Badge>
          <Badge tone="success">Dans les seuils</Badge>
          <Badge tone="warning">Surstock</Badge>
          <Badge tone="danger">Stock bas</Badge>
        </div>
        <Notice>Un refus serveur conserve la saisie.</Notice>
        <Notice success>Une opération confirmée a été enregistrée.</Notice>
        <Empty title="État vide">Un texte explique comment démarrer.</Empty>
      </section>
      {open && (
        <Modal title="Exemple de dialogue" onClose={close}>
          <p>
            Ce dialogue utilise le même composant que les mouvements : focus
            clavier, touche Échap et retour au bouton d’ouverture.
          </p>
          <Field
            label="Saisie de démonstration"
            hint="La valeur reste locale au catalogue de composants."
          />
          <Button
            onClick={() => {
              close();
              setMessage(
                "Dialogue confirmé dans le catalogue de développement. Aucune donnée métier modifiée.",
              );
            }}
          >
            Confirmer l’exemple
          </Button>
        </Modal>
      )}
    </>
  );
}
