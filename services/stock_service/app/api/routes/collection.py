"""Surveillance explicite de fiches publiques et validation humaine traçable."""

import json
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, field_validator, model_validator
from libs.common.database import connect, db_path, now
from libs.common.security import current_user, editor
from services.stock_service.app.repositories.stock_repo import (
    product,
    check_version,
    remember,
)
from services.stock_service.app.schemas.product_schemas import normalize_price
from services.stock_service.app.services.collection.network import (
    safe_url,
    CollectionError,
)
from services.stock_service.app.services.collection.worker import enqueue, audit
from .crm import Mutation, Id, replay
from .market import Observation

router = APIRouter(prefix="/collection", tags=["Collecte publique"])


class Identity(Mutation):
    brand: str = Field(min_length=1, max_length=160)
    manufacturer_ref: str = Field(min_length=1, max_length=160)
    gtin: str = Field(default="", max_length=14)
    variant: str = Field(min_length=1, max_length=400)
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("gtin")
    @classmethod
    def barcode(cls, value):
        if value and (
            len(value) not in (8, 12, 13, 14)
            or not value.isascii()
            or not value.isdigit()
            or sum(
                int(n) * (3 if i % 2 == 0 else 1) for i, n in enumerate(value[-2::-1])
            )
            % 10
            != (-int(value[-1])) % 10
        ):
            raise ValueError("GTIN avec clé valide requis")
        return value


class Watch(Mutation):
    retailer: Literal["Tunisianet", "Mytek", "Spacenet"]
    source_url: str = Field(max_length=2000)
    interval_hours: int = Field(ge=6, le=168, default=24)

    @model_validator(mode="after")
    def url(self):
        self.source_url = safe_url(self.retailer, self.source_url)
        return self


class WatchUpdate(Mutation):
    expected_version: int = Field(ge=1)
    enabled: bool


class Review(Mutation):
    accept: bool
    note: str = Field(min_length=1, max_length=900)
    tax_basis: Literal["TTC", "HT", "UNKNOWN"] = "UNKNOWN"
    delivery: str | None = None
    availability: Literal["IN_STOCK", "OUT_OF_STOCK", "UNKNOWN"] | None = None

    @field_validator("delivery")
    @classmethod
    def cost(cls, value):
        return normalize_price(value) if value is not None else None


def watch_by_id(db, identity):
    row = db.execute(
        "SELECT * FROM collection_watches WHERE id=?", (identity,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Surveillance introuvable.")
    return dict(row)


@router.get("/products/{product_id}")
def read(product_id: Id, request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        product(db, product_id)
        identity = db.execute(
            "SELECT * FROM product_identities WHERE product_id=?", (product_id,)
        ).fetchone()
        jobs = [
            dict(r)
            for r in db.execute(
                "SELECT j.*,w.retailer,w.source_url FROM collection_jobs j JOIN collection_watches w ON w.id=j.watch_id WHERE w.product_id=? ORDER BY j.id DESC LIMIT 100",
                (product_id,),
            )
        ]
        for job in jobs:
            job["result"] = json.loads(job["result"]) if job["result"] else None
        worker = getattr(request.app.state, "collection_thread", None)
        return dict(
            identity=dict(identity) if identity else None,
            watches=[
                dict(r)
                for r in db.execute(
                    "SELECT * FROM collection_watches WHERE product_id=? ORDER BY id",
                    (product_id,),
                )
            ],
            jobs=jobs,
            events=[
                dict(r)
                for r in db.execute(
                    "SELECT e.*,u.name actor_name FROM collection_events e JOIN users u ON u.id=e.actor_id WHERE product_id=? ORDER BY e.id DESC LIMIT 50",
                    (product_id,),
                )
            ],
            worker_running=bool(worker and worker.is_alive()),
        )


@router.post("/products/{product_id}/identity")
def identity(product_id: Id, body: Identity, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "collection-identity", product_id)
        if cached is not None:
            return cached
        product(db, product_id)
        old = db.execute(
            "SELECT * FROM product_identities WHERE product_id=?", (product_id,)
        ).fetchone()
        version = old["version"] if old else 0
        if version != body.expected_version:
            raise HTTPException(409, "Identité modifiée ; rechargez la fiche.")
        db.execute(
            "INSERT INTO product_identities VALUES (?,?,?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET brand=excluded.brand,manufacturer_ref=excluded.manufacturer_ref,gtin=excluded.gtin,variant=excluded.variant,version=excluded.version,updated_at=excluded.updated_at",
            (
                product_id,
                body.brand,
                body.manufacturer_ref,
                body.gtin,
                body.variant,
                version + 1,
                now(),
            ),
        )
        audit(
            db,
            product_id,
            json.dumps(
                dict(
                    reason=body.reason,
                    before=dict(old) if old else None,
                    after=body.model_dump(exclude={"idempotency_key"}),
                ),
                ensure_ascii=False,
            ),
            user["id"],
        )
        result = dict(version=version + 1)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.post("/products/{product_id}/watches", status_code=201)
def create_watch(product_id: Id, body: Watch, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "collection-watch", product_id)
        if cached is not None:
            return cached
        product(db, product_id)
        if not db.execute(
            "SELECT 1 FROM product_identities WHERE product_id=?", (product_id,)
        ).fetchone():
            raise HTTPException(409, "Renseignez l’identité produit avant activation.")
        if db.execute(
            "SELECT 1 FROM collection_watches WHERE product_id=? AND source_url=?",
            (product_id, body.source_url),
        ).fetchone():
            raise HTTPException(409, "Cette URL est déjà surveillée pour ce produit.")
        if (
            db.execute(
                "SELECT COUNT(*) FROM collection_watches WHERE enabled=1"
            ).fetchone()[0]
            >= 200
        ):
            raise HTTPException(
                409,
                "Limite locale de 200 fiches actives atteinte ; mettez une surveillance en pause.",
            )
        cursor = db.execute(
            "INSERT INTO collection_watches(product_id,retailer,source_url,interval_hours,enabled,next_due,actor_id,created_at) VALUES (?,?,?,?,1,?,?,?)",
            (
                product_id,
                body.retailer,
                body.source_url,
                body.interval_hours,
                now(),
                user["id"],
                now(),
            ),
        )
        audit(
            db,
            product_id,
            f"Surveillance activée : {body.retailer}, {body.source_url}, toutes les {body.interval_hours} h.",
            user["id"],
        )
        result = dict(id=cursor.lastrowid)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.post("/watches/{watch_id}/state")
def toggle(watch_id: Id, body: WatchUpdate, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "collection-toggle", watch_id)
        if cached is not None:
            return cached
        watch = watch_by_id(db, watch_id)
        check_version(watch, body.expected_version)
        if (
            body.enabled
            and not watch["enabled"]
            and db.execute(
                "SELECT COUNT(*) FROM collection_watches WHERE enabled=1"
            ).fetchone()[0]
            >= 200
        ):
            raise HTTPException(409, "Limite locale de 200 fiches actives atteinte.")
        db.execute(
            "UPDATE collection_watches SET enabled=?,version=version+1,actor_id=? WHERE id=?",
            (int(body.enabled), user["id"], watch_id),
        )
        audit(
            db,
            watch["product_id"],
            "Surveillance reprise." if body.enabled else "Surveillance suspendue.",
            user["id"],
        )
        result = dict(id=watch_id)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.post("/watches/{watch_id}/run", status_code=201)
def run(watch_id: Id, body: Mutation, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "collection-run", watch_id)
        if cached is not None:
            return cached
        watch = watch_by_id(db, watch_id)
        if not watch["enabled"]:
            raise HTTPException(409, "Surveillance suspendue.")
        if db.execute(
            "SELECT 1 FROM collection_jobs WHERE watch_id=? AND status IN ('QUEUED','RUNNING')",
            (watch_id,),
        ).fetchone():
            raise HTTPException(409, "Une collecte est déjà en attente ou en cours.")
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        if db.execute(
            "SELECT 1 FROM collection_jobs WHERE watch_id=? AND created_at>?",
            (watch_id, cutoff),
        ).fetchone():
            raise HTTPException(
                409, "Attendez 15 minutes entre deux demandes de collecte."
            )
        result = dict(id=enqueue(db, watch, user["id"]))
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.post("/jobs/{job_id}/review")
def review(job_id: Id, body: Review, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "collection-review", job_id)
        if cached is not None:
            return cached
        job = db.execute(
            "SELECT j.*,w.product_id,w.retailer FROM collection_jobs j JOIN collection_watches w ON w.id=j.watch_id WHERE j.id=?",
            (job_id,),
        ).fetchone()
        if not job:
            raise HTTPException(404, "Collecte introuvable.")
        if job["status"] != "SUCCEEDED" or job["review_state"] != "PENDING":
            raise HTTPException(
                409, "Cette collecte n’est pas en attente de validation."
            )
        observation_id = None
        if body.accept:
            identity = db.execute(
                "SELECT * FROM product_identities WHERE product_id=?",
                (job["product_id"],),
            ).fetchone()
            if identity["version"] != job["identity_version"]:
                raise HTTPException(
                    409, "Identité modifiée depuis la collecte ; relancez une collecte."
                )
            data = json.loads(job["result"])
            for field in ("manufacturer_ref", "gtin"):
                if (
                    identity[field]
                    and data[field]
                    and identity[field].casefold() != data[field].casefold()
                ):
                    raise HTTPException(
                        409,
                        "Référence constructeur ou GTIN contradictoire ; refusez ce rapprochement.",
                    )
            if (
                body.availability
                and data["availability"] != "UNKNOWN"
                and body.availability != data["availability"]
            ):
                raise HTTPException(
                    409,
                    "Disponibilité différente du relevé : effectuez une nouvelle collecte ou un relevé manuel.",
                )
            observation = Observation(
                product_id=job["product_id"],
                retailer=job["retailer"],
                source_url=data["source_url"],
                manufacturer_ref=identity["manufacturer_ref"],
                variant=identity["variant"],
                price=data["price"],
                currency=data["currency"],
                tax_basis=body.tax_basis,
                delivery=body.delivery,
                availability=body.availability or data["availability"],
                confirmed=True,
                note=f"Collecte #{job_id} · {body.note}",
                observed_at=data["observed_at"],
                idempotency_key=body.idempotency_key,
            )
            fields = observation.model_dump(exclude={"idempotency_key"})
            fields.update(created_at=now(), actor_id=user["id"])
            observation_id = db.execute(
                f"INSERT INTO market_observations({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                list(fields.values()),
            ).lastrowid
        db.execute(
            "UPDATE collection_jobs SET review_state=?,observation_id=? WHERE id=?",
            ("ACCEPTED" if body.accept else "REJECTED", observation_id, job_id),
        )
        audit(
            db,
            job["product_id"],
            f"Collecte #{job_id} {'validée' if body.accept else 'refusée'} : {body.note}",
            user["id"],
        )
        result = dict(observation_id=observation_id)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result
