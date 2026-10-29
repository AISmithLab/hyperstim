"""The changelog's notes (plan 013, decision 10): one short line for each change to what the
collector picks or in what order, shown on the day it went live.

A change to the collector's rules or order adds a line here in the same commit, without a date:
the collector dates it the first day it runs with it. Keep each under ~70 characters.
"""

# (note, day): the day only for the notes from before the collector dated them itself.
NOTES: tuple[tuple[str, str | None], ...] = (
    ("Collecting starts: 150 videos a day, lowest r first", "2026-10-26"),
    ("Each channel gets 5 videos first; failed downloads retried", "2026-10-29"),
    ("Fewest-video channels first; channels with under 10% kids' videos left out", "2026-10-29"),
    ("Channels with 1–4 videos by score first; at most 3 new channels a day", "2026-10-29"),
)
