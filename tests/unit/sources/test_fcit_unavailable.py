"""mvp-sources task 4.1: Fantacalcio.it's injured and suspended pages read into facts, each injury sentence by
rules: its kind, the body part and the return window; the sentences aren't kept (design C4; R3.1)."""

from __future__ import annotations

import datetime as dt

import pytest

from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.fcit_unavailable import read_injuries, read_suspensions
from fantadamus.web.readers.injury_rules import back_of, banned_rounds, body_part_of, kind_of
from tests.sources_pages import injured_page, suspended_page

TODAY = dt.date(2026, 11, 15)
D = dt.date


def test_the_injured_page() -> None:
    """Each club's players with what the rules make of their sentences; a club with nobody listed is kept,
    empty."""
    page = injured_page(
        {
            "Alfa": [
                (
                    "Alfa Due",
                    "Il difensore fermato da una lesione muscolare del bicipite femorale della coscia "
                    "sinistra. "
                    "Lungo stop, rientro dalla fine di novembre.",
                ),
                ("Alfa Nove", "Out per la febbre nel turno precedente."),
            ],
            "Beta": [("Beta Uno", "Fastidio fisico: da valutare in vista della 13a giornata.")],
            "Gamma": [],
        }
    )
    facts = read_injuries(page, TODAY)
    assert [club.model_dump() for club in facts.payload.clubs] == [
        {
            "club": "Alfa",
            "players": [
                {
                    "name": "Alfa Due",
                    "kind": "muscle",
                    "body_part": "hamstring",
                    "back_from": D(2026, 11, 21),
                    "back_until": D(2026, 11, 30),
                    "to_be_assessed": False,
                },
                {
                    "name": "Alfa Nove",
                    "kind": "illness",
                    "body_part": None,
                    "back_from": None,
                    "back_until": None,
                    "to_be_assessed": False,
                },
            ],
        },
        {
            "club": "Beta",
            "players": [
                {
                    "name": "Beta Uno",
                    "kind": "other",
                    "body_part": None,
                    "back_from": None,
                    "back_until": None,
                    "to_be_assessed": True,
                }
            ],
        },
        {"club": "Gamma", "players": []},
    ]
    assert facts.problems == []


@pytest.mark.parametrize(
    ("sentence", "kind", "part"),
    [
        ("Operato in estate al ginocchio destro, recuperabile da gennaio.", "surgery", "knee"),
        ("Fermo per la frattura della mano destra.", "fracture", "other"),
        ("Lesione al crociato anteriore del ginocchio: stagione finita.", "ligament", "knee"),
        ("Distrazione di medio grado agli adduttori della coscia destra.", "muscle", "adductor"),
        ("Risentimento muscolare al polpaccio.", "muscle", "calf"),
        ("Contusione alla caviglia rimediata in allenamento.", "knock", "ankle"),
        ("Influenza: salta la trasferta.", "illness", None),
        ("KO in Nazionale per un problema alla spalla.", "national team", "shoulder"),
        ("Da valutare durante la sosta per le Nazionali.", "other", None),
        ("Problema alla schiena.", "other", "back"),
        ("Affaticamento alla coscia.", "muscle", "thigh"),
        ("Dolore al piede sinistro.", "other", "foot"),
    ],
)
def test_the_kind_and_the_body_part(sentence: str, kind: str, part: str | None) -> None:
    """In order: surgery, a fracture, a ligament, a muscle, a knock, illness, an injury with the national
    team, else other; the international break isn't a national-team injury. The most precise body part
    wins."""
    assert (kind_of(sentence), body_part_of(sentence)) == (kind, part)


@pytest.mark.parametrize(
    ("sentence", "back_from", "back_until", "assess"),
    [
        ("Rientro dalla fine di novembre.", D(2026, 11, 21), D(2026, 11, 30), False),
        ("Recuperabile dall'inizio di dicembre.", D(2026, 12, 1), D(2026, 12, 10), False),
        ("Tornerà in campo da metà dicembre.", D(2026, 12, 11), D(2026, 12, 20), False),
        ("Recuperabile dalla seconda metà di dicembre.", D(2026, 12, 16), D(2026, 12, 31), False),
        (
            "Ipotesi di rientro da febbraio.",
            D(2027, 2, 1),
            D(2027, 2, 28),
            False,
        ),  # a month before the read's
        (
            "Fermo da inizio ottobre per la frattura, recuperabile da dicembre.",
            D(2026, 12, 1),
            D(2026, 12, 31),
            False,
        ),
        ("Da valutare rientro da fine novembre.", D(2026, 11, 21), D(2026, 11, 30), False),
        ("Stop di circa sei settimane dopo il ko del 26 ottobre.", D(2026, 12, 7), D(2026, 12, 7), False),
        ("Stop di circa 3 settimane.", D(2026, 12, 6), D(2026, 12, 6), False),  # from the read
        ("Stop di circa due settimane dal 20 settembre.", None, None, False),  # passed: the page's own guess
        ("Tempi di recupero da valutare.", None, None, True),
        ("Out dal 20 settembre per una lesione al ginocchio.", None, None, False),  # a since, not a return
    ],
)
def test_the_return_window(sentence: str, back_from: D | None, back_until: D | None, assess: bool) -> None:
    """A month's part (early, mid, the second half, late) or the whole month after a word for coming back;
    else a stop of about so long, from the date the sentence gives or from the read; else "to be assessed"."""
    back = back_of(sentence, TODAY)
    assert (back.back_from, back.back_until, back.to_be_assessed) == (back_from, back_until, assess)


def test_the_suspended_page() -> None:
    """Who's banned and the rounds he misses, and who's one booking from a ban; "Nessuno" lists nobody."""
    page = suspended_page(
        {
            "Alfa": ([("Alfa Sei", "squalificato nella 12a giornata di campionato")], ["Alfa Tre"]),
            "Beta": ([("Beta Otto", "squalificato per due giornate")], []),
            "Gamma": ([], []),
        }
    )
    facts = read_suspensions(page)
    assert [club.model_dump() for club in facts.payload.clubs] == [
        {"club": "Alfa", "banned": [{"name": "Alfa Sei", "rounds": [12]}], "one_booking": ["Alfa Tre"]},
        {"club": "Beta", "banned": [{"name": "Beta Otto", "rounds": []}], "one_booking": []},
        {"club": "Gamma", "banned": [], "one_booking": []},
    ]
    assert facts.problems == []
    assert banned_rounds("squalificato nella 12a e nella 13a giornata") == [12, 13]


@pytest.mark.parametrize(
    "page",
    [
        injured_page({"Alfa": [("Alfa Due", "Out.")]}, title="Probabili formazioni"),
        "<html><head><title>Infortunati Serie A</title></head><body>Nothing here</body></html>",
    ],
)
def test_an_injured_page_that_isnt_one_is_unreadable(page: str) -> None:
    with pytest.raises(UnreadablePageError):
        read_injuries(page, TODAY)


@pytest.mark.parametrize(
    "page",
    [
        suspended_page({"Alfa": ([], [])}, title="Infortunati Serie A"),
        "<html><head><title>Squalificati e diffidati Serie A</title></head><body></body></html>",
    ],
)
def test_a_suspended_page_that_isnt_one_is_unreadable(page: str) -> None:
    with pytest.raises(UnreadablePageError):
        read_suspensions(page)
