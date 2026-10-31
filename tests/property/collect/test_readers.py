"""P4: a reader given a page with any required part removed refuses it, never returning part of its facts
(design C3; R3.4)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.fco import read_round
from tests.collect_pages import FcoMatch, fco_round_page

PAGE = fco_round_page(FcoMatch("Alfa", "Beta"), FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00"))
REMOVALS = [
    '<p class="prb-incontro__data">',  # a kickoff's element
    '<span class="prb-incontro__nome">',  # a team's name
    'title="Gazzetta"',  # an outlet's column
    '<div class="stp-qval">',  # one of the 1X2 odds
    '<section class="prb-squadra prb-squadra--away">',  # a team's lineup
    '<td class="prb-cella"><span data-original-title="Probabilita&#039; x">',  # a percentage cell
]


@given(st.sampled_from(REMOVALS), st.integers(min_value=0, max_value=3))
def test_p4_partial_pages_fail(removal: str, which: int) -> None:
    starts = [i for i in range(len(PAGE)) if PAGE.startswith(removal, i)]
    at = starts[which % len(starts)]
    broken = PAGE[:at] + PAGE[at:].replace(removal, '<i class="gone">', 1)
    with pytest.raises(UnreadablePageError):
        read_round(broken, round=10)
