# 001 — Overall architecture

## Goal

Replace the old static site (vanilla HTML/JS, dataset baked into a ~10 MB JS file, separate live-analysis API) with a maintainable Next.js frontend and a single backend that serves both the dataset and live analysis.

## Repo layout

```
frontend/   Next.js app (static export → GitHub Pages)
backend/    FastAPI app (runs on our server)
plans/      numbered plans
.github/workflows/   CI + Pages deploy
```

## Frontend

- Next.js App Router, TypeScript, Tailwind, `output: "export"`. Deployed by a GitHub Actions workflow on push to `main`.
- Backend URL injected at build time via `NEXT_PUBLIC_API_BASE` (GitHub Actions variable), not hard-coded.
- Served as a GitHub Pages project page, so the app uses `basePath` = `/<repo-name>` (set from env so it can change).
- Pages:
  - `/` Home: one-line pitch, one input that accepts a YouTube link or a video ID (no file upload), a few highlighted videos, links into the rest of the site.
  - `/rankings` Sortable, filterable, paginated table of all videos (score, category breakdown, topic, era, etc.). Each row links to its detail page.
  - `/video?id=<youtube-id>` Per-video detail: embedded YouTube player, score, category breakdown, metadata, "compare with…". Query param rather than `/video/[id]` because a static export can't pre-render pages for videos analyzed live.
  - `/compare` Two videos side by side with per-category breakdown; state in the URL query (`?a=…&b=…`) so links are shareable.
  - `/how-it-works` Method explained for a general audience (features → categories → score).
  - `/about` Team, paper, contact.
  - `/faq` Accordion of common questions.
- Shared layout: top nav, footer, light/dark theme. Data fetched client-side from the backend with small typed hooks; static text pages need no backend.
- Home input flow: parse link/ID → if the video is in the dataset, go to its detail page; otherwise start live analysis, show progress, then land on the detail page.
- Carry over the useful old-site behaviours (shareable compare links, accessible chart fallbacks), re-implemented rather than copied.

## Backend

- FastAPI + uvicorn, run as a systemd service behind the existing nginx (TLS). Deployment files live only on the server.
- Config via env (`.env` on server, `.env.example` in repo): dataset path, pipeline path, allowed CORS origin, rate limits.
- Endpoints (v1):
  - `GET /api/videos` — list with search, filters, sort, pagination (powers rankings + search).
  - `GET /api/videos/{id}` — one video with full breakdown.
  - `GET /api/meta` — filter options, dataset size, last-updated date.
  - `POST /api/analyze` (YouTube link or video ID only), `GET /api/analyze/{job_id}` — live analysis (same contract as today's API, cleaned up).
  - `GET /api/health`.
- Data exposure: the API returns video IDs, public metadata, and scores/features only. Downloaded clips are never served, never committed, and are deleted once analysis finishes; playback on the site uses YouTube embeds.
- Data: dataset loaded into memory at startup from a file outside the repo (5k rows is small). Analysis jobs and results stored in SQLite so they survive restarts. Analysis runs the existing pipeline via its configured path (not vendored into this repo).
- Tests: pytest for endpoints with a small synthetic fixture dataset.

## Migration

1. Scaffold both apps + CI (lint, typecheck, build, tests).
2. Backend data endpoints, then frontend pages against them.
3. Port live analysis into the new backend; run it on a new port alongside the current API.
4. Switch nginx + Pages over; retire the old API and site.

## Resolved questions

1. Dataset is public via the API (IDs, metadata, scores); downloaded clips are never exposed.
2. GitHub Pages project page.
3. Yes — rankings rows link to a per-video detail page.
4. No file upload; YouTube links or video IDs only.
