# 009 — Privacy policy

**Area:** Privacy policy page (`/privacy`), cookie consent, and (later) analytics.

## Goal

Build `/privacy`: a short policy, in plain words, that says exactly what the site does with visitor data today. Also set out what changes once analytics are added, so that step is planned and doesn't need a rewrite.

## What the site does today (checked in the code)

| Where | What it sees or stores | Kept |
|---|---|---|
| GitHub Pages (hosts the pages) | IP address, browser, pages requested, in GitHub's own logs | GitHub's policy |
| Fonts | Self-hosted at build (`next/font`), so no request goes to Google Fonts | – |
| Our server (API) | Reverse proxy access and error logs: IP, time, URL requested, browser. The API itself logs no IPs (uvicorn's access log off in the app, see **Logs**) | 14 days |
| Live check, rate limit | IP address, in memory only, to allow 5 new checks per hour | ≤ 1 hour, never written to disk |
| Live check, results | Video ID, public video details, results. Nothing about who asked | Until removed by hand (plan 004) |
| Live check, the clip | Downloaded to our server for analysis | Deleted when the analysis finishes |
| YouTube thumbnails | Fetched by our server on each request (see **Thumbnails**), so YouTube never sees the visitor | Not stored on the server; the visitor's browser keeps each for a day |
| YouTube player | Loads only after "Play video" is clicked. Privacy-enhanced mode (`youtube-nocookie.com`). Once playing, YouTube may set cookies and local storage | Google's policy |
| Cookies, local storage | None set by us | – |
| Contact form (Google Form, linked) | What the visitor writes: reply email, request, optional IP/time | Deleted once the request is handled |

## Decisions

- **Plain words, short sections, for parents.** The same tone as How it works. No legal boilerplate beyond what the law requires.
- **Facts only, and kept true.** Each statement matches the table above. A change to any of these behaviours updates the policy in the same change (a rule added to 001).
- **"Last updated" date** at the top of the page.
- **Sections:**
  No "In short" summary box _(human decision, 2026-10-16)_.
  No "Who we are" section _(human decision, 2026-10-16)_: the policy names no team, and the contact link is in **Your choices**.
  1. **When you browse the site**: GitHub Pages logs, our server's logs (full IP addresses _(human decision)_, kept 14 days), and why: to run the site and keep it safe from abuse.
  2. **When you check a video**: what is saved (the video's ID, public details and results, kept and shown to anyone who checks it later); the IP held in memory for at most an hour for the limit; the clip deleted after analysis.
  3. **YouTube**: thumbnails come from our server, so YouTube doesn't see you while you browse (how long the server keeps them isn't stated _(human decision, 2026-10-16)_); the player loads only after you click, and then Google's privacy policy applies (link).
  4. **Cookies**: we set none. YouTube may, only after you start a video. One sentence on browser privacy signals: "We don't track you, so Do Not Track signals change nothing." _(human decision)_
  5. **Children**: the site is meant for parents and adults. We don't knowingly collect personal information from anyone, children included.
  6. **Your choices**: "To ask what we hold about you, or to have it deleted, please fill out the contact us form." _(human decision, 2026-10-16)_. No reply time and no hint about IP address and time (the form's IP and time fields cover it) _(human decision, 2026-10-16)_. Nothing on the form being run by Google, what we do with messages, or complaining to a data protection authority _(human decision, 2026-10-16)_.
  No "Changes to this policy" section; the "Last updated" date at the top stays _(human decision, 2026-10-16)_.
- **One policy for every visitor, with no jurisdiction named** _(human decision: visitors are mainly in the US, but anyone can visit)_. The text names no law and has no region-specific parts. Its content still meets the strictest common rules (EU/UK GDPR; in the US, California's CalOPPA and COPPA), which costs only a few plain sentences since we collect almost nothing:
  - what is collected, why, how long, who else sees it, the contact, a dated last update (all);
  - why we keep logs, said in plain words (security) (GDPR). GDPR also expects who runs the site, a reply time for requests and the right to complain to a data protection authority; left out _(human decision, 2026-10-16)_;
  - how Do Not Track is handled (CalOPPA, which applies once we collect emails through the contact form);
  - the children section (COPPA). The site is for parents, but its topic and picture-book style may make it look aimed at children. Today that's fine: IPs used only for security and rate limiting need no parental consent. **It matters for analytics** (below).
  - Not legal advice: if the team belongs to an institution, its privacy office should read the final text.
- **Logs** (checked on the server; details stay off the repo). The policy promises 14 days, so every log with visitor IPs must keep to that:
  - Reverse proxy access/error logs: already rotated daily and deleted after 14 days. No change.
  - This repo's backend: uvicorn's access log is turned off in the app itself, not by a `--no-access-log` flag on the server _(human decision, 2026-10-17: off by default)_; also off locally. The reverse proxy already logs each request, so it would only add a second copy, kept as long as the server keeps the service's output. The app's own log lines contain no IPs (checked). Tested; documented in `backend/README.md`.
  - The old site's live-analysis API is out of scope: this site runs on this repo's backend only _(human decision)_.
- **Thumbnails through our backend** _(human decision: no third party sees the visitor before they press play; also one fewer outside dependency)_. Changes plans 004 and 005, which loaded thumbnails from YouTube's image server.
  - `GET /api/thumbnails/{video_id}?size=hq|mq`: the backend fetches the image from YouTube on each request and stores nothing _(human decision, 2026-10-17: no prefetching, no server cache)_; the response has a 1-day cache header so the visitor's browser reuses it. The request to YouTube comes from our server, with no visitor data.
  - Only for videos the site knows (in the dataset or with a stored analysis); anything else is 404 without asking YouTube, so the endpoint can't be used to fetch arbitrary images. Unknown sizes: 422 (FastAPI's validation error).
  - If YouTube has no thumbnail: 404; YouTube unreachable: 502. Either way the frontend shows the image's grey box.
  - Frontend: `thumbnailUrl` moves from `lib/youtube.ts` to `lib/api.ts` (the one place that talks to the backend) and points to the endpoint (through `NEXT_PUBLIC_API_BASE`); every user (`YouTubePlayer`, `TimeChart`, `VideoStrip`) is unchanged otherwise.
  - Speed: one fewer outside host for the browser to connect to, but each image now goes through our one server (the fetch from YouTube takes about 40–90 ms), so first loads, especially far from the server, are a bit slower. The browser cache covers repeat views.
  - Tests: dataset/live/unknown ID, bad sizes and IDs, fetched on every request (nothing stored), a missing thumbnail → 404, YouTube down → 502.
- **Contact form** _(human decision: a Google Form)_: https://forms.gle/oLbWLgE8sT6zHhLR9, title "HyperStim? Support", a general contact form that also takes privacy requests _(human decision)_. Linked from the policy as "contact us" _(human decision)_, from the policy only, no footer link _(human decision)_; not embedded (no Google code on our pages); no Google sign-in; responses go to a team account checked at least weekly; each response deleted once handled. Fields:

  | Field | Type, required | Description shown in the form |
  |---|---|---|
  | (Form description) | – | "Questions, feedback, or requests about your data on the HyperStim? website. Please don't include anything sensitive. We reply within 30 days and delete your message once it's handled." |
  | Email address | Short answer, email validation, required | "So we can reply. We use it only for this request." |
  | What would you like to do? | Multiple choice, required: "Ask what data you hold about me" · "Delete my data" · "Ask a question about privacy" · "Report a problem" · "Give feedback" · "Other" | – |
  | Details | Paragraph, required | "Tell us what your message is about." |
  | IP address | Short answer, optional | "Only for requests about our server logs, which we can find only by IP address and time. We keep logs for 14 days." |
  | Date and time of your visit | Short answer, optional | "Roughly, with your time zone, e.g. 16 Oct 2026, 3 pm EST." |

  Form settings: "Collect email addresses" off (the field above does it without a Google account), "Limit to 1 response" off (needs sign-in), no file upload (needs sign-in).
- **No cookie banner until analytics** _(human decision: only if the rules require it only with analytics; checked, they do)_. This changes 001.
  - EU/UK rules (ePrivacy) require consent before a site stores or reads anything on the visitor's device, unless it is strictly needed for what the visitor asked for. We store nothing (no cookies, no `localStorage`), so there is nothing to ask about. US law has no cookie-consent requirement.
  - The YouTube player loads only after "Play video" is clicked (plan 004), so YouTube's cookies follow the visitor's own request (the usual "click to load" approach). The policy explains this in **YouTube** and **Cookies**.
  - With analytics, the banner and the footer's "Cookie settings" link become required (below).
- **The kid: `kid_quiet`** _(human decision)_: sitting cross-legged, finger on lips, winking ("we keep quiet about you"). Transparent background. Sits on the policy card's top edge at the hero's right, at the hero kids' head size (`w-54 lg:w-61 xl:w-72`, `STYLE.md`) _(human decision, 2026-10-16: looked smaller than on the other pages; its head is turned, so it's measured by head height, not eye distance)_. Added to `frontend/art/used.json`.
- **Page layout** (`STYLE.md`, Privacy page): the H1 and "Last updated", with the kid on the card's top edge; then **one section card holding all sections**, divided by lines (one card per section looked heavy for a text page). The text uses the card's full width _(human decision, 2026-10-16: `max-w-prose` left a third of the card empty)_. Anchors on each H2 (`#cookies`, `#youtube`, …), so other pages can link to a section. External links (GitHub, Google, the contact form) open in a new tab.
- **Links in:** footer "Privacy policy" (exists) and the FAQ answer "Do you keep anything about me?" (exists, plan 006).
- **No backend.** Static page.

## Later: adding Google Analytics

Adding GA changes the picture in four ways:

1. **Consent is required first.** GA sets cookies (`_ga`) and sends the visitor's IP, device and browsing to Google. For EU/UK visitors that needs opt-in **before** GA loads. US law needs no banner, but one banner for everyone is simpler than detecting location, and fits the one-policy rule. So 001's banner becomes necessary: Accept / Reject of equal weight, GA loads only after Accept, choice in `localStorage`, "Cookie settings" link in the footer to change it.
2. **The policy gains:** an **Analytics** section (what GA collects, Google as processor, retention, transfers to the US), a **cookie table** (name, purpose, duration), consent as the legal basis, and how to withdraw consent. **Cookies** loses "we don't set any cookies".
3. **Settings to choose then:** data retention (2 months, the minimum), Google Signals and ad personalisation off, data sharing off.
4. **Children (COPPA):** if the site counts as aimed at children (see **One policy**), GA's cookies need verifiable parental consent, which a banner can't give. Check this before adding GA; a cookieless tool avoids it.
5. **Do Not Track / Global Privacy Control:** honour GPC as a "Reject" (California treats it as an opt-out).
6. **Code:** the GA ID from `NEXT_PUBLIC_GA_ID`; when unset (local dev, forks, CI), no analytics code at all. The script is added only after consent, through one small consent module that the YouTube player can also read.

A cookieless analytics tool (self-hosted or EU-hosted) would avoid points 1–5: no banner, a one-paragraph policy change. Worth weighing when the time comes; this plan doesn't decide it.

## Steps

1. ~~Answer the open questions.~~ The copy is reviewed on the built page _(human decision: no separate copy review in the plan)_; the text lives in `PrivacyPage.tsx`.
2. ~~Build `/privacy`~~ (page, sections, anchors, kid); tests: headings and anchors in order, the contact link, the stated retention times (logs, the rate-limit count).
3. ~~Backend: the thumbnail endpoint~~ (`thumbnails.py`, README); the README's **Privacy** section (access log off, 14-day proxy logs).
4. ~~Update 001~~ (privacy page, no banner until analytics, the policy-stays-true rule, the thumbnail endpoint), 004 and 005 (thumbnails from our backend).
5. ~~Lint, type check, tests, build; screenshots at 360, 768, 1280, 1920 px.~~

## Open questions

None. Next: the final copy (step 1).
