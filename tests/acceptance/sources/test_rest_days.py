"""AT-2 of mvp-sources: each side's rest days, worked out by hand from invented fixtures, and shown on a card
and an outlook as context, with their source (design C3; R2.2, R2.3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from fantadamus.domains.context import rest_days
from fantadamus.domains.fixtures.silver import FixtureRow, OtherFixtureRow
from tests.lineup_harness import a_round
from tests.sources_pages import Box, link, start_date, uefa_box, wiki_page
from tests.xy_harness import NOW

pytestmark = pytest.mark.anyio

ROME = ZoneInfo("Europe/Rome")
NAMES = {"alfa": "Alfa", "beta": "Beta", "gamma": "Gamma", "delta": "Delta"}
SOURCE = {"captured_at": dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC), "content_sha256": "0" * 64}
SERIE_A = "https://example.org/serie-a"
CHAMPIONS = "https://example.org/wiki/2026%E2%80%9327_UEFA_Champions_League_league_phase?action=raw"
EUROPA = "https://example.org/wiki/2026%E2%80%9327_UEFA_Europa_League_league_phase?action=raw"


def _rome(day: int, month: int, time: str) -> dt.datetime:
    hour, minute = (int(part) for part in time.split(":"))
    return dt.datetime(2026, month, day, hour, minute, tzinfo=ROME).astimezone(dt.UTC)


def _serie_a(round: int, home: str, away: str, kickoff: dt.datetime) -> FixtureRow:
    return FixtureRow(source_url=SERIE_A, **SOURCE, round=round, home=home, away=away, kickoff_at=kickoff)


def _other(url: str, competition: str, home: str, away: str, kickoff: dt.datetime) -> OtherFixtureRow:
    return OtherFixtureRow(
        source_url=url, **SOURCE, competition=competition, home=home, away=away, kickoff_at=kickoff
    )


def test_at2_rest_days_by_hand() -> None:
    """Alfa v Beta on Saturday 31 October at 15:00. Alfa played Serie A on Sunday 25 October and the Champions
    League on Wednesday 28 October, and plays it again on Tuesday 3 November: 3 days' rest, 3 days to the next
    match, both European, so a European week. Beta played Serie A on Saturday 24 October, after the Europa
    League on Thursday 22 October, and plays it on Thursday 5 November: 7 days' rest, 5 to the next, no
    European match within 3 days."""
    kickoff = _rome(31, 10, "15:00")
    serie_a = [
        _serie_a(9, "delta", "alfa", _rome(25, 10, "20:45")),
        _serie_a(9, "beta", "gamma", _rome(24, 10, "18:00")),
        _serie_a(10, "alfa", "beta", kickoff),
    ]
    other = [
        _other(CHAMPIONS, "Champions League", "alfa", "Ostrava Rovers", _rome(28, 10, "21:00")),
        _other(CHAMPIONS, "Champions League", "Kessel", "alfa", _rome(3, 11, "18:45")),
        _other(EUROPA, "Europa League", "beta", "Lupa", _rome(22, 10, "18:45")),
        _other(EUROPA, "Europa League", "Vico", "beta", _rome(5, 11, "21:00")),
    ]
    alfa = rest_days("alfa", kickoff, serie_a, other, NAMES)
    assert alfa.days.model_dump() == {
        "previous": {
            "competition": "Champions League",
            "opponent": "Ostrava Rovers",
            "home": True,
            "kickoff": dt.datetime(2026, 10, 28, 21, 0, tzinfo=ROME),
        },
        "next": {
            "competition": "Champions League",
            "opponent": "Kessel",
            "home": False,
            "kickoff": dt.datetime(2026, 11, 3, 18, 45, tzinfo=ROME),
        },
        "days_since": 3,
        "days_to": 3,
        "european_week": True,
        "line": "Alfa: 3 days' rest since the Champions League on Wednesday 28 October; 3 days to the "
        "Champions League on Tuesday 3 November.",
    }
    assert [source.source_url for source in alfa.sources] == [CHAMPIONS]
    beta = rest_days("beta", kickoff, serie_a, other, NAMES)
    assert beta.days.previous is not None
    assert (beta.days.previous.competition, beta.days.previous.opponent) == ("Serie A", "Gamma")
    assert (beta.days.days_since, beta.days.days_to, beta.days.european_week) == (7, 5, False)
    assert beta.days.line == (
        "Beta: 7 days' rest since Serie A on Saturday 24 October; 5 days to the Europa League on Thursday 5 "
        "November."
    )
    assert [source.source_url for source in beta.sources] == [SERIE_A, EUROPA]


ALFA_IN_EUROPE = wiki_page(
    [
        uefa_box(Box(link("Alfa"), link("Ostrava Rovers"), start_date(dt.date(2026, 10, 28)), "21:00")),
        uefa_box(Box(link("Kessel"), link("Alfa"), start_date(dt.date(2026, 11, 3)), "18:45")),
        uefa_box(Box(link("Beta"), link("Lupa"), start_date(dt.date(2026, 10, 21)), "18:45")),
        uefa_box(Box(link("Vico"), link("Beta"), start_date(dt.date(2026, 11, 4)), "21:00")),
    ]
)
ALFA_LINE = (
    "Alfa: 3 days' rest since the Champions League on Wednesday 28 October; 3 days to the Champions League "
    "on Tuesday 3 November."
)


async def _content(client: Any, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    result = await client.call_tool(tool, args)
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


async def test_at2_on_the_card_and_the_outlook(tmp_path: Path) -> None:
    """With nothing stored, the card has the collector read the competition's page first; each side then
    shows its rest days, and the page is at the bottom with the sources. The outlook shows his club's, on the
    same read: the page, fresh, isn't read again, until within 24 hours of the match it has to be a day old at
    most (R7.1)."""
    async with a_round(tmp_path, other={CHAMPIONS: ALFA_IN_EUROPE}) as here:
        content = await _content(here.client, "match_card", {"club": "Alfa"})
        assert content["status"] == "card", content["message"]
        card = content["card"]
        alfa, beta = card["sides"]
        assert alfa["rest"]["line"] == ALFA_LINE
        assert alfa["rest"]["european_week"] is True
        assert beta["rest"]["line"] == (
            "Beta: 10 days' rest since the Champions League on Wednesday 21 October; 4 days to the Champions "
            "League on Wednesday 4 November."
        )
        assert beta["rest"]["european_week"] is False
        assert "Wikipedia, Champions League" in {line["label"] for line in card["sources"]}
        assert [url for url, *_ in here.web.calls].count(CHAMPIONS) == 1

        outlook = await _content(here.client, "player_outlook", {"player": "Alfa Nove"})
        assert outlook["status"] == "outlook", outlook["message"]
        [player] = outlook["answer"]["players"]
        assert player["rest"]["line"] == ALFA_LINE
        assert CHAMPIONS in {source["source_url"] for source in player["sources"]}
        assert [url for url, *_ in here.web.calls].count(CHAMPIONS) == 1

        here.clock.now = NOW + dt.timedelta(hours=25)  # a day on, the page is still fresh: a week's target
        await _content(here.client, "player_outlook", {"player": "Alfa Nove"})
        assert [url for url, *_ in here.web.calls].count(CHAMPIONS) == 1
        here.clock.now = _rome(31, 10, "15:00") - dt.timedelta(hours=23)  # near the match, a day's target
        await _content(here.client, "player_outlook", {"player": "Alfa Nove"})
        assert [url for url, *_ in here.web.calls].count(CHAMPIONS) == 2
