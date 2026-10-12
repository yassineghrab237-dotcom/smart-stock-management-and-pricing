"""Outils du propriétaire local ; aucun secret accepté en argument de commande."""

import argparse
import getpass
from pydantic import ValidationError
from pathlib import Path
from libs.common.database import connect, now
from libs.common.maintenance import backup, restore, verify, inspect_database
from libs.common.security import hash_password
from services.auth_service.app.schemas.auth_schemas import Setup


def recover_admin(database, email, password, reason, confirmed=False):
    if not confirmed:
        raise ValueError("Confirmation explicite de récupération requise.")
    if not reason.strip():
        raise ValueError("Motif requis.")
    path = Path(database).resolve(strict=True)
    inspect_database(path)
    try:
        validated = Setup(name="Récupération locale", email=email, password=password)
    except ValidationError:
        raise ValueError(
            "Adresse ou mot de passe invalide : 12 à 256 caractères, majuscule et chiffre requis."
        ) from None
    with connect(path, write=True) as db:
        row = db.execute(
            "SELECT u.id FROM users u LEFT JOIN user_access a ON a.user_id=u.id WHERE u.email=? AND u.role='ADMIN' AND COALESCE(a.active,1)=1",
            (validated.email,),
        ).fetchone()
        if not row:
            raise ValueError(
                "Administrateur actif introuvable. Aucun compte créé ou réactivé."
            )
        db.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (hash_password(validated.password), row["id"]),
        )
        # Expire instead of deleting session records; no business data removed.
        for table in ("sessions", "mobile_sessions"):
            db.execute(f"UPDATE {table} SET expires_at=0 WHERE user_id=?", (row["id"],))
        db.execute(
            "INSERT INTO local_recovery_events(user_id,reason,created_at) VALUES (?,?,?)",
            (row["id"], reason.strip(), now()),
        )
    return row["id"]


def main():
    parser = argparse.ArgumentParser(
        description="Maintenance locale Precios, sans écrasement de base."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["backup", "restore-copy"]:
        p = commands.add_parser(name)
        p.add_argument("--source", required=True)
        p.add_argument("--destination", required=True)
    p = commands.add_parser("verify")
    p.add_argument("--source", required=True)
    p = commands.add_parser("recover-admin")
    p.add_argument("--database", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--confirm-reset", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            result = backup(args.source, args.destination)
        elif args.command == "restore-copy":
            result = restore(args.source, args.destination)
        elif args.command == "verify":
            result = verify(args.source)
        else:
            if not args.confirm_reset:
                raise ValueError(
                    "Ajoutez --confirm-reset pour autoriser le remplacement du mot de passe et l’expiration des sessions de ce compte."
                )
            password = getpass.getpass("Nouveau mot de passe (masqué) : ")
            if password != getpass.getpass("Confirmer le mot de passe (masqué) : "):
                raise ValueError("Les mots de passe diffèrent.")
            recover_admin(args.database, args.email, password, args.reason, True)
            print(
                "Accès administrateur réinitialisé. Sessions expirées, données conservées."
            )
            return
        print(
            f"Vérification réussie : {result['filename']} ; SHA-256 {result['sha256']}"
        )
    except (ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
