# Style guide

The single, current source for how the site looks. Values (colours, fonts) live only in code, as tokens in `src/app/globals.css`; this file names them and says how they're used. Plans reference this file instead of describing styles; when a plan adds or changes a style, this file is updated in the same change. `Design Mockup.png` sets the overall look only.

## The look

- Playful illustrations, quiet UI. The hand-drawn art and the handwritten headings carry the character; cards, controls and popovers stay clean, light and consistent so they don't compete with them.
- A recurring character: the same hand-drawn kid (dark tousled hair with a top knot, mint-and-white shirt) appears on every page, in a pose that fits that page (`kid_*` files in `frontend/art/`).
- Lots of whitespace, large rounded corners, pastel panels, pill-shaped controls.
- Light theme only. Colour is never the only way information is shown.

## Tokens (`globals.css`)

- Ink: `navy` (headings, links, controls), `ink` (body text), `primary` (primary button), `error` (error text).
- Accents: `marker` (highlight behind heading words), `sunny` (selected segment, focus ring on inputs), `leaf`, `sky-blue`, `coral`.
- Score scale, cool → warm: `sky-blue` → `leaf` → `scale-low` → `scale-mid` → `scale-high` (see Score meter).
- Panels: `butter`, `mint`, `sky`.
- Fonts: `font-hand` (Shantell Sans 600) for headings and hand-lettered bits, such as the info "i"; `font-sans` (Nunito) for everything else.

## Rules

- **Borders:** 1px `navy/15` on surfaces, `navy/10` for dividers and row lines. 2px `navy` only on inputs and outlined buttons. No dark or thick borders on surfaces.
- **Corners:** sections `rounded-[2rem]`; boxes inside them and popovers `rounded-2xl`; controls `rounded-full`.
- **Shadows:** none, except popovers (one soft shadow, below). No hard or dark shadows.
- **No decoration on UI chrome:** no tilt, tails or pointers, and no hand-drawn borders. Those belong to the illustrations.
- **Hand-drawn art** comes from the team (see `CLAUDE.md`). Decorative images are `aria-hidden` with `alt=""`, hidden below `md` where they would crowd the layout. A kid shown with a page's content (rather than as decoration) stays at every width, smaller on phones. Art with a near-white background (`kid_2`, `kid_lens_*`) sits on white only, never on a pastel panel; where it overlaps a border line it uses `mix-blend-multiply` so the line shows through, plus `brightness-[1.03]` where its background would show as a faint box on white (`kid_lens_*`). Art can "interact" with a card by sitting on its edges: flowers peeking over a top edge, plants growing from a bottom edge, the kid peeking over a top edge.

## Surfaces

| Surface | Classes |
|---|---|
| Page container | `mx-auto max-w-6xl px-4 sm:px-6 lg:px-8`, the same on every page and in the header and footer. `html` has `scrollbar-gutter: stable` (`globals.css`), so the container stays in the same place whether or not a page scrolls. |
| Section card (white) | `rounded-[2rem] border border-navy/15 bg-white px-4 py-8 sm:px-8` |
| Section panel (pastel) | `rounded-[2rem] bg-butter px-5 py-8 sm:px-8` (or `bg-mint` / `bg-sky`), no border |
| Message box (error, empty) | `rounded-2xl bg-sky p-6 text-center` |
| Message box with the kid (a video being checked live, or failing to be) | `kid_2` (`w-[280px]`, centred, at every width) on the white page just above a `max-w-2xl` message box. |
| Popover (info tips) | `InfoTip`: `rounded-2xl border border-navy/15 bg-white px-4 py-3 text-sm text-ink shadow-[0_4px_16px_rgb(15_46_138/0.08)]`, `w-64`, opens next to its trigger on the side with no controls, flips when there's no room. A trigger right after a label at a row's start uses `align="row"`: the popover starts at the row's left edge. Only for supplementary text; anything users need to act should be visible text instead (e.g. helper text under an input). It may end with one "More about this →" text link to where the topic is explained (the measurement popovers link to How it works). The gap to the trigger is transparent padding inside the popover, so the mouse can cross it to the link. |

## Text

- H1: `font-hand font-semibold text-navy`, `text-[2rem] sm:text-[2.75rem] lg:text-[3.25rem]`. Only the home page's H1 has its key words in `.marker`; other pages' H1s have no highlight. A data title (a video's title on its page) is smaller, `text-[1.375rem] sm:text-2xl lg:text-[1.75rem] leading-tight`, clamped to 2 lines, no marker.
- H2: `font-hand text-2xl font-semibold text-navy sm:text-3xl`.
- Body: `text-ink`, intro `text-lg`. Helper text under a control: `mt-2 text-sm text-ink`.
- Error text: `font-semibold text-error`, in an `aria-live="polite"` element.
- Muted note (e.g. a table's “↓ Least stimulating” row): `text-sm text-ink/80`, centred.
- Numbers in columns (ranks, scores): `tabular-nums`, right-aligned in a fixed-width column, never abbreviated (`16,375`, not `16k`).

## Data display

- **Tables:** space between columns as right padding on cells, `pr-4 sm:pr-6` (`pr-4 sm:pr-5` after a narrow right-aligned number column), the same on header, rows and skeleton rows; row lines `navy/10`, header line `navy/15`. A linked row: the name's link covers the whole row (`after:absolute after:inset-0` on a `relative` row, name `font-semibold text-navy hover:underline`); a link in the row's second line (e.g. a video's channel) sits above it (`relative z-10 hover:text-navy hover:underline`).

- **Score meter** (`ScoreMeter`): the score as a bold navy number, then 5 equal segments (`h-2.5 flex-1 rounded-[3px]`, `gap-1`), `aria-hidden`. Filled segments = `max(1, ceil(score / 20))`; one is always filled as a visual convention, and the number stays the exact value. All filled segments share one colour, set by how many are filled: 1 `sky-blue`, 2 `leaf`, 3 `scale-low`, 4 `scale-mid`, 5 `scale-high`; unfilled `navy/10`. Regular size (rankings): number beside the meter from `sm` up, above it on phones. Compact size (measurement rows): number (`w-8`, right-aligned) always beside a `w-[4.5rem]` meter.

- **Score cell** (`ScoreCell`, rankings): the score as a bold navy number (`text-sm tabular-nums`, centred) on a tile, `h-8 w-10 rounded-lg`, in the score meter's colour for that score (same `filledSegments` rule) at 50 % (`bg-sky-blue/50` … `bg-scale-high/50`); navy on every tile is at least 6.3 : 1. No value: a muted `–` (`text-ink/60`) without a tile, its reason sr-only ("None detected", "Not measured", "No cuts").

- **Rankings table** (`lg`+): a table-fixed table with the table rules above: rank (`w-16`, bold navy, right-aligned; calmest first −1, −2… as on the home card), name (title + second line, as linked rows), Overall (`w-14`), then the 12 measurements (`w-12` each) in their three groups. A `navy/10` line on the left of Overall and of each group's first column. Two header rows: the group names (`text-xs` semibold `ink`, centred over their columns), then the column names set vertically (`[writing-mode:vertical-rl] rotate-180`, `text-xs` semibold navy), each a sort button (`w-10 rounded-full py-2`, `hover:bg-sky`; a ▼ under every name, `navy/30` so each reads as clickable; the selected one `bg-sunny` with a navy ▼/▲; `aria-sort` on its `th`). Rows `h-16`, `hover:bg-sky/60`. While the next page loads, the rows stay at `opacity-60` with `aria-busy`.

- **Rankings cards** (below `lg`): an `ol` of rows (`py-3`, `navy/10` lines, `hover:bg-sky/60`), `grid-cols-[3.5rem_1fr]`: the rank (bold navy, right-aligned), then the name lines and, under them (`mt-2`, wrapping, `gap-x-5`), "Overall" and the selected measurement's name (`text-sm`), each followed by its score cell.

- **Rankings page**: the H1 and intro (`text-lg`, `max-w-prose`) at the top left, the "What the measurements mean →" link on its own line under it (`mt-1`); the kid (`kid_blocks`, flipped with `-scale-x-100` so it faces the page, `w-56 lg:w-64`, `translate-y-[4%]` so knees and blocks rest on the line) at the right, on the rankings card's top edge, hidden below `md`. The card (section card) holds the search and view control, the category chips with the order button at the row's right end (`lg`+), the "Rank by" select and the order button beside it (below `lg`; below `sm` the category and "Rank by" selects side by side, `grid-cols-2 gap-x-3`, both `compact`, with the order button under them, its text aligned with the select's edge via `-ml-3`), the results line (`text-ink`), the table or cards, and the page control.

- **Score gauge** (`ScoreGauge`): a half-circle dial (inline SVG, as wide as its container; `max-w-48` when stacked, the full score column from `lg`) in five equal bands in the score scale colours, a navy needle with a round navy hub, and "calm" / "intense" (`text-sm text-ink`) under its two ends. Under it the score as a `font-hand` navy number (`text-5xl`) with a smaller "/ 100" (`text-xl`), then the score's info button. On first render the needle sweeps from 0 while the number counts up (1 s, ease-out); with `prefers-reduced-motion` both show the final value at once. The dial and the counting number are `aria-hidden`; one sr-only sentence gives the score.

- **Measurement table** (`Measurements`): groups with an H3 (`font-hand text-lg font-semibold text-navy`), then one row per measurement (`min-h-11`, row lines `navy/10`): name (semibold navy) and its info button, then a compact score meter (right). Rows without a percentile show a muted reason (`text-sm text-ink/80`, right-aligned) in place of number and meter. The info popover opens from the row's left edge (`InfoTip align="row"`, row is `relative`), so it stays on screen on phones.

- **Channel header**: `grid-cols-[2fr_1fr]`, no card: the channel name (H1, data title size), the meta line (`mt-1 text-ink`: "{29} videos in our dataset · 2018–2026") and a "View on YouTube ↗" text link in the left 2/3; the right third stays empty for the kid's head.

- **Video header**: `grid-cols-[2fr_1fr]`, top-aligned, at every width: title and channel (bold navy link) on the left; the video preview (`YouTubePlayer`) on the right. No card.

- **Score panel** (`ScorePanel`, video and channel pages): a `relative` section card with `py-6` and an sr-only H2; gauge column (gauge vertically centred) and measurements side by side from `lg`, no divider: `13rem` with `gap-x-8`, from `xl` `17rem` with `gap-x-12`; stacked below `lg`, with a `navy/10` line between them. The kid (`kid_3`, looking toward the measurements, `w-40 sm:w-44 lg:w-52`, head ~75 % of the home kid's) peeks over its top edge, hands on the border line. No other art on it. On the channel page the kid is `kid_lens_downward` (magnifying glass, looking down), at the panel's right end (`w-32 sm:w-44 lg:w-52`, table edge 84 % down the image), and the panel sits `mt-4` under the header.

- **Over-years chart** (`TimeChart`, channel page): inline SVG at the measured width, no frame. Plot 220 px high on phones, 280 px from `sm`, 320 px from 880 px wide; y gutter 32 px. Gridlines every 20 (`navy/10`), y labels 0, 50, 100 (`text-xs fill-ink/80`). Axis `navy/30` with a 5 px tick at each Jan 1; year labels (`text-xs fill-ink`, white halo so lines can pass under them) at each tick but the last, thinned to every n-th year when closer than 44 px. One dot per video (`r` 4.5, `fill-navy/50`; marked or hovered `r` 7, `fill-navy`), a pointer target of `r` 12 around it. Trend line `stroke-navy` 2.5 px, a monotone curve. The chart's size and axis are the same for every measurement. A video with none detected (a per-minute count of 0) is an open ring on the 0 line (`r` 4.5, `fill-white`, 2 px `stroke-navy/60`; marked `r` 7, `stroke-navy`); a video with no cuts (Scene discontinuity) is a × 8 px wide, 7 px above the 0 line (2 px `stroke-navy/60`, round caps; marked 11 px, 2.75 px `stroke-navy`). No legend for them; the popover names them. Hover: a dashed `navy/50` guide from the axis up to the dot, and a popover with the popover look (`w-64`, above the dot, below it near the top): title, date, then the measurement's name and a compact `ScoreMeter`. Dots and line fade in over 200 ms (`motion-safe:animate-fade-in`) when the measurement changes. The SVG is `aria-hidden`; an sr-only table (inside an sr-only `div`, since a table ignores its 1 px width) carries the values.
  - **Hanging thumbnails** (from `sm`): `mqdefault` thumbnails, 64 × 36 px, `rounded`, `ring-2 ring-white` (marked/hovered: `ring-navy`), lazy-loaded; buttons. Each hangs on a line (`navy/20` 1 px; marked: `navy` 2 px) from its date on the axis; a thumbnail goes to the first row with room (6 px apart in a row), and shifts inward at the chart's ends. Rows start 28 px under the axis and overlap like a fanned deck: 10 px apart, later rows on top. The hovered (else the opened) thumbnail stands out: on top, 8 px lower, `scale-108`, and the thumbnails below it in its stack slide down 52 px (`transition-[top,scale] duration-200`, none with reduced motion). The chart reserves those 52 px under the stacks, so nothing below it moves.
  - **Band** (phones): a `sunny/25` rectangle over the plot covering the dates of the strip's cards in view.

- **Video panel** (`VideoPanel`, under the over-years chart): `mt-6 rounded-2xl bg-sky p-4 sm:p-5`, the preview (`YouTubePlayer`, plays on click, `sm:w-60`) left and the text right from `sm`, stacked below. Title `font-hand text-lg` navy, 2 lines; date `text-sm text-ink`; the measurement's name (semibold navy) and a compact `ScoreMeter` (or a muted reason); "Video details →" text link and a "Close" outlined button. Focusable (`tabIndex=-1`): when it opens, it takes focus without the browser's jump (`preventScroll`) and scrolls into view smoothly (`scrollIntoView` with `block: "nearest"`; instant with reduced motion).

- **Video strip** (`VideoStrip`, phones): an H3 (`font-hand text-lg`) with ‹ › buttons (`size-11 rounded-full border-2 border-navy`, disabled `navy/20`), then a horizontal scroller (`snap-x snap-mandatory`, bleeding to the card's padding edge with `-mx-4 px-4 scroll-px-4`). Cards `w-40` with `pr-3`: a timeline row (`border-t navy/20` line, a `navy/40` dot per video, the year in `text-xs font-bold text-navy` at a year's first card), then one link: thumbnail (`aspect-video rounded-xl`, lazy), date `text-xs`, title `text-sm font-semibold text-navy` (2 lines), compact `ScoreMeter` or muted reason. A marked card's link gets `bg-sky` (`rounded-2xl p-1.5 -mx-1.5`).

- **Step list** (live analysis): an `ol`, centred as a block (`w-fit`), left-aligned text, one row per step (`min-h-7`, icon `size-5` + `gap-2.5`). Done: a `leaf` disc with a white check, text `ink`. Current: a navy ring with a navy dot, text bold navy, `aria-current="step"`. Next: a `navy/30` ring, text `ink/70`. Icons `aria-hidden`; done and current steps carry sr-only "(done)" / "(current)".

- **Progress bar** (live analysis): `role="progressbar"` with an `aria-label` and `aria-valuenow` in %; track `h-3 rounded-full bg-navy/12` (visible on the sky message box), fill `rounded-full bg-navy` whose width glides over the 2 s between updates (`transition-[width] duration-[2000ms] ease-linear`, none with `motion-reduce`). Never full before the work is done (at most 99 %). Bar `max-w-md`, centred; the time left (`mt-2 text-sm text-ink`) centred under it at every width. A polite live region announces step changes, not the bar.

- **Video preview** (`YouTubePlayer`): a 16:9 box as wide as its container, `rounded-2xl overflow-hidden`. Before a click: the YouTube thumbnail (`object-cover`), a `navy/20` scrim and a centred primary button with a play icon; the button shows its "Play video" label from a 20rem-wide box (`@xs`) and is a round icon-only `size-12` button below that. The click swaps in the player in the same box and moves focus to it.

- **How it works page**: one column of section cards (`gap-8`) under the H1, ending with the mint questions panel. Each card holds an H2, at most a one-sentence lead (`mt-2`, full width) and one diagram. The page follows one video through a check: the cards for steps 1–4 have step headings. The H1 sits at the top left, level with the home page's H1. The kid (`kid_wonder`, `w-52 sm:w-64 lg:w-[19rem]`, head about the home kid's size) lies on the first card's top edge (negative bottom margins, `-mb-5 sm:-mb-10 lg:-mb-11`, so elbows and laptop rest on the border line); from `sm` its art's top lines up with the H1's letters (`sm:-mt-4`), and below `sm` the kid sits centred under the H1.

- **Check field** (`CheckVideoForm`): the label, the text input with the primary "Check video →" button (a row from `md`), the hint and the error line. It always sits on `butter`, so it reads as the same thing wherever it appears: the home page's "Check a video" section panel, and How it works step 1, where it's a `rounded-2xl bg-butter` box (`px-5 pt-5 pb-1`, `lg:w-[28.25rem]` so the field is as long as the home page's) on the right of a slim card (title and sentence at the top left like every step title, `lg:grid-cols-[1fr_auto] lg:grid-rows-[auto_1fr] lg:items-start`; stacked below `lg`).

- **Step headings** (How it works): the H2 (`flex items-center gap-3`) starts with a `size-9` `sunny` number circle (`font-hand text-lg`, navy, `aria-hidden`) and an sr-only "Step 1:". Steps inside a diagram have no numbers, so they don't clash with the page's.

- **Diagrams** (How it works): drawn in code, never as images, from HTML boxes and inline SVG with the tokens only: `navy` lines and text, `navy/10`–`navy/30` for neutral marks, pastels and score-scale colours for fills. Boxes inside a section card are `rounded-2xl bg-sky`. Text in a diagram is HTML (`text-xs`/`text-sm`, never scaled with the drawing), placed at a % of the drawing's width, so it stays readable at every width. Every diagram is `aria-hidden`, with text next to it that says the same thing; words in a diagram that the text around it doesn't repeat (a ✓ list of criteria) are real text and are read out. Fills stay few and quiet: one or two pastels per diagram, `sunny` only for a highlight. A calm-to-intense row uses the score scale's 5 colors (as in `ScoreMeter`), filled up to the marked video and as rings after it. A diagram of steps is a row with `→` from `lg`, a 2 × 2 grid without arrows at `md`, stacked with `↓` below `md`.

- **Numbered markers**: a `size-6` navy circle with a white bold number (`Marker`), `aria-hidden`. A diagram's markers match the numbers in the list that explains them, so the diagram can drop its labels where they don't fit (the How it works timeline shows labels from `lg` only).

- **Timeline** (How it works, what we measure): a "Visual" and an "Audio" track (`text-xs` semibold names, beside the tracks from `sm`, above them below), numbered from left to right: events have their marker above the visual track or below the audio track; whole-clip levels sit in a column right of the tracks (icons under markers for the visual levels; a dashed `navy` average line in the audio track with its marker at its end). A time axis under it (`0:30 — 5 minutes — 5:30`, `text-xs`, `navy/30` line).

- **Measurement list** (How it works): the 12 under the timeline in marker order: one column below `sm`, two from `sm`, three from `lg`, four from `xl`. Each item: its marker, the name (`text-sm` semibold navy) and its one-line description under it (`text-sm`, at most two lines at every width). Each item has the measurement's anchor (`#rapid-cutting`, …) with `scroll-mt-[32rem]`, so on desktop a link lands with the timeline in view (on phones the list is too long for that), and is highlighted while targeted (`target:bg-butter`, `rounded-xl`).

## Controls

All at least 44 px tall (`min-h-11`, or `h-12` for form controls).

| Control | Classes |
|---|---|
| Text input | `h-12 rounded-full border-2 border-navy bg-white px-5 text-navy`, placeholder `text-ink/70`, focus: `focus:shadow-[0_0_0_5px_var(--color-sunny)] focus:outline-none`, invalid: `aria-invalid:border-error` |
| Search input | The text input with `pl-12` and a navy magnifier (`left-5 size-4`, `aria-hidden`) in a `role="search"` form; label sr-only. |
| Primary button | `h-12 rounded-full bg-primary px-6 font-bold text-white hover:bg-navy` |
| Outlined button | `min-h-11 rounded-full border-2 border-navy px-5 font-semibold text-navy` |
| Segmented control (`SegmentedControl`; switch between views) | `role="group"` with an `aria-label`: `flex rounded-full border border-navy/15 bg-white`. Each option is a `group flex min-h-11 rounded-full p-1 text-sm font-semibold text-navy` button with `aria-pressed`, filled by a visible pill `flex items-center rounded-full px-3 group-hover:bg-sky group-aria-pressed:bg-sunny`. The pill keeps the same 4 px gap to the border on every side, so its curve follows the border's. Sits on the right of its section's H2, wrapping below it when the row is too narrow; on the rankings page on the right of the search from `md`, above it below `md`. |
| Chips (`Chip`; one of many, e.g. the measurement picker, the rankings category) | A `role="group"` with an `aria-label`, then rows of `aria-pressed` buttons, one pressed at a time: each a button (`group flex min-h-11 items-center rounded-full text-sm font-semibold text-navy`) with the pill `rounded-full border border-navy/15 px-3 py-1.5 group-hover:bg-sky group-aria-pressed:border-sunny group-aria-pressed:bg-sunny`. Grouped rows start with a small label (`mr-1.5 text-sm text-ink`) and wrap. Below `sm` they become a select. |
| Select (`Select`) | Text input look with `appearance-none pr-11` and a navy chevron at the right (`right-5 size-4`); its label above it (`text-sm font-semibold text-navy`). `compact` (two side by side on phones): below `sm` `pl-4 pr-9`, chevron `right-3.5`; the label gets `min-w-0` so long option names are cut, not widening the column. |
| Order button (rankings) | A quiet text button that shows the current order and flips it: `group min-h-11 text-sm font-semibold text-navy`, holding `flex items-center gap-1.5 rounded-full px-3 py-1.5 group-hover:bg-sky` with a navy ⇅ icon (`size-4`, `aria-hidden`) and "Most intense first" / "Calmest first"; `aria-label` "Order: …". No border or fill, so it doesn't compete with the segmented control or chips. From `lg` right-aligned on the category row (`ml-auto`), wrapping under the chips when the row is full; below `lg` next to the "Rank by" select. |
| Page control (`Pagination`) | A `nav` (`aria-label="Pages"`), centred: ‹ Previous and Next › as outlined buttons (`min-h-11 min-w-11`, disabled `navy/20` border and `navy/30` text; only the arrows below `sm`), between them the page buttons (`h-11 min-w-11 rounded-full text-sm font-semibold`, `hover:bg-sky`, current `bg-sunny` with `aria-current="page"`) in 9 slots with `…` gaps (always the first and last page); below `sm` the text "Page 3 of 655" instead. |
| Text link | `font-bold text-navy underline decoration-2 underline-offset-4 hover:decoration-sunny`; trailing arrow `aria-hidden` |
| Info button | `InfoTip`: navy-outlined circle with a `font-hand` "i", 44 px touch target |
| Accordion (common questions) | Native `<details>`/`<summary>`, no JavaScript. Summary: `flex min-h-11 items-center justify-between gap-4 py-2 font-semibold text-navy`, no browser marker, a navy chevron that turns over when open (`group-open:rotate-180`, no transition with reduced motion). Answer: body text, `pb-4`. Items divided by `navy/10` lines, all closed at first. On the How it works page it sits in a mint section panel, `max-w-3xl`, with plants growing from the panel's bottom edge on `md`+. |

Focus: a 3px `navy` outline on every focusable element (global `:focus-visible`), except inputs, which use the sunny ring.
