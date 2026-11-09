# 018 — Blog

**Area:** The blog: the Blog tab, the post list (`/blog/`), each post's page (`/blog/<slug>/`), how posts are written (markdown files and the writing guide), and how posts show up in search results and link previews.

## Goal

The team publishes a blog post now and then. Visitors find all posts under a new **Blog** tab, newest first, and read each one on its own page. Each post is one markdown file in the repo, and can have figures, videos, YouTube embeds and references besides text and headings. Every post can be found through search engines on its own.

Layout review: the artifact "Blog page layout" (round 2).

## Decisions

- **Tab order:** Home, Rankings, Compare, How it works, **Blog**, About. The tools come first, Blog sits with the reading pages, and About stays last. On the post pages, Blog is marked as the current tab.
- **Post list (`/blog/`):**
  - H1 "Blog", with no intro line under it _(human decision, 2026-11-09: the sample line didn't work)_.
  - The kid is `kid_notebook` (lying on its tummy, writing in a notebook with a pencil) _(human decision, 2026-11-09: art added by the team)_. It lies at the right on the card's top edge, as on Rankings, hidden below `md`. It appears on this page only, not on posts _(human decision, 2026-11-09)_.
    - Its head is the hero kids' size, compared by head, not by the whole figure _(human decision, 2026-11-09: it was drawn too big)_. The transparent margins are trimmed when it's converted. The eye distance is 0.122 of the trimmed width, which gives `md:w-[15.375rem] lg:w-[17.5rem] xl:w-[20.5rem]`, with `translate-y-[4%]` so it rests on the line. The heading text keeps clear of it with right padding, and the hero gets a minimum height so the kid stays clear of the header. Add it to `art/used.json` (largest width 328).
  - One section card with every post, newest first. Each post shows its date, its title (`font-hand`, a link that covers the whole row) and its TL;DR.
  - Posts are separated by straight `navy/10` lines _(human decision, 2026-11-09: the lines curved at their ends)_.
  - The TL;DR uses the card's full width _(human decision, 2026-11-09)_.
  - **10 posts per page on every screen**, in numbered pages _(human decision, 2026-11-09: with the TL;DRs, phones scrolled a long way after a few posts; one fixed count, so a page number means the same posts on every device)_.
    - Page 1 is `/blog/`; later pages are `/blog/page/2/` and so on. Each is a static page built at build time, so paging works without JavaScript. There's no `/blog/page/1/`.
    - The page control sits under the list, inside the card, above a `navy/10` line. It's the site's page control (`STYLE.md`, Page control): ‹ Previous, the page numbers and Next › from `sm`, and "‹ Page 1 of 2 ›" on phones. Here its parts are links, not buttons. There's no control when everything fits on one page.
    - Each later page has the H1 "Blog" and the kid, like page 1. Its title is "Blog, page 2 - HyperStim?", with the same description and a canonical URL of its own. All pages are in the sitemap.
    - A new post pushes the oldest post on each page onto the next one. Links to page 2 and beyond don't promise fixed content; the newer / older links on posts are what lead through all posts in order.
- **Post page (`/blog/<slug>/`):**
  - From the top: "← All posts" (text link), the H1 title, the date, then the TL;DR box (`rounded-2xl bg-butter`, a "TL;DR" heading in `font-hand`).
  - The title fills the full width before it wraps, with no balanced line breaks _(human decision, 2026-11-09: the title didn't use the full width)_.
  - Then the body at the page container's full width _(human decision, 2026-11-09: it didn't use the full width)_, followed by References and the newer/older links.
  - No author or reading time _(human decision, 2026-11-09)_.
- **Elements inside a post:**
  - Headings: `##` and `###` (the H1 is the title).
  - Figures: the image with a caption under it.
  - Videos hosted with the site: a native `<video controls preload="none">` with a poster image and a caption.
  - YouTube embeds: the existing `YouTubePlayer` (nothing loads from YouTube before Play) with a caption.
  - References: a citation `[1]` in the text links to the numbered References list at the post's end, and each reference has a ↩ link back to the text. In the list, the number `[1]` has the same style as the reference text (`ink`, regular weight) _(human decision, 2026-11-09)_.
  - Lists, links, bold, italic, quotes and tables, all standard markdown.
- **Captions:** "Figure N." and "Video N." are numbered automatically, figures and videos counted separately in the order they appear. YouTube embeds count as videos. The author writes only the caption text _(human decision, 2026-11-09)_.
- **References use markdown footnotes** (`[^key]` in the text, `[^key]: …` anywhere in the file), numbered by first use and shown as `[1]`. Authors don't number them by hand, so adding a citation never means renumbering.
- **Newer / older links** at the bottom: "← Newer post" and "Older post →", each with that post's title. A link appears only when that post exists.
  - From `sm`: side by side, newer on the left, older on the right and right-aligned.
  - Below `sm`: stacked, both left-aligned, newer on top, with a straight `navy/10` line between them _(human decision, 2026-11-09: one left- and one right-aligned looked odd on phones)_.
  - No background fill _(human decision, 2026-11-09: drop the blue boxes)_. A thin solid line across the full width above both links (`border-t border-navy/10`, `pt-3`), the same line as above References _(human decision, 2026-11-09)_. Each link: a small "← Newer post" / "Older post →" label (`text-sm font-semibold text-ink`), then the title (`font-hand text-lg` navy, underlined on hover).
- **Files:**
  - One markdown file per post: `frontend/content/blog/<slug>.md`. The slug is the filename and becomes the URL.
  - Front matter fields:
    - `title` (required)
    - `date` (required, `YYYY-MM-DD`)
    - `tldr` (required)
    - `description` (optional; see Search and previews)
  - Images, videos and posters go in `frontend/public/blog-media/<slug>/`, and the markdown refers to them by filename only.
- **Markdown rendering** happens at build time into static HTML, with no JavaScript needed to read a post.
  - Libraries: `react-markdown`, `remark-gfm` (footnotes, tables), `remark-directive` (the figure, video and YouTube blocks) and `gray-matter` (front matter). All four are widely used. They render to React, so `YouTubePlayer` and the site's own styles plug in directly.
  - MDX was not chosen: authors would have to write JSX, and its errors are harder to read.
  - Block syntax: `::figure[Caption]{src=… alt=…}`, `::video[Caption]{src=… poster=…}`, `::youtube[Caption]{id=…}`. The renderer's checks (media, alt, footnotes, headings `##`/`###` only, no bare `![…](…)` images) run as the page builds.
  - A static export needs at least one page per dynamic route, so before the first post (and while the list fits on one page) a stand-in at `/blog/_/` (and `/blog/page/_/`) renders the not-found page: `noindex`, linked from nowhere, not in the sitemap.
- **Checks that fail the build on a broken post:**
  - A required field is missing or a date is invalid.
  - A media file the post refers to is missing.
  - A figure has no `alt`.
  - Two posts have the same slug.
  - A footnote is used but never defined, or defined but never used.
- **Writing guide (`frontend/content/blog/README.md`):** it stays in the repo and is not part of the site; the post loader skips it _(human decision, 2026-11-09)_. It covers:
  - Where files go, the front matter, and every element with a copy-paste example.
  - Rules for media: our own images and recordings only, sizes, formats and alt text.
  - How to preview a post locally (`npm run dev`) and how to publish one (branch, commit type, release).
  - It links to an example post that uses every element. That post doubles as the test fixture (`frontend/src/lib/blog/fixtures/every-element.md`), so the guide's examples are known to render.
  - The test posts (the example and ten short ones, so two list pages) and their media (made from the team's art) live in `src/lib/blog/fixtures/`. The E2E build reads them instead of `content/blog/` (`BLOG_CONTENT_DIR`, `BLOG_MEDIA_DIR`) and copies their media into `out/`, so nothing of them ships.
- **Media rules:**
  - Videos must be the team's own material: screen recordings, animations, talks. Never clips downloaded from YouTube (`CLAUDE.md`, Public repository); a YouTube video is embedded instead.
  - Videos: MP4 (H.264), at most 10 MB each, with a poster image.
  - Images: WebP or PNG, at most 2× their display width.
  - Images and figures come from the team (`CLAUDE.md`).
- **Search and previews (plan 011):**
  - Every post is its own static page with:
    - title "<post title> - HyperStim?"
    - meta description: the post's `description`, or its TL;DR if none is set; at most 155 characters, checked in `metadata.test.ts`
    - canonical URL
    - Open Graph tags (`og:type` article, published date) with the site's share image
  - `/blog/` and every post go in the sitemap, each post with its date as `lastModified`.
  - Each post also gets `BlogPosting` structured data (JSON-LD: headline, date, description), which lets Google show the date in results.
  - Everything is in the built HTML, so readers that don't run JavaScript get the full post.
  - Every post uses the site's share image; posts don't set their own _(human decision, 2026-11-09)_.
- **Blog page description:** "Research, insights, and real-world examples exploring how kids’ videos use editing, motion, colors, and sound to create different viewing experiences." (150 characters) _(human decision, 2026-11-09)_. Title "Blog - HyperStim?". Added to plan 011's Page descriptions table.
- **Before the first post:** the Blog tab ships, and the list shows a message box (`rounded-2xl bg-sky p-6 text-center`): "No posts yet. Check back soon." _(human decision, 2026-11-09)_.
- **Drafts:** a post in progress lives on an unmerged branch and is previewed locally with `npm run dev`. There is no `draft` field _(human decision, 2026-11-09)_.
- **Privacy policy:** no change expected.
  - Figures and videos load from our own site.
  - YouTube embeds use `YouTubePlayer`, which the policy already covers ("When you play a video, YouTube may set cookies…").
  - Step 9 re-reads the policy to confirm it doesn't name the pages where videos play.
- **Commit types:**
  - Building the blog is `feat`.
  - Each new post is `feat: Add the blog post "<title>" (plan 018)`: new text visitors can read, so it gets a release note and a minor version.
- **Style:** `STYLE.md` gets entries for the Blog list page, the post page, the TL;DR box, figures and captions, references and the newer/older links. These reuse the existing surfaces (section card, butter panel, text link, video preview); there are no new tokens.

## Steps

1. Add the dependencies (`react-markdown`, `remark-gfm`, `remark-directive`, `gray-matter`), then update `package-lock.json` and `frontend/README.md`.
2. `src/lib/blog/` loader: read `content/blog/*.md` (skipping `README.md`), check the front matter and media, sort newest first, and give each post its newer/older neighbor.
   - Unit tests cover each failing check, the sort order, the neighbors at both ends, caption numbering and footnote numbering.
3. Renderer (`components/blog/PostBody.tsx`): map markdown and the `figure` / `video` / `youtube` blocks to the site's elements (automatic numbering, captions, `YouTubePlayer`), with footnotes shown as `[1]` and a References section.
   - Component tests use the every-element fixture, including the ↩ links and an axe check.
4. `src/app/blog/page.tsx` (list, page 1), `src/app/blog/page/[page]/page.tsx` (pages 2 and up) and `src/app/blog/[slug]/page.tsx`, all with `generateStaticParams`, with metadata from `pageMetadata` (the article type and date added to the helper) and JSON-LD.
   - Paging: move `Pagination` from `components/rankings/` to `components/` (two uses now) and give it a link mode (`href(page)` in place of `onChange`; disabled steps become `aria-disabled` spans). Rankings keeps the button mode.
   - Component tests check: newest first, the row link, 10 per page, the page control's links and current page, no control with 10 posts or fewer, and that the newer/older links appear only when those posts exist.
5. Header: add Blog before About, and mark it current on `/blog/…`; update the header test. Update plan 001's nav line.
6. Sitemap: add `/blog/`, its later pages and each post. Extend the sitemap and metadata tests to check the posts, the description length and the canonical URL.
7. The writing guide (`content/blog/README.md`) and the every-element fixture.
8. E2E spec (`e2e/blog.spec.ts`):
   - list → post → older → newer → All posts
   - list page 1 → Next → page 2 → Previous, with fixture posts that make 2 pages
   - the YouTube embed loads only after Play
   - a citation jumps to its reference and back
   - axe, the keyboard path, and 320 px reflow on both pages
   - the no-JavaScript check on `/blog/` and on a post
   - Safari check: the post page's video and the newer/older grid.
9. Re-read the privacy policy against step 3 (expect no change). Add the `STYLE.md` entries. Add plan 011's description row and sitemap line.
10. Screenshots at 360 and 1280 px next to the header and footer, compared with `STYLE.md`. Then a manual keyboard and screen reader pass, and a check on a real iPhone.
11. The first real post comes from the team. Until then, the site ships with no posts, and the list shows the "No posts yet" message. The E2E spec runs against a test post (fixture) so the post page is covered anyway.

## Review decisions

- 2026-11-09: In the layout mockup, the intro line under "Blog" is gone, the kid is removed from post pages, the dividers between posts are straight, and the list and post use the full width (artifact round 2).
- 2026-11-09: In the layout mockup, `kid_notebook` replaces the stand-in, post titles fill the full width, and reference numbers are gray (artifact round 3).
- 2026-11-09: In the layout mockup, the newer / older links sit under the same thin line as References, with no fill (artifact round 4).
- 2026-11-09: In the layout mockup, the newer / older links stack left-aligned on phones (artifact round 5).
- 2026-11-09: In the layout mockup, the list has 10 posts per page with the page control under it, plus a page 2 view (artifact round 6).

## Open questions

None.
