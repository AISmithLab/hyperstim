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
- **Hand-drawn art** comes from the team (see `CLAUDE.md`). Decorative images are `aria-hidden` with `alt=""`, hidden below `md` where they would crowd the layout. A kid shown with a page's content (rather than as decoration) stays at every width, smaller on phones. Art with a near-white background (`kid_2`, `kid_lens_*`) sits on white only, never on a pastel panel; where it overlaps a border line it uses `mix-blend-multiply` so the line shows through. Art can "interact" with a card by sitting on its edges: flowers peeking over a top edge, plants growing from a bottom edge, the kid peeking over a top edge.

## Surfaces

| Surface | Classes |
|---|---|
| Page container | `mx-auto max-w-6xl px-4 sm:px-6 lg:px-8`, the same on every page and in the header and footer. `html` has `scrollbar-gutter: stable` (`globals.css`), so the container stays in the same place whether or not a page scrolls. |
| Section card (white) | `rounded-[2rem] border border-navy/15 bg-white px-4 py-8 sm:px-8` |
| Section panel (pastel) | `rounded-[2rem] bg-butter px-5 py-8 sm:px-8` (or `bg-mint` / `bg-sky`), no border |
| Message box (error, empty) | `rounded-2xl bg-sky p-6 text-center` |
| Message box with the kid (a video being checked live, or failing to be) | `kid_2` (`w-[280px]`, centred, at every width) on the white page just above a `max-w-2xl` message box. |
| Popover (info tips) | `InfoTip`: `rounded-2xl border border-navy/15 bg-white px-4 py-3 text-sm text-ink shadow-[0_4px_16px_rgb(15_46_138/0.08)]`, `w-64`, opens next to its trigger on the side with no controls, flips when there's no room. A trigger right after a label at a row's start uses `align="row"`: the popover starts at the row's left edge. Only for supplementary text; anything users need to act should be visible text instead (e.g. helper text under an input). |

## Text

- H1: `font-hand font-semibold text-navy`, `text-[2rem] sm:text-[2.75rem] lg:text-[3.25rem]`, key words in `.marker`. A data title (a video's title on its page) is smaller, `text-[1.375rem] sm:text-2xl lg:text-[1.75rem] leading-tight`, clamped to 2 lines, no marker.
- H2: `font-hand text-2xl font-semibold text-navy sm:text-3xl`.
- Body: `text-ink`, intro `text-lg`. Helper text under a control: `mt-2 text-sm text-ink`.
- Error text: `font-semibold text-error`, in an `aria-live="polite"` element.
- Muted note (e.g. a table's “↓ Least stimulating” row): `text-sm text-ink/80`, centred.
- Numbers in columns (ranks, scores): `tabular-nums`, right-aligned in a fixed-width column, never abbreviated (`16,375`, not `16k`).

## Data display

- **Tables:** space between columns as right padding on cells, `pr-4 sm:pr-6` (`pr-4 sm:pr-5` after a narrow right-aligned number column), the same on header, rows and skeleton rows; row lines `navy/10`, header line `navy/15`. A linked row: the name's link covers the whole row (`after:absolute after:inset-0` on a `relative` row, name `font-semibold text-navy hover:underline`); a link in the row's second line (e.g. a video's channel) sits above it (`relative z-10 hover:text-navy hover:underline`).

- **Score meter** (`ScoreMeter`): the score as a bold navy number, then 5 equal segments (`h-2.5 flex-1 rounded-[3px]`, `gap-1`), `aria-hidden`. Filled segments = `max(1, ceil(score / 20))`; one is always filled as a visual convention, and the number stays the exact value. All filled segments share one colour, set by how many are filled: 1 `sky-blue`, 2 `leaf`, 3 `scale-low`, 4 `scale-mid`, 5 `scale-high`; unfilled `navy/10`. Regular size (rankings): number beside the meter from `sm` up, above it on phones. Compact size (measurement rows): number (`w-8`, right-aligned) always beside a `w-[4.5rem]` meter.

- **Score gauge** (`ScoreGauge`): a half-circle dial (inline SVG, as wide as its container; `max-w-48` when stacked, the full score column from `lg`) in five equal bands in the score scale colours, a navy needle with a round navy hub, and "calm" / "intense" (`text-sm text-ink`) under its two ends. Under it the score as a `font-hand` navy number (`text-5xl`) with a smaller "/ 100" (`text-xl`), then the score's info button. On first render the needle sweeps from 0 while the number counts up (1 s, ease-out); with `prefers-reduced-motion` both show the final value at once. The dial and the counting number are `aria-hidden`; one sr-only sentence gives the score.

- **Measurement table** (`Measurements`): groups with an H3 (`font-hand text-lg font-semibold text-navy`), then one row per measurement (`min-h-11`, row lines `navy/10`): name (semibold navy) and its info button, then a compact score meter (right). Rows without a percentile show a muted reason (`text-sm text-ink/80`, right-aligned) in place of number and meter. The info popover opens from the row's left edge (`InfoTip align="row"`, row is `relative`), so it stays on screen on phones.

- **Video header**: `grid-cols-[2fr_1fr]`, top-aligned, at every width: title and channel (bold navy link) on the left; the video preview (`YouTubePlayer`) on the right. No card.

- **Score panel** (video page): a `relative` section card with `py-6` and an sr-only H2; gauge column (gauge vertically centred) and measurements side by side from `lg`, no divider: `13rem` with `gap-x-8`, from `xl` `17rem` with `gap-x-12`; stacked below `lg`, with a `navy/10` line between them. The kid (`kid_3`, looking toward the measurements, `w-40 sm:w-44 lg:w-52`, head ~75 % of the home kid's) peeks over its top edge, hands on the border line. No other art on it.

- **Step list** (live analysis): an `ol`, centred as a block (`w-fit`), left-aligned text, one row per step (`min-h-7`, icon `size-5` + `gap-2.5`). Done: a `leaf` disc with a white check, text `ink`. Current: a navy ring with a navy dot, text bold navy, `aria-current="step"`. Next: a `navy/30` ring, text `ink/70`. Icons `aria-hidden`; done and current steps carry sr-only "(done)" / "(current)".

- **Progress bar** (live analysis): `role="progressbar"` with an `aria-label` and `aria-valuenow` in %; track `h-3 rounded-full bg-navy/12` (visible on the sky message box), fill `rounded-full bg-navy` whose width glides over the 2 s between updates (`transition-[width] duration-[2000ms] ease-linear`, none with `motion-reduce`). Never full before the work is done (at most 99 %). Bar `max-w-md`, centred; the time left (`mt-2 text-sm text-ink`) centred under it at every width. A polite live region announces step changes, not the bar.

- **Video preview** (`YouTubePlayer`): a 16:9 box as wide as its container, `rounded-2xl overflow-hidden`. Before a click: the YouTube thumbnail (`object-cover`), a `navy/20` scrim and a centred primary button with a play icon; the button shows its "Play video" label from a 20rem-wide box (`@xs`) and is a round icon-only `size-12` button below that. The click swaps in the player in the same box and moves focus to it.

## Controls

All at least 44 px tall (`min-h-11`, or `h-12` for form controls).

| Control | Classes |
|---|---|
| Text input | `h-12 rounded-full border-2 border-navy bg-white px-5 text-navy`, placeholder `text-ink/70`, focus: `focus:shadow-[0_0_0_5px_var(--color-sunny)] focus:outline-none`, invalid: `aria-invalid:border-error` |
| Primary button | `h-12 rounded-full bg-primary px-6 font-bold text-white hover:bg-navy` |
| Outlined button | `min-h-11 rounded-full border-2 border-navy px-5 font-semibold text-navy` |
| Segmented control (switch between views) | `role="group"` with an `aria-label`: `flex rounded-full border border-navy/15 bg-white px-0.5`. Each option is a `group flex min-h-11 items-center rounded-full text-sm font-semibold text-navy` button with `aria-pressed`, holding a visible pill `rounded-full px-3 py-1.5 group-hover:bg-sky group-aria-pressed:bg-sunny`. Sits on the right of its section's H2, wrapping below it when the row is too narrow. |
| Text link | `font-bold text-navy underline decoration-2 underline-offset-4 hover:decoration-sunny`; trailing arrow `aria-hidden` |
| Info button | `InfoTip`: navy-outlined circle with a `font-hand` "i", 44 px touch target |

Focus: a 3px `navy` outline on every focusable element (global `:focus-visible`), except inputs, which use the sunny ring.
