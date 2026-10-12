import { useState } from "react";
import { post, errorMessage, money } from "../../api";
import {
  Badge,
  Button,
  Field,
  Modal,
  Notice,
  ResourceState,
  useResource,
} from "../../ui";

type Kind = "catalogue" | "sales" | "transactions";
interface Source {
  kind: Kind;
  csv_text: string;
  filename: string;
  delimiter: "," | ";";
}
interface Preview {
  valid: boolean;
  count: number;
  preview_token: string;
  message?: string;
  rows: {
    line: number;
    sku: string;
    label: string;
    errors: string[];
    data: Record<string, string | number | null> | null;
  }[];
}
interface ImportEntry {
  id: number;
  kind: Kind;
  filename: string;
  row_count: number;
  actor_name: string;
  created_at: string;
}
interface Sale {
  id: number;
  reference: string;
  sku: string;
  product_name: string;
  sold_on: string;
  quantity: number;
  unit_price: string;
}
const templates = {
  transactions:
    "reference,sku,sold_on,quantity,unit_price_ttc,tax_rate,discount_ttc,unit_cost_ht,customer_id\n",
  catalogue:
    "sku,name,category,unit,cost_price,current_price,min_price,threshold_min,threshold_max\n",
  sales: "reference,sku,sold_on,quantity,unit_price\n",
};
const labels: Record<string, string> = {
  unit_price_ttc: "Prix unitaire TTC (TND)",
  tax_rate: "Taxe (%)",
  discount_ttc: "Remise unitaire TTC (TND)",
  unit_cost_ht: "Coût unitaire HT (TND)",
  customer_id: "Identifiant client CRM",
  stock_before: "Stock actuel",
  stock_after_batch: "Stock après tout le fichier",
  name: "Nom",
  category: "Catégorie",
  unit: "Unité",
  cost_price: "Coût",
  current_price: "Prix actuel",
  min_price: "Prix minimum",
  threshold_min: "Seuil minimum",
  threshold_max: "Seuil maximum",
  reference: "Référence vente",
  sold_on: "Date de vente",
  quantity: "Quantité",
  unit_price: "Prix unitaire",
};

export default function ImportsPage({
  write,
  refresh,
}: {
  write: boolean;
  refresh: () => void;
}) {
  const [kind, setKind] = useState<Kind>("catalogue");
  const [delimiter, setDelimiter] = useState<"," | ";">(",");
  const [source, setSource] = useState<Source | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [revision, setRevision] = useState(0);
  const history = useResource<{ items: ImportEntry[] }>("/imports", revision);
  const sales = useResource<{ items: Sale[] }>("/imports/sales", revision);

  async function select(file?: File) {
    setSource(null);
    setPreview(null);
    setError("");
    setSuccess("");
    if (!file) return;
    setBusy(true);
    try {
      if (file.size > 1000000)
        throw new Error("Le fichier doit faire au maximum 1 Mo.");
      const csv_text = new TextDecoder("utf-8", { fatal: true }).decode(
        await file.arrayBuffer(),
      );
      setSource({ kind, delimiter, csv_text, filename: file.name });
    } catch {
      setError(
        "Impossible de lire le fichier : utilisez un CSV UTF-8 de moins de 1 Mo.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function analyze() {
    if (!source || busy) return;
    setBusy(true);
    setError("");
    setSuccess("");
    setPreview(null);
    try {
      setPreview(await post<Preview>("/imports/preview", source));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function commit() {
    if (!source || !preview?.valid || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await post<{ count: number; already_imported: boolean }>(
        "/imports/commit",
        { ...source, preview_token: preview.preview_token },
      );
      setSuccess(
        result.already_imported
          ? "Ce fichier avait déjà été enregistré. Aucune ligne ajoutée."
          : `${result.count} ligne(s) importée(s). ${kind === "transactions" ? "Ventes confirmées et stock décrémenté. Consultez Ventes et devis." : kind === "sales" ? "Le stock actuel est conservé." : "Les nouveaux produits ont un stock de zéro."}`,
      );
      setConfirm(false);
      setPreview(null);
      setSource(null);
      setRevision((v) => v + 1);
      refresh();
    } catch (e) {
      setError(
        `${errorMessage(e)} En cas de réponse perdue, réessayez sans changer le fichier : les doublons sont empêchés côté serveur.`,
      );
      setConfirm(false);
    } finally {
      setBusy(false);
    }
  }
  function changeKind(next: Kind) {
    setKind(next);
    setSource(null);
    setPreview(null);
    setError("");
    setSuccess("");
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">DONNÉES MÉTIER</span>
          <h1>Imports CSV</h1>
          <p>
            Vérifiez chaque ligne avant d’enregistrer votre catalogue ou vos
            ventes.
          </p>
        </div>
      </div>
      {success && <Notice success>{success}</Notice>}
      {error && <Notice>{error}</Notice>}
      {write && (
        <section className="panel import-panel">
          <div
            className="import-options"
            role="group"
            aria-label="Type d’import"
          >
            <Button
              variant={kind === "catalogue" ? "primary" : "secondary"}
              aria-pressed={kind === "catalogue"}
              disabled={busy}
              onClick={() => changeKind("catalogue")}
            >
              Catalogue produits
            </Button>
            <Button
              variant={kind === "sales" ? "primary" : "secondary"}
              aria-pressed={kind === "sales"}
              disabled={busy}
              onClick={() => changeKind("sales")}
            >
              Historique des ventes
            </Button>
            <Button
              variant={kind === "transactions" ? "primary" : "secondary"}
              aria-pressed={kind === "transactions"}
              disabled={busy}
              onClick={() => changeKind("transactions")}
            >
              Ventes avec sortie de stock
            </Button>
          </div>
          <h2>
            {kind === "catalogue"
              ? "Ajouter de nouveaux produits"
              : kind === "transactions"
                ? "Importer des ventes avec sortie de stock"
                : "Importer les ventes passées"}
          </h2>
          <p>
            {kind === "catalogue"
              ? "Les SKU existants sont refusés. Aucun produit n’est remplacé et le stock initial reste à zéro."
              : kind === "transactions"
                ? "Ventes en TND : prix et remise unitaires TTC, taxe par ligne, coût HT facultatif. Même référence pour les lignes du même panier ; date et client identiques. customer_id est l’identifiant CRM, facultatif. Le stock sera décrémenté maintenant : n’importez pas ici des ventes dont la sortie de stock est déjà enregistrée."
                : "Chaque SKU doit correspondre exactement à un produit existant. Les ventes passées ne déclenchent aucun mouvement et ne modifient pas le stock actuel."}
          </p>
          <p>
            CSV UTF-8 · 1 Mo maximum · 1 000 lignes maximum · montants avec un
            point décimal, sans devise. Toute ligne invalide bloque
            l’intégralité de l’import.
          </p>
          <a
            className="button secondary"
            download={`modele-${kind}.csv`}
            href={`data:text/csv;charset=utf-8,${encodeURIComponent(templates[kind].replaceAll(",", delimiter))}`}
          >
            Télécharger le modèle CSV
          </a>
          <div className="field">
            <label htmlFor="import-delimiter">Séparateur</label>
            <select
              id="import-delimiter"
              value={delimiter}
              disabled={busy}
              onChange={(e) => {
                const next = e.target.value as "," | ";";
                setDelimiter(next);
                setPreview(null);
                setSource((s) => (s ? { ...s, delimiter: next } : null));
              }}
            >
              <option value=",">Virgule (,)</option>
              <option value=";">Point-virgule (;)</option>
            </select>
          </div>
          <Field
            key={`${kind}-${revision}`}
            label="Fichier CSV"
            type="file"
            accept=".csv,text/csv"
            disabled={busy}
            onChange={(e) => void select(e.target.files?.[0])}
          />
          {source && (
            <p>
              Fichier sélectionné : <strong>{source.filename}</strong>
            </p>
          )}
          <Button disabled={!source || busy} onClick={analyze}>
            {busy ? "Traitement en cours…" : "Analyser le fichier"}
          </Button>
          {preview && (
            <div className="import-preview">
              <h2>Aperçu : {preview.count} ligne(s)</h2>
              <Badge tone={preview.valid ? "success" : "danger"}>
                {preview.valid
                  ? "Toutes les lignes sont valides"
                  : "Import bloqué"}
              </Badge>
              {preview.message && <Notice>{preview.message}</Notice>}
              <div
                className="import-rows"
                tabIndex={0}
                aria-label="Lignes de l’aperçu CSV"
              >
                {preview.rows.map((row) => (
                  <article className="import-row" key={row.line}>
                    <strong>
                      Ligne {row.line} · {row.sku || "SKU manquant"}
                    </strong>
                    <span>{row.label}</span>
                    {row.data && (
                      <dl>
                        {Object.entries(row.data)
                          .filter(
                            ([key, value]) => labels[key] && value !== null,
                          )
                          .map(([key, value]) => (
                            <div key={key}>
                              <dt>{labels[key]}</dt>
                              <dd>{String(value)}</dd>
                            </div>
                          ))}
                      </dl>
                    )}
                    {row.errors.map((message, index) => (
                      <p className="import-error" key={index}>
                        {message}
                      </p>
                    ))}
                  </article>
                ))}
              </div>
              <Button
                disabled={!preview.valid || busy}
                onClick={() => setConfirm(true)}
              >
                Vérifier et confirmer l’import
              </Button>
            </div>
          )}
        </section>
      )}
      <section className="panel import-panel">
        <h2>Imports enregistrés</h2>
        <p>Les 100 derniers imports, avec leur auteur et leur date.</p>
        <ResourceState {...history} />
        {history.data &&
          (history.data.items.length ? (
            <div className="import-rows">
              {history.data.items.map((entry) => (
                <article className="import-row" key={entry.id}>
                  <strong>{entry.filename}</strong>
                  <span>
                    {entry.kind === "transactions"
                      ? "Ventes avec sortie de stock"
                      : entry.kind === "sales"
                        ? "Ventes historiques"
                        : "Catalogue"}{" "}
                    · {entry.row_count} ligne(s) · {entry.actor_name}
                  </span>
                  <time>
                    {new Date(entry.created_at).toLocaleString("fr-FR")}
                  </time>
                </article>
              ))}
            </div>
          ) : (
            <p>Aucun import enregistré.</p>
          ))}
      </section>
      <section className="panel import-panel">
        <h2>Ventes historiques importées sans mouvement</h2>
        <p>
          Les 100 dernières ventes par date. Cet historique reste séparé des
          mouvements de stock ; les recommandations IA restent indisponibles
          jusqu’à validation des données et des modèles.
        </p>
        <ResourceState {...sales} />
        {sales.data &&
          (sales.data.items.length ? (
            <div className="import-rows">
              {sales.data.items.map((sale) => (
                <article className="import-row" key={sale.id}>
                  <strong>
                    {sale.reference} · {sale.product_name}
                  </strong>
                  <span>
                    {sale.sku} · {sale.sold_on}
                  </span>
                  <span>
                    {sale.quantity} unité(s) · Prix unitaire :{" "}
                    {money(sale.unit_price)}
                  </span>
                </article>
              ))}
            </div>
          ) : (
            <p>Aucune vente importée.</p>
          ))}
      </section>
      {confirm && preview && (
        <Modal
          title="Confirmer l’import CSV"
          onClose={() => {
            if (!busy) setConfirm(false);
          }}
        >
          <p>
            Enregistrer <strong>{preview.count} ligne(s)</strong> depuis{" "}
            {source?.filename} ?
          </p>
          <p>
            {kind === "transactions"
              ? "Les ventes seront confirmées et les quantités retirées du stock actuel. Vérifiez qu’elles n’ont jamais été enregistrées, y compris sous d’autres références. Le lot complet est annulé si une ligne échoue."
              : kind === "sales"
                ? "Les ventes sont ajoutées à l’historique. Le stock actuel ne change pas."
                : "Les produits seront créés à stock zéro."}
          </p>
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => setConfirm(false)}
          >
            Retour à l’aperçu
          </Button>
          <Button disabled={busy} onClick={commit}>
            {busy ? "Enregistrement…" : "Confirmer l’enregistrement"}
          </Button>
        </Modal>
      )}
    </>
  );
}
