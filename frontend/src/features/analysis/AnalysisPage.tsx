import { useEffect, useState } from "react";
import { post, errorMessage, type User } from "../../api";
import {
  Badge,
  Button,
  Empty,
  Notice,
  ResourceState,
  useResource,
} from "../../ui";
interface Forecast {
  product_id: number;
  sku: string;
  name: string;
  detail: string;
  prediction: number | null;
  target_week?: string;
  weeks: number;
  model_mae?: number;
  baseline_mae?: number;
  baseline_name?: string;
  tuning?: { tuned: boolean; tuning_folds: number };
}
interface Job {
  id: number;
  status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "INTERRUPTED";
  progress: number;
  message: string;
  stale: boolean;
  created_at: string;
  result: { products: Forecast[]; as_of: string } | null;
}
const statusLabels = {
  QUEUED: "En attente",
  RUNNING: "Calcul en cours",
  SUCCEEDED: "Terminé",
  FAILED: "Échec",
  INTERRUPTED: "Interrompu",
};
export default function AnalysisPage({
  user,
  navigate,
}: {
  user: User;
  navigate: (page: string) => void;
}) {
  const [revision, setRevision] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [success, setSuccess] = useState("");
  const resource = useResource<{ items: Job[] }>("/analysis/jobs", revision);
  const active = resource.data?.items.some(
    (j) => j.status === "QUEUED" || j.status === "RUNNING",
  );
  useEffect(() => {
    if (!active || resource.error) return;
    const timer = window.setInterval(() => setRevision((v) => v + 1), 2500);
    return () => window.clearInterval(timer);
  }, [active, resource.error]);
  async function start() {
    if (busy) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await post<Job>("/analysis/jobs", {});
      setSuccess(
        "Analyse prise en charge. Son état s’actualise pendant le calcul.",
      );
      setRevision((v) => v + 1);
    } catch (e) {
      setError(
        `${errorMessage(e)} Actualisez les traitements avant de relancer ; une analyse identique ne sera pas exécutée deux fois.`,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">AIDE À LA DÉCISION</span>
          <h1>Analyser les ventes</h1>
          <p>
            Estimer la demande à partir de vos ventes historiques et confirmées,
            puis vérifier ses limites.
          </p>
        </div>
        {user.role !== "VIEWER" && (
          <Button disabled={busy || active} onClick={start}>
            {busy
              ? "Demande en cours…"
              : active
                ? "Analyse en cours…"
                : "Lancer l’analyse"}
          </Button>
        )}
      </div>
      <section className="panel padded">
        <h2>Avant de commencer</h2>
        <p>
          Les ventes confirmées et les imports historiques alimentent le calcul,
          après déduction des retours des ventes opérationnelles. Chaque produit
          nécessite au moins 16 semaines terminées consécutives, jusqu’à la
          semaine dernière. Les semaines manquantes restent inconnues ; elles ne
          sont pas remplacées par zéro.
        </p>
        <p>
          À partir de 24 semaines, les réglages sont comparés sur deux périodes
          anciennes. Les 4 dernières semaines sont réservées au contrôle final.
          Une prévision est affichée seulement si le modèle bat trois méthodes
          simples : dernière semaine, moyenne récente et répétition à quatre
          semaines. Ce contrôle ne garantit pas les ventes futures.
        </p>
        <Button variant="secondary" onClick={() => navigate("imports")}>
          Ouvrir les imports CSV
        </Button>
        <p className="source-note">
          Calcul Python local, sans tokens. Aucun stock ni prix modifié. La
          véracité des données importées n’est pas certifiée.
        </p>
      </section>
      {error && <Notice>{error}</Notice>}
      {success && <Notice success>{success}</Notice>}
      <ResourceState {...resource} />
      {resource.data?.items.length === 0 && (
        <Empty
          title="Aucune analyse réalisée"
          action={
            <Button variant="secondary" onClick={() => navigate("imports")}>
              Importer mes ventes
            </Button>
          }
        >
          Importez votre historique, puis lancez une première analyse.
        </Empty>
      )}
      {resource.data?.items.map((job) => (
        <section key={job.id} className="panel padded analysis-job">
          <div className="section-heading">
            <h2>Analyse #{job.id}</h2>
            <Badge
              tone={
                job.status === "SUCCEEDED"
                  ? "success"
                  : job.status === "FAILED" || job.status === "INTERRUPTED"
                    ? "danger"
                    : "neutral"
              }
            >
              {statusLabels[job.status]}
            </Badge>
          </div>
          <p>{job.message}</p>
          <progress
            aria-label={`Progression analyse ${job.id}`}
            max={100}
            value={job.progress}
          />
          <small>
            {job.progress} % ·{" "}
            {new Date(job.created_at).toLocaleString("fr-FR")}
          </small>
          {job.stale && (
            <Notice>
              Les données, la date ou la méthode ont changé depuis cette
              analyse. Ses résultats sont historiques. Lancez une nouvelle
              analyse avant de décider.
            </Notice>
          )}
          {job.result && (
            <div className="forecast-grid">
              {job.result.products.length === 0 && (
                <p>Aucun produit dans le catalogue lors de cette analyse.</p>
              )}
              {job.result.products.map((p) => (
                <article className="import-row" key={p.product_id}>
                  <strong>{p.name}</strong>
                  <span>
                    {p.sku} · {p.weeks} semaine(s) de ventes
                  </span>
                  {p.prediction !== null && !job.stale && (
                    <div className="forecast-value">
                      {p.prediction} unités
                      <small>
                        Demande estimée · semaine du {p.target_week}
                      </small>
                    </div>
                  )}
                  <p>{p.detail}</p>
                  {p.model_mae !== undefined && (
                    <p>
                      Écart moyen lors du contrôle : modèle {p.model_mae} unités
                      ; meilleure méthode simple {p.baseline_mae} unités
                      {p.baseline_name ? ` (${p.baseline_name})` : ""}.
                    </p>
                  )}
                  {p.tuning && (
                    <p className="source-note">
                      {p.tuning.tuned
                        ? "Réglages comparés sur deux périodes antérieures au contrôle final."
                        : "Historique court : réglages fixes, sans recherche automatique."}
                    </p>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      ))}
    </>
  );
}
