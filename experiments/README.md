# Experiments

Research experiments on YouTube videos, kept apart from the website.

- **Branch:** `experiments`, based on `main` and rebased onto newer `main` over time; experiment files live only in `experiments/`, so rebases don't conflict. Checked out as its own worktree next to the website checkout. Pushed to `origin`, so it is public. _(human decision: based on main; no need to keep it private)_
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
| Image | Thumbnails, storyboards (frame sprites), from YouTube's image servers | No known limit; logged, not budgeted |
| Player | Any yt-dlp call, including metadata-only | **Downloads**: YouTube's unpublished per-IP limit, which blocks the server when exceeded |

Limits _(human decision)_:

- **Downloads: at most 10 player requests a day (UTC)**, no hourly limit. At most one download per video, ever: the whole video at ≤ 360p with audio, cached in `cache/` and reused by every signal. Wait while the collector is blocked (its `blocked_until`).
- **API units: 2,000 a day**; more when needed, decided on the day from that day's use. The collector budgets 7,000 of the 10,000 and uses ~1,700–3,100 (2026-10-30 to 11-09). Never re-fetch a page already read: save results and page tokens.

`tools/yt.py` is the only way experiments reach YouTube: it checks the limits, then writes one row per request to `ledger.tsv`. The ledger stays separate from the collector's `attempts` table (experiments never write to the prod database); the later block analysis joins the two. _(human decision)_

`ledger.tsv` columns: `at` (UTC), `experiment`, `kind` (API, image, player), `what`, `target` (video/channel ID or request), `units`, `outcome`, `note`.
