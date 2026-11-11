"""`match_card`: one fixture on one screen, from the same facts and values as every other answer (mvp-cards
design C5; R1, R4.5, R4.6, R6.1).

It gathers every known player of both clubs at once, as a lineup gathers a squad, and prices each one the way
`player_outlook` does. Missing lineups or odds don't stop a card: it gives what's known and lists what could
make it better. A card at the clock's time is logged for the calibration; a replay isn't. A match of a round
whose deadline has passed is shown as it stood then, since the collector has moved on to the next round.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from mcp.server.mcpserver import MCPServer
from pydantic import AwareDatetime, BaseModel

from fantadamus.core.clubs import UnknownClubError
from fantadamus.domains.cards import (
    CardPlayer,
    FixtureLine,
    Lineups,
    Listed,
    MatchNumbers,
    Out,
    Place,
    RotationRisk,
    Scorer,
    Taker,
    Valued,
    card_player,
    likeliest_scorers,
    lineups,
    match_numbers,
    rotation_risks,
    round_lines,
    scoring_rules,
    takers,
    your_players,
)
from fantadamus.domains.fixtures.gold import deadline, matches, next_round
from fantadamus.domains.fixtures.silver import FixtureRow
from fantadamus.domains.odds.gold import TeamXg
from fantadamus.domains.season.gold import known_players, league_goals_per_match, team_season
from fantadamus.lake.decision_log import Decision
from fantadamus.league.rules import StoredRules, left_out, scoring_for
from fantadamus.league.squads import MINE, SquadStore
from fantadamus.mcp.advisor import (
    REFRESH,
    ROME,
    Advisor,
    Facts,
    Gathered,
    RefreshItem,
    Updated,
    logged_player,
    model_inputs,
    model_value,
)
from fantadamus.mcp.tools.lineup import SourceLine, source_lines, sources_of

_BEFORE_THE_LOCK = dt.timedelta(seconds=1)


class CardSide(BaseModel):
    """One side's lineups, its players by ID: each is in the card's `players` once."""

    club: str
    eleven: list[int]
    """In role order, likeliest first."""
    official: bool
    official_due: dt.datetime | None
    disputed: list[Place]
    out: list[Out]
    takers: list[Taker]


class Card(BaseModel):
    round: int
    match: str
    kickoff: dt.datetime
    deadline: dt.datetime
    """Both in Europe/Rome; the deadline is the round's first kickoff."""
    as_of: dt.datetime
    past_deadline: bool
    """The round's deadline has passed: this is the card as it stood then (R1.4)."""
    updated: Updated | None
    numbers: MatchNumbers | None
    """None when neither odds nor a table give the match's expected goals."""
    sides: list[CardSide]
    """Home first."""
    players: list[CardPlayer]
    """Each player the card names: the likely elevens, the contenders and the user's, once each."""
    scorers: list[Scorer]
    rotation: list[RotationRisk]
    yours: list[int]
    """The user's players in the match, by ID, first in role order and likeliest first."""
    classic_rules: bool
    """No league rules are stored, so the points are Classic's (R4.6)."""
    left_out: list[str]
    sources: list[SourceLine]


class RoundOverview(BaseModel):
    round: int
    deadline: dt.datetime
    """In Europe/Rome."""
    as_of: dt.datetime
    lines: list[FixtureLine]
    """One per fixture, in kickoff order, kickoffs in Europe/Rome."""


class OverviewResult(BaseModel):
    status: Literal["overview", "refresh"]
    message: str
    overview: RoundOverview | None = None
    improve: list[RefreshItem] = []
    refresh: list[RefreshItem] = []


class CardResult(BaseModel):
    status: Literal["card", "refused", "no_match", "refresh"]
    message: str
    card: Card | None = None
    improve: list[RefreshItem] = []
    """What could make the card better: read with `read_page`, submit, and ask again."""
    refresh: list[RefreshItem] = []
    """With `refresh`: what's needed before a card can be given."""


@dataclass(frozen=True)
class _Found:
    """What the stored facts say about the asked match at one time."""

    round: int | None
    match: FixtureRow | None
    gathered: Gathered | None
    past: tuple[FixtureRow, dt.datetime] | None = None
    """Two clubs' match in a round whose deadline has passed, and that deadline."""


def card_for(
    advisor: Advisor,
    squads: SquadStore,
    club: str,
    other_club: str | None = None,
    *,
    team: str = MINE,
    as_of: dt.datetime | None = None,
) -> CardResult:
    """The card of `club`'s match in the next round, or of the two clubs' match (C5)."""
    try:
        keys = [advisor.clubs.key(club), *([advisor.clubs.key(other_club)] if other_club else [])]
    except UnknownClubError as error:
        return CardResult(status="refused", message=str(error))
    if len(set(keys)) < len(keys):
        return CardResult(status="refused", message="A club doesn't play itself: name two clubs, or one.")

    def ask(when: dt.datetime, facts: Facts, _tried: Mapping[str, str] | None) -> _Found:
        return _find(advisor, keys, facts, when)

    done = advisor.after_collecting(
        as_of, ask, lambda found: [item.fact for item in found.gathered.plan.items] if found.gathered else []
    )
    found, when = done.result, done.when
    names = " and ".join(advisor.clubs.names[key] for key in keys)
    if found.past is not None:
        match, lock = found.past
        at = lock - _BEFORE_THE_LOCK
        facts = Facts.read(advisor.lake, at)
        known = known_players(facts.players, at)
        playing = [player for player in known if player.club in (match.home, match.away)]
        gathered = advisor.gather(playing, at, facts=facts, known=known, any_age=True)
        return _answer(advisor, squads, team, match, gathered, at, past=True, tried={}, log=False)
    if found.round is None or found.gathered is None:
        items = found.gathered.plan.items if found.gathered is not None else []
        return CardResult(status="refresh", message=REFRESH, refresh=items)
    if found.match is None:
        if len(keys) == 2:
            return CardResult(status="refused", message=f"{names} don't meet in round {found.round}.")
        return CardResult(status="no_match", message=f"{names} have no match in round {found.round}.")
    return _answer(
        advisor,
        squads,
        team,
        found.match,
        found.gathered,
        when,
        past=False,
        tried=done.tried,
        log=as_of is None,
    )


_OVERVIEW_FACTS = frozenset({"fixtures", "match_odds", "team_season"})
"""What an overview reads: the takers and players' figures are the cards'."""


def overview_for(advisor: Advisor, *, as_of: dt.datetime | None = None) -> OverviewResult:
    """The next round at a glance (C6): each fixture's numbers, team-level only, gathering no player and
    logging nothing."""

    def ask(
        when: dt.datetime, facts: Facts, _tried: Mapping[str, str] | None
    ) -> tuple[Gathered, list[tuple[FixtureRow, TeamXg | None]]]:
        return advisor.round_xg(when, facts=facts)

    done = advisor.after_collecting(
        as_of, ask, lambda found: [item.fact for item in found[0].plan.items if item.fact in _OVERVIEW_FACTS]
    )
    (gathered, found), when, tried = done.result, done.when, done.tried
    items = [
        item.model_copy(update={"collector": tried[item.fact]}) if item.fact in tried else item
        for item in gathered.plan.items
        if item.fact in _OVERVIEW_FACTS
    ]
    if gathered.round is None:
        return OverviewResult(status="refresh", message=REFRESH, refresh=items)
    lines = [
        line.model_copy(update={"kickoff": line.kickoff.astimezone(ROME)})
        for line in round_lines(found, advisor.clubs.names)
    ]
    lock = gathered.first_kickoff or min(match.kickoff_at for match, _ in found)
    overview = RoundOverview(round=gathered.round, deadline=lock.astimezone(ROME), as_of=when, lines=lines)
    said = f"Round {gathered.round}: {len(lines)} matches."
    if any(not line.from_odds for line in lines):
        said += " Some have no odds yet: team form gives their numbers, or there are none."
    return OverviewResult(
        status="overview",
        message=said,
        overview=RoundOverview.model_validate(_rounded(overview.model_dump())),
        improve=items,
    )


def register(server: MCPServer, advisor: Advisor, squads: SquadStore) -> None:
    """Add `match_card` and `round_overview` to `server`."""

    @server.tool(
        description="The next round at a glance, team-level only. In this order: the round and its deadline"
        " (Rome time); then one line per fixture in kickoff order: the match and its kickoff, "
        "the favourite and its chance and the draw, both sides' expected goals and clean "
        "sheets, and three goals or more where the odds price it. Use it for a question across "
        "the round (where are the goals, which keepers are safest), then offer match_card for "
        "any fixture. It returns 'overview', or 'refresh' when the round's fixtures aren't "
        "known yet; 'improve' lists what could make it better. as_of replays an earlier time."
    )
    def round_overview(as_of: AwareDatetime | None = None) -> OverviewResult:
        return overview_for(advisor, as_of=as_of)

    @server.tool(
        description="One fixture of the next round on one screen: name one club, or both. In this order: "
        "the context line (the match, its kickoff and the round's deadline in Rome time, when "
        "the facts were updated); the user's players in the match first (yours), with what each"
        " is worth; the match in numbers (each side's chance to win and the draw, expected "
        "goals, clean sheets, three goals or more and both teams to score where the odds price "
        "them, how far apart the odds pages are); each side's season so far (goals per match, "
        "its record and last five results, oldest first: context that should never move a "
        "number); each side's likely eleven with how sure it is, its disputed places naming the"
        " outlets that disagree, and who's out, said as 'listed as out by 3 outlets', never "
        "'injured'; the penalty takers with their record; the likeliest scorers; rotation "
        "risks. Sources at the bottom. Round chances the way people say them. Without stored "
        "league rules the points are Classic's (classic_rules): say so. 'improve' lists what "
        "could make it better: read with read_page, submit, ask again. Other statuses: "
        "'no_match', 'refused' (an unknown club, or two that don't meet) and 'refresh' (the "
        "round's fixtures aren't known yet). A match of a round past its deadline comes as it "
        "stood then (past_deadline): say so. Players are named once in players, and by "
        "player_id elsewhere. Pass team for a league-mate's squad; as_of replays an earlier "
        "time."
    )
    def match_card(
        club: str,
        other_club: str | None = None,
        team: str = MINE,
        as_of: AwareDatetime | None = None,
    ) -> CardResult:
        return card_for(advisor, squads, club, other_club, team=team, as_of=as_of)


def _find(advisor: Advisor, keys: Sequence[str], facts: Facts, when: dt.datetime) -> _Found:
    """The asked match in the next round, with its clubs' players gathered; or two clubs' match in the round
    before it, whose deadline has passed."""
    round = next_round(facts.fixtures, when)
    if round is None:  # gathering nobody still asks for the fixtures, and whatever else is stale
        nobody = advisor.gather([], when, facts=facts, known=[])
        return _Found(None, None, nobody, past=_earlier(keys, facts.fixtures, when))
    match = next(
        (
            row
            for row in matches(facts.fixtures, when)
            if row.round == round and set(keys) <= {row.home, row.away}
        ),
        None,
    )
    if match is None:
        past = _earlier(keys, facts.fixtures, when) if len(keys) == 2 else None
        return _Found(round, None, advisor.gather([], when, facts=facts, known=[]), past=past)
    known = known_players(facts.players, when)
    playing = [player for player in known if player.club in (match.home, match.away)]
    return _Found(round, match, advisor.gather(playing, when, facts=facts, known=known))


def _earlier(
    keys: Sequence[str], fixtures: Sequence[FixtureRow], when: dt.datetime
) -> tuple[FixtureRow, dt.datetime] | None:
    """Two clubs' match in the latest round whose deadline has passed, if they met in it, with that
    deadline."""
    if len(keys) != 2:
        return None
    rows = matches(fixtures, when)
    locks: dict[int, dt.datetime] = {}
    for row in rows:
        locks[row.round] = min(locks.get(row.round, row.kickoff_at), row.kickoff_at)
    passed = [round for round, lock in locks.items() if lock <= when]
    if not passed:
        return None
    latest = max(passed)
    met = next((row for row in rows if row.round == latest and set(keys) <= {row.home, row.away}), None)
    return (met, locks[latest]) if met is not None else None


def _answer(
    advisor: Advisor,
    squads: SquadStore,
    team: str,
    match: FixtureRow,
    gathered: Gathered,
    when: dt.datetime,
    *,
    past: bool,
    tried: Mapping[str, str],
    log: bool,
) -> CardResult:
    stored = advisor.rules.get(advisor.user)
    league, classic = scoring_rules(stored.rules if stored is not None else None)
    clubs = (match.home, match.away)
    sides = [
        side
        for side in gathered.sides
        if side.match is not None and (side.match.home, side.match.away) == clubs
    ]
    per_match = league_goals_per_match(gathered.teams, when)
    valued = [
        Valued(
            listed=Listed(player=side.player, role=side.form.role, present=side.present),
            value=model_value(model_inputs(side, per_match), scoring_for(league, side.form.role)),
            form=side.form,
        )
        for side in sides
        if side.present is not None
    ]
    xg = next((side.xg for side in sides if side.xg is not None), None)
    table = {club: row for club in clubs if (row := team_season(gathered.teams, club, when)) is not None}
    orders = {side.player.club: side.order for side in sides}
    listed = [part.listed for part in valued]
    card_sides = [
        _side(advisor, lineups(club, listed, match.kickoff_at), takers(orders.get(club), club, valued))
        for club in clubs
    ]
    squad = squads.get(advisor.user, team)
    yours = your_players(valued, {player.player_id for player in squad.players} if squad else set())
    named = [
        *(player_id for side in card_sides for player_id in side.eleven),
        *(c.player_id for side in card_sides for place in side.disputed for c in place.contenders),
        *(player.player_id for player in yours),
    ]
    by_id = {part.listed.player.player_id: part for part in valued}
    shown = [by_id[player_id] for player_id in dict.fromkeys(named)]
    sources = sources_of(sides)
    lines = source_lines(sources, advisor, when)
    times = [line.captured_at for line in lines]
    round = match.round
    lock = deadline(gathered.fixtures, round, when) or match.kickoff_at
    title = f"{advisor.clubs.names[match.home]} v {advisor.clubs.names[match.away]}"
    card = Card(
        round=round,
        match=title,
        kickoff=match.kickoff_at.astimezone(ROME),
        deadline=lock.astimezone(ROME),
        as_of=when,
        past_deadline=past,
        updated=Updated(newest=max(times), oldest=min(times)) if times else None,
        numbers=match_numbers(xg, match.home, match.away, table) if xg is not None else None,
        sides=card_sides,
        players=[card_player(part) for part in shown],
        scorers=likeliest_scorers(valued),
        rotation=rotation_risks(valued, {club: row.played for club, row in table.items()}),
        yours=[player.player_id for player in yours],
        classic_rules=classic,
        left_out=[
            *left_out(league),
            *(f"{rule.name}: counted in the full lineup, not in a card" for rule in league.formula_rules),
        ],
        sources=lines,
    )
    if log:
        advisor.log.append(
            Decision(
                kind="card",
                as_of=when,
                logged_at=advisor.clock(),
                user=advisor.user,
                round=round,
                players=[
                    logged_player(
                        part.listed.player.player_id, part.listed.player.name, part.value, playing=True
                    )
                    for part in shown
                ],
                rules=stored or StoredRules(user=advisor.user, saved_at=when, rules=league),
                content_hashes=sorted({source.content_sha256 for source in sources}),
            )
        )
    improve = [
        item.model_copy(update={"collector": tried[item.fact]}) if item.fact in tried else item
        for item in gathered.plan.items
    ]
    rounded = Card.model_validate(_rounded(card.model_dump()))
    return CardResult(status="card", message=_message(card, improve), card=rounded, improve=improve)


def _side(advisor: Advisor, found: Lineups, order: list[Taker]) -> CardSide:
    return CardSide(
        club=advisor.clubs.names[found.club],
        eleven=[starter.player_id for starter in found.eleven],
        official=found.official,
        official_due=found.official_due.astimezone(ROME) if found.official_due else None,
        disputed=found.disputed,
        out=found.out,
        takers=order,
    )


def _rounded(value: object) -> object:
    """Every chance and value to three decimals, so that a card stays within its size (R6.2)."""
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded(item) for item in value]
    return value


def _message(card: Card, improve: Sequence[RefreshItem]) -> str:
    said = [f"{card.match}, round {card.round}."]
    if card.past_deadline:
        said.append("The round's deadline has passed: this is the card as it stood then.")
    if card.numbers is None:
        said.append("Neither odds nor the table give this match's expected goals yet.")
    if not any(side.eleven for side in card.sides):
        said.append("The outlets haven't published lineups for it yet.")
    if card.classic_rules:
        said.append("Points are on Classic's rules: no league rules are stored.")
    if improve:
        said.append("Some facts could be better: see improve.")
    return " ".join(said)
