import { useState, type FormEvent } from "react";
import { patch, post, errorMessage } from "../../api";
import { Button, Field, Notice } from "../../ui";
import { type Contact, kinds, stages } from "./types";
export default function ContactForm({
  contact,
  onSaved,
}: {
  contact?: Contact;
  onSaved: (c: Contact) => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [key, setKey] = useState(() => crypto.randomUUID());
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    const values = Object.fromEntries(new FormData(e.currentTarget));
    const body = {
      ...values,
      lead_days: Number(values.lead_days),
      min_order: Number(values.min_order),
      idempotency_key: key,
    };
    try {
      const result = contact
        ? await patch<Contact>(`/crm/contacts/${contact.id}`, {
            ...body,
            expected_version: contact.version,
          })
        : await post<Contact>("/crm/contacts", body);
      onSaved(result);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} onChange={() => setKey(crypto.randomUUID())}>
      <fieldset className="crm-fields" disabled={busy}>
        <legend className="sr-only">Coordonnées commerciales</legend>
        <Field
          label="Nom du contact"
          name="name"
          required
          maxLength={180}
          defaultValue={contact?.name}
        />
        <div className="field">
          <label htmlFor="contact-kind">Type de relation</label>
          <select
            id="contact-kind"
            name="kind"
            defaultValue={contact?.kind ?? "CUSTOMER"}
          >
            {Object.entries(kinds).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <Field
          label="Entreprise"
          name="company"
          maxLength={180}
          defaultValue={contact?.company}
        />
        <Field
          label="E-mail du contact"
          name="email"
          type="email"
          maxLength={254}
          defaultValue={contact?.email}
        />
        <Field
          label="Téléphone"
          name="phone"
          maxLength={60}
          defaultValue={contact?.phone}
        />
        <Field
          label="Adresse"
          name="address"
          maxLength={1000}
          defaultValue={contact?.address}
        />
        <div className="field">
          <label htmlFor="contact-stage">Statut commercial</label>
          <select
            id="contact-stage"
            name="stage"
            defaultValue={contact?.stage ?? "PROSPECT"}
          >
            {Object.entries(stages).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="contact-permission">
            Préférence de contact commercial
          </label>
          <select
            id="contact-permission"
            name="contact_permission"
            defaultValue={contact?.contact_permission ?? "UNKNOWN"}
          >
            <option value="UNKNOWN">Non renseignée</option>
            <option value="ALLOWED">Contact autorisé</option>
            <option value="REFUSED">Ne pas contacter</option>
          </select>
        </div>
        <Field
          label="Délai fournisseur indicatif (jours)"
          name="lead_days"
          type="number"
          min={0}
          max={3650}
          defaultValue={contact?.lead_days ?? 0}
          hint="0 : délai non renseigné. À préciser avant le réapprovisionnement."
        />
        <Field
          label="Minimum de commande indicatif (unités)"
          name="min_order"
          type="number"
          min={1}
          max={1000000}
          defaultValue={contact?.min_order ?? 1}
        />
        {contact && (
          <Field
            label="Motif de modification"
            name="reason"
            required
            maxLength={1000}
          />
        )}
      </fieldset>
      {error && <Notice>{error}</Notice>}
      <Button type="submit" disabled={busy}>
        {busy ? "Enregistrement…" : "Enregistrer la fiche"}
      </Button>
    </form>
  );
}
