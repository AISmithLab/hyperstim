# 001: Variant pairs

**Question:** Do studios publish near-identical versions of one video (same animation; new colors, background or title), and is there evidence they test the variants against each other?

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
2. Inspection sheet: every signal of the framework as one row, grouped by category, with a verdict (same: the signal fires; different) and a short finding; same rows are tinted yellow _(human decision)_, and each row links to its deep dive. Rows under "What changed" use a stated plain rule (e.g. same below 10 ΔE).
3. Frame-by-frame viewer: the two downloads play in sync (A is the clock, B follows at the alignment offset), with sound from A, B, both or off; frame and cut stepping; timeline tracks for alignment, cuts, loudness of A and B, audio match, motion, outline match and changed area.
4. Deep dives: signals against baselines, owner/titles/tags, colors and changed parts, audio levels, features and audience.
5. Method notes sit in (i) tips next to what they explain, not in a section of their own.

The page carries the two 360p downloads so they can play: keep it private to the team.

## Search: more pairs in the seed channels

**Goal:** find every re-skinned pair in Kids TV (A, 4,736 videos, since 2013) and Kids Channel (B, 1,150, created 2014-10-30), without scoring all pairs, and with no single signal (title) as the gate. Three **pair types**, searched in the same run: A×B (5.4 M pairs), A×A (11.2 M) and B×B (0.66 M) _(human decision, 2026-11-11: within channels too)_; 17.3 M in all.

Within a channel, look-alikes come from more than reuse: a shared channel template (intro, logo, characters), episodes of one series, re-uploads and compilations. So:
- Every threshold and percentile is computed **per pair type**, against random pairs of that type (a random A×A pair already shares the template).
- **Compilations** (longer than 10 min, or titles like "compilation", "collection", "1 hour") stay out of pairs _(human decision)_: they contain other videos rather than vary them. Counted in the report, left for later.
- The agent also labels **re-upload** (same video, nothing changed) apart from re-skin.

**Constraints** _(human decision)_: results within half a day, in one run of a few hours; API units as needed (the 2,000-a-day limit doesn't apply to this search); up to **200 player requests in one day** for this search _(human decision, 2026-11-11; accepted though 121 in 24 h caused the first block)_: downloads stop at the first failed one, and while the collector is blocked. Image requests paced at 2 a second, one at a time _(human decision: be friendly to their servers)_. Storyboards need a player request, same as a download, so the gate can't use them: it works from API and image signals, and downloads go to the pairs the agent confirms.

Funnel: each stage passes only some pairs on to the next, which costs more per pair; everything is saved to `results/search/`, so reruns cost nothing. Expected sizes: all 17.3 M → recall ~60–100 k → rank ~5 k → gate ~200–800 → agent confirms → download ≤ ~100.

| Stage | What | Cost |
|---|---|---|
| 0. Inventory | All uploads of both channels: `playlistItems` (page tokens saved), then `videos.list` for title, description, tags, duration, publish time, stats | ≈ 240 API units |
| 1. Recall | Each video gets its top-k videos, of each pair type it is in, from **several independent lists**, unioned: title subject (char n-gram TF-IDF after removing channel boilerplate like "3D", "Nursery Rhymes"); thumbnail embedding (DINOv2, as in the seed); thumbnail outline (edge map, catches recolors); middle auto-frame (YouTube's `hq2.jpg`, a frame it takes at ½ of every video, separate from the custom thumbnail; `hq1`/`hq3` at ¼ and ¾ are fetched in stage 3 for candidates only, if these frames exist for these videos). A pair can enter through any one list. k ≈ 10 per list | thumbnail + `hq2` × 5,886 videos ≈ 11.8 k image requests (~1.6 h at 2 a second), stopping at the first 429 or run of errors; embeddings ~30 min CPU; the extra pair types cost no extra images |
| 2. Rank | One screen score per pair from the image and API signals (auto-frame outline similarity, thumbnail similarity, title subject, duration fit allowing an end screen, publish order), each as a percentile against random pairs of its type, as in the signal framework. Keeps the top ~5,000 pairs (split across types by how many of each pass the 99th percentile) plus each video's best 2, with the cut set so the seed pair passes with margin | local |
| 3. Gate (automatic) | For the ranked candidates: all 3 × 3 auto-frame pairs (positions differ when one version has an end screen, and verses repeat) on outline SSIM, plus thumbnail and API signals, each against random pairs of its type. A pair passes when an image signal beats the 99th percentile; the rest stop here. A random sample of the stopped pairs goes on as an audit of what the gate misses | `hq1` + `hq3` for the candidates' videos: up to ~8 k image requests (≤ 1.1 h) |
| 4. Agent review | Only pairs that passed the gate _(human decision: tokens are plentiful but gated first)_: an agent looks at a side-by-side sheet (both thumbnails + auto-frames, the signals that fired) and labels each: re-upload / same animation re-skinned / same song, different animation / unrelated, with a confidence. Catches what the signals miss (redrawn background, same characters) | tokens |
| 5. Download | Only the most suspicious: agent-confirmed re-skins with the highest confidence, most different strategy profiles first _(human decision)_, one queue across pair types, with at least ~20 pairs of each type that has them _(human decision)_. Downloads and `score_pair.py` + `build_report.py`, up to 200 player requests (~100 pairs, fewer when videos repeat), plus ~10 baseline videos. Also tells how well the agent's label agrees with the full signals | ≤ 200 player requests |

Seed pair check first: stages 1–2 must rank the seed pair near the top, and the auto-frames must exist for 2014 videos (6 image requests). If they don't, the recall and the gate fall back to thumbnails and API signals, and the plan comes back for review.

**Run:** one session of a few hours (stages 0–4 ≈ 4–5 h, mostly paced image requests); stage 5 starts as soon as the first pairs are confirmed, so the day ends with full reports. Progress goes to the search report as stages finish. No multi-agent orchestration for discovery: it is deterministic scripts; the agent is used only where judgment pays (stage 4).

**Scope:** the seed channel pair only _(human decision, 2026-11-11)_. Kids Channel's "Our Family" lists 8 more (1 API unit): Kids Channel - Cartoon Videos for Kids (US, 2,784 videos) and 7 language channels (461–2,405 videos each; likely dubs, a separate localization question). All 10 would be 15,174 videos, ≈ 610 API units and 2.6× the image requests; left for later.

**Deliverables** _(human decision)_, all private artifact pages; the layout depends on how many pairs get downloaded:
- **5 or fewer:** an overview page, plus one artifact per pair report in the seed pair's structure (Pair report, above; `build_report.py`), linked from the overview.
- **More than 5:** one artifact with tabs: the overview first, then one tab per pair report (grouped by pair type, strongest first). Each tab loads its data, stills and videos only when opened.
  - Size: a pair report is ~18 MB today (two downloads ~8 MB, stills ~10 MB). Stills get recompressed and the pair data goes in per-pair JSON files next to the page (an artifact version holds 256 MB); the videos go in the artifact's asset store (20 MB per file). If the store's quota runs out, the lowest-ranked pairs keep their stills and storyboards but drop the synced video, and their tab says so.
  - `build_report.py` splits into a page shell and a per-pair renderer, used by both layouts.
- Either way: the overview is republished as stages finish, built by `build_search_report.py` from `results/search/`; the seed pair is included (its existing report reused); gate-passed pairs without a download get no report, only their row in the overview with the image evidence and the agent's label.

Overview sections:
0. What stood out: the strongest pairs and the surprises (same-day releases, large audience gaps, re-skins within a channel), each linking to its pair report.
1. Funnel: counts per stage and pair type, budget used.
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

## Open questions


- Same subject: is "fill up with the closest videos by title and thumbnail" the right fallback for rare songs and non-song content, and are 10 studios / 30 pairs the right minimums? A free check first: how many dataset videos share their title's subject with at least 10 other studios.

- Baseline size: is ~10 downloaded baseline videos enough for a 99th percentile, or should baselines lean on API and image signals and the dataset's existing features?
