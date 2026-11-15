"""mvp-alerts task 2.2: what a check does with the call now: keep it, leave it, or alert (design C4; R1.2,
R3.3)."""

from __future__ import annotations

import datetime as dt

from fantadamus.domains.alerts import Call, Change, Decided, Latest, decide, newest
from tests.alerts_data import AT, LATER, NAMES, ROLES, a_call, moved

BENCHED = a_call(starters=[1, 11, 3, 4, 5, 6, 7, 13, 8, 9, 14], bench=[10, 2, 12], at=LATER)
SAVED = AT - dt.timedelta(days=1)


def _decide(baseline: Call | None, call: Call, saved_at: dt.datetime = SAVED) -> Decided:
    latest = {2: Latest(official="bench", official_at=LATER)}
    return decide(baseline, call, saved_at=saved_at, roles=ROLES, latest=latest, names=NAMES)


def test_without_a_baseline_the_call_becomes_it() -> None:
    assert _decide(None, BENCHED) == Decided("baseline", [])


def test_a_squad_or_rules_saved_after_the_baseline_make_a_new_one() -> None:
    assert _decide(a_call(), BENCHED, saved_at=AT + dt.timedelta(minutes=1)) == Decided("baseline", [])


def test_an_unchanged_call() -> None:
    assert _decide(a_call(), moved(a_call(), at=LATER, chances={2: 0.1})) == Decided("unchanged", [])


def test_a_changed_call_alerts_with_its_cause() -> None:
    decided = _decide(a_call(), BENCHED)
    assert decided.step == "alert"
    assert decided.found == [
        Change("swap", now=11, before=2, role="D"),
        Change("bench", now=2, before=11, role="D"),
    ]
    assert decided.alert is not None
    assert decided.alert.title == "Fantadamus · Round 12"
    assert decided.alert.text == (
        "Start Costa instead of Bianchi: the official lineup has Bianchi on the bench. "
        "Bianchi is now your first defender off the bench."
    )


def test_the_baseline_is_the_newest_call_seen() -> None:
    told, alerted = a_call(), moved(BENCHED, at=LATER)
    assert newest([told, alerted]) is alerted
    assert newest([alerted, None, told]) is alerted
    assert newest([None]) is None


def test_a_squad_saved_as_the_call_was_made_keeps_it() -> None:
    assert _decide(a_call(), BENCHED, saved_at=AT).step == "alert"
