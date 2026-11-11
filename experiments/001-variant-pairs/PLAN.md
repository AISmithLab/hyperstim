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

## Steps

0. Write `tools/yt.py` (budget check + ledger) before any further YouTube request.
1. Score the seed pair on every signal: 2 downloads. This tests the framework.
2. Find the company's other channels: start from Kids Channel's "Our Family" list and check each with the owner signal (API).
3. List all their uploads with the Data API (saving page tokens).
4. Find candidate pairs from API signals (same normalized song across channels, similar duration); narrow with image signals.
5. Downloads only for the top candidates and a small baseline set (~10 videos), within the daily limit; spread over days.
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
