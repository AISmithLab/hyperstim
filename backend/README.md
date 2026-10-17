# HyperStim backend

FastAPI app that serves the website's data API from the dataset in `data/`, plus live analysis of other videos with the analysis pipeline (`pipeline/`). The API contract is mirrored by the frontend's `src/lib/api.ts`; change both together.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/). It installs the pinned Python (`.python-version`) and all Python dependencies, including dev tools.
- For the pipeline only (live analysis, not needed for the data API or tests):
  - **ffmpeg + ffprobe 6.1.1**, the version the dataset was extracted with (Ubuntu 24.04: `apt install ffmpeg`).
  - **[deno](https://deno.com/)**, the JavaScript runtime yt-dlp uses for YouTube (`--remote-components ejs:github`).

## Setup

```sh
cd backend
uv sync
cp .env.example .env
```

## Environment variables

See `.env.example`.

| Variable | Purpose |
|---|---|
| `DATASET_PATH` | Dataset TSV (`data/videos.tsv`); its `videos.meta.json` must sit next to it. |
| `CORS_ORIGIN` | The one origin allowed to call the API (the frontend's URL). |
| `ANALYSIS_DIR` | Folder for live analyses: one JSON result per video, plus the running video's temporary clip. Outside the repo on the server (locally `analysis/`, git-ignored). |
| `ANALYSIS_LIMIT_PER_IP` | New live analyses one IP address may start per hour; `0` = no limit (local development). Optional, default 5. |
| `YOUTUBE_API_KEY` | YouTube Data API key for the live analysis's made-for-kids check (1 quota unit per new video). Empty = no check, for local development; always set it on the server. Never commit it. |
| `YTDLP_COOKIES` | Optional cookies file for yt-dlp, if YouTube asks for one. Never commit it. |

## Commands

| Command | What it does |
|---|---|
| `uv run --env-file .env uvicorn --factory hyperstim_api.main:create_app --reload` | Dev server at http://localhost:8000 (API docs at `/docs`) |
| `uv run ruff check` | Lint |
| `uv run ruff format` | Format (CI runs `ruff format --check`) |
| `uv run mypy` | Type check |
| `uv run pytest` | Tests |

## Dataset

`data/videos.tsv` (one row per video: ID, title, channel, category, publication date, duration, and the 12 raw features) and `data/videos.meta.json` (source commit, cache version, date) are copied from the research repo by:

```sh
uv run python scripts/import_dataset.py <path-to-research-repo-checkout>
```

The script only reads the research repo, checks the data against its figures of record, and refuses to write if anything is off. Re-run it when the research data changes and commit both files. Video clips are never stored here.

At startup the app scores every video (`src/hyperstim_api/scoring.py`): each of the 12 features is ranked as a percentile within the dataset, the 12 percentiles are averaged, and the score is that average's percentile among all videos (0 = least, 100 = most stimulating). A channel's score is the mean of its videos' scores.

Rankings (`GET /api/videos` and `GET /api/channels`; `src/hyperstim_api/ranking.py`) are sorted once at startup for the score and each feature: most intense first, ties by ID. Rows with no value come last and get no rank; on a per-minute feature, zero events counts as no value. A request filters by category (`sort`, `order`, `category`, `q`, `offset`, `limit`; channels also `minVideos`), and the ranks are counted within that category. Calmest first (`order=asc`) reverses the list and counts the ranks from the calm end (1 = the calmest). Search matches without regard to case or accents and doesn't change ranks. A channel is listed under a category when at least one of its videos is in it.

## Live analysis

A video that isn't in the dataset is analyzed on request (`POST /api/analyses/{id}`, polled with `GET /api/analyses/{id}`; `src/hyperstim_api/analysis.py`): check YouTube's made-for-kids flag (Data API, `YOUTUBE_API_KEY`) and look up with yt-dlp, download the clip and measure it with the unchanged pipeline scripts, then score it against the dataset. Live results never change the dataset's scores, rankings or counts; `GET /api/videos/{id}` serves them like dataset videos.

- One video at a time, in a background thread of the API process; up to 10 more wait in a queue. **Run the API as a single process** (no `--workers`).
- Measuring uses at most 4 cores (`MEASURE_CORES` in `analysis.py`; more barely help, since most of the work is single-threaded), leaving the rest of the server free.
- Each video's state is `ANALYSIS_DIR/<id>.json`. Results are kept until the file is deleted; videos waiting or running when the API stopped start again at the next start.
- The per-IP limit sees the visitor's address only if uvicorn trusts the reverse proxy: on the server, run it with `--proxy-headers --forwarded-allow-ips <proxy address>`. The counts are kept in memory only.

## Thumbnails

`GET /api/thumbnails/{id}?size=hq|mq` (`src/hyperstim_api/thumbnails.py`) serves a video's YouTube thumbnail (`hq` 480×360, `mq` 320×180), so visitors' browsers don't contact YouTube before they press play (the privacy policy says so; plan 009). Only for videos in the dataset or requested for live analysis; anything else is 404. The server fetches the image from YouTube on each request and stores nothing; the response tells the visitor's browser to keep it for a day. A thumbnail YouTube doesn't have is 404; YouTube unreachable is 502.

## Privacy

The privacy policy (`/privacy`, plan 009) promises what the server keeps; keep the server set up to match:

- uvicorn's access log is off in the app (`create_app`), so no flag is needed. The reverse proxy already logs every request (deleted after 14 days); uvicorn's would be a second copy with visitors' IPs, kept as long as the server keeps the service's output. The app's own log lines contain no IPs.
- The reverse proxy's access and error logs are deleted after 14 days.
- A change to what the backend stores or logs updates the policy in the same change.

## Channel lookup

`GET /api/channel-lookup?url=…` (`src/hyperstim_api/channel_lookup.py`) finds the channel behind a YouTube channel link (`/channel/UC…`, `/@handle`, `/c/…`, `/user/…`; not video links), and says whether it's in the dataset; the compare page and the rankings search use it. A `/channel/UC…` link is answered from what we have. A handle, `/c/` or `/user/` link asks YouTube with yt-dlp (under a second), is cached in memory for a day, and counts toward the same per-IP limit as new live analyses (`ANALYSIS_LIMIT_PER_IP`).
- Needs ffmpeg/ffprobe and deno on the server (see Prerequisites); `deno` must be on the service's `PATH`.
- The progress estimate uses typical step durations (`TYPICAL_S` in `analysis.py`); each finished analysis logs its step times, so re-time them if the server changes.

## Pipeline

See [`pipeline/README.md`](pipeline/README.md).
