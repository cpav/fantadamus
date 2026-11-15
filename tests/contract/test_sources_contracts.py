"""mvp-sources: the new facts' contracts, as a submit tool will receive them (design C2, C4, C6)."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import pytest
from pydantic import ValidationError

from fantadamus.contracts.xy.fixtures import OtherFixturesPayload
from fantadamus.contracts.xy.ratings import RatingsPayload
from fantadamus.contracts.xy.unavailable import InjuriesPayload, SuspensionsPayload

MATCH = {"home": "Alfa", "away": "Ostrava Rovers", "kickoff_at": "2026-09-08T21:00:00+02:00"}


def _parse(payload: dict[str, Any]) -> OtherFixturesPayload:
    return OtherFixturesPayload.model_validate_json(json.dumps(payload))


def test_other_fixtures_payload() -> None:
    """Task 2.1 (R2.1): a competition's matches, each with its kickoff stored in UTC and two different clubs;
    a league phase's 144 matches fit."""
    payload = _parse({"competition": "Champions League", "matches": [MATCH]})
    assert payload.matches[0].kickoff_at == dt.datetime(2026, 9, 8, 19, 0, tzinfo=dt.UTC)
    assert OtherFixturesPayload.__version__ == "1.0.0"
    assert len(_parse({"competition": "Coppa Italia", "matches": [MATCH] * 144}).matches) == 144
    wrong: list[tuple[dict[str, Any], str]] = [
        ({"competition": "Serie B", "matches": [MATCH]}, "competition"),
        ({"competition": "Europa League", "matches": []}, "at least 1"),
        ({"competition": "Europa League", "matches": [MATCH] * 201}, "at most 200"),
        ({"competition": "Europa League", "matches": [MATCH | {"away": "ALFA"}]}, "plays itself"),
        (
            {"competition": "Europa League", "matches": [MATCH | {"kickoff_at": "2026-09-08T21:00:00"}]},
            "timezone",
        ),
        ({"competition": "Europa League", "matches": [MATCH], "score": "2-1"}, "Extra inputs"),
    ]
    for payload_json, reason in wrong:
        with pytest.raises(ValidationError, match=reason):
            _parse(payload_json)


INJURED: dict[str, Any] = {
    "name": "Alfa Due",
    "kind": "muscle",
    "body_part": "hamstring",
    "back_from": "2026-11-21",
    "back_until": "2026-11-30",
    "to_be_assessed": False,
}


def test_injuries_and_suspensions_payloads() -> None:
    """Task 4.1 (R3.1): each club's injured players, with a known kind, a body part and a return window, or
    none; and each club's banned players with the rounds they miss, and who's one booking from a ban."""
    injuries = InjuriesPayload.model_validate_json(
        json.dumps({"clubs": [{"club": "Alfa", "players": [INJURED]}]})
    )
    assert injuries.clubs[0].players[0].back_from == dt.date(2026, 11, 21)
    plain = {"name": "Alfa Nove", "kind": "other"}
    [player] = (
        InjuriesPayload.model_validate({"clubs": [{"club": "Beta", "players": [plain]}]}).clubs[0].players
    )
    assert (player.body_part, player.back_from, player.to_be_assessed) == (None, None, False)
    wrong_injury: list[tuple[dict[str, Any], str]] = [
        ({"kind": "bruise"}, "kind"),
        ({"body_part": "elbow"}, "body_part"),
        ({"back_until": None}, "both or neither"),
        ({"back_from": "2026-12-01"}, "before"),
        ({"to_be_assessed": True}, "a window or to be assessed"),
    ]
    for wrong, reason in wrong_injury:
        with pytest.raises(ValidationError, match=reason):
            InjuriesPayload.model_validate({"clubs": [{"club": "Alfa", "players": [INJURED | wrong]}]})
    with pytest.raises(ValidationError, match="listed twice"):
        InjuriesPayload.model_validate({"clubs": [{"club": "Alfa", "players": [INJURED, INJURED]}]})
    with pytest.raises(ValidationError, match="listed twice"):
        InjuriesPayload.model_validate(
            {"clubs": [{"club": "Alfa", "players": []}, {"club": "ALFA", "players": []}]}
        )

    bans: dict[str, Any] = {
        "club": "Alfa",
        "banned": [{"name": "Alfa Sei", "rounds": [12]}],
        "one_booking": ["Alfa Tre"],
    }
    suspensions = SuspensionsPayload.model_validate_json(json.dumps({"clubs": [bans]}))
    assert suspensions.clubs[0].banned[0].rounds == [12]
    assert SuspensionsPayload.__version__ == InjuriesPayload.__version__ == "1.0.0"
    wrong_bans: list[tuple[dict[str, Any], str]] = [
        ({"banned": [{"name": "Alfa Sei", "rounds": [39]}]}, "less than or equal to 38"),
        ({"one_booking": ["Alfa Tre", "alfa tre"]}, "listed twice"),
        ({"banned": [{"name": "Alfa Tre", "rounds": []}]}, "both banned and one booking"),
    ]
    for wrong, reason in wrong_bans:
        with pytest.raises(ValidationError, match=reason):
            SuspensionsPayload.model_validate({"clubs": [bans | wrong]})


RATED: dict[str, Any] = {
    "club": "Alfa",
    "name": "UNO A.",
    "role": "P",
    "ratings": [{"desk": "Fantacalcio.it", "rating": 6.5}, {"desk": "Roma", "rating": None}],
}


def test_ratings_payload() -> None:
    """Task 6.1 (R4.2): a round's matches, each player with his club, role and each desk's base rating, None
    for "s.v."; a desk that hasn't published is left out."""
    payload = RatingsPayload.model_validate_json(
        json.dumps({"round": 11, "matches": [{"home": "Alfa", "away": "Beta", "players": [RATED]}]})
    )
    assert payload.matches[0].players[0].ratings[1].rating is None
    assert (payload.matches[0].players[0].came_on, payload.matches[0].players[0].minutes) == (False, None)
    assert RatingsPayload.__version__ == "1.0.0"
    wrong: list[tuple[dict[str, Any], str]] = [
        ({"club": "Gamma"}, "plays in neither"),
        ({"ratings": [{"desk": "Napoli", "rating": 6.0}]}, "desk"),
        ({"ratings": [{"desk": "Roma", "rating": 11.0}]}, "less than or equal to 10"),
        ({"ratings": [{"desk": "Roma", "rating": 6.0}, {"desk": "Roma", "rating": 6.5}]}, "twice"),
        ({"minutes": 140}, "less than or equal to 130"),
    ]
    for change, reason in wrong:
        with pytest.raises(ValidationError, match=reason):
            RatingsPayload.model_validate(
                {"round": 11, "matches": [{"home": "Alfa", "away": "Beta", "players": [RATED | change]}]}
            )
    twice = {"home": "Alfa", "away": "Gamma", "players": []}
    with pytest.raises(ValidationError, match="Alfa plays twice"):
        RatingsPayload.model_validate(
            {"round": 11, "matches": [{"home": "Alfa", "away": "Beta", "players": []}, twice]}
        )
