"""The match card's pure parts (mvp-cards design C2 to C4; R2 to R4).

This module knows what a card says about a fixture, from facts and values already worked out: the odds' team
xG, the table's rows and, in later tasks, each player's availability and value. It reads nothing and prices
nothing itself, so a card can't disagree with the other answers. The table's record and form are shown and
never used in a number (R2.4).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, SerializerFunctionWrapHandler, model_serializer

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import LeagueRules
from fantadamus.domains.availability.consensus import Availability
from fantadamus.domains.fixtures.silver import FixtureRow
from fantadamus.domains.odds.gold import TeamXg
from fantadamus.domains.players.resolve import KnownPlayer, resolve, same_surname
from fantadamus.domains.season.gold import PenaltyOrder
from fantadamus.domains.season.silver import PlayerSeasonRow, TeamSeasonRow
from fantadamus.domains.sources import Confidence, of_outlets
from fantadamus.engine import odds
from fantadamus.engine.constants import ROTATION_P_START, SCORERS, USUAL_SHARE
from fantadamus.engine.keepers import KeeperValue, clean_sheet
from fantadamus.engine.outfield import OutfieldValue
from fantadamus.league.rules import CLASSIC

OFFICIAL_DUE = dt.timedelta(hours=1)
"""The official lineups come out about an hour before kickoff (R3.4)."""
ROLES: tuple[Role, ...] = ("P", "D", "C", "A")


class Season(BaseModel):
    """A club's season so far, from the table: context beside the numbers, never in them."""

    played: int
    goals_for_per_match: float
    goals_against_per_match: float
    wins: int | None
    draws: int | None
    losses: int | None
    form: str | None
    """The last results as letters, oldest first."""


class Side(BaseModel):
    club: str
    p_win: float
    expected_goals: float
    p_clean_sheet: float
    """e^-xG of the other side's expected goals, as a keeper's is."""
    season: Season | None


class MatchNumbers(BaseModel):
    home: Side
    away: Side
    p_draw: float
    from_odds: bool
    """False when team form stood in for the odds."""
    spread: float | None
    """How far apart the odds pages' chances are; None with one page or none."""
    p_three_or_more: float | None
    p_both_score: float | None
    """Both None unless the odds showed over/under 2.5: the 1X2 alone, or team form, doesn't price goals."""


def season(row: TeamSeasonRow | None) -> Season | None:
    """The table's row for a club, per match; None without a row or before a match is played."""
    if row is None or not row.played:
        return None
    return Season(
        played=row.played,
        goals_for_per_match=row.goals_for / row.played,
        goals_against_per_match=row.goals_against / row.played,
        wins=row.wins,
        draws=row.draws,
        losses=row.losses,
        form=row.form,
    )


def match_numbers(xg: TeamXg, home: str, away: str, table: Mapping[str, TeamSeasonRow]) -> MatchNumbers:
    """The match in numbers (C2): the chances `team_xg` gives, each side's clean sheet, and the goals'
    chances where the odds price them; `table`, each club's latest row, only as its season so far."""
    market = odds.model(xg.home_xg, xg.away_xg) if xg.from_odds and xg.totals else None
    return MatchNumbers(
        home=Side(
            club=home,
            p_win=xg.p_home_win,
            expected_goals=xg.home_xg,
            p_clean_sheet=clean_sheet(xg.away_xg),
            season=season(table.get(home)),
        ),
        away=Side(
            club=away,
            p_win=xg.p_away_win,
            expected_goals=xg.away_xg,
            p_clean_sheet=clean_sheet(xg.home_xg),
            season=season(table.get(away)),
        ),
        p_draw=xg.p_draw,
        from_odds=xg.from_odds,
        spread=xg.spread if xg.from_odds and len(xg.sources) > 1 else None,
        p_three_or_more=market.p_over if market is not None else None,
        p_both_score=market.p_btts if market is not None else None,
    )


@dataclass(frozen=True)
class Listed:
    """One player the outlets list for a match, with how they see him."""

    player: KnownPlayer
    role: Role
    present: Availability


class Starter(BaseModel):
    player_id: int
    name: str
    role: Role
    p_start: float
    confidence: Confidence


class Contender(BaseModel):
    player_id: int
    name: str
    p_start: float
    dissent: list[str] = []
    """The outlets on the smaller side of the consensus, when the outlets disagree about him."""


class Place(BaseModel):
    """Disputed starting places: a ballottaggio with a likely starter in it, or the likely starters of one
    role the outlets disagree about, set against the next in line."""

    role: Role
    places: int = 1
    """How many starting places are in doubt among the contenders."""
    contenders: list[Contender]
    """Likeliest first."""


class Out(BaseModel):
    player_id: int
    name: str
    role: Role
    outlets: int
    """How many outlets list him as unavailable: why, and until when, they don't say."""


class Lineups(BaseModel):
    club: str
    eleven: list[Starter]
    """In role order, likeliest first."""
    official: bool
    official_due: dt.datetime | None
    """When the official lineups are due, until they're stored."""
    disputed: list[Place]
    out: list[Out]


def lineups(club: str, players: Sequence[Listed], kickoff: dt.datetime) -> Lineups:
    """One side's lineups (C3): the official eleven once stored, otherwise the eleven likeliest with one
    keeper, the likeliest; the disputed places until then; and who's out."""
    mine = [part for part in players if part.player.club == club]
    official = any(part.present.official is not None for part in mine)
    if official:
        picked = [
            part for part in mine if part.present.official and part.present.official.status == "starter"
        ]
    else:
        keepers = sorted((part for part in mine if part.role == "P"), key=_likeliest)
        picked = keepers[:1] + sorted((part for part in mine if part.role != "P"), key=_likeliest)[:10]
    eleven = sorted(picked, key=lambda part: (ROLES.index(part.role), *_likeliest(part)))
    return Lineups(
        club=club,
        eleven=[
            Starter(
                player_id=part.player.player_id,
                name=part.player.name,
                role=part.role,
                p_start=part.present.p_start,
                confidence=of_outlets(part.present),
            )
            for part in eleven
        ],
        official=official,
        official_due=None if official else kickoff - OFFICIAL_DUE,
        disputed=[] if official else _places(mine, {part.player.player_id for part in picked}),
        out=[
            Out(player_id=part.player.player_id, name=part.player.name, role=part.role, outlets=count)
            for part in sorted(mine, key=lambda part: (ROLES.index(part.role), part.player.name))
            if (count := sum(view.status == "unavailable" for view in part.present.outlets))
        ],
    )


def _likeliest(part: Listed) -> tuple[float, str]:
    return -part.present.p_start, part.player.name


def _places(mine: Sequence[Listed], eleven: Collection[int]) -> list[Place]:
    """The starting places in doubt (C3). Each ballottaggio with a likely starter in it is one place, its
    contenders joined whichever side named whom, a rival found by surname when the outlet writes him another
    way. Then, for each role, the likely starters the outlets disagree about share one place each, set against
    as many of the next in line: the likeliest of the role outside the eleven. A bench player the outlets
    disagree about is no starting place."""
    by_id = {part.player.player_id: part for part in mine}
    mates = [part.player for part in mine]
    group = {player_id: {player_id} for player_id in by_id}
    for part in mine:
        for view in part.present.outlets:
            if view.status != "ballottaggio":
                continue
            for name in view.rivals:
                rival = resolve(name, mates).player or same_surname(name, mates)
                if rival is not None:  # one of his club's, perhaps himself, which joins nothing
                    joined = group[part.player.player_id] | group[rival.player_id]
                    for member in joined:
                        group[member] = joined
    places: list[Place] = []
    seen: set[int] = set()
    for part in sorted(mine, key=_likeliest):
        members = group[part.player.player_id]
        if part.player.player_id in seen or len(members) == 1 or not members & set(eleven):
            continue
        seen |= members
        places.append(_place([by_id[member] for member in members], len(members & set(eleven))))
    for role in ROLES:
        held = [
            part
            for part in mine
            if part.role == role
            and part.player.player_id in eleven
            and part.player.player_id not in seen
            and part.present.disputed
        ]
        if not held:
            continue
        waiting = sorted(
            (
                part
                for part in mine
                if part.role == role
                and part.player.player_id not in eleven
                and part.player.player_id not in seen
                and part.present.p_start > 0
            ),
            key=_likeliest,
        )
        places.append(_place([*held, *waiting[: len(held)]], len(held)))
    return sorted(places, key=lambda place: ROLES.index(place.role))


def _place(members: Sequence[Listed], places: int) -> Place:
    contenders = sorted(members, key=_likeliest)
    return Place(
        role=contenders[0].role,
        places=places,
        contenders=[
            Contender(
                player_id=member.player.player_id,
                name=member.player.name,
                p_start=member.present.p_start,
                dissent=_dissent(member.present),
            )
            for member in contenders
        ],
    )


def _dissent(present: Availability) -> list[str]:
    """The outlets on the smaller side of the consensus, when the outlets disagree; none in an even split. The
    consensus is on the outlets' own scale, before the calibration map."""
    if not present.disputed:
        return []
    above = [view.outlet for view in present.outlets if view.p_start > present.raw_p_start]
    below = [view.outlet for view in present.outlets if view.p_start < present.raw_p_start]
    if len(above) == len(below):
        return []
    return sorted(above if len(above) < len(below) else below)


@dataclass(frozen=True)
class Valued:
    """A listed player with his value, as `player_outlook` works it out, and his season figures."""

    listed: Listed
    value: OutfieldValue | KeeperValue
    form: PlayerSeasonRow


class CardPlayer(BaseModel):
    player_id: int
    name: str
    club: str
    role: Role
    p_start: float
    confidence: Confidence
    p_scores: float | None = None
    """An outfield player's chance of scoring in the match, if he starts and from a cameo together."""
    p_scores_if_starts: float | None = None
    goal_share: float | None = None
    """His share of his side's expected goals."""
    p_clean_sheet: float | None = None
    expected_conceded: float | None = None
    """A keeper's."""
    key: float
    """What he's worth this round, under the scoring table: the ordering key (method §A3)."""

    @model_serializer(mode="wrap")
    def _without_empty(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        """A keeper has no scoring chances and an outfield player no clean sheet: their fields are left out,
        so that a card stays within its size (R6.2)."""
        found: dict[str, object] = handler(self)
        return {name: value for name, value in found.items() if value is not None}


class Scorer(BaseModel):
    player_id: int
    name: str
    club: str
    role: Role
    p_scores: float


class Taker(BaseModel):
    name: str
    """As his club-mates know him, or as the page writes him when none answers to it."""
    player_id: int | None
    penalties_scored: int | None
    penalties_taken: int | None


class RotationRisk(BaseModel):
    player_id: int
    name: str
    club: str
    role: Role
    p_start: float
    rated: int
    """His rated games this season, against his club's matches played."""
    played: int
    disputed: bool


def scoring_rules(stored: LeagueRules | None) -> tuple[LeagueRules, bool]:
    """The rules a card's points follow, and whether they're Classic's because none are stored (R4.6)."""
    return (stored, False) if stored is not None else (CLASSIC, True)


def card_player(part: Valued) -> CardPlayer:
    """What the match means for one player (C4), from the value the other answers give him."""
    value, player = part.value, part.listed.player
    found = CardPlayer(
        player_id=player.player_id,
        name=player.name,
        club=player.club,
        role=part.listed.role,
        p_start=part.listed.present.p_start,
        confidence=of_outlets(part.listed.present),
        key=value.key,
    )
    if isinstance(value, KeeperValue):
        return found.model_copy(
            update={"p_clean_sheet": value.p_clean_sheet, "expected_conceded": value.expected_conceded}
        )
    return found.model_copy(
        update={
            "p_scores": scoring_chance(value),
            "p_scores_if_starts": value.p_scores,
            "goal_share": value.goal_share,
        }
    )


def scoring_chance(value: OutfieldValue) -> float:
    """His chance of scoring in the match: if he starts, and from a cameo with a rating."""
    return value.p_start * value.p_scores + value.p_cameo * value.p_scores_cameo


def likeliest_scorers(parts: Sequence[Valued]) -> list[Scorer]:
    """The match's best chances of scoring, either club's, a likely cameo included."""
    found = [
        Scorer(
            player_id=part.listed.player.player_id,
            name=part.listed.player.name,
            club=part.listed.player.club,
            role=part.listed.role,
            p_scores=scoring_chance(part.value),
        )
        for part in parts
        if isinstance(part.value, OutfieldValue)
    ]
    return sorted(found, key=lambda scorer: (-scorer.p_scores, scorer.name))[:SCORERS]


def takers(order: PenaltyOrder | None, club: str, parts: Sequence[Valued]) -> list[Taker]:
    """The club's penalty takers in order, each found among his club-mates as `penalty_share` finds him,
    with his penalties scored and taken this season."""
    if order is None:
        return []
    mates = {part.listed.player.player_id: part for part in parts if part.listed.player.club == club}
    found = []
    for name in order.takers:
        player = resolve(name, [part.listed.player for part in mates.values()]).player
        form = mates[player.player_id].form if player is not None else None
        found.append(
            Taker(
                name=player.name if player is not None else name,
                player_id=player.player_id if player is not None else None,
                penalties_scored=form.penalties_scored if form is not None else None,
                penalties_taken=form.penalties_taken if form is not None else None,
            )
        )
    return found


def rotation_risks(parts: Sequence[Valued], played: Mapping[str, int]) -> list[RotationRisk]:
    """Players who usually start for their club, whose chance this round is low. One the outlets disagree
    about while he's still likely to start is in a disputed place instead, and one an outlet lists as out is
    out."""
    found = []
    for part in parts:
        present, player = part.listed.present, part.listed.player
        matches = played.get(player.club, 0)
        usual = matches > 0 and part.form.rated_appearances >= USUAL_SHARE * matches
        out = any(view.status == "unavailable" for view in present.outlets)
        if usual and not out and present.p_start < ROTATION_P_START:
            found.append(
                RotationRisk(
                    player_id=player.player_id,
                    name=player.name,
                    club=player.club,
                    role=part.listed.role,
                    p_start=present.p_start,
                    rated=part.form.rated_appearances,
                    played=matches,
                    disputed=present.disputed,
                )
            )
    return sorted(found, key=lambda risk: (ROLES.index(risk.role), risk.p_start, risk.name))


def your_players(parts: Sequence[Valued], squad: Collection[int]) -> list[CardPlayer]:
    """The user's players in the match, in role order and likeliest first."""
    mine = [part for part in parts if part.listed.player.player_id in squad]
    return [
        card_player(part)
        for part in sorted(mine, key=lambda part: (ROLES.index(part.listed.role), *_likeliest(part.listed)))
    ]


class FixtureLine(BaseModel):
    """One fixture of the round overview, team-level only (C6)."""

    home: str
    away: str
    kickoff: dt.datetime
    favourite: str | None = None
    """The likelier winner; None in an even match, or without numbers."""
    p_favourite: float | None = None
    p_draw: float | None = None
    home_goals: float | None = None
    away_goals: float | None = None
    home_clean_sheet: float | None = None
    away_clean_sheet: float | None = None
    p_three_or_more: float | None = None
    from_odds: bool = False
    """Without odds, team form gives the numbers; without either there are none."""


def round_lines(
    rows: Sequence[tuple[FixtureRow, TeamXg | None]], names: Mapping[str, str]
) -> list[FixtureLine]:
    """The round overview's lines, in kickoff order (R5.1), each from the match's team xG as a card has it."""
    found = []
    for match, xg in sorted(rows, key=lambda pair: (pair[0].kickoff_at, pair[0].home, pair[0].away)):
        line = FixtureLine(home=names[match.home], away=names[match.away], kickoff=match.kickoff_at)
        if xg is not None:
            numbers = match_numbers(xg, match.home, match.away, {})
            home, away = numbers.home, numbers.away
            favourite = (
                line.home if home.p_win > away.p_win else line.away if away.p_win > home.p_win else None
            )
            line = line.model_copy(
                update={
                    "favourite": favourite,
                    "p_favourite": max(home.p_win, away.p_win),
                    "p_draw": numbers.p_draw,
                    "home_goals": home.expected_goals,
                    "away_goals": away.expected_goals,
                    "home_clean_sheet": home.p_clean_sheet,
                    "away_clean_sheet": away.p_clean_sheet,
                    "p_three_or_more": numbers.p_three_or_more,
                    "from_odds": numbers.from_odds,
                }
            )
        found.append(line)
    return found
