import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  LayoutDashboard,
  Package,
  ArrowLeftRight,
  Bell,
  Tags,
  LogOut,
  Menu,
  X,
  Boxes,
  Users,
  Palette,
} from "lucide-react";
import { api, post, errorMessage, type User } from "./api";
import { Badge, Button, Field, Loading, Notice } from "./ui";
import {
  DashboardPage,
  AlertsPage,
  MovementsPage,
  PricingPage,
  UsersPage,
  DesignPage,
} from "./pages";
import ProductsPage from "./Products";
const navigation = [
  { id: "dashboard", label: "Tableau de bord", icon: LayoutDashboard },
  { id: "products", label: "Produits et stock", icon: Package },
  { id: "movements", label: "Mouvements", icon: ArrowLeftRight },
  { id: "alerts", label: "Alertes", icon: Bell },
  { id: "pricing", label: "Prix et recommandations", icon: Tags },
];
export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [setup, setSetup] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sessionMessage, setSessionMessage] = useState("");
  const [page, setPage] = useState(
    location.pathname === "/design" ? "design" : "dashboard",
  );
  const [menu, setMenu] = useState(false);
  const [revision, setRevision] = useState(0);
  const closeMenu = useCallback(() => {
    setMenu(false);
    requestAnimationFrame(() =>
      document.getElementById("mobile-menu-trigger")?.focus(),
    );
  }, []);
  useEffect(() => {
    if (!menu) return;
    const sidebar = document.querySelector<HTMLElement>(".sidebar");
    sidebar?.querySelector<HTMLButtonElement>("button")?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeMenu();
      if (event.key === "Tab" && sidebar) {
        const buttons = Array.from(
          sidebar.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"),
        );
        const first = buttons[0];
        const last = buttons.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    const breakpoint = window.matchMedia("(max-width: 900px)");
    const resize = () => {
      if (!breakpoint.matches) closeMenu();
    };
    document.addEventListener("keydown", keydown);
    breakpoint.addEventListener("change", resize);
    return () => {
      document.removeEventListener("keydown", keydown);
      breakpoint.removeEventListener("change", resize);
    };
  }, [menu, closeMenu]);
  const initialize = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const status = await api<{ required: boolean }>("/auth/setup");
      setSetup(status.required);
      if (!status.required) {
        try {
          setUser(await api<User>("/auth/me"));
        } catch (e) {
          if (!(e instanceof Error) || !("status" in e) || e.status !== 401)
            throw e;
        }
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void initialize();
    const expire = () => {
      setUser(null);
      setPage("dashboard");
      setMenu(false);
      history.replaceState(null, "", "/");
      setSessionMessage(
        "Votre session a expiré. Vos opérations confirmées sont conservées.",
      );
    };
    window.addEventListener("session-expired", expire);
    return () => window.removeEventListener("session-expired", expire);
  }, [initialize]);
  const changePage = (next: string) => {
    setPage(next);
    if (menu) closeMenu();
    history.replaceState(null, "", next === "design" ? "/design" : "/");
    window.scrollTo(0, 0);
  };
  const refresh = () => setRevision((v) => v + 1);
  if (loading)
    return (
      <main className="auth-shell">
        <Loading />
      </main>
    );
  if (error)
    return (
      <main className="auth-shell">
        <div className="auth-card">
          <h1>Smart Stock</h1>
          <Notice>{error}</Notice>
          <Button onClick={initialize}>
            Réessayer la connexion au service
          </Button>
        </div>
      </main>
    );
  if (!user)
    return (
      <Auth
        setup={setup}
        message={sessionMessage}
        onSuccess={(u) => {
          setUser(u);
          setPage(
            import.meta.env.DEV && location.pathname === "/design"
              ? "design"
              : "dashboard",
          );
          setMenu(false);
          setSetup(false);
          setSessionMessage("");
        }}
      />
    );
  const write = user.role !== "VIEWER";
  const title =
    navigation.find((n) => n.id === page)?.label ??
    (page === "users" ? "Collaborateurs" : "Catalogue des composants");
  return (
    <div className="app">
      <a className="skip" href="#main">
        Aller au contenu
      </a>
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <div className="brand">
          <span className="brand-icon">
            <Boxes size={25} />
          </span>
          <div>
            Smart Stock<small>Management & Pricing</small>
          </div>
          <Button
            className="mobile-only"
            variant="ghost"
            aria-label="Fermer le menu"
            onClick={closeMenu}
          >
            <X size={20} />
          </Button>
        </div>
        <div className="nav-label">ESPACE DE GESTION</div>
        <nav aria-label="Navigation principale">
          {navigation.map((n) => (
            <button
              key={n.id}
              className={page === n.id ? "active" : ""}
              onClick={() => changePage(n.id)}
              aria-current={page === n.id ? "page" : undefined}
            >
              <n.icon size={19} />
              {n.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          {user.role === "ADMIN" && (
            <button
              className={page === "users" ? "active" : ""}
              onClick={() => changePage("users")}
            >
              <Users size={18} />
              Collaborateurs
            </button>
          )}
          {import.meta.env.DEV && (
            <button onClick={() => changePage("design")}>
              <Palette size={18} />
              Design system
            </button>
          )}
          <div className="local-note">
            <span className="status-dot" /> Espace local
            <br />
            <small>Données de votre base de stock</small>
          </div>
        </div>
      </aside>
      {menu && (
        <button
          className="menu-scrim"
          aria-label="Fermer le menu"
          onClick={closeMenu}
        />
      )}
      <div className="workspace" inert={menu ? true : undefined}>
        <header className="topbar">
          <div>
            <Button
              className="mobile-only"
              id="mobile-menu-trigger"
              variant="ghost"
              aria-label="Ouvrir le menu"
              onClick={() => setMenu(true)}
            >
              <Menu size={22} />
            </Button>
            <span className="breadcrumb">
              Gestion / <strong>{title}</strong>
            </span>
          </div>
          <div className="user-menu">
            <span className="avatar">
              {user.name.slice(0, 1).toUpperCase()}
            </span>
            <div className="user-name">
              {user.name}
              <small>
                {user.role === "ADMIN"
                  ? "Administrateur"
                  : user.role === "MANAGER"
                    ? "Gestionnaire"
                    : "Lecture seule"}
              </small>
            </div>
            <Button
              variant="ghost"
              aria-label="Se déconnecter"
              onClick={async () => {
                try {
                  await post("/auth/logout", {});
                  setUser(null);
                  setPage("dashboard");
                  setMenu(false);
                  history.replaceState(null, "", "/");
                } catch (e) {
                  setError(errorMessage(e));
                }
              }}
            >
              <LogOut size={18} />
            </Button>
          </div>
        </header>
        <main id="main" className="main" tabIndex={-1}>
          {!write && (
            <div className="readonly">
              <Badge>Lecture seule</Badge> Vous pouvez consulter les données.
              Les opérations sont réservées aux gestionnaires.
            </div>
          )}
          {page === "dashboard" && (
            <DashboardPage revision={revision} navigate={changePage} />
          )}
          {page === "products" && (
            <ProductsPage write={write} revision={revision} refresh={refresh} />
          )}
          {page === "movements" && (
            <MovementsPage
              write={write}
              revision={revision}
              refresh={refresh}
            />
          )}
          {page === "alerts" && (
            <AlertsPage revision={revision} navigate={changePage} />
          )}
          {page === "pricing" && (
            <PricingPage write={write} revision={revision} refresh={refresh} />
          )}
          {page === "users" && user.role === "ADMIN" && <UsersPage />}
          {page === "design" &&
            (import.meta.env.DEV ? (
              <DesignPage />
            ) : (
              <Notice>Cette page est réservée au développement.</Notice>
            ))}
        </main>
        <footer className="footer">
          Smart Stock · Les montants sont affichés sans devise ni taxe présumée.
        </footer>
      </div>
    </div>
  );
}
function Auth({
  setup,
  message,
  onSuccess,
}: {
  setup: boolean;
  message: string;
  onSuccess: (user: User) => void;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      await post(
        setup ? "/auth/setup" : "/auth/login",
        Object.fromEntries(data),
      );
      onSuccess(await api<User>("/auth/me"));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-shell">
      <div className="auth-intro">
        <div className="brand">
          <span className="brand-icon">
            <Boxes size={29} />
          </span>
          Smart Stock
        </div>
        <h1>
          Un stock clair.
          <br />
          Des décisions éclairées.
        </h1>
        <p>
          Vos produits, vos mouvements et vos alertes dans un espace de travail
          simple.
        </p>
        <div className="auth-feature">
          <Package size={22} /> Suivez chaque unité, chaque opération.
        </div>
      </div>
      <section className="auth-card">
        <Badge>
          {setup ? "Première utilisation" : "Votre espace de gestion"}
        </Badge>
        <h2>{setup ? "Créer le premier administrateur" : "Bienvenue"}</h2>
        <p>
          {setup
            ? "Initialisez votre base locale avec un compte administrateur. Aucun produit de démonstration ne sera ajouté."
            : "Connectez-vous pour retrouver votre stock."}
        </p>
        {message && <Notice>{message}</Notice>}
        <form onSubmit={submit}>
          {setup && (
            <Field
              label="Nom"
              name="name"
              required
              maxLength={120}
              autoComplete="name"
            />
          )}
          <Field
            label="Adresse e-mail"
            name="email"
            type="email"
            required
            autoComplete="username"
          />
          <Field
            label="Mot de passe"
            name="password"
            type="password"
            required
            minLength={setup ? 12 : 1}
            autoComplete={setup ? "new-password" : "current-password"}
            hint={
              setup
                ? "12 caractères minimum, avec une majuscule et un chiffre."
                : undefined
            }
          />
          {error && <Notice>{error}</Notice>}
          <Button type="submit" disabled={busy} className="full">
            {busy
              ? "Connexion en cours…"
              : setup
                ? "Créer mon espace"
                : "Se connecter"}
          </Button>
        </form>
        <small className="auth-foot">
          Accès protégé · Persistance dans votre base locale
        </small>
      </section>
    </main>
  );
}
