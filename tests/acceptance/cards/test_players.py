"""AT-5 and AT-6 of mvp-cards: what the match means for each player, from the engine's own values, under the
stored rules or Classic's (design C4; R4)."""

from __future__ import annotations

import pytest

from fantadamus.domains.cards import (
    card_player,
    likeliest_scorers,
    rotation_risks,
    scoring_rules,
    takers,
    your_players,
)
from fantadamus.domains.season.gold import PenaltyOrder
from fantadamus.engine.keepers import KeeperValue
from fantadamus.engine.outfield import OutfieldValue
from fantadamus.league.rules import CLASSIC
from tests.cards_data import listed, source, valued

PLAYED = {"alfa": 9, "beta": 9}


def test_at5_a_scorer_by_hand() -> None:
    """His chance of scoring in the match is his chance if he starts, times his chance of starting, plus his
    chance from a cameo, times his chance of one; his share is the engine's."""
    part = valued(listed("Alfa Nove", "A", (80, 80, 80, 80)), goals=5)
    value = part.value
    assert isinstance(value, OutfieldValue)
    found = card_player(part)
    assert found.p_scores == pytest.approx(0.8 * value.p_scores + value.p_cameo * value.p_scores_cameo)
    assert found.p_scores_if_starts == value.p_scores
    assert found.goal_share == value.goal_share
    assert (found.p_clean_sheet, found.expected_conceded) == (None, None)
    assert (found.p_start, found.key, found.confidence.label) == (0.8, value.key, "agree")


def test_at5_the_likeliest_scorers() -> None:
    """The five best chances of either club, a likely cameo included; keepers aren't in it."""
    parts = [
        valued(listed("Alfa Uno", "P")),
        valued(listed("Alfa Nove", "A"), goals=6),
        valued(listed("Alfa Dieci", "A"), goals=3),
        valued(listed("Alfa Sei", "C"), goals=1),
        valued(listed("Alfa Due", "D"), goals=0),
        valued(listed("Alfa Tredici", "A", (10, 10, 10, 10)), goals=6),  # off the bench, often
        valued(listed("Beta Nove", "A", club="beta"), goals=4),
        valued(listed("Beta Due", "D", club="beta"), goals=0),
    ]
    found = likeliest_scorers(parts)
    by_chance = sorted(parts[1:], key=lambda part: -(card_player(part).p_scores or 0.0))
    assert [scorer.name for scorer in found] == [part.listed.player.name for part in by_chance[:5]]
    assert "Alfa Tredici" in [scorer.name for scorer in found]
    assert "Alfa Uno" not in [scorer.name for scorer in found]
    assert [scorer.p_scores for scorer in found] == sorted(
        (scorer.p_scores for scorer in found), reverse=True
    )


def test_at5_a_keeper() -> None:
    """A keeper's clean sheet is e^-xG of his opponents' goals, and his goals conceded are theirs."""
    part = valued(listed("Alfa Uno", "P"), opponent_xg=1.2)
    value = part.value
    assert isinstance(value, KeeperValue)
    found = card_player(part)
    assert found.p_clean_sheet == value.p_clean_sheet
    assert found.expected_conceded == 1.2
    assert (found.p_scores, found.p_scores_if_starts, found.goal_share) == (None, None, None)


def test_at5_the_takers() -> None:
    """The club's order as the page gives it, each found among his club-mates with his record; a name no
    club-mate answers to is kept as written, with no record."""
    parts = [
        valued(listed("Alfa Nove", "A"), penalties=(2, 3)),
        valued(listed("Alfa Dieci", "A"), penalties=(1, 1)),
        valued(listed("Beta Nove", "A", club="beta"), penalties=(4, 4)),
    ]
    order = PenaltyOrder(takers=["NOVE A", "Alfa Dieci", "Nessuno"], source=source())
    found = takers(order, "alfa", parts)
    assert [(taker.name, taker.penalties_scored, taker.penalties_taken) for taker in found] == [
        ("Alfa Nove", 2, 3),
        ("Alfa Dieci", 1, 1),
        ("Nessuno", None, None),
    ]
    assert [taker.player_id for taker in found] == [
        parts[0].listed.player.player_id,
        parts[1].listed.player.player_id,
        None,
    ]
    assert takers(None, "alfa", parts) == []


def test_at5_a_rotation_risk() -> None:
    """A usual starter whose chance is low, or whose place is disputed, is a risk; a player who seldom starts
    isn't, nor one the outlets list as out."""
    parts = [
        valued(listed("Alfa Due", "D", (45, 45, 45, 45)), rated=8),  # usually starts, now 45%
        valued(listed("Alfa Tre", "D", (90, 90, 90, 50)), rated=7),  # usually starts, disputed
        valued(listed("Alfa Quattro", "D", (30, 30, 30, 30)), rated=2),  # seldom starts
        valued(listed("Alfa Cinque", "D", (None, None, 20, 20)), rated=9),  # out
        valued(listed("Alfa Sei", "C"), rated=9),  # starts, as usual
        valued(listed("Beta Due", "D", (40, 40, 40, 40), club="beta"), rated=6),  # 6 of 9: not quite usual
    ]
    found = rotation_risks(parts, PLAYED)
    assert [(risk.name, risk.disputed) for risk in found] == [("Alfa Due", False), ("Alfa Tre", True)]
    assert (found[0].rated, found[0].played) == (8, 9)


def test_at5_rotation_at_its_edges() -> None:
    """Rated in exactly 70% of the matches is usual; exactly 60% to start isn't low; one match played counts;
    with no match played, or no table row for the club, nobody usually starts yet."""
    usual = valued(listed("Alfa Due", "D", (50, 50, 50, 50)), rated=7)
    even = valued(listed("Alfa Tre", "D", (60, 60, 60, 60)), rated=9)
    assert [risk.name for risk in rotation_risks([usual, even], {"alfa": 10})] == ["Alfa Due"]
    first = valued(listed("Alfa Due", "D", (50, 50, 50, 50)), rated=1)
    assert [risk.name for risk in rotation_risks([first], {"alfa": 1})] == ["Alfa Due"]
    unplayed = valued(listed("Alfa Due", "D", (50, 50, 50, 50)), rated=0)
    assert rotation_risks([unplayed], {"alfa": 0}) == []
    assert rotation_risks([usual], {}) == []


def test_at5_your_players_first() -> None:
    """The user's players in the match, in role order and likeliest first, each with what he's worth."""
    parts = [
        valued(listed("Alfa Nove", "A", (60, 60, 60, 60))),
        valued(listed("Alfa Uno", "P")),
        valued(listed("Alfa Dieci", "A")),
        valued(listed("Beta Due", "D", club="beta")),
    ]
    mine = {part.listed.player.player_id for part in parts if part.listed.player.name != "Alfa Dieci"}
    found = your_players(parts, mine)
    assert [player.name for player in found] == ["Alfa Uno", "Beta Due", "Alfa Nove"]
    assert [player.key for player in found] == [card_player(parts[i]).key for i in (1, 3, 0)]


def test_at6_classic_without_rules() -> None:
    assert scoring_rules(None) == (CLASSIC, True)


def test_at6_a_leagues_own_rules() -> None:
    """A league that scores a forward's goal 4 instead of 3 changes his points, never his chances."""
    rows = [row.model_copy(update={"points": 4.0}) if row.event == "goal" else row for row in CLASSIC.events]
    league = CLASSIC.model_copy(update={"events": rows})
    assert scoring_rules(league) == (league, False)
    part = listed("Alfa Nove", "A", (80, 80, 80, 80))
    classic, own = card_player(valued(part, goals=5)), card_player(valued(part, goals=5, rules=league))
    assert own.key > classic.key
    assert (own.p_start, own.p_scores, own.goal_share) == (
        classic.p_start,
        classic.p_scores,
        classic.goal_share,
    )
