"""mvp-roles P2: reading the same statistics page twice stores nothing new, and the second read confirms the
figures, whatever order the page lists its players in and whatever it shows in the columns nobody reads; a
changed figure stores the read again (design C4; R1.5)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.facts import payload_hash
from fantadamus.web.collector import season_submissions, to_store
from fantadamus.web.readers.fcit_stats import read_stats
from tests.collect_pages import stats_page
from tests.roles_data import stats_read

ROWS = stats_read()["players"][:6]  # each example builds and parses a page: enough to shuffle
FIRST = season_submissions(read_stats(stats_page(ROWS)))
LAST = {domain.source: {payload_hash(item.payload) for item in items} for domain, items in FIRST.items()}
unread = st.fixed_dictionaries(
    {"mfv": st.sampled_from(["6,0", "7,5", "11,25"]), "rp": st.sampled_from(["0", "2"]), "esp": st.just("1")}
)


@given(
    order=st.permutations(ROWS),
    cells=st.dictionaries(st.sampled_from([row["player_id"] for row in ROWS]), unread, max_size=4),
    changed=st.none() | st.sampled_from([row["player_id"] for row in ROWS]),
)
def test_p2_same_page_stores_nothing_new(
    order: list[dict[str, object]], cells: dict[int, dict[str, str]], changed: int | None
) -> None:
    rows = [row | {"assists": 5} if row["player_id"] == changed else row for row in order]
    again = season_submissions(read_stats(stats_page(rows, cells=cells)))
    stored = to_store(again, LAST)
    assert [domain.source for domain in stored] == ([] if changed is None else ["season_stats"])
