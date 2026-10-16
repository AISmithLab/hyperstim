# 008 — Compare page

**Area:** Compare page (`/compare`). The "Compare with…" links on the video and channel pages are recorded in plans 004 and 005.

**Status:** built, in review (2026-10-16).

## Goal

Build `/compare`: two videos, or two channels, side by side, showing **where they differ**. It shows no verdict and takes no votes. The page answers one question: "How different is the production of these two?" Everything else stays on the detail pages, which the compare page links to. The page itself needs no backend changes; channel links (proposed) add one lookup endpoint.

## Decisions

- **Scope.** The page, its picker, and the "Compare with…" links. Not in scope: comparing a video with a channel _(human decision)_, more than two items, comparing from the rankings rows, and any vote or "guess which" game _(human decision)_.
- **No voting, no stored input.** Nothing the visitor does on this page is sent anywhere except the reads below. So we need no database, can't get too few votes to mean anything, and can't have the results skewed on purpose _(human decision)_.
- **Videos or channels**, switched with the segmented control, as on the rankings page. Videos are the default. Switching clears both slots, since IDs don't carry over.
- **Two slots, A and B**, each with a fixed colour: A is a soft coral and B a soft blue (plan 001's `#FDA28C` / `#9FBBF5`, as the new tokens `side-a` / `side-b`). Colour is never the only cue: each slot, headline and table column also carries an "A" or "B" badge (a circle in its colour, navy letter; at the top of a slot as large as the × beside it _(human decision)_).
- **"vs." between the two slots** _(human decision)_, in grey body text like the intro _(human decision)_, also while picking: centred between the two items once both are in, level with the fields while picking, and between the stacked pickers on phones.
- **The picker: one field per empty slot** that takes both kinds of input, so visitors never need to know what's in our dataset:
  - **Typing a name** lists matches from the dataset as they type (300 ms debounce). The list shows about 6 at a time and **scrolls** _(human decision, 2026-10-16)_; more load as it nears the end (20 per request, `offset` paging), so typing stays fast however many match. Arrow keys move through what's loaded and load more at the end. For videos it shows title and channel; for channels, the name and "{N} videos". No scores in the list _(human decision)_. It's an ARIA combobox with a listbox: arrow keys, Enter, Escape. No library.
  - **Pasting a YouTube link or ID** (videos only) offers that video as the first option, "Use this video". If the video is in the dataset or was checked before, it loads straight away. Otherwise the live check starts in that slot (see **Live check in a slot**).
  - **No match:** "No videos in our dataset match “{q}”. Paste a YouTube link to check any video." For channels: "No channels in our dataset match “{q}”."
  - **A channel link in video mode:** "That’s a channel link. Switch to Channels to compare channels." In channel mode, links are looked up (see **Channel links**).
  - **The other slot's item is left out** of the suggestions; pasting its link says “That video is already in the other slot.” A URL with the same ID twice keeps only A.
  - **Search fails:** “We couldn’t search right now. Please try again in a moment.”
- **Channel links in the channel picker** _(human decision, 2026-10-16)_. The channel field also takes YouTube links, so a parent can paste whatever they have:
  - **Channel links:** `youtube.com/channel/UC…`, `youtube.com/@handle`, and the older `/c/…` and `/user/…` forms.
  - **Video links** (any form the check field takes): the video's channel is used.
  - A pasted link is offered as one option, "Use this channel's link". Picking it looks the channel up ("Looking up this channel…" under the field, usually under a second, a few seconds when YouTube has to be asked).
  - **In our dataset:** the slot fills with that channel, as if it had been picked from the list.
  - **Not in our dataset:** the field stays, with the message “{Channel name} isn’t in our dataset yet. Checking a whole channel is coming soon. For now, pick a channel from our dataset.” The name is shown when the lookup found it; otherwise it says “This channel”.
  - **Can't be found** (removed, private, not a channel): “We couldn’t find a YouTube channel for that link.”
- **Searching channels** lists every channel that has a channel page (`minVideos=1`), not only the ≥ 5 shown in the rankings, because a parent may look for a small channel. Its score still averages fewer videos, as on its own page.
- **Where people usually start: from a detail page.** The video page gets a "Compare with another video →" text link and the channel page a "Compare with another channel →" link. Each opens `/compare` with A filled, so only B is left to pick. On the video page the link shares the channel name's line (its own line on phones), which keeps it clear of the kid peeking over the score panel. On the channel page it follows "View on YouTube ↗".
- **A filled slot** shows a compact header:
  - Video: its preview (`YouTubePlayer`), the title (3 lines at most) as a link to the video's page, and the channel.
  - Channel: the name as a link to the channel's page, and its meta line as on the channel page ("{29} videos in our dataset · 2018–2026"). No separate "details →" links _(human decision)_.
  - Each has its badge at the top left and a **× button at the top right** ("Remove video A") that empties the slot, with focus in its field _(human decision)_. No "Change" button. When both slots are filled, the headers sit side by side at every width, so the two stay in view together. Empty slots (pickers) are stacked below `md`.
- **One sound at a time.** Both previews can be played, but when one starts, the other pauses. This uses the YouTube embed's message API (`enablejsapi=1`): the player reports its state, and the page sends `pauseVideo` to the other one. No script is loaded from YouTube. `YouTubePlayer` gains an optional `onPlay` callback and a `pause()` handle. The video and channel pages don't use them.
- **What a comparison shows,** in this order, once both slots are filled:
  1. **Summary:** one sentence.
     - Videos: “[B] is more intense overall: 41 vs 82.” A's score always comes first, like the table's columns _(human decision)_. Within 5 points _(human decision)_: “[A] and [B] are about as intense as each other: 52 vs 49.”
     - Channels: “[B]’s videos are more intense on average: …”
     - [A]/[B] are the badges, followed by the name in sr-only text. No good/bad wording (plan 006).
  2. **The biggest differences, in words** _(human decision)_ (instead of a long list of bars, _human decision: too long to read_): under the summary, at most **two** lines, for the measurements whose values differ most, and only by **20 points or more**. Each says what the higher side does more, in plain words, with the two values: “[A] cuts to a new shot more often: 99 vs 0.” Values are always the 0–100 values the table shows _(human decision)_: mixing units and 0–100 values was hard to read. **A's value always comes first** (“[B] is louder: 21 vs 77”), not the higher one _(human decision)_: swapping the order made the numbers hard to read. With no difference of 20+: “Their 12 measurements are all within 20 points of each other.”
     - A count of 0 is a 0 like any other value (plan 004) _(human decision, 2026-10-16)_: “99 vs 0” is a big difference. A side without a value ("No cuts", "No sound", "Not measured") has no difference to compare.
  3. **Every measurement in a table** _(human decision)_: Overall, then the 12 in their three groups (group names as small row headers), one column per side headed by its badge. **From `lg`, two columns** _(human decision)_, like the video page: Overall and Pacing intensification on the left, the other two groups on the right; stacked below `lg`. **The headline measurements' rows are highlighted** (butter background) _(human decision)_, so it's clear where to look. Each value is a score cell, as in the rankings. A side without a value shows its reason ("No cuts", "No sound", "Not measured") in muted text, as on the video page, with no note explaining it _(human decision)_. The info button next to each name explains it and gives both raw values where there is a unit (“A: 30.3 cuts per minute”). No “Biggest differences first” note _(human decision)_.
  4. **Channels only — Over the years:** both channels on **one chart**: dots and a trend line per channel, with the measurement picker (Overall + the 12) above it, as on the channel page. This is the one thing two channel pages can't show: how the two changed over time, and how widely each channel's videos spread. Hovering a dot shows the same popover as on the channel page. There are no hanging thumbnails, video panel or strip; a dot links to its video's page. Below `sm` the chart stays (it scales). The sr-only table holds both channels' values.
- **Chart colours:** fills use `side-a`/`side-b`. Lines and dot outlines use darker shades, `side-a-strong` (`#D9603F`, 3.7 : 1) and `side-b-strong` (`#4F7FE0`, 3.9 : 1). A's trend line is solid and B's dashed, and A's videos are circles and B's squares, so colour isn't the only cue.
- **Live check in a slot.** `LiveAnalysis` gains a compact form: the step list and progress bar inside the slot, without the kid. A failure shows its message in the slot; × empties it. The other slot stays usable meanwhile. The comparison appears once both are scored.
- **State in the URL:** `/compare?a={id}&b={id}`, with channels as `/compare?view=channels&a=…&b=…`. Defaults are left out. Filling or changing a slot adds a history entry, so links can be shared and Back works. An invalid or unknown ID shows a message in that slot ("We couldn’t find this video."); × empties it. A video ID not in the dataset still starts the live check, as on the video page.
- **The kid: `kid_compare`** _(human decision)_: sitting cross-legged, a coral card in one hand and a blue card in the other (the A side's colour on the left), looking between them. It sits on the card's top edge at the right of the H1 row, hidden below `md`, **as large as the home page's kid** (same head size: 288 / 328 / 384 px wide at `md` / `lg` / `xl`, see 001) _(human decision, 2026-10-16: at `md` it was 62 % of the home kid)_. The right padding that keeps the text clear grows with it at `md`. It's taller than the H1 and intro, so it rises above them rather than pushing the H1 down; the H1 stays level with the other pages'. The Videos/Channels control sits under the intro, so the kid has the row's right end (as on the rankings page).
- **Reuse:** page container, section card, message box, search input, segmented control, chips/select (via `MeasurementPicker`), outlined button, text link, `InfoTip` (`STYLE.md`); `parseVideoInput`, `featureDisplay`, `formatValue`, `FEATURE_INFO`; `getVideo`, `getChannel`, `getVideos`/`getChannels` with `q`; `LiveAnalysis`; the channel chart's scales, year axis and trend helpers (`chart.ts`).
  - New: `ComparePage`, `Picker` (combobox), `Slot`, `Comparison` (summary, headlines, table), `CompareChart`.
  - `TimeChart` keeps its look. Its scales and axis move into shared pieces (`timeScale` in `chart.ts`, `ChartGrid`/`TimeAxis` in `ChartAxes.tsx`), and `CompareChart` is a second, smaller chart on them (two series, no thumbnails), since the channel page's thumbnail and panel logic doesn't fit two channels.
  - The measurement info popover (`FeatureTip`) moves out of the measurement table, for the compare table too.
- **New styles go into `STYLE.md` in the same change:** the `side-a`/`side-b` tokens and their strong shades, the A/B badge, the compare slot, the combobox listbox, the comparison (headlines and table), and the two-series chart.

## Design

### Layout

DOM order: H1 + intro → view control → slot A → “vs.” → slot B → summary → headlines → table → (channels) over the years → footer.

| Width | Layout |
|---|---|
| `lg`+ | H1, intro and the Videos/Channels control under it, top left; the kid on the card's top edge at the right. One section card holds the two slots in two equal columns with “vs.” between them. Under them, in the same card, the summary and headlines, then the two tables side by side (`max-w-5xl`, centred). Channels: an "Over the years" section card below. |
| `md`–`lg` | Same, with narrower columns. |
| < `md` | Empty slots (pickers) stacked, with “vs.” between them. Filled slots side by side in two narrow columns with a narrow “vs.”: badge and ×, preview, title (3 lines). The summary, headlines and table run full width; long measurement names wrap. |

**Desktop (1280 px), two videos**

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ HyperStim?                                      Home  Rankings  Compare  How it works  About │
├────────────────────────────────────────────────────────────────────────────────────────────┤
│  Compare                                                                                   │
│  Put two videos side by side and see where their production differs.     {kid, two cards} │
│  ( Videos | Channels )                                                    {sits on edge}  │
│  ╭─ card ──────────────────────────────────────────────────────────────────────────────╮  │
│  │  (A)                            ×           (B)                            ×         │  │
│  │  ┌───────────────────────────────┐          ┌───────────────────────────────┐        │  │
│  │  │ ▶ preview                     │   vs.    │ ▶ preview                     │        │  │
│  │  └───────────────────────────────┘          └───────────────────────────────┘        │  │
│  │  Super Fast Toy Party (link)                Quiet Garden Walk (link)                 │  │
│  │  Wheelie Friends TV                         Little Leaf                              │  │
│  │ ──────────────────────────────────────────────────────────────────────────────────── │  │
│  │            (A) is more intense overall: 82 vs 41.                                    │  │
│  │            (A) cuts to a new shot more often: 88 vs 35.                              │  │
│  │            (A) has more sudden loud moments: 80 vs 0.                                │  │
│  │                                                                                      │  │
│  │                         (A)   (B)                              (A)   (B)             │  │
│  │  Overall               [82]  [41]       Sustained sensory intensity                  │  │
│  │  Pacing intensification                 Visual intensity (i)  [40]  [3]              │  │
│  │ ░Rapid cutting (i)     [88]  [35]░      …                                            │  │
│  │  Scene discontinuity   [60]  No cuts    Reward patterning                            │  │
│  │  …                                      …                                            │  │
│  │  (░ = highlighted headline row)                                                      │  │
│  ╰──────────────────────────────────────────────────────────────────────────────────────╯  │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Desktop, picking B** (A filled from the video page's link)

```
│  │  (A) Super Fast Toy Party …               (B)                                       │  │
│  │  [preview, title, channel]                Video or channel name, or a YouTube link  │  │
│  │                                           ( 🔍 bluey                             )  │  │
│  │                                           ┌───────────────────────────────────────┐ │  │
│  │                                     vs.   │ Bluey Dance Mode                      │ │  │
│  │                                           │ Ludo Studio                           │ │  │
│  │                                           └───────────────────────────────────────┘ │  │
│  │                                           Search our dataset, or paste a link to     │  │
│  │                                           check any video.                           │  │
```

**Phone (360 px), two videos**

```
┌──────────────────────────────┐
│ HyperStim?               ☰   │
├──────────────────────────────┤
│ Compare                      │
│ Put two videos side by side… │
│ ( Videos | Channels )        │
│ ╭─ card ───────────────────╮ │
│ │ (A)      ×   (B)      ×  │ │
│ │ [preview] vs. [preview]  │ │
│ │ Super Fast   Quiet       │ │
│ │ Toy Party    Garden Walk │ │
│ │ ──────────────────────── │ │
│ │ (A) is more intense      │ │
│ │ overall: 82 vs 41.       │ │
│ │ (A) cuts to a new shot   │ │
│ │ more often: 88 vs 35.    │ │
│ │              (A)   (B)   │ │
│ │ Overall      [82]  [41]  │ │
│ │ Rapid        [88]  [35]  │ │
│ │ cutting (i)              │ │
│ │ …                        │ │
│ ╰──────────────────────────╯ │
└──────────────────────────────┘
```

**Channels:** the same card, with channel headers. Below it is a second section card, "Over the years": the measurement picker, then one chart with A's dots and solid line and B's dots and dashed line, and a small legend: (A) {name} ── (B) {name} - - .

### States

- **Nothing picked:** two empty pickers, and under the card a muted line: “Not sure where to start? [Browse the rankings →](/rankings)”.
- **One picked:** that slot's header and the other slot's picker. No summary yet.
- **Loading a slot:** a skeleton header in that slot (`aria-busy`).
- **Live check in a slot:** the compact step list + bar. Screen readers hear step changes, as on the video page.
- **Slot error** (unknown ID, failed check, network): a message in the slot with "Try again" (network only); × empties the slot.
- **Search loading:** the list keeps its last results, dimmed. Older responses are ignored, as in rankings.

### Copy

| Where | Text |
|---|---|
| `<title>` | Compare - HyperStim? · once both are loaded: {A} vs {B} - HyperStim? |
| Meta description | Put two kids’ videos or channels side by side and see where their production differs. |
| H1 | Compare |
| Intro | Videos: Put two videos side by side and see where their production differs. · Channels: Put two channels side by side and see where their production differs. |
| View control `aria-label` | Compare · Videos · Channels |
| Slot heading (sr-only H2) | Video A / Video B · Channel A / Channel B |
| Picker label | Videos: Video name or YouTube link · Channels: Channel name or YouTube link |
| Picker placeholder | Title, channel, or link… · Channel name, or link… |
| Picker hint | Videos: Search our dataset, or paste a link to check any video. · Channels: Search our dataset, or paste a channel or video link. |
| Link option | Use this video: {ID} · Channels: Use this channel’s link |
| Channel lookup (under the field) | Looking up this channel… · {Name} isn’t in our dataset yet. Checking a whole channel is coming soon. For now, pick a channel from our dataset. · We couldn’t find a YouTube channel for that link. · You’ve looked up or checked several new videos and channels in the last hour. Please try again later, or pick a channel from our dataset. · We couldn’t look up that link. Please try again in a moment. · That channel is already in the other slot. |
| Loading more (in the list) | Loading more… |
| No match | No videos in our dataset match “{q}”. Paste a YouTube link to check any video. · No channels in our dataset match “{q}”. You can also paste a channel or video link. |
| Channel link in video mode | That’s a channel link. Switch to Channels to compare channels. |
| Invalid link | That doesn’t look like a YouTube link or video ID. (as the check field) |
| Suggestions count (sr-only, live) | {20} suggestions(, more as you scroll) |
| Slot button | × (`aria-label` “Remove video A”) |
| Between the slots (`aria-hidden`) | vs. |
| Already picked | That video is already in the other slot. |
| Search error | We couldn’t search right now. Please try again in a moment. |
| Slot errors | We couldn’t find this video. · We couldn’t find this channel. · We couldn’t load this video. Try again |
| Summary, videos | [A] is more intense overall: {82} vs {41}. ([B] …: {A’s} vs {B’s}.) · [A] and [B] are about as intense as each other: {52} vs {49}. |
| Summary, channels | [A]’s videos are more intense on average: {82} vs {41}. · [A] and [B]’s videos are about as intense as each other: {52} vs {49}. |
| Headline | [A] cuts to a new shot more often: {99} vs {0}. (channels: [A]’s videos cut …) · none: Their 12 measurements are all within 20 points of each other. |
| Table caption (sr-only) | Every measurement: {A} (A) and {B} (B), 0–100 |
| Info popover extra | A: {30.3 cuts per minute} · B: {0 cuts per minute} |
| Channels section H2 | Over the years |
| Chart legend | (A) {name} · (B) {name} |
| Nothing picked | Not sure where to start? Browse the rankings → |
| Video page link | Compare with another video → |
| Channel page link | Compare with another channel → |

## API contract

No changes. The page uses:

```
GET /api/videos?q=<text>&sort=score&order=desc&offset=<n>&limit=20                picker suggestions (videos)
GET /api/channels?q=<text>&sort=score&order=desc&minVideos=1&offset=<n>&limit=20   picker suggestions (channels)
GET /api/videos/{id}       a filled video slot (dataset or live-checked)
POST/GET /api/analyses/{id} live check in a slot
GET /api/channels/{id}     a filled channel slot (includes its videos for the chart)
```

Channel links _(human decision, 2026-10-16)_:

```
GET /api/channel-lookup?url=<YouTube channel or video link>
  → 200 { channelId, name: string | null, inDataset: boolean }
  → 404  no channel found for the link (removed, private, unknown handle)
  → 422  not a YouTube channel or video link
  → 429  too many lookups from this IP address
```

- Fast paths, no YouTube request: a `/channel/UC…` link (`inDataset` from the dataset; `name` from the dataset, else null); a video in the dataset or already checked live (its stored channel).
- Otherwise the backend asks YouTube through yt-dlp, as the live check's look-up step does (a handle, `/c/`, `/user/`, or a video we don't have). Results are cached in memory for a day. **A lookup that asks YouTube counts toward the live check's per-IP limit** (`ANALYSIS_LIMIT_PER_IP`, plan 004), sharing its count _(human decision, 2026-10-16)_; fast paths don't count. Over the limit: 429, and the field says “You’ve looked up or checked several new videos and channels in the last hour. Please try again later, or pick a channel from our dataset.”

Suggestions come in score order, not by closeness of match. The list is short and ranked by Overall, as on the rankings page.

## Steps

The frontend is built against mock data, then reviewed. There is no backend step.

1. **Shared pieces.**
   - Tokens `side-a`, `side-b`, `side-a-strong`, `side-b-strong` (contrast checked).
   - `YouTubePlayer`: `onPlay` and `pause()` via the embed's message API.
   - `LiveAnalysis`: compact form.
   - Chart helpers needed by both charts move into `chart.ts`.
   - `STYLE.md` entries.
2. **Picker.** `ComparePicker`: debounced search, link/ID detection, the combobox keyboard pattern, leaving out the other slot's item, the no-match and wrong-kind messages.
3. **Page.**
   - `/compare` (`useSearchParams` inside `Suspense`) with the URL state helper (parse with fallbacks, serialize without defaults; tested).
   - Slots, summary, headlines, table, `CompareChart`, all states.
   - The "Compare with…" links on the video and channel pages.
4. **Tests.**
   - URL state and history.
   - View switch clears the slots.
   - Picker: debounce, keyboard, link option, live check start, other item excluded.
   - Summary wording, including the 5-point "about as intense" rule.
   - Headlines: at most two, 20+ points, the higher side, 0–100 values; their rows highlighted.
   - Only one player plays (message API mocked).
   - Chart: two series, sr-only table.
   - Every state renders.
5. **Review.**
   - Screenshots at 360 and 1280 px, plus 320, 768 and 1920 px, next to the video and channel pages, compared with `STYLE.md`.
   - Keyboard-only pass through the picker.
   - Two real previews: playing one pauses the other.
   - A run against the real backend, including a live check in slot B.
   - Stop for review.

## Review decisions

- Desktop sketch: the Videos/Channels control moved under the intro, and the kid sits on the card's top edge at the right (see **Decisions**, the kid).
- Desktop, picking and phone sketches: × at each slot's top right, “vs.” between the slots, linked titles, no scores in the suggestions, and the headlines and table in place of the bars (see **Decisions**: "vs.", the picker, a filled slot, what a comparison shows).
- Desktop and phone sketches: headlines in 0–100 values, the table in two columns from `lg`, the headline rows highlighted (see **Decisions**, what a comparison shows).

## Open questions

None.
