"""mvp-roles P1: the statistics reader reads the same rows whatever order the page lists them
in. A page without a column it reads is unreadable; a row with a bad value is left out with a reason, never
read as a wrong number (design C3; R1.2, R1.6)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.fcit_stats import COLUMNS, read_stats
from tests.collect_pages import STATS_COLUMNS, stats_page
from tests.roles_data import stats_read

ROWS = stats_read()["players"]
EXPECTED = read_stats(stats_page(ROWS)).payload
BAD = {
    "pg": ["x", "-1", "1,5", ""],
    "mv": ["x", "", "6.5"],
    "gol": ["x", "-1", "1,5", ""],
    "gs": ["x", "-1", ""],
    "rig": ["x", "1-2", "3 / x"],
    "ass": ["x", ""],
    "amm": ["x", "2,0"],
}
bad_cells = st.sampled_from(sorted(BAD)).flatmap(
    lambda key: st.tuples(st.just(key), st.sampled_from(BAD[key]))
)


@given(
    order=st.permutations(ROWS),
    missing=st.none() | st.sampled_from(sorted(COLUMNS)),
    bad=st.none() | st.tuples(st.sampled_from([row["player_id"] for row in ROWS]), bad_cells),
)
def test_p1_any_order_and_partial_pages(
    order: list[dict[str, object]], missing: str | None, bad: tuple[int, tuple[str, str]] | None
) -> None:
    columns = [column for column in STATS_COLUMNS if column[0] != missing]
    cells = {bad[0]: {bad[1][0]: bad[1][1]}} if bad else None
    page = stats_page(order, columns=columns, cells=cells)
    if missing is not None:
        try:
            read_stats(page)
        except UnreadablePageError:
            return
        raise AssertionError(f"a page without the {missing!r} column was read")
    facts = read_stats(page)
    if bad is None:
        assert facts.payload == EXPECTED
        assert facts.problems == []
        return
    assert [player for player in EXPECTED.players if player.player_id != bad[0]] == facts.payload.players
    assert len(facts.problems) == 1
    assert f"({bad[0]})" in facts.problems[0]
