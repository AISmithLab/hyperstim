# 005 — Channel detail page

## Goal

Build `/channel?id=<channel-id>`: one channel's overall stimulation score and its 12 measurements, laid out like the video page (plan 004), plus a chart of how its videos' stimulation changed over the years, overall or for one measurement at a time, with each video's thumbnail hanging from its date; a thumbnail opens a panel with that video's player. The channel links on the home page and the video page already point here. The backend gets `GET /api/channels/{id}`.

## Decisions

- **Scope.** The page, the endpoint, the over-years chart with its video thumbnails and measurement picker, and the page's states. Not in scope: comparing channels, live-analyzed videos (they never join the dataset, plan 004).
- **Query param** (`/channel?id=…`, already used by `channelHref`), read on the client, as for `/video`.
- **Every channel in the dataset gets a page,** also the 30 with fewer than 5 videos (the home page ranks only ≥ 5, but a video page can link to any channel). No rank number, as on the video page.
- **Information hierarchy**, top to bottom:
  1. Which channel: name on the top left, then "{29} videos in our dataset · 2018–2026" and a "View on YouTube ↗" link. The kid on the top right.
  2. The answer: the score panel, same layout as the video page (gauge left, 12 measurements right). Above the fold at 1280 × 720, like the video page.
  3. Over the years: a chart section below the panel, showing which videos the scores come from.
- **Channel score** = mean of its videos' scores (plan 002, unchanged).
- **Channel measurements** = for each of the 12, the mean of its videos' percentiles (missing values left out), shown with the same measurement table as the video page. Same as the score's rule, so no new statistic. "None detected" only when no video of the channel has any event; "Not measured" when no video has a value. The popover's second line: "This channel: {1.6} per minute on average" (mean of raw values, same units rule as plan 004).
- **The kid:** `kid_lens_downward` _(human decision)_ (the kid with the magnifying glass, looking down: "taking a closer look at a channel"), not used on any page yet. Top right, peeking over the score panel's top edge from its right end, looking down toward the panel. Near-white background, so `mix-blend-multiply` on the edge, as on the video page. Same size as the video page's kid. Decorative.
- **Over-years chart** (**new**, hand-written inline SVG, no chart library), open-ended: no frame around the plot _(human decision: option A of the explored timelines)_.
  - One dot per video at its publish date (`published_at`, day precision), y = its percentile (0–100) for the selected measurement, or its score for "Overall".
  - X axis: ticks and labels at each year (Jan 1); the range spans the first to the last video, padded to whole years.
  - Y axis: 0–100, gridlines every 20 (`navy/10`, the meter's five bands), labels 0, 50, 100. No dataset-middle line _(human decision)_.
  - A **trend line** through the videos' own values in date order, with very little smoothing, so the trend stays real but reads a bit smoother _(human decision)_: each point is the mean of the video and its direct neighbours (3-video window, 2 at the ends), drawn as a monotone curve (no overshoot past the points). Drawn with ≥ 3 videos; fewer, dots only.
  - **One measurement at a time, Overall by default** _(human decision: keeps the video panel's layout fixed)_. Dots navy at partial opacity (overlaps stay readable), the line navy 2.5 px; no other colours.
  - **Event-count measurements** (the six per-minute ones): videos with 0 events sit on a separate "None detected" strip under the 0 line, not at their tied percentile (which reads as ~60, see plan 004). The trend line runs over the videos above the strip only _(human decision)_.
  - Missing values are left out, with a muted note "{2} videos not measured".
  - **Video thumbnails on the time axis** _(human decision: option A, liked better than a separate linked strip)_: under the axis, each video's YouTube thumbnail hangs on a thin line (`navy/20`, 1 px) from its date on the axis. One thumbnail per video. Thumbnails that would overlap drop to the next row (first row with room, in date order), but the rows overlap like a fanned deck, 10 px apart, later rows on top _(human decision: separate rows piled up too much vertical space, ~8 rows on a 60-video channel, and the dataset may grow; option A of the explored overlap versions)_; a thumbnail near the chart's ends shifts inward and its line slants. From `sm` up _(human decision: phones get the strip below)_. Size 64 × 36 px, `rounded` corners, a 2 px white ring so the lines pass behind them. Lazy-loaded (`loading="lazy"`), since each one is a request to YouTube's image server (the privacy policy covers it, plan 004). No text about the rows _(human decision)_.
  - **Clicking a thumbnail or a dot opens the video panel** under the chart _(human decision: as in the explored mock-up)_. The thumbnails are buttons (accessible name: "{title}, {Sep 6, 2024}"), so keyboard and screen-reader users can reach every video; the dots are pointer-only (out of the tab order).
  - **Video panel** (**new**): a `rounded-2xl bg-sky` box under the chart. Left: the video's preview (`YouTubePlayer`, 16:9, ~15rem wide), which plays when clicked, like on the video page; it doesn't start on its own, and no hint text _(human decision)_. Right: title, date, the selected measurement's name and this video's value for it (compact `ScoreMeter`, or "None detected" / "Not measured"), then "Video details →" (to `/video?id=…`) _(human decision)_ and a "Close" outlined button. Stacked (player above) below `sm`. One video at a time: opening another replaces it; the opened video's dot and thumbnail stay marked. Changing the measurement keeps the panel and updates its value. When it opens, the page scrolls it into view with a smooth scroll (none with `prefers-reduced-motion`) instead of jumping _(human decision: the jump felt abrupt)_, and focus moves to it; on Close focus goes back to the thumbnail.
  - **Phones (below `sm`): the whole chart, dots only, with a video strip under it** _(human decision: option B on phones only)_. No hanging thumbnails and no video panel. The strip (**new**, `VideoStrip`): a horizontal scroller of cards in date order, each year starting with a year marker on a thin timeline line. Card (~148 px wide, `scroll-snap-align: start`): thumbnail (16:9, `rounded-xl`, lazy-loaded), date, title (2 lines), the selected measurement's value (compact `ScoreMeter`, or "None detected" / "Not measured"). **The whole card is one link to the video's page** (`/video?id=…`) _(human decision: instead of playing it in place)_. So a click differs by width on purpose: the player panel from `sm` up, the video's page on phones _(human decision: a player under the chart is cramped on a phone)_. H5-level heading "The {29} videos we measured" with ‹ › buttons (scroll by ~80 % of the width; disabled at the ends). Opens at the oldest videos.
    - **Linked to the chart:** a `sunny/25` band on the plot covers the dates of the cards in view and follows the scroll. Tapping a dot scrolls the strip to its card and marks both (dot grows, card gets a `bg-sky` background) and shows the dot's popover. Dots stay out of the tab order; the card links are the keyboard and screen-reader path.
  - **Linked hover:** hovering a thumbnail or a dot marks the pair: the dot grows, the thumbnail gets a navy ring, its line turns navy 2 px, and a dashed guide runs up from the date. The thumbnail also stands out of its stack: it comes to the front, drops 8 px and grows a little, and the thumbnails below it in its stack slide down, opening space above and below it (~200 ms; none with `prefers-reduced-motion`) _(human decision)_. The opened video's thumbnail stays out of its stack the same way. The chart keeps room under the stacks for this, so nothing below it moves. Both show the same popover (`InfoTip` look): title (2 lines), date, the value with a compact `ScoreMeter` (number, then the 5-segment meter, as everywhere else) _(human decision)_. The dot's hit area is ~24 px.
  - **Screen readers:** the SVG is `aria-hidden`; an sr-only table carries the values (date, video title, the selected measurement), since there's no visible table _(human decision)_. No keyboard navigation of the dots _(human decision)_; the thumbnail buttons are the keyboard path to the videos.
  - With `prefers-reduced-motion` nothing animates; otherwise the dots and line fade to the new measurement (~200 ms). No other animation.
- **Measurement picker** (**new**) _(human decision: chips, one at a time)_: 13 choices (Overall + 12) are too many for one segmented control and too long a dropdown on desktop.
  - **From `sm`:** chips (the segmented control's pill look: `aria-pressed` buttons in a `role="group"`, one pressed at a time), arranged like the measurement table: "Overall" first on its own, then the three groups, each a small label followed by its chips, wrapping. The pressed chip has the sunny pill.
  - **Below `sm`:** a native `<select>` with "Overall" and three `<optgroup>`s; phones show their own full-screen picker, which handles 13 options well, while the chips would take ~7 rows.
  - No legend, chart title or info "i": the chips name what's shown, and the measurement descriptions are in the score panel's popovers above.
  - The choice isn't kept in the URL for now _(human decision)_.
- **Reuse:** `ScoreGauge`, `Measurements` (gains a "This video" / "This channel" label prop), `InfoTip`, the YouTube thumbnail URL helper from `YouTubePlayer`. New: `TimeChart`, `MeasurementPicker`, `VideoPanel`. Page container, section card, message box from `STYLE.md`.
- **New styles go into `STYLE.md` in the same change:** channel header, the over-years chart (with the hanging thumbnails), the video panel, the measurement picker (chips + phone select).

## Design

### Layout

DOM order: header → score panel → over-years section → footer.

| Width | Layout |
|---|---|
| `lg`+ | Header: name and meta line (2/3) · kid space (1/3). Score panel as on the video page; the kid on its top edge at the right. Over-years section (section card): H2, picker chips under it, chart (plot ~360 px high, full width) with the thumbnail rows under its axis, note, the video panel once opened. |
| `sm`–`lg` | Header as above; panel stacked as on the video page; the kid on its top edge at the right. Chips wrap; plot ~320 px high; deeper thumbnail stacks. |
| < `sm` | Same order; kid smaller; picker is a `<select>`; plot ~260 px high, year labels thinned to every 2nd year when they don't fit; no thumbnails on the axis; the video strip under the chart. |

**Desktop (1280 px)**

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ HyperStim?                                      Home  Rankings  Compare  How it works  About │
├────────────────────────────────────────────────────────────────────────────────────────────┤
│  Wheelie Friends TV                                                                        │
│  29 videos in our dataset · 2018–2026 · View on YouTube ↗                                  │
│                                                                      {kid with lens ↙}     │
│  ╭─ score panel ───────────────────────────────────────────────────────────────────────╮   │
│  │   ,-'''''-.        Pacing intensification          Sustained sensory intensity      │   │
│  │  /    \    \       Rapid cutting (i)    78 ▮▮▮▮▯   Visual intensity (i)   61 ▮▮▮▮▯  │   │
│  │ calm   ●  intense  …                               …                                │   │
│  │    74 / 100 (i)                                    Reward patterning …              │   │
│  ╰─────────────────────────────────────────────────────────────────────────────────────╯   │
│                                                                                            │
│  ╭─ over the years (white card) ───────────────────────────────────────────────────────╮   │
│  │  How it changed over years?                                                         │   │
│  │  (Overall)                                                                          │   │
│  │  Pacing intensification  (Rapid cutting) (Scene discontinuity) (Palette …) …        │   │
│  │  Sustained sensory intensity  ( Visual intensity ) ( Visual brightness ) …          │   │
│  │  Reward patterning  ( Audio build-resolve ) ( Surprise reveals )                    │   │
│  │                                                                                     │   │
│  │ 100 ┤                                                                               │   │
│  │     │            ●          ●  ●        ●  ●──────●───────●                         │   │
│  │  50 ┤          ●  ●───────●─────●───●───●      ●       ●                            │   │
│  │     │     ●───●      ●                ●                                             │   │
│  │   0 ┼──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬                      │   │
│  │      2018 │ 2019 │ │  2020 │ 2021│  │2022 │ │ 2023 │ 2024  │ 2025                   │   │
│  │         [▣]   [▣][▣]     [▣] [▣][▣]  [▣][▣]  [▣]  [▣]   [▣]                       │   │
│  │          [▣]   [▣][▣]     [▣] [▣][▣]   [▣]     [▣]  └[▣]                            │   │
│  │           [▣]    [▣]       [▣]   [▣]                                                │   │
│  │  ╭─ video panel (sky) ───────────────────────────────────────────────────────────╮  │   │
│  │  │ ┌──────────────────┐  Tiny Trucks Race to the Rainbow Bridge                   │  │   │
│  │  │ │  ▶ YouTube player │  Sep 6, 2024                                             │  │   │
│  │  │ │                  │  Overall   74 ▮▮▮▮▯                                       │  │   │
│  │  │ └──────────────────┘  Video details →   ( Close )                              │  │   │
│  │  ╰───────────────────────────────────────────────────────────────────────────────╯  │   │
│  ╰─────────────────────────────────────────────────────────────────────────────────────╯   │
├────────────────────────────────────────────────────────────────────────────────────────────┤
```

`[▣]` = a video's thumbnail, hanging on a line from its date; rows overlap like a fanned deck. The panel appears after a thumbnail or dot is clicked. For an event-count measurement, a "None detected" strip sits between the 0 line and the year labels, with the zero-event videos as dots on it.

**Phone (360 px)**

```
┌──────────────────────────────┐
│ Wheelie Friends TV           │
│ 29 videos · 2018–2026        │
│ View on YouTube ↗  {kid ↙}   │
│ ╭─ score panel ────────────╮ │
│ │   gauge, 74 / 100        │ │
│ │   12 measurement rows    │ │
│ ╰──────────────────────────╯ │
│ ╭─ over the years ─────────╮ │
│ │ How it changed over      │ │
│ │ years?                   │ │
│ │ [ Overall            ▾ ] │ │
│ │ 100┤      ●   ●──●       │ │
│ │  50┤ ●──●──●             │ │
│ │   0┼──┬───┬───┬───┬──    │ │
│ │     18  20  22  24  26   │ │
│ │ The 29 videos we… (‹)(›) │ │
│ │ ─2018──•──────•─────2019 │ │
│ │ ┌────────┐ ┌────────┐ ┌─ │ │
│ │ │ thumb  │ │ thumb  │ │  │ │
│ │ └────────┘ └────────┘ └─ │ │
│ │ Feb 2, 2018 Apr 30, 2018 │ │
│ │ Tiny Trucks… Wheelie W…  │ │
│ │ 21 ▮▯▯▯▯    34 ▮▮▯▯▯     │ │
│ ╰──────────────────────────╯ │
└──────────────────────────────┘
```

### States

- Loading: skeletons for the name, the panel (as on the video page) and a grey chart box; `aria-busy`, sr-only "Loading channel…".
- No `id` or not a channel ID (`UC` + 22 characters): message box, "That doesn’t look like a channel link.", "Check a video →" to `/`.
- Not in the dataset (404): `kid_2` above the message box: "This channel isn’t in our dataset." + "Check a video →". (Also reached from a live-analyzed video whose channel isn't in the dataset.)
- Error: message box + "Try again", as on the other pages.

### Copy

| Where | Text |
|---|---|
| `<title>` | Channel details - HyperStim? · after load: {channel name} - HyperStim? |
| Meta description | How stimulating are this channel’s videos, and how has that changed over the years? |
| Meta line | {29} videos in our dataset · {2018}–{2026} (one year: · {2024}; 1 video: “1 video in our dataset”) |
| Link | View on YouTube ↗ (sr-only “(opens in a new tab)”) → `https://www.youtube.com/channel/{id}` |
| Gauge H2 (sr-only) | Stimulation score |
| Gauge InfoTip | Score 0–100: the average of this channel’s video scores. Each is where a video’s production sits among the videos in our dataset, not whether it is good or bad. |
| Measurement popover, 2nd line | This channel: {1.6} per minute on average |
| Section H2 | How it changed over years? _(human decision)_ |
| Picker label (sr-only for the chips; visible for the select) | Show |
| Strip label | None detected |
| Missing note | {2} videos not measured (1: “1 video not measured”) |
| Popover (dot or thumbnail) | “{title}” · {Sep 6, 2024} · {Overall}: {74} + meter (or “None detected”) |
| Thumbnail button (accessible name) | {title}, {Sep 6, 2024} |
| Strip heading (phones) | The {29} videos we measured (1: “The 1 video we measured”) |
| Strip buttons (sr-only) | Older videos · Newer videos |
| Card link (accessible name) | {title}, {Sep 6, 2024} |
| Video panel | {title} · {Sep 6, 2024} · {Overall} + meter (or None detected / Not measured) · Video details → · Close |
| sr-only table caption | {Channel name}’s videos over the years |
| sr-only table columns | Published · Video · {Overall / measurement name} |
| Not in dataset | This channel isn’t in our dataset. |
| Error | We couldn’t load this channel. |

## API contract (frontend `api.ts` ↔ backend)

```
GET /api/channels/{id}
  → {
      id: string, name: string, videoCount: number,
      score: number,                                   // 0–100, 1 decimal
      features: [{ key, value, percentile }],          // the 12; value = mean raw, percentile = mean of the videos' percentiles; null if no video has one
      videos: [{                                       // oldest first
        id: string, title: string, publishedAt: string, // YYYY-MM-DD
        score: number,
        features: [{ key, value, percentile }]          // as in GET /api/videos/{id}
      }]
    }
  404 → { detail: "Channel not found" }
  422 → id not UC + 22 characters of [A-Za-z0-9_-]
```

At most 60 videos per channel (~40 KB), so no paging. Thumbnails are built from the video ID in the frontend, as on the video page. The "None detected" rules stay in the frontend (zero `value`).

## Backend

- `Video` gains `published_at`; `Channel` gains its videos (date order) and the 12 channel features. `channels_by_id` dict.
- `GET /api/channels/{id}` as above; ID pattern via `Path(pattern=…)`. All 542 channel IDs in the dataset match `^UC[A-Za-z0-9_-]{22}$` (checked).
- Tests (synthetic fixture): found channel has all fields, videos in date order with their features; channel feature = mean of the videos' percentiles with missing left out, `null` when all missing; score = mean of video scores; unknown → 404; malformed → 422.

## Steps

1. **Backend.** Dataset fields, endpoint, tests.
2. **API client + mocks.** `getChannel(id)`; mock channels with made-up names and dates: one spanning many years with ~60 videos (busy years, for the thumbnail rows), one single-year, one with a single video, one with zero-event and missing values; one mock ID → 404.
3. **Shared pieces.** `Measurements` label prop; `MeasurementPicker`; `TimeChart` (scales, ticks, the smoothed trend line, the strip, thumbnail rows and lines, linked hover, the popover) with its pure helpers tested; `VideoPanel` (reusing `YouTubePlayer`); `VideoStrip` (cards, year markers, ‹ ›, the scroll band); `STYLE.md` entries; `kid_lens_downward` in `used.json`.
4. **Page.** `/channel` with all states.
5. **Tests.** Trend smoothing (3-video window, ends, ≥ 3 videos) and the curve never passing the points' range; zero-event videos go to the strip and out of the trend; missing values counted in the note; thumbnail row placement (no overlaps within a row, date order, shifted at the ends) and the focused thumbnail standing out of its stack; a thumbnail or dot opens the panel with the player and the selected measurement's value, another replaces it, Close returns focus, “Video details →” links to `/video?id=…`; on phones: no axis thumbnails or panel, cards link to `/video?id=…`, the band follows the scroll, a dot scrolls to its card, ‹ › disabled at the ends; year range and meta-line copy (1 video, 1 year); picker: default Overall, one at a time, chips and select both switch the chart and the panel's value; the sr-only table follows the picker; each state renders; title set after load.
6. **Review.** Screenshots at 360 and 1280 px (plus 320, 768, 1920, keyboard-only) next to the video page, compared with `STYLE.md`; panel above the fold at 1280 × 720; run against the real backend with a 60-video and a small channel. Stop for review.

## Review decisions

1. **Thumbnails on the time axis** (option A): the desktop sketch under **Layout** now shows them hanging from the axis.
2. **One measurement at a time; a click opens the video panel:** the desktop sketch under **Layout** shows the single navy line, plain chips and the panel; the phone sketch shows the `<select>`.
3. **Option B on phones, cards link to the video page:** the phone sketch under **Layout** shows the strip under the chart.

4. **Thumbnail rows overlap like a fanned deck** (option A of the explored overlap versions): the desktop sketch under **Layout** shows the overlapping rows (see **Decisions**: video thumbnails on the time axis, linked hover).

## Open questions

None.
