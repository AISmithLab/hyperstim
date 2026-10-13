# HyperStim backend

FastAPI app that serves the website's data API from the dataset in `data/`, plus the analysis pipeline (`pipeline/`) for live analysis. The API contract is mirrored by the frontend's `src/lib/api.ts`; change both together.

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

## Pipeline

See [`pipeline/README.md`](pipeline/README.md).
