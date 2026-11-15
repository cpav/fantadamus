"""mvp-alerts task 1.3: why a change happened, from the facts read after the call compared, the official
lineup first (design C2; R2.2)."""

from __future__ import annotations

import datetime as dt

from fantadamus.domains.alerts import Cause, Change, Latest, cause
from tests.alerts_data import AT, LATER, NAMES, a_call, moved

SWAP = Change("swap", now=11, before=2, role="D")
BEFORE = a_call()
AFTER = moved(BEFORE, at=LATER)
EARLIER = AT - dt.timedelta(hours=1)


def test_the_official_lineup_first() -> None:
    latest = {2: Latest(official="bench", official_at=LATER, out="knock", out_at=LATER)}
    assert cause(SWAP, BEFORE, AFTER, latest, NAMES) == Cause(
        "official", "the official lineup has Bianchi on the bench"
    )
    latest = {2: Latest(official="not listed", official_at=LATER)}
    assert cause(SWAP, BEFORE, AFTER, latest, NAMES) == Cause(
        "official", "the official lineup leaves Bianchi out of the squad"
    )
    latest = {11: Latest(official="starter", official_at=LATER)}
    assert cause(SWAP, BEFORE, AFTER, latest, NAMES) == Cause("official", "the official lineup starts Costa")


def test_the_injury_and_ban_pages() -> None:
    latest = {2: Latest(out="thigh muscle injury", out_at=LATER)}
    assert cause(SWAP, BEFORE, AFTER, latest, NAMES) == Cause(
        "injury", "the injury page has Bianchi out: thigh muscle injury"
    )
    latest = {2: Latest(out="banned for round 12", banned=True, out_at=LATER)}
    assert cause(SWAP, BEFORE, AFTER, latest, NAMES) == Cause("ban", "Bianchi is banned")


def test_the_probable_lineups() -> None:
    after = moved(AFTER, chances={**BEFORE.chances, 2: 0.4})
    assert cause(SWAP, BEFORE, after, {}, NAMES) == Cause(
        "outlets", "the probable lineups give Bianchi 40% to start, from 80%"
    )
    after = moved(AFTER, chances={**BEFORE.chances, 11: 0.95})
    assert cause(SWAP, BEFORE, after, {}, NAMES) == Cause(
        "outlets", "the probable lineups give Costa 95% to start, from 80%"
    )


def test_facts_read_before_the_call_compared_arent_a_cause() -> None:
    latest = {2: Latest(official="bench", official_at=EARLIER, out="knock", out_at=AT)}
    assert cause(SWAP, BEFORE, AFTER, latest, NAMES) is None


def test_otherwise_the_newest_facts() -> None:
    after = moved(AFTER, chances={**BEFORE.chances, 2: 0.804})
    assert cause(SWAP, BEFORE, after, {}, NAMES) is None
    assert cause(Change("formation", formations=("3-4-3", "4-3-3")), BEFORE, AFTER, {}, NAMES) is None


def test_who_each_change_is_about() -> None:
    latest = {
        2: Latest(official="bench", official_at=LATER),
        11: Latest(official="starter", official_at=LATER),
    }
    assert cause(Change("in", now=11, role="D"), BEFORE, AFTER, latest, NAMES) == Cause(
        "official", "the official lineup starts Costa"
    )
    assert cause(Change("out", before=2, role="D"), BEFORE, AFTER, latest, NAMES) == Cause(
        "official", "the official lineup has Bianchi on the bench"
    )
    assert cause(Change("captain", now=11, before=2), BEFORE, AFTER, latest, NAMES) == Cause(
        "official", "the official lineup has Bianchi on the bench"
    )


def test_a_fact_that_doesnt_explain_the_move_isnt_its_cause() -> None:
    """The player who lost his place: starting, or a chance gone up, doesn't explain it; the one who took it:
    benched, out or a chance gone down doesn't either."""
    out = Change("out", before=2, role="D")
    came = Change("in", now=11, role="D")
    starts = {2: Latest(official="starter", official_at=LATER)}
    assert cause(out, BEFORE, AFTER, starts, NAMES) is None
    up = moved(AFTER, chances={**BEFORE.chances, 2: 0.95, 11: 0.5})
    assert cause(out, BEFORE, up, {}, NAMES) is None
    assert cause(came, BEFORE, up, {}, NAMES) is None
    benched = {11: Latest(official="bench", official_at=LATER, out="knock", out_at=LATER)}
    assert cause(came, BEFORE, AFTER, benched, NAMES) is None


def test_a_fact_read_as_the_call_was_made_isnt_news() -> None:
    latest = {2: Latest(official="bench", official_at=AT)}
    assert cause(SWAP, BEFORE, AFTER, latest, NAMES) is None
