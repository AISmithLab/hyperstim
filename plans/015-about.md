# 015 — About page

**Area:** About page (`/about`), and the footer's links.

## Goal

Build `/about`: who makes the site (the AI Smith Lab at UC San Diego) and why, and how to get in touch. For parents, in plain words: no data or technical details _(human decision, 2026-10-26)_.

## Decisions

- **The site speaks as the lab** _(human decision, 2026-10-26)_: the AI Smith Lab at UC San Diego. Named on this page only, not in the footer's copyright (it stays "© {year} HyperStim?") _(human decision, 2026-10-26)_.
- **Layout: the text straight on the page, no card, no section headings** _(human decision, 2026-10-26: like the About pages of other research projects; variation 2, "open column", of the second round of mockups)_, at the same width as the other pages' content _(human decision, 2026-10-27: the narrower column looked out of step with the other pages)_: the H1 "About us" _(human decision, 2026-10-27)_, the text, then the team. Then "Get in touch" on a mint section panel with plants growing from its bottom edge from `md`, as on the How it works questions panel _(human decision, 2026-10-26: greenery idea 4, to make the page warmer)_.
- **Text** _(human decision, 2026-10-26: the team's own words; its opening question dropped, 2026-10-27)_:
  - "While concerns about overstimulating children's content are growing, parents often have limited information about how videos differ in their pacing, colors, motion, and sound."
  - "HyperStim? is a research-based platform developed by the AI Smith Lab at UC San Diego. By analyzing thousands of children's YouTube videos, we measure their audiovisual stimulation levels and make the results accessible to parents for exploration and comparison." "AI Smith Lab" is an external text link to https://aismithlab.com _(human decision, 2026-10-26)_.
  - "Our mission is to bring greater transparency to children's digital media and empower families to make informed decisions about what their children watch."
- **Team** _(human decision, 2026-10-26)_: "Contributors: Shao-Yu Chu, Noel Mekogue" (alphabetical by last name) and "Advisor: Haojian Jin". No photos _(human decision, 2026-10-26)_.
- **Get in touch:** "Questions, corrections or ideas? Please fill out our contact form." The form is plan 009's Google Form (`CONTACT_URL`), as an external text link (new tab, sr-only "(opens in a new tab)") _(human decision, 2026-10-26: use the form)_. Plan 009 now links it from the policy and this page _(human decision, 2026-10-26)_.
- **"HyperStim?" in bold italic** wherever the page's text mentions it _(human decision, 2026-10-26)_.
- **American English** _(human decision, 2026-10-26: "colors", not "colours"; a site-wide rule in `CLAUDE.md`)_.
- **Not on the page** _(human decision, 2026-10-26)_: the paper or any link to the research, the dataset, the GitHub repo (it goes in the footer), acknowledgements (maybe later).
- **The kid: `kid_wave`** _(human decision, 2026-10-26: art added by the team)_, sitting cross-legged and waving, on the contact panel's top edge at the right; hidden below `md`. Its head is the same size as on the other pages _(human decision, 2026-10-26: measured by head size)_: measured by head height, since its eyes are drawn wide apart for its head (by eye distance it came out about 12 % smaller), which gives `kid_quiet`'s widths, `w-54 lg:w-61 xl:w-72`. Added to `art/used.json` (largest width 288).
- **Navigation:** "About" joins the header nav, last: Home, Rankings, Compare, How it works, About.
- **Footer, less in it.** A footer holds what the header doesn't: legal pages, settings, outside links. So:
  - Left: "© {year} HyperStim?" (unchanged) _(human decision, 2026-10-26)_.
  - Right, in this order: **Privacy policy · Cookie settings · GitHub ↗** _(GitHub as a text link: human decision, 2026-10-26)_. Privacy policy and its cookie settings belong together; the outside link goes last, its ↗ saying it leaves the site. Cookie settings is shown only when there is a choice to make (plan 009), and must stay reachable from every page.
  - Dropped: "FAQ" (it only jumps to the questions at the end of How it works, which is in the header) and "About us" (in the header instead).
  - GitHub: the public repo, opening in a new tab.
- **Privacy policy:** unchanged. The page adds only links, all of them to places the policy already covers (the contact form) or outside links (GitHub, like any link). No new third party loads anything.
- **Style:** a new page layout (one open column), reusing the questions panel's plants and the shared text styles; `STYLE.md` gets an **About page** entry. No new surfaces or controls.

## Steps

1. `src/app/about/page.tsx` + `components/about/AboutPage.tsx`; metadata (title, description) and sitemap entry (plan 011).
2. `kid_wave` converted to WebP via `used.json`.
3. Header: add About. Footer: the three links in the order above.
4. Tests: one H1 and only the contact H2; contributors (by last name) then advisor; the lab and form links (new tab); the name in bold italic; header marks About as current; footer links and order, no FAQ.
5. `STYLE.md` entry; plan 001's pages, header and footer lines; plans 002 and 006's footer mentions.
6. Screenshots at 360 and 1280 px (with the header and footer), compared against `STYLE.md`.

## Open questions

None.
