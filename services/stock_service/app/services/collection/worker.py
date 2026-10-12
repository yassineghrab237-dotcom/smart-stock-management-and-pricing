"""File SQLite durable, un GET borné par fiche ; aucune application automatique de prix."""

import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from libs.common.database import connect, now
from .network import DOMAINS, CollectionError, fetch
from .parser import extract
from .robots import rules

log = logging.getLogger(__name__)


def audit(db, product_id, detail, actor):
    db.execute(
        "INSERT INTO collection_events(product_id,detail,actor_id,created_at) VALUES (?,?,?,?)",
        (product_id, detail, actor, now()),
    )


def enqueue(db, watch, actor):
    identity = db.execute(
        "SELECT version FROM product_identities WHERE product_id=?",
        (watch["product_id"],),
    ).fetchone()
    if not identity:
        raise CollectionError("Identité produit à renseigner avant collecte.")
    cursor = db.execute(
        "INSERT INTO collection_jobs(watch_id,watch_version,identity_version,status,message,created_at,actor_id) VALUES (?,?,?,'QUEUED',?,?,?)",
        (
            watch["id"],
            watch["version"],
            identity["version"],
            "Collecte en attente du service local.",
            now(),
            actor,
        ),
    )
    next_due = (
        datetime.now(timezone.utc) + timedelta(hours=watch["interval_hours"])
    ).isoformat()
    db.execute(
        "UPDATE collection_watches SET next_due=? WHERE id=?", (next_due, watch["id"])
    )
    return cursor.lastrowid


def claim(path):
    with connect(path, write=True) as db:
        # A dead worker cannot strand an active job forever. No immediate retry storm.
        stale = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        db.execute(
            "UPDATE collection_jobs SET status='INTERRUPTED',message='Service interrompu ; relance manuelle ou prochaine échéance.',finished_at=? WHERE status='RUNNING' AND started_at<?",
            (now(), stale),
        )
        due = db.execute(
            """SELECT w.* FROM collection_watches w JOIN users u ON u.id=w.actor_id
            LEFT JOIN user_access a ON a.user_id=u.id WHERE w.enabled=1 AND w.next_due<=?
            AND u.role IN ('ADMIN','MANAGER') AND COALESCE(a.active,1)=1
            AND NOT EXISTS(SELECT 1 FROM collection_jobs j WHERE j.watch_id=w.id AND j.status IN ('QUEUED','RUNNING'))
            ORDER BY w.next_due,w.id LIMIT 20""",
            (now(),),
        ).fetchall()
        for watch in due:
            enqueue(db, watch, watch["actor_id"])
        job = db.execute(
            "SELECT j.*,w.product_id,w.retailer,w.source_url,w.enabled,w.version current_version FROM collection_jobs j JOIN collection_watches w ON w.id=j.watch_id WHERE j.status='QUEUED' ORDER BY j.id LIMIT 1"
        ).fetchone()
        if not job:
            return None
        job = dict(job)
        actor = db.execute(
            "SELECT u.role,COALESCE(a.active,1) active FROM users u LEFT JOIN user_access a ON a.user_id=u.id WHERE u.id=?",
            (job["actor_id"],),
        ).fetchone()
        if (
            not job["enabled"]
            or job["watch_version"] != job["current_version"]
            or not actor["active"]
            or actor["role"] not in ("ADMIN", "MANAGER")
        ):
            db.execute(
                "UPDATE collection_jobs SET status='INTERRUPTED',message='Surveillance ou accès modifié avant exécution.',finished_at=? WHERE id=?",
                (now(), job["id"]),
            )
            return None
        job["started_at"] = now()
        db.execute(
            "UPDATE collection_jobs SET status='RUNNING',started_at=?,message='Lecture de robots.txt et de la fiche publique.' WHERE id=?",
            (job["started_at"], job["id"]),
        )
        return job


def reserve(path, retailer, delay, stop):
    with connect(path, write=True) as db:
        row = db.execute(
            "SELECT next_request FROM collection_hosts WHERE retailer=?", (retailer,)
        ).fetchone()
        start = max(time.time(), row["next_request"] if row else 0)
        db.execute(
            "INSERT INTO collection_hosts VALUES (?,?) ON CONFLICT(retailer) DO UPDATE SET next_request=excluded.next_request",
            (retailer, start + delay),
        )
    if stop.wait(max(0, start - time.time())):
        raise CollectionError("Collecte interrompue à l’arrêt du service.")


def run_one(path, fetcher=fetch, stop=None, throttle=True):
    stop = stop or threading.Event()
    job = claim(path)
    if not job:
        return False
    result = None
    status = "FAILED"
    message = "Collecte non aboutie."
    try:
        retailer = job["retailer"]

        def pace(target):
            if throttle:
                reserve(path, retailer, 10, stop)

        _, raw_rules = fetcher(
            retailer,
            "https://" + urlsplit(job["source_url"]).hostname + "/robots.txt",
            before_request=pace,
            max_bytes=512000,
        )
        robots = raw_rules.decode("utf-8-sig", errors="replace")
        if "<html" in robots[:1000].lower() or "<!doctype" in robots[:1000].lower():
            raise CollectionError(
                "robots.txt renvoie une page HTML ; collecte différée."
            )
        if not rules(robots, job["source_url"])[0]:
            raise CollectionError("Fiche exclue par robots.txt ; collecte arrêtée.")

        def guard(target):
            allowed, delay = rules(robots, target)
            if not allowed:
                raise CollectionError("Fiche exclue par robots.txt ; collecte arrêtée.")
            if throttle:
                reserve(path, retailer, delay, stop)
            if stop.is_set():
                raise CollectionError("Collecte interrompue à l’arrêt du service.")

        final_url, raw = fetcher(retailer, job["source_url"], before_request=guard)
        # Defense in depth for adapters; production fetch calls guard before every redirect.
        if not rules(robots, final_url)[0]:
            raise CollectionError("Destination exclue par robots.txt.")
        values = extract(raw, final_url)
        result = dict(
            values,
            source_url=final_url,
            observed_at=now(),
            content_sha256=hashlib.sha256(raw).hexdigest(),
            robots_sha256=hashlib.sha256(raw_rules).hexdigest(),
            parser_version="structured-v1",
        )
        status = "SUCCEEDED"
        message = "Offre extraite ; identité, variante et livraison à valider."
    except CollectionError as exc:
        message = str(exc)
        status = "BLOCKED" if "robots" in message else "FAILED"
    except Exception:
        log.exception("Collection job %s failed", job["id"])
        message = "Erreur de lecture inattendue ; aucun prix publié."
    with connect(path, write=True) as db:
        # A concurrent pause wins over a response arriving late.
        current = db.execute(
            "SELECT enabled,version FROM collection_watches WHERE id=?",
            (job["watch_id"],),
        ).fetchone()
        if not current["enabled"] or current["version"] != job["watch_version"]:
            status = "INTERRUPTED"
            result = None
            message = "Surveillance modifiée pendant la collecte."
        db.execute(
            "UPDATE collection_jobs SET status=?,message=?,finished_at=?,result=? WHERE id=? AND status='RUNNING' AND started_at=?",
            (
                status,
                message,
                now(),
                json.dumps(result, ensure_ascii=False) if result else None,
                job["id"],
                job["started_at"],
            ),
        )
    return True


def serve(path, stop):
    while not stop.is_set():
        try:
            worked = run_one(path, stop=stop)
        except Exception:
            log.exception("Collection scheduler unavailable")
            worked = False
        stop.wait(1 if worked else 10)
