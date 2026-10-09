"""Shared local paths. Importing configuration never creates directories."""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[4]
load_dotenv(BASE_DIR / ".env", override=False)


def _path(name: str, default: Path) -> Path:
    value = Path(os.getenv(name, str(default))).expanduser()
    return (value if value.is_absolute() else BASE_DIR / value).resolve()


DATA_DIR = _path("DATA_DIR", BASE_DIR / "data")
ARTIFACTS_DIR = _path("ARTIFACTS_DIR", BASE_DIR / "artifacts")
MODELS_DIR = _path("MODELS_DIR", ARTIFACTS_DIR / "models")
REPORTS_DIR = _path("REPORTS_DIR", ARTIFACTS_DIR / "reports")


def ensure_output_dirs() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
