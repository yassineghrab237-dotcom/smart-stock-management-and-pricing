import { useState } from "react";
import { date, errorMessage, post } from "../../api";
import { Button, Notice, ResourceState, useResource } from "../../ui";
interface Backup {
  filename: string;
  verified: boolean;
  created_at?: string;
  sha256?: string;
  tables?: Record<string, number>;
}
export default function MaintenancePage() {
  const [revision, setRevision] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [success, setSuccess] = useState("");
  const resource = useResource<{ items: Backup[] }>(
    "/maintenance/backups",
    revision,
  );
  async function create() {
    if (busy) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await post("/maintenance/backups", {});
      setRevision((v) => v + 1);
      setSuccess(
        "Copie SQLite créée et vérifiée. Téléchargez la base et son manifeste pour la conserver ailleurs.",
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="commercial-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">ADMINISTRATION · CONTINUITÉ</span>
          <h1>Sauvegardes locales</h1>
          <p>
            Conservez une copie cohérente et vérifiez-la avant de la restaurer.
          </p>
        </div>
        <Button disabled={busy} onClick={create}>
          {busy ? "Sauvegarde en cours…" : "Créer une sauvegarde vérifiée"}
        </Button>
      </div>
      <section className="commercial-panel">
        <h2>Conserver et restaurer</h2>
        <p>
          La sauvegarde comprend les produits, ventes, CRM et comptes de cette
          base. Elle contient des données confidentielles et n’est pas chiffrée
          : conservez les deux fichiers dans un emplacement protégé. Une copie
          sur ce même disque ne protège pas contre sa panne.
        </p>
        <p>
          La restauration se fait vers un nouveau fichier, avec la commande
          locale documentée dans docs/MAINTENANCE.md. La base en cours n’est
          jamais remplacée. Les modèles ML et fichiers du projet se sauvegardent
          séparément.
        </p>
      </section>
      {error && <Notice>{error}</Notice>}
      {success && <Notice success>{success}</Notice>}
      <ResourceState {...resource} />
      {resource.data?.items.length === 0 && (
        <section className="commercial-panel">
          <h2>Aucune sauvegarde créée</h2>
          <p>
            Créez une première copie avant de commencer à saisir vos données
            réelles.
          </p>
        </section>
      )}
      {resource.data?.items.map((b) => (
        <article className="commercial-panel" key={b.filename}>
          <h2>{b.created_at ? date(b.created_at) : "Copie à vérifier"}</h2>
          <p>{b.filename}</p>
          {b.verified ? (
            <>
              <p>
                Intégrité SQLite, références et empreinte SHA-256 vérifiées.
              </p>
              <div className="commercial-actions">
                <a
                  className="button secondary"
                  download
                  href={`/api/maintenance/backups/${b.filename}/database`}
                >
                  Télécharger la base SQLite
                </a>
                <a
                  className="button secondary"
                  download
                  href={`/api/maintenance/backups/${b.filename}/manifest`}
                >
                  Télécharger le manifeste
                </a>
              </div>
            </>
          ) : (
            <Notice>
              Copie incomplète ou modifiée. Téléchargement désactivé ; créez une
              nouvelle sauvegarde.
            </Notice>
          )}
        </article>
      ))}
    </div>
  );
}
