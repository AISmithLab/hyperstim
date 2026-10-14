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

## Live analysis

A video that isn't in the dataset is analyzed on request (`POST /api/analyses/{id}`, polled with `GET /api/analyses/{id}`; `src/hyperstim_api/analysis.py`): check YouTube's made-for-kids flag (Data API, `YOUTUBE_API_KEY`) and look up with yt-dlp, download the clip and measure it with the unchanged pipeline scripts, then score it against the dataset. Live results never change the dataset's scores, rankings or counts; `GET /api/videos/{id}` serves them like dataset videos.

- One video at a time, in a background thread of the API process; up to 10 more wait in a queue. **Run the API as a single process** (no `--workers`).
- Measuring uses at most 4 cores (`MEASURE_CORES` in `analysis.py`; more barely help, since most of the work is single-threaded), leaving the rest of the server free.
- Each video's state is `ANALYSIS_DIR/<id>.json`. Results are kept until the file is deleted; videos waiting or running when the API stopped start again at the next start.
- The per-IP limit sees the visitor's address only if uvicorn trusts the reverse proxy: on the server, run it with `--proxy-headers --forwarded-allow-ips <proxy address>`. The counts are kept in memory only.
- Needs ffmpeg/ffprobe and deno on the server (see Prerequisites); `deno` must be on the service's `PATH`.
- The progress estimate uses typical step durations (`TYPICAL_S` in `analysis.py`); each finished analysis logs its step times, so re-time them if the server changes.

## Pipeline

See [`pipeline/README.md`](pipeline/README.md).
