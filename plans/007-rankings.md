# 007 — Rankings page

**Area:** Rankings page (`/rankings`) and the ranking endpoints.

## Goal

Build `/rankings`: every video or channel in the dataset, ranked by the overall stimulation score or by any one of the 12 measurements. Users can switch between videos and channels, search by name, filter by category, and page through the results. Each row shows the overall score and the 12 measurements as colour-coded numbers. The home card's "See full rankings →" already links here. The backend's `GET /api/videos` and `GET /api/channels` gain sorting by measurement, a category filter, search, and paging.

## Decisions

- **Scope.** The page, the extended list endpoints, and the page's states. Not in scope: comparing, rows for live-analyzed videos (these never join the dataset, plan 004), and downloads or exports.
- **Videos or channels**, switched with the segmented control (as on the home card). Videos are the default. Switching keeps the search, category, and ranking criterion, and goes back to page 1.
- **Columns:** rank, name, Overall, then the 12 measurements in the research taxonomy's three groups (the order of the measurement table, plan 004). Video rows: title, with the channel (linked) on a second line. Channel rows: name, with "{N} videos" on a second line. A row links to its video or channel page.
- **Ranking criterion:** Overall by default. Clicking a column header (Overall or any measurement) ranks by that column, keeping the current order _(human decision: switching columns used to jump back to most intense first)_. Clicking the selected header again flips the order. One criterion at a time.
- **Order button** _(human decision: an order switch on wide screens too, on the category row; quiet, so it doesn't race the view control for attention)_: a text button with a ⇅ icon that shows the current order ("Most intense first" / "Calmest first") and flips it on click. No border or fill (`STYLE.md`, Order button). From `lg` at the right end of the category row; below `lg` next to the "Rank by" select (under it below `sm`) _(human decision: the same button on narrow screens, in place of a segmented control)_.
- **Ranks:**
  - A rank is the position, most intense first, by the selected criterion among the rows in the selected category. **Search does not change ranks**: it only hides rows, so a search result still shows a video's real place.
  - When the order is flipped to calmest first, the list is reversed and the ranks count back from the calm end: −1 is the calmest, then −2, −3, as on the home card (screen readers: “1st calmest”) _(human decision: not the huge numbers)_. The API returns them as 1, 2, 3 in that order; the page adds the minus sign.
  - Rows with no value for the criterion ("No cuts", "No sound", "Not measured", see plan 004) get no rank ("–"). They come last in both orders.
  - A count of 0 is a value (0, plan 004) _(human decision, 2026-10-16)_, so those rows are ranked, at the calm end. **Equal values share a rank** (the first one's: 1, 2, 2, 4), so the thousands of videos tied at 0 don't get arbitrary ranks; calmest first, they are all −1 _(human decision, 2026-10-16)_.
  - Ties are listed by ID, so the order is stable (same rule as plan 002). With Overall, all categories, most intense first, the top 3 match the home card.
- **Colour-coded numbers** (**new**, the *score cell*). Each score is a navy bold number on a rounded tile. The tile's background is the score scale colour the score meter uses for that score (`filledSegments`: `sky-blue`, `leaf`, `scale-low`, `scale-mid`, `scale-high`) at 50 %. At 50 %, navy text has a contrast of at least 6.3 : 1 on every colour (checked). Full-strength colours fail on `leaf` and `scale-high`. The number carries the value, so colour is never the only cue. Empty values show a muted "–" on no tile, with the reason for screen readers.
- **Search:** one search input at the top of the card. It matches any part of the name, ignoring case and accents. For videos it searches the title and the channel name (typing a channel's name lists its videos). For channels it searches the name. Results update as the user types (300 ms debounce) and the list goes back to page 1. 1–100 characters; the field is trimmed.
- **Category filter:** "All" (the default), then the dataset's categories (Music, Narrative, Play & activity, Educational, Gaming), as chips. The five are fixed in the frontend (`lib/categories.ts`, keys `music`, `narrative`, `play`, `educational`, `gaming`, also used in the URL and the API), like the 12 measurements, so the chips show without waiting for the backend (`STYLE.md`; a select below `sm`). Only one can be picked, as with the measurement picker (plan 005). A channel is listed under a category if at least one of its videos is in it. Its scores stay whole-channel scores, the same numbers as on its channel page; the filter only picks which channels are listed _(human decision)_.
- **Channels listed:** the ones with ≥ 5 scored videos (512), as on the home card, so the two agree _(human decision)_.
- **Paging on the server:** 25 rows per page, fetched with `offset` + `limit`, so a page never loads the whole dataset. A numbered page control sits under the table (**new**, see **Design**). Changing the page moves focus to the results line above the table and scrolls it into view (instantly with reduced motion), so keyboard users start at the new rows.
- **State in the URL:** `/rankings?view=channels&sort=cuts_per_min&order=asc&category=music&q=…&page=2`, with defaults left out. Links can be shared and Back works. Typing in search replaces the history entry; every other change adds one. Invalid values fall back to their defaults. The home card's link carries its current view (`/rankings?view=channels`).
- **While loading:** skeleton rows on first load. On later changes the current rows stay, dimmed (`opacity-60`, `aria-busy`), until the new page arrives, so the table doesn't jump. A response to an older request is ignored, so a slow, outdated response never replaces a newer one (`useApi` gains a `stale` flag).
- **Phones and tablets (below `lg`): cards instead of the table.** The table needs about 900 px (14 columns), so the full table starts at `lg` (overrides 001's `md`). Each card shows rank, name, second line, the Overall tile, and the tile of the selected measurement when one is selected. All 12 are on the row's own page _(human decision)_. Table and cards are both rendered and CSS breakpoints show one (likewise chips or select, and the "Rank by" row), so the first paint already fits the screen _(human decision: no flash of the phone controls on load)_. Since there are no headers to click, a "Rank by" select (Overall + the 12 in `<optgroup>`s, as the measurement picker's phone select) and the order button take their place.
- **The kid: `kid_blocks`, a new pose from the team** _(human decision: not one of the existing kids)_: kneeling, stacking colourful blocks into a tower. Flipped horizontally, so the kid faces the page rather than out of it _(human decision: flip if it looks better)_. At the H1 row's right, knees and blocks resting on the card's top edge (`w-56 lg:w-64`). Transparent background, so no blend mode. Decorative, hidden below `md`.
- **Reuse:** page container, section card, message box, text input, segmented control, chips, select, outlined button, text link (`STYLE.md`); `FEATURE_INFO`, `FEATURE_GROUPS`, `featureDisplay` (`lib/features.ts`); `filledSegments` (`ScoreMeter`); `MeasurementPicker` (moved to `components/`, gains a `label`); `channelHref`/`videoHref`. With a second use each, the segmented control, chip and select become shared components (`SegmentedControl`, `Chip`, `Select`), used by the home card and the measurement picker too. The segmented control's pill fills its option with the same 4 px gap to the border on every side, so its curve follows the border's, here and on the home card _(human decision: the pill's and the border's radii didn't match)_. New: `ScoreCell`, `Pagination`, `RankingsPage`.
- **New styles go into `STYLE.md` in the same change:** the score cell, the rankings table (grouped, rotated sortable headers), the rankings card (phones), and the page control.

## Design

### Layout

DOM order: H1 + intro → rankings card (search + view switch, category chips, results line, table/cards, page control) → footer.

| Width | Layout |
|---|---|
| `lg`+ | H1 and intro on the top left. Section card: search input (left, `max-w-md`) and the Videos/Channels control (right) on one row; category chips under them; results line; the table; the page control centred under it. The kid on the card's top edge at the right. |
| `md`–`lg` | Same card. Below the chips: a "Rank by" select and the order button on one row. Cards instead of the table. |
| `sm`–`md` | The view control, then the search full width under it _(human decision: view control first on narrow screens)_; chips; "Rank by" and order on one row. Cards. No kid. |
| < `sm` | As above, with a category select instead of chips, side by side with "Rank by" (two columns), so the results start higher _(human decision)_; the order button under them. Page control reduced to ‹ · Page 3 of 655 · ›. |

**Table header** (`lg`+): two header rows. Row 1 has the group names centred over their columns _(human decision)_ (`colspan` 6 / 4 / 2, `text-xs` semibold, with a `navy/15` line under each group). Row 2 has the column names: "#", "Video", then "Overall" and the 12 measurement names, set vertically (reading bottom to top) so 48 px columns can hold them. Each name is a sort button (44 px target) with a ▼/▲ on the selected column and a faint ▼ under every other one, so all columns read as clickable _(human decision)_. The selected header has the sunny pill. The `th` carries `aria-sort`. A thin `navy/10` gap separates Overall from the 12.

**Desktop (1280 px)**

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ HyperStim?                                      Home  Rankings  Compare  How it works  About │
├────────────────────────────────────────────────────────────────────────────────────────────┤
│  Stimulation rankings                                                                      │
│  16,375 videos and 512 channels, ranked by how intense their production is.                │
│                                                                           {kid with lens}  │
│  ╭─ rankings card ──────────────────────────────────────────────────────────────────────╮  │
│  │  ( 🔍 Search videos or channels…           )                 ( Videos | Channels )   │  │
│  │  Category  (All) (Music) (Narrative) (Play & activity) (Educational) (Gaming)  ⇅ Most…│  │
│  │                                                                                      │  │
│  │  Showing 1–25 of 16,375 videos                                                       │  │
│  │                                    Pacing intensification  Sustained sensory  Reward │  │
│  │                              ┌───┐  ───────────────────── ────────────────  ────── │  │
│  │                              │ O │   R   S   P   L   M   L   V   V   A   S   A   S │  │
│  │  #  Video                    │ v │   a   c   a   u   o   o   i   i   u   i   u   u │  │
│  │                              │ ▼ │   ⋮   ⋮   ⋮   ⋮   ⋮   ⋮   ⋮   ⋮   ⋮   ⋮   ⋮   ⋮ │  │
│  │ ─────────────────────────────└───┘───────────────────────────────────────────────── │  │
│  │  1  Super Fast Toy Party     [99]  [96][88][91][97][84][90] [72][65][93][88] [94][97]│  │
│  │     Wheelie Friends TV                                                               │  │
│  │  2  Color Blast Song Mix     [99]  [94][90][95][71][88][93] [80][77][90][91] [85] – │  │
│  │     Rainbow Hop                                                                      │  │
│  │  …                                                                                   │  │
│  │                                                                                      │  │
│  │                 ‹ Previous   1  2  [3]  4  5  …  655   Next ›                        │  │
│  ╰──────────────────────────────────────────────────────────────────────────────────────╯  │
└────────────────────────────────────────────────────────────────────────────────────────────┘
  [nn] = score cell (number on a 50 % score-colour tile); – = no value
```

**Phone (360 px)**

```
┌──────────────────────────────┐
│ HyperStim?               ☰   │
├──────────────────────────────┤
│ Stimulation rankings         │
│ 16,375 videos and 512        │
│ channels, ranked by …        │
│ ╭─ card ───────────────────╮ │
│ │ ( Videos | Channels )    │ │
│ │ ( 🔍 Search videos…     )│ │
│ │ Category     Rank by     │ │
│ │ [ All     ▾] [ Rapid c ▾]│ │
│ │ ⇅ Most intense first     │ │
│ │                          │ │
│ │ 1–25 of 16,375 videos    │ │
│ │ ──────────────────────── │ │
│ │ 1  Super Fast Toy Party  │ │
│ │    Wheelie Friends TV    │ │
│ │    Overall [99]          │ │
│ │    Rapid cutting [96]    │ │
│ │ ──────────────────────── │ │
│ │ 2  Color Blast Song Mix  │ │
│ │    …                     │ │
│ │                          │ │
│ │  ‹   Page 1 of 655   ›   │ │
│ ╰──────────────────────────╯ │
└──────────────────────────────┘
```

### States

- Loading (first): skeleton rows/cards, `aria-busy`, sr-only "Loading rankings…".
- Loading (later): current rows dimmed, `aria-busy`; the results line updates when the new page arrives.
- No match (search or filter): message box "No {videos} match “{q}”." (with a category: "No {music} {videos} match …") and a "Clear search" outlined button.
- Page past the end (from an old link): goes to the last page.
- Error: message box "We couldn’t load the rankings." + "Try again", as on the other pages.

### Copy

| Where | Text |
|---|---|
| `<title>` | Stimulation rankings - HyperStim? |
| Meta description | Every video and channel in our dataset, ranked by how intense its production is. |
| H1 | Stimulation rankings |
| Intro | Videos and channels in our dataset, ranked by how intense their production is. Then, on its own line _(human decision)_: [What the measurements mean →](/how-it-works) (no counts: the results line has them, and needs no extra request; no sentence on the 5-video minimum _(human decision)_) |
| Search label (sr-only) / placeholder | Search videos / Title or channel… · Search channels / Channel name… (short enough for 320 px) |
| View control `aria-label` | Show ranking of · Videos · Channels |
| Category label | Category · All · Music · Narrative · Play & activity · Educational · Gaming |
| Rank by (below `lg`) | Rank by · Overall · {12 names} |
| Order button | ⇅ Most intense first / ⇅ Calmest first (`aria-label` “Order: …”) |
| Results line (`aria-live="polite"`) | Showing {26}–{50} of {5,699} {music} videos (the criterion is left out: the selected header shows it _(human decision)_); channels: “… of {120} channels with {music} videos …”; with search: “… matching “{q}” …” |
| Table caption (sr-only) | {Videos}, ranked by {Overall}, {most intense first} |
| Sort button | the column's name; the header's `aria-sort` tells the current order |
| Rank “–” (sr-only) | Not ranked |
| Rank “−{12}” (sr-only), calmest first | {12th} calmest |
| Empty cell (sr-only) | No cuts / No sound / Not measured |
| Page control (`nav` “Pages”) | ‹ Previous · Next › (`aria-label` “Previous page” / “Next page”) · page buttons (`aria-label` “Page {3}”), current `aria-current="page"` · phones: Page {3} of {655} |
| No match | No {videos} match “{q}”. · Clear search |
| Error | We couldn’t load the rankings. · Try again |

## API contract (frontend `api.ts` ↔ backend)

```
GET /api/videos?sort=score|<feature key>&order=desc|asc&category=<key>&q=<text>&offset=0&limit=25
  → { items: [{ id, title, channelId, channel, category,               // category: key, e.g. "play"
                rank: number | null,                 // by `sort` within `category`, 1 = first in `order`; null = no value
                score: number,                       // 0–100, 1 decimal
                features: [{ key, value, percentile }] }],   // the 12, as in GET /api/videos/{id}
      total: number }                                // rows matching category + q

GET /api/channels?sort=…&order=…&category=…&q=…&minVideos=5&offset=0&limit=25
  → { items: [{ id, name, videoCount, rank, score, features }], total }
```

- `sort` defaults to `score` and `order` to `desc`. `category` is a key from `lib/categories.ts` (`play` = the dataset's “play & activity”); empty = all; an unknown key → 422. `q` 1–100 characters. `offset` ≥ 0, `limit` 1–100 (default 20). Anything else → 422.
- **Breaking change:** `sort=score_desc|score_asc` becomes `sort=score&order=desc|asc`. The home card is updated in the same change.
- 25 rows × 12 features ≈ 10 KB per page.

## Backend

- `Video` gains `category` (the API key: the dataset's “play & activity” is `play`; an unknown category stops the load); `Channel` gains `categories` (the set of its videos' categories).
- A count of 0 on a per-minute feature ranks as percentile 0, as the API sends it (plan 004, `dataset.py`) _(human decision, 2026-10-16)_. The six keys match the frontend's `perMin`/`cutsPerMin` units, and a test checks this.
- At startup, for each of the 13 criteria (score + 12), the videos and the channels are pre-sorted once: most intense first, ties by ID, no-value rows last. A request filters by category (O(n), fine for 16k rows), numbers the ranks (equal values share one), applies the search, reverses for `asc` and counts its ranks from the calm end (no-value rows stay last), and slices. One helper (`ranking.py`) serves both videos and channels. A feature ranks by its percentile (for a channel, the mean percentile shown in its tile).
- Search: compare `casefold()` + accents removed (NFKD, combining marks dropped), precomputed per row.
- Tests (synthetic fixture): each criterion's order and tie-break; equal values share a rank, also in `asc`; `asc` is the reverse; no-value rows last and unranked in both orders; category filter for videos, and channels with ≥ 1 video in the category; search ignores case and accents, keeps ranks, and matches a video's channel name; `offset`/`limit`/`total`; `minVideos`; bad params → 422.

## Steps

Order: the frontend first (steps 2–5, on mock data) and a review of it; then the backend (step 1) and the review against it _(human decision)_.

1. **Backend.** Dataset fields, pre-sorted orders, the extended endpoints, the category keys, tests. Update `backend/README.md` if it lists the endpoints.
2. **API client + mocks.** New params and types; the home card moves to `sort`/`order`; mocks with made-up names: enough rows for many pages, all categories, counts of 0 and missing values, accented names.
3. **Shared pieces.** `ScoreCell`; `Pagination` (page window helper tested: 1 … 4 5 [6] 7 8 … 655); the URL state helper (parse with fallbacks, serialize without defaults; tested); `STYLE.md` entries; `kid_blocks` in `used.json`.
4. **Page.** `/rankings` (`useSearchParams` inside `Suspense`, as on `/channel`) with the table, cards, controls, and all states; the home card's link carries the view.
5. **Tests.** Header click sorts and the second click flips (`aria-sort`); rank by select + order button below `lg`; view switch keeps search/category/criterion and resets the page; search debounce, page reset, and the replace-vs-push history rule; category chips/select; paging moves focus to the results line; stale responses ignored; cell colours follow `filledSegments`; empty cells read their reason; each state renders.
6. **Review.** Screenshots at 360 and 1280 px (plus 320, 768, 1024, 1920, keyboard-only) next to the home card, compared with `STYLE.md`; run against the real backend (search speed, last page). Stop for review.

## Review decisions

- Layout sketch (`lg`+): the results line no longer names the criterion (see Copy, Results line).
- Layout sketch (`lg`+): the category row ends with the order button, right-aligned (see Decisions, Order button).
- Layout sketch (phone): the view control moved above the search (see Layout, `sm`–`md`).
- Layout sketch (phone): the category and "Rank by" selects side by side (see Layout, < `sm`).
- Layout sketch (phone): the order button replaces the “( Most intense | Calmest )” control under “Rank by” (see Decisions, Order button).

## Open questions

None.
