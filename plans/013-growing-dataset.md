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
- **Every eligible upload gets the same chance; no number per channel-year** _(human decision, 2026-10-26: scores are defined by the v2 reference set (4), so the dataset's mix doesn't change what a score means)_. The dataset is v2's picks plus every eligible upload (2015 onwards, every channel) whose `r` is below a cut-off `t`. The collector raises `t` slowly (150 videos a day, 7), so the dataset grows by an even random slice of all uploads: each channel and year in proportion to how much it uploaded (plus each channel's floor of 5, below). Raising `t` only adds; nothing already in is taken out.
- **The updates build on v2's picks** _(human decision, 2026-10-26)_: they stay, and count as the lowest numbers in their channel-year. v2 took 5 per channel-year whatever its size, so small channel-years stay over-represented until `t` catches up with them; that fades as `t` rises.
- **At least 5 videos per channel, picked by the same `r`** _(human decision, 2026-10-29: with no 5-video minimum in the channel rankings (9), channels with 1 or 2 videos topped them on the strength of one high score; on 2026-10-29, 75 of 588 channels had fewer than 5, 45 of them 1)_. The dataset is every eligible upload under `t`, **plus each channel's eligible uploads with the lowest `r` until it has 5** (its "floor").
  - **The same videos, only sooner:** as `t` rises, a channel's uploads come in from its lowest `r` upwards, so the floor takes exactly the videos `t` would take first for that channel. Once `t` passes them they're ordinary picks; in the long run the dataset is the one the rule above builds.
  - **Spread over time as before:** a channel's lowest numbers are a random draw over its whole history, so its 5 are spread over its years in proportion to what it uploaded each year. A channel that only started recently gets recent videos, which is what it is. (Not one per year round-robin as v2: those aren't the videos `t` takes first, so the tilt would never fade.)
  - **Fewer than 5 eligible uploads:** the channel keeps what it has; each new eligible upload of it is taken, whatever its `r`, until it has 5.
  - **Counts as having:** its videos in the dataset (v2's picks included) and its eligible ones waiting to be downloaded. A channel that drops below 5 (videos gone offline, 5) is topped up again from its next lowest numbers.
  - **Small channels are over-represented for a while**, like v2's picks; scores don't change (4), and the next reference set is drawn evenly anyway.
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
3. **Filling the floor** (1) _(human decision, 2026-10-29)_: channels with fewer than 5, the fewest first, then each channel's lowest `r`. Their uploads are checked for eligibility in `r` order, ahead of raising `t`, 3 for each video a channel lacks; eligible ones beyond its 5 go back to unchecked, so it gets exactly its lowest numbers (at most 10 batches of 50 a tick, so channels with few eligible uploads don't hold up the rest). The downloads come out of the 150 a day, not on top of it: on 2026-10-29 the floor lacked ~250–300 videos, about 2 days of downloads, and after that only newly discovered channels need it (~5 each, a few a week).
4. **Raising `t`:** the eligible upload with the next lowest `r`, over all channels and years at once. Because `r` is random, this spreads evenly over channels and years by itself.

Downloads take the picks under `t` first (new uploads, new channels, and the few already checked to raise `t`), then the floor's. While a floor video is ready, `t` isn't raised. A slot never waits for the floor: when no floor video is ready (waiting for its eligibility check or a download retry, 7), `t` is raised as before, and a floor video due for its retry comes after the few picks checked meanwhile.

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
- **Provenance per video**: rule version, `r`, the cut-off `t` when it was picked, why it was picked (`sample`: under `t`; `floor`: to give its channel 5, 1) _(2026-10-29)_, whether it was measured by the collector or taken over from a live check, yt-dlp and ffmpeg versions, pipeline commit (with "+changes" if the pipeline folder had uncommitted changes), `CACHE_VERSION`, added date. Kept in the database and the exported files; the API exposes only `added_at`.
- **The cut-off `t`** is the highest number the sampling has checked. v2's picks don't count towards it, also when they're taken out later: their numbers played no part in how they were picked. Neither do the floor's checks and picks (1) _(2026-10-29)_: they reach high numbers within one channel, and counting them would raise `t` past uploads of other channels that were never checked.
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
- **Failed downloads are retried** _(human decision, 2026-10-28: on 2026-10-28 five downloads in a row, 14:19–14:49 UTC, got an empty file with no block, and all five downloaded fine by hand hours later; failing them for good dropped good videos)_. Any failure that isn't a block (empty file, timeout, yt-dlp or ffmpeg error, measuring error) keeps the video `eligible` with a `retry_at`:
  - **When:** 1 day after the 1st failure, 3 days after the 2nd, 7 days after the 3rd. **Given up** (`failed`, for good) at the 4th failure, ~11 days after the first. One schedule for every kind of failure: telling "gone for good" from "glitch" by error text is fragile, and the 3 wasted tries of a truly dead video cost nothing.
  - **Within the 150 a day, never on top of it:** a retry is an ordinary download, takes one of the day's slots and counts towards the 150. Retries get no extra slots, so they can't come in a burst: after the wait they're picked like any other eligible video, one per slot at the usual random spacing (~10 min).
  - **Order:** a due retry is picked by its `r` like the rest; its `r` is below the cut-off, so due retries go before new videos. Five due retries delay the next new video by about 50 minutes.
  - **The cut-off and the sampling rule don't change:** a video waiting for its retry is still `eligible` (in the dataset or waiting), only a given-up one is `failed`.
  - **Three failures in a row (not blocks) pause downloads for 1 hour**, with no change to the pace. A short outage then costs 3 tries, not a dozen, and the tries come back through the schedule above.
  - The 6 videos failed so far (2026-10-27/28) go back to `eligible`, due at once, with their one failure counted.
  - `status` shows the retries waiting and the videos given up.
- **The downloader's output is kept** _(human decision, 2026-10-28: the 2026-10-28 failures couldn't be explained, as only the last 180 characters of yt-dlp's quiet error output were kept)_. The download script runs yt-dlp with `--verbose` and, for each try that fails, writes yt-dlp's full output (with ffmpeg's) to a log file next to the clip; its one-line message is the last `ERROR:` line or the "wrote N B" check, as now. The collector moves these to `download-logs/<date>/<id>.log` in its data folder, keeps them 30 days, and names the file in its warning line. On the server only: the logs hold our server's address and YouTube stream URLs, never visitor data, so the privacy policy doesn't change. A listed change in `pipeline/README.md`; `--verbose` changes no downloaded bytes, so feature values stay comparable.
- **Also when the live check is blocked**: the live analysis writes a `youtube-blocked` marker file with the time; the collector honours it like its own block. The live check never waits for the collector.
- **Status**: `hyperstim-collector status` (count today/this week, pace, queue by priority, last block; channels below the floor and the videos they lack, and channels with fewer than 5 eligible uploads in all); `GET /api/meta` shows when the last video was added, so a stalled collector is visible.

### 8. On this server

- **The collector runs on this server** _(human decision, 2026-10-26)_, at 150/day with the safeguards in 7. At ~2 % of the observed block rate and with no bursts, a block is unlikely; the collector stops at the first sign, and the logs then tell us the real limit.
- A second, small instance was weighed: it would keep live checks working during a collector block, but only if YouTube blocks per IP and not per subnet (unknown; a second instance in the same cloud likely shares the subnet), and it's a second server to set up, patch and secure, with results copied over. If blocks ever happen at this pace, moving is cheap: the collector's only output is two TSV files.

### 9. Showing the growth

- **Exact counts, not "16k+"**: a rounded number hides the growth.
- **Home hero: videos, channels, and what each gained in the past week** _(human decision, 2026-10-25)_: "Explore and compare **16,402** ▲1,043 videos from **542** ▲12 channels to better understand what your child is watching.", with a small raised badge after each total holding its gain in the past week. Under the paragraph, a key: "↑ added in the past week" _(human decision, 2026-10-28: the options artifact's raised badge after each total; it shows the new channels too, and two pills side by side would repeat)_. This replaces the line with the pill "+1,043 videos in the past week". A bare "+1,043" after the sentence's two numbers read as unclear (2026-10-26); here each gain sits on the total it adds to, and the arrow and the key say what it is. The channel count is new on the home page _(human decision, 2026-10-25)_. The badges are on the home page only _(human decision, 2026-10-25)_. They count the last 7 days, today included, in the visitor's time zone (not since Monday, so they never drop to a small number at the start of a week) _(human decision, 2026-10-25: counted in days)_: the same window as their links, so each badge's number and the list it opens agree _(human decision, 2026-10-26)_. Each takes its number from the rankings' total for that filter: `GET /api/videos?addedFrom=…&limit=1` and `GET /api/channels?addedFrom=…&limit=1`. The channel rankings list every channel, with no 5-video minimum _(human decision, 2026-10-28: the minimum kept small channels from being judged on a few videos; the collector now keeps adding videos to them)_ (plan 007), so the channel badge's number is the channel count's rise too, and the list it opens shows that many. A badge with 0 is left out; the key goes when both are. The key says "in the past week" _(human decision, 2026-10-26: "the last 7 days" was one number too many)_.
- **Each badge links to its new rankings** _(human decision, 2026-10-26)_: the videos badge to `/rankings?q=added:>{the date 7 days ago}`, so the rankings open with `added:>2026-10-19` in the search box and list only the videos added since (plan 007, Search filters); the channels badge to `/rankings?view=channels&q=added:>{the date 7 days ago}`, the Channels tab listing only the channels added since _(human decision, 2026-10-28)_. On hover the fill deepens (`sky-blue/25`); no underline. Screen readers hear each link as "1,043 videos added in the past week" / "12 channels added in the past week" (sr-only text; the arrow and the key are `aria-hidden`). The badges are links inside a sentence, so the target-size minimum (WCAG 2.5.8) doesn't apply; they are ~17 px high.
- **The badge's look** _(human decision, 2026-10-28: option H3 with an arrow instead of the +; the green H1 badge didn't work)_: the growth pill's blue, `bg-sky` with navy number and arrow (≥ 6 : 1), the arrow a small solid triangle drawn in SVG _(human decision, 2026-10-29: J2; the ↑ character looked out of place, since the body font has none and a borrowed one differs in size and weight per device)_, `rounded-full px-[7px] text-sm font-bold tabular-nums` (the size of the old pill's text), raised a little (`align-[0.4em]`), after a no-break space (not a margin, so copied text reads "16,402 1,043" and the badge never wraps away from its total). The key: `mt-3 text-sm text-ink`, starting with the badge holding only the arrow. No new colour. `STYLE.md`'s growth pill entry becomes this badge.
- **Channels without a name** _(human decision, 2026-10-28: fetch their names from YouTube)_: 9 channels in the reference set (1–2 videos each) have an empty `channel_title`. The 5-video minimum hid them from the rankings; now they'd show as rows with no name (their pages and the compare picker already show a blank). **The existing ones are patched too** _(human decision, 2026-10-28)_: a one-off lookup on 2026-10-28 found all 9 (1 unit), so none is left without a name.
  - **Where the names live** (built 2026-10-29): `backend/data/videos.channel-names.tsv` (`channel_id`, `channel_title`), committed next to `videos.tsv`, holds the 9. The API's loader uses a name from it when a video (reference or collected) carries none; a name a video has is never replaced. `videos.tsv` stays as imported from the research repo. Changed from the earlier plan (a collector lookup exported as `collected/channel-names.tsv`) because all 9 are in the reference set, which never changes, and the collected videos always carry the name `videos.list` gives; and the local site reads the live collector's export, so a collector-side fix would only show locally after a release. Names missing later (an empty `channelTitle` from the Data API) are filled by the collector's repair pass (decision 12), proposed.
  - **Until a name is known**, the site shows the **channel's ID** instead, styled so it doesn't read as a name _(human decision, 2026-10-28)_: a small "Channel ID" label, then the ID in the device's code font, both regular weight in `ink` _(human decision, 2026-10-29: I2, labeled "Channel ID", from the options artifact)_. The API sends an empty name and the frontend shows it wherever a channel's name goes (rankings, home card, channel page and its title, compare picker and slots, video page); the link and accessible name are "Channel ID UC…". `STYLE.md`: Channel without a name.
- **Rankings page: no growing count** _(human decision, 2026-10-26)_. The results line ("Showing 1–25 of 16,402 videos") is the count: it stays put while the visitor is on the page (see No surprises while browsing) and is current at every page load, also when arriving from another page of the site, so it matches the home page's number. For channels it counts every channel, as the home page does ("… of 544 channels"; with a category "… of 120 channels with music videos"), so the two numbers match _(human decision, 2026-10-28: the 5-video minimum is dropped; 544 on home vs 510 in the rankings had looked like a mismatch, 2026-10-26)_. Plan 007's results line changes with it.
- **The animation** _(human decision, 2026-10-25: option A on load, option B on arrival, from the options artifact)_:
  - **On page load (A):** the sentence, the badges and the key are on the page from the first paint, with skeleton bars where the numbers go, so nothing swaps or pops in _(human decision, 2026-10-26: a placeholder sentence, then the numbers, then the pill made the features look patched on)_. For readers that don't run JavaScript (plan 011, Readers other than people) the built page reads "Explore and compare thousands of videos from hundreds of channels…": the bars' width comes from CSS-drawn digits (`before:content-[attr(data-digits)]`), not digits in the HTML, and sr-only "thousands of" / "hundreds of" stand in for the numbers until they arrive (screen readers hear them too); on screen nothing changes _(human decision, 2026-10-29)_. When the counts arrive, all four start counting up together from their value 7 days ago to today's, ease-out (the score gauge's motion), **at the same speed**: the one with the longest way to go takes 1 s, the others take less in proportion (a rise half as large takes 0.5 s), but at least 0.3 s, so a small rise like the channels' few still visibly counts _(human decision, 2026-10-27: 1.5 s made the numbers feel slow to load)_. Videos count from `videoCount` minus the videos badge, channels from `channelCount` minus the channels badge, the badges from 0. Only if the counts can't be had does the sentence say "thousands of", without badges or key.
  - **When a new video arrives while the page is open (B):** the changed digits roll, odometer style (~0.9 s), in the video count and its badge, and in the channel count and its badge when a new channel arrives _(human decision, 2026-10-28)_. Both badges get their number at page load and then rise with the totals from `meta` (a new channel adds 1 to both), so no extra request. The page checks `GET /api/meta` every 60 s while the tab is visible. At 150/day a visitor sees a roll every ~10 minutes, so few will, which is why the badges carry the growth on every visit _(human decision, 2026-10-25)_.
  - **"In the past week" is a moving window**, so on its own it would sometimes go down (when a busy day falls out of it). Visitors never see that: on an open page the counts only ever roll up, by the number of videos and channels added since the page loaded; anything that would lower a number (the window moving on, a video going offline) shows only at the next page load, where the badges count up from 0 anyway _(human decision, 2026-10-26: digits rolling down would confuse)_.
  - Only real numbers from the API; nothing is faked or extrapolated between checks. With `prefers-reduced-motion` the numbers change without counting or rolling (the site's existing rule, `STYLE.md`'s score gauge). Screen readers get the plain number once (the moving digits are `aria-hidden`, an sr-only copy holds the value; no `aria-live`, so nothing is announced every minute).
- **No surprises while browsing** _(human decision, 2026-10-26)_: new videos only make the counts roll. Rows never appear, disappear or change rank on a page someone is looking at; that happens at the next page load.
  - The rankings page (and the compare page's pickers, which search the same lists) remembers the dataset's time from its first answer and sends it as `asOf` with every later request (next page, sort, filter, search). The API then answers as the dataset was at that time: it leaves out videos added after it and keeps ones removed after it, and works out channel scores from those videos. Because scores never change (4), that is exactly what the visitor saw before, so page 2 continues page 1 without skipped or repeated rows.
  - The time lives in the page's memory only, not the URL, so a shared or reloaded link shows the current rankings.
  - Removed videos stay in the API's memory with the time they were removed, so it can answer for earlier times. Their own pages show them as no longer available, as for any video YouTube took down.
  - The rankings' results line ("Showing 1–25 of 16,375 videos") belongs to the table, so it stays put too.
- **API, additive** (`GET /api/meta`): `videoCount` and `channelCount` (already there, now growing), `addedLast7Days` (the past week, in UTC; the badges use the rankings' totals instead, in the visitor's time zone), `channelCount7DaysAgo`, `lastAddedAt`, `referenceCount` (16,375), `channelsCheckedAt` (last discovery run).
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
- **One collector, on prod; dev reads the committed copy** (`COLLECTED_DIR` = `backend/data/collected/` in `.env.example`), so a fresh clone shows the dataset as of the last daily commit, and `git pull` brings in the new videos _(human decision, 2026-10-27: keeps the repo the only link between prod and dev; a second collector would double the load on YouTube and pick different videos)_.

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

### 11. On the prod server (step 5)

Added to plan 010's instance by `deploy/setup.sh`, from `server.env`, like the rest of it:

```
<prod-dir>/
  data/collector/              COLLECTOR_DATA_DIR: collector.db, collected/ (COLLECTED_DIR)
  data/usage/                  USAGE_DIR (plan 014)
  data-repo/                   the data bot's clone (bot user), pushes with the deploy key
  <service>-collector.service  the collector
  <service>-data.service/.timer the daily commit
  env                          gains COLLECTED_DIR, USAGE_DIR and the collector's settings
<clips-dir>/                   COLLECTOR_CLIPS_DIR (server.env): clips/, cache/, work/, backups/
```

- **`server.env` gains three values:** `COLLECTOR_CLIPS_DIR` (the existing local folder on the clips volume), `COLLECT_PER_DAY` (150) and `DATA_USER` (the bot's system user). The units budget stays at its default (7,000).
- **The collector unit** runs `python -m hyperstim_api.collector run` from `releases/current`, as the service user, with the same `env` file and sandbox as the API. It may write only to `data/` and the clips folder; `CPUQuota=100%`, `Nice=10`, `CPUWeight=20`, idle I/O priority, `MemoryMax=2G`. `setup.sh` enables it but doesn't start it; `release.sh` does (the running release may not have the collector yet).
- **`release.sh` restarts both:** the collector after the API is healthy (and keeps the API if the collector doesn't come up: it says so and logs `collector-failed`). The sudo rule gains `systemctl restart <service>-collector`.
- **The daily backup** of `collector.db` is done by the collector itself, once a day (SQLite's online backup), into `<clips-dir>/backups/`, keeping 7. On the clips volume, so a lost system disk doesn't take the backups with it. Tests.
- **The data bot:** its own system user (no login shell, no sudo), home in `<prod-dir>/data-bot/` with an SSH key `setup.sh` makes and prints (GitHub's host key pinned, checked against GitHub's published fingerprint). Its timer runs daily at 03:00 UTC (`Persistent`, so a missed run catches up): `releases/current/scripts/commit-data.sh <prod-dir>/data-repo <prod-dir>/data/collector/collected`, so it runs released code, never unreleased `main`. Sandboxed: it may write only to its home and clone.
- **Who reads what** (ACLs, so nobody else gets in): the release group reads `data/analysis/`, `data/usage/` and `data/collector/` (plan 014); the bot reads only `data/collector/collected/`. `setup.sh` sets them, also as defaults for new files.

**The handover** (go-live), so nothing is collected twice:

1. Stop the local collector (Claude).
2. `sudo deploy/setup.sh` (folders, units, bot, key).
3. Move the local collector's state in and hand the clips folder to the service user, then run `setup.sh` again for the ACLs (the local `COLLECTOR_DATA_DIR` is `<clips-dir>/data`):

   ```sh
   sudo mv <clips-dir>/data/collector.db* <prod-dir>/data/collector/
   sudo sh -c 'mv <clips-dir>/data/collected/* <prod-dir>/data/collector/collected/'  # glob as root: setup.sh closed <clips-dir>
   sudo mv <clips-dir>/data/collector.log <prod-dir>/data/collector/local-run.log
   sudo rmdir <clips-dir>/data/collected <clips-dir>/data
   sudo chown -R <service-user>: <prod-dir>/data/collector <clips-dir>
   sudo deploy/setup.sh
   ```
4. `hyperstim-release`: the API serves the collected videos, the collector carries on where the local one stopped.
5. Local `.env`s point `COLLECTED_DIR` back at `backend/data/collected/`; it fills from the bot's first commit, the day after go-live.

**One release instead of two, with no trial period** _(human decision, 2026-10-27)_: the collector, the frontend and `COLLECTED_DIR` go live together in one release.

### 12. When something fails _(human decision, 2026-10-29)_

An audit of the collector on 2026-10-29 found that downloads already come back (decision 7), but other steps either stop everything or decide for good on one bad answer. Six rules, each with what changes:

1. **One failure never stops the rest.**
   - A Data API error on one item (one channel's upload list, one batch of details) is counted on that item and the item is skipped until its retry is due; today the same failing call comes first on every tick and blocks all API work. Built with its own waits: 1 hour, 6 hours, then a day at a time, never final (an error says nothing about the item); the job that hit it waits the same way, so an outage costs a few calls, not one a minute.
   - Downloads run even when the tick's API work failed; today they're skipped with it.
   - A failed daily backup is logged and tried again the next hour; today it fails every tick, so a full or missing clips volume stops the collector.
2. **No final decision on one answer.** Whatever is decided for good from a single answer gets the downloads' retry schedule (1, 3 and 7 days; final at the 4th):
   - a video missing from `videos.list` (`gone`) or with no `madeForKids` field;
   - a Shorts probe that couldn't decide (v2 counted it as a Short);
   - the monthly offline check: a video is removed only when it's still missing a day later (two checks), and the removal is written in one transaction with its `removed.tsv` row (today a crash between the two leaves it on the site and never checked again);
   - an unexpected error inside a download (disk, classifier, export) counts as a failed try, so it takes a slot and follows the schedule; today it repeats every 10 minutes outside the 150-a-day pace.
3. **Unfinished work resumes.** A new channel's full upload list is read page by page with the next page saved, and the channel only counts as listed when the last page is in; today a listing that fails partway is never finished, so its older uploads are missing for good and the sample is skewed towards new uploads. Built: at most 200 pages a tick, the rest on the next (so a channel with over 10,000 uploads is now read in full too); on the first start after the update, every channel that joined after v2's scan is read again in full, adding only the missing uploads.
4. **Gaps are filled by a repair pass**, daily (built so; it costs no units when nothing is missing, so a measured video waits a day, not a month):
   - dataset videos or channels with an empty title or channel name: `videos.list` / `channels.list`, the names kept in `collector.db` and exported as `collected/channel-names.tsv`, which the API reads like the reference set's names file (decision 9);
   - uploads skipped for having no publish date: looked up again with `videos.list`;
   - channels whose listing never finished (rule 3).
5. **Someone hears about it.**
   - `status` shows, per kind: items waiting for a retry, given up in the past 30 days, the last success of each job (download, upload lists, offline check, repair, backup, export) and how long a block has lasted. The daily commit runs as its own service, so its last success is in its journal, not in `status` (step 16 watches it).
   - **Alerts are GitHub issues opened by the bot** _(human decision, 2026-10-29)_, only when something hasn't worked for a day, from fixed templates because the repo is public (Alert issues, below).
6. **Nothing incomplete is shown** _(human decision, 2026-10-29)_. A video goes on the site only when everything it shows is in place: ID, title, channel ID, channel name, publish date, and its measurement (at least one feature value; a single empty feature, e.g. a silent clip, is a measured result). Until then it stays in the backlog, measured but not exported, and the repair pass (4) fills the gaps.
   - The collector exports only complete videos; a measured video with a gap waits with `state = 'measured'`, not `collected`, and goes out once repaired, with the time it went out as its `added_at` (so lists read as of an earlier time don't change). It counts towards the day's 150 when it's measured, as now. A measurement with no feature value at all is a failed download. A measured video the repair can't find 4 days running is gone (`ineligible`).
   - The API skips any collected row that is incomplete anyway (logged with its ID), so a gap never reaches a visitor even from a hand-edited file.
   - The reference set is complete with `videos.channel-names.tsv` (decision 9); a test on the committed data keeps it so. Its rows are never left out of the scoring pools, so scores don't move.
   - No category isn't a gap: the classifier ran and no keyword placed the video (6 of the first 278 collected); it shows without a category, as now.

Kept as is: quota exhaustion (waits for the next quota day), blocks (decision 7), the export (written whole, so it heals on the next write), the API's reload (keeps the last good dataset), the daily commit (the next day carries everything).

**Alert issues** _(human decision, 2026-10-29: fixed text with typed blanks; only for major problems, something not working for a day, so issues don't bombard us)_. The bot fills a fixed template; nothing else can go out:
- **Templates in the repo** (`backend/src/hyperstim_api/collector/alerts.py`, next to the code that fills them, so they ship with each release): title and body are fixed text with named slots. Each slot has a type the code checks before posting: a number, a UTC date or time, a duration in whole hours or days, or one word from a fixed list. A value that doesn't fit is replaced by "unknown", never posted. **No free text**: no error messages, log lines, file paths, hostnames, IPs, user names or stream URLs, since any of these can carry server details.
- **Only after a day**: every alert waits until something has not worked for 24 hours. Shorter trouble (a block, a retry, a restart, a day the quota ran out) shows only in `status` and the log; the collector already rides it out (rules 1–3).
- **Few and quiet**:
  - One open issue per kind (and per job for `job-failing`), found by its labels (`alert`, `alert:<kind>`).
  - **Comments only when something changes** _(human decision, 2026-10-29: the bot comments when the situation changes or gets worse)_, each from a fixed template:
    - the state changed and has held for two hourly checks (so a flicker isn't reported): "Still no new video. State is now <state>: <meaning>.";
    - the 3-day and 7-day marks: "Still no new video after <n> days. State: <state>." (the 7-day one adds "This is the last reminder; the next comment will be when it works again."). For `job-failing`, the same with "<job> still not working after <n> days.";
    - nothing else: no comment while the situation stays the same.
  - **It resolves them itself**: when the problem clears, the bot closes the issue with the fixed comment "Working again since <time>."
  - The same kind isn't opened again within 24 hours of closing, so a problem that comes and goes stays one issue a day at most.
  - At most 3 issues a day across all kinds.
- **The checker runs on its own**: a systemd timer, every hour, separate from the collector, reading `collector.db` and the timers' last results; so a collector that has stopped altogether is still reported.
- **The details stay on the server**: each issue ends with the fixed line "Details: the collector's `status` command and its log on the server."
- **Its own token, Issues only** _(human decision, 2026-10-29: a fine-grained token)_: a fine-grained personal access token with only "Issues: read and write" on this repo, in `server.env` (never in the repo); the data bot's deploy key can't open issues.
- **Two templates.** The title names when the problem started, not how long it has lasted, so it stays true without edits _(human decision, 2026-10-29: a length like "1 day" would stay "1 day" all week)_.

| Kind | When | Title | Slots |
|---|---|---|---|
| `stalled` | no video added for 24 hours | Collector: no video added since <date> | since when; the state (`running`, `blocked`, `paused`, `waiting-for-quota`, `not-running`); videos waiting for a retry |
| `job-failing` | a job hasn't worked for 24 hours past when it was due | Collector: <job> not working since <date> | the job (`upload-lists`, `details`, `discovery`, `offline-check`, `repair`, `export`, `backup`, `data-commit`); its last success; failures in a row |

Each body is fixed text: the slot values, a fixed one-line meaning for the state or job the slot names (e.g. `blocked`: "YouTube is refusing our downloads. The collector waits and tries again by itself."), "This issue closes by itself when …", and the Details line. Examples of each, in six scenarios: the alert issues artifact (2026-10-29).

A YouTube block, a crashing collector or an empty clips volume all end in no new videos, so `stalled` covers them; `job-failing` catches the jobs that fail quietly while downloads go on (a stale backup, the site's data not updating, new uploads not being listed). The state slot tells which; the details are on the server.

Neither template can show anything that isn't already public: what was added and when is on the site, and "blocked" says only that downloads paused.

### Privacy policy (plan 009)

No change needed for the collector: it handles no visitor data; it only talks to YouTube from our server, as live checks and thumbnails already do; the clips it keeps are of videos it picked itself, not ones a visitor checked (whose clips are still deleted, as the policy says); new dataset videos' thumbnails go through the existing endpoint. Checked again at build time. (A second instance would also be "us"; still no change.)

### Effects on other plans

- 001: the dataset is no longer fixed; usage counts (plan 014); the collector service; scores against a fixed reference set; "downloaded clips are deleted once analysis finishes" becomes true for live checks only (the collector's are kept on the clips volume).
- 002: the hero sentence gains the channel count and the past week's gains as badges on the two totals, all animated.
- 007: the channel rankings drop the 5-video minimum (2026-10-28); the animated video count under the intro; `asOf` keeps the table steady while browsing.
- 008: the pickers send `asOf` too.
- 006: score lead copy, two new common questions (scores don't change; how we choose channels and videos), discovery date, dataset box.
- `STYLE.md`: the growth badge, and the count-up / rolling-digits motion.
- 010: `release.sh` and `release-notes.sh` treat `data:` commits as above; the tag ruleset for `v*`; `setup.sh` installs the collector unit (1 core, low priority), its clips folder, the data bot's user, clone, deploy key and timer, `server.env` gets `COLLECTOR_CLIPS_DIR` and the pace, `release.sh` restarts both services. The shared API key's note ("a new analysis costs 1, prod caps at 1,000/day") gets the collector's share. The hourly alert check (decision 12): its service, timer and root-only token file, and the token in `server.env`.
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
5. **Deploy (plan 010, decision 11):** _built 2026-10-27._ the collector and data-bot units and timer, `server.env.example`, `env.template`, `setup.sh` (folders, bot user and key, ACLs), the sudo rule, `release.sh` (restart both), the collector's daily backup (tests), `deploy/README.md`, plans 010 and 014. Checked with `shellcheck` and a dry run of `setup.sh`'s rendering. Stop for review.
6. **First run on the server:** none; no trial period before go-live _(human decision, 2026-10-27)_. The local run on this server since 2026-10-26 already showed downloads and measuring work there.
7. **Frontend:** exact counts, the count-up and rolling digits, up only (home: videos, channels, pill), polling `meta` while visible, `asOf` in rankings and compare pickers, `api.ts` types, How it works copy and the two common questions; `STYLE.md` gets the count's style; screenshots at 360/1280 px.
8. **Go live:** the handover (decision 11), then a release (frontend and backend together, by the team).
9. **Docs:** `backend/README.md` (collector, env vars, commands), `.env.example`, plans 001/002/006/007/010, `CLAUDE.md`.
10. **Faster numbers on the home page** (2026-10-27): the count-up at the same speed (1 s for the longest, at least 0.3 s; `RollingNumber` takes a duration, the hero works it out; `STYLE.md` Growing counts); `gc.freeze()` after each load (10, tests: a reload frees the old dataset); plan 007's step 8. Measure on the dev site before and after (time until the numbers settle), screenshots at 360/1280 px. Stop for review.
11. **Retries and download logs** (2026-10-28, decision 7): _built 2026-10-28._ `retry_at` for eligible uploads and the retry schedule; give up at the 4th failure; the 1-hour pause after 3 failures in a row; reset the 6 failed videos (at each start; nothing to do once none is left with fewer than 4 failures); `status` counts; `--verbose` and the per-try log in `58_download_clips_v2.py` (listed in `pipeline/README.md`), moved to `download-logs/` and pruned after 30 days; `backend/README.md`. Tests (fake downloader): a failure comes back after 1, 3 and 7 days and is given up at the 4th; retries count towards the 150 and come one per slot; 3 failures in a row pause 1 hour; a block still waits and leaves the video eligible; the log file is kept and pruned. Stop for review; deployed with the next release.
12. **New channels on the home page** (2026-10-28, decision 9): _built 2026-10-28._ The pill becomes a raised badge after each total (an up triangle, sky) and the key line under the paragraph; `useGrowth` also asks for `GET /api/channels?addedFrom=…&limit=1` and returns the channel gain (rising with `channelCount` on each poll, rolling like the totals) and its rankings link (`view=channels`); skeletons for both badges; a badge with 0 left out, the key with both. **No 5-video minimum** (plans 002, 005, 007, 008): `minVideos` defaults to 1 in the API (the parameter stays, additive), the rankings and the home rankings card stop sending 5, the results line drops "with 5+ videos", the "has fewer than 5 videos, so it isn't ranked" message goes, `MIN_VIDEOS` and the mock follow. `STYLE.md`: the growth pill entry becomes the badge and key. Tests: unit (`useGrowth`: channel count and link, `view=channels`, the channel badge rises with `channelCount`), pytest (`minVideos` default 1: a 1-video channel is ranked), component (`Hero`: both badges, their links and sr-only names, 0 hides a badge, both 0 hide the key, axe), E2E (home: the channels badge opens the Channels tab filtered to `added:>`, keyboard path, 320 px reflow). Screenshots at 360/1280 px. Stop for review.
13. **Channel names** (2026-10-28, decision 9, Channels without a name): _built 2026-10-29._ `backend/data/videos.channel-names.tsv` with the 9 names from the 2026-10-28 lookup; the loader uses it for videos with no channel name; `ChannelName` (I2) and `channelLabel` wherever a channel's name goes; `STYLE.md`; `backend/README.md`. Tests: pytest (a missing name is filled for reference and collected videos; a name a video has is never replaced; without an entry it stays empty), component (`ChannelName`: the name as is; the label and ID, named "Channel ID UC…", axe; the rankings' Channels tab with a nameless channel), E2E: the full suite (the rankings' Channels tab passes axe, compare's two channels). Stop for review.
14. **When something fails** (2026-10-29, decision 12, rules 1–6): _built 2026-10-29._ the rules in the collector (`collector.py`, `youtube.py`, `store.py` with a migration for the per-item retry counts, listing progress and the `measured` state); the repair pass and `collected/channel-names.tsv` (read by the API like the reference set's names); only complete videos exported, and the API skipping incomplete rows; `status`; `backend/README.md`. Tests with a fake Data API and downloader: a failing channel listing is skipped and retried while downloads go on; a `gone` video and an undecided Shorts probe come back on the schedule; a removal needs two checks and is one transaction; a backup failure doesn't stop the tick; an unexpected error takes a slot; a listing that fails on page 3 resumes at page 3; a measured video with no channel name isn't exported until the repair fills it, then is; the API skips an incomplete row; the committed reference set is complete. Stop for review; deployed with the next release.
15. **A sensible sentence before the counts arrive** (2026-10-29, On page load (A); plan 011, Readers other than people): _built 2026-10-29._ The hero's skeleton bars (`Room` in `Hero.tsx`) keep their digits in a `data-digits` attribute shown by a CSS `::before`, instead of as text; sr-only "thousands of" and "hundreds of" next to the two totals' bars while loading. `STYLE.md` Growing counts says so. Tests: component (`Hero` while loading: the paragraph's text is "Explore and compare thousands of videos from hundreds of channels…" with no digits, the bars are still there; fails before the change), E2E (plan 011's no-JavaScript check covers the homepage). Screenshots at 360/1280 px before and after, to show the bars are unchanged. Stop for review.
16. **Alert issues** (2026-10-29, decision 12, Alert issues): _built 2026-10-29._ `collector/alerts.py`: the typed slots and their check, the two templates and their fixed meanings, `decide` (nothing before a day; one issue per kind and job; a state change commented once it held for two checks; the 3- and 7-day comments, none after; closing on recovery; 24 hours before reopening; at most 3 a day; a stopped collector is `stalled`, not one issue per job), GitHub's API with the token (or only the log without one), its memory in `alerts.json`; the command `python -m hyperstim_api.collector alerts`. The collector records what the check reads: a heartbeat each tick (`tick_at`), `low_space`, the backup's time, the export's failures. The daily commit's runs are read from systemd (`systemctl show`). `deploy/`: `alerts.service`/`.timer` (hourly) and the root-only `alerts.env`, `setup.sh` (the repo from the checkout's origin), `server.env.example`, `README.md` (creating the token); `backend/README.md`, `.env.example`. Tests (pytest): every slot type turns free text (a path, an IP, an error line) into "unknown"; the templates; each rule of `decide`; the daily commit from systemd's last run; the check end to end with a fake GitHub; a failed send is tried again; the collector's records. `setup.sh`: `bash -n`, shellcheck (only the existing notes), templates rendered with `envsubst`. Deployed with the next release, then `sudo deploy/setup.sh` with the token. Stop for review.
17. **At least 5 videos per channel** (2026-10-29, decisions 1, 2 and 6, the floor): _built 2026-10-29._ a `pick` column on uploads (`sample` or `floor`; a migration sets `sample` on everything picked so far); checking a floor channel's unchecked uploads in `r` order, fewest-video channels first, 3 per video it lacks, the eligible ones beyond its 5 back to unchecked; `next_eligible` takes the picks under `t`, then the floor's (fewest videos first), each by `r`; `t` raised only when no floor video is ready; a new upload of a channel below 5 is taken whatever its `r`; `cutoff()` counts `sample` only; `pick` in the exported provenance; `status` counts; `backend/README.md`. Tests (fake Data API and downloader): a 1-video channel is topped up to 5 by its lowest numbers, before uploads above `t` of other channels; the floor's checks and picks don't raise `t`; once `t` passes a floor pick nothing changes; a channel with 3 eligible uploads keeps 3 and takes its next eligible new upload above `t`; a channel that loses a video offline is topped up again; with no floor video ready the slot goes to raising `t`; floor downloads count towards the 150; an older database's uploads become `sample`. Stop for review; deployed with the next release.

By hand (the team), in order:

| When | Who | What |
|---|---|---|
| Done | you | Review plans 013 and 014. |
| Now | you | Review step 5 (decision 11). |
| After step 5 is merged | a repo admin | GitHub → Settings → Rules → Rulesets → New tag ruleset: target `v*`, restrict creations, updates and deletions, bypass: repository admins only. |
| After step 5 is merged | you, on the server | In your clone: `git pull`; add the new values to `deploy/server.env` (from `server.env.example`); `sudo deploy/setup.sh`. It prints the data bot's public key. |
| Then | a repo admin | GitHub → Settings → Deploy keys → Add deploy key: the printed key, "Allow write access" on. |
| Then | Claude, then you | Claude stops the local collector; you run the move commands Claude gives (paths from your `server.env`), then `sudo deploy/setup.sh` again. |
| Then | you | `hyperstim-release` (Claude never releases). |
| Next day | you | Check the first daily `data:` commit on GitHub and the counts on the live site. |
| After the release with step 16 | a repo admin | GitHub → your profile → Settings → Developer settings → Fine-grained tokens → Generate: this repo only, "Issues: Read and write" only (`deploy/README.md`, GitHub step 4). |
| Then | you, on the server | Put the token in `ALERT_GITHUB_TOKEN` in `deploy/server.env`; `sudo deploy/setup.sh`. Without it, the hourly check only logs what it would post. |
| Then | you | Check the alerts timer is listed (`systemctl list-timers`) and its first run's log; when the first alert issue opens, check it carries its `alert` labels. |

## Review decisions

Decisions made while building (2026-10-26), each in its spot above where it fits there:

- **Lists answer as of a version**: every list answer carries `asOf`, the time of the dataset's last addition or removal; before any, the reference set's date (`2026-09-01T00:00:00Z`), so a page can pin itself from the very first answer.
- **The count-up is shared**: `ScoreGauge`'s count-up moved into `lib/motion.ts` (`useCountUp`), used by the gauge and the new rolling number (`components/RollingNumber.tsx`). Each digit is a strip of 0–9 twice, so 9 → 0 keeps rolling up.
- **Pinning**: on the rankings page one pin is shared by the Videos and Channels views; each compare picker keeps its own.
- **How it works ③**: before the first full discovery run the scan date shows v2's (August 2026).
- **The first offline check takes out a few hundred v2 videos** (deleted or private since August), so the count dips below 16,375 for a couple of days before additions overtake it. This happens in the local run, before production.
- **The deployment (step 5)** is planned in decision 11. Already built and tested: `scripts/commit-data.sh` (the daily commit), `scripts/check-data-commits.sh` (CI and `release.sh`), the `data` type in `release-notes.sh` and the hook.

## Open questions

- **Channels that stay below 5** (fewer than 5 eligible uploads in all, or between discovery and their top-up, about a day): should the channel rankings (plan 007) mark a score from fewer than 5 videos, or leave it as is? Not part of step 17 unless decided.

Usage counts: plan 014.
