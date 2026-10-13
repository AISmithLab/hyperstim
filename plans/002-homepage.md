# 002 — Homepage

## Goal

Build the home page (`/`) following the look of the mockup's home panel: hero with illustration on top, "check a video" card bottom-left, and a top-ranked table bottom-right (replacing the mockup's highlights block). Build it first on mock data, then add the backend endpoints that feed it.

## Decisions

- **Scope.** This plan also covers what the home page needs to exist at all: frontend scaffold, root layout (header + footer), the typed API client, and the backend scaffold with the endpoints below. Cookie banner, other pages, live analysis, and the Pages deploy workflow are later plans.
- **Score shown.** "Stimulation score", 0–100 = the dataset's composite percentile (higher = more intense production than other videos in the dataset). Shown as an integer plus a small bar.
- **"Top" means highest score**, so the table is titled "Most stimulating", never "top-rated" or "best". It keeps this title even though it also shows the least stimulating (see below). _(briefly “Most and least stimulating”)_
- **High ranks are a warning, not a prize.** The table highlights the most stimulating videos/channels as the ones to watch out for. Nothing in it looks like an award: no gold/silver/bronze, trophies, stars, or crowns. Ranks 1–3 get a warning style (see table card below); this is shown by design only, with no extra text.
- **Both ends in one table.** The table shows the 3 most and the 3 least stimulating, separated by a "…" row, so parents see the range. _(was: no calm view; only the most stimulating, calmer videos on `/rankings`)_
- **Table rows.**
  - Videos: rank, video title (channel name in small text below it), score. Row links to `/video?id=…`.
  - Channels: rank, channel name, score, plus "N videos" in small text below the name. Not linked for now (no channel page yet).
  - Ranks 1–3, a "…" row, then the 3 lowest-scoring, in rank order (e.g. 1, 2, 3, …, 10,410, 10,411, 10,412). Their ranks count back from `total`. When the dataset is too small for a gap, overlapping items are dropped and the "…" row is left out. Then a "See full rankings →" link to `/rankings`. _(was: top 5 rows)_
- **Channel score** = mean stimulation score of the channel's videos in the dataset; only channels with ≥ 5 scored videos are ranked.
- **Art location** changes from 001: originals live in `frontend/art/`, and `public/images/` holds only generated WebP files (see **Images**).
- **Mock data** uses made-up video titles and channel names, so the public repo makes no claims about real channels.
- **Analyze form, this plan only:** parses a YouTube link or 11-char ID client-side; invalid input shows an inline error; valid input navigates to `/video?id=…` (page built in a later plan). Live analysis wiring comes with that plan.

## Design

### Layout

| Width | Layout |
|---|---|
| `lg`+ (≥1024) | Row 1: hero text (left, ~55%) · illustration (right). Row 2: check-a-video card (left, ~45%) · table card (right). Max-width container. |
| `md` (768–1023) | Hero text full width, illustration below it at ~70% width, centred. Row 2 stacked: form card, then table card. |
| < `md` (320–767) | Single column: heading → illustration (full width) → paragraph → form card → table card. Decorations hidden. Input and button stack, both full width. |

### Elements, top to bottom

All visible text is in **Copy** below; this list says only where things go.

1. **Header** (shared layout): skip link (visible on focus) first; logo left, links to `/`; nav right with the current page underlined and `aria-current="page"`; `sun_1.png` small, decorative, beside the nav on `lg`+. Below `lg`: menu button opens the nav as a full-width list.
2. **Hero, left.** H1 (Shantell Sans _(was: Patrick Hand)_, navy, large) with a yellow marker highlight behind its last words; intro in two paragraphs (Nunito, slate). _(was: one intro paragraph plus a small note under it)_
3. **Hero, right.** `kid_1.png`, `aria-hidden`, no speech bubble. _(was: with a hand-styled CSS speech bubble saying “What’s next?”)_
4. **Check-a-video card** (butter panel `#FEF8D4`, large rounded corners). `grass_1.png` / `flower_1.png` peeking from the bottom-left corner on `md`+. H2 with an info button on the same row, right-aligned with the “Check video” button (small navy-outlined circle, navy “i” in Shantell Sans _(was: Patrick Hand)_, no fill; 44 px touch target) _(was: right next to the H2; briefly a larger sunny-yellow filled circle)_, visible label + input (white, 2px navy outline, thick sunny-yellow ring on focus _(was: light grey-navy outline, default focus outline)_), primary button, inline error (`aria-live="polite"`). The intro and hint live in a small popup from the info button, styled as a speech bubble (white, 2px navy outline, tail pointing at the button, slight tilt) _(was: plain white card with subtle border)_: shown while the mouse hovers; a click/tap or Enter/Space keeps it open until clicked again, Escape, or a click outside. Not hover-only, so it works on touch and keyboard. The input's `aria-describedby` points to the popup text, so screen readers get it without opening it. _(was: intro under the H2 and hint under the button, always visible)_
5. **Table card** (white card, subtle border, large rounded corners). `flower_2.png` decorative at top-right corner on `md`+.
   - H2 with the chip group to its right (wraps below it on narrow screens). Pill chips; active chip filled sunny yellow. Two buttons with `aria-pressed`; default Videos.
   - Table with an sr-only caption naming the current view. Columns: rank, name, score. The Score header has a small info "i" right after it (same component and behaviour as the check-a-video card) with the score explanation. _(was: explanation as a footnote under the table)_
   - Every row has the same fixed height (room for a two-line name plus the second line), so the card doesn't change height when switching views or while loading. The "…" row is short and `aria-hidden`; screen readers get the gap from the rank numbers. _(was: rows sized to content)_
   - Rank cell: ranks 1–3 sit inside a hand-drawn warning triangle (art below), number in navy, centred in the lower part of the triangle; other ranks are a plain slate number with a thousands separator. _(was: ranks 4–5)_ The triangle is `aria-hidden`; the rank number stays real text, and no "warning" wording is added. The triangle's shape carries the meaning, so it doesn't rely on colour alone. No row tint. _(was: rows 1–3 get a very light coral row tint)_
   - Name cell: name clamped to 2 lines (full name stays in the DOM); second line in small text (channel name for videos, video count for channels).
   - Score cell: integer, then a bar (yellow → orange → coral by value) that is `aria-hidden`.
   - "See full rankings" link. _(was: footnote, then the link)_
   - States: loading = 3 grey skeleton rows, the "…" row, 3 more _(was: 5 rows)_ (`aria-busy`) plus sr-only loading text; error = message + retry button; empty = message.
6. **Footer** (shared layout): copyright on the left, footer links on the right on `md`+ _(was: links left, copyright right)_; stacked below `md` with the links first. _(was: also a “Source code on GitHub” link)_ No contact email for now. "Cookie settings" comes with the cookie-banner plan.

### Copy

Final text for every string on the page. `{…}` = filled in at runtime. Arrows (→) after link/button text are decorative (`aria-hidden`). Use typographic apostrophes (’).

**Page metadata**

| Where | Text |
|---|---|
| `<title>` | HyperStim? - How stimulating are kids’ videos? |
| Meta description | See how fast, loud, and intense children’s YouTube videos are. |

**Header**

| Where | Text |
|---|---|
| Skip link | Skip to main content |
| Logo alt | HyperStim? home |
| Nav `aria-label` | Main |
| Nav items | Home · Rankings · Compare · How it works · About |
| Menu button (closed / open) | Menu / Close menu |

**Hero**

| Where | Text |
|---|---|
| H1 | How stimulating are the videos **your child watches?** (bold part = marker highlight) |
| Intro, paragraph 1 | *HyperStim?* (italic, the site’s name as in the logo) measures the production style of children’s videos: how fast they cut, how loud they get, and how saturated the colors are. _(was: “HyperStim”, upright, no “?”)_ |
| Intro, paragraph 2 | See how any video compares with {N} other kids’ videos. _(was: “… with {N} others in our research dataset.”; before that one paragraph with paragraph 1 and “more than {N}”)_ |
| `{N}` | Video count from `/api/meta`, rounded down to whole thousands as “{n}k+” (10,412 → “10k+”); below 1,000, the exact count. Before it loads or if it fails: “thousands of”. _(was: “more than 5,400”, rounded down to the nearest 100)_ |
| Illustration alt | (empty, decorative) |

**Check-a-video card**

| Where | Text |
|---|---|
| H2 | Check a video |
| Info button label (sr) | More about checking a video |
| Info popup, line 1 | Paste a YouTube link or video ID to see its stimulation score. _(was: intro under the H2)_ |
| Input label | YouTube link or video ID |
| Placeholder | https://www.youtube.com/watch?v=… |
| Button | Check video → |
| Info popup, line 2 | Works best with children’s videos up to 15 minutes. _(was: hint under the button)_ |
| Error: empty | Paste a YouTube link or video ID first. |
| Error: not valid | That doesn’t look like a YouTube link or video ID. |

**Table card**

| Where | Text |
|---|---|
| H2 | Most stimulating _(briefly “Most and least stimulating”)_ |
| Chip group `aria-label` | Show ranking of |
| Chips | Videos · Channels |
| Caption (videos / channels) | The 3 most and 3 least stimulating videos / The 3 most and 3 least stimulating channels _(was: Top 5 most stimulating videos / channels)_ |
| Column headers | # (sr-only: Rank) · Video *or* Channel · Score + info “i” |
| Score info button label (sr) | About the score |
| Video row, second line | {channel name} |
| Channel row, second line | {n} videos |
| Score info popup | Score 0–100: how intense the production is compared with the rest of our dataset. / A channel’s score is the average of its videos. (two lines) _(was: footnote under the table)_ |
| Link | See full rankings → |
| Loading (sr-only) | Loading rankings… |
| Error | We couldn’t load the rankings. |
| Error button | Try again |
| Empty | No rankings yet. |

**Footer**

| Where | Text |
|---|---|
| Footer nav `aria-label` | Footer |
| Links | Privacy policy · About us · FAQ |
| Copyright | © {year} HyperStim Research Team _(was: “research team”, lower case)_ |

All decorative images (`kid_1`, `sun_1`, `grass_*`, `flower_*`, warning triangle) have `alt=""`.

### Images

- **Two folders, so the art backlog never reaches the delivered site:**
  - `frontend/art/`: every original from the team, used or not (the backlog). Committed, but not deployed: Next.js only ships what's in `public/`.
  - `frontend/public/images/`: generated, git-ignored. A script (`npm run images`, run automatically before `dev` and `build`) converts only the images listed in `frontend/art/used.json` to WebP, resized to 2× their largest display width (≈ 100–300 KB instead of 1–2 MB). Unused art adds nothing to the site's size or load time.
  - Every page uses the same images through `/images/<name>.webp` (a small helper adds the `basePath`). Using a new image = add one line to `used.json`.
  - Conversion uses `sharp` (dev dependency only).
- Used on this page: `Logo`, `kid_1`, `sun_1`, `grass_1`, `flower_1`, `flower_2`, and the warning triangle once it arrives.
- **New art needed from the team: warning triangle** (`warning_1.png`).
  - Shows: a road-sign-style warning triangle with rounded corners, empty inside (no "!"); the rank number is laid over it in code.
  - Colours: sunny yellow fill `#F8D040`, coral outline `#F85858`.
  - Style: hand-drawn crayon, matching the other illustrations; slightly wobbly edges.
  - Size: 1:1 canvas, at least 256 × 256 px, triangle filling the canvas; transparent PNG.
  - Until it arrives, ranks 1–3 render as plain numbers (no placeholder art).

## API contract (frontend `api.ts` ↔ backend)

```
GET /api/meta
  → { videoCount: number, channelCount: number, updatedAt: string /* ISO date */ }
GET /api/videos?sort=score_desc|score_asc&limit=3
  → { items: [{ id: string, title: string, channel: string, score: number }], total: number }
GET /api/channels?sort=score_desc|score_asc&limit=3&minVideos=5
  → { items: [{ name: string, score: number, videoCount: number }], total: number }
```

`/api/videos` gets search/filters/pagination in the rankings plan; this plan implements only `sort` (`score_desc`, `score_asc`; _was: `score_desc` only_) and `limit`. The home table makes one request per end and view. `score` is rounded to 1 decimal by the backend; the frontend shows it as an integer.

## Steps

1. **Frontend scaffold.** Next.js (App Router, TS, static export, `basePath` from env), Tailwind with the palette from 001 as theme tokens, Shantell Sans _(was: Patrick Hand)_ + Nunito via `next/font`, ESLint, Vitest + Testing Library. npm scripts: `lint`, `typecheck`, `build`, `test`. GitHub Actions CI running them.
2. **Images.** Move the originals from `public/images/` to `frontend/art/`; add `used.json` and the conversion script; git-ignore `public/images/`. Request the warning triangle from the team.
3. **Shared layout.** Header (with mobile menu) and footer as above.
4. **API client + mocks.** Types and functions for the three endpoints in `src/lib/api.ts`; mock responses (made-up data, ~10 videos, ~6 channels) used when `NEXT_PUBLIC_API_MOCK=1`.
5. **Home page.** Hero, check-a-video card (with link/ID parser), table card with chip toggle and all states.
6. **Frontend tests + review.** Unit tests: link/ID parser, chip toggle switches table and caption, loading/error/empty states. Manual check at 320, 360, 768, 1280, 1920 px and keyboard-only. Stop here for review of the page on mock data.
7. **Backend scaffold.** FastAPI app, env config (`DATASET_PATH`, `CORS_ORIGIN`), `.env.example`, ruff + mypy + pytest, CI job. Dataset loaded into memory at startup.
8. **Backend endpoints.** `/api/health`, `/api/meta`, `/api/videos` (sort + limit), `/api/channels` (sort, limit, minVideos). Pytest against a small synthetic fixture dataset (ranking order, channel threshold, limits, bad params → 422).
9. **Connect.** Frontend uses the real backend when `NEXT_PUBLIC_API_BASE` is set; run both locally and check the page end to end.

## Review decisions

Human decisions from the step 6 review of the page on mock data (recorded per the human-decision rule in `CLAUDE.md`).

1. **Images can't be selected or dragged, on every page.** Set once for all `<img>` in the global stylesheet (`user-select: none`, `-webkit-user-drag: none`), so later pages get it without extra work.
2. **Heading font is Shantell Sans, weight 600, on every page** (headings, the info “i”, and any other hand-lettered text; body and UI stay Nunito). Chosen after comparing ten handwritten Google Fonts on the home hero: marker-style and very readable. Replaces 001's example **Patrick Hand** (thin, narrow pen strokes that read like notebook handwriting). Shantell Sans runs wider, so heading sizes are about 10 % smaller than with Patrick Hand.

## Open questions

None.

## Resolved questions

1. Copy: approved as in **Copy**, with the user's edits.
2. Channel ranking: mean score, channels with ≥ 5 scored videos.
3. Images: originals (incl. unused ones) kept in `frontend/art/`; only used images are converted and shipped.
4. Footer: no contact email for now; copyright holder “HyperStim Research Team” _(was: “HyperStim research team”)_.
5. Header nav: Home · Rankings · Compare · How it works · About; FAQ only in the footer (overrides 001).
