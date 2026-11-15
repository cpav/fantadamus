"""AT-5 of mvp-sources: a desk's bias for a player by hand on invented ratings, with its sample and 90%
interval; a claim shown on the card and the outlook; his expected vote unchanged (design C7; R5)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from fantadamus.domains.raters import claim, desk_bias
from fantadamus.domains.ratings.silver import MatchRatingRow
from tests.lineup_harness import a_round
from tests.xy_harness import NOW, send

pytestmark = pytest.mark.anyio

SOURCE = {"source_url": "https://example.org/voti", "content_sha256": "0" * 64}
MATCHES: list[tuple[float | None, float | None, float | None]] = [
    (7.0, 6.5, 6.5),
    (6.5, 6.0, 6.0),
    (6.0, 6.0, 5.5),
    (7.0, 6.5, 6.5),
    (6.5, 6.0, 6.5),
]
"""Fantacalcio.it, Roma and Torino's ratings of him in five matches."""
CLAIM = "Fantacalcio.it rates him 0.40 above the other desks, over 5 matches."


def _rows(name: str, ratings: list[tuple[float | None, float | None, float | None]]) -> list[MatchRatingRow]:
    rows = []
    for round, scores in enumerate(ratings, start=1):
        at = NOW - dt.timedelta(days=7 * (len(ratings) - round + 1))
        for desk, rating in zip(("Fantacalcio.it", "Roma", "Torino"), scores, strict=True):
            rows.append(
                MatchRatingRow(
                    **SOURCE,
                    captured_at=at,
                    round=round,
                    home="alfa",
                    away="beta",
                    club="alfa",
                    name=name,
                    role="A",
                    came_on=False,
                    minutes=None,
                    desk=desk,
                    rating=rating,
                )
            )
    return rows


def test_at5_bias_by_hand() -> None:
    """Fantacalcio.it's rating less the other two desks' mean, match by match: 0.5, 0.5, 0.25, 0.5 and 0.25, a
    mean of 0.40 over 5 matches. Their sample deviation is 0.137, a standard error of 0.061, so the 90%
    interval is 0.40 plus or minus 1.645 times 0.061: 0.30 to 0.50. A match one desk saw without rating him
    doesn't count. The three desks' biases add up to nothing: Roma's and Torino's are -0.20 each."""
    rows = _rows("NOVE A.", [*MATCHES, (6.0, None, 6.5)])
    found = {bias.desk: bias for bias in desk_bias(rows)}
    league = found["Fantacalcio.it"]
    assert (league.club, league.name, league.matches) == ("alfa", "NOVE A.", 5)
    assert league.bias == pytest.approx(0.40)
    assert league.low == pytest.approx(0.2993, abs=1e-4)
    assert league.high == pytest.approx(0.5007, abs=1e-4)
    assert found["Roma"].bias == pytest.approx(-0.20)
    assert found["Torino"].bias == pytest.approx(-0.20)
    assert claim(league) == CLAIM
    assert claim(found["Roma"]) is None  # under 0.25
    assert claim(found["Torino"]) is None
    assert claim(desk_bias(_rows("NOVE A.", MATCHES[:4]))[0]) is None  # 4 matches: too few


async def _content(client: Client, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    result = await client.call_tool(tool, args)
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


async def _stored(client: Client) -> None:
    """Five earlier rounds' ratings of Alfa Nove, as Claude would submit them from the ratings page."""
    for round, (league, roma, torino) in enumerate(MATCHES, start=4):
        ratings = [
            {"desk": "Fantacalcio.it", "rating": league},
            {"desk": "Roma", "rating": roma},
            {"desk": "Torino", "rating": torino},
        ]
        payload = {
            "round": round,
            "matches": [
                {
                    "home": "Alfa",
                    "away": "Beta",
                    "players": [{"club": "Alfa", "name": "NOVE A.", "role": "A", "ratings": ratings}],
                }
            ],
        }
        url = f"https://example.org/voti/{round}-giornata"
        assert not (await send(client, "submit_ratings", payload, NOW - dt.timedelta(days=30), url)).is_error


async def test_at5_a_claim_shown(tmp_path: Path) -> None:
    """The card's player and his outlook carry the claim; a player without one carries none."""
    async with a_round(tmp_path) as here:
        await _stored(here.client)
        card = (await _content(here.client, "match_card", {"club": "Alfa"}))["card"]
        players = {player["name"]: player for player in card["players"]}
        assert players["Alfa Nove"]["raters"] == [CLAIM]
        assert "raters" not in players["Alfa Dieci"]
        [player] = (await _content(here.client, "player_outlook", {"player": "Alfa Nove"}))["answer"][
            "players"
        ]
        assert player["raters"] == [CLAIM]


async def test_at5_the_expected_vote_unchanged(tmp_path: Path) -> None:
    """The league's rater's bias is already in his average rating (R5.3): his outlook's value is the same with
    the ratings stored as without."""
    async with a_round(tmp_path / "plain") as here:
        [before] = (await _content(here.client, "player_outlook", {"player": "Alfa Nove"}))["answer"][
            "players"
        ]
    async with a_round(tmp_path / "rated") as here:
        await _stored(here.client)
        [after] = (await _content(here.client, "player_outlook", {"player": "Alfa Nove"}))["answer"][
            "players"
        ]
    assert after["value"] == before["value"]
    assert after["raters"] == [CLAIM]
