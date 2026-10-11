import { useState } from "react";
import { post, errorMessage, type User } from "../../api";
import { Badge, Button, Field, Modal, Notice } from "../../ui";
export function AccountActions({
  user,
  actorId,
  refresh,
}: {
  user: User;
  actorId: number;
  refresh: () => void;
}) {
  const [action, setAction] = useState<"access" | "revoke" | null>(null);
  const [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [success, setSuccess] = useState("");
  async function confirm() {
    if (busy || !action) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const result = await post<{ detail: string }>(
        `/auth/users/${user.id}/${action === "access" ? "access" : "revoke-sessions"}`,
        action === "access" ? { active: user.active === false, reason } : {},
      );
      setAction(null);
      setSuccess(result.detail);
      refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="account-actions">
      <Badge tone={user.active === false ? "danger" : "success"}>
        {user.active === false ? "Désactivé" : "Actif"}
      </Badge>
      {user.id !== actorId && (
        <Button
          variant="secondary"
          onClick={() => {
            setAction("access");
            setReason("");
            setError("");
          }}
        >
          {user.active === false ? "Réactiver" : "Désactiver"}
        </Button>
      )}
      <Button
        variant="ghost"
        onClick={() => {
          setAction("revoke");
          setError("");
        }}
      >
        Déconnecter partout
      </Button>
      {success && <Notice success>{success}</Notice>}
      {action && (
        <Modal
          title={
            action === "revoke"
              ? "Déconnecter ce compte partout ?"
              : user.active === false
                ? "Réactiver ce compte ?"
                : "Désactiver ce compte ?"
          }
          onClose={() => {
            if (!busy) setAction(null);
          }}
        >
          <p>
            {action === "revoke"
              ? "Les sessions web et mobile seront fermées. Le compte et ses historiques restent conservés."
              : user.active === false
                ? "Le compte pourra se connecter de nouveau. Les anciennes sessions restent fermées."
                : "Le compte ne pourra plus se connecter. Ses sessions seront fermées. Les produits et historiques seront conservés."}
          </p>
          {action === "access" && (
            <Field
              label="Motif du changement d’accès"
              value={reason}
              maxLength={1000}
              disabled={busy}
              onChange={(e) => setReason(e.target.value)}
            />
          )}
          {error && <Notice>{error}</Notice>}
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => setAction(null)}
          >
            Annuler
          </Button>
          <Button
            disabled={busy || (action === "access" && !reason.trim())}
            onClick={confirm}
          >
            {busy ? "Traitement…" : "Confirmer le changement"}
          </Button>
        </Modal>
      )}
    </div>
  );
}
