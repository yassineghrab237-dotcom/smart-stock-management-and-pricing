"""Sauvegardes cohérentes SQLite, vérification et restauration sans écrasement."""

from contextlib import closing
import hashlib
import json
import sqlite3
from pathlib import Path
from libs.common.database import now


def manifest_path(path):
    return Path(str(path) + ".manifest.json")


def inspect_database(path):
    try:
        return _inspect_database(path)
    except sqlite3.DatabaseError as exc:
        raise ValueError("Fichier SQLite illisible ou endommagé.") from exc


def _inspect_database(path):
    path = Path(path).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("La base échoue au contrôle d’intégrité.")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("La base contient des références incohérentes.")
        tables = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        if not {"users", "products", "movements"}.issubset(tables):
            raise ValueError("Ce fichier ne contient pas une base Precios reconnue.")
        counts = {
            name: db.execute(
                'SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"'
            ).fetchone()[0]
            for name in tables
        }
    return counts


def checksum(path):
    result = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def backup(source, destination):
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve()
    if (
        destination == source
        or destination.exists()
        or manifest_path(destination).exists()
    ):
        raise ValueError("Destination déjà présente : aucun fichier ne sera remplacé.")
    inspect_database(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive reservation prevents overwriting a concurrently created file.
    with destination.open("xb"):
        pass
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(destination)) as dest:
            src.backup(dest)
    counts = inspect_database(destination)
    manifest = dict(
        format="precios-sqlite-v1",
        created_at=now(),
        filename=destination.name,
        sha256=checksum(destination),
        tables=counts,
    )
    with manifest_path(destination).open("x", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


def verify(source):
    source = Path(source).resolve(strict=True)
    manifest = json.loads(manifest_path(source).read_text(encoding="utf-8"))
    if manifest.get("format") != "precios-sqlite-v1" or manifest.get(
        "sha256"
    ) != checksum(source):
        raise ValueError("Empreinte de sauvegarde invalide ou format inconnu.")
    if manifest.get("tables") != inspect_database(source):
        raise ValueError("Le contenu ne correspond plus au manifeste.")
    return manifest


def restore(source, destination):
    verify(source)
    # Restores into a NEW database; never modifies the running database.
    return backup(source, destination)
