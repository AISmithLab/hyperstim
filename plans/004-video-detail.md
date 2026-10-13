# 004 — Video detail page

## Goal

Build `/video?id=<youtube-id>`: one video's stimulation score and its 12 measurements, visible without scrolling, plus the video itself on request. The check-a-video form and the rankings rows on the home page already link here. The backend gets `GET /api/videos/{id}`.

## Decisions

- **Scope.** The page, the endpoint, a shared YouTube player, and the states for videos not in the dataset. Not in scope: live analysis (a video not in the dataset gets a "not checked yet" state until that plan), the compare link (comes with `/compare`), and the cookie banner.
- **Query param, not a path** (`/video?id=…`), as 001 says: a static export can't pre-render pages for videos analyzed later. The page reads the ID on the client.
- **Information hierarchy.** People arrive with one question: how stimulating is this video? They already know the video (they pasted its link or clicked its title). So, top to bottom:
  1. Which video this is: title, channel, and the video preview beside them. _(was: a small thumbnail, title, channel; before that title, channel, the kid)_
  2. The answer: the overall score, and the 12 measurements behind it, in one score panel. **The panel fits above the fold on desktop (1280 × 720) up to its bottom padding** (_was: the whole panel; review decision 30 trades ~20 px for a larger kid_)**; on phones the gauge does**, the measurements follow right below.
  3. The video plays on request, in the preview in the header. _(was: extras below the panel: the video, on request)_
  _(was: title block with category, date and length → score card → player → breakdown card with descriptions, the breakdown below the fold)_
- **Video header: title (smaller, 2 lines) and channel on the left 2/3** (no "Watch on YouTube" link: the embedded player links to YouTube; _was: also "Watch on YouTube ↗"_)**; the video preview (16:9) on the right 1/3, at every width.** _(was: a small static thumbnail on the left, for recognition only)_ No category, published date or length. _(was: title block with the kid on its right; before that a metadata line "{Category} · Published {date} · {length}")_
- **Score**, as on the home page: the 0–100 percentile. Shown on a **gauge** (see Design). No sentence under it; the score's info popover says it is a position in our dataset, not a grade. _(was: a sentence under the gauge, “More intense than about {87}% of the {16,375} kids’ videos in our dataset.”)_ No rank number (#412 of 16,375): the page is about this one video, and a rank reads like a leaderboard.
- **Measurements = the 12 features, in the research taxonomy's three groups**, as a compact table: name + info "i", percentile number, small meter. What each one measures, and this video's raw value where it has a readable unit, are in the info popover. No group subtotals: a group score would be a new summary with no research behind it.
  - Groups: **Pacing intensification** (types 1.1–1.6), **Sustained sensory intensity** (2.1–2.4), **Reward patterning** (3.1–3.2). _(was: plain names Pacing / Constant intensity / Build-ups and surprises)_
  - Measurement names are the research taxonomy's type names (see **Copy**), in sentence case. _(was: plain-language names such as “Cuts”, “Scene jumps”)_
  - **"None detected" instead of a percentile when an event count is 0.** Many videos have no flashes, build-ups or surprise sounds, and with ties at 0 a zero would show as a middling percentile (e.g. 60). Applies to the per-minute features (1.1, 1.3, 1.4, 1.6, 3.1, 3.2).
  - **Missing values** (1.2 has none when no cuts were found; 1.6/2.3 missing for 7 videos): "No cuts" for 1.2, "Not measured" otherwise. No meter for either.
  - Raw values (in the popover) only for features with a plain unit (per minute, share of time). Saturation, brightness, loudness (LUFS) and scene dissimilarity have none: their units mean nothing to parents.
  - _(was: a separate breakdown card, each row with a visible description and value)_
- **Copy limits** (from the research team's guidance): describe what is measured, not effects on children. No claims about addiction, attention, or development; no "good/bad" or "safe/unsafe" wording.
- **No clip-coverage note.** _(was: a muted line at the bottom of the score panel: “We measured up to 5 minutes of each video, starting 30 seconds in.”)_
- **The video: the preview in the header; a click turns it into the player in the same spot.** No player below the score panel. _(was: a thumbnail card below the score panel, max ~800 px wide)_ The preview is a 16:9 box showing the video's YouTube thumbnail with a centred "▶ Play video" button. Clicking swaps in the `youtube-nocookie.com` player and starts it; nothing else on the page moves. The click is the consent 001 asks for, so this works before the cookie banner exists. The thumbnail comes from YouTube's image server (no cookies, but YouTube sees the visitor's IP; the privacy policy will say so) and loads with the page, since it's at the top. `YouTubePlayer` component, reused by `/compare` later. People who prefer YouTube itself use the player's own YouTube link. _(was: a "Watch on YouTube ↗" link in the title block)_ _(was: a collapsed "Watch the video here" button with no thumbnail; before that, a thumbnail facade always open beside the score card)_
- **Score meter becomes a shared component** (`ScoreMeter`), used by the rankings card and the measurement rows (compact size).
- **New styles go into `STYLE.md` in the same change:** `ScoreGauge`, the measurement table, the video disclosure (Data display / Controls), and `ScoreMeter` as the meter's owner.
- **The kid is the site's recurring character** and appears on every page (now a rule in `STYLE.md`). On this page _(was: dropped from the result for a while, review decision 21)_:
  - `kid_3` (peeking over an edge with both hands on it, looking down to the right, smiling; transparent PNG), one image for every video. _(was: `kid_lens_downward`; before that `kid_lens_smile` / `kid_lens_surprised` by the 90th-percentile rule (`kidMood`, kept in the code); the switch can return with a surprised version of this pose)_
  - Peeking over the score panel's top edge, hands on the border line (the art's table edge, 92.1 % down the image), looking right toward the measurements (no flip). Head the same size as decision 30's (~75 % of the home page kid): `w-40` phones, `w-44` from `sm`, `w-52` from `lg`; above the right part of the gauge column from `lg`, at the panel's left below that. At every width. The space above the panel makes room for it (`mt-28 sm:mt-20 lg:mt-16 xl:mt-10`). _(was: `kid_lens_*` lying on the edge, ~144 px; before that in the gauge column's corner, and to the right of the title block)_ Decorative (`alt=""`, `aria-hidden`): the text already says how intense the video is.
  - Not shown while loading. In the "not checked yet" state: `kid_2` (peeking over a table with a teddy bear).
  - The kid images are RGB with a near-white background (250–255, not transparent), so they sit on white only, never on a pastel panel. On the panel edge the kid uses `mix-blend-multiply`, so the border line shows through the background. A transparent version from the team would be cleaner.
- **No plants on the score panel** (review decision 31). _(was: `plant_3` and `plant_1` on its bottom-left edge)_
  - _(was: `kid_2` in the "not checked yet" state only, no character on the result)_

## Design

### Layout

DOM order at every width: header (metadata, then preview) → score panel (gauge, then measurements) → (footer). _(was: title block → score panel → video card)_

| Width | Layout |
|---|---|
| `lg`+ (≥1024) | Header: title, channel (2/3, top-aligned) · preview (1/3). Kid on the panel's top edge above the gauge column. Score panel: gauge column (13rem with `gap-x-8` below `xl`, 17rem with `gap-x-12` from `xl`; the gauge fills it, vertically centred) · measurements in two columns: Pacing intensification on the left; Sustained sensory intensity above Reward patterning on the right. No divider between them. |
| `md` (768–1023) | Header as above; kid on the panel's top edge at its left. Score panel: gauge (~192 px) centred; the two measurement columns below. |
| < `md` (320–767) | Header as above (the preview's play button shows its icon only); kid on the panel's top edge at its left. Score panel: gauge, then the three groups in one column. |

_(was: thumbnail left of the text, the kid in the score panel, a video card below the panel; before that title block · kid in the header and a vertical divider between gauge and measurements)_

Sketches: not to scale (names shortened only in the phone sketch); made-up title and channel; `▮▮▮▯▯` = compact meter, `(i)` = info button.

**Desktop (1280 px; the whole score panel is above the fold)**

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ HyperStim?                                         Home  Rankings  Compare  How it works  About    │
├────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                    │
│  Tiny Trucks Race to the Rainbow Bridge!                         ┌───────────────────────────────┐ │
│  Wheelie Friends TV                                              │ [thumbnail] ( ▶ Play video )  │ │
│                                                                  └───────────────────────────────┘ │
│                     {kid, lens →}                                                                  │
│  ╭─ score panel (white card) ──────────────────────────────────────────────────────────────────╮   │
│  │                          Pacing intensification              Sustained sensory intensity    │   │
│  │                                                                                             │   │
│  │    ,-'''''''-.          Rapid cutting (i)        93 ▮▮▮▮▮   Visual intensity (i)    81 ▮▮▮▮▮│   │
│  │  ,'         `.          Scene discontinuity (i)  71 ▮▮▮▮▯   Visual brightness (i)   45 ▮▮▮▯▯│   │
│  │ /      \       \        Palette instability (i)  88 ▮▮▮▮▮   Audio intensity (i)     66 ▮▮▮▮▯│   │
│  │ calm     ●  intense     Luminance flash (i)      64 ▮▮▮▮▯   Silence elimination (i) 30 ▮▮▯▯▯│   │
│  │     87 / 100 (i)         Motion density (i)       58 ▮▮▮▯▯                                  │   │
│  │                          Loudness jumps (i)       40 ▮▮▯▯▯   Reward patterning              │   │
│  │                                                              Audio build-resolve (i) None d.│   │
│  │                                                              Surprise reveals (i)    None d.│   │
│  ╰─────────────────────────────────────────────────────────────────────────────────────────────╯   │
│                                                                                                    │
├────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ © 2026 HyperStim?                                                    Privacy policy  About us  FAQ │
└────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

After "Play video": the preview becomes the YouTube player, same size and place.

**Phone (360 × 640; the gauge is above the fold)**

```
┌──────────────────────────────┐
│ HyperStim?           ☰ Menu  │
├──────────────────────────────┤
│ Tiny Trucks Race   ┌───────┐ │
│ to the Rainbow B…  │  (▶)  │ │
│ Wheelie Friends TV └───────┘ │
│  {kid →}                     │
│ ╭─ score panel ────────────╮ │
│ │    ,-'''''''-.           │ │
│ │  ,'    \      `.         │ │
│ │ calm    ●  intense       │ │
│ │       87 / 100 (i)       │ │
│ │ ──────────────────────── │ │  ← fold
│ │ Pacing intensification   │ │
│ │ Rapid cutting (i) 93 ▮▮▮▮│ │
│ │ Scene discont… (i)71 ▮▮▮▯│ │
│ │ …  (12 rows, 3 groups)   │ │
│ ╰──────────────────────────╯ │
└──────────────────────────────┘
```

**Not checked yet** (any width)

```
                  {kid_2 peeking}
╭─ message box (sky) ──────────────────────────────╮
│        We haven’t checked this video yet         │
│  It isn’t one of the 16,375 videos in our        │
│  dataset. Checking new videos is coming soon.    │
│   Check another video →    Watch on YouTube ↗    │
╰──────────────────────────────────────────────────╯
```

### Elements, top to bottom

All surfaces and controls are from `STYLE.md`; new ones are marked **new**.

1. **Video header** (no card): a `grid-cols-[2fr_1fr]` grid, items top-aligned (_was: vertically centred_): the text on the left, the video preview (`YouTubePlayer`) on the right. _(was: a static thumbnail `w-28 sm:w-48 lg:w-56` on the left)_ H1 = the video title (`font-hand`, `text-[1.375rem] sm:text-2xl lg:text-[1.75rem]`, no marker, clamped to 2 lines with the full title in the DOM). Under it: channel name (bold navy), a link to the channel page (`/channel?id={channelId}`, hover underline; _was: plain text_). _(was: then the "Watch on YouTube" text link)_ _(was: title block with the kid on its right, title `text-[1.5rem] sm:text-[2rem] lg:text-[2.25rem]`)_
2. **Score panel** (section card, white).
   - Panel padding `py-6` (_was: `py-8` on desktop_); no vertical divider, a gap instead (`gap-x-8` at `lg`, `gap-x-12` from `xl`; _was: `gap-x-12` from `lg`, which wrapped measurement names at 1024 px_); a `navy/10` line between gauge and measurements only when stacked.
   - **Gauge column** (**new**: `ScoreGauge`). An sr-only H2 "Stimulation score" names the panel (_was: a visible H2 with the score `InfoTip`_); the score `InfoTip` sits after the number. A half-circle dial (inline SVG, ~192 px wide below `lg`, the full column from `lg`; _was: ~240 px and 21rem_) split into five bands in the score scale colours (`sky-blue` → `leaf` → `scale-low` → `scale-mid` → `scale-high`, 20 points each), "calm" and "intense" labels under its two ends (small, ink), and a navy needle with a round hub. Under the dial: the score as a large navy `font-hand` number with "/ 100" small after it. _(was: then the comparison sentence)_
   - **Animation:** on first render the needle sweeps from 0 to the score (~1 s, ease-out) while the number counts up with it. With `prefers-reduced-motion`, both show the final value at once. The SVG is `aria-hidden`; the counting number is `aria-hidden` too, with the final score in sr-only text, so screen readers read one value.
   - **Measurements** (**new**: measurement table). Each group: H3 (`font-hand text-lg text-navy`), then one row per feature, `min-h-11`, lines `navy/10`. Row: name (semibold navy) + `InfoTip`; percentile (bold navy, `tabular-nums`, right-aligned fixed-width column); `ScoreMeter` compact (5 segments, ~4.5 rem wide). "None detected" / "No cuts" / "Not measured" in muted text in place of number + meter. sr-only text on the number: "Higher than {93}% of videos in our dataset". The popover: the description, then this video's value where there is one.
3. **Video preview** (**new**: `YouTubePlayer`), in the header. A 16:9 `rounded-2xl` box, overflow hidden, as wide as its column. Before the click: the thumbnail as `<img alt="">`, a light navy scrim, centred primary button with a play icon; the "Play video" label shows from a 20rem-wide box, a round icon-only button below that. _(was: a card below the score panel, max ~800 px wide, lazy-loaded thumbnail)_ After: the iframe (`title` = video title, `allow="autoplay; encrypted-media; picture-in-picture; fullscreen"`) in the same box, focus moved to it. No "hide" control: the player is just a player once loaded.
4. **States**
   - Loading: skeletons for the thumbnail, the title and the score panel (dial outline, 12 grey rows), `aria-busy`, sr-only loading text. The preview is a grey 16:9 box.
   - No `id` or not a valid ID: message box with the text and a "Check another video" link to `/`.
   - Not in the dataset (404): `kid_2` (decorative, ~280 px wide, every width) on the white page just above the message box (its background isn't transparent), then the box with the text, "Check another video" and "Watch on YouTube" links.
   - Error (network/5xx): message box + "Try again" (outlined button), as on the home page.

### Copy

`{…}` = filled in at runtime. Arrows are decorative (`aria-hidden`). Typographic apostrophes.

**Page metadata**

| Where | Text |
|---|---|
| `<title>` (static, before load) | Video details - HyperStim? |
| `<title>` (after load, set on the client) | {video title} - HyperStim? |
| Meta description | How stimulating is this video? Its score and what we measured. |

**Title block**

| Where | Text |
|---|---|
| Link | _(dropped; was: Watch on YouTube ↗, sr-only "(opens in a new tab)")_ |

**Score panel: gauge**

| Where | Text |
|---|---|
| H2 (sr-only) | Stimulation score |
| Dial end labels | calm · intense |
| Number | {87} / 100 (sr-only: "Stimulation score {87} out of 100") |
| InfoTip | Score 0–100: where this video’s production sits among the videos in our dataset, not whether it is good or bad. |

_(was: a “Comparison” row: “More intense than about {87}% of the {16,375} kids’ videos in our dataset.”)_ `{N}` in the not-in-dataset text is the exact count from `/api/meta`; while it loads it is left out.

**Score panel: measurements**

| Group (H3) |
|---|
| Pacing intensification |
| Sustained sensory intensity |
| Reward patterning |

| # | Name | Popover: description | Popover: this video |
|---|---|---|---|
| 1.1 | Rapid cutting | How often the picture switches to a new shot. | {22.6} cuts per minute |
| 1.2 | Scene discontinuity | How different each new shot looks from the one before. | — |
| 1.3 | Palette instability | How often the colors on screen are replaced. | {21.0} per minute |
| 1.4 | Luminance flash | How often the picture suddenly gets brighter. | {1.6} per minute |
| 1.5 | Motion density | How much of the time things on screen move fast. | {21}% of the time |
| 1.6 | Loudness jumps | How often the sound jumps well above its usual level. | {0.3} per minute |
| 2.1 | Visual intensity | How saturated the colors are. | — |
| 2.2 | Visual brightness | How bright the picture is. | — |
| 2.3 | Audio intensity | How loud the sound is overall. | — |
| 2.4 | Silence elimination | How much of the time sound is playing. | Sound {77}% of the time |
| 3.1 | Audio build-resolve | Sound that rises steadily, then drops back. | {0.2} per minute |
| 3.2 | Surprise reveals | Loud sounds that land right on a cut. | {0.2} per minute |

Per-minute values: 1 decimal; shares: whole percent. Info button sr label: "About {name}".

| Where | Text |
|---|---|
| Percentile (sr-only) | Higher than {93}% of videos in our dataset |
| Zero events | None detected |
| 1.2 missing | No cuts |
| Other missing | Not measured |

**Video**

| Where | Text |
|---|---|
| Button | Play video (sr-only: "Play video: {video title}") |
| iframe `title` | {video title} |

**States**

| Where | Text |
|---|---|
| Loading (sr-only) | Loading video… |
| Invalid / missing ID | That doesn’t look like a YouTube video ID. |
| Not in dataset, H1 | We haven’t checked this video yet |
| Not in dataset, text | It isn’t one of the {16,375} videos in our dataset. Checking new videos is coming soon. |
| Links | Check another video → · Watch on YouTube ↗ |
| Error | We couldn’t load this video. |
| Error button | Try again |

## API contract (frontend `api.ts` ↔ backend)

```
GET /api/videos/{id}
  → {
      id: string, title: string, channelId: string, channel: string,
      score: number,             // 0–100, 1 decimal
      features: [{ key: string, value: number | null, percentile: number | null }]  // the 12, in taxonomy order
    }
  404 → { detail: "Video not found" }
  422 → id not 11 characters of [A-Za-z0-9_-]

GET /api/videos     items gain channelId: string   (review decision 26; was: no channel ID)
GET /api/channels   items gain id: string          (the channel ID; was: name only)
```

`percentile` is the feature's percentile in the dataset (same formula as the score, 1 decimal), `null` when `value` is. The "None detected" rule lives in the frontend. Feature names and descriptions are frontend copy keyed by `key`. _(was: also `category`, `publishedAt`, `durationS`; dropped since the page no longer shows them)_

## Backend

- `Video` keeps the 12 values and their percentiles (computed at startup from the pools `scoring.py` already builds). A dict by ID for lookup.
- `GET /api/videos/{id}` as above; ID pattern checked by FastAPI (`Path(pattern=…)`).
- CORS stays GET-only.
- Tests (synthetic fixture): found video has all fields and 12 features in order; missing value → `null` value and percentile; unknown ID → 404; malformed ID → 422; feature percentiles match `scoring.percentile_rank`.

## Steps

1. **Backend.** Endpoint, dataset fields, tests.
2. **API client + mocks.** `getVideo(id)` in `api.ts` (404 surfaces as `ApiError` with status 404); mock details for the mock videos, with one zero-event, one missing-value case, and one mock ID that returns 404.
3. **Shared pieces.** Extract `ScoreMeter` from `RankingsCard` (no visual change) with a compact size; `ScoreGauge`; `YouTubePlayer`; `STYLE.md` entries; add `kid_2`, `kid_lens_smile`, `kid_lens_surprised` to `used.json`; the mood rule (`kidMood(features)`) as a small tested function.
4. **Page.** `/video` with all states; `useSearchParams` inside a `Suspense` boundary (needed for static export).
5. **Tests.** Value formatting (per minute, percent), "None detected"/missing rules, kid mood rule, gauge needle angle for 0/50/100 and reduced motion, video card swaps to the iframe on click (and loads nothing from YouTube before), each state renders, title set after load.
6. **Review.** Screenshots at 360 and 1280 px (plus 320, 768, 1920 and keyboard-only check) compared with `STYLE.md`; check the score panel is above the fold at 1280 × 720 and the gauge at 360 × 640; run against the real backend. Stop for review.

## Review decisions

1. **Show the layout as ASCII sketches** in the plan (desktop, phone, not-checked state), under **Layout**.
2. **The kid is a recurring character that shows up on every page.** Added to `STYLE.md` (The look).
3. **This page uses `kid_lens_smile` / `kid_lens_surprised`:** smile when none of the 12 dimensions is above 50, surprised otherwise (see **Decisions**). _(threshold later changed to 90, decision 11)_
4. **The most important info shows without scrolling; the main thing is the scores.** Title block keeps the video title, the channel and the kid; category and date are dropped. Below it, one large score panel.
5. **Score panel: overall score on the left, as a gauge with an animation; measurements on the right**, in a relatively compact table. No visible description per measurement: it's in a tooltip.
6. **Measurement columns:** one column for Pacing intensification; the other holds Sustained sensory intensity on top and Reward patterning below.
7. **The video should be embedded somewhere, maybe only shown when required**, placed by information hierarchy (Claude's proposal: collapsed below the score panel; settled by decision 13).
8. **Drop the clip-coverage note** (“We measured up to 5 minutes…”) **and the cookie note** (“Plays from YouTube, which may set cookies.”).
9. **Keep a video thumbnail.** Maybe a click expands the page in between and the embedded video shows up; better ideas wanted (settled by decision 13).
10. **Measurement names are the research type names:** rapid cutting, scene discontinuity, palette instability, luminance flash, motion density, loudness jumps, visual intensity, visual brightness, audio intensity, silence elimination, audio build-resolve, surprise reveals. The rest of the text is fine.
11. **Kid split at 90:** smile when no measurement is above 90.
12. **No within-category comparison now.**
13. **Video: a thumbnail card below the score panel**; a click turns it into the player in place. (Chosen over a thumbnail by the title playing in a pop-up, and over expanding the player between the title and the score panel.)

14. **Redesign brief (pasted review) applied, except where decisions 15–18 say otherwise:** compact video header with a small static thumbnail beside the title; the kid moved out of the header into the score panel, flipped to face the measurements, in the gauge column's bottom-right corner, without adding height; no vertical divider; less padding and spacing between header and panel.
15. _(replaced by decision 19)_ **The video stays an in-place card below the panel** (the brief's modal player not adopted); the header gets only a small thumbnail, for recognition.
16. **Drop the comparison sentence** under the gauge.
17. **Measurement meters keep 5 cells** and their colours (the brief's 10 cells and new thresholds not adopted).
18. **Fonts stay as in `STYLE.md`:** the video title, category headings and score number keep the handwritten font (the brief's sans-serif title, headings and score not adopted). Only the title's size is reduced.

19. **Remove the video player at the bottom of the page** (replaces decision 15).
20. **The video preview moves to the top right:** 2/3 of the width for the video metadata, 1/3 for the preview. Claude's reading: the preview is the player too (click plays in place), so the video can still be watched on the page.
21. **Drop the kid's figure (for now).**

22. **Drop "Watch on YouTube"** on the result: the embedded player allows jumping to YouTube. (Kept in the not-checked-yet state, which has no player.)
23. **Drop the "Stimulation score" title** (Claude kept it as sr-only text so the panel still has a heading, and moved its "i" next to the score).
24. **Gauge about 80 % of its size**, to allow more gap between the columns.

25. **Video titles: at most two lines, anything longer ends in “…”** (already the case; checked with an extra-long title at 360 and 1280 px).
26. **Channel names are links, on the home page and on this page,** for the channel details page to come. Claude's choices: the link is `/channel?id={channelId}` (a query param like `/video`, since the page will be a static export too), keyed by the channel ID because names aren't unique; so `/api/videos` items gain `channelId` and `/api/channels` items gain `id` (backend and tests updated, see API contract). Home page: in the Videos view the channel name under each title links to the channel (the rest of the row still opens the video); in the Channels view the whole row links to the channel. _(overrides plan 002: “Channels … Not linked for now”)_ Until the channel page exists, these links lead to the site's 404 page.

27. **Kid on the score panel's top edge, looking at the measurements** (Claude's suggested fix 1), with the existing `kid_lens_*` art. _(art replaced by decision 30)_
28. _(replaced by decision 31)_ **Plants on the panel's bottom edge: a selection, not all;** save some for the other pages. Claude chose `plant_3` and `plant_1`.
29. Claude's fixes along the way: the header's title is top-aligned so the kid has room under it; the gauge column is 13rem below `xl` so measurement names don't wrap at 1024 px.

30. **Use `kid_lens_downward` instead; the kid should look similarly large as the one on the home page.** Asked about the fold (home size pushes the panel ~80 px down): **~75 % of the home size, keeping close to the fold.** At 1280 × 720 the last row is visible and only the panel's bottom padding is cut.

31. **The page leaves little breathing space: remove the flowers at the bottom, and use `kid_3` instead of `kid_lens_downward`.** Kept the gaps above the panel as they were, so the smaller-reaching kid leaves ~20 px more space under the title (5–11 px before).

32. **The header and content must stay in the same place on every page** (the width must not change). Diagnosis: the content width is the same (1152 px) everywhere; what moved was its position. On browsers with classic scrollbars (Windows, most Linux, macOS with a mouse), a page that scrolls loses 15 px to the scrollbar and its centred content sits 7.5 px further left than on a page that doesn't scroll (e.g. the home page vs this page at 1280 × 1080 or 1920 × 1080). Fix: `scrollbar-gutter: stable` on `html`, which always reserves the scrollbar's space (site-wide, `globals.css`). Side effect: on a page that doesn't scroll, the footer's sky background stops 15 px short of the window's right edge.

## Open questions

1. **Feature descriptions** in **Copy** are new wording; the research team may want to check them.

## Resolved questions

1. Smile threshold: no measurement above 90 (review decision 11).
2. Comparison within the video's category: not now (review decision 12).
3. Thumbnail placement: a card below the score panel that becomes the player (review decision 13).
