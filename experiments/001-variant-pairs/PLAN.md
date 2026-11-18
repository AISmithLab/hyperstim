# 001: Variant pairs

**Question:** Do studios publish near-identical versions of one video (same animation; new colors, background or title), and is there evidence they test the variants against each other?

**Parts** _(human decision, 2026-11-12)_: 1. quantify how similar the seed pair is (Signal framework, Pair report); 2. search the two seed channels for more pairs (Search: more pairs in the seed channels); 3. search other channels (Search: other channels); 4. does the more stimulating version get more views? (Views and stimulation, proposed) _(human decision, 2026-11-17: part of 001)_.

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

## Search: other channels

_(human decision, 2026-11-12: a third part of 001, built step by step; each step is planned in depth when we reach it)_

**Goal:** a large corpus of **re-skins** across many channels: the same animation with a new look, and with it the variants that keep the animation but change the audio (any sound effect added or removed, such as chuckles; louder or quieter) _(human decision, 2026-11-12)_, the pacing (sped up) or the cuts (scenes added for more cuts per minute) _(human decision)_. Re-uploads, same template, shared segments, same song and **dubs** (same video in another language) are out of scope _(human decision: dubs don't tell us anything about stimulation)_.

**Principles:**
- Within an owner first: pairs are compared only inside an owner group, so results stay comparable with the seed channels. Comparing across owners comes later, as a step of its own (Ideas, below).
- Never all pairs, and no cut-off decided in advance _(human decision, 2026-11-12: pairs are rare, so false negatives are the bigger risk)_: the number of pairs grows with the square of the videos (100 k videos = 5 billion pairs), so steps narrow the candidates without listing every pair, by early decisions that are cheap and keep recall high, not by a fixed cap (a top-k, a share of pairs). Each early decision is measured on what it drops: its recall on known re-skins and an audit sample of the pairs it stops.
- Don't learn only the strategy we've seen: the seed studio's re-skins are one strategy; others may redraw, re-time or re-voice instead. Whatever the found re-skins teach is a way in, never the only one.
- Light enough for scale: API and image signals before any download; nothing that costs a download per video.

### Step 1: Channel discovery and grouping

**Goal:** group the channels we already have by owner, using only the API: which channels belong to one company, how big each group is, and which groups are worth searching. No images, no player requests.

**Channels:** the 662 channels in the dataset (542 in the reference set, 319 collected, 199 in both); Kids TV is among them; Kids Channel is neither in the dataset nor featured by a dataset channel, so the two seed channels are added by hand, for the check. The collector's excluded (not kids-focused) channels stay out.
- **Family channels** too: a channel outside the dataset that a dataset channel features is fetched and grouped as well _(human decision, 2026-11-12)_, so groups show the whole company, not only its channels we happen to have. Featured lists also name friends and partners, so a featured channel joins a group only when other owner evidence confirms it (a shared copyright holder, app or email, both channels featuring each other, or a section named like "our channels" / "family"). Otherwise it is kept as featured only, not grouped. The 662 feature 2,389 channels outside the dataset; most sit in general "Featured Channels" (1,286) or friends sections, ~770 in family sections.
  - A family section names the company's own channels or languages ("Our Channels", "Visit Other Pinkfong Channels", "In More Languages", "Worldwide"), not friends, partners, recommendations or favorites.
- One hop only: channels that only family channels feature are listed as the **frontier** but not fetched; going further is a later step _(human decision: eventually, not now)_.

**Data per channel** (≈ 1,050 API units for the 662; within the 2,000-a-day limit _(human decision, 2026-11-12)_):

| Source | Gives | Units |
|---|---|---|
| `channels.list` (snippet, statistics, brandingSettings, contentDetails) | Description, country, created, keywords, videos and subscriber count, uploads playlist | 1 per 50 channels ≈ 14 |
| `channelSections.list` | Featured channels (`multiplechannels` sections) | 1 per channel ≈ 662 |
| `videos.list` for the dataset's video IDs | Video descriptions (copyright lines, links, apps, emails) | 1 per 50 videos ≈ 360 |

Family channels have no dataset videos, so their evidence is fetched **cheapest first**, and a channel that already has a strong link skips the later stages: (1) `channels.list` for all (1 unit per 50; confirmed 729 of 2,389 from channel descriptions and family sections); (2) `playlistItems` (50 latest uploads) and `videos.list` for their descriptions, 2 units a channel, the most-featured first; (3) the channel's own `channelSections` (a mutual feature), 1 unit. About 3,300–4,500 units, so the fetch may need a second day; it waits for each new Pacific day by itself. It runs on the experiments' own key and project, within their 9,500 a day (experiments README, YouTube budget) _(human decision, 2026-11-12; first 2,000, then 2,500 a day of the site's key)_, so it should finish within a day.

All responses are saved (by `tools/yt.py`, in `cache/api/`); reruns cost nothing. Script: `channels.py fetch` (the requests, resumable) and `channels.py group` (offline, rerun at any time).

**Evidence and links** (from `owner_evidence` in `tools/metadata.py`, which 001 already uses):
- Strong: one channel lists the other in a section named like "our channels" / "family" (not "friends", "partners", "channels we love", "other great channels", "related"); a shared copyright holder; a shared app ID; a shared email.
- Weak: a feature in a general "featured channels" section, one-way or mutual (changed 2026-11-12: with the family channels' own sections fetched, friends that feature each other chained CBBC, CBeebies and Sesame Street into one group of 159, and Masha into Cleo & Cuquín); a shared domain (not a social, shortener or merch host); similar channel names (one name contains the other).
- A value counts for a channel only when it is in the channel's description or in at least two of its videos' descriptions: a credit in one video (a guest, a song licensor) doesn't name the owner. Copyright holders are compared without company suffixes ("Pvt. Ltd."); legal boilerplate ("respective owners", "Section 107") is dropped.
- Evidence that unrelated channels share (e.g. a music licensor's copyright line, a distributor's or network's domain) marks a **network**, not an owner: such values are kept apart, listed with their channels, and don't link channels by themselves. They are interesting in their own right (a network or channel-building service behind many channels). Rule: holders named together in one channel's descriptions count as one company (a rename such as USP Studios → USP Digital; an owner and the studio it bought); a value is a network when its channels' holders form two or more unrelated companies, unless (for a copyright holder) most of its channels name it first.

**Groups:** connected channels over strong links. An agent checks, from the saved responses (descriptions, featured sections, video titles; no page requests), groups held together by a single link, groups larger than ~10 channels, and channels linked only by weak evidence. A "single link" is one whose removal splits the group into two parts of 2+ channels each, counted on the graph of channels and evidence values (each shared holder links each of its channels to the value; counting channel-to-channel links instead made every holder link look single). Language channels (dubs) stay in their group but are marked, so later steps can skip them.

**Output:** `results/channels/` (`channels.tsv`, `links.tsv`, `groups.tsv` and `groups.json`: group, channels, evidence per link, videos, subscribers, languages, flags; `networks.tsv`; `frontier.tsv`), and a private artifact page: the groups ranked by size, each link's evidence, the networks and the frontier count.

**Check:** Kids TV and Kids Channel must land in one group, by the copyright line, together with the "Our Family" channels confirmed as the same owner (dubs marked).

### Step 2: Learn from the seed re-skins

**Goal:** use part 2's labelled pairs to design the screen for many channels as a **cascade of cheap classifiers**, each tier using only what is cheaper than the next, so downloads go only to pairs that are very likely re-skins. Main question _(human decision, 2026-11-12)_: how much can metadata and images (no download) rule out, at what loss of re-skins?

**Resources** _(human decision, 2026-11-12)_, scarcest first; each tier spends a cheaper one to save a scarcer one:

| Resource | Supply | Use |
|---|---|---|
| Downloads (player requests) | Tight: 50 a day, a run's own budget when agreed | Only for pairs the cascade is confident about |
| Agent tokens | Some to burn; a few 5-h cycles are fine, but **ask before using up a whole cycle or the next ones** (the user may be saving tokens for other work) | The uncertain band between the classifiers' cut-offs, and audits |
| Image requests | No known limit, but ~1 a second: the **time** bottleneck (2 images × 100 k videos ≈ 2.3 days) | Videos the metadata tier can't rule out |
| API units | Loose: 9,500 a day (1 unit = 50 videos' metadata) | Metadata for every video |
| CPU | Mostly idle (8 cores, 29 GB); keep memory well clear of the limit | Pair features, embeddings, classifiers |

**Where it sits:** every tier is **before the download**: the cascade replaces filters 2–4 (candidates, score, gate) and shrinks filter 5 (agent), so only likely re-skins are downloaded. After the download nothing changes: the overlap step (6b) and `score_pair.py`'s full report confirm each pair.

**Tiers** (as built; each screen only rules pairs out, at a cut-off set from recall on the re-skins):

| Tier | Inputs | Cost | Trained against | Cut-off |
|---|---|---|---|---|
| M. Metadata screen | Title (char n-grams after boilerplate; shared words), description, tags, duration (log ratio, fit with an end screen, shorter length), days apart, pair type | API only | Random pairs (plus labelled look-alikes) | 98 % of same-length re-skins |
| I. Thumbnail screen | M's + thumbnail embedding and outline (I1); with the middle frame too (I2), the better of the two is used | 1 (or 2) images a video | Same | 97 % overall, with M |
| L. Look-alike model | M's + thumbnail + middle frame (embedding, outline, thumbnail against frame); gate frames (¼, ¾) compared | 1 more image, only for videos in I's survivors | Everything that survives M and I: look-alikes, re-uploads, unlabelled pairs | Orders the survivors; the agent reads down to the cut for a recall target (95 %) |
| A. Agent | Sheets of 10, as filter 5 | Tokens | | Its label decides the download |
| D. Download | Agent-confirmed re-skins | Downloads | | |

Screens use logistic regression: boosted trees rule out a little more, but fall off a cliff (keeping nearly every pair) when a few hard pairs move, as adding the audit's 686 look-alike labels showed. Cut-offs at 98 %, not 99 %: with ~150 re-skins, 99 % is set by a single pair. Boosted trees for the look-alike model, where linear models can't separate re-skins from look-alikes. The base fit uses part 2's labels only; `--with-audit` adds the audit's.

No tier sends pairs straight to download: images and metadata can't tell re-skins from series episodes and same-song versions with the precision a download needs, so the agent stays the last check.

**Medleys:** a re-skin where one video is at least twice as long (a short song re-skinned inside a medley) is a different strategy: duration and title don't match by design. Cut-offs are set on same-length re-skins; medley recall is reported at each cut.

**Classifiers** _(human decision, 2026-11-12: simple, light, no GPU)_: logistic regression and gradient-boosted trees (scikit-learn's histogram version) on a few dozen pair features; a depth-limited tree as a readable check. They train in seconds on CPU. scikit-learn is listed in `experiments/pyproject.toml` at the version already in `uv.lock` (1.9.1) _(human decision, 2026-11-12)_. **No GPU:** the only heavy model is the DINOv2 embedding, which kept up with image requests on 2 CPU threads in part 2, so image requests, not compute, set the time; a GPU would not turn days into hours here.

**Data:** offline, no requests. `cache/search.db` (5,887 videos with metadata; the 350 k candidate pairs with signals, labels, overlap), `cache/search/*.npz` (thumbnail and middle-frame embedding and outline per video), `results/search/` (calibration, labels).
- Labels as they are now _(human decision, 2026-11-12: some are wrong and being fixed in another session, but accurate enough; rerun with the fixed labels later, results shouldn't shift much)_. Read fresh on each run: a rerun is one command.
- Positives: re-skin pairs (confidence ≥ 0.7) that pass the overlap step (6b), 165 (151 same-length, 14 medleys). Re-uploads (144) are a separate class, reported apart (easier; they would inflate recall).
- Negatives: the other labels (hard negatives), plus random unlabelled pairs of each type (re-skins are ~1 in 50 k pairs, so random pairs are negatives with few errors).
- Pair features are computed for **all 8.26 M pairs** (metadata vectorized, image features from the saved embeddings, in chunks), so ruled-out rates are measured on every pair, not only candidates.
- Cross-validation by video group (connected videos in one fold, so near-copies don't leak); cut-offs chosen inside the training folds.
- **Bias:** labels exist only where part 2's chain found a pair, so recall is recall among findable pairs. The audit estimates the rest.

**Analyses:**
1. **Metadata alone (M):** share of pairs and of videos ruled out at 99 %, 98 % and 95 % recall; which features carry it; the re-skins it loses and why (e.g. new title with no shared words).
2. **Images (I, G):** the same on M's survivors, for thumbnail only (1 image) vs thumbnail + middle frame (2); and what the ¼ and ¾ frames add. Which re-skins only one signal finds (signals not to drop).
3. **Narrowing without listing pairs:** for channels too big to pair in full, a radius search per signal (every neighbour closer than a radius set from recall on the positives) and blocking keys (title subject, duration), with recall and candidates per video. Exact search in numpy at this size.
4. **Cascade against the hand-set chain:** recall, agent sheets and downloads per 1,000 videos, against part 2's score and gate on the same pairs; and the cost of a 10 k-video group in API units, image hours, sheets, download days.
5. **Recall audit** (tokens): pairs the cascade or part 2 would drop, labelled by the agent from saved images (thumbnail and middle frame; gate frames where fetched), strata mixed on each sheet: 150 just below each of the three cut-offs (metadata, thumbnail, look-alike), 150 part 2 non-candidates with the highest single signal, 100 random non-candidates; 700 in all. Re-skins found go back into 1–4. ~70 sheets, likely well within one 5-h cycle (part 2's ~580 sheets took more than one); checked with the user before it starts.

**Generalization:** all labels come from one studio (USP), so the cut-offs fit its way of re-skinning. They are a starting point, checked on a second owner group (e.g. Moonbug) before they set that group's cut-offs.

**Output:** `learn.py` (`features`, `fit [--with-audit]`, `audit sample|next|check|results`, `report`; page template `learn_report.html`), tests in `tests/test_learn.py`; `results/learn/` (`fit.json`, `fit_with_audit.json`, `audit/`; the 8.26 M-pair feature table and scores stay in `cache/learn/`); a private artifact page: what each tier rules out and loses, the lost re-skins with their thumbnails, cascade vs hand-set chain, cost table, and a recommendation for the next step.

### Ideas for the next steps (not built yet)

- **Which groups to search:** screen a sample of each group (e.g. its most-viewed videos, 1 image each), count re-skins, and search high-yield groups in full. Yield is likely heavy-tailed: a few big studios may give most of the corpus. Step 2 sets the images per video and the candidate rule.
- Audio or whole-video inputs need a download per video, so they can't go into the screen at scale; they belong after the download, where 001's framework already scores audio levels, speed, added cuts and added parts.
- **Across owners:** the same comparison between groups, with its own baseline class (different owner), as a separate step. Interesting because of channel farms (e.g. channels built by AI agents and sold as "passive income") copying successful videos.
- **Beyond our channels:** grow from the frontier (featured channels), and from the networks' and copyright holders' other channels.

## Views and stimulation (2026-11-17)

**Question:** within a re-skin family (same animation, same audio, same cuts), does the more stimulating version get more views? The earlier paper compared unrelated videos; a family is a matched set, like siblings in a twin study, so content, song, pacing and (mostly) channel are held fixed.

**What "more stimulating" can mean here:** re-skins keep cuts and motion, so the treatment is mainly visual: color saturation (the site's visual intensity), lightness, plus loudness (re-skins often re-mix the gain). Pacing measures are a placebo: they should not differ.

**Pilot (2026-11-17, existing data, 0 requests):** 44 re-skin families, 147 videos, all with saturation and views; 176 pairs differ by ≥ 5 in saturation (34 families, 166 of the pairs within one channel). In 23 of 34 families the more saturated version has more views (sign test p = 0.058); median ratio 1.22×. The more saturated one is the later one in 77 of 176 pairs, so order and saturation aren't the same thing. Exploratory only: the user spotted the pattern on these families, so they can't also confirm it.

**Decisions:**

1. **Hold-out.** USP families = exploratory (fit the model, choose the measure). The confirmatory test runs on families from part 3 (other studios), with hypothesis, measure, model and exclusions written here before their views are looked at.
2. **Measures:** three, each tested on its own, none primary and no composite: mean saturation, mean lightness (L*), loudness (LUFS). Holm correction across the three _(human decision, 2026-11-17)_.
3. **Outcome:** log total views, with an age control _(human decision, 2026-11-17: total views only; no daily fetch over a window; first weeks after release can't be had, YouTube shows no view history to non-owners)_.
   - Views as saved by the search run (2026-11-11/12); age = days from publish to that fetch (the cached response's time), per video. Part 3's families use their own fetch date. No new requests.
   - **Expected views** take age and era together: the median log views of the channel's other videos published within ±90 days, in the same length class (up to 4 min, longer), compilations and family videos left out; the window doubles until it holds 10. The outcome is log views − expected. Within a family the later version is always the younger one, and that holds in re-upload families too, so neither can give the age curve; the channel's other videos can. _(Changed while building: the plan had the curve from the re-upload families.)_ This also replaces the year bands and the channel term.
   - **Shorts** count views differently (every play since 2025-03), so a family mixing Shorts and long videos is compared within format only, or left out. Length can't tell them apart (40 of 44 re-skin families are 3 min or shorter); the downloaded files' aspect ratio can (vertical = Short), with no requests.
   - **Holiday versions** (Christmas, Halloween, and other holiday words in the title) gain mostly in season: a holiday flag in the model.

**Model** (video *i* in family *g*):

`log(views_ig) − expected_ig = α_g + β·stim_ig + δ·later_ig + h·holiday_ig + ε_ig`

- α_g: family fixed effect (absorbs song, animation, studio). Only within-family differences estimate β.
- later: not the first-published version in the family (the "later version won" pattern).
- Standard errors clustered by family (CR1). With ~150 videos, few terms; add one only if it's decided before the fit.
- **Test:** a within-family permutation test of β (shuffle the measure among a family's versions, 10,000 times), Holm across the three measures; the regression's t-test as a check. Intervals: 2,000 family resamples.
- **Pairwise form** (easier to read): for each pair, P(higher version has more views) = logistic(Δexpected + β·Δstim + δ·Δlater + h·Δholiday), no intercept, each family weighted once. Reported as an odds ratio per step.
- **Heterogeneity:** a random slope per studio once there are ≥ 3 studios with ≥ 10 families.

**Negative controls:**

- **Re-upload families** (100 after the format split; nothing changed): the within-family spread of views around expected is the noise floor (channel, timing, luck).
- **Placebo measure:** cuts per minute, which re-skins share; its β should be ≈ 0.

**Threats** (stated, not all fixable):
- **The studio chooses.** A studio may re-skin a hit into a newer, brighter style, promote one version (playlists, end screens, compilations), or delete the losers (we only see survivors). The design shows association within a family, not cause.
- **Thumbnail and title** change with the re-skin and drive clicks; the design can't tell whether an effect runs through the thumbnail or the video. Not measured _(human decision, 2026-11-17: no thumbnail saturation measure)_.
- **Measurement window:** a video's features come from the dataset's clip where it is in the dataset, else from its pair report's shared part, so two versions of one family can be measured on different stretches.
- **Power:** see the results; part 3's other studios are what make this a test rather than an anecdote.

**Built** (2026-11-17; 0 requests): `views_model.py run` (fit → `results/views/model.json`, ~3 min on CPU) and `views_model.py page` (`views_page.py` with the template `views_report.html` → `cache/views/index.html`, a private page); tests in `tests/test_views_model.py`. numpy and scipy only.

**Results, USP (exploratory, 2026-11-17):** 44 re-skin families, 147 videos (no family mixes Shorts and long videos; 56 videos are Shorts).

| Measure | Views per step | 95% interval | p (permutation) | p (Holm) |
|---|---|---|---|---|
| Saturation, per 10 points | 1.18× | 0.95–1.44 | 0.200 | 0.600 |
| Lightness, per 10 L* | 1.29× | 0.78–2.15 | 0.327 | 0.600 |
| Loudness, per 3 dB | 1.21× | 0.89–2.07 | 0.219 | 0.600 |
| Cuts per minute (placebo), per 5 | 1.12× | 0.74–1.79 | 0.735 | – |

- All three point the same way (more stimulating, more views); none passes. The pairwise form (who has more views, ignoring by how much) gives saturation 1.54× odds per 10 points (1.05–2.30), lightness 1.85× (0.70–7.6), but loudness 0.63× (0.25–1.28): loudness's sign isn't stable. With the placebo as wide as the real measures, this run can't tell an effect from noise. A window of ±180 days gives the same ratios (1.16×, 1.30×, 1.26×).
- **Noise floor:** views around expected spread ~2.6× inside a re-skin family and ~2.9× inside a re-upload family: re-skins vary no more than unchanged copies.
- **Later versions:** 0.68× expected in re-skins (p 0.21), 0.50× in re-uploads (p 0.011). In raw views a later version beats its family's first in 32 of 103 (re-skins) and 31 of 116 (re-uploads): the winners noticed on the page are the minority. Likely reason: studios re-release hits, so the first version is a proven success.
- **Power** (chance to pass Holm's strictest level, p < 0.017, if these effects are true): saturation 34% at 100 families, 47% at 150, 65% at 200; lightness 11% at 100, 31% at 200; loudness under 10% at any size up to 200. A clear answer for saturation needs ~300 families.

**Confirmatory test** (fixed 2026-11-17, before any other studio's views are looked at):

- **Data:** re-skin families found by part 3 in other owner groups (not USP), labelled by the agent as re-skin with confidence ≥ 0.7, compilations out, 2 or more versions with views and all three features; Shorts and long videos split by the downloads' aspect ratio. Views and fetch time from that group's own `videos.list` responses.
- **Hypotheses** (one-sided in what they claim, two-sided in the test): H1 more saturated, H2 lighter, H3 louder versions get more views than expected for their age, within a family.
- **Model, test, controls:** exactly as above (`views_model.py`, its constants unchanged: ±90-day window, 4-min length class, 10,000 permutations); Holm across H1–H3 at α = 0.05. The placebo and the noise floor are reported but don't gate.
- **Run when** there are ≥ 150 families outside USP; before that, families are counted but their results not opened. If part 3 can't reach 150, report what there is as a second exploratory set.
- **Report** every measure's ratio and interval whatever the p-value; any change to the analysis after this date is listed as a deviation.

**Steps:**

1. ✓ `views_model.py` with tests; run on USP (results above).
2. ✓ Confirmatory test written (above); run once part 3 has ≥ 150 families outside USP. `views_model.py` reads USP's search database for now; it gets a source per owner group when part 3's searches exist.
3. ✓ Private page: estimates, versions inside each family, noise floor and order, power, all families.

## Steps

0. Write `tools/yt.py` (budget check + ledger) before any further YouTube request.
1. Score the seed pair on every signal: 2 downloads. This tests the framework.
2. Find the company's other channels: start from Kids Channel's "Our Family" list and check each with the owner signal (API).
3. Search the seed channel pair for more pairs (see Search, above).
4. Search other channels, step by step (see Search: other channels, above) _(human decision, 2026-11-12: was "later, not this time")_. First: channel discovery and grouping; then, alongside it, learn from the seed re-skins (step 2, offline).
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

**Channel groups** (2026-11-12, part 3 step 1; fetch done: ~6,200 API units over two Pacific days, the last ~3,700 on the experiments' own key; no images or downloads; `channels.py`, page built by `build_channels_report.py`):
- 3,034 channels: the 662 dataset channels, 2,371 family channels they feature (outside the dataset), and Kids Channel added by hand. Family channels confirmed cheapest first: 729 by channel descriptions, more by video descriptions; 1,102 stay **featured only** (no evidence beyond being featured).
- **521 groups, 124 with 2 or more channels**; 23 network values. Largest: USP (263 channels, 41 in the dataset, most of them language channels), Moonbug (148, 43), a fairy-tales language network (60, 33), Pinkfong (52), Super Simple (41), PAW Patrol (35), Masha (33), BabyBus (32), Animaj with Pocoyo, Maya the Bee and HeyKids (29), Kids Planet (26).
- **Seed check passes:** Kids TV and Kids Channel are in one group (USP).
- USP files under two names, "USP Studios" and "USP Digital": holders named together in one channel count as one company, so they merge.
- Review of the 14 single links (7 groups), done by hand from the saved data: likely right: Animaj (Pocoyo's app is registered to Animaj), Booba (shared email), Pinkfong, ZeeKay with Mister Maker and Totally Spies. **Wrong:** G037 (Cartoon Network, Cartoonito, Netflix Jr., Lucas the Spider: distributors list licensed shows in family sections). **Doubtful:** G032 (Wizz, Me Too!, Baby Jake) and G018 (First Toons, HopHop). Not yet cut: Open questions.
- The frontier (channels the family channels feature, not fetched) is 2,369.

**Search run** (2026-11-11 to 2026-11-12):
- Filters 0–5: 5,887 videos, 4,066 after compilations (30 min); 8.26 M pairs → 350,498 candidates (4.2%) → 9,714 scored above the cut (2.8%) → 5,736 through the gate (59%, plus 65 stopped pairs audited) → 5,799 labelled by the agent. 11,793 image requests, 0 errors.
- Labels (confidence ≥ 0.7 shown in groups): re-skin 227, re-upload 164, same song 368, same template 2,207, shared segments 1,542, unrelated 1,291.
- Downloads: 364 videos of re-skin and re-upload pairs. 127 from the server (stopped at a 403 after 125 in a day), 237 from a laptop on another network (`remote_download.py` → `import_downloads.py`), 0 rejected.
- Overlap (6b): 333 pairs aligned (269 by audio, 64 by frames); 304 share at least half of the shorter video. 25 re-skin pairs and 4 re-upload pairs share little, most only a 2–3 s intro.
- Groups: re-skin 41 groups of 139 videos (largest 11); re-upload 102 of 221; same song 26 of 86; same template 30 of 326 (largest 100, a series); shared segments 251 of 797.
- Full reports: 98 of 98 selected (n − 1 per re-skin group), 0 failed after two fixes (a silent soundtrack crashed the overlap step and the audio step). With frame sampling: mean 14 min a report, peak 5.0 GB for one score step (was ~4 GB a 5-min pair and the cause of the out-of-memory stop).
- Pages: an overview plus one page per label, all private.

**Step 2: learn from the seed re-skins** (2026-11-12; offline, 0 requests; `learn.py`, a private page from `learn.py report`; labels as of 2026-11-12, before the other session's fixes):
- Classes: 165 confirmed re-skins (151 same-length, 14 medleys), 144 re-uploads, 5,408 other labels, 8.26 M pairs of 4,066 videos. Features for all pairs take 26 s (1.4 GB peak); each fit ~10 min on CPU. No GPU needed.
- **Metadata alone** (logistic regression, cut at 98 %) keeps 173,838 pairs (2.1 %) with 148 of 151 same-length re-skins: it rules out ~98 % of pairs. Re-skins share title words, have nearly the same duration and are under ~10 min. Within one studio it saves almost no images: 3,961 of 4,066 videos are still in a kept pair.
- **Adding the thumbnail** (cut at 97 % overall) keeps 70,707 pairs (0.86 %) with 147 of 151.
- **Look-alike model** (boosted trees on the survivors) orders the agent's list: 1,701 pairs for 90 % (136 of 151), 4,983 for 95 % (144), 32,029 for 97 % (147). Top 50: 37 re-skins, 5 re-uploads, 4 look-alikes, so nothing goes straight to download. Downloads for 95 %: 126 videos (3 %), against part 2's 364 (9 %, re-uploads included). Agent sheets at 95 %: 499, about part 2's 583; at 90 %: 171.
- **Gate frames (¼, ¾):** on the 38,699 survivor pairs that have them, the boosted model's list at 95 % is 2,165 with them against 2,281 without; at 98 % 4,809 against 3,636. They help the linear model only. An earlier fit (before the fix below) showed a 3× gain that did not hold up.
- **Narrowing:** shared title words (Jaccard ≥ 0.267) catch every re-skin within 179 k pairs (88 neighbours a video); single image signals don't narrow; the frame embedding at 98 % gives 49 neighbours a video.
- **Recall audit** (700 pairs on 70 sheets, 7 agents, ~110–145 k tokens each): re-skins found below the metadata cut 1 of 150 (a medley), below the image cut 0 of 150, below the look-alike cut 5 of 150 (one at 2× speed), high single signal 3 of 150 (all medleys), random 0 of 100 (≤ 3.6 %, 95 % interval). None of the 9 had been found by part 2. The agents also flagged 4 likely pairs outside the sample, not yet checked.
- **Medleys:** 14 of 165 re-skins and 4 of the audit's 9; the screens keep 6–8 of the 14 by chance. They need their own route (Open questions).
- **Instability:** adding the audit's 686 look-alike labels made the boosted screens keep ~99 % of pairs, and logistic regression at 99 % kept 7.8 M: with ~150 positives, the last few re-skins set the cut. Hence logistic screens, 98 %/97 % cut-offs and the base fit on part 2's labels only. With the audit's labels (`--with-audit`) the agent's list at 95 % grows to 7,796 pairs: the cut-offs move with a few unusual re-skins.
- To redo once the label fixes and the gate check land: `learn.py fit`, `fit --with-audit`, `report`.

## Open questions

- Step 2, medleys: 14 of 165 re-skins and 4 of the audit's 9 are a song re-skinned inside a longer video; the screens lose most of them by design. A route of their own (a short video's thumbnail or middle frame against any frame of a long video with shared title words), or leave them for later?
- Step 2, gate frames: skip the ¼ and ¾ frames in the screen and fetch them only for the agent's sheets? With the fixed screens they barely shorten the best model's list (Results, step 2), and they would cost 2 more images for ~90 % of videos.

- Sped-up copies _(human decision, 2026-11-13: show the 2x videos next to their 1x originals, with their stats, on a page of their own)_: `speed.py` takes the videos titled as sped up (X2 / 2x speed: 7, all Kids TV's Wheels on the Bus, 2024–2025) and matches each against same-song candidates played at 2x (every second frame embedding, then the frame check), comparing frames at matched moments pixel by pixel: each moment takes the closest 1x frame within ±1 s, since the alignment's lag can be off by a frame step (median difference ≤ 10 of 255 = the same picture; matches came out at 2–8, the next-best candidates at 19 or more, re-skins at 20–60). After 124 more candidate downloads (2026-11-13, 123 on the laptop; 2026-11-14, KpIs4qf6HQ0 on the server, after it failed on the laptop), **6 of the 7 are matched**: exact 2x copies of four Baby Bao Panda videos (pink K71QjqJlAI0, also played three times in a row in uwnBzV6vNZs; yellow 8-93_TmkKfc; orange yCSjhx5qiv0; red k3vCYP_aQ3w from 2018), and the Christmas ride, whose 1x picture was found only inside a compilation published a year after it (HIQBjbLrMYU), so its views aren't compared. The 2x short vvaQBakslQw has no match among all its candidates. Each match gets a full report _(human decision, 2026-11-14: the page should have the reports as well)_: the 1x video against the 2x copy slowed to 1x (picture and sound, ffmpeg; a copy that plays the song several times is cut to its first time), so every signal compares the same moments, and the report says so in its lead (`speed.py reports`; `prepare_pair.py` and `score_pair.py` take the slowed file as `--b-file`, keeping its clips and features in the pair's own folders, and the site's measures leave these reports out, since a slowed copy's cuts per minute aren't the real video's). A family with two or more copies (the pink one) also gets the all-versions report, its copies played slowed. Slowing can't undo the speed-up exactly: the copies keep the original's pitch (sped up by time-stretching, so slowing uses ffmpeg's `atempo`), but stretching twice with two tools changes the waveform (correlation ≈ 0, fingerprint 1.5%; the spectrum still matches, 0.91–0.94 against a baseline p99 of 0.27–0.39), and the slowed frames fall between the original's, so moving parts read as changed (ΔE 11–15 on five of six, with saturation, lightness and hues the same). The audio level ("re-recorded") and the color and shape changes are therefore artifacts here: `score_pair.py --slowed` marks such a pair, and its lead claims neither. Page: `speed.py page` → `cache/search/site/speed/`; videos in the page's own asset store.
- Gate misses, being checked _(human decision, 2026-11-12: the stopped pairs never got a frame-by-frame check)_: every stopped pair the agent hasn't seen gets filter 6b's overlap check on the downloaded videos (`gate_check.py`: 3,913 pairs, 993 videos, 877 to download on the laptop, frame embeddings cached per video). Pairs that share at least half of each video go to the agent to tell re-skins from re-uploads, then on to reports and groups as usual. Stage table in `results/search/gate_check.json` and `gate_check_status.txt`. Done 2026-11-12: 3,912 pairs checked (one pair with a live stream left out: nothing fixed to download); **556 share at least half of each video** (520 same-channel, 516 by audio), another 157 hold one video inside a longer one. They touch 327 videos, 302 not in any group yet; 62 clusters, the largest (108 videos) Rattic Mini's "& More" compilations that reshuffle the same episodes. 26 pairs touch the re-skin or re-upload groups (21 add a video, 2 join two groups). The agent labels the 556 _(human decision, 2026-11-12: go ahead with labelling and the steps after it)_ on the usual sheets plus, per pair, a row of frames from the downloaded videos at matching moments (B time = A time + the check's lag) and the overlap shares in the pair data (`review.py`): sharing the audio alone doesn't tell a re-skin from a different animation of the same song. Labelled 2026-11-12 (7 agents, ~0.7 M tokens): 393 same-template, 107 same-song, 25 shared-segments, **23 re-skin** (19 confident), 7 re-upload, 1 unrelated. Most of the same-template pairs are Rattic Mini compilations that share one background-music track (the audio match isn't shared footage); most same-song pairs are Kaboochi shorts, one song in many animations. Many of the new re-skins are holiday versions (Christmas, Halloween) of shorts. Re-skin groups: 39 → 44 (6 new, 5 grown, two of them merged), 125 → 147 videos; 103 reports (19 new, 2 dropped as the groups' linking pairs changed). The re-skin page's 1 GB asset store was full: the 14 videos no report used any more (removed compilations) were deleted to make room. Pages republished 2026-11-13. The audio-share fix changed the shares of 87 earlier pairs but none crossed a threshold: the groups stay the same.
- Gate misses: the auto-frames sit at fixed shares of each video (¼, ½, ¾), so when one version has a new intro or end screen, they show different moments of the same animation. The gate compares all 3 × 3 frame pairs, and the thumbnail is a second way through, but a shift between those points can still stop a re-skin: the audit found 1 re-skin in 65 stopped pairs (`ZPOOOfJmzp4` / `cMOSJ1QIa3w`), so roughly 60 of the 3,978 stopped pairs (95% range 2–330). The images are cached, so the agent could review all stopped pairs with no new YouTube requests.

- Same subject: is "fill up with the closest videos by title and thumbnail" the right fallback for rare songs and non-song content, and are 10 studios / 30 pairs the right minimums? A free check first: how many dataset videos share their title's subject with at least 10 other studios.

- Baseline size: is ~10 downloaded baseline videos enough for a 99th percentile, or should baselines lean on API and image signals and the dataset's existing features?

- Channel groups: cut the wrong join in G037 (Cartoon Network / Netflix Jr. / Lucas the Spider) and decide the doubtful G032 and G018, with a short list of cut links in `channels.py`? Or leave them, since a distributor's group only widens the later sampling a little?

- Views and stimulation: the confirmatory test runs at ≥ 150 families outside USP, where saturation's effect (if it is as large as USP's) passes only about half the time; wait for ~300 instead, which may take several owner groups' searches?
