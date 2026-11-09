"""AT-3 of mvp-review: a lineup's real score as the league scores it, by hand: its table, its substitutions
on real ratings, its formula rules and captain on real votes, its thresholds; and who makes it unknown (design
C3; R2.2, R2.3)."""

from __future__ import annotations

import dataclasses
from typing import Any

from fantadamus.contracts.xy.league import Band, EventRow, FormulaRule, LeagueRules, Unit
from fantadamus.domains.review import Events, RealScore, Round, Unknown, real_score
from fantadamus.engine.lineup import arrange
from fantadamus.engine.simulate import plan
from fantadamus.league.rules import CLASSIC, READY_MADE
from tests.lineup_data import full_squad, lineup_rules

SQUAD = full_squad()  # keepers 1 to 3, defenders 4 to 11, midfielders 12 to 19, forwards 20 to 25
LINEUP = lineup_rules()  # role for role, five substitutions, thresholds 66 and 72
ARRANGED = arrange(
    SQUAD, "3-4-3", LINEUP
)  # keeper 1; defenders 4, 5, 6; midfielders 12 to 15; forwards 20 to 22
PLAN = plan(ARRANGED, LINEUP)
QUIET = Events(
    open_goals=0,
    penalties_scored=0,
    penalties_missed=0,
    assists=0,
    yellows=0,
    reds=0,
    penalties_saved=0,
    conceded=0,
    own_goals=0,
)


def rated(rating: float | None, **events: Any) -> Round:
    return Round(rating, dataclasses.replace(QUIET, **events))


def _rounds(**changes: Round | Unknown) -> dict[int, Round | Unknown]:
    """Everyone in the squad rated 6 with nothing else, unless `changes` says otherwise, as `p20=...`."""
    rounds: dict[int, Round | Unknown] = {player.player_id: rated(6.0) for player in SQUAD}
    rounds.update({int(name[1:]): found for name, found in changes.items()})
    return rounds


ROUND = _rounds(
    p1=rated(6.0, conceded=2),  # 6 - 2
    p5=rated(None),  # no rating: the first defender on the bench comes on
    p7=rated(5.5),
    p12=rated(6.5, yellows=1),  # 6.5 - 0.5
    p20=rated(7.0, open_goals=1, assists=1),  # 7 + 3 + 1
    p21=rated(7.0),
)
CLASSIC_LEAGUE = CLASSIC.model_copy(update={"lineup": LINEUP})


def test_at3_a_real_score_by_hand() -> None:
    scored = real_score(ROUND, PLAN, CLASSIC_LEAGUE)
    assert scored.moves == [(5, 7)]
    assert scored.points[1] == 4.0
    assert scored.points[12] == 6.0
    assert scored.points[20] == 11.0
    # 4 + 6 + 5.5 + 6 (defence) + 6 + 6 + 6 + 6 (midfield) + 11 + 7 + 6 (attack)
    assert scored.total == 69.5
    assert scored.fantasy_goals == 1
    assert (scored.unknown, scored.not_counted, scored.rules) == ([], [], {})


def test_at3_formula_rules_and_the_captain_on_real_votes() -> None:
    """The attack modifier leaves out the forward who scored and gives the 7 a point; the captain, on a 7,
    gets a point; with the captain unrated, his vice's 7 counts."""
    attack, captain = (
        entry.rule for entry in READY_MADE if entry.rule.name in ("attack modifier", "captain")
    )
    league = CLASSIC_LEAGUE.model_copy(update={"formula_rules": [attack, captain]})
    scored = real_score(ROUND, PLAN, league, captain=20, vice=21)
    assert scored.rules == {"attack modifier": 1.0, "captain": 1.0}
    from_the_spot = _rounds(p20=rated(7.0, penalties_scored=1))  # left out too: a penalty is a goal
    assert real_score(from_the_spot, PLAN, league, captain=20).rules["attack modifier"] == 0.0
    assert scored.total == 71.5
    assert scored.fantasy_goals == 1
    covered = real_score(ROUND, PLAN, league, captain=5, vice=21)
    assert covered.rules["captain"] == 1.0
    nobody = real_score(_rounds(p5=rated(None), p6=rated(None)), PLAN, league, captain=5, vice=6)
    assert nobody.rules["captain"] == 0.0  # no rating for either, and no stand-in vote


def test_at3_penalties_cards_and_saves() -> None:
    """A penalty scored counts in place of the goal; a miss, a red and an own goal cost; a keeper's save
    pays."""
    rounds = _rounds(
        p1=rated(6.0, conceded=1, penalties_saved=1),  # 6 + 3 - 1
        p21=rated(6.0, penalties_scored=1, penalties_missed=1, reds=1, own_goals=1),  # 6 + 3 - 3 - 1 - 2
    )
    scored = real_score(rounds, PLAN, CLASSIC_LEAGUE)
    assert (scored.points[1], scored.points[21]) == (8.0, 3.0)
    gentler = [row for row in CLASSIC.events if row.event not in ("penalty_missed", "yellow_card")]
    league = LeagueRules(events=gentler, lineup=LINEUP)
    kinder = _rounds(p21=rated(6.0, penalties_scored=1, penalties_missed=1, yellows=1))
    assert real_score(kinder, PLAN, league).points[21] == 9.0  # an event the table leaves out costs nothing


def test_at3_a_keeper_who_conceded_is_left_out() -> None:
    """A rule that leaves out whoever conceded or saved a penalty leaves out the keeper too."""
    keeper = FormulaRule(
        name="keeper bonus",
        who=[Unit(role="P")],
        combine="each",
        leave_out="bonus_or_goal",
        bands=[Band(from_value=0.0, points=1.0)],
    )
    league = CLASSIC_LEAGUE.model_copy(update={"formula_rules": [keeper]})
    assert real_score(_rounds(), PLAN, league).rules == {"keeper bonus": 1.0}
    assert real_score(ROUND, PLAN, league).rules == {"keeper bonus": 0.0}  # he conceded two
    one = _rounds(p1=rated(6.0, conceded=1))
    assert real_score(one, PLAN, league).rules == {"keeper bonus": 0.0}
    saved = _rounds(p1=rated(6.0, penalties_saved=1))
    assert real_score(saved, PLAN, league).rules == {"keeper bonus": 0.0}


def test_at3_a_defenders_clean_sheet_from_his_teams_goals() -> None:
    """A league that gives defenders a clean sheet reads it from his team's goals conceded in the round."""
    rows = [*CLASSIC.events, EventRow(event="clean_sheet", points=1.0, roles=["D"])]
    league = LeagueRules(events=rows, lineup=LINEUP)
    kept = real_score(ROUND, PLAN, league, conceded={4: 0, 6: 1, 7: 0})
    assert (kept.points[4], kept.points[6], kept.points[7]) == (7.0, 6.0, 6.5)
    unknown = real_score(ROUND, PLAN, league, conceded={})
    assert unknown.points[4] == 6.0
    assert unknown.not_counted == ["clean_sheet"]


def test_at3_what_the_reads_cant_say_is_named() -> None:
    """A decisive goal, a set-piece assist, and counts a read stored before the new columns doesn't have."""
    rows = [
        *CLASSIC.events,
        EventRow(event="decisive_goal", points=1.0, roles=["A"]),
        EventRow(event="set_piece_assist", points=0.5, roles=["P", "D", "C", "A"]),
    ]
    league = LeagueRules(events=rows, lineup=LINEUP)
    old = rated(6.0, reds=None, penalties_saved=None, own_goals=None)
    scored = real_score(_rounds(p20=rated(7.0, open_goals=1, assists=1), p13=old), PLAN, league)
    assert scored.not_counted == ["decisive_goal", "set_piece_assist", "own_goal", "red_card"]
    assert scored.points[20] == 11.0  # the goal and the assist at their own values
    two = real_score(_rounds(p20=rated(7.0, open_goals=1, penalties_scored=1)), PLAN, league)
    assert two.not_counted == ["decisive_goal"]
    benched = real_score(_rounds(p5=rated(None), p7=old, p8=old), PLAN, CLASSIC_LEAGUE)
    assert benched.not_counted == [
        "own_goal",
        "red_card",
    ]  # the substitute who came on, not the one who didn't
    unused = real_score(_rounds(p8=old), PLAN, CLASSIC_LEAGUE)
    assert unused.not_counted == []


def test_at3_an_unknown_player() -> None:
    """A starter whose round isn't known makes the score unknown; a bench player only if he could have come
    on."""
    starter = real_score(_rounds(p13=Unknown("two matches between the reads")), PLAN, CLASSIC_LEAGUE)
    assert starter == RealScore(None, None, {}, [], {}, [13], [])
    unreached = real_score(_rounds(p16=Unknown("not in the read after the round")), PLAN, CLASSIC_LEAGUE)
    assert unreached.total == 67.0  # the keeper's 6 and his clean sheet, and ten 6s
    assert unreached.unknown == []
    missing = Unknown("not in the read after the round")
    reached = real_score(_rounds(p5=rated(None), p7=missing), PLAN, CLASSIC_LEAGUE)
    assert reached == RealScore(None, None, {}, [], {}, [7], [])
    both = real_score(_rounds(p5=rated(None), p7=missing, p16=missing), PLAN, CLASSIC_LEAGUE)
    assert both.unknown == [7]  # the midfielder on the bench couldn't have come on
