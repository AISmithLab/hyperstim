"""Rankings of videos or channels by the score or one feature (plan 007).

Each criterion's order is computed once: most intense first, ties by ID, rows with no
value last. A request then keeps the rows in its category, numbers their ranks (equal
values share one), applies the search, reverses the ranked rows for `asc` (counting their
ranks from the calm end), and slices a page. A search matches names, or a row's exact ID
(a pasted link, plan 007).
"""

import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal, Protocol

from hyperstim_api import scoring

Order = Literal["desc", "asc"]

CRITERIA: tuple[str, ...] = ("score", *scoring.FEATURES)


class FeatureLike(Protocol):
    @property
    def key(self) -> str: ...
    @property
    def value(self) -> float | None: ...
    @property
    def percentile(self) -> float | None: ...


class Rankable(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def score(self) -> float: ...
    @property
    def features(self) -> tuple[FeatureLike, ...]: ...


def rank_value(item: Rankable, criterion: str) -> float | None:
    """What `criterion` ranks `item` by: its score or a feature percentile; None = no value."""
    if criterion == "score":
        return item.score
    for f in item.features:
        if f.key == criterion:
            return f.percentile
    return None


def fold(text: str) -> str:
    """Case and accents removed, for search: "Café" and "cafe" match."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


@dataclass(frozen=True)
class Ranked[T]:
    item: T
    rank: int | None  # by the criterion within the category, 1 = first in the order asked for


class Ranking[T: Rankable]:
    """Rows ranked by every criterion; `names` are what a search matches."""

    def __init__(self, items: Iterable[T], names: Callable[[T], Iterable[str]]) -> None:
        rows = list(items)
        self._text = {item.id: "\n".join(fold(n) for n in names(item)) for item in rows}
        self._orders: dict[str, list[tuple[T, float | None]]] = {}
        for criterion in CRITERIA:
            valued = [(item, rank_value(item, criterion)) for item in rows]
            valued.sort(key=lambda r: (r[1] is None, -(r[1] or 0), r[0].id))
            self._orders[criterion] = valued

    def page(
        self,
        criterion: str,
        order: Order,
        keep: Callable[[T], bool],
        query: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Ranked[T]], int]:
        """One page of the rows `keep` selects and `query` matches, and their count."""
        valued: list[tuple[T, float]] = []
        unranked: list[Ranked[T]] = []
        for item, value in self._orders[criterion]:
            if not keep(item):
                continue
            if value is None:
                unranked.append(Ranked(item, None))
            else:
                valued.append((item, value))
        if order == "asc":
            # 1 = the calmest; rows with no value stay last.
            valued.reverse()
        ranked: list[Ranked[T]] = []
        for i, (item, value) in enumerate(valued):
            # Equal values share the first one's rank (e.g. the many videos with a count of 0).
            tied = i > 0 and value == valued[i - 1][1]
            ranked.append(Ranked(item, ranked[-1].rank if tied else i + 1))
        rows = ranked + unranked
        if query:
            q = fold(query)
            rows = [r for r in rows if r.item.id == query or q in self._text[r.item.id]]
        return rows[offset : offset + limit], len(rows)
