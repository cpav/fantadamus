"""mvp-alerts task 1.3: the notification, the action first and its cause after (design C3; R3.1)."""

from __future__ import annotations

from fantadamus.domains.alerts import Cause, Change, alert_text
from tests.alerts_data import NAMES

SWAP = Change("swap", now=11, before=2, role="D")
BENCH = Change("bench", now=12, before=11, role="D")
OFFICIAL = Cause("official", "the official lineup has Bianchi on the bench")


def test_the_shape() -> None:
    alert = alert_text(12, [SWAP, BENCH], [OFFICIAL, None], NAMES)
    assert alert.title == "Fantadamus · Round 12"
    assert alert.subtitle == "Official lineup out"
    assert alert.text == (
        "Start Costa instead of Bianchi: the official lineup has Bianchi on the bench. "
        "Fontana is now your first defender off the bench."
    )
    assert alert.shown == 2


def test_each_kind_of_change_in_words() -> None:
    found = [
        Change("in", now=11, role="D"),
        Change("out", before=13),
        Change("formation", formations=("3-4-3", "4-3-3")),
        Change("captain", now=9, before=8),
        Change("vice", now=8, before=9),
        Change("swap", now=14, before=8, role="A"),
    ]
    alert = alert_text(12, found, [None] * len(found), NAMES, limit=1000)
    assert alert.subtitle == "Your call changed"
    assert alert.text == (
        "Start Costa. Bench Rizzo. Play 4-3-3 instead of 3-4-3. Captain Bruno instead of Greco. "
        "Make Greco vice-captain instead of Bruno. "
        "Start Lombardi instead of Greco, on the newest lineups and odds."
    )


def test_a_cause_is_said_once() -> None:
    found = [SWAP, Change("captain", now=11, before=2)]
    alert = alert_text(12, found, [OFFICIAL, OFFICIAL], NAMES)
    assert alert.text == (
        "Start Costa instead of Bianchi: the official lineup has Bianchi on the bench. "
        "Captain Costa instead of Bianchi."
    )


def test_the_strongest_cause_is_the_subtitle() -> None:
    injury = Cause("injury", "the injury page has Verdi out: knock")
    ban = Cause("ban", "Neri is banned")
    outlets = Cause("outlets", "the probable lineups give Rossi 40% to start, from 80%")
    assert alert_text(12, [SWAP, SWAP], [outlets, injury], NAMES).subtitle == "Injury news"
    assert alert_text(12, [SWAP, SWAP], [injury, ban], NAMES).subtitle == "Ban news"
    assert alert_text(12, [SWAP], [outlets], NAMES).subtitle == "Probable lineups moved"
    assert alert_text(12, [SWAP, SWAP], [outlets, OFFICIAL], NAMES).subtitle == "Official lineup out"


def test_more_changes_are_counted() -> None:
    found = [SWAP, BENCH, Change("captain", now=9, before=8), Change("vice", now=8, before=9)]
    alert = alert_text(12, found, [OFFICIAL, None, None, None], NAMES, limit=150)
    assert alert.shown == 1
    assert alert.text == (
        "Start Costa instead of Bianchi: the official lineup has Bianchi on the bench. "
        "And 3 more changes: ask for your lineup."
    )
    assert len(alert.text) <= 150
    one_more = alert_text(12, found[:2], [OFFICIAL, None], NAMES, limit=120)
    assert one_more.text.endswith("And 1 more change: ask for your lineup.")


def test_a_first_change_too_long_for_its_cause_keeps_its_action() -> None:
    long = Cause("injury", "the injury page has Bianchi out: " + "a very long description " * 10)
    alert = alert_text(12, [SWAP], [long], NAMES, limit=100)
    assert alert.text == "Start Costa instead of Bianchi."
    assert alert.shown == 1


def test_a_name_too_long_for_any_sentence_is_cut() -> None:
    alert = alert_text(12, [SWAP], [None], {11: "X" * 300, 2: "Bianchi"}, limit=100)
    assert len(alert.text) == 100
    assert alert.text.endswith("…")


def test_a_player_whose_name_isnt_known() -> None:
    alert = alert_text(12, [Change("in", now=99)], [None], NAMES)
    assert alert.text == "Start player 99."
