# The collected dataset

The videos added to the HyperStim dataset since the reference set (16,375 videos, 2015 to August 2026), committed every day by the data bot, as they stood at 23:59:59 UTC the day before. How they're picked: [plan 013](../../../plans/013-growing-dataset.md).

- `<year>.tsv`: the videos added that year, in the order they were added.
- `removed.tsv`: videos taken out because they went offline.
- `excluded-channels.tsv`: channels left out because few of their uploads are made for kids (below).
- `CHANGELOG.tsv`: one row a finished day, the newest first (below).
- `growth.svg`, `growth-dark.svg`: the chart in the repo's README.

## CHANGELOG.tsv

The site at the end of each finished day: every count is at 23:59:59 UTC, and the day still running has no row yet. Channels left out for their kids share are counted nowhere, as on the site, using today's list for every row, so a channel that comes or goes changes the past rows too.

| Column | What it counts |
|---|---|
| `date` | the day (UTC) |
| `videos`, `channels` | on the site |
| `ch_1` … `ch_4`, `ch_5plus` | channels on the site with 1, 2, 3, 4, or 5 or more videos (they add up to `channels`) |
| `ch_ready` | channels not on the site yet, with a video checked and waiting to download |
| `ch_out` | channels left out for their kids share (the list below), with or without videos |
| `added_v`, `removed_v` | videos added that day, and taken out as offline |
| `new_ch` | channels that got their first video that day |
| `note` | a change to what the collector picks, or in what order, or to how this file counts, that went live that day; and when `ch_ready` and `ch_out` aren't from 23:59:59, when they are from |

`ch_ready` and `ch_out` can't be worked out again later, so the collector records them when it closes a day, just after midnight. They're blank for the days before it started recording them. When they aren't from 23:59:59 (the collector was down at midnight, or the day was recounted from a backup taken just after it), the note says when they're from, e.g. "ch_ready and ch_out as of 2026-10-27 00:00:41 UTC"; "at the day's last export (time not kept)" marks a day recorded before the time was kept.

## History

Until the day the changelog's note says "Counts end at 23:59:59 UTC" (plan 013), the files were committed as they stood at the commit's time, not at the end of a day:

- 2026-10-28 to 2026-10-30: at 03:00 UTC; 2026-10-31: at 00:49 UTC; then at 23:59:59 UTC until the change was deployed.
- Each commit's newest changelog row was the day still running, so it was partial; the next commit replaced it with the whole day.
- Each commit's message counted the videos added since the commit before, so it covered parts of two days and didn't match a changelog row. The release notes' "Dataset" line read those partial newest rows.
- `ch_ready` and `ch_out` were recorded at each export, the day's last one standing (time not kept), until days were recounted from backups (above).
- `ch_ready` and `ch_out` for 2026-10-26 to 2026-10-28 were recounted from backups with the kids-share rule, which went live on 2026-10-29; on those days no channel was left out on the site.

The commits and release notes stay as they were; the changelog's rows in the latest commit are what counts.

## excluded-channels.tsv

The channels left out of the site now, by channel ID. A channel's **kids share** is the share of its checked uploads that YouTube marks as made for kids; under 10 % (from 20 checked on) it's left out, with its videos. It's worked out again every time the files are written, so a channel comes back once its share reaches 10 %; the file's history shows when one came or went.

| Column | What it is |
|---|---|
| `channel_id`, `channel_title` | the channel |
| `checked` | its uploads whose made-for-kids answer is known (the videos picked for the reference set don't count, since they were picked for being made for kids) |
| `for_kids` | of those, made for kids |
| `kids_pct` | `for_kids` as a percentage of `checked` |
| `videos` | its videos in the dataset, not shown on the site while it's left out |
