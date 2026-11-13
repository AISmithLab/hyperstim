# 001: Variant pairs

**Question:** Do studios publish near-identical versions of one video (same animation; new colors, background or title), and is there evidence they test the variants against each other?

**Parts** _(human decision, 2026-11-12)_: 1. quantify how similar the seed pair is (Signal framework, Pair report); 2. search the two seed channels for more pairs (Search: more pairs in the seed channels); 3. search other channels (planned when part 2 is done).

**Seed pair** (same song, two channels the user believes are one company; published 18 days 1 h 27 min apart):

| Video | Channel | Published (UTC) |
|---|---|---|
| `pRPe05YfXxg` Five Little Ducks (cartoon) | Kids TV - Nursery Rhymes And Baby Songs | 2014-10-18 08:14:11 |
| `AJ1vEJXC0-M` Five Little Ducks (3D) | Kids Channel | 2014-11-05 09:41:12 |

## Signal framework

- Studios use different strategies (e.g. new title but the same audio; different total length but the same song part), so **a pair needn't be similar on every signal**. Some signals firing is evidence enough.
- Each signal is scored against **baselines**: the same subject by another studio; random pairs from one channel; random dataset pairs. A signal **fires** when the pair beats the 99th percentile of unrelated pairs in every set that is large enough (the strictest wins).
  - **Same subject** controls for look-alikes that come from the content, not from reuse (same melody, same title words, ducks in both). The subject is the run of title words the pair shares (a song, a story, a character); when fewer than 10 other studios' videos share it, the set is filled up with the other studios' videos closest to the pair by title and thumbnail embedding. The report says which way the set was built.
  - A set needs **at least 30 pairs** to set a threshold. A smaller set is shown with its size but doesn't set one, and the signal is marked "weak baseline".
  - Sizes, seed pair: whole-dataset signals (timing, title, duration, features): same subject 118 pairs (16 versions of the song from 14 other channels), same channel 5,000, random 5,000. Sampled signals (description, tags, thumbnails; 182 videos): 150, 120 (8 channels × 6 videos), 600. Download signals: a time-shift baseline only (B moved 3–30 s), until baseline downloads exist.
- The set of signals that fire is the pair's **strategy profile** (e.g. "same audio, new title, recolored"); profiles are compared across pairs and studios.
- Align the two videos in time first (audio cross-correlation), before any frame-by-frame signal.
- Signals are grouped into metadata, visual and audio, plus a summary of what changed and how the pair compares. _(human decision)_

### Metadata

| Signal | Measures | Needs |
|---|---|---|
| Owner | Same company, from the strongest evidence found: featured channels (`channelSections`, `multiplechannels`); a shared company in video descriptions' copyright lines; shared domains, emails or app links in channel and video descriptions. Free text varies by channel, so match general patterns (URLs by domain, emails, "©" lines), not one layout. When that isn't conclusive, an agent checks the channel pages by hand. _(human decision)_ | API |
| Timing | Days between publishing; time of day | API |
| Title | Similarity after normalizing the song name | API |
| Description and tags | Text and tag overlap | API |
| Duration | Difference in total length | API |

### Visual

| Signal | Measures | Needs |
|---|---|---|
| Thumbnail | Embedding and grayscale hash similarity | Image |
| Storyboard | Similarity of the storyboard frame sequences; rough cut positions (a cheap first look at the signals below) | Image |
| Aligned cuts | Share of cuts at the same time (± 1 frame) after alignment | Download |
| Motion curve | Correlation of camera and object motion over time (optical flow) | Download |
| Structure | Layout and shapes regardless of color: grayscale and edge SSIM per aligned frame | Download |
| Frame content | DINOv2 embedding similarity per aligned frame | Download |

### Audio

Levels, from most to least similar; a pair's audio level is the closest one that holds. _(human decision)_

| Level | Measures | Needs |
|---|---|---|
| Exact same audio | Fingerprint and waveform match | Download |
| Same audio, adjusted | Match after normalizing loudness (and EQ, speed); the gain and speed differences | Download |
| Same backing, different overlay | Backing track matches, vocals or sound effects (e.g. chuckles) differ: compare separated stems | Download |
| Same song, re-recorded | Melody, key and tempo match (chroma), but no shared recording; what any studio's version shows | Download |

For each level: offset between the two, and the **longest matching segment** (the song part can match even when total lengths differ).

### What changed and how they compare

| Signal | Measures | Needs |
|---|---|---|
| Color | Hue and saturation difference | Download |
| Changed area | Share of the frame that changed: background vs characters | Download |
| Added or cut parts | Intro, outro or segments only one version has (from the alignment) | Download |
| Our features | Difference in the 12 pipeline features (free if the video is in the dataset) | Download, or free |
| Audience | View and like ratio | API |

## Pair report

One artifact page per pair (`report.html`, built by `build_report.py`), every pair in the same structure _(human decision)_:

1. The two videos' basic info as a table, one column per video, one row per field: thumbnail, title, channel, channel ID, video ID, published date and time, length, views (and likes), channel subscribers, channel history (created, age at upload, videos, views, country) _(human decision)_.
Each report's synced player starts at the beginning of the video _(human decision, 2026-11-12: it opened mid-video)_.
2. Inspection sheet: every signal of the framework as one row, grouped by category, with a verdict (same: the signal fires; different) and a short finding; same rows are tinted yellow _(human decision)_, and each row links to its deep dive. Rows under "What changed" use a stated plain rule (e.g. same below 10 ΔE).
3. Frame-by-frame viewer: the two downloads play in sync (A is the clock, B follows at the alignment offset), with sound from A, B, both or off; frame and cut stepping; timeline tracks for alignment, cuts, loudness of A and B, audio match, motion, outline match and changed area.
4. Deep dives: signals against baselines, owner/titles/tags, colors and changed parts, audio levels, features and audience.
5. Method notes sit in (i) tips next to what they explain, not in a section of their own.

The page carries the two 360p downloads so they can play: keep it private to the team.

## Search: more pairs in the seed channels

**Goal:** find every re-skinned pair in Kids TV (A, 4,736 videos, since 2013) and Kids Channel (B, 1,150, created 2014-10-30), without scoring all pairs, and with no single signal (title) as the gate. Three **pair types**, searched in the same run: A×B (5.4 M pairs), A×A (11.2 M) and B×B (0.66 M) _(human decision, 2026-11-11: within channels too)_; 17.3 M in all.

Within a channel, look-alikes come from more than reuse: a shared channel template (intro, logo, characters), episodes of one series, re-uploads and compilations. So:
- Every threshold and percentile is computed **per pair type**, against random pairs of that type (a random A×A pair already shares the template).
- **Compilations** (longer than 30 min _(human decision, 2026-11-11: was 10 min)_, or titles like "compilation", "collection", "1 hour") stay out of pairs _(human decision)_: they contain other videos rather than vary them. Counted in the report, left for later.
- The agent also labels **re-upload** (same video, nothing changed) apart from re-skin.

**Constraints** _(human decision)_: results within half a day, in one run of a few hours; API units as needed (the 2,000-a-day limit doesn't apply to this search); up to **500 player requests in one day** for this search _(human decision, 2026-11-11; was 200, and accepted though 121 in 24 h caused the first block)_: downloads stop at the first failed one, and while the collector is blocked. Storyboards need a player request, same as a download, so the gate can't use them: it works from API and image signals, and downloads go to the pairs the agent confirms.

**Pacing** _(human decision: random gaps, be friendly to their servers)_: one request at a time, each gap drawn at random.
- Images: gap uniform 0.5–1.5 s (mean 1 s, ~1 a second) _(human decision, 2026-11-11; was a fixed 2 a second)_.
- Downloads: gap uniform 45–135 s (mean 90 s) after each one finishes; 200 downloads fit in ~5 h, inside the run.
- Both in `tools/yt.py` (`EXP_IMAGE_GAP`, `EXP_PLAYER_GAP` as min–max), so every experiment gets them; README's budget section updated with it.

### Filter chain

Each stage is a filter with its own queue, and all run at once: a pair moves to the next queue as soon as it passes, so the first full reports come ~1–1.5 h into the run instead of at the end _(human decision; named so it isn't confused with the analysis pipeline in `backend/pipeline/`)_. Everything is saved to `results/search/` (queues in one SQLite file, `cache/search.db`, rebuilt from the saved results if lost), so a stopped run resumes where it was and reruns cost nothing. Expected sizes: all 17.3 M → candidates ~60–100 k → scored ~5 k → gate ~200–800 → agent confirms → download ≤ ~100.

| Filter | Takes | Passes on | Cost |
|---|---|---|---|
| 0. Inventory | Both channels' uploads: `playlistItems` (page tokens saved), then `videos.list` for title, description, tags, duration, publish time, stats | All videos, into the image queue in **random order** (so the first ~15 min are a random sample for the baselines) | ≈ 240 API units, ~5 min |
| 1. Images | Thumbnail + middle auto-frame (`hq2.jpg`, a frame YouTube takes at ½ of every video, separate from the custom thumbnail) per video; embeddings (DINOv2) and outlines as they arrive | Each video, as soon as its two images are in | 11.8 k images at ~1 a second ≈ 3.3 h; embeddings keep up |
| 2. Candidates | A video that arrives is compared with every video already in, of each pair type: title subject (char n-gram TF-IDF after removing channel boilerplate like "3D", "Nursery Rhymes"), thumbnail embedding, thumbnail outline (catches recolors), middle auto-frame (embedding and outline). Embeddings at 224 × 126 (16 × 9 patches), 2 torch threads: enough for near-duplicates, and they keep up on the loaded machine | Pairs that beat the **99th percentile of random pairs of their type** on any one of the five. A fixed cut, not "top 10 per video", because a top 10 is only known once every video is in. The percentiles come from all pairs of the first 500 videos (random order) | local |
| 3. Score | One screen score from all image and API signals (plus duration fit allowing an end screen, publish order), as percentiles against random pairs of the type | Pairs above a cut set so the seed pair passes with margin | local |
| 4. Gate | Fetches `hq1`/`hq3` (¼ and ¾) for the pair's videos, ahead of the bulk images in the image queue; all 3 × 3 auto-frame pairs on outline SSIM and embedding (positions differ when one version has an end screen, and verses repeat); random baseline from 210 videos' auto-frames | Pairs where the best auto-frame match beats the 99th percentile of their type, or the thumbnail beats its 99.9th (the thumbnail already passed at the 99th). A random 3% of the stopped pairs (up to 60) goes on as an audit of what the gate misses | up to ~8 k images ≈ 2.2 h, spread over the run |
| 5. Agent review | Only gated pairs _(human decision: tokens are plentiful but gated first)_, in batches of ~10 on one sheet (both thumbnails + auto-frames, the signals that fired); labels: re-upload / re-skin (same animation re-skinned) / same song, different animation / same template (series episodes on one template, different content) / shared segments (compilations sharing footage, a short cut from a long video) / unrelated, with a confidence. Same template and shared segments were added during the run (2026-11-11), when most gated pairs turned out to be series episodes and compilations. Pairs whose videos already have 5+ same-template or shared-segments labels go to the back of the queue. Catches what the signals miss (redrawn background, same characters) | Confident re-skins (confidence ≥ 0.7), most different strategy profiles first _(human decision)_, one queue across pair types with at least ~20 pairs of each type that has them _(human decision)_ | tokens |
| 6. Download | Both videos of confident re-skin and re-upload pairs, once each (a video in several pairs is reused) | Downloaded pairs | ≤ 500 player requests a day, paced |
| 6b. Overlap | Aligns each downloaded re-skin and re-upload pair: audio first, then frames (DINOv2 at 2 fps) when the audio covers less than half; `overlap.py`. By frames, a part of the video counts as shared where its 10 s windows find their own best lag within 3 s of the pair's (changed 2026-11-12, after a review question: the earlier frame-by-frame test missed re-skins of songs whose scenes repeat, like 5ElsiB8aoIg ↔ cjtn_IOstAI at 48%, now 95%; checked on 38 pairs: matches 0.87–1.0, the rest ≤ 0.46). Each second of a video counts once: a compilation that plays the other video's song three times covers that song once (fixed 2026-11-12: repeats were counted again, giving shares up to 16× the shorter video for 31 pairs, which let compilations through as linked) | Pairs whose aligned parts cover **at least half of each video**: the main content must overlap _(human decision, 2026-11-11: a 2–3 s shared part, like an intro sting, doesn't count)_, of the longer video too _(human decision, 2026-11-12: compilations that hold a whole version, like UCrI_HkV9gw and pjbLaZqWo2Q, aren't re-skins)_. The half is set from the first 36 reports, which split cleanly into 0.02–0.12 and 0.79–1.0. Pairs under half of the shorter are listed apart as "looked alike, little shared"; pairs under half of the longer as "one inside a longer video" (compilations, shorts cut from a longer video, longer versions with more added) | local, ~1 min a pair |
| 7. Groups and full reports | Pairs of one label that pass 6b form **groups** (connected videos), shown together rather than as separate pairs _(human decision, 2026-11-11)_. For a re-skin group of n versions, n − 1 full reports cover every change: each version against the group's earliest, along the labelled links (`report_selection.py`), all of them _(human decision, 2026-11-11: keep the reports at this scale)_. Re-upload groups get no full report (nothing changed); their overlap shows it. Reports: `prepare_pair.py` (align, cut clips, pipeline features), `score_pair.py` with signal order (below), then the report (`run_reports.py`). When the audio covers less than half, the pair is aligned by its frames instead and the report says so. CPU only _(human decision, 2026-11-11)_ | — | 5–15 min a pair (measured; 30 min when stems run) |

**Running it** _(human decision, 2026-11-11: the first run stopped when the machine ran out of memory)_: the first run held every frame of both full videos in memory at three sizes (~4 GB for a 5-min pair, far more for long ones) with 6 pairs at once, and the out-of-memory killer stopped every process at 14:17 UTC. So: `score_pair.py` keeps only the frames it samples; a pair starts only while enough memory is free; each step's peak memory goes into `reports.tsv`; and the rest of the run (downloads, overlap, reports, site build) is one detached, resumable job under a memory cap, so neither a session ending nor one large pair stops the others.

**Signal order** _(human decision)_ in `score_pair.py`: signals run cheapest first, and a costly one runs only when it can still change the pair's verdict; the report then says which signal settled it (e.g. stems: "settled by waveform match, r 0.998"). Every signal still has a row. Example: stem separation decides only "same backing, different overlay", so it runs only when the waveforms don't match. Every 10th pair runs every signal, to check the order never changes a verdict. Before the run, time each signal on the seed pair to set the order.

**Timeline** (estimate; the machine's load was 42 on 8 cores on 2026-11-11, which could double the scoring time):

| | Image gap 0.5 s (2 a second) | Image gap ~1 s (chosen) |
|---|---|---|
| Image requests (~20 k) | ~2.8 h | ~5.6 h |
| First full report | ~1–1.5 h | ~1–1.5 h (gate frames go first) |
| All pairs through the agent | ~3 h | ~5.6 h |
| All ~100 full reports | ~3.5–4 h with signal order | ~6 h (images and downloads both ~5–6 h, scoring keeps up) |

At ~1 a second the run is limited by images, not scoring, and still ends inside the day; signal order then matters less for time, but keeps the CPU free for the machine's other work.

Seed pair check first: the auto-frames must exist for 2014 videos (6 image requests), and the filters must pass the seed pair. If not, the plan comes back for review.

**Run:** one session, ~6 h; the overview is republished as stages finish. No multi-agent orchestration for the filters: they are scripts; the agent is used only where judgment pays (filter 5, run as subagents in batches while the queue fills).

**Scope:** the seed channel pair only _(human decision, 2026-11-11)_. Kids Channel's "Our Family" lists 8 more (1 API unit): Kids Channel - Cartoon Videos for Kids (US, 2,784 videos) and 7 language channels (461–2,405 videos each; likely dubs, a separate localization question). All 10 would be 15,174 videos, ≈ 610 API units and 2.6× the image requests; left for later.

**Deliverables** _(human decision)_, all private artifact pages; the layout depends on how many pairs get downloaded:
- **5 or fewer:** an overview page, plus one artifact per pair report in the seed pair's structure (Pair report, above; `build_report.py`), linked from the overview.
- **More than 5:** one base artifact with the overall results for **re-skins only** (facts, filter chain from the agent review on, channel story, strategy profiles; linking only the re-skin groups page) _(human decision, 2026-11-12)_, and **one artifact per label** (re-skin, re-upload, same song, same template, shared segments) that lists its groups _(human decision, 2026-11-11: when the size limits get in the way)_: the re-skin page opens with the channel story's timeline, each link opening its pair's full report (or jumping to its group when it has none) _(human decision, 2026-11-12)_, then the families table, one row per group linking to it _(human decision, 2026-11-12: the page had become a long scroll)_, views as min / median / max, with the median left out ("–") for families of two _(human decision, 2026-11-13: a median of two says nothing)_; each group is headed by its number and name ("1. Wheels Bus Classic") _(human decision, 2026-11-12: was a small "Group 1")_ and is a table, one row per version, earliest first: thumbnail and auto-frames on the left, then title, channel, release date, views, likes, like rate (likes / views) _(human decision, 2026-11-12)_ and visual intensity (the site's metric: the percentile of `mean_saturation` among the dataset's videos; "not measured" for videos never downloaded) _(human decision, 2026-11-12)_ and visual brightness (the site's percentile of `mean_lstar`, lightness, the same way) _(human decision, 2026-11-13)_. Every column sorts from an arrow in its header _(human decision, 2026-11-12)_. Groups can be starred, and the page can show only the starred ones _(human decision, 2026-11-12)_; stars are shared by everyone who can open the page (the artifact's database), or kept in the browser where that isn't available. Each group can also hold a short note (up to 500 characters), shown under its head and edited in place, kept the same way as the stars _(human decision, 2026-11-13)_. Then its pairs with the overlap, and for re-skins its reports: first one with **all the group's versions together** (every video in a grid, played in sync on the earliest version's clock, then their measures side by side; `search_group_report.html`) _(human decision, 2026-11-12)_, with the pair report's frame-by-frame view across the group: change map and outlines over each tile (against the version its full report links it to), frame and cut stepping, and timeline lanes per version for cuts, changed area and outline match _(human decision, 2026-11-12: the frame-by-frame view is what helps most)_; then the full pair reports. Reports open in a panel on the right _(human decision, 2026-11-12: was opening below, in place)_ whose width can be dragged _(human decision, 2026-11-12)_. Unrelated pairs are counted, not listed _(human decision, 2026-11-11)_. Each report loads its data, stills and videos only when opened. Built by `build_search_site.py` into `cache/search/site/`.
  - Size: an artifact version holds 256 MB and at most 511 files (255 a publish). Stills are recompressed and a pair is at most 4 files (page, data with inlined thumbnails, stills sheet, frames for pairs without a video); the overview's image strips are packed 25 to a sheet. The videos go in the artifact's asset store as viewer copies (re-encoded under 18 MB when longer), one per video, and `videos.json` maps each tab to them. A pair without a video keeps its stills and storyboards, and its tab says so.
  - `build_report.py` splits into a page shell and a per-pair renderer, used by both layouts.
- Either way: the overview is republished as pairs move through the filters, built by `build_search_report.py` from `results/search/`; the seed pair is included (its existing report reused); gate-passed pairs without a download get no report, only their row in the overview with the image evidence and the agent's label.

Overview sections:
0. What stood out: the strongest pairs and the surprises (same-day releases, large audience gaps, re-skins within a channel), each linking to its pair report.
1. Filter chain: how many pairs passed each filter and wait in each queue, by pair type; budget used; time to the end.
2. Candidates that passed the gate, by pair type: both thumbnails and auto-frames side by side, screen score, the signals that fired, the agent's label, link to the full pair report where there is one.
3. Channel story, to test "B was built from A's catalog" vs "B was built to test variants":
   - Timeline of B's uploads, each marked re-skin of an A video or not; and the lag to its A version. Within-channel re-skins on the same timeline: does A re-skin its own videos too, before or after B existed? A burst of re-skins of old A videos right after 2014-10-30 reads as catalog reuse; repeated near-same-day releases read as testing.
   - Feedback: does A's later look (thumbnail saturation and lightness over time, free; pipeline features where in the dataset) move toward B's style after B's versions outperform? That would be the strongest evidence of learning from a test.
4. Strategy profiles across all validated pairs (which signals fire how often), and how the agent's labels compare with the full reports.

## Steps

0. Write `tools/yt.py` (budget check + ledger) before any further YouTube request.
1. Score the seed pair on every signal: 2 downloads. This tests the framework.
2. Find the company's other channels: start from Kids Channel's "Our Family" list and check each with the owner signal (API).
3. Search the seed channel pair for more pairs (see Search, above).
4. Later, not this time: extend the search to the company's other channels _(human decision)_.
5. Downloads only for agent-confirmed pairs and a small baseline set (~10 videos), within the search's 200.
6. Strategy profiles per pair and studio.

## Results

**Owner, seed pair** (2026-11-10, 4 API units):
- Same company: both videos' descriptions end in "© 2024 USP Digital Private Limited" and link the same USP Digital app.
- Featured channels: Kids Channel lists an "Our Family" section of 8 channels (and a separate "Featured Channels" section of 9), but not Kids TV; Kids TV lists no channels. So featured channels alone would have missed this pair: the copyright line found it.
- Kids Channel was created 2014-10-30, six days before its version of the video (2014-11-05); Kids TV's version is from 2014-10-18. The re-skinned version may have been among a new channel's first uploads.

**Framework built** (2026-11-10): `tools/yt.py` (budget + ledger), `tools/` signal modules (`align`, `audio`, `visual`, `changes`, `metadata`, `baselines`), `score_pair.py` (all signals → `results/<name>.json`), `build_report.py` (report page; built into `cache/`, since it holds stills). Own uv env in `experiments/` (CPU torch, demucs, DINOv2 via torch.hub). Rerun: download both videos with `tools/yt.py`, cut clips from 0:30 into `cache/clips/` (and the shared part into `cache/clips-shared/`), run the backend pipeline's `extract`/`derive` into `cache/features/`, then `score_pair.py A B --name N` and `build_report.py N`.

**Seed pair, all signals** (2026-11-10; 2 downloads, 6 API units, 199 image requests):
- Alignment: one segment, B = A − 0.60 s, 93.6 s long, same speed. A has 23.8 s more at the end (an end screen).
- Fire: owner (copyright line), thumbnail embedding, storyboard, aligned cuts (12 of 12 on the same frame ± 1), motion (overall r 0.88, characters 0.81, tilt), structure (gray, edges: narrow margins).
- Don't fire: days apart (18 d; same-channel pairs are closer), time of day, title (no shared words after the song name), description, tags, duration (the end screen), thumbnail hash, horizontal pan (none to correlate), frame content (DINOv2 reads forest vs farm; repeated verses inflate the baseline).
- Audio level: **same audio, adjusted**: waveform r 0.998, B 1.0 dB quieter; all four stems r ≥ 0.91, so no new overlay.
- What changed: 64% of the frame redrawn (background), 15% recolored with the same shapes (ducks), 21% unchanged; B more saturated (0.52 → 0.76) and darker (−15 L*). Features on the shared part: same cuts per minute; saturation 131 vs 192, lightness 54 vs 39.
- Audience: B (3D, later, new channel) has 7.7× the views and 3.0× the like rate.
- Profile: same owner, same audio adjusted, same cuts and motion, look-alike thumbnail; new title, recolored, redrawn background, end screen only in A.
- Framework findings: the storyboard alone recovers the offset (−0.5 s; tiles sit at whole seconds, not at yt-dlp's fragment durations) and the cuts, so it can screen candidates without downloads. Download signals use a time-shift baseline (B moved 3–30 s) until baseline downloads exist; the repeated verses make it strict. The dataset has publish dates only, so time of day uses the API sample.

**Search run** (2026-11-11 to 2026-11-12):
- Filters 0–5: 5,887 videos, 4,066 after compilations (30 min); 8.26 M pairs → 350,498 candidates (4.2%) → 9,714 scored above the cut (2.8%) → 5,736 through the gate (59%, plus 65 stopped pairs audited) → 5,799 labelled by the agent. 11,793 image requests, 0 errors.
- Labels (confidence ≥ 0.7 shown in groups): re-skin 227, re-upload 164, same song 368, same template 2,207, shared segments 1,542, unrelated 1,291.
- Downloads: 364 videos of re-skin and re-upload pairs. 127 from the server (stopped at a 403 after 125 in a day), 237 from a laptop on another network (`remote_download.py` → `import_downloads.py`), 0 rejected.
- Overlap (6b): 333 pairs aligned (269 by audio, 64 by frames); 304 share at least half of the shorter video. 25 re-skin pairs and 4 re-upload pairs share little, most only a 2–3 s intro.
- Groups: re-skin 41 groups of 139 videos (largest 11); re-upload 102 of 221; same song 26 of 86; same template 30 of 326 (largest 100, a series); shared segments 251 of 797.
- Full reports: 98 of 98 selected (n − 1 per re-skin group), 0 failed after two fixes (a silent soundtrack crashed the overlap step and the audio step). With frame sampling: mean 14 min a report, peak 5.0 GB for one score step (was ~4 GB a 5-min pair and the cause of the out-of-memory stop).
- Pages: an overview plus one page per label, all private.

## Open questions

- Gate misses, being checked _(human decision, 2026-11-12: the stopped pairs never got a frame-by-frame check)_: every stopped pair the agent hasn't seen gets filter 6b's overlap check on the downloaded videos (`gate_check.py`: 3,913 pairs, 993 videos, 877 to download on the laptop, frame embeddings cached per video). Pairs that share at least half of each video go to the agent to tell re-skins from re-uploads, then on to reports and groups as usual. Stage table in `results/search/gate_check.json` and `gate_check_status.txt`. Done 2026-11-12: 3,912 pairs checked (one pair with a live stream left out: nothing fixed to download); **556 share at least half of each video** (520 same-channel, 516 by audio), another 157 hold one video inside a longer one. They touch 327 videos, 302 not in any group yet; 62 clusters, the largest (108 videos) Rattic Mini's "& More" compilations that reshuffle the same episodes. 26 pairs touch the re-skin or re-upload groups (21 add a video, 2 join two groups). The agent labels the 556 _(human decision, 2026-11-12: go ahead with labelling and the steps after it)_ on the usual sheets plus, per pair, a row of frames from the downloaded videos at matching moments (B time = A time + the check's lag) and the overlap shares in the pair data (`review.py`): sharing the audio alone doesn't tell a re-skin from a different animation of the same song. Labelled 2026-11-12 (7 agents, ~0.7 M tokens): 393 same-template, 107 same-song, 25 shared-segments, **23 re-skin** (19 confident), 7 re-upload, 1 unrelated. Most of the same-template pairs are Rattic Mini compilations that share one background-music track (the audio match isn't shared footage); most same-song pairs are Kaboochi shorts, one song in many animations. Many of the new re-skins are holiday versions (Christmas, Halloween) of shorts. Re-skin groups: 39 → 44 (6 new, 5 grown, two of them merged), 125 → 147 videos; 103 reports (19 new, 2 dropped as the groups' linking pairs changed). The re-skin page's 1 GB asset store was full: the 14 videos no report used any more (removed compilations) were deleted to make room. Pages republished 2026-11-13. The audio-share fix changed the shares of 87 earlier pairs but none crossed a threshold: the groups stay the same.
- Gate misses: the auto-frames sit at fixed shares of each video (¼, ½, ¾), so when one version has a new intro or end screen, they show different moments of the same animation. The gate compares all 3 × 3 frame pairs, and the thumbnail is a second way through, but a shift between those points can still stop a re-skin: the audit found 1 re-skin in 65 stopped pairs (`ZPOOOfJmzp4` / `cMOSJ1QIa3w`), so roughly 60 of the 3,978 stopped pairs (95% range 2–330). The images are cached, so the agent could review all stopped pairs with no new YouTube requests.

- Same subject: is "fill up with the closest videos by title and thumbnail" the right fallback for rare songs and non-song content, and are 10 studios / 30 pairs the right minimums? A free check first: how many dataset videos share their title's subject with at least 10 other studios.

- Baseline size: is ~10 downloaded baseline videos enough for a 99th percentile, or should baselines lean on API and image signals and the dataset's existing features?

