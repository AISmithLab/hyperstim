"""Settings, read only from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LIMIT_PER_IP = 5  # new analyses per IP per hour when ANALYSIS_LIMIT_PER_IP is unset


@dataclass(frozen=True)
class Settings:
    dataset_path: Path
    cors_origin: str
    analysis_dir: Path
    thumbnail_dir: Path
    ytdlp_cookies: Path | None = None
    youtube_api_key: str | None = None  # None = no made-for-kids check
    analysis_limit_per_ip: int = DEFAULT_LIMIT_PER_IP  # 0 = no limit


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set (see .env.example).")
    return value


def _limit(name: str) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return DEFAULT_LIMIT_PER_IP
    try:
        value = int(raw)
    except ValueError:
        value = -1
    if value < 0:
        raise RuntimeError(f"Environment variable {name} must be a whole number ≥ 0, got {raw!r}.")
    return value


def load_settings() -> Settings:
    cookies = os.environ.get("YTDLP_COOKIES", "").strip()
    return Settings(
        dataset_path=Path(_required("DATASET_PATH")),
        cors_origin=_required("CORS_ORIGIN").rstrip("/"),
        analysis_dir=Path(_required("ANALYSIS_DIR")),
        thumbnail_dir=Path(_required("THUMBNAIL_DIR")),
        ytdlp_cookies=Path(cookies) if cookies else None,
        youtube_api_key=os.environ.get("YOUTUBE_API_KEY", "").strip() or None,
        analysis_limit_per_ip=_limit("ANALYSIS_LIMIT_PER_IP"),
    )
