import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from libs.common.database import connect, db_path, now
from libs.common.security import current_user, editor
from services.stock_service.app.services.analysis import snapshot, run_analysis

router = APIRouter(prefix="/analysis/jobs", tags=["Analyses de ventes"])


def expire(db):
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    db.execute(
        "UPDATE analysis_jobs SET status='INTERRUPTED',message='Analyse interrompue ou sans progression depuis 10 minutes. Relancez le traitement.',updated_at=? WHERE status IN ('QUEUED','RUNNING') AND updated_at<?",
        (now(), cutoff),
    )


def serialize(row, fingerprint):
    result = dict(row)
    result["result"] = json.loads(result["result"]) if result["result"] else None
    result["stale"] = result["fingerprint"] != fingerprint
    return result


@router.post("")
def start(request: Request, tasks: BackgroundTasks, user=Depends(editor)):
    path = db_path(request)
    with connect(path, write=True) as db:
        expire(db)
        source, fingerprint = snapshot(db)
        existing = db.execute(
            "SELECT * FROM analysis_jobs WHERE fingerprint=? AND status IN ('QUEUED','RUNNING','SUCCEEDED') ORDER BY id DESC LIMIT 1",
            (fingerprint,),
        ).fetchone()
        if existing:
            return serialize(existing, fingerprint)
        # Un seul calcul à la fois par base, même si les données évoluent.
        active = db.execute(
            "SELECT * FROM analysis_jobs WHERE status IN ('QUEUED','RUNNING') ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if active:
            return serialize(active, fingerprint)
        stamp = now()
        cursor = db.execute(
            "INSERT INTO analysis_jobs(fingerprint,status,progress,message,actor_id,created_at,updated_at) VALUES (?,'QUEUED',0,?,?,?,?)",
            (fingerprint, "Analyse en attente de démarrage.", user["id"], stamp, stamp),
        )
        job_id = cursor.lastrowid
        row = db.execute("SELECT * FROM analysis_jobs WHERE id=?", (job_id,)).fetchone()
        tasks.add_task(run_analysis, path, job_id, source)
        return serialize(row, fingerprint)


@router.get("")
def jobs(request: Request, user=Depends(current_user)):
    with connect(db_path(request), write=True) as db:
        expire(db)
        _, fingerprint = snapshot(db)
        return {
            "items": [
                serialize(r, fingerprint)
                for r in db.execute(
                    "SELECT * FROM analysis_jobs ORDER BY id DESC LIMIT 30"
                )
            ]
        }
