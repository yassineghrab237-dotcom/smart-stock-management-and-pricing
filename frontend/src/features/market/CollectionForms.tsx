import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { post, errorMessage } from "../../api";
import { Button, Field, Notice } from "../../ui";
import type { Identity, Job } from "./collectionTypes";

export function MutationForm({
  path,
  body,
  children,
  label,
  onSaved,
}: {
  path: string;
  body: (data: FormData) => object;
  children?: ReactNode;
  label: string;
  onSaved: () => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [success, setSuccess] = useState("");
  const pending = useRef<{ payload: string; key: string } | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const values = body(new FormData(event.currentTarget));
    const payload = JSON.stringify({ path, values });
    if (pending.current?.payload !== payload)
      pending.current = { payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await post(path, { ...values, idempotency_key: pending.current.key });
      setSuccess("Enregistré.");
      pending.current = null;
      onSaved();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <fieldset disabled={busy} className="collection-fields">
        <legend className="sr-only">{label}</legend>
        {children}
        <Button type="submit" disabled={busy}>
          {busy ? "Enregistrement…" : label}
        </Button>
      </fieldset>
      {error && <Notice>{error}</Notice>}
      {success && <Notice success>{success}</Notice>}
    </form>
  );
}
export function IdentityForm({
  productId,
  identity,
  onSaved,
}: {
  productId: number;
  identity: Identity | null;
  onSaved: () => void;
}) {
  return (
    <MutationForm
      path={`/collection/products/${productId}/identity`}
      label="Enregistrer l’identité"
      onSaved={onSaved}
      body={(d) => ({
        ...Object.fromEntries(d),
        expected_version: identity?.version ?? 0,
      })}
    >
      <Field
        label="Marque canonique"
        name="brand"
        required
        maxLength={160}
        defaultValue={identity?.brand}
      />
      <Field
        label="Référence constructeur canonique"
        name="manufacturer_ref"
        required
        maxLength={160}
        defaultValue={identity?.manufacturer_ref}
      />
      <Field
        label="GTIN / EAN"
        name="gtin"
        maxLength={14}
        defaultValue={identity?.gtin}
        hint="Facultatif. Clé de contrôle vérifiée ; ne pas saisir le SKU du marchand."
      />
      <Field
        label="Configuration, état et garantie"
        name="variant"
        required
        maxLength={400}
        defaultValue={identity?.variant}
      />
      <Field
        label="Motif de définition de l’identité"
        name="reason"
        required
        maxLength={1000}
      />
    </MutationForm>
  );
}
export function WatchForm({
  productId,
  onSaved,
}: {
  productId: number;
  onSaved: () => void;
}) {
  return (
    <MutationForm
      path={`/collection/products/${productId}/watches`}
      label="Activer cette surveillance"
      onSaved={onSaved}
      body={(d) => ({
        ...Object.fromEntries(d),
        interval_hours: Number(d.get("interval_hours")),
      })}
    >
      <label className="field">
        Enseigne à collecter
        <select name="retailer">
          <option>Tunisianet</option>
          <option>Mytek</option>
          <option>Spacenet</option>
        </select>
      </label>
      <Field
        label="URL publique à collecter"
        name="source_url"
        type="url"
        required
        maxLength={2000}
        hint="Lien direct d’une fiche produit, sans paramètres de recherche."
      />
      <Field
        label="Intervalle de collecte (heures)"
        name="interval_hours"
        type="number"
        required
        min={6}
        max={168}
        defaultValue={24}
      />
    </MutationForm>
  );
}
export function ReviewForm({
  job,
  onSaved,
}: {
  job: Job;
  onSaved: () => void;
}) {
  return (
    <MutationForm
      path={`/collection/jobs/${job.id}/review`}
      label="Enregistrer la décision"
      onSaved={onSaved}
      body={(d) => ({
        accept: d.get("decision") === "accept",
        tax_basis: d.get("tax_basis"),
        availability: d.get("availability"),
        delivery: d.get("delivery") || null,
        note: d.get("note"),
      })}
    >
      <label className="field">
        Décision de rapprochement
        <select name="decision" defaultValue="reject">
          <option value="reject">Refuser cette offre</option>
          <option value="accept">
            Confirmer le produit et la variante exacte
          </option>
        </select>
      </label>
      <label className="field">
        Taxes vérifiées sur la fiche
        <select
          name="tax_basis"
          defaultValue={job.result?.tax_basis ?? "UNKNOWN"}
        >
          <option value="UNKNOWN">Base inconnue</option>
          <option value="TTC">TTC</option>
          <option value="HT">HT</option>
        </select>
      </label>
      {job.result?.availability === "UNKNOWN" && (
        <label className="field">
          Disponibilité vérifiée sur la fiche
          <select name="availability" defaultValue="UNKNOWN">
            <option value="UNKNOWN">Inconnue</option>
            <option value="IN_STOCK">En stock annoncé</option>
            <option value="OUT_OF_STOCK">Rupture annoncée</option>
          </select>
        </label>
      )}
      <Field
        label="Livraison vérifiée pour une unité"
        name="delivery"
        inputMode="decimal"
        pattern="[0-9]+([.][0-9]{1,4})?"
        hint="Vide = inconnue ; 0 seulement si gratuité vérifiée."
      />
      <Field
        label="Preuve et motif de rapprochement"
        name="note"
        required
        maxLength={900}
        hint="Vérifiez référence, mémoire, stockage, état et garantie. Une référence absente n’est pas une correspondance prouvée."
      />
    </MutationForm>
  );
}
