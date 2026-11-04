"""P3: collecting the same page twice stores nothing new (design C6; R1.4). P9: the marks are the starters
(R3.1).

Two synthetic round pages are read once: the original, and a variant whose fixtures, odds and one outlet's
percentage changed (its official lineups didn't). Each example takes the page's facts in any order and swaps
in the variant's for some kinds of fact: the same facts, in whatever order, store nothing new, and exactly the
kinds swapped in are stored. No page is parsed per example, which keeps 500 examples fast under coverage;
AT-1 checks a real second collection end to end through the lake.
"""

from __future__ import annotations

import random

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.facts import payload_hash
from fantadamus.web.collector import submissions, to_store
from fantadamus.web.readers.fco import read_round
from tests.collect_pages import FcoMatch, fco_round_page, squad

GAMMA = FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", confirmed=True)
PAGE = submissions(read_round(fco_round_page(FcoMatch("Alfa", "Beta", confirmed=True), GAMMA)))
VARIANT = submissions(
    read_round(
        fco_round_page(
            FcoMatch(
                "Alfa",
                "Beta",
                kickoff="31/10/2026 15:30",
                odds=("1,66", "3,80", "5,00"),
                percents={"Alfa Nove": (90, 90, 55, 90)},
                confirmed=True,
            ),
            GAMMA,
        )
    )
)
CHANGED = ["fixtures", "match_odds", "outlet_lineup"]  # what the variant changes, by construction
LAST = {domain.source: {payload_hash(item.payload) for item in items} for domain, items in PAGE.items()}


@given(swapped=st.sets(st.sampled_from(CHANGED)), order=st.randoms(use_true_random=False))
def test_p3_same_pages_store_nothing_new(swapped: set[str], order: random.Random) -> None:
    again = {}
    for domain, items in PAGE.items():
        read = VARIANT[domain] if domain.source in swapped else items
        again[domain] = order.sample(read, len(read))  # the page may list matches and outlets in any order
    assert {domain.source for domain in to_store(again, LAST)} == swapped


_HOME = st.tuples(st.integers(0, 11), st.integers(0, 2))
"""How many of the probable starters, and of the probable bench, are marked. Few enough cases to run them
all, since each one parses a page."""
_AWAY = st.sampled_from(((11, 0), (10, 0), (9, 0)))


def _team(club: str, marks: tuple[int, int]) -> tuple[list[str], list[str]]:
    """The players marked, and the rest of the two tables, as the page writes them."""
    written = [f"{name.split()[1].upper()} {club[0]}" for name in squad(club)[:13]]
    marked = written[: marks[0]] + written[11 : 11 + marks[1]]
    return sorted(marked), sorted(set(written) - set(marked))


def _names(club: str, marks: tuple[int, int]) -> tuple[str, ...]:
    listed = squad(club)
    return (*listed[: marks[0]], *listed[11 : 11 + marks[1]])


@given(home=_HOME, away=_AWAY)
def test_p9_the_marks_are_the_starters(home: tuple[int, int], away: tuple[int, int]) -> None:
    """However many are marked, in either table: with 10 or 11 for both teams they are the starters and the
    rest the bench; with fewer for either team the lineup isn't out; with more, it's named as a problem."""
    marked = (*_names("Alfa", home), *_names("Beta", away))
    facts = read_round(fco_round_page(FcoMatch("Alfa", "Beta", marked=marked), round=10))
    if min(sum(home), sum(away)) < 10:
        assert facts.officials == []
        assert facts.problems == []
    elif sum(home) > 11:
        assert facts.officials == []
        assert len(facts.problems) == 1
    else:
        [official] = facts.officials
        for team, club, marks in ((official.home_team, "Alfa", home), (official.away_team, "Beta", away)):
            starters, rest = _team(club, marks)
            assert team.starters == starters
            assert team.bench == rest
            assert team.unnamed_starters == 11 - sum(marks)
