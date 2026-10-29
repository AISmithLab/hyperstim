# The collected dataset

The videos added to the HyperStim dataset since the reference set (16,375 videos, 2015 to August 2026), committed every day by the data bot. How they're picked: [plan 013](../../../plans/013-growing-dataset.md).

- `<year>.tsv`: the videos added that year, in the order they were added.
- `removed.tsv`: videos taken out because they went offline.
- `excluded-channels.tsv`: channels left out because few of their uploads are made for kids.
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
| `added_v`, `removed_v` | videos added that day, and taken out as offline |
| `new_ch` | channels that got their first video that day |
| `note` | a change to what the collector picks, or in what order, that went live that day |

`ch_ready` is blank for the days before the collector started recording it: those days can't be counted again.
