"""`compare_players`: "X or Y?" for two forwards (design C10; R1 to R4, R7, R9 to R12, R14).

1. A user without league rules gets the setup step.
2. Both names resolve to players with profiles, or the candidates come back.
3. The round is the next one whose deadline hasn't passed; a player whose club has no match in it isn't
   playing.
4. Every fact the answer needs is checked for freshness. Whatever is missing or stale goes into one refresh
   plan, lineups first, then odds, then season figures.
5. Otherwise the forward model answers, and the answer is logged.
"""

from __future__ import annotations

import datetime as dt
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer
from pydantic import AwareDatetime, BaseModel

from fantadamus.core.clock import Clock
from fantadamus.core.clubs import Clubs
from fantadamus.domains.availability.consensus import Availability, OfficialView, OutletView
from fantadamus.domains.availability.gold import availability
from fantadamus.domains.availability.silver import (
    LINEUP_VIEWS,
    OFFICIAL_LINEUPS,
    OUTLET_VIEWS,
    LineupViewRow,
    OutletViewRow,
)
from fantadamus.domains.facts import SilverRow, Source, read_silver
from fantadamus.domains.fixtures.gold import deadline, fixture, next_round
from fantadamus.domains.fixtures.silver import FIXTURES, FixtureRow
from fantadamus.domains.freshness import Fact, is_fresh
from fantadamus.domains.odds.gold import TeamXg, team_xg
from fantadamus.domains.odds.silver import ODDS
from fantadamus.domains.players.resolve import KnownPlayer, resolve
from fantadamus.domains.season.gold import (
    PenaltyOrder,
    known_players,
    penalty_order,
    player_form,
    team_season,
)
from fantadamus.domains.season.silver import (
    PENALTY_TAKERS,
    PLAYER_SEASONS,
    TEAM_SEASONS,
    PlayerSeasonRow,
    TeamSeasonRow,
)
from fantadamus.engine.forwards import ForwardInputs, ForwardValue, Verdict, compare
from fantadamus.lake.decision_log import Decision, DecisionLog, LoggedPlayer
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import RulesStore, SetupStep, StoredRules, scoring_for, setup_step

ROME = ZoneInfo("Europe/Rome")
DEFAULT_READING_LIST = Path("config/reading_list.toml")
_PLAN_ORDER = {
    "probable_lineups": 0,
    "match_odds": 1,
    "player_season": 2,
    "team_season": 2,
    "penalty_takers": 2,
}
_LATEST = dt.datetime.max.replace(tzinfo=dt.UTC)

Why = Literal["missing", "stale", "partial"]
"""`partial`: the match's odds show no over/under 2.5, which prices the bonuses (R5.4)."""


class ReadingItem(BaseModel):
    """One fact's entry in `config/reading_list.toml` (design C11)."""

    need: str
    submit_tool: str
    pages: list[str] = []
    search: list[str] = []


def load_reading_list(path: Path = DEFAULT_READING_LIST) -> dict[str, ReadingItem]:
    facts = tomllib.loads(path.read_text(encoding="utf-8"))["facts"]
    return {fact: ReadingItem.model_validate(entry) for fact, entry in facts.items()}


class RefreshItem(BaseModel):
    """A fact to read and submit: which, why, where, and with which tool (R11.1)."""

    fact: str
    why: Why
    about: str
    submit_tool: str
    pages: list[str]
    search: list[str]


class PlayerAnswer(BaseModel):
    """One player's side of the answer, with what it takes to give reasons (R10.3, R10.8)."""

    name: str
    player_id: int
    club: str
    role: str
    """His Classic role."""
    fixture: str | None
    kickoff: dt.datetime | None
    """In Europe/Rome."""
    opponent: str | None
    p_win: float | None
    p_draw: float | None
    p_loss: float | None
    """His team's chances, from the fitted odds or team form."""
    team_xg: float | None
    opponent_xg: float | None
    team_xg_from_odds: bool
    outlets: list[OutletView]
    """Each outlet's view, with his ballottaggio rivals by name."""
    official: OfficialView | None
    disputed: bool
    penalty_taker: bool
    """His club's first penalty taker."""
    penalties_scored: int
    penalties_taken: int
    appearances: int
    rated_appearances: int
    average_rating: float | None
    goals: int
    assists: int
    value: ForwardValue
    notes: list[str]
    sources: list[Source]


class Flip(BaseModel):
    """What would change the order: the leader's p_start or team xG falling below these (R10.4)."""

    player: str
    p_start_below: float | None
    team_xg_below: float | None


class Answer(BaseModel):
    message: str
    round: int
    deadline: dt.datetime
    """In Europe/Rome: the kickoff of the round's first match."""
    as_of: dt.datetime
    verdict: Verdict
    flip: Flip
    check_before_deadline: list[str]
    rules: StoredRules
    """The league rules this answer used (R12.4)."""
    players: list[PlayerAnswer]


class CompareResult(BaseModel):
    status: Literal["setup", "choose", "refresh", "forwards only", "answer"]
    message: str
    setup: SetupStep | None = None
    candidates: dict[str, list[KnownPlayer]] = {}
    refresh: list[RefreshItem] = []
    answer: Answer | None = None


@dataclass(frozen=True)
class _Facts:
    fixtures: list[FixtureRow]
    players: Sequence[Any]
    teams: Sequence[Any]
    takers: Sequence[Any]
    views: Sequence[Any]
    outlet_views: Sequence[Any]
    officials: Sequence[Any]
    odds: Sequence[Any]

    @classmethod
    def read(cls, lake: LakeStore) -> _Facts:
        return cls(
            fixtures=read_silver(lake, FIXTURES),
            players=read_silver(lake, PLAYER_SEASONS),
            teams=read_silver(lake, TEAM_SEASONS),
            takers=read_silver(lake, PENALTY_TAKERS),
            views=read_silver(lake, LINEUP_VIEWS),
            outlet_views=read_silver(lake, OUTLET_VIEWS),
            officials=read_silver(lake, OFFICIAL_LINEUPS),
            odds=read_silver(lake, ODDS),
        )


def _fresh[R: SilverRow](
    rows: Sequence[R], fact: Fact, as_of: dt.datetime, kickoff: dt.datetime | None = None
) -> list[R]:
    return [
        row
        for row in rows
        if row.captured_at <= as_of and is_fresh(row.captured_at, fact, as_of=as_of, kickoff=kickoff)
    ]


def _unique(sources: Sequence[Source]) -> list[Source]:
    return sorted(
        set(sources), key=lambda source: (source.captured_at, source.source_url, source.content_sha256)
    )


@dataclass(frozen=True)
class _Side:
    """One player with every fact his answer needs; `match` None means he isn't playing this round."""

    player: KnownPlayer
    form: PlayerSeasonRow
    table: TeamSeasonRow
    order: PenaltyOrder
    match: FixtureRow | None
    present: Availability | None
    xg: TeamXg | None


@dataclass(frozen=True)
class Advisor:
    """Everything `compare_players` reads and writes, for one user."""

    lake: LakeStore
    rules: RulesStore
    log: DecisionLog
    clubs: Clubs
    reading: dict[str, ReadingItem]
    user: str
    clock: Clock

    def _item(self, fact: str, why: Why, about: str, **values: str) -> RefreshItem:
        entry = self.reading[fact]
        fields = {"home": "", "away": "", "club": "", "player": ""} | values

        def fill(text: str) -> str:
            return " ".join(text.format(**fields).split())

        return RefreshItem(
            fact=fact,
            why=why,
            about=about,
            submit_tool=entry.submit_tool,
            pages=[fill(page) for page in entry.pages],
            search=[fill(hint) for hint in entry.search],
        )

    def _match_item(self, fact: str, why: Why, match: FixtureRow) -> RefreshItem:
        home, away = self.clubs.names[match.home], self.clubs.names[match.away]
        return self._item(fact, why, f"{home} v {away}", home=home, away=away)

    def compare(
        self, first: str, second: str, *, as_of: dt.datetime | None = None, odds_unavailable: bool = False
    ) -> CompareResult:
        as_of = (as_of or self.clock()).astimezone(dt.UTC)
        stored = self.rules.get(self.user)
        if stored is None:
            return CompareResult(
                status="setup",
                message="This user has no league rules yet: ask for them, then call set_league_rules.",
                setup=setup_step(),
            )
        facts = _Facts.read(self.lake)
        known = known_players(facts.players, as_of)
        plan: list[tuple[tuple[int, dt.datetime, str], RefreshItem]] = []

        def need(item: RefreshItem, kickoff: dt.datetime = _LATEST) -> None:
            if all((existing.fact, existing.about) != (item.fact, item.about) for _, existing in plan):
                plan.append(((_PLAN_ORDER.get(item.fact, 3), kickoff, item.about), item))

        players: list[KnownPlayer] = []
        candidates: dict[str, list[KnownPlayer]] = {}
        for name in (first, second):
            resolution = resolve(name, known)
            if resolution.candidates:
                candidates[name] = resolution.candidates
            elif resolution.player is None:
                need(self._item("player_season", "missing", f"{name}'s profile", player=name))
            else:
                players.append(resolution.player)
        if candidates:
            return CompareResult(
                status="choose",
                message="A name matches more than one player: ask which.",
                candidates=candidates,
            )
        forms = {player.player_id: player_form(facts.players, player.player_id, as_of) for player in players}
        others = [player.name for player in players if (form := forms[player.player_id]) and form.role != "A"]
        if others:
            return CompareResult(
                status="forwards only",
                message=f"This slice only compares forwards, and {', '.join(others)} isn't one.",
            )

        teams = _fresh(facts.teams, "team_season", as_of)
        takers = _fresh(facts.takers, "penalty_takers", as_of)
        for rows, fresh, fact, about in (
            (facts.teams, teams, "team_season", "the Serie A table"),
            (facts.takers, takers, "penalty_takers", "the penalty takers"),
        ):
            if not fresh:  # every answer needs them, whoever the players turn out to be
                why: Why = "stale" if any(row.captured_at <= as_of for row in rows) else "missing"
                need(self._item(fact, why, about))
        fixtures = _fresh(facts.fixtures, "fixtures", as_of)
        round = next_round(fixtures, as_of)
        if round is None:
            stale = next_round(facts.fixtures, as_of) is not None
            need(self._item("fixtures", "stale" if stale else "missing", "the next round's fixtures"))
        sides: list[_Side] = []
        for player in players:
            form = forms[player.player_id]
            if form is None or not _fresh([form], "player_season", as_of):
                about = f"{player.name}'s profile"
                need(self._item("player_season", "stale", about, player=player.name, club=player.club))
            table = team_season(teams, player.club, as_of)
            if table is None:
                stale = team_season(facts.teams, player.club, as_of) is not None
                need(self._item("team_season", "stale" if stale else "missing", "the Serie A table"))
            order = penalty_order(takers, player.club, as_of)
            if order is None:
                stale = penalty_order(facts.takers, player.club, as_of) is not None
                need(self._item("penalty_takers", "stale" if stale else "missing", "the penalty takers"))
            match = fixture(fixtures, player.club, round, as_of) if round is not None else None
            present, xg = (
                self._match_facts(player, match, facts, known, as_of, odds_unavailable, need)
                if match
                else (None, None)
            )
            if form is not None and table is not None and order is not None:
                sides.append(_Side(player, form, table, order, match, present, xg))

        first_kickoff = deadline(fixtures, round, as_of) if round is not None else None
        if plan or round is None or first_kickoff is None or len(sides) != 2:
            return CompareResult(
                status="refresh",
                message="Some facts are missing or stale. For each item, read the first listed page that "
                "opens, or find one with its search hint, submit what it says with the named tool, then call "
                "compare_players again.",
                refresh=[item for _, item in sorted(plan, key=lambda entry: entry[0])],
            )
        answer = self._answer(sides, known, round, first_kickoff, as_of, stored)
        return CompareResult(status="answer", message=answer.message, answer=answer)

    def _match_facts(
        self,
        player: KnownPlayer,
        match: FixtureRow,
        facts: _Facts,
        known: list[KnownPlayer],
        as_of: dt.datetime,
        odds_unavailable: bool,
        need: Callable[[RefreshItem, dt.datetime], None],
    ) -> tuple[Availability | None, TeamXg | None]:
        """His availability and team xG for the match, asking for whatever is missing or stale."""

        def available(
            views: Sequence[LineupViewRow], outlet_views: Sequence[OutletViewRow]
        ) -> Availability | None:
            return availability(
                player,
                home=match.home,
                away=match.away,
                views=views,
                outlet_views=outlet_views,
                officials=facts.officials,
                players=known,
                as_of=as_of,
            )

        present = available(
            _fresh(facts.views, "probable_lineups", as_of, match.kickoff_at),
            _fresh(facts.outlet_views, "probable_lineups", as_of, match.kickoff_at),
        )
        if present is None:
            stale = available(facts.views, facts.outlet_views) is not None
            need(
                self._match_item("probable_lineups", "stale" if stale else "missing", match), match.kickoff_at
            )
        fresh_odds = _fresh(facts.odds, "match_odds", as_of, match.kickoff_at)
        odds = [row for row in fresh_odds if (row.home, row.away) == (match.home, match.away)]
        teams = _fresh(facts.teams, "team_season", as_of) if odds_unavailable else []
        xg = team_xg(odds, teams, home=match.home, away=match.away, as_of=as_of)
        if not odds_unavailable and not odds:
            stale = any(
                row.home == match.home and row.away == match.away and row.captured_at <= as_of
                for row in facts.odds
            )
            need(self._match_item("match_odds", "stale" if stale else "missing", match), match.kickoff_at)
        elif not odds_unavailable and all(row.p_over is None for row in odds):
            need(self._match_item("match_odds", "partial", match), match.kickoff_at)
        return present, xg

    def _answer(
        self,
        sides: list[_Side],
        known: list[KnownPlayer],
        round: int,
        first_kickoff: dt.datetime,
        as_of: dt.datetime,
        stored: StoredRules,
    ) -> Answer:
        inputs = [self._inputs(side, known) for side in sides]
        result = compare(inputs[0], inputs[1], scoring_for(stored.rules, "A"))
        verdict = result.verdict
        players = [
            self._player_answer(side, value, taker.penalty_taker, round)
            for side, value, taker in zip(sides, result.values, inputs, strict=True)
        ]
        if not verdict.first_plays:
            message = f"Neither {verdict.first} nor {verdict.second} will play: field another forward."
        elif not verdict.second_plays:
            message = f"Start {verdict.first}; {verdict.second} won't play, "
            message += "so put a fit forward first on the bench."
        else:
            message = f"Start {verdict.first}, put {verdict.second} first on the bench."
            if verdict.no_cover_differs:
                message += f" Without bench cover, start {verdict.no_cover_first}."
        message += f" Margin {verdict.margin:.2f} points: {verdict.label}."
        answer = Answer(
            message=message,
            round=round,
            deadline=first_kickoff.astimezone(ROME),
            as_of=as_of,
            verdict=verdict,
            flip=Flip(
                player=verdict.first, p_start_below=result.flip_p_start, team_xg_below=result.flip_team_xg
            ),
            check_before_deadline=[
                f"{part.name} plays in the round's first match ({part.fixture}, "
                f"{part.kickoff:%a %d %b %H:%M} Rome time): his official lineup is out about an hour before "
                "the deadline, so check it then."
                for part in players
                if part.kickoff is not None and part.kickoff == first_kickoff
            ],
            rules=stored,
            players=players,
        )
        self.log.append(
            Decision(
                as_of=as_of,
                logged_at=self.clock(),
                user=self.user,
                round=round,
                players=[
                    LoggedPlayer(
                        player_id=part.player_id,
                        name=part.name,
                        p_start=part.value.p_start,
                        p_cameo=part.value.p_cameo,
                        p_scores=part.value.p_scores,
                        key=part.value.key,
                    )
                    for part in players
                ],
                first=verdict.first,
                second=verdict.second,
                margin=verdict.margin,
                label=verdict.label,
                rules=stored,
                content_hashes=sorted({source.content_sha256 for part in players for source in part.sources}),
            )
        )
        return answer

    @staticmethod
    def _inputs(side: _Side, known: list[KnownPlayer]) -> ForwardInputs:
        """The forward model's inputs; a player without a match has no chance of a rating (R2.3)."""
        mates = [mate for mate in known if mate.club == side.player.club]
        home = side.match is not None and side.match.home == side.player.club
        xg, present = side.xg, side.present
        return ForwardInputs(
            name=side.player.name,
            mantra_role=side.form.mantra_role,
            appearances=side.form.appearances,
            rated_appearances=side.form.rated_appearances,
            average_rating=side.form.average_rating,
            goals=side.form.goals,
            assists=side.form.assists,
            yellow_cards=side.form.yellow_cards,
            club_goals_per_match=side.table.goals_for / side.table.played if side.table.played else 0.0,
            penalty_taker=resolve(side.order.takers[0], mates).player == side.player,
            team_xg=(xg.home_xg if home else xg.away_xg) if xg else 0.0,
            p_win=(xg.p_home_win if home else xg.p_away_win) if xg else 0.0,
            p_loss=(xg.p_away_win if home else xg.p_home_win) if xg else 0.0,
            p_start=present.p_start if present else 0.0,
            p_cameo=present.p_cameo if present else 0.0,
        )

    def _player_answer(
        self, side: _Side, value: ForwardValue, penalty_taker: bool, round: int
    ) -> PlayerAnswer:
        match, present, xg = side.match, side.present, side.xg
        notes: list[str] = []
        sources = [side.form.source, side.table.source, side.order.source]
        if match is None:
            notes.append(f"{side.player.name} has no match in round {round}: counted as not playing.")
        else:
            sources.append(match.source)
        if present is not None:
            sources += [view.source for view in present.outlets]
            if present.official is not None:
                sources.append(present.official.source)
            if present.disputed:
                notes.append(f"The outlets disagree about {side.player.name} (spread {present.spread:.2f}).")
        if xg is not None:
            sources += xg.sources
            if not xg.from_odds:
                notes.append("Team xG comes from regressed team form: no match odds were found.")
            elif not xg.totals:
                notes.append("No over/under 2.5 was found: goal chances come from the 1X2 alone.")
        home = match is not None and match.home == side.player.club
        form = side.form
        return PlayerAnswer(
            name=side.player.name,
            player_id=side.player.player_id,
            club=side.player.club,
            role=form.role,
            fixture=f"{self.clubs.names[match.home]} v {self.clubs.names[match.away]}" if match else None,
            kickoff=match.kickoff_at.astimezone(ROME) if match else None,
            opponent=self.clubs.names[match.away if home else match.home] if match else None,
            p_win=(xg.p_home_win if home else xg.p_away_win) if xg else None,
            p_draw=xg.p_draw if xg else None,
            p_loss=(xg.p_away_win if home else xg.p_home_win) if xg else None,
            team_xg=(xg.home_xg if home else xg.away_xg) if xg else None,
            opponent_xg=(xg.away_xg if home else xg.home_xg) if xg else None,
            team_xg_from_odds=bool(xg and xg.from_odds),
            outlets=present.outlets if present else [],
            official=present.official if present else None,
            disputed=bool(present and present.disputed),
            penalty_taker=penalty_taker,
            penalties_scored=form.penalties_scored,
            penalties_taken=form.penalties_taken,
            appearances=form.appearances,
            rated_appearances=form.rated_appearances,
            average_rating=form.average_rating,
            goals=form.goals,
            assists=form.assists,
            value=value,
            notes=notes,
            sources=_unique(sources),
        )


def register(server: MCPServer, advisor: Advisor) -> None:
    """Add `compare_players` to `server`."""

    @server.tool(
        description='Answer "X or Y?" for two forwards for the next round, from the stored facts. It '
        "returns one of: the setup step (no league rules yet: ask the user, then call set_league_rules); "
        "candidates (a name matches several players: ask which); a refresh plan (facts missing or stale: "
        "read the listed pages, submit with the named tools, then call again); 'forwards only'; or the "
        "answer with its breakdown. Set odds_unavailable only after looking for the match odds on the listed "
        "pages and finding none: the answer then uses regressed team form and says so. as_of replays an "
        "earlier question."
    )
    def compare_players(
        first: str, second: str, as_of: AwareDatetime | None = None, odds_unavailable: bool = False
    ) -> CompareResult:
        return advisor.compare(first, second, as_of=as_of, odds_unavailable=odds_unavailable)
