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

from hyperstim_api.collector.sampling import FIRST_VIDEOS_PER_DAY, FLOOR, left_out, rank

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
    duration_s INTEGER,
    pick TEXT NOT NULL DEFAULT 'sample', -- why it was checked: sample (under t) | floor
    score REAL                         -- dataset videos: their score, for the download order
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
-- Channels left out for their kids share (decision 1), worked out at each export.
CREATE TABLE IF NOT EXISTS left_out (
    channel_id TEXT PRIMARY KEY,
    kids INTEGER NOT NULL,             -- of its answers, made for kids
    answers INTEGER NOT NULL           -- checked uploads whose made-for-kids answer is known
);
-- The changelog's counts that can't be worked out again later (decision 10), one row per UTC
-- day, the day's last export wins: channels not on the site yet with a video waiting, and
-- channels left out (NULL on the days before it was recorded).
CREATE TABLE IF NOT EXISTS daily (day TEXT PRIMARY KEY, ch_ready INTEGER NOT NULL, ch_out INTEGER);
-- The changelog's notes (decision 10): each dated the first day the collector ran with it.
CREATE TABLE IF NOT EXISTS notes (note TEXT PRIMARY KEY, day TEXT NOT NULL);
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
        "pick": "TEXT NOT NULL DEFAULT 'sample'",  # everything checked before was `sample`
        "score": "REAL",  # filled in when the collector starts
    },
    "daily": {"ch_out": "INTEGER"},
}
V2_JOINED = "2026-08-26"
# A channel's videos in the dataset or on their way: what the floor counts.
HAVE_STATES = "('v2', 'measured', 'collected', 'eligible')"  # v2's scan: when v2's channels joined
# A channel's videos in the dataset (measured ones too: they wait only for a name).
IN_STATES = "('v2', 'measured', 'collected')"
KEPT = "NOT IN (SELECT channel_id FROM left_out)"  # a channel not left out: `<id column> {KEPT}`
# Each channel with videos in the dataset: how many, and its score as the site ranks it (the
# mean of its videos' scores).
HAVE = (
    "WITH have AS (SELECT channel_id, COUNT(*) AS n, AVG(score) AS score FROM uploads "
    f"WHERE state IN {IN_STATES} GROUP BY channel_id) "
)
# Uploads whose made-for-kids answer is known: those that passed that check (the later checks
# need it), those that failed it, and the floor's eligible ones put back unchecked (`trimmed`).
# v2's picks don't count: they were picked for being made for kids.
ANSWERED = (
    "state IN ('eligible', 'measured', 'collected', 'failed') OR (state = 'ineligible' "
    "AND reason IN ('not_for_kids', 'duration', 'short')) OR (state = 'new' AND reason = 'trimmed')"
)


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
    pick: str = "sample"

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

    def below_floor(self) -> list[sqlite3.Row]:
        """Channels that are in with fewer than `FLOOR` videos (in the dataset or waiting to be
        downloaded), the fewest first: `id`, `have`."""
        return self.db.execute(
            "WITH have AS (SELECT channel_id, COUNT(*) AS n FROM uploads "
            f"WHERE state IN {HAVE_STATES} GROUP BY channel_id) "
            "SELECT c.id, COALESCE(h.n, 0) AS have FROM channels c "
            "LEFT JOIN have h ON h.channel_id = c.id "
            f"WHERE c.status = 'in' AND c.id {KEPT} AND COALESCE(h.n, 0) < ? ORDER BY have, c.id",
            (FLOOR,),
        ).fetchall()

    def next_floor_unchecked(
        self, now: float, first_year: int, settled_before: str, per_missing: int, n: int
    ) -> list[str]:
        """Unchecked uploads of channels below the floor: each channel's lowest numbers,
        `per_missing` for each video it lacks, the channels with the fewest videos first."""
        rows = self.db.execute(
            "WITH have AS (SELECT channel_id, COUNT(*) AS n FROM uploads "
            f"WHERE state IN {HAVE_STATES} GROUP BY channel_id), "
            "floor AS (SELECT c.id, COALESCE(h.n, 0) AS have FROM channels c "
            "LEFT JOIN have h ON h.channel_id = c.id "
            f"WHERE c.status = 'in' AND c.id {KEPT} AND COALESCE(h.n, 0) < :floor), "
            "next AS (SELECT u.id, u.channel_id, u.r, f.have, ROW_NUMBER() OVER "
            "(PARTITION BY u.channel_id ORDER BY u.r) AS k FROM uploads u "
            "JOIN floor f ON f.id = u.channel_id WHERE u.state = 'new' AND u.retry_at <= :now "
            "AND u.published_at >= :first AND u.published_at < :settled) "
            "SELECT id FROM next WHERE k <= (:floor - have) * :per_missing "
            "ORDER BY have, channel_id, r LIMIT :n",
            {
                "floor": FLOOR,
                "now": now,
                "first": f"{first_year}-01-01",
                "settled": settled_before,
                "per_missing": per_missing,
                "n": n,
            },
        ).fetchall()
        return [str(r["id"]) for r in rows]

    def trim_floor(self) -> int:
        """The floor's eligible picks beyond a channel's `FLOOR` (its other videos counted),
        highest numbers first, go back to unchecked; returns how many. They keep `trimmed` as
        their reason, so their made-for-kids answer still counts."""
        before = self.db.total_changes
        self.db.execute(
            "WITH other AS (SELECT channel_id, COUNT(*) AS n FROM uploads "
            "WHERE state IN ('v2', 'measured', 'collected') "
            "OR (state = 'eligible' AND pick = 'sample') GROUP BY channel_id), "
            "floor AS (SELECT id, channel_id, ROW_NUMBER() OVER "
            "(PARTITION BY channel_id ORDER BY r) AS k FROM uploads "
            "WHERE state = 'eligible' AND pick = 'floor') "
            "UPDATE uploads SET state = 'new', pick = 'sample', reason = 'trimmed', "
            "checked_at = NULL "
            "WHERE id IN (SELECT f.id FROM floor f LEFT JOIN other o "
            "ON o.channel_id = f.channel_id WHERE f.k > ? - COALESCE(o.n, 0))",
            (FLOOR,),
        )
        return self.db.total_changes - before

    def next_eligible(self, now: float) -> Upload | None:
        """The next eligible upload to download, not waiting for a retry (decision 2): first
        the channels with 1 to `FLOOR` - 1 videos in the dataset, highest channel score first;
        then a channel's first video, while fewer than `FIRST_VIDEOS_PER_DAY` channels got
        theirs today; then by number over all. Within a channel, its lowest number, whether
        picked under the cut-off or for the floor; left-out channels get none."""
        row = self.db.execute(
            HAVE + "SELECT u.* FROM uploads u LEFT JOIN have h ON h.channel_id = u.channel_id "
            f"WHERE u.state = 'eligible' AND u.retry_at <= :now AND u.channel_id {KEPT} "
            "AND (h.n > 0 OR :first) "
            "ORDER BY CASE WHEN h.n < :floor THEN 0 WHEN h.n IS NULL THEN 1 ELSE 2 END, "
            "CASE WHEN h.n < :floor THEN -COALESCE(h.score, -1) END, u.r LIMIT 1",
            {"now": now, "first": self.first_video_left(now), "floor": FLOOR},
        ).fetchone()
        return _upload(row) if row else None

    def ready(self, now: float, pick: str | None = None) -> int:
        """Eligible uploads that can be downloaded now (not waiting for a retry, not of a
        left-out channel, not a first video once today's are taken); only those picked for
        `pick` if given."""
        row = self.db.execute(
            "SELECT COUNT(*) AS n FROM uploads WHERE state = 'eligible' AND retry_at <= ? "
            f"AND pick = COALESCE(?, pick) AND channel_id {KEPT} AND (? OR channel_id IN "
            f"(SELECT channel_id FROM uploads WHERE state IN {IN_STATES}))",
            (now, pick, self.first_video_left(now)),
        )
        return int(row.fetchone()["n"])

    def first_videos_today(self, now: float) -> int:
        """Channels that got their first video today (UTC): their first video added today and
        none of v2's."""
        row = self.db.execute(
            "SELECT COUNT(*) FROM (SELECT u.channel_id FROM attempts a "
            "JOIN uploads u ON u.id = a.video_id WHERE a.outcome = 'collected' "
            "GROUP BY u.channel_id HAVING MIN(a.at) >= ?) f WHERE NOT EXISTS "
            "(SELECT 1 FROM uploads v WHERE v.channel_id = f.channel_id AND v.state = 'v2')",
            (now - now % 86400,),
        ).fetchone()
        return int(row[0])

    def first_video_left(self, now: float) -> bool:
        return self.first_videos_today(now) < FIRST_VIDEOS_PER_DAY

    def set_scores(self, scores: Iterable[tuple[str, float | None]]) -> None:
        """Dataset videos' scores, where not set yet (they never change)."""
        self.db.executemany(
            "UPDATE uploads SET score = ? WHERE id = ? AND score IS NULL",
            [(score, video_id) for video_id, score in scores],
        )

    def unscored(self) -> list[sqlite3.Row]:
        """Added videos without a score: `video_id`, `features` (JSON)."""
        return self.db.execute(
            "SELECT c.video_id, c.features FROM collected c JOIN uploads u ON u.id = c.video_id "
            "WHERE u.score IS NULL"
        ).fetchall()

    # --- the changelog's counts and notes (decision 10) ----------------------------

    def ready_to_join(self) -> int:
        """Channels with no video in the dataset but an eligible upload waiting to download;
        left-out channels not counted."""
        row = self.db.execute(
            "SELECT COUNT(DISTINCT channel_id) FROM uploads "
            f"WHERE state = 'eligible' AND channel_id {KEPT} AND channel_id NOT IN "
            "(SELECT channel_id FROM uploads WHERE state IN ('v2', 'collected'))"
        ).fetchone()
        return int(row[0])

    def record_daily(self, day: str, ch_ready: int, ch_out: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO daily (day, ch_ready, ch_out) VALUES (?, ?, ?)",
            (day, ch_ready, ch_out),
        )

    def daily(self) -> dict[str, sqlite3.Row]:
        """The recorded counts by day: `ch_ready`, `ch_out` (None before it was recorded)."""
        return {r["day"]: r for r in self.db.execute("SELECT * FROM daily")}

    def date_notes(self, notes: Iterable[tuple[str, str | None]], today: str) -> None:
        """Dates each note not seen before: its own date if it has one, else today."""
        self.db.executemany(
            "INSERT OR IGNORE INTO notes VALUES (?, ?)",
            [(note, day or today) for note, day in notes],
        )

    def notes(self) -> dict[str, list[str]]:
        """The notes by day, in the order they were dated."""
        out: dict[str, list[str]] = {}
        for r in self.db.execute("SELECT note, day FROM notes ORDER BY rowid"):
            out.setdefault(r["day"], []).append(r["note"])
        return out

    # --- the kids share (decision 1) -----------------------------------------------

    def update_left_out(self) -> list[sqlite3.Row]:
        """Works out each channel's kids share from its answers and keeps the channels left
        out; returns them (`channel_id`, `kids`, `answers`), by ID."""
        rows = self.db.execute(
            "SELECT channel_id, SUM(reason != 'not_for_kids') AS kids, COUNT(*) AS answers "
            f"FROM uploads WHERE {ANSWERED} GROUP BY channel_id ORDER BY channel_id"
        ).fetchall()
        out = [r for r in rows if left_out(int(r["kids"]), int(r["answers"]))]
        with self.transaction():
            self.db.execute("DELETE FROM left_out")
            self.db.executemany(
                "INSERT INTO left_out (channel_id, kids, answers) VALUES (?, ?, ?)",
                [(r["channel_id"], r["kids"], r["answers"]) for r in out],
            )
        return out

    def left_out_list(self) -> list[sqlite3.Row]:
        """The channels left out at the last `update_left_out`, by ID: `channel_id`, `title`,
        `kids`, `answers`, and `videos` (its videos in the dataset, as the site would count
        them)."""
        return self.db.execute(
            "SELECT l.channel_id, COALESCE(c.title, '') AS title, l.kids, l.answers, "
            "(SELECT COUNT(*) FROM uploads u WHERE u.channel_id = l.channel_id "
            "AND u.state IN ('v2', 'collected')) AS videos "
            "FROM left_out l LEFT JOIN channels c ON c.id = l.channel_id ORDER BY l.channel_id"
        ).fetchall()

    def levels(self) -> dict[int, int]:
        """Channels that are in and not left out, with fewer than `FLOOR` videos in the
        dataset: how many have 0, 1, …"""
        rows = self.db.execute(
            "WITH have AS (SELECT channel_id, COUNT(*) AS n FROM uploads "
            f"WHERE state IN {IN_STATES} GROUP BY channel_id) "
            "SELECT COALESCE(h.n, 0) AS have, COUNT(*) AS n FROM channels c "
            "LEFT JOIN have h ON h.channel_id = c.id "
            f"WHERE c.status = 'in' AND c.id {KEPT} AND COALESCE(h.n, 0) < ? GROUP BY 1",
            (FLOOR,),
        )
        return {int(r["have"]): int(r["n"]) for r in rows}

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
        the dataset or waiting to be downloaded. (v2's picks, also ones taken out later, and the
        floor's checks have numbers that played no part in how the sampling picked.)"""
        row = self.db.execute(
            "SELECT MAX(r) AS r FROM uploads WHERE pick = 'sample' AND ("
            "state IN ('eligible', 'ineligible', 'measured', 'collected', 'failed') "
            "OR (state = 'removed' AND id IN (SELECT video_id FROM collected)))"
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
            "u.r, u.pick FROM collected c JOIN uploads u ON u.id = c.video_id "
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
        pick=row["pick"],
    )
