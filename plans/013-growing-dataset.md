# 013 — Growing dataset

**Area:** The dataset's growth: which videos are added, how they are collected and measured, how the API serves them, and how the site shows that the dataset keeps growing.

## Goal

Turn the fixed dataset (16,375 videos, 542 channels, 2015 to August 2026) into one that keeps growing, slowly and steadily, so that:

1. it doesn't stop at August 2026: new uploads keep coming in;
2. coverage gets deeper: more videos per channel and year over the years we already have, and channels that are new to us;
3. visitors see the count going up, so the site feels current.

The research repo's v2 curation is the starting point: choose channels, then draw a random sample of their eligible uploads. The updates build on v2's picks; unlike v2 they take no fixed number per channel and year (1).

## What v2 did (the research repo, read-only)

- **Channels:** YouTube Data API channel search on 36 queries in 5 categories; kept channels with ≥ 10K subscribers and > 100 videos, not auto-generated ("- Topic"). 646 passed, 542 ended up with at least one video. Tier set by subscriber count at discovery.
- **Uploads:** each channel's full upload list from the Data API (uploads playlist; 696,121 uploads for about 16,000 quota units). yt-dlp's flat listing was rejected: it has no dates.
- **Draw:** per channel × publication year (2015 onwards), a shuffle seeded by the channel ID; candidates checked in shuffled order, the first 5 that pass are kept ("share k" = the k-th kept video, so shares 1..k form a k-per-year dataset).
- **Eligible:** made for kids; 2–60 minutes (120–3,600 s); not a Short (a 120–180 s video is probed at `/shorts/<id>`); still online and not blocked in the US. About 44 % of uploads pass. No language or view filter.
- **Category:** a keyword classifier on title, then tags, then description (`63_classify_categories.py`), after sampling.
- **Download limit:** with no cookies, YouTube blocked the IP after about 300 clips in an hour (every request: "Sign in to confirm you're not a bot"), then lifted the block after about 2 hours (once 8 hours). Effective rate at full speed about 100 clips/hour. A different IP got through at once; machines in the same data-centre subnet may share one allowance.

Two consequences:

- **There is no shortage of videos.** About 300,000 eligible uploads exist for the current channels alone, against our 16,375. At the pace below (150/day) that's years of growth, so we choose a slow, steady pace on purpose and never need to rush.
- **New uploads alone grow slowly**: a few a day at first. Visible growth comes mainly from deeper coverage of the years we have, and new channels.

## Decisions (proposed)

### 1. Which videos: one sampling rule

- **Each upload gets a fixed random number** `r` in [0, 1): the first 8 bytes of `sha256("hyperstim-sample-v1:" + video_id)`. Everyone can recompute it, it never changes, and it doesn't depend on what else the channel uploaded or when we looked. (v2's shuffle reshuffles the whole year whenever the year's upload list changes, which is why it can't handle a year that's still running.)
- **Every eligible upload gets the same chance; no number per channel-year** _(human decision, 2026-10-26: scores are defined by the v2 reference set (4), so the dataset's mix doesn't change what a score means)_. The dataset is v2's picks plus every eligible upload (2015 onwards, every channel) whose `r` is below a cut-off `t`. The collector raises `t` slowly (150 videos a day, 7), so the dataset grows by an even random slice of all uploads: each channel and year in proportion to how much it uploaded. Raising `t` only adds; nothing already in is taken out.
- **The updates build on v2's picks** _(human decision, 2026-10-26)_: they stay, and count as the lowest numbers in their channel-year. v2 took 5 per channel-year whatever its size, so small channel-years stay over-represented until `t` catches up with them; that fades as `t` rises.
- **The running year needs no rule of its own.** Whether a video is in depends only on its own `r` and `t`, not on what else the channel uploads, so a video from December has the same chance as one from January, and nothing waits for a year to end. (This replaces the first draft's per-year rate and January close-out, which only existed to hit a number per year.) Each new upload is checked once it's a day old _(human decision, 2026-10-26: 3 days was longer than needed)_ and is in if `r < t` and it's eligible; the dataset is only a day or two behind YouTube.
  - **Why wait a day:** the wait doesn't affect who gets picked (that's `r`), only how fresh the dataset is. It lets the things settle that would otherwise waste a download: a scheduled premiere or live stream is listed before it can be watched (and a live stream's length is only known once it ends), and uploads are often deleted, made private or re-uploaded soon after they go up. A premiere or stream that still hasn't finished after a day is checked again the next day.
- **Years:** 2015 onwards, as v2 (YouTube Kids' launch). The range grows forward by itself; no earlier years.
- **Busy channels will make up a growing share of the dataset.** Uploads are very unevenly spread (v2's upload lists, 2015–2025: 4,155 channel-years, 601,256 uploads, ~44 % eligible):

  | Uploads per channel-year | median | 75th pct | 90th | 99th | max |
  |---|---|---|---|---|---|
  | | 77 | 174 | 332 | 1,077 | 6,148 |

  The 100 busiest channels (of 644) made 52 % of all uploads. Scores don't change with this (4); the video rankings will show more of the busy channels over time. `hyperstim-collector status` shows the share of the dataset from the 100 busiest channels.
- **The next reference set is drawn evenly** _(human decision, 2026-10-26)_: when the percentiles are someday defined by a new, larger set (4), that set is drawn from the dataset as an even sample (e.g. the same number per channel-year), not the whole dataset with its lean towards busy channels.

### 2. In what order

The collector always works on the highest-priority job first:

1. **New uploads** under `t` (a few a day, more as `t` rises).
2. **New channels** (3): their uploads under `t`.
3. **Raising `t`:** the eligible upload with the next lowest `r`, over all channels and years at once. Because `r` is random, this spreads evenly over channels and years by itself.

### 3. New channels

- **Re-run v2's discovery every week** _(human decision, 2026-10-26)_: the same 36 queries (one page each, as v2) and the same rules (≥ 10K subscribers, > 100 videos, not "- Topic"), tier from subscribers at discovery. A search costs 100 quota units, so the queries are spread out: 6 a day, so all 36 run every 6 days, each query at least weekly (~600 units/day, see 7). New channels that pass are added automatically; the date each channel joined is recorded. (Daily would fit the quota, but search results barely change from day to day.)
  - **Near misses, monthly:** channels the searches found but that were under 10K subscribers or 100 videos are re-checked once a month with `channels.list` (1 unit per 50 channels), so a channel that grows past the bar is added even if search stops showing it.
- **Discovery is the only way in** _(human decision, 2026-10-26)_. Channels people check on the site are never added; that would make the dataset lean towards what our visitors watch.
- **What people look up, as a guide for what to expand next** _(human decision, 2026-10-26: keep track of it)_: counted and kept on the server for the team (plan 014: live checks, channel lookups and searches for things we don't have). It's for us to read, e.g. to add a search query that finds such channels; it never adds anything by itself.
- A channel is never removed. If it's taken down, its videos go offline and are handled like any other (5).

### 4. Scores stay comparable: a fixed reference set

Today a score is a percentile within the dataset. If that dataset grows every day, every score shifts a little every day: a video that was 72 yesterday is 73 today, shared compare links change, and by plan 010's rules scores would "change meaning" with every new video.

- **Score everything against a fixed reference set** _(human decision, 2026-10-26)_, the v2 dataset (16,375 videos). New dataset videos and live checks are scored against it exactly as live checks are today. A video's score never changes; rankings change only because new videos slot in.
- **Update the reference set when the distribution shifts** _(human decision, 2026-10-26)_. To see a shift, `hyperstim-collector status` shows the average score and the share in each fifth (0–20, …, 80–100) of the videos added since v2; for a sample like the reference both stay near 50 and 20 %. Updating it is a deliberate major release with a note, as plan 010 already says.
- **Copy** (plan 006): the score lead "more intense than 74 of every 100 videos in our dataset" becomes "… of every 100 videos we compare with", and a new FAQ: "Do scores change as the dataset grows? No. Every video is compared with the same set of 16,375 videos from 2015 to August 2026, so its score stays the same. If we ever update that set, we'll say so."
- Channel scores still change as a channel gets more videos (the mean of more videos). That's intended: the estimate gets better.

### 5. Videos that go offline: taken out and replaced _(human decision, 2026-10-26)_

- Every dataset video is re-checked with the Data API once a month (spread over the days, ≈ 1 unit per 50 videos). Deleted, private or blocked in the US → taken out of the dataset (v2's rule). The site would otherwise show players that don't play. Nothing replaces it: with no number per channel-year there's no count to restore, and the sample is still "every eligible upload under `t`" _(follows from the 2026-10-26 decision in 1; the earlier "take out and replace" was for a fixed number per channel-year)_.
- The reference set is not changed by this (scores stay put).
- So the count can dip slightly; net it keeps going up. A visitor never sees it go down on an open page (9).

### 6. How it runs: a collector service

- **A separate process** (`hyperstim-collector`, its own systemd service), not inside the API: the API stays a single, light web process, and a collector crash or slow download never touches visitors. Same repo, same release, same `.venv`; it reuses the live analysis's pipeline wrapper (`analysis.py`'s `Pipeline`), so a dataset video is measured exactly like a live check (ffmpeg 6.1.1, `CACHE_VERSION` 11, the unchanged pipeline scripts).
- **State in one SQLite file** (`collector.db` in the instance's `data/`; Python's built-in `sqlite3`, no new dependency): channels, the upload lists (~700K rows; too many for TSV files), each upload's `r` and eligibility, samples, measurements, and one row per download attempt and its outcome.
- **The API reads a TSV the collector writes**, not the database: after each finished video the collector rewrites `collected.tsv` (same columns as `videos.tsv`, plus `added_at`) and `removed.tsv`, atomically (write, then rename). The API checks their modification time every 5 minutes, builds the new dataset in the background and swaps it in. The API's loader barely changes, and the collector could move to another machine with a plain file copy.
- **One download at a time, never at the same time as a live check**: before each download the collector looks in `ANALYSIS_DIR` for a waiting or running live job and waits. Measuring runs on **at most 1 core** _(human decision, 2026-10-26: the server also runs other research and the site)_, at low priority (systemd `CPUQuota=100%`, `Nice=10`, low `CPUWeight`, so anything else on the server goes first). Measured on this server: a full 5-minute clip takes ~29 s on one core at `nice 10` and ~200 MB of memory, so 150 a day is ~75 minutes of one core a day (~5 % of a core on average). Downloads use the network, not CPU.
- **Clips are kept on the clips volume** _(human decision, 2026-10-26)_, in their own folder, next to the v2 clips and never inside or mixed with them: `clips/` for the mp4s and `cache/` for the pipeline's per-clip `.npz` files. The path is set on the server (`COLLECTOR_CLIPS_DIR` in `server.env`, never in the repo); `setup.sh` creates the folder for the service user and the systemd unit may write only there and in `data/`. Keeping them means a future feature set can be measured again without downloading, which is the scarce part. Size: ~13 MB a clip (v2: 212 GB for 16,375), so ~2 GB a day at 150/day, ~0.7 TB a year; the volume has ~1.7 TB free, so `status` shows the free space and the collector pauses below 50 GB. Live checks' clips are still deleted after measuring (unchanged; the privacy policy says so). These clips are never served or committed, like all clips.
- **No cookies, no proxies** (the research rule: signing in risks the account and is a human decision; a proxy would be a third party).
- **Provenance per video**: rule version, `r`, the cut-off `t` when it was picked, whether it was measured by the collector or taken over from a live check, yt-dlp and ffmpeg versions, pipeline commit (with "+changes" if the pipeline folder had uncommitted changes), `CACHE_VERSION`, added date. Kept in the database and the exported files; the API exposes only `added_at`.
- **The cut-off `t`** is the highest number the sampling has checked. v2's picks don't count towards it, also when they're taken out later: their numbers played no part in how they were picked.
- **Live results are reused**: if a picked video was already checked live (same pipeline version), its features are taken over without downloading again. A live check never puts a video into the dataset by itself, though: that would bias the sample towards what visitors check.
- **Dev:** off unless `COLLECTOR_*` env vars are set; without `collected.tsv` the API serves the fixed dataset exactly as today.

### 7. YouTube's limits

Two separate limits: the **Data API quota** (listing uploads, video details, channel search; per Google Cloud project) and **downloads** (yt-dlp; YouTube blocks the IP).

**Data API quota.** 10,000 units a day per project, reset at midnight Pacific time; a search costs 100 units, every other call we use (`playlistItems.list`, `videos.list`, `channels.list`) 1 unit per page or per 50 IDs. More quota only through YouTube's compliance audit. YouTube's developer policies also say:

- **One API project per client** (III.D.1.c). The site is one client, so the collector **shares the live check's project and key**; no second project to get more quota (the first draft proposed one; v2's rotation of several keys isn't an option for us). The budget below keeps the two apart instead.
- The policies also limit storing API data to 30 days (III.E.4.d). **We don't apply that limit** _(human decision, 2026-10-26: titles, channel names and dates are publicly visible on YouTube)_: upload lists and details are kept, and updated only by the daily new-upload check and the monthly offline check (5).

| Use | Units a day |
|---|---|
| Live checks (existing cap: 1,000 new checks a day, 1 unit each; usually far fewer) | ≤ 1,000 |
| New uploads: each channel's newest page of uploads, daily (~650 channels) | ~650 |
| Details of new uploads (eligibility, ~160 uploads a day in batches of 50) and of picked candidates | ~20 |
| Monthly offline check of dataset videos (16K now, ~50K later) | ~10–35 |
| Discovery (36 searches a week, 3), plus near misses monthly | ~550 |
| **Total** | **~2,250 at most** |
| Once, at the start: the full upload lists (~700K uploads), spread over 3 days | ~5,500 |

- **The collector stops its Data API work at 7,000 units a day**, so at least 3,000 are always left for live checks, and pauses until the reset if YouTube says the quota is used up.
- **New uploads are checked every day** _(human decision, 2026-10-26)_: ~650 units a day (6.5 % of the quota), a few `/shorts/` probes, and a few downloads a day.

**Downloads.**

- **150 videos a day** _(human decision, 2026-10-25; kept 2026-10-26)_, spaced at random (on average one every ~10 minutes, never two at once). That is ~6 an hour, about 2 % of the rate that got us blocked, and spread over the whole day instead of a burst. ~1,000 more videos a week: enough that a weekly visitor sees a clearly bigger number, and the eligible pool lasts for years.
- **The pace is our choice, not a limit we hit.** There are years of videos to collect and the server has CPU to spare, so the only thing that changes with pace is how fast the dataset grows against the risk of a block. It stays at 150 and changes only by hand (`COLLECT_PER_DAY`, env var), e.g. if we want the dataset to grow faster. No automatic ramp-up _(changed from the first draft's ramp to 400/day: an automatic ramp would only raise the risk without a reason)_.
- **Block detection**: the error text "not a bot" (matched in the full stderr; age-restricted videos say "confirm your age", which looked the same in v2's cut-off logs) → stop downloading, wait 6 hours, try one video; still blocked → double the wait (up to 2 days) and halve the pace. Age-restricted, private or region-blocked → that video is skipped and the next by `r` is picked.
- **Also when the live check is blocked**: the live analysis writes a `youtube-blocked` marker file with the time; the collector honours it like its own block. The live check never waits for the collector.
- **Status**: `hyperstim-collector status` (count today/this week, pace, queue by priority, last block); `GET /api/meta` shows when the last video was added, so a stalled collector is visible.

### 8. On this server

- **The collector runs on this server** _(human decision, 2026-10-26)_, at 150/day with the safeguards in 7. At ~2 % of the observed block rate and with no bursts, a block is unlikely; the collector stops at the first sign, and the logs then tell us the real limit.
- A second, small instance was weighed: it would keep live checks working during a collector block, but only if YouTube blocks per IP and not per subnet (unknown; a second instance in the same cloud likely shares the subnet), and it's a second server to set up, patch and secure, with results copied over. If blocks ever happen at this pace, moving is cheap: the collector's only output is two TSV files.

### 9. Showing the growth

- **Exact counts, not "16k+"**: a rounded number hides the growth.
- **Home hero: videos, channels, and the past week** _(human decision, 2026-10-25)_: "Explore and compare **16,402** videos from **542** channels to better understand what your child is watching." and under it, on its own line, the pill "**+1,043 videos in the past week**" _(human decision, 2026-10-26: after the sentence's two numbers, a bare "+1,043" read as unclear)_. The channel count is new on the home page _(human decision, 2026-10-25)_. The pill is on the home page only _(human decision, 2026-10-25)_. It counts the last 7 days, today included, in the visitor's time zone (not since Monday, so it never drops to a small number at the start of a week) _(human decision, 2026-10-25: counted in days)_: the same window as its link, so the pill's number and the list it opens agree _(human decision, 2026-10-26)_. It takes its number from the rankings' total for that filter (`GET /api/videos?addedFrom=…&limit=1`). It says "in the past week" _(human decision, 2026-10-26: "the last 7 days" was one number too many)_.
- **The pill links to the new videos** _(human decision, 2026-10-26)_: `/rankings?q=added:>{the date 7 days ago}`, so the rankings open with `added:>2026-10-19` in the search box and list only the videos added since (plan 007, Search filters). On hover its fill deepens; no underline, no arrow _(human decision, 2026-10-26: an underline didn't fit the pill; the blue pill alone says it's clickable)_.
- **The pill's colour: `bg-sky` with `navy` text** (the pastel blue of How it works ④'s panel, ≥ 6 : 1), `rounded-full`, `text-sm font-bold`, not green _(human decision, 2026-10-25: green would bring in a new colour)_. `STYLE.md` gets it as a surface.
- **Rankings page: no growing count** _(human decision, 2026-10-26)_. The results line ("Showing 1–25 of 16,402 videos") is the count: it stays put while the visitor is on the page (see No surprises while browsing) and is current at every page load, also when arriving from another page of the site, so it matches the home page's number. For channels it says the 5-video minimum ("… of 510 channels with 5+ videos"; with a category "… of 120 channels with music videos (5+ videos each)"), so it adds up with the home page's channel count, which counts every channel _(human decision, 2026-10-26: 544 on home vs 510 in the rankings looked like a mismatch)_. Plan 007's results line changes with it.
- **The animation** _(human decision, 2026-10-25: option A on load, option B on arrival, from the options artifact)_:
  - **On page load (A):** the sentence and the pill are on the page from the first paint, with skeleton bars where the numbers go, so nothing swaps or pops in _(human decision, 2026-10-26: a placeholder sentence, then the numbers, then the pill made the features look patched on)_. When the counts arrive, all three start counting up together from their value 7 days ago to today's, ease-out (the score gauge's motion), **at the same speed**: the one with the longest way to go takes 1 s, the others take less in proportion (a rise half as large takes 0.5 s), but at least 0.3 s, so a small rise like the channels' few still visibly counts _(human decision, 2026-10-27: 1.5 s made the numbers feel slow to load)_. Videos count from `videoCount − addedLast7Days`, channels from 7 days ago, the pill from 0. Only if the counts can't be had does the sentence say "thousands of" and the pill go.
  - **When a new video arrives while the page is open (B):** the changed digits roll, odometer style (~0.9 s), in the video count and in the pill (and the channel count when a channel is added). The page checks `GET /api/meta` every 60 s while the tab is visible. At 150/day a visitor sees a roll every ~10 minutes, so few will, which is why the pill carries the growth on every visit _(human decision, 2026-10-25)_.
  - **"In the past week" is a moving window**, so on its own it would sometimes go down (when a busy day falls out of it). Visitors never see that: on an open page the counts only ever roll up, by the number of videos added since the page loaded; anything that would lower a number (the window moving on, a video going offline) shows only at the next page load, where the pill counts up from 0 anyway _(human decision, 2026-10-26: digits rolling down would confuse)_.
  - Only real numbers from the API; nothing is faked or extrapolated between checks. With `prefers-reduced-motion` the numbers change without counting or rolling (the site's existing rule, `STYLE.md`'s score gauge). Screen readers get the plain number once (the moving digits are `aria-hidden`, an sr-only copy holds the value; no `aria-live`, so nothing is announced every minute).
- **No surprises while browsing** _(human decision, 2026-10-26)_: new videos only make the counts roll. Rows never appear, disappear or change rank on a page someone is looking at; that happens at the next page load.
  - The rankings page (and the compare page's pickers, which search the same lists) remembers the dataset's time from its first answer and sends it as `asOf` with every later request (next page, sort, filter, search). The API then answers as the dataset was at that time: it leaves out videos added after it and keeps ones removed after it, and works out channel scores from those videos. Because scores never change (4), that is exactly what the visitor saw before, so page 2 continues page 1 without skipped or repeated rows.
  - The time lives in the page's memory only, not the URL, so a shared or reloaded link shows the current rankings.
  - Removed videos stay in the API's memory with the time they were removed, so it can answer for earlier times. Their own pages show them as no longer available, as for any video YouTube took down.
  - The rankings' results line ("Showing 1–25 of 16,375 videos") belongs to the table, so it stays put too.
- **API, additive** (`GET /api/meta`): `videoCount` and `channelCount` (already there, now growing), `addedLast7Days` (the pill's "past week"), `channelCount7DaysAgo`, `lastAddedAt`, `referenceCount` (16,375), `channelsCheckedAt` (last discovery run).
- **How it works ③** (plan 006): "(at our latest scan, August 2026)" becomes the date of the last discovery run, from the API; "Pick a few at random, every year" stays true, and box 4's "the same share from every year of every channel" becomes exactly true (one `t` for all). "We keep adding videos" can go in the dataset box (copy in plan 006).
- **A new common question** (How it works, plan 006) _(human decision, 2026-10-25)_, after "How is a channel's score worked out?":
  - **Q:** How do you choose the channels and videos?
  - **A:** We look for kids' channels on YouTube that have at least 10,000 subscribers and more than 100 videos, leaving out channels YouTube makes automatically. From each channel, we pick videos at random from everything it has uploaded since 2015, so every video has the same chance, popular or not _(wording updated 2026-10-26 for the sampling decision in 1)_. Every video we pick must be made for kids, 2 to 60 minutes long, not a Short, and still online. We keep adding new channels and videos.
  - It names no numbers per year _(human decision, 2026-10-25)_. "More than 100" is v2's actual rule (`video_count > 100`); "100+" in How it works box 1 says the same in short.

### 10. Data in the repo and backups

- `backend/data/videos.tsv` stays the v2 dataset, now also the reference set. It doesn't change.
- **Every addition is recorded on the server** (`collector.db`, with a daily SQLite backup kept 7 days) **and committed daily to this repo as a second copy** _(human decision, 2026-10-26: daily, not monthly; a separate safeguard and the record of what was added)_, **next to the v2 list in `backend/data/`** _(human decision, 2026-10-26: no second repo to maintain)_.

**Live without releases.** The site never waits for the commit:

- The prod API reads the collector's files in the instance's `data/` folder (`COLLECTED_DIR`), reloaded every 5 minutes (6), not the copy in the repo or in the release checkout. A new video is on the site within minutes, with no commit, release or deployment.
- **A reload builds a whole new dataset** off to the side (sorted rankings and ready-made ranks, plan 007) and swaps it in at once; requests keep using the old one until then.
- **The loaded dataset is kept out of Python's garbage collector** _(human decision, 2026-10-27: its full passes over the dataset's ~474k objects took ~250 ms each, freed nothing, and delayed random requests by 150–190 ms)_: after the first load and after each swap, `gc.freeze()`, so the collector's passes skip it. It costs no memory: the dataset is freed by reference counting when it's replaced (checked: all of it, with nothing left for the collector). Before each swap's freeze, `gc.unfreeze()` and one `gc.collect()` in the reload thread, as a safeguard should the dataset ever hold reference cycles; that one pass (~250 ms) is the only pause left, once per reload.
- The daily commit is only the record and the backup. A release changes nothing about which videos are served.
- Dev reads the committed copy (`COLLECTED_DIR` = `backend/data/collected/` in `.env.example`), so a fresh clone shows the dataset as of the last daily commit.

**The files** (append-only, so each day's diff is just the new lines and git stays small):

- `backend/data/collected/<year>.tsv`: the added videos, in the order they were added, one file per year of adding (~45 KB a day, ~16 MB a year). Same columns as `videos.tsv`, plus `added_at` and the provenance (6).
- `backend/data/collected/removed.tsv`: videos taken out (5), with the date.
- `backend/data/collected/CHANGELOG.tsv`: one line a day with a change: date, videos added, removed, channels that got their first video, and the totals (videos, channels) at the end of the day. Written by the collector with the other files; the release notes read its last line.
- `backend/data/collected/meta.json`: the date of the last full discovery run (How it works ③).

**The daily commit:**

- **Who:** a git identity for the job ("HyperStim data bot"), no GitHub account. It pushes to `main` with a **deploy key** of this repo, held by its own system user (`<data-user>`) and run by a systemd timer once a day. The collector service, which parses downloaded videos, never sees the key.
- **How:** its own clone (in `<prod-dir>`, separate from `repo/` and the dev checkouts), checked out at `origin/main`; copy the day's lines in, commit only `backend/data/collected/`, push. If someone pushed in between: fetch, rebase, push again (no conflicts, since only the bot writes those files).
- **Message:** `data: Add 151 videos and 1 channel, remove 2 (2026-10-27)`. No plan suffix, and no server details anywhere in the files.
- **Guard rails**, because a key that can push to `main` could push anything:
  - In GitHub, a tag ruleset lets only admins create `v*` tags (deploy keys aren't exempt), so the key can't start a deployment. If `main` gets branch protection later, the deploy key is added as its only bypass.
  - CI fails a `data:` commit that changes anything outside `backend/data/collected/`.
  - `release.sh` refuses to release if any `data:` commit since the last release changes another path, so a stray code change can't ride out with a release.
- **CI** runs once a day on the bot's push (fine, _(human decision, 2026-10-26)_).

**Release notes and versions** (plan 010's `release.sh` and `scripts/release-notes.sh`):

- **A new commit type `data`**: added to `CLAUDE.md`'s commit rules (what it's for: the bot's daily dataset commits only) and to the `commit-msg` hook.
- `data:` commits **don't bump the version and aren't listed** in the notes. Instead the notes get one line, from the files: "Dataset: 16,375 → 21,402 videos, 542 → 560 channels since v1.3.0." So releases stay about the code, and the growth shows up once per release.
- With only `data:` commits since the last release, `release.sh` says there's nothing to release and stops (nothing would change on the site anyway).

### Privacy policy (plan 009)

No change needed for the collector: it handles no visitor data; it only talks to YouTube from our server, as live checks and thumbnails already do; the clips it keeps are of videos it picked itself, not ones a visitor checked (whose clips are still deleted, as the policy says); new dataset videos' thumbnails go through the existing endpoint. Checked again at build time. (A second instance would also be "us"; still no change.)

### Effects on other plans

- 001: the dataset is no longer fixed; usage counts (plan 014); the collector service; scores against a fixed reference set; "downloaded clips are deleted once analysis finishes" becomes true for live checks only (the collector's are kept on the clips volume).
- 002: the hero sentence gains the channel count and the last-7-days pill, all animated.
- 007: the animated video count under the intro; `asOf` keeps the table steady while browsing.
- 008: the pickers send `asOf` too.
- 006: score lead copy, two new common questions (scores don't change; how we choose channels and videos), discovery date, dataset box.
- `STYLE.md`: the pill, and the count-up / rolling-digits motion.
- 010: `release.sh` and `release-notes.sh` treat `data:` commits as above; the tag ruleset for `v*`; `setup.sh` installs the collector unit (1 core, low priority), its clips folder, the data bot's user, clone, deploy key and timer, `server.env` gets `COLLECTOR_CLIPS_DIR` and the pace, `release.sh` restarts both services. The shared API key's note ("a new analysis costs 1, prod caps at 1,000/day") gets the collector's share.
- `CLAUDE.md`: the `data` commit type; what's cleared to commit (`backend/data/collected/`); the collector next to the pipeline in "Dev environment".
- CI (plan 012): the `data:` path check.
- `backend/pipeline/`: add `63_classify_categories.py` unchanged (README table updated).

## Steps

**Local first** _(human decision, 2026-10-26)_: the collector is built and run on the dev checkout first: it collects for real (this server, 150/day, the dev API key, clips in their own folder on the clips volume) and the local dev site serves the growing dataset with the new frontend. Nothing is committed or pushed meanwhile, and no daily `data:` commits run: production gets the frontend change and the added videos only with the deployment (step 8). At the deployment the local `collector.db` and clips folder become prod's (moved, owned by the service user), so nothing is collected twice.

**The upload lists start from v2's** (research repo, `runs/contemporary-v2/catalogue-cache/`, copied read-only into `collector.db`; IDs and dates only), so collecting starts at once instead of after 3 days of listing; the daily new-upload check then pages each channel back to the last known upload.


Build (Claude; each on the plan's branch with lint, type check, tests and build passing):

1. **Review this plan** (and plan 014).
2. **Collector core** (`backend/src/hyperstim_collector/`): Data API client (uploads, metadata, discovery, monthly offline check; daily unit budget, resumable), the sampling rule (tests: nothing leaves as `t` rises, v2 picks kept, new uploads and new channels under `t`, same chance whenever in the year a video comes out), eligibility (v2's checks and Shorts probe), priority queue, SQLite schema.
3. **Measure and export:** reuse `Pipeline` from `analysis.py`; category via the copied classifier; atomic `collected.tsv` / `removed.tsv`; pacing, block detection and back-off, waiting for live checks; `status` command; the daily commit (bot user, timer, guard rails), `data` type in `release.sh`, `release-notes.sh`, the hook and CI. Tests with a fake downloader.
4. **API:** load base + collected − removed, score against the reference set, reload on file change without a restart; `asOf` on the list endpoints (tests: page 2 at an earlier time continues page 1 exactly, also across an addition and a removal); `meta` fields; the `youtube-blocked` marker from live analysis. Tests.
5. **Deploy (plan 010):** systemd unit and `server.env` values, `setup.sh`, `release.sh`, `deploy/README.md`; backups; the data bot's deploy key and the `v*` tag ruleset (by hand, a repo admin).
6. **First run on the server**, before any frontend change, with the API not yet serving the added videos (`COLLECTED_DIR` unset in prod): list all uploads (3 days of quota), then collect at 150/day for 2 weeks; check the block log, CPU use (1 core), measurement times, and that collected videos' features match a few re-measured v2 videos.
7. **Frontend:** exact counts, the count-up and rolling digits, up only (home: videos, channels, pill), polling `meta` while visible, `asOf` in rankings and compare pickers, `api.ts` types, How it works copy and the two common questions; `STYLE.md` gets the count's style; screenshots at 360/1280 px.
8. **Go live:** set `COLLECTED_DIR` in prod's `server.env`, then a release (frontend and backend together, by the team).
9. **Docs:** `backend/README.md` (collector, env vars, commands), `.env.example`, plans 001/002/006/007/010, `CLAUDE.md`.
10. **Faster numbers on the home page** (2026-10-27): the count-up at the same speed (1 s for the longest, at least 0.3 s; `RollingNumber` takes a duration, the hero works it out; `STYLE.md` Growing counts); `gc.freeze()` after each load (10, tests: a reload frees the old dataset); plan 007's step 8. Measure on the dev site before and after (time until the numbers settle), screenshots at 360/1280 px. Stop for review.

By hand (the team), in order:

| When | Who | What |
|---|---|---|
| Now | you | Review plans 013 and 014; answer 014's open question. |
| Before step 6 | a repo admin | GitHub → Settings → Rules → Rulesets → New tag ruleset: target `v*`, restrict creations, updates and deletions, bypass: repository admins only. |
| Before step 6 | you, on the server | Fill the new values in `deploy/server.env` (from `server.env.example`: the clips folder on the clips volume, the pace 150, the data bot's user), then `sudo deploy/setup.sh`. It prints the data bot's public key. |
| Before step 6 | a repo admin | GitHub → Settings → Deploy keys → Add deploy key: the printed key, "Allow write access" on. |
| Before step 6 | you | `hyperstim-release`: ships the collector (steps 2–5). Nothing on the site changes yet, since the API doesn't serve the added videos until step 8. |
| Step 6 (3 days, then 2 weeks) | you | Nothing to do; Claude reports the upload listing, then the trial (blocks, CPU, timing, features). Decide whether to go live. |
| Step 7 | you | Review the home and rankings pages (screenshots), the How it works copy (score lead, two common questions) and the privacy policy sentence (plan 014). |
| Step 8 | you | `hyperstim-release` (Claude never releases). |
| After | you | Check the first daily `data:` commit on GitHub and the counts on the live site. |

## Review decisions

Decisions made while building (2026-10-26), each in its spot above where it fits there:

- **Lists answer as of a version**: every list answer carries `asOf`, the time of the dataset's last addition or removal; before any, the reference set's date (`2026-09-01T00:00:00Z`), so a page can pin itself from the very first answer.
- **The count-up is shared**: `ScoreGauge`'s count-up moved into `lib/motion.ts` (`useCountUp`), used by the gauge and the new rolling number (`components/RollingNumber.tsx`). Each digit is a strip of 0–9 twice, so 9 → 0 keeps rolling up.
- **Pinning**: on the rankings page one pin is shared by the Videos and Channels views; each compare picker keeps its own.
- **How it works ③**: before the first full discovery run the scan date shows v2's (August 2026).
- **The first offline check takes out a few hundred v2 videos** (deleted or private since August), so the count dips below 16,375 for a couple of days before additions overtake it. This happens in the local run, before production.
- **Not yet built, for the deployment (step 5)**: the collector's systemd unit, the data bot's user, clone, key and timer, and the `setup.sh` / `server.env.example` / `deploy/README.md` changes. They change the server's users and permissions, so they're done with the team at go-live. Built and tested: `scripts/commit-data.sh` (the daily commit), `scripts/check-data-commits.sh` (CI and `release.sh`), the `data` type in `release-notes.sh` and the hook.

## Open questions

None. Usage counts: plan 014.
