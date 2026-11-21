"""The changelog's notes (plan 013, decision 10): one short line for each change to what the
collector picks or in what order, or to how the changelog counts, shown on the day it went live.

A change to the collector's rules or order adds a line here in the same commit, without a date:
the collector dates it the first day it runs with it. Keep each under ~70 characters. To reword
a note already dated, change it here and map the old wording to the new in REWORDED: the
collector swaps the text and keeps the day.
"""

# From this note's day on, `ch_held` counts the channels whose thin years have nothing ready;
# `recount` counts the days before it again from the backups (plan 013, step 37).
HELD_READY = "ch_held also counts channels whose thin years have nothing ready"

# (note, day): the day only for the notes from before the collector dated them itself.
NOTES: tuple[tuple[str, str | None], ...] = (
    ("Collecting starts: 150 videos a day, lowest r first", "2026-10-26"),
    ("Each channel gets 5 videos first; failed downloads retried", "2026-10-29"),
    ("Fewest-video channels first; channels with under 10% kids' videos left out", "2026-10-29"),
    ("Channels with 1–4 videos by score first; at most 3 new channels a day", "2026-10-29"),
    ("Counts end at 23:59:59 UTC; ch_ready, ch_out recounted from backups", None),
    ("Thinnest channels first; under 5 eligible a year left out; 3 new a day", None),
    ("A third of downloads for new channels to catch up; at most 3 new a day", None),
    ("New channels join by subscribers, most first; their counts read weekly", None),
    ("Pace lowered from 150 to 120 videos a day after three blocks", None),
    ("ch_yr_2nd leaves out held channels, now in ch_held; ch_out is ch_left_out", None),
    ("Took out compilations of existing videos; no new ones are collected", None),
    (
        "Earlier rows count them as never added, except ch_ready, ch_held, ch_yr_2nd and "
        "ch_yr_med, which couldn't be recounted and still include them",
        "2026-11-18",
    ),
    (HELD_READY, None),
)

# old wording: new wording, for notes reworded after they were dated.
REWORDED: dict[str, str] = {
    "Took out videos that no longer fit our collection criteria": (
        "Took out compilations of existing videos; no new ones are collected"
    ),
}
