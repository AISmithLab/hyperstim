"""The collector's state: one SQLite file (`collector.db`), used by one process at a time.

Channels and their upload lists, each upload's number and what became of it, the added
videos with their measurements and provenance, removals, download attempts and the Data
API units used per day.
"""

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hyperstim_api.collector.sampling import rank

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    subscriber_count INTEGER,
    video_count INTEGER,
    tier TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,              -- in | near_miss | rejected
    source TEXT NOT NULL,              -- v2 | discovery
    queries TEXT NOT NULL DEFAULT '',  -- the discovery queries that found it
    joined_at TEXT,                    -- when it became `in` (v2's: the v2 scan)
    checked_at TEXT,                   -- last time its stats were read
    listed_at REAL                     -- last time its newest uploads were read
);
CREATE TABLE IF NOT EXISTS uploads (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    published_at TEXT NOT NULL,
    r REAL NOT NULL,
    -- new | v2 | eligible | ineligible | collected | failed | removed
    state TEXT NOT NULL DEFAULT 'new',
    reason TEXT NOT NULL DEFAULT '',
    retry_at REAL NOT NULL DEFAULT 0,  -- `new` uploads are not checked before this
    checked_at REAL,
    online_at REAL,                    -- dataset videos: last seen online (monthly check)
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    channel_title TEXT NOT NULL DEFAULT '',
    duration_s INTEGER
);
CREATE INDEX IF NOT EXISTS uploads_state_r ON uploads (state, r);
CREATE INDEX IF NOT EXISTS uploads_channel ON uploads (channel_id);
CREATE TABLE IF NOT EXISTS collected (
    video_id TEXT PRIMARY KEY,
    added_at TEXT NOT NULL,            -- UTC, ISO 8601
    category TEXT,                     -- None: no keyword placed it
    features TEXT NOT NULL,            -- JSON: the 12 raw values
    cutoff REAL NOT NULL,              -- the cut-off when it was picked
    provenance TEXT NOT NULL           -- JSON
);
CREATE TABLE IF NOT EXISTS removed (
    video_id TEXT PRIMARY KEY,
    removed_at TEXT NOT NULL,
    reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY,
    video_id TEXT NOT NULL,
    at REAL NOT NULL,
    outcome TEXT NOT NULL,             -- collected | unavailable | blocked | failed
    message TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS attempts_at ON attempts (at);
CREATE TABLE IF NOT EXISTS units (day TEXT PRIMARY KEY, used INTEGER NOT NULL);
"""


@dataclass(frozen=True)
class Upload:
    id: str
    channel_id: str
    published_at: str
    r: float
    state: str
    title: str
    description: str
    tags: str
    channel_title: str
    duration_s: int | None


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None)  # autocommit; `transaction()`
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        # With WAL this can lose the last moments on a power cut, never corrupt the file.
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.db.execute("BEGIN")
        done = False
        try:
            yield
            done = True
        finally:
            # Also rolls back when the generator is closed without finishing the block.
            self.db.execute("COMMIT" if done else "ROLLBACK")

    # --- small values --------------------------------------------------------------

    def get(self, key: str, default: str = "") -> str:
        row = self.db.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def set(self, key: str, value: object) -> None:
        self.db.execute(
            "INSERT INTO kv (key, value) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    # --- Data API units ------------------------------------------------------------

    def units_used(self, day: str) -> int:
        row = self.db.execute("SELECT used FROM units WHERE day = ?", (day,)).fetchone()
        return int(row["used"]) if row else 0

    def add_units(self, day: str, units: int) -> None:
        self.db.execute(
            "INSERT INTO units (day, used) VALUES (?, ?) "
            "ON CONFLICT (day) DO UPDATE SET used = used + excluded.used",
            (day, units),
        )

    # --- channels ------------------------------------------------------------------

    def upsert_channel(self, **fields: Any) -> None:
        keys = list(fields)
        updates = ", ".join(f"{k} = excluded.{k}" for k in keys if k != "id")
        self.db.execute(
            f"INSERT INTO channels ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)}) "
            f"ON CONFLICT (id) DO UPDATE SET {updates}",
            [fields[k] for k in keys],
        )

    def update_channel(self, channel_id: str, **fields: Any) -> None:
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.db.execute(f"UPDATE channels SET {sets} WHERE id = ?", [*fields.values(), channel_id])

    def channel_status(self, channel_id: str) -> str | None:
        row = self.db.execute("SELECT status FROM channels WHERE id = ?", (channel_id,)).fetchone()
        return str(row["status"]) if row else None

    def channels(self, status: str) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM channels WHERE status = ? ORDER BY id", (status,)
        ).fetchall()

    # --- uploads -------------------------------------------------------------------

    def add_uploads(self, channel_id: str, uploads: Iterable[tuple[str, str]]) -> int:
        """Adds uploads not seen before; returns how many were new."""
        before = self.db.total_changes
        self.db.executemany(
            "INSERT OR IGNORE INTO uploads (id, channel_id, published_at, r) VALUES (?, ?, ?, ?)",
            [(vid, channel_id, published, rank(vid)) for vid, published in uploads],
        )
        return self.db.total_changes - before

    def known(self, video_id: str) -> bool:
        return (
            self.db.execute("SELECT 1 FROM uploads WHERE id = ?", (video_id,)).fetchone()
            is not None
        )

    def upload(self, video_id: str) -> Upload | None:
        row = self.db.execute("SELECT * FROM uploads WHERE id = ?", (video_id,)).fetchone()
        return _upload(row) if row else None

    def next_unchecked(
        self, now: float, first_year: int, settled_before: str, n: int, below: float = 1.0
    ) -> list[str]:
        """The unchecked uploads with the lowest numbers (under `below`), from channels that
        are in."""
        rows = self.db.execute(
            "SELECT u.id FROM uploads u JOIN channels c ON c.id = u.channel_id "
            "WHERE u.state = 'new' AND c.status = 'in' AND u.retry_at <= ? AND u.r < ? "
            "AND u.published_at >= ? AND u.published_at < ? ORDER BY u.r LIMIT ?",
            (now, below, f"{first_year}-01-01", settled_before, n),
        ).fetchall()
        return [str(r["id"]) for r in rows]

    def next_eligible(self) -> Upload | None:
        row = self.db.execute(
            "SELECT * FROM uploads WHERE state = 'eligible' ORDER BY r LIMIT 1"
        ).fetchone()
        return _upload(row) if row else None

    def count(self, state: str) -> int:
        row = self.db.execute("SELECT COUNT(*) AS n FROM uploads WHERE state = ?", (state,))
        return int(row.fetchone()["n"])

    def cutoff(self) -> float:
        """The highest number the sampling has checked: every eligible upload below it is in
        the dataset or waiting to be downloaded. (v2's picks, also ones taken out later, have
        numbers that played no part in how they were picked.)"""
        row = self.db.execute(
            "SELECT MAX(r) AS r FROM uploads "
            "WHERE state IN ('eligible', 'ineligible', 'collected', 'failed') "
            "OR (state = 'removed' AND id IN (SELECT video_id FROM collected))"
        ).fetchone()
        return float(row["r"] or 0.0)

    def set_state(self, video_id: str, state: str, reason: str = "", **fields: Any) -> None:
        sets = ", ".join(["state = ?", "reason = ?", *(f"{k} = ?" for k in fields)])
        self.db.execute(
            f"UPDATE uploads SET {sets} WHERE id = ?",
            [state, reason, *fields.values(), video_id],
        )

    def in_dataset(self, checked_before: float, n: int) -> list[str]:
        """Dataset videos (v2's and added) not seen online since `checked_before`."""
        rows = self.db.execute(
            "SELECT id FROM uploads WHERE state IN ('v2', 'collected') "
            "AND COALESCE(online_at, 0) < ? ORDER BY COALESCE(online_at, 0), id LIMIT ?",
            (checked_before, n),
        ).fetchall()
        return [str(r["id"]) for r in rows]

    # --- added and removed videos --------------------------------------------------

    def add_collected(
        self,
        video_id: str,
        added_at: str,
        category: str | None,
        features: dict[str, float | None],
        cutoff: float,
        provenance: dict[str, object],
    ) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO collected VALUES (?, ?, ?, ?, ?, ?)",
            (video_id, added_at, category, json.dumps(features), cutoff, json.dumps(provenance)),
        )

    def collected_rows(self) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT c.*, u.channel_id, u.channel_title, u.title, u.published_at, u.duration_s, "
            "u.r FROM collected c JOIN uploads u ON u.id = c.video_id ORDER BY c.added_at, u.id"
        ).fetchall()

    def add_removed(self, video_id: str, removed_at: str, reason: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO removed VALUES (?, ?, ?)", (video_id, removed_at, reason)
        )

    def removed_rows(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM removed ORDER BY removed_at, video_id").fetchall()

    # --- download attempts ---------------------------------------------------------

    def log_attempt(self, video_id: str, at: float, outcome: str, message: str = "") -> None:
        self.db.execute(
            "INSERT INTO attempts (video_id, at, outcome, message) VALUES (?, ?, ?, ?)",
            (video_id, at, outcome, message[-500:]),
        )

    def attempts_since(self, since: float) -> int:
        row = self.db.execute("SELECT COUNT(*) AS n FROM attempts WHERE at >= ?", (since,))
        return int(row.fetchone()["n"])


def _upload(row: sqlite3.Row) -> Upload:
    return Upload(
        id=row["id"],
        channel_id=row["channel_id"],
        published_at=row["published_at"],
        r=row["r"],
        state=row["state"],
        title=row["title"],
        description=row["description"],
        tags=row["tags"],
        channel_title=row["channel_title"],
        duration_s=row["duration_s"],
    )
