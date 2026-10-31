"""P3: collecting the same page twice stores nothing new (design C6; R1.4).

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
from tests.collect_pages import FcoMatch, fco_round_page

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
