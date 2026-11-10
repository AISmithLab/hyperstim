# 001: Variant pairs

**Question:** Do studios publish near-identical versions of one video (same animation; new colors, background or title), and is there evidence they test the variants against each other?

**Seed pair** (same song, two channels the user believes are one company; published 18 days 1 h 27 min apart):

| Video | Channel | Published (UTC) |
|---|---|---|
| `pRPe05YfXxg` Five Little Ducks (cartoon) | Kids TV - Nursery Rhymes And Baby Songs | 2014-10-18 08:14:11 |
| `AJ1vEJXC0-M` Five Little Ducks (3D) | Kids Channel | 2014-11-05 09:41:12 |

## Hypotheses

Similarity alone doesn't separate them; outcome signals do.

- **H1, variant testing:** versions released close together, followed by a decision (a loser removed, the winning style taking over later uploads).
- **H2, re-skinning:** one asset repackaged for other channels or audiences, no testing.
- **H0:** only a shared song or template, which any studio's version of the rhyme would also show.

## Signal framework

- Studios use different strategies (e.g. new title but the same audio; different total length but the same song part), so **a pair needn't be similar on every signal**. Some signals firing is evidence enough.
- Each signal is scored against **baselines**: the same song by another studio; random pairs from one channel; random dataset pairs. A signal **fires** when the pair beats the 99th percentile of unrelated pairs.
- The set of signals that fire is the pair's **strategy profile** (e.g. "same audio, new title, recolored"); profiles are compared across pairs and studios.
- Align the two videos in time first (audio cross-correlation), before any frame-by-frame signal.

| Group | Signal | Needs |
|---|---|---|
| Who and when | Same owner (channel links, featured channels); days between publishing; similar time of day | API |
| Metadata | Title, description and tag similarity after normalizing the song name; duration difference | API |
| Thumbnail | Thumbnail embedding and grayscale hash similarity | Image |
| Coarse visual | Similarity of storyboard frame sequences; rough cut positions | Image |
| Audio | Fingerprint match; offset; **longest matching segment** (the song part); same vocal take or re-sung | Download |
| Fine visual | Cut timestamps after alignment; motion curve (camera movement) correlation; grayscale/edge SSIM; DINOv2 frame embeddings | Download |
| What changed | Hue/saturation difference; share of the frame that changed (background vs characters) | Download |
| Our features | Difference in the 12 pipeline features (free if the video is in the dataset) | Download, or free |
| Outcome (H1 vs H2) | View/like ratio; later uploads following the winning style; versions gone since | API |

## Steps

0. Write `tools/yt.py` (budget check + ledger) before any further YouTube request.
1. Score the seed pair on every signal: 2 downloads. This tests the framework.
2. Confirm the two channels are one company; find its other channels (API).
3. List all their uploads with the Data API (saving page tokens).
4. Find candidate pairs from API signals (same normalized song across channels, similar duration); narrow with image signals.
5. Downloads only for the top candidates and a small baseline set (~10 videos), within 10 a day; spread over days.
6. Strategy profiles per pair and studio; outcome signals to weigh H1 against H2.

## Results

None yet.

## Open questions

- Baseline size: is ~10 downloaded baseline videos enough for a 99th percentile, or should baselines lean on API and image signals and the dataset's existing features?
