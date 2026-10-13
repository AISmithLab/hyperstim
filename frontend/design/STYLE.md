# Style guide

The single, current source for how the site looks. Values (colours, fonts) live only in code, as tokens in `src/app/globals.css`; this file names them and says how they're used. Plans reference this file instead of describing styles; when a plan adds or changes a style, this file is updated in the same change. `Design Mockup.png` sets the overall look only.

## The look

- Playful illustrations, quiet UI. The hand-drawn art and the handwritten headings carry the character; cards, controls and popovers stay clean, light and consistent so they don't compete with them.
- Lots of whitespace, large rounded corners, pastel panels, pill-shaped controls.
- Light theme only. Colour is never the only way information is shown.

## Tokens (`globals.css`)

- Ink: `navy` (headings, links, controls), `ink` (body text), `primary` (primary button), `error` (error text).
- Accents: `marker` (highlight behind heading words), `sunny` (active chip, focus ring on inputs), `scale-low` → `scale-mid` → `scale-high` (score bars), `leaf`, `sky-blue`, `coral`.
- Panels: `butter`, `mint`, `sky`.
- Fonts: `font-hand` (Shantell Sans 600) for headings and hand-lettered bits, such as the info "i"; `font-sans` (Nunito) for everything else.

## Rules

- **Borders:** 1px `navy/15` on surfaces, `navy/10` for dividers and row lines. 2px `navy` only on inputs and outlined buttons; 2px `navy/20` on chips. No dark or thick borders on surfaces.
- **Corners:** sections `rounded-[2rem]`; boxes inside them and popovers `rounded-2xl`; controls `rounded-full`.
- **Shadows:** none, except popovers (one soft shadow, below). No hard or dark shadows.
- **No decoration on UI chrome:** no tilt, tails or pointers, and no hand-drawn borders. Those belong to the illustrations.
- **Hand-drawn art** comes from the team (see `CLAUDE.md`). Decorative images are `aria-hidden` with `alt=""`, hidden below `md` where they would crowd the layout.

## Surfaces

| Surface | Classes |
|---|---|
| Page container | `mx-auto max-w-6xl px-4 sm:px-6 lg:px-8` |
| Section card (white) | `rounded-[2rem] border border-navy/15 bg-white px-4 py-8 sm:px-8` |
| Section panel (pastel) | `rounded-[2rem] bg-butter px-5 py-8 sm:px-8` (or `bg-mint` / `bg-sky`), no border |
| Message box (error, empty) | `rounded-2xl bg-sky p-6 text-center` |
| Popover (info tips) | `InfoTip`: `rounded-2xl border border-navy/15 bg-white px-4 py-3 text-sm text-ink shadow-[0_4px_16px_rgb(15_46_138/0.08)]`, `w-64`, opens next to its trigger on the side with no controls, flips when there's no room. Only for supplementary text; anything users need to act should be visible text instead (e.g. helper text under an input). |

## Text

- H1: `font-hand font-semibold text-navy`, `text-[2rem] sm:text-[2.75rem] lg:text-[3.25rem]`, key words in `.marker`.
- H2: `font-hand text-2xl font-semibold text-navy sm:text-3xl`.
- Body: `text-ink`, intro `text-lg`. Helper text under a control: `mt-2 text-sm text-ink`.
- Error text: `font-semibold text-error`, in an `aria-live="polite"` element.

## Controls

All at least 44 px tall (`min-h-11`, or `h-12` for form controls).

| Control | Classes |
|---|---|
| Text input | `h-12 rounded-full border-2 border-navy bg-white px-5 text-navy`, placeholder `text-ink/70`, focus: `focus:shadow-[0_0_0_5px_var(--color-sunny)] focus:outline-none`, invalid: `aria-invalid:border-error` |
| Primary button | `h-12 rounded-full bg-primary px-6 font-bold text-white hover:bg-navy` |
| Outlined button | `min-h-11 rounded-full border-2 border-navy px-5 font-semibold text-navy` |
| Chip (toggle) | `min-h-11 rounded-full border-2 border-navy/20 bg-white px-5 font-semibold text-navy hover:border-navy/50`, pressed: `border-sunny bg-sunny` (`aria-pressed`) |
| Text link | `font-bold text-navy underline decoration-2 underline-offset-4 hover:decoration-sunny`; trailing arrow `aria-hidden` |
| Info button | `InfoTip`: navy-outlined circle with a `font-hand` "i", 44 px touch target |

Focus: a 3px `navy` outline on every focusable element (global `:focus-visible`), except inputs, which use the sunny ring.
