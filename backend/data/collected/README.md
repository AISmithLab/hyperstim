# The collected dataset

The videos added to the HyperStim dataset since the reference set (16,375 videos, 2015 to August 2026), committed every day by the data bot. How they're picked: [plan 013](../../../plans/013-growing-dataset.md).

- `<year>.tsv`: the videos added that year, in the order they were added.
- `removed.tsv`: videos taken out because they went offline.
- `excluded-channels.tsv`: channels left out because few of their uploads are made for kids (below).
- `CHANGELOG.tsv`: one row a day, the newest first (below).
- `growth.svg`, `growth-dark.svg`: the chart in the repo's README.

## CHANGELOG.tsv

The site at the end of each day (UTC). Channels left out for their kids share are counted nowhere, as on the site.

| Column | What it counts |
|---|---|
| `date` | the day (UTC) |
| `videos`, `channels` | on the site |
| `ch_1` … `ch_4`, `ch_5plus` | channels on the site with 1, 2, 3, 4, or 5 or more videos (they add up to `channels`) |
| `ch_ready` | channels not on the site yet, with a video checked and waiting to download |
| `ch_out` | channels left out for their kids share (the list below), with or without videos |
| `added_v`, `removed_v` | videos added that day, and taken out as offline |
| `new_ch` | channels that got their first video that day |
| `note` | a change to what the collector picks, or in what order, that went live that day |

`ch_ready` and `ch_out` are blank for the days before the collector started recording them: those days can't be counted again.

## excluded-channels.tsv

The channels left out of the site now, by channel ID. A channel's **kids share** is the share of its checked uploads that YouTube marks as made for kids; under 10 % (from 20 checked on) it's left out, with its videos. It's worked out again every time the files are written, so a channel comes back once its share reaches 10 %; the file's history shows when one came or went.

| Column | What it is |
|---|---|
| `channel_id`, `channel_title` | the channel |
| `checked` | its uploads whose made-for-kids answer is known (the videos picked for the reference set don't count, since they were picked for being made for kids) |
| `for_kids` | of those, made for kids |
| `kids_pct` | `for_kids` as a percentage of `checked` |
| `videos` | its videos in the dataset, not shown on the site while it's left out |
