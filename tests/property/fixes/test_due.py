"""P1 (mvp-fixes design; R1.2, R1.4): a page is due exactly when its newest answered try is older than its
cadence; failed tries never hold it back, and an answered try always counts."""

from __future__ import annotations

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.lake.collect_log import ANSWERED, newest
from fantadamus.web.cadence import due
from fantadamus.web.collector import CollectReport, Outcome, PageKind, PageReport, page_of

NOW = dt.datetime(2026, 11, 21, 8, 0, tzinfo=dt.UTC)
FACTS = (
    "fixtures",
    "player_season",
    "penalty_takers",
    "team_season",
    "other_fixtures",
    "injuries",
    "suspensions",
)
ANSWERS: list[Outcome] = sorted(ANSWERED)
offsets = st.lists(st.integers(min_value=-14 * 24 * 60, max_value=60), max_size=6)


def _runs(kind: PageKind, minutes: list[int], outcome: Outcome) -> list[CollectReport]:
    found = []
    for minute in minutes:
        at = NOW + dt.timedelta(minutes=minute)
        page = PageReport(url=f"https://site.example/{kind}", page=kind, outcome=outcome)
        found.append(CollectReport(started_at=at, finished_at=at, round=None, pages=[page]))
    return found


@given(st.sampled_from(FACTS), offsets, offsets, st.sampled_from(ANSWERS))
def test_p1_due_follows_the_last_answered_try(
    fact: str, answered: list[int], failed: list[int], answer: Outcome
) -> None:
    kind = page_of(fact)
    good = _runs(kind, answered, answer)
    with_failures = newest(good + _runs(kind, failed, "failed"), NOW, kind, ANSWERED)
    without = newest(good, NOW, kind, ANSWERED)
    assert with_failures == without  # failed tries never hold it back
    assert due(fact, with_failures, NOW, None) == due(fact, without, NOW, None)
    tried = [NOW + dt.timedelta(minutes=minute) for minute in answered if minute <= 0]
    assert with_failures == (max(tried) if tried else None)  # an answered try always counts, at or before now
