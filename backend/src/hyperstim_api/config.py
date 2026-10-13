"""Settings, read only from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    dataset_path: Path
    cors_origin: str


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set (see .env.example).")
    return value


def load_settings() -> Settings:
    return Settings(
        dataset_path=Path(_required("DATASET_PATH")),
        cors_origin=_required("CORS_ORIGIN").rstrip("/"),
    )
