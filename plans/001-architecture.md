# 001 — Overall architecture

**Area:** Site-wide: architecture, hosting, API conventions, privacy, and rules that apply to every page.

## Goal

Replace the old static site (vanilla HTML/JS, dataset baked into a ~10 MB JS file, separate live-analysis API) with a maintainable Next.js frontend and a single backend that serves both the dataset and live analysis.

## Repo layout

```
frontend/   Next.js app (static export → GitHub Pages)
backend/    FastAPI app (runs on our server)
plans/      numbered plans
.github/workflows/   CI (plan 012) + Pages deploy
README.md, DEVELOPMENT.md   repo front page, developer guide (below)
```

### README and developer guide _(human decision, 2026-10-24: the README read like a developer guide)_

- **`README.md` is for anyone who lands on the repo** (parents, researchers, developers): what the site is, not how to work on it.
  1. `# HyperStim?`, the site's name _(human decision, 2026-10-24)_, the SonarQube Cloud badges (quality gate, coverage, reliability rating; each links to the project's new-code summary) and the Deploy workflow's status badge _(human decision, 2026-10-24)_, and a one-line pitch: how stimulating are kids' YouTube videos?
  2. **What it is:** one paragraph: a platform that helps parents understand how stimulating children's videos are by analyzing audiovisual features (rapid scene changes, bright colors, loud sounds), so they can explore and compare videos and make more informed decisions about what their children watch. The name links to the live site _(human decision, 2026-10-24: better framing)_.
  3. **What you can do:** check any video by its link; rankings of videos and channels; compare two videos or channels; how it works. One line each, linking to the site's pages.
  4. **What the score is and isn't:** production style only, measured from a 5-minute clip; it doesn't judge content, educational value or age appropriateness. Same copy limits as the site (plan 006): no claims about effects on children.
  5. **How it's built:** 2–3 lines (static Next.js site on GitHub Pages; Python/FastAPI API with the video dataset and the analysis pipeline), linking to `DEVELOPMENT.md`.
  6. **Privacy** (link to the policy) and **License** (Apache 2.0, link to `LICENSE`).
- **No numbers that go stale** (video count, dates) and **no link to the research** _(human decision, 2026-10-24)_.
- **`DEVELOPMENT.md` is the developer entry point:** the old README's content, moved unchanged (repo map, "Run locally" from plan 003, "Release" from plan 010). It links to the `frontend/`, `backend/` and `deploy/` READMEs.
- **Plan 010's pending switch to semantic-version tags** also changes the "Release" section: whichever change lands second updates it in `DEVELOPMENT.md` _(human decision, 2026-10-24)_.

## Frontend

- Next.js App Router, TypeScript, Tailwind, `output: "export"`. Deployed by a GitHub Actions workflow when a release tag is pushed, so `main` is the latest dev version and the live site can be behind it (plan 010) _(human decision, 2026-10-17)_.
- Backend URL injected at build time via `NEXT_PUBLIC_API_BASE` (GitHub Actions variable), not hard-coded.
- Served as a GitHub Pages project page, so the app uses `basePath` = `/<repo-name>` (set from env so it can change).
- Pages:
  - `/` Home: one-line pitch, one input that accepts a YouTube link or a video ID (no file upload), a few highlighted videos, links into the rest of the site.
  - `/rankings` Sortable, filterable, paginated table of all videos (score, category breakdown, topic, era, etc.). Each row links to its detail page.
  - `/video?id=<youtube-id>` Per-video detail: embedded YouTube player, score, category breakdown, metadata, "compare with…". Query param rather than `/video/[id]` because a static export can't pre-render pages for videos analyzed live.
  - `/compare` Two videos side by side with per-category breakdown; state in the URL query (`?a=…&b=…`) so links are shareable.
  - `/how-it-works` Method explained for a general audience (features → categories → score).
  - `/about` Who makes the site (the AI Smith Lab at UC San Diego), why, and how to get in touch (plan 015) _(human decision, 2026-10-26: built; no paper)_.
  - `/faq` Accordion of common questions.
  - `/privacy` Privacy policy (plan 009): what we store, why, and for how long; GitHub Pages, YouTube and Google Analytics; no cookies from us unless the visitor accepts analytics _(2026-10-17, plan 009)_. Embeds use `youtube-nocookie.com`. **The policy must stay true:** every change is checked against it; a change to what the site or backend stores, logs, or loads from third parties that the policy would have to reflect is agreed with the team before it's built, and then updates the policy in the same change _(human decision, 2026-10-16, plan 009; agreed first: 2026-10-17)_.
- Shared layout on every page (in the root layout):
  - Header: site name/logo (links home) and nav (Home, Rankings, Compare, How it works, About _(plan 015, 2026-10-26)_), with the current page marked.
  - Cookie banner for Google Analytics (Accept / Reject of equal weight) and a "Cookie settings" button in the footer _(human decision, 2026-10-17, plan 009: GA added; the rules require a banner only with analytics)_. Nothing from Google loads before Accept. YouTube players load only after "Play video" is clicked (plan 004).
  - Site icon (browser tab, bookmarks, home screen): the logo's "H" _(human decision, 2026-10-17: without one, browsers showed the default icon of the domain the site is served from)_. Next.js metadata files `src/app/icon.png` and `apple-icon.png`, so every page declares it under the site's base path; how it's made is in `STYLE.md`.
  - Footer: only what the header doesn't have _(plan 015, 2026-10-26)_: "© {year} HyperStim?" on the left _(human decision, 2026-10-26: no lab or school named there)_; on the right Privacy policy, Cookie settings (only when there is a choice to make, plan 009), GitHub ↗ (the repo, new tab) _(human decision, 2026-10-26)_. No FAQ (the questions are on How it works, in the header), no About (in the header), no contact email (the form is on the About page).
- Data fetched client-side from the backend with small typed hooks; static text pages need no backend.
- Responsive (RWD), mobile-first with Tailwind's default breakpoints; supported from 320 px phones up to wide desktop monitors:
  - Content in a max-width container on large screens so lines and tables don't stretch.
  - Nav collapses into a menu button on small screens.
  - Rankings: table on `md`+, stacked cards on phones.
  - Compare and detail pages: side-by-side on `lg`+, stacked on smaller screens.
  - Touch targets ≥ 44 px; no hover-only interactions; YouTube embeds and charts scale with width.
  - Check each page at 360, 768, 1280, and 1920 px wide before merging.
- Home input flow: parse link/ID → if the video is in the dataset, go to its detail page; otherwise start live analysis, show progress, then land on the detail page.
- Carry over the useful old-site behaviours (shareable compare links, accessible chart fallbacks), re-implemented rather than copied.

## Visual style

Guided by `frontend/design/Design Mockup.png`. It sets the look only: its text, names, and layouts are not ours to copy.

- Look: warm and friendly, with hand-drawn crayon/watercolor illustrations, lots of whitespace, cards with large rounded corners, pastel section backgrounds, pill-shaped filter chips, and a yellow marker highlight behind key words in headings.
- Fonts (Google Fonts via `next/font`, self-hosted at build):
  - Headings, logo: a rounded handwritten font, e.g. **Patrick Hand**.
  - Body, UI, tables: a rounded sans-serif, e.g. **Nunito**.
- Palette (Tailwind theme tokens; tune for contrast during the build):

  | Role | Hex |
  |---|---|
  | Page background (white) | `#FFFFFF` |
  | Heading / nav ink (navy) | `#0F2E8A` |
  | Body text (slate) | `#4A5262` |
  | Primary button | `#0F4A9C` |
  | Marker highlight / sunny accent | `#F8E683` / `#F8D040` |
  | Stimulation scale low → high | `#F8D040` → `#F8A048` → `#F85858` |
  | Compare: video A / video B | `#FDA28C` / `#9FBBF5` |
  | Pastel panels: butter / mint / sky | `#FEF8D4` / `#E5F6E6` / `#EEF6FA` |
  | Accents: leaf green / sky blue / heart coral | `#448D62` / `#32ADF7` / `#FD7371` |

- Light theme only (no dark mode for now). Colours are never the only way information is shown (scores also carry numbers/labels).
- Illustrations live in `frontend/public/images/`. Claude Code asks for each one (object, pose, colours, size, background) and the team supplies it; no placeholder art is committed.
- **The kid** _(human decision, 2026-10-16)_:
  - **Hidden below `md` (768 px) on every page**: the hero kids, the kid on the score panel, and `kid_2` above the message box. Layouts drop the room they kept for it there.
  - **The hero kids (home, rankings, compare, how it works, privacy) have the same head size** at every width they show at. The measure is the distance between the eyes (centre to centre): **30 px at `md`, 34 px at `lg`, 40 px from `xl`**, the home kid's size on desktop. Each artwork draws the kid at its own scale, so each page's width = target ÷ the art's eye distance per image width: `kid_1` 0.087, `kid_blocks_2` 0.119, `kid_compare` 0.104, `kid_wonder` 0.110, `kid_quiet` 0.139 (privacy, plan 009; its head is turned, so the ratio comes from its head height against `kid_compare`'s).

    | Art (page) | `md` | `lg` | `xl`+ |
    |---|---|---|---|
    | `kid_1` (home) | 344 px | 392 px | 464 px |
    | `kid_blocks_2` (rankings) | 252 px | 288 px | 336 px |
    | `kid_compare` (compare) | 288 px | 328 px | 384 px |
    | `kid_wonder` (how it works) | 272 px | 308 px | 364 px |
    | `kid_quiet` (privacy) | 216 px | 244 px | 288 px |

  - The score-panel kids (video, channel) keep their own size (about 75 % of the home kid's head, plan 004). New art gets its eye ratio measured and its widths from this table.
  - `STYLE.md` gets this in the same change (the **Hand-drawn art** rule, the recurring-character line, and each page's entry); the pages' plans (002, 004–008) say what it means for each.

## Backend

- FastAPI + uvicorn, run as a systemd service behind the existing nginx (TLS). Deployment files live only on the server. Prod runs from its own clone at the release tag, separate from the dev checkout (plan 010) _(human decision, 2026-10-17)_.
- Config via env (`.env` on server, `.env.example` in repo): dataset path, pipeline path, allowed CORS origin, rate limits.
- Endpoints (v1):
  - `GET /api/videos` — list with search, filters, sort, pagination (powers rankings + search).
  - `GET /api/videos/{id}` — one video with full breakdown.
  - `GET /api/meta` — filter options, dataset size, last-updated date.
  - `POST /api/analyze` (YouTube link or video ID only), `GET /api/analyze/{job_id}` — live analysis (same contract as today's API, cleaned up).
  - `GET /api/health`.
  - `GET /api/thumbnails/{id}` — a known video's YouTube thumbnail, fetched by the backend and cached for 30 days _(human decision, 2026-10-17, plan 009)_ so visitors' browsers never contact YouTube before they press play _(human decision, 2026-10-16, plan 009)_.
- Data exposure: the API returns video IDs, public metadata, and scores/features only. Downloaded clips are never served, never committed, and are deleted once analysis finishes; playback on the site uses YouTube embeds.
- Data: dataset loaded into memory at startup from a file outside the repo (5k rows is small). Analysis results stored as plain JSON files, one per video, so they survive restarts _(human decision, plan 004: plain files are enough for this lightweight task)_. Analysis runs the existing pipeline via its configured path (not vendored into this repo).
- Tests: pytest for endpoints with a small synthetic fixture dataset.

## Migration

1. Scaffold both apps + CI (lint, typecheck, build, tests).
2. Backend data endpoints, then frontend pages against them.
3. Port live analysis into the new backend; run it on a new port alongside the current API.
4. Switch nginx + Pages over; retire the old API and site.

## Open questions

None.

## Resolved questions

1. Dataset is public via the API (IDs, metadata, scores); downloaded clips are never exposed.
2. GitHub Pages project page.
3. Yes — rankings rows link to a per-video detail page.
4. No file upload; YouTube links or video IDs only.
5. Privacy policy contact and log retention: moved to plan 009 (server logs kept 14 days) _(2026-10-16)_.
