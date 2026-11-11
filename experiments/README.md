# Experiments

Research experiments on YouTube videos, kept apart from the website.

- **Branches** _(human decision, 2026-11-11)_:
  - `exp/main`: the base, based on `main` and rebased onto newer `main` over time; it holds what all experiments share (these rules, the budget tool `tools/yt.py`, the uv env, the ledger). Experiment files live only in `experiments/`, so rebases don't conflict.
  - `exp/NNN-short-title`: one per experiment, named after its folder (`exp/001-variant-pairs`), based on `exp/main` and rebased onto it over time. When an experiment is ready, it is merged into `exp/main` the website's way (rebase, checks, `git merge --ff-only`).
  - Pushed to `origin`, so they are public. _(human decision: based on main; no need to keep it private)_
- **Tests** _(human decision)_: experiment code has tests too (pytest, in `tests/` for `tools/` and in `NNN-*/tests/` for an experiment's own scripts), with no network or YouTube requests. Before a commit: `uv run ruff check .` and `uv run pytest` pass.
- **Never merged into `main`** unless the user explicitly says so in that request; double-check before any merge. Publishing results (e.g. as a blog post, plan 018) is decided later. _(human decision)_
- Never commit downloaded clips (`cache/` is ignored) or server details (paths, hosts, usernames): read them from env vars.

## Experiments

| # | Folder | Question |
|---|---|---|
| 001 | `001-variant-pairs/` | Do studios publish near-identical versions of one video, and is there evidence they test the variants against each other? |

Each experiment folder has a `PLAN.md`: question, hypotheses, method, steps, results so far, open questions. Decisions are marked _(human decision)_ in place, as in the website's plans.

## YouTube budget

Experiments share the server's IP and Data API key with the collector and live analysis (plan 013). A YouTube block stops all three: the first one (2026-11-01) came after ~5 downloads in 1 h / 121 in 24 h and lasted 6–10 h; the latest was 2026-11-10 02:39 UTC.

There are two budgets, one per kind of limit YouTube has. Request kinds, cheapest first; use the cheapest that answers the question:

| Kind | What | Counts against |
|---|---|---|
| API | Data API calls (`videos.list`, `playlistItems.list`, `channels.list`: 1 unit; `search.list`: 100 units) | **API units**: the key's official quota of 10,000 a day (Pacific time) |
| Image | Thumbnails, storyboards (frame sprites), from YouTube's image servers | No known limit; logged, not budgeted; one at a time with a random gap of 0.5–1.5 s (~1 a second), to be friendly to their servers _(human decision, 2026-11-11)_ |
| Player | Any yt-dlp call, including metadata-only | **Downloads**: YouTube's unpublished per-IP limit, which blocks the server when exceeded |

Limits _(human decision)_:

- **Downloads: at most 50 player requests a day (UTC)** _(human decision, 2026-11-11; was 10)_, no hourly limit, but a random gap of 45–135 s after each download _(human decision)_; an experiment's plan may allow more for one run (`EXP_PLAYER_PER_DAY`; gaps: `EXP_IMAGE_GAP`, `EXP_PLAYER_GAP`). At most one download per video, ever: the whole video at ≤ 360p with audio, cached in `cache/` and reused by every signal. Wait while the collector is blocked (its `blocked_until`).
- **API units: 2,000 a day**; more when needed, decided on the day from that day's use. The collector budgets 7,000 of the 10,000 and uses ~1,700–3,100 (2026-10-30 to 11-09). Never re-fetch a page already read: save results and page tokens.

`tools/yt.py` is the only way experiments reach YouTube: it checks the limits, then writes one row per request to `ledger.tsv`. The ledger stays separate from the collector's `attempts` table (experiments never write to the prod database); the later block analysis joins the two. _(human decision)_

Each experiment branch commits the ledger rows it made; `.gitattributes` merges the ledger as a union, so rebases and merges keep every branch's rows.

`ledger.tsv` columns: `at` (UTC), `experiment`, `kind` (API, image, player), `what`, `target` (video/channel ID or request), `units`, `outcome`, `note`.
