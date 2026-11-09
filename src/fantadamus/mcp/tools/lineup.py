"""`best_lineup`: "who do I field?" (mvp-lineup design C8; R3, R5, R6.1, R7.1).

The same steps as the other tools come first: the setup step, collecting, and one refresh plan of what's
missing. A lineup is held back only when no number can be given. For a match's odds or lineups it goes ahead
on the best data it has, says which numbers rest on something more basic, and lists what could improve them.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from mcp.server.mcpserver import MCPServer
from pydantic import AwareDatetime, BaseModel

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import FormulaRule, LineupRules
from fantadamus.core.names import name_key
from fantadamus.domains.availability.consensus import Availability
from fantadamus.domains.calibration import summary_line
from fantadamus.domains.facts import Source
from fantadamus.domains.fixtures.gold import matches as round_matches
from fantadamus.domains.fixtures.silver import FixtureRow
from fantadamus.domains.players.resolve import KnownPlayer, resolve
from fantadamus.domains.season.gold import known_players, league_goals_per_match
from fantadamus.domains.sources import Confidence, describe, of_outlets
from fantadamus.engine.constants import (
    CAMEO_SHARE,
    DOUBTFUL_BELOW,
    P_START_BENCH,
    P_START_STARTER,
    SIMULATIONS,
)
from fantadamus.engine.keepers import KeeperInputs, KeeperValue
from fantadamus.engine.lineup import ROLE_WORDS, ROLES, Arrangement, Candidate, CannotFieldError, arrange
from fantadamus.engine.outfield import OutfieldInputs, OutfieldValue
from fantadamus.engine.rank import Label, Option, Scoring, label, verdict
from fantadamus.engine.simulate import (
    Reached,
    Side,
    SimPlayer,
    Simulated,
    keeper_player,
    outfield_player,
    ranked,
    simulate,
)
from fantadamus.lake.decision_log import Decision
from fantadamus.league.rules import (
    SetupStep,
    StoredRules,
    scoring_for,
    setup_step,
)
from fantadamus.league.squads import MINE, SquadStore, StoredSquad
from fantadamus.mcp.advisor import (
    REFRESH,
    ROME,
    TAKES_PENALTIES,
    Advisor,
    Facts,
    Gathered,
    PlayerFacts,
    RefreshItem,
    Updated,
    logged_player,
    model_inputs,
    model_value,
)

SCORERS_SHOWN = 5
PLACE_CALLS = 2
MOVES_SHOWN = 5
_RULES = {
    "same_role": "role for role",
    "role_first": "role first, then bench order",
    "bench_order": "in bench order",
}


class LineupPlayer(BaseModel):
    """One player's line: a full breakdown stays with `player_outlook` (R5.4)."""

    player_id: int
    name: str
    club: str
    role: Role
    match: str | None
    p_start: float
    confidence: Confidence | None
    """How sure his chance of starting is; none where no outlet gave one (R5.3 of `mvp-collect`)."""
    start_range: tuple[float, float] | None = None
    """The outlets' lowest and highest, when they disagree."""
    value: float
    """What his rating is worth, whichever way he gets it: the key (§A3)."""
    p_scores: float | None = None
    p_clean_sheet: float | None = None
    penalties: bool = False


class BenchPlace(LineupPlayer):
    reason: str


class Concern(BaseModel):
    """A squad player who's out, or a starter who's doubtful, and who covers him (R5.3)."""

    name: str
    status: Literal["out", "doubtful"]
    p_start: float
    covered_by: str | None


class Scorer(BaseModel):
    name: str
    chance: float


class SourceLine(BaseModel):
    """A page, once for the whole answer (R5.4)."""

    label: str
    captured_at: dt.datetime


class Call(BaseModel):
    """A choice that matters: between two formations, or a starter and the player behind him (R5.2)."""

    kind: Literal["formation", "place"]
    first: str
    second: str
    worth: float
    """In points: between formations the difference in expected score, between players what the choice is
    worth (R8)."""
    label: Label
    text: str
    ceiling: str | None = None
    """In a coin flip between formations, the one with the higher ceiling: variance helps an underdog."""


class RuleWorth(BaseModel):
    """What one of the league's formula rules adds on average in this lineup (mvp-rules R3.2)."""

    name: str
    average: float


class ThresholdCost(BaseModel):
    points: float
    advised: float
    chosen: float


class Override(BaseModel):
    """What the user's own choice costs against the advice, over the same simulated rounds (R3.5)."""

    advised_formation: str
    advised_expected: float
    advised_starters: list[str]
    cost: float
    """Expected points given up."""
    fantasy_goals_cost: float
    thresholds: list[ThresholdCost]


class Lineup(BaseModel):
    message: str
    team: str
    round: int
    lock: dt.datetime
    """In Europe/Rome: the kickoff of the round's first match."""
    first_match: str
    updated: Updated
    formation: str
    expected: float
    low: float
    high: float
    """Eight rounds out of ten fall from `low` to `high`."""
    fantasy_goals: float
    thresholds: list[Reached]
    starters: list[LineupPlayer]
    bench: list[BenchPlace]
    bench_rule: str
    left_off: list[str]
    formations: list[Simulated]
    """Every allowed formation that can be fielded, best first, as advised (R6.1)."""
    rules_worth: list[RuleWorth] = []
    """What each of the league's formula rules adds on average in this lineup."""
    captain: str | None = None
    """Where the league has a captain: the one who brings the most, or the user's (mvp-rules R3.3)."""
    vice: str | None = None
    """Whose rating counts when the captain has none."""
    calls: list[Call]
    override: Override | None = None
    last_round: str | None = None
    """How the last scored round's forecasts did, in a line (R7.6)."""
    out_and_doubtful: list[Concern]
    likely_scorers: list[Scorer]
    moved: list[str]
    check_before_lock: list[str]
    warnings: list[str]
    """Every number that rests on something more basic, and what the score leaves out (R2.3, R5.5)."""
    improve: list[RefreshItem]
    """What could improve those numbers: try once, then answer anyway (R5.6)."""
    sources: list[SourceLine]


class LineupResult(BaseModel):
    status: Literal["setup", "squad", "choose", "refused", "refresh", "lineup"]
    message: str
    setup: SetupStep | None = None
    unresolved: dict[str, list[KnownPlayer]] = {}
    """Names to start or leave out that could be several players of the squad."""
    refresh: list[RefreshItem] = []
    lineup: Lineup | None = None


@dataclass(frozen=True)
class _Priced:
    """A squad player with his model's answer."""

    facts: PlayerFacts
    inputs: OutfieldInputs | KeeperInputs
    value: OutfieldValue | KeeperValue
    scoring: Scoring
    penalties: bool
    no_lineups: bool

    @property
    def rating(self) -> float:
        return self.value.p_rating


def _assumed(facts: PlayerFacts) -> Availability:
    """Without any lineup for his match: how often he's had a rating so far, capped at a listed starter's
    chance."""
    played = facts.table.played
    p_start = min(facts.form.rated_appearances / played, P_START_STARTER) if played else P_START_BENCH
    return Availability(
        p_start=p_start,
        p_cameo=CAMEO_SHARE * (1 - p_start),
        spread=0.0,
        disputed=False,
        outlets=[],
        official=None,
    )


def _priced(gathered: Gathered, stored: StoredRules, as_of: dt.datetime) -> list[_Priced]:
    league = league_goals_per_match(gathered.teams, as_of)
    priced = []
    for facts in gathered.sides:
        scoring = scoring_for(stored.rules, facts.form.role)
        taker = facts.penalty_share >= TAKES_PENALTIES
        no_lineups = facts.match is not None and facts.present is None
        modelled = dataclasses.replace(facts, present=_assumed(facts)) if no_lineups else facts
        inputs = model_inputs(modelled, league)
        priced.append(_Priced(facts, inputs, model_value(inputs, scoring), scoring, taker, no_lineups))
    return priced


def _match_name(advisor: Advisor, match: FixtureRow) -> str:
    return f"{advisor.clubs.names[match.home]} v {advisor.clubs.names[match.away]}"


def _simulated(priced: Sequence[_Priced]) -> tuple[list[SimPlayer], list[tuple[float, float]]]:
    """Each player as the simulation sees him, and the goals expected in each of the squad's matches."""
    indexes: dict[tuple[str, str], int] = {}
    matches: list[tuple[float, float]] = []
    players: list[SimPlayer] = []
    for part in priced:
        facts, side = part.facts, None
        if facts.match is not None:
            pair = facts.match.home, facts.match.away
            if pair not in indexes:
                indexes[pair] = len(matches)
                xg = facts.xg
                matches.append((xg.home_xg, xg.away_xg) if xg else (0.0, 0.0))
            side = indexes[pair], 0 if facts.match.home == facts.player.club else 1
        players.append(_sim_player(part, side))
    return players, matches


def _sim_player(part: _Priced, side: Side | None) -> SimPlayer:
    player_id = part.facts.player.player_id
    if isinstance(part.inputs, KeeperInputs) and isinstance(part.value, KeeperValue):
        return keeper_player(player_id, part.inputs, part.value, part.scoring, side)
    if isinstance(part.inputs, OutfieldInputs) and isinstance(part.value, OutfieldValue):
        return outfield_player(player_id, part.inputs, part.value, part.scoring, side)
    raise TypeError(f"player {player_id}: a keeper's inputs need a keeper's value")


def _candidate(part: _Priced) -> Candidate:
    player = part.facts.player
    return Candidate(
        player_id=player.player_id,
        name=player.name,
        role=part.facts.form.role,
        club=player.club,
        p_start=part.value.p_start,
        p_cameo=part.value.p_cameo,
        key=part.value.key,
    )


def _line(advisor: Advisor, part: _Priced) -> dict[str, object]:
    facts, value = part.facts, part.value
    present = facts.present
    values = [view.p_start for view in present.outlets] if present else []
    return {
        "player_id": facts.player.player_id,
        "name": facts.player.name,
        "club": advisor.clubs.names[facts.player.club],
        "role": facts.form.role,
        "match": _match_name(advisor, facts.match) if facts.match else None,
        "p_start": round(value.p_start, 3),
        "confidence": of_outlets(present) if present else None,
        "start_range": (round(min(values), 3), round(max(values), 3))
        if present and present.disputed
        else None,
        "value": round(value.key, 2),
        "p_scores": round(value.p_scores, 3) if isinstance(value, OutfieldValue) else None,
        "p_clean_sheet": round(value.p_clean_sheet, 3)
        if isinstance(value, KeeperValue) and facts.match
        else None,
        "penalties": part.penalties,
    }


def _bench_reason(player: Candidate, arranged: Arrangement, first_in_role: bool, part: _Priced) -> str:
    fielded = next(starter for starter in arranged.starters if starter.role == player.role)
    if player.role == "P" and player.club == fielded.club:
        return f"plays exactly when {fielded.name} doesn't, so the place is covered"
    if not part.rating:
        return "won't play"
    if first_in_role:
        return f"first in if a {ROLE_WORDS[player.role]} misses out: {part.rating:.0%} to get a rating"
    return f"next {ROLE_WORDS[player.role]} in"


def _ordinal(number: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(number, f"{number}th")


def _worded(players: Sequence[Candidate]) -> str:
    return " and ".join(f"{player.name} {player.key:.1f}" for player in players)


def formation_call(results: Sequence[Simulated], arrangements: Mapping[str, Arrangement]) -> Call | None:
    """The best formation against the next, and the players it comes down to (§A7). Within about 0.15 points
    it's a coin flip, and the higher ceiling is worth naming: variance helps an underdog (R3.4)."""
    if len(results) < 2:
        return None
    best, other = results[0], results[1]
    gap = abs(best.mean - other.mean)
    worded = label(gap)
    ours, theirs = arrangements[best.formation].starters, arrangements[other.formation].starters
    gained = [player for player in ours if player not in theirs]
    lost = [player for player in theirs if player not in ours]
    ceiling = None
    text = f"{best.formation} over {other.formation}: {worded}, {gap:.2f} points. "
    if sum(player.key for player in gained) >= sum(player.key for player in lost):
        text += f"{_worded(gained)} over {_worded(lost)}."
    else:
        one = len(lost) == 1
        text += (
            f"On paper {_worded(lost)} {'is' if one else 'are'} worth more than {_worded(gained)}, but the "
            f"simulated rounds favour this lineup: from the bench {'he covers' if one else 'they cover'} a "
            "starter who misses out."
        )
    if worded == "coin flip":
        ceiling = other.formation if other.high > best.high else best.formation
        text += f" {ceiling} has the higher ceiling, which helps an underdog."
    return Call(
        kind="formation",
        first=best.formation,
        second=other.formation,
        worth=round(gap, 3),
        label=worded,
        text=text,
        ceiling=ceiling,
    )


def place_calls(
    arranged: Arrangement, options: Mapping[int, Option], rules: Sequence[FormulaRule] = ()
) -> list[Call]:
    """The closest choices between a role's last starter and the player behind him, with what each is worth
    (R5.2, R8). A keeper's club-mate covers him rather than competes, and nobody competes with a player who
    won't play. A coin flip in a role a formula rule counts says the rule could tip it (mvp-rules R3.5)."""
    calls = []
    for role in ROLES:
        line = [player for player in arranged.starters if player.role == role]
        last = line[-1]
        behind = next(
            (
                player
                for player in arranged.bench
                if player.role == role
                and (role != "P" or player.club != last.club)
                and player.p_start + player.p_cameo > 0
            ),
            None,
        )
        if behind is None:
            continue
        choice = verdict(options[last.player_id], options[behind.player_id])
        tipping = [
            rule.name
            for rule in rules
            if rule.who != "captain" and any(unit.role == role for unit in rule.who)
        ]
        tip = (
            f" The {' and the '.join(tipping)} could tip this."
            if tipping and choice.label == "coin flip"
            else ""
        )
        calls.append(
            Call(
                kind="place",
                first=last.name,
                second=behind.name,
                worth=round(choice.margin, 3),
                label=choice.label,
                text=f"{_ordinal(len(line))} {ROLE_WORDS[role]}: {last.name} {last.key:.1f} v "
                f"{behind.name} {behind.key:.1f}: {choice.label}, worth {choice.margin:.2f}.{tip}",
            )
        )
    return sorted(calls, key=lambda call: (call.worth, call.first))[:PLACE_CALLS]


def _concerns(priced: Mapping[int, _Priced], arranged: Arrangement) -> list[Concern]:
    starters = {player.player_id for player in arranged.starters}
    found = []
    for player_id, part in priced.items():
        present = part.facts.present
        role = part.facts.form.role
        cover = next(
            (
                player.name
                for player in arranged.bench
                if player.role == role and priced[player.player_id].rating > 0
            ),
            None,
        )
        if not part.rating and part.facts.match is not None:
            found.append(
                Concern(
                    name=part.facts.player.name,
                    status="out",
                    p_start=0.0,
                    covered_by=cover if player_id in starters else None,
                )
            )
        elif player_id in starters and (
            part.value.p_start < DOUBTFUL_BELOW or (present is not None and present.disputed)
        ):
            found.append(
                Concern(
                    name=part.facts.player.name,
                    status="doubtful",
                    p_start=round(part.value.p_start, 3),
                    covered_by=cover,
                )
            )
    return found


def _scorers(priced: Mapping[int, _Priced], arranged: Arrangement) -> list[Scorer]:
    chances = [
        Scorer(name=player.name, chance=round(value.p_scores, 3))
        for player in arranged.starters
        if isinstance(value := priced[player.player_id].value, OutfieldValue)
    ]
    return sorted(chances, key=lambda scorer: (-scorer.chance, scorer.name))[:SCORERS_SHOWN]


def _warnings(
    advisor: Advisor,
    priced: Sequence[_Priced],
    gone: Sequence[str],
    left_out: Sequence[str],
    round: int,
    rules: LineupRules,
) -> list[str]:
    """Every number resting on something more basic, naming the match or player and what it affects (R5.5)."""
    no_odds: dict[str, list[str]] = {}
    no_totals: dict[str, list[str]] = {}
    no_lineups: dict[str, list[str]] = {}
    found: list[str] = []
    for part in priced:
        facts = part.facts
        name = facts.player.name
        found += facts.disagreements
        if facts.match is None:
            found.append(f"{name} has no match in round {round}: counted as not playing.")
            continue
        match = _match_name(advisor, facts.match)
        if facts.xg is not None and not facts.xg.from_odds:
            no_odds.setdefault(match, []).append(name)
        elif facts.xg is not None and not facts.xg.totals:
            no_totals.setdefault(match, []).append(name)
        if part.no_lineups:
            no_lineups.setdefault(match, []).append(name)
        present = facts.present
        if (
            present is not None
            and not present.official
            and all(view.status == "not listed" for view in present.outlets)
        ):
            found.append(f"No outlet lists {name}: he's at the default {part.value.p_start:.0%} to start.")
        if present is not None and present.by_surname:
            written = ", ".join(present.by_surname)
            found.append(f"The outlets write {written}: matched to {name} by surname.")
        if not facts.form.rated_appearances:
            found.append(f"{name} has no rated games: he's on his role's priors.")
        if facts.form.role == "P" and facts.form.goals_conceded is None:
            found.append(f"{name}'s goals conceded aren't known: an average defence is assumed.")
    for match, names in no_odds.items():
        found.append(
            f"{match} has no odds: its numbers come from team form. This affects {', '.join(names)}."
        )
    for match, names in no_totals.items():
        found.append(
            f"{match} has no over/under: goal chances come from the 1X2 alone. "
            f"This affects {', '.join(names)}."
        )
    for match, names in no_lineups.items():
        found.append(
            f"{match} has no lineups yet: chances of starting come from how often each player has played. "
            f"This affects {', '.join(names)}."
        )
    found += [f"{name} is no longer listed at any club: left out." for name in gone]
    found += left_out
    if rules.other_rules:
        found.append(f"The score doesn't include {', '.join(rules.other_rules)}.")
    return list(dict.fromkeys(found))  # sources disagreeing on a club is one fact, whoever it's about


def _sources(priced: Sequence[_Priced]) -> list[Source]:
    sources: list[Source] = []
    for part in priced:
        facts = part.facts
        sources += [facts.form.source, facts.table.source, facts.order.source]
        if facts.match is not None:
            sources.append(facts.match.source)
        if facts.present is not None:
            sources += [view.source for view in facts.present.outlets]
            if facts.present.official is not None:
                sources.append(facts.present.official.source)
        if facts.xg is not None:
            sources += facts.xg.sources
    return sources


def _source_lines(sources: Sequence[Source], advisor: Advisor, as_of: dt.datetime) -> list[SourceLine]:
    """Each page once, by label, as read most recently."""
    worked = advisor.collect_log.last_worked(as_of) if advisor.collect_log is not None else {}
    newest: dict[str, dt.datetime] = {}
    for source in sources:
        label = describe(source.source_url)
        seen = max(source.captured_at, worked.get(source.source_url, source.captured_at))
        newest[label] = max(seen, newest.get(label, seen))
    return [SourceLine(label=label, captured_at=newest[label]) for label in sorted(newest)]


def _percent(chance: float) -> int:
    return round(chance * 100)


def _moved(
    advisor: Advisor, team: str, round: int, as_of: dt.datetime, result: Simulated, priced: Sequence[_Priced]
) -> list[str]:
    """What changed since this team's last lineup for this round, from the log: no replay (design C8)."""
    earlier = [
        decision
        for decision in advisor.log.read()
        if decision.kind == "lineup"
        and decision.user == advisor.user
        and decision.team is not None
        and name_key(decision.team) == name_key(team)
        and decision.round == round
        and decision.override_cost is None
        and decision.as_of < as_of
    ]
    if not earlier:
        return []
    last = max(earlier, key=lambda decision: decision.as_of)
    changes = []
    if last.formation != result.formation:
        changes.append(f"formation {last.formation} → {result.formation}")
    then = {logged.player_id: logged.p_start for logged in last.players}
    moves = sorted(
        (
            (
                now - then[part.facts.player.player_id],
                part.facts.player.name,
                then[part.facts.player.player_id],
                now,
            )
            for part in priced
            if part.facts.player.player_id in then
            and _percent(now := part.value.p_start) != _percent(then[part.facts.player.player_id])
        ),
        key=lambda move: (-abs(move[0]), move[1]),
    )
    changes += [f"{name} {old:.0%} → {new:.0%}" for _, name, old, new in moves[:MOVES_SHOWN]]
    if last.expected is not None and abs(result.mean - last.expected) >= 0.05:
        changes.append(f"expected {last.expected:.1f} → {result.mean:.1f}")
    return changes


def _before_lock(
    advisor: Advisor, priced: Sequence[_Priced], first_kickoff: dt.datetime, first_match: str
) -> list[str]:
    early = [
        part.facts
        for part in priced
        if part.facts.match is not None and part.facts.match.kickoff_at == first_kickoff
    ]
    if not early:
        return [f"No player of yours is in {first_match}, so this lineup is final unless news breaks."]
    waiting = [
        facts.player.name for facts in early if facts.present is None or facts.present.official is None
    ]
    if not waiting:
        return [f"The official lineup for {first_match} is out, and this lineup uses it."]
    return [
        f"{', '.join(waiting)} play in the round's first match ({first_match}): the official lineup is out "
        "about an hour before the lock, so check it then."
    ]


def last_round(advisor: Advisor) -> str | None:
    report = advisor.scores.latest() if advisor.scores is not None else None
    return summary_line(report) if report is not None else None


def _rounded(result: Simulated) -> Simulated:
    return result.model_copy(
        update={
            "mean": round(result.mean, 2),
            "low": round(result.low, 2),
            "high": round(result.high, 2),
            "fantasy_goals": round(result.fantasy_goals, 3),
            "rules": {name: round(points, 2) for name, points in result.rules.items()},
        }
    )


@dataclass(frozen=True)
class _Asked:
    """What the user wants to choose themself (R3.5)."""

    start: Sequence[str] = ()
    leave_out: Sequence[str] = ()
    formation: str | None = None
    captain: str | None = None

    def __bool__(self) -> bool:
        return bool(self.start or self.leave_out or self.formation or self.captain)


def lineup_for(
    advisor: Advisor,
    squads: SquadStore,
    team: str = MINE,
    as_of: dt.datetime | None = None,
    *,
    start: Sequence[str] = (),
    leave_out: Sequence[str] = (),
    formation: str | None = None,
    captain: str | None = None,
    rounds: int = SIMULATIONS,
) -> LineupResult:
    """The lineup, after the collector has read the pages of what was missing or stale. A replay of an earlier
    `as_of` never collects and isn't logged."""
    stored = advisor.rules.get(advisor.user)
    step = setup_step(stored.rules if stored is not None else None, lineup=True)
    if step is not None or stored is None or stored.rules.lineup is None:
        return LineupResult(status="setup", message=step.message if step else "", setup=step)
    rules = stored.rules.lineup
    if captain is not None and not any(rule.who == "captain" for rule in stored.rules.formula_rules):
        return LineupResult(
            status="refused", message="This league's rules have no captain, so there's none to name."
        )
    squad = squads.get(advisor.user, team)
    if squad is None:
        return LineupResult(
            status="squad",
            message=f"No squad stored for {team}: ask the user for the players, then call set_squad.",
        )
    if formation is not None and formation not in (rules.formations or ()):
        allowed = ", ".join(rules.formations or ())
        return LineupResult(
            status="refused", message=f"{formation} isn't a formation this league allows: {allowed}."
        )
    wanted = [player.player_id for player in squad.players]

    def ask(when: dt.datetime, facts: Facts, _tried: Mapping[str, str] | None) -> Gathered:
        return _gather_squad(advisor, wanted, facts, known_players(facts.players, when), when)

    done = advisor.after_collecting(as_of, ask, lambda found: [item.fact for item in found.plan.items])
    gathered, when, tried = done.result, done.when, done.tried

    def noted(items: Sequence[RefreshItem]) -> list[RefreshItem]:
        return [
            item.model_copy(update={"collector": tried[item.fact]}) if item.fact in tried else item
            for item in items
        ]

    round, first_kickoff = gathered.round, gathered.first_kickoff
    with_match = [side for side in gathered.sides if side.match is not None]
    if gathered.needed or round is None or first_kickoff is None or not with_match:
        return LineupResult(status="refresh", message=REFRESH, refresh=noted(gathered.needed))
    if all(side.present is None for side in with_match):
        return LineupResult(status="refresh", message=REFRESH, refresh=noted(gathered.plan.items))
    return _answer(
        advisor,
        stored,
        rules,
        squad,
        gathered,
        when,
        round,
        first_kickoff,
        noted(gathered.better),
        _Asked(start, leave_out, formation, captain),
        log=as_of is None,
        rounds=rounds,
    )


def _named(names: Sequence[str], players: Sequence[KnownPlayer]) -> dict[str, int] | LineupResult:
    """Each name's player ID within the squad, or what to do about the ones that don't find one."""
    found: dict[str, int] = {}
    unresolved: dict[str, list[KnownPlayer]] = {}
    for name in names:
        resolution = resolve(name, players)
        if resolution.player is not None:
            found[name] = resolution.player.player_id
        elif resolution.candidates:
            unresolved[name] = resolution.candidates
        else:
            return LineupResult(status="refused", message=f"{name} isn't in this squad.")
    if unresolved:
        return LineupResult(
            status="choose",
            message="A name matches more than one player of this squad: ask which.",
            unresolved=unresolved,
        )
    return found


def _override(advised: Simulated, chosen: Simulated, arranged: Arrangement) -> Override:
    """What the choice costs: the same rounds, so the difference is the choice, not luck."""
    marks = {mark.points: mark.chance for mark in chosen.thresholds}
    return Override(
        advised_formation=advised.formation,
        advised_expected=round(advised.mean, 2),
        advised_starters=[player.name for player in arranged.starters],
        cost=round(advised.mean - chosen.mean, 2) + 0.0,  # adding 0.0 turns a rounded -0.0 into 0.0
        fantasy_goals_cost=round(advised.fantasy_goals - chosen.fantasy_goals, 3) + 0.0,
        thresholds=[
            ThresholdCost(points=mark.points, advised=mark.chance, chosen=marks[mark.points])
            for mark in advised.thresholds
        ],
    )


def _squad_players(known: Sequence[KnownPlayer], wanted: Sequence[int]) -> list[KnownPlayer]:
    ids = set(wanted)
    return [player for player in known if player.player_id in ids]


def _gather_squad(
    advisor: Advisor, wanted: Sequence[int], facts: Facts, known: list[KnownPlayer], when: dt.datetime
) -> Gathered:
    players = _squad_players(known, wanted)
    gathered = advisor.gather(players, when, facts=facts, known=known)
    if not players:  # nothing else would ask for the page that says who they are
        gathered.plan.need(advisor.refresh_item("player_season", "stale", "the squad's season figures"))
    return gathered


@dataclass(frozen=True)
class _Fielding:
    """Who plays in each formation: as advised, and as the user chose (R3.5)."""

    advised: dict[str, Arrangement]
    chosen: dict[str, Arrangement]
    left_out: list[str]


def _fielding(
    candidates: Sequence[Candidate], priced: Sequence[_Priced], rules: LineupRules, asked: _Asked
) -> _Fielding | LineupResult:
    advised: dict[str, Arrangement] = {}
    left_out: list[str] = []
    for formation in rules.formations or ():
        try:
            advised[formation] = arrange(candidates, formation, rules)
        except CannotFieldError as problem:
            left_out.append(f"{formation} is left out: {problem}.")
    if not advised:
        return LineupResult(
            status="squad",
            message="This squad can't field any formation the league allows. " + " ".join(left_out),
        )
    captain = [asked.captain] if asked.captain else []
    named = _named((*asked.start, *asked.leave_out, *captain), [part.facts.player for part in priced])
    if isinstance(named, LineupResult):
        return named
    chosen: dict[str, Arrangement] = {}
    if asked:
        problems: list[str] = []
        captain_id = named[asked.captain] if asked.captain else None
        start_ids = {named[name] for name in asked.start} | (
            {captain_id} if captain_id is not None else set()
        )
        leave_ids = {named[name] for name in asked.leave_out}
        for shape in [asked.formation] if asked.formation else (rules.formations or ()):
            try:
                arranged = arrange(candidates, shape, rules, start_ids, leave_ids)
            except CannotFieldError as problem:
                problems.append(f"{problem}.")
            else:  # a captain the user names starts, and wears the armband
                chosen[shape] = arranged.model_copy(update={"captain": captain_id})
        if not chosen:
            return LineupResult(status="refused", message=problems[0])
    return _Fielding(advised, chosen, left_out)


def _bench_places(advisor: Advisor, arranged: Arrangement, by_id: Mapping[int, _Priced]) -> list[BenchPlace]:
    bench = []
    seen: set[Role] = set()
    for player in arranged.bench:
        part = by_id[player.player_id]
        reason = _bench_reason(player, arranged, player.role not in seen, part)
        seen.add(player.role)
        bench.append(BenchPlace.model_validate(_line(advisor, part) | {"reason": reason}))
    return bench


def _message(best: Simulated, override: Override | None, captain: str | None, vice: str | None) -> str:
    thresholds = ", ".join(f"{mark.points:g}: {mark.chance:.0%}" for mark in best.thresholds[:3])
    message = f"{best.formation}, expected about {best.mean:.0f} points" + (
        f"; chance of reaching {thresholds}." if thresholds else "."
    )
    if captain is not None:
        message += f" Captain {captain}" + (f", vice {vice}." if vice else ".")
    if override is not None:
        message += (
            f" Against the advice ({override.advised_formation}, about {override.advised_expected:.0f}), "
            f"this costs {override.cost:.2f} points."
        )
    return message


def _answer(
    advisor: Advisor,
    stored: StoredRules,
    rules: LineupRules,
    squad: StoredSquad,
    gathered: Gathered,
    when: dt.datetime,
    round: int,
    first_kickoff: dt.datetime,
    improve: list[RefreshItem],
    asked: _Asked,
    *,
    log: bool,
    rounds: int,
) -> LineupResult:
    team = squad.team
    known = gathered.known
    priced = _priced(gathered, stored, when)
    by_id = {part.facts.player.player_id: part for part in priced}
    candidates = [_candidate(part) for part in priced]
    fielding = _fielding(candidates, priced, rules, asked)
    if isinstance(fielding, LineupResult):
        return fielding
    arrangements, chosen = fielding.advised, fielding.chosen
    players, matches = _simulated(priced)
    # The advice and the user's choice over the same simulated rounds, so that the cost isn't luck (R3.5).
    simulated = simulate(
        players,
        matches,
        [*arrangements.values(), *chosen.values()],
        rules,
        formula_rules=stored.rules.formula_rules,
        rounds=rounds,
    )
    results = ranked(simulated[: len(arrangements)], rules)
    advised = results[0]
    best = ranked(simulated[len(arrangements) :], rules)[0] if asked else advised
    arranged = chosen[best.formation] if asked else arrangements[best.formation]
    override = _override(advised, best, arrangements[advised.formation]) if asked else None
    first_match = next(
        _match_name(advisor, row)
        for row in round_matches(gathered.fixtures, when)
        if row.round == round and row.kickoff_at == first_kickoff
    )
    known_ids = {player.player_id for player in known}
    gone = [player.name for player in squad.players if player.player_id not in known_ids]
    sources = _sources(priced)
    lines = _source_lines(sources, advisor, when)
    times = [line.captured_at for line in lines]

    def name_of(player_id: int | None) -> str | None:
        return by_id[player_id].facts.player.name if player_id is not None else None

    captain, vice = name_of(best.captain), name_of(best.vice)
    message = _message(best, override, captain, vice)
    moved = [] if asked else _moved(advisor, team, round, when, best, priced)
    options: dict[int, Option] = {player_id: part.value for player_id, part in by_id.items()}
    formation_choice = None if asked else formation_call(results, arrangements)
    calls = [
        *([formation_choice] if formation_choice else []),
        *place_calls(arranged, options, stored.rules.formula_rules),
    ]
    rounded = _rounded(best)
    lineup = Lineup(
        message=message,
        team=team,
        round=round,
        lock=first_kickoff.astimezone(ROME),
        first_match=first_match,
        updated=Updated(newest=max(times), oldest=min(times)),
        formation=best.formation,
        expected=rounded.mean,
        low=rounded.low,
        high=rounded.high,
        fantasy_goals=rounded.fantasy_goals,
        thresholds=best.thresholds,
        starters=[
            LineupPlayer.model_validate(_line(advisor, by_id[player.player_id]))
            for player in arranged.starters
        ],
        bench=_bench_places(advisor, arranged, by_id),
        bench_rule=f"Your league substitutes {_RULES[rules.substitution_mode or 'same_role']}, the first "
        f"bench player with a rating, up to {rules.substitutions}.",
        left_off=[player.name for player in arranged.left_off],
        formations=[_rounded(result) for result in results],
        rules_worth=[RuleWorth(name=name, average=points) for name, points in rounded.rules.items()],
        captain=captain,
        vice=vice,
        calls=calls,
        override=override,
        last_round=last_round(advisor),
        out_and_doubtful=_concerns(by_id, arranged),
        likely_scorers=_scorers(by_id, arranged),
        moved=moved,
        check_before_lock=_before_lock(advisor, priced, first_kickoff, first_match),
        warnings=_warnings(advisor, priced, gone, fielding.left_out, round, rules),
        improve=improve,
        sources=lines,
    )
    if log:
        advisor.log.append(
            Decision(
                kind="lineup",
                as_of=when,
                logged_at=advisor.clock(),
                user=advisor.user,
                round=round,
                players=[
                    logged_player(
                        part.facts.player.player_id,
                        part.facts.player.name,
                        part.value,
                        playing=part.facts.match is not None,
                    )
                    for part in priced
                ],
                team=team,
                formation=best.formation,
                expected=best.mean,
                thresholds={f"{mark.points:g}": mark.chance for mark in best.thresholds},
                starters=[player.player_id for player in arranged.starters],
                bench=[player.player_id for player in arranged.bench],
                override_cost=override.cost if override else None,
                rules_worth=rounded.rules or None,
                captain=best.captain,
                vice=best.vice,
                advised_starters=[player.player_id for player in arrangements[advised.formation].starters]
                if override
                else None,
                advised_formation=advised.formation if override else None,
                advised_bench=[player.player_id for player in arrangements[advised.formation].bench]
                if override
                else None,
                advised_captain=advised.captain if override else None,
                advised_vice=advised.vice if override else None,
                rules=stored,
                content_hashes=sorted({source.content_sha256 for source in sources}),
            )
        )
    return LineupResult(status="lineup", message=message, lineup=lineup)


def register(server: MCPServer, advisor: Advisor, squads: SquadStore, *, rounds: int = SIMULATIONS) -> None:
    """Add `best_lineup` to `server`. The tests simulate fewer `rounds`, to keep the checks fast."""

    @server.tool(
        description="Pick the eleven, the bench in order and the formation for the next round, from the "
        "stored squad and the league's rules, simulated under the league's real rules. It returns one of: "
        "the setup step (league settings unset: ask the user, then call set_league_rules); 'squad' (no squad "
        "stored: ask the user, then call set_squad); a refresh plan (facts missing or stale: read the listed "
        "pages, submit with the named tools, then call again); or the lineup, with every allowed formation, "
        "who's doubtful, warnings about anything basic and what could improve it. Without a team it's the "
        "user's own squad. Where the league has a captain, it names the captain and the vice who bring the "
        "most. To price the user's own choice, pass players to start or leave_out of the eleven, a "
        "formation, or a captain (who then starts): it returns that lineup with what it costs against the "
        "advice. as_of replays an earlier question."
    )
    def best_lineup(
        team: str = MINE,
        start: list[str] | None = None,
        leave_out: list[str] | None = None,
        formation: str | None = None,
        captain: str | None = None,
        as_of: AwareDatetime | None = None,
    ) -> LineupResult:
        return lineup_for(
            advisor,
            squads,
            team,
            as_of,
            start=start or (),
            leave_out=leave_out or (),
            formation=formation,
            captain=captain,
            rounds=rounds,
        )
