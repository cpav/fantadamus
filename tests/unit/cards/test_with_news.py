"""mvp-sources task 5.1: the card's out list with the pages' detail, and a player marked one booking from a
ban, on invented outlets: pure, so that `make mutate` can check it (design C5; R3.2, R3.3)."""

from __future__ import annotations

import dataclasses

from fantadamus.domains.availability.news import News, OutDetail
from fantadamus.domains.cards import Out, Reported, card_player, lineups, with_news
from tests.cards_data import KICKOFF, listed, source, valued

THIGH = OutDetail(reason="thigh muscle injury", back="back from late November")
PAGE = (source("https://www.fantacalcio.it/infortunati-serie-a"),)


def _news(out: OutDetail | None, *, one_booking: bool = False, banned: bool = False) -> News:
    return News(out=out, one_booking=one_booking, banned=banned, sources=PAGE)


def test_the_out_list_with_the_pages() -> None:
    """The outlets' out list keeps its count and gains the pages' reason and return; a player only a page has
    out joins it, in role order, with a disagreement where outlets have him starting; another club's player
    and a player the pages don't have out aren't added."""
    out_player = listed("Alfa Dodici", "D", (None, None, None, None))
    starter = listed("Alfa Nove", "A")
    benched = listed("Alfa Sette", "C", (10, 30, 5, 30))
    elsewhere = listed("Beta Nove", "A", club="beta")
    found = lineups("alfa", [out_player, starter, benched], KICKOFF)
    assert [entry.name for entry in found.out] == ["Alfa Dodici"]
    reported = [
        Reported(out_player.player, "D", _news(THIGH), out_player.present),
        Reported(
            starter.player, "A", _news(OutDetail(reason="banned for round 12"), banned=True), starter.present
        ),
        Reported(benched.player, "C", _news(None, one_booking=True), benched.present),
        Reported(elsewhere.player, "A", _news(THIGH), elsewhere.present),
    ]
    assert [entry.model_dump() for entry in with_news(found.out, "alfa", reported)] == [
        {
            "player_id": out_player.player.player_id,
            "name": "Alfa Dodici",
            "role": "D",
            "outlets": 4,
            "reason": "thigh muscle injury",
            "back": "back from late November",
        },
        {
            "player_id": starter.player.player_id,
            "name": "Alfa Nove",
            "role": "A",
            "outlets": 0,
            "reason": "banned for round 12",
            "disagreement": "Fantacalcio.it, Gazzetta, SOS Fanta and Sky have him starting; "
            "Fantacalcio.it's bans page has him banned.",
        },
    ]
    assert with_news(found.out, "alfa", []) == found.out
    assert [Out.model_validate(entry.model_dump()) for entry in found.out] == found.out


def test_one_booking_from_a_ban_marked() -> None:
    """Only a player the suspended page lists among the diffidati is marked; the mark is left out
    otherwise."""
    part = valued(listed("Alfa Sette", "C"))
    assert "one_booking_from_a_ban" not in card_player(part).model_dump()
    warned = dataclasses.replace(part, news=_news(None, one_booking=True))
    assert card_player(warned).model_dump()["one_booking_from_a_ban"] is True
    banned_only = dataclasses.replace(part, news=_news(THIGH))
    assert "one_booking_from_a_ban" not in card_player(banned_only).model_dump()
