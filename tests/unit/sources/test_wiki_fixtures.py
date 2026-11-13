"""mvp-sources task 2.1: Wikipedia's page of a competition read into its matches, each from its `Football box`
template: the date, the kickoff in Italian time and both clubs (design C2; R2.1)."""

from __future__ import annotations

import datetime as dt
from typing import get_args

import pytest

from fantadamus.contracts.xy.fixtures import Competition
from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.wiki_fixtures import TITLES, competition_of, read_other_fixtures
from tests.sources_pages import (
    CUP_PROSE,
    Box,
    cup_box,
    link,
    plain_date,
    start_date,
    uefa_box,
    wiki_page,
)

SEPTEMBER, NOVEMBER = dt.date(2026, 9, 8), dt.date(2026, 11, 25)


def _read(boxes: list[str], prose: str | None = None) -> list[tuple[str, str, dt.datetime]]:
    page = wiki_page(boxes) if prose is None else wiki_page(boxes, prose)
    facts = read_other_fixtures(page, "Champions League")
    return [(match.home, match.away, match.kickoff_at) for match in facts.payload.matches]


def test_a_league_phase_page() -> None:
    """Each match's date from its `Start date`, its kickoff from the first time, in Italian time (CEST to 24
    October, CET after), and each club from its link, whatever the flags, references and local times around
    them."""
    boxes = [
        uefa_box(
            Box(link("Alfa", "Alfa FC"), link("Ostrava Rovers"), start_date(SEPTEMBER), "21:00", "2\u20131")
        ),
        uefa_box(
            Box(
                link("Kessel", "FC Kessel"),
                link("Beta", "Beta Calcio"),
                start_date(NOVEMBER),
                "18:45&nbsp;{{small|(19:45 [[UTC+03:00|UTC+3]])}}",
            )
        ),
    ]
    facts = read_other_fixtures(wiki_page(boxes), "Champions League")
    assert facts.payload.competition == "Champions League"
    assert [(m.home, m.away, m.kickoff_at) for m in facts.payload.matches] == [
        ("Alfa", "Ostrava Rovers", dt.datetime(2026, 9, 8, 19, 0, tzinfo=dt.UTC)),
        ("Kessel", "Beta", dt.datetime(2026, 11, 25, 17, 45, tzinfo=dt.UTC)),
    ]
    assert facts.problems == []


def test_the_cup_page() -> None:
    """The Coppa Italia writes its dates as text and its zone after the time, puts the winner in bold and each
    side's tier after its name; its knockout boxes aren't collapsible."""
    boxes = [
        cup_box(
            Box(
                "'''" + link("Gamma", "Gamma 1907") + " (1)'''",
                link("Vico", "LR Vico") + " (2)",
                plain_date(dt.date(2026, 8, 8)),
                "20:00 [[Central European Summer Time|CEST]]",
                "1\u20131",
            )
        ),
        cup_box(
            Box(
                link("Delta") + " (1)",
                link("Alfa", "Alfa FC") + " (1)",
                plain_date(dt.date(2027, 1, 14)),
                "21:00 [[Central European Time|CET]]",
            ),
            collapsible=False,
        ),
    ]
    assert _read(boxes, CUP_PROSE) == [
        ("Gamma", "Vico", dt.datetime(2026, 8, 8, 18, 0, tzinfo=dt.UTC)),
        ("Delta", "Alfa", dt.datetime(2027, 1, 14, 20, 0, tzinfo=dt.UTC)),
    ]


@pytest.mark.parametrize(
    ("team1", "date", "time"),
    [
        ("Winner of Match 37", plain_date(dt.date(2027, 3, 2)), "21:00 [[Central European Time|CET]]"),
        (link("Alfa") + " (1) or " + link("Gamma") + " (1)", plain_date(dt.date(2027, 1, 14)), "21:00"),
        (link("Alfa"), "2\u20133 March 2027", "21:00 [[Central European Time|CET]]"),
        (link("Alfa"), "TBD", "21:00"),
        (link("Alfa"), start_date(SEPTEMBER), "TBD"),
        (link("Alfa"), start_date(SEPTEMBER), ""),
    ],
)
def test_an_unsettled_match_is_left_out(team1: str, date: str, time: str) -> None:
    """A match without a fixed date, a kickoff or both clubs isn't a match yet: it's left out, and counted."""
    settled = uefa_box(Box(link("Beta"), link("Kessel"), start_date(NOVEMBER), "21:00"))
    unsettled = cup_box(Box(team1, link("Delta"), date, time))
    facts = read_other_fixtures(wiki_page([settled, unsettled]), "Coppa Italia")
    assert [(m.home, m.away) for m in facts.payload.matches] == [("Beta", "Kessel")]
    assert facts.problems == ["1 match without a fixed date, a kickoff or both clubs, left out"]


def test_a_match_that_doesnt_hold_together_is_named() -> None:
    """A club playing itself is named; the page's other matches still count."""
    boxes = [
        uefa_box(Box(link("Beta"), link("Kessel"), start_date(NOVEMBER), "21:00")),
        uefa_box(Box(link("Alfa"), link("Alfa", "Alfa FC"), start_date(NOVEMBER), "21:00")),
    ]
    facts = read_other_fixtures(wiki_page(boxes), "Europa League")
    assert [(m.home, m.away) for m in facts.payload.matches] == [("Beta", "Kessel")]
    assert len(facts.problems) == 1
    assert facts.problems[0].startswith("Alfa v Alfa: ")
    assert "plays itself" in facts.problems[0]


@pytest.mark.parametrize(
    "page",
    [
        "",
        wiki_page([]),
        "{{Football boxes are gone|date=8 September 2026}}",
        wiki_page([cup_box(Box("Winner of Match 37", "Winner of Match 38", "2\u20133 March 2027", "21:00"))]),
        wiki_page([uefa_box(Box(link("Alfa"), link("Kessel"), start_date(SEPTEMBER), "21:00"))[:-12]]),
    ],
)
def test_a_page_without_a_match_is_unreadable(page: str) -> None:
    """No match template, none settled or one left open: the layout changed, or there's nothing to keep."""
    with pytest.raises(UnreadablePageError):
        read_other_fixtures(page, "Champions League")


@pytest.mark.parametrize(
    ("url", "competition"),
    [
        (
            "https://en.wikipedia.org/wiki/2026%E2%80%9327_UEFA_Champions_League_league_phase?action=raw",
            "Champions League",
        ),
        (
            "https://en.wikipedia.org/wiki/2026\u201327_UEFA_Europa_League_league_phase?action=raw",
            "Europa League",
        ),
        (
            "https://en.wikipedia.org/wiki/2026%E2%80%9327_UEFA_Conference_League_knockout_phase?action=raw",
            "Conference League",
        ),
        ("https://example.org/wiki/2026%E2%80%9327_Coppa_Italia?action=raw", "Coppa Italia"),
    ],
)
def test_the_competition_from_the_address(url: str, competition: str) -> None:
    """A knockout round's page, added after its draw, is the same competition's."""
    assert competition_of(url) == competition


def test_every_competition_has_its_title() -> None:
    assert sorted(TITLES.values()) == sorted(get_args(Competition))


def test_an_address_naming_no_competition_is_refused() -> None:
    with pytest.raises(ValueError, match="names none of"):
        competition_of("https://en.wikipedia.org/wiki/2026%E2%80%9327_Serie_A?action=raw")
