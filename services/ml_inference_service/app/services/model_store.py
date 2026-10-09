from pathlib import Path
from joblib import load
from hashlib import sha256
import json
from ..core.config import DATA_DIR
from services.ml_training_service.app.services.artifacts import dataset_fingerprint


def latest_artifact(models_dir: Path, prefix: str) -> Path:
    # ex: prefix="demand_weekly_"
    files = sorted(models_dir.glob(f"{prefix}*.joblib"))
    if not files:
        raise FileNotFoundError(
            f"Aucun artefact trouvé pour prefix={prefix} dans {models_dir}"
        )
    return files[-1]


class ModelStore:
    def __init__(self, models_dir: Path):
        self.models_dir = models_dir
        self._cache = {}

    def load_latest(self, key: str, prefix: str):
        path = latest_artifact(self.models_dir, prefix)
        content_hash = sha256(path.read_bytes()).hexdigest()
        marker = path.with_suffix(".sha256")
        if (
            not marker.is_file()
            or marker.read_text(encoding="ascii").strip() != content_hash
        ):
            raise ValueError(
                "Artefact non enregistré localement ou intégrité invalide; réentraîner localement."
            )
        metadata_file = path.with_suffix(".metadata.json")
        if not metadata_file.is_file():
            raise ValueError("Provenance locale de l'artefact absente.")
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        if metadata.get("data_dir") != str(DATA_DIR) or metadata.get(
            "dataset_fingerprint"
        ) != dataset_fingerprint(DATA_DIR):
            raise ValueError(
                "Le modèle et les données ne correspondent plus; réentraîner localement."
            )
        cached = self._cache.get(key)
        if (
            cached
            and cached.get("path") == str(path)
            and cached.get("sha256") == content_hash
        ):
            return cached["obj"]
        obj = load(path)
        self._cache[key] = {"path": str(path), "sha256": content_hash, "obj": obj}
        return obj
