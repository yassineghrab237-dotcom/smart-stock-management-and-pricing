"""Register only explicitly requested local training artifacts.

Hashes detect corruption and exclude historical unregistered pickle files.
They are not signatures; this directory must stay under trusted local control.
"""

from hashlib import sha256
from pathlib import Path
from joblib import dump as joblib_dump
import json
from ..core.config import DATA_DIR


def dataset_fingerprint(directory: Path) -> str:
    digest = sha256()
    for path in sorted(directory.glob("*.csv")) + sorted(directory.glob("config.json")):
        digest.update(path.name.encode("utf-8"))
        digest.update(sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def dump(model: object, path: Path) -> None:
    joblib_dump(model, path)
    path.with_suffix(".sha256").write_text(
        sha256(path.read_bytes()).hexdigest(), encoding="ascii"
    )
    path.with_suffix(".metadata.json").write_text(
        json.dumps(
            {
                "data_dir": str(DATA_DIR),
                "dataset_fingerprint": dataset_fingerprint(DATA_DIR),
                "provenance": "explicit_local_training",
                "quality_evaluation": "not_performed",
            }
        ),
        encoding="utf-8",
    )
