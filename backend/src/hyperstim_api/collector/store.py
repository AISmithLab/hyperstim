"""The collector's state: one SQLite file (`collector.db`), used by one process at a time.

Channels and their upload lists, each upload's number and what became of it, the added
videos with their measurements and provenance, removals, download attempts and the Data
API units used per day.
"""

import json
import os
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
    listed_at REAL,                    -- last time its newest uploads were read
    api_failures INTEGER NOT NULL DEFAULT 0,  -- Data API errors in a row reading its uploads
    retry_at REAL NOT NULL DEFAULT 0,  -- after an error: not read again before this
    full_listing TEXT                  -- reading all its uploads: '' or the next page; else NULL
);
CREATE TABLE IF NOT EXISTS uploads (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    published_at TEXT NOT NULL,
    r REAL NOT NULL,
    -- new | v2 | eligible | ineligible | measured | collected | failed | removed
    -- (measured: measured, but waiting for a missing title, channel name or date)
    state TEXT NOT NULL DEFAULT 'new',
    reason TEXT NOT NULL DEFAULT '',
    -- not before: `new`, checked; `eligible`, downloaded; `v2`/`collected`, checked online
    retry_at REAL NOT NULL DEFAULT 0,
    unsure INTEGER NOT NULL DEFAULT 0, -- answers that couldn't settle its state, in a row
    api_failures INTEGER NOT NULL DEFAULT 0,  -- Data API errors in a row checking it
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
# Columns added since the first release (plan 013, decision 12), added to an older database
# when it's opened: table -> column -> its definition.
ADDED_COLUMNS = {
    "channels": {
        "api_failures": "INTEGER NOT NULL DEFAULT 0",
        "retry_at": "REAL NOT NULL DEFAULT 0",
        "full_listing": "TEXT",
    },
    "uploads": {
        "unsure": "INTEGER NOT NULL DEFAULT 0",
        "api_failures": "INTEGER NOT NULL DEFAULT 0",
    },
}
V2_JOINED = "2026-08-26"  # v2's scan: when v2's channels joined


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
    unsure: int = 0
    api_failures: int = 0

    def complete(self) -> bool:
        """Everything the site shows about it is in place (plan 013, decision 12)."""
        return all(
            v.strip() for v in (self.title, self.channel_id, self.channel_title, self.published_at)
        )


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None)  # autocommit; `transaction()`
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        # With WAL this can lose the last moments on a power cut, never corrupt the file.
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Adds the columns an older database lacks. Channels that joined after v2's scan were
        read in one go, and a read that failed partway was never finished: they're read again
        in full (adding only the uploads still missing)."""
        for table, columns in ADDED_COLUMNS.items():
            have = {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")}
            for name, definition in columns.items():
                if name in have:
                    continue
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
                if (table, name) == ("channels", "full_listing"):
                    self.db.execute(
                        "UPDATE channels SET full_listing = '' "
                        "WHERE status = 'in' AND joined_at > ?",
                        (V2_JOINED,),
                    )

    def close(self) -> None:
        self.db.close()

    def backup(self, path: Path) -> None:
        """A consistent copy of the whole database, made while it's in use (SQLite's online
        backup), written whole and renamed into place."""
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.unlink(missing_ok=True)
        target = sqlite3.connect(tmp)
        try:
            self.db.backup(target)
        finally:
            target.close()
        os.replace(tmp, path)

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

    def next_eligible(self, now: float) -> Upload | None:
        """The eligible upload with the lowest number, not waiting for a retry."""
        row = self.db.execute(
            "SELECT * FROM uploads WHERE state = 'eligible' AND retry_at <= ? ORDER BY r LIMIT 1",
            (now,),
        ).fetchone()
        return _upload(row) if row else None

    def ready(self, now: float) -> int:
        """Eligible uploads that can be downloaded now (not waiting for a retry)."""
        row = self.db.execute(
            "SELECT COUNT(*) AS n FROM uploads WHERE state = 'eligible' AND retry_at <= ?", (now,)
        )
        return int(row.fetchone()["n"])

    def retrying(self, now: float) -> list[float]:
        """When the uploads waiting for a retry are due, soonest first."""
        rows = self.db.execute(
            "SELECT retry_at FROM uploads WHERE state = 'eligible' AND retry_at > ? "
            "ORDER BY retry_at",
            (now,),
        )
        return [float(r["retry_at"]) for r in rows]

    def requeue_failed(self, below: int) -> int:
        """Failed uploads with fewer than `below` failed downloads become eligible again, due at
        once (those given up before failures were retried); returns how many."""
        before = self.db.total_changes
        self.db.execute(
            "UPDATE uploads SET state = 'eligible', retry_at = 0 WHERE state = 'failed' AND "
            "(SELECT COUNT(*) FROM attempts a WHERE a.video_id = uploads.id "
            "AND a.outcome = 'failed') < ?",
            (below,),
        )
        return self.db.total_changes - before

    def count(self, state: str) -> int:
        row = self.db.execute("SELECT COUNT(*) AS n FROM uploads WHERE state = ?", (state,))
        return int(row.fetchone()["n"])

    def cutoff(self) -> float:
        """The highest number the sampling has checked: every eligible upload below it is in
        the dataset or waiting to be downloaded. (v2's picks, also ones taken out later, have
        numbers that played no part in how they were picked.)"""
        row = self.db.execute(
            "SELECT MAX(r) AS r FROM uploads "
            "WHERE state IN ('eligible', 'ineligible', 'measured', 'collected', 'failed') "
            "OR (state = 'removed' AND id IN (SELECT video_id FROM collected))"
        ).fetchone()
        return float(row["r"] or 0.0)

    def set_state(self, video_id: str, state: str, reason: str = "", **fields: Any) -> None:
        sets = ", ".join(["state = ?", "reason = ?", *(f"{k} = ?" for k in fields)])
        self.db.execute(
            f"UPDATE uploads SET {sets} WHERE id = ?",
            [state, reason, *fields.values(), video_id],
        )

    def in_dataset(self, checked_before: float, now: float, n: int) -> list[Upload]:
        """Dataset videos (v2's and added) not seen online since `checked_before`, and not
        waiting to be checked again."""
        rows = self.db.execute(
            "SELECT * FROM uploads WHERE state IN ('v2', 'collected') "
            "AND COALESCE(online_at, 0) < ? AND retry_at <= ? "
            "ORDER BY COALESCE(online_at, 0), id LIMIT ?",
            (checked_before, now, n),
        ).fetchall()
        return [_upload(r) for r in rows]

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
            "u.r FROM collected c JOIN uploads u ON u.id = c.video_id "
            "WHERE u.state IN ('collected', 'removed') ORDER BY c.added_at, u.id"
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

    def failures(self, video_id: str) -> int:
        """Failed downloads of the video (blocks not counted)."""
        row = self.db.execute(
            "SELECT COUNT(*) AS n FROM attempts WHERE video_id = ? AND outcome = 'failed'",
            (video_id,),
        )
        return int(row.fetchone()["n"])

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
        unsure=row["unsure"],
        api_failures=row["api_failures"],
    )
