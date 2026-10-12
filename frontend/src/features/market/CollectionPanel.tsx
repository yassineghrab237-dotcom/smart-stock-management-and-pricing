import { useState } from "react";
import { date, money } from "../../api";
import {
  Badge,
  Button,
  Empty,
  Notice,
  ResourceState,
  useResource,
} from "../../ui";
import {
  IdentityForm,
  WatchForm,
  MutationForm,
  ReviewForm,
} from "./CollectionForms";
import type { CollectionState } from "./collectionTypes";
const states: Record<string, string> = {
  QUEUED: "En attente",
  RUNNING: "En cours",
  SUCCEEDED: "Offre extraite",
  FAILED: "Échec",
  BLOCKED: "Accès différé",
  INTERRUPTED: "Interrompue",
};
export default function CollectionPanel({
  productId,
  write,
  onObservation,
}: {
  productId: number;
  write: boolean;
  onObservation: () => void;
}) {
  const [revision, setRevision] = useState(0);
  const data = useResource<CollectionState>(
    `/collection/products/${productId}`,
    revision,
  );
  const refresh = () => setRevision((v) => v + 1);
  return (
    <section className="market-card collection-panel">
      <div className="collection-heading">
        <div>
          <span className="eyebrow">COLLECTE PUBLIQUE</span>
          <h2>Surveiller les offres</h2>
        </div>
        <Button variant="secondary" onClick={refresh}>
          Actualiser les collectes
        </Button>
      </div>
      <p>
        Les fiches activées sont consultées pendant le fonctionnement du serveur
        local. Chaque offre extraite doit être validée avant comparaison.
      </p>
      <ResourceState {...data} />
      {data.data && (
        <>
          <Badge tone={data.data.worker_running ? "success" : "warning"}>
            {data.data.worker_running
              ? "Service local en marche"
              : "Service de collecte arrêté"}
          </Badge>
          {!data.data.worker_running && (
            <p>
              Les demandes restent dans la file. Démarrez le serveur avec la
              collecte activée pour les exécuter.
            </p>
          )}
          <details className="collection-details" open={!data.data.identity}>
            <summary>
              1. Identité de référence{" "}
              {data.data.identity &&
                `· ${data.data.identity.brand} ${data.data.identity.manufacturer_ref}`}
            </summary>
            {data.data.identity && (
              <p>
                {data.data.identity.variant} · GTIN{" "}
                {data.data.identity.gtin || "non renseigné"}
              </p>
            )}
            {write ? (
              <IdentityForm
                key={data.data.identity?.version ?? 0}
                productId={productId}
                identity={data.data.identity}
                onSaved={refresh}
              />
            ) : (
              !data.data.identity && <Notice>Identité non renseignée.</Notice>
            )}
          </details>
          {write && data.data.identity && (
            <details className="collection-details">
              <summary>2. Ajouter une fiche à surveiller</summary>
              <WatchForm productId={productId} onSaved={refresh} />
            </details>
          )}
          {!data.data.watches.length ? (
            <Empty title="Aucune fiche activée">
              Définissez l’identité puis ajoutez les URL des produits
              équivalents.
            </Empty>
          ) : (
            <div className="collection-list">
              {data.data.watches.map((w) => (
                <article key={w.id}>
                  <div className="collection-heading">
                    <strong>{w.retailer}</strong>
                    <Badge tone={w.enabled ? "success" : "neutral"}>
                      {w.enabled ? "Active" : "En pause"}
                    </Badge>
                  </div>
                  <a href={w.source_url} target="_blank" rel="noreferrer">
                    {w.source_url}
                  </a>
                  <p>
                    Toutes les {w.interval_hours} h · prochaine échéance{" "}
                    {date(w.next_due)}
                  </p>
                  {write && (
                    <div className="collection-actions">
                      <MutationForm
                        path={`/collection/watches/${w.id}/state`}
                        body={() => ({
                          enabled: !w.enabled,
                          expected_version: w.version,
                        })}
                        label={
                          w.enabled
                            ? "Mettre en pause"
                            : "Reprendre la surveillance"
                        }
                        onSaved={refresh}
                      />
                      {!!w.enabled && (
                        <MutationForm
                          path={`/collection/watches/${w.id}/run`}
                          body={() => ({})}
                          label="Collecter maintenant"
                          onSaved={refresh}
                        />
                      )}
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
          <h3>Résultats et contrôles</h3>
          {!data.data.jobs.length && (
            <p>
              Aucune collecte exécutée. Après activation, actualisez dans
              quelques instants.
            </p>
          )}
          <div className="collection-list">
            {data.data.jobs.map((job) => (
              <article key={job.id}>
                <div className="collection-heading">
                  <strong>
                    {job.retailer} · collecte #{job.id}
                  </strong>
                  <Badge
                    tone={
                      job.status === "SUCCEEDED"
                        ? "success"
                        : job.status === "FAILED"
                          ? "danger"
                          : "warning"
                    }
                  >
                    {states[job.status] ?? job.status}
                  </Badge>
                </div>
                <p>
                  {date(job.created_at)} · {job.message}
                </p>
                {job.result && (
                  <>
                    <h4>{job.result.name}</h4>
                    <p className="collection-price">
                      {money(job.result.price)} {job.result.currency} ·{" "}
                      {job.result.tax_basis === "UNKNOWN"
                        ? "taxes à vérifier"
                        : job.result.tax_basis}
                    </p>
                    <p>
                      Référence constructeur :{" "}
                      {job.result.manufacturer_ref || "absente de la page"} ·
                      GTIN : {job.result.gtin || "absent"}
                    </p>
                    <p>
                      Code marchand : {job.result.merchant_sku || "absent"} ·{" "}
                      {job.result.availability === "IN_STOCK"
                        ? "Stock annoncé disponible"
                        : job.result.availability === "OUT_OF_STOCK"
                          ? "Rupture annoncée"
                          : "Disponibilité inconnue"}
                    </p>
                    <a
                      href={job.result.source_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Vérifier la fiche d’origine
                    </a>
                    <details>
                      <summary>Traçabilité de l’extraction</summary>
                      <p>
                        Observé le {date(job.result.observed_at)} ·{" "}
                        {job.result.parser_version}
                      </p>
                      <p>Empreinte page : {job.result.content_sha256}</p>
                      <p>Empreinte robots : {job.result.robots_sha256}</p>
                    </details>
                    {job.review_state === "PENDING" && write ? (
                      <details className="collection-details">
                        <summary>Valider ou refuser le rapprochement</summary>
                        <ReviewForm
                          job={job}
                          onSaved={() => {
                            refresh();
                            onObservation();
                          }}
                        />
                      </details>
                    ) : (
                      <Badge>
                        {job.review_state === "ACCEPTED"
                          ? "Offre validée"
                          : job.review_state === "REJECTED"
                            ? "Offre refusée"
                            : "Validation requise"}
                      </Badge>
                    )}
                  </>
                )}
              </article>
            ))}
          </div>
          <details className="collection-details">
            <summary>Historique des décisions</summary>
            {data.data.events.map((e) => (
              <p key={e.id}>
                {date(e.created_at)} · {e.actor_name} ·{" "}
                {e.detail.startsWith("{")
                  ? "Identité produit définie ou révisée."
                  : e.detail}
              </p>
            ))}
          </details>
        </>
      )}
    </section>
  );
}
