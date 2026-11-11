"""The advisor behind `compare_players` and `player_outlook` (design C10; R1 to R4, R7, R9 to R12, R14;
mvp-roles design C9, R4, R5; mvp-lineup C5): the facts, the models and the steps the tools share.

1. A user without league rules gets the setup step.
2. Both names resolve to players with season figures, or the candidates come back.
3. The round is the next one whose deadline hasn't passed; a player whose club has no match in it isn't
   playing.
4. Every fact the answer needs is checked for freshness. Whatever is missing or stale goes into one refresh
   plan, lineups first, then odds, then season figures.
5. Otherwise each player's model answers: the keeper model or the outfield model. Two players of one role get
   a verdict; two roles get each player's outlook and no verdict, since that choice is the formation call. The
   answer is logged.
"""

from __future__ import annotations

import datetime as dt
import functools
import logging
import tomllib
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

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
from fantadamus.domains.facts import SilverRow, Source, latest_by, read_silver
from fantadamus.domains.fixtures.gold import deadline, fixture, matches, next_round
from fantadamus.domains.fixtures.silver import FIXTURES, FixtureRow
from fantadamus.domains.freshness import FACTS_WINDOW, Fact, is_fresh
from fantadamus.domains.odds.gold import TeamXg, team_xg
from fantadamus.domains.odds.silver import ODDS
from fantadamus.domains.players.resolve import KnownPlayer, resolve
from fantadamus.domains.season.gold import (
    PenaltyOrder,
    known_players,
    league_goals_per_match,
    order_change,
    penalty_mismatch,
    penalty_order,
    penalty_share,
    takers_ahead,
    team_season,
)
from fantadamus.domains.season.silver import (
    PENALTY_TAKERS,
    SEASON_STATS,
    TEAM_SEASONS,
    PenaltyTakerRow,
    PlayerSeasonRow,
    TeamSeasonRow,
    read_player_seasons,
)
from fantadamus.domains.sources import Confidence, describe, disagreement, of_odds, of_outlets, weaker
from fantadamus.engine import keepers, outfield
from fantadamus.engine.keepers import KeeperInputs, KeeperValue
from fantadamus.engine.lineup import ROLE_WORDS
from fantadamus.engine.outfield import OutfieldInputs, OutfieldValue
from fantadamus.engine.rank import Scoring, Verdict
from fantadamus.lake.calibration_store import CalibrationStore
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import Decision, DecisionLog, LoggedPlayer
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import RulesStore, SetupStep, StoredRules, left_out, scoring_for, setup_step
from fantadamus.league.squads import SquadStore
from fantadamus.web.cadence import may_read
from fantadamus.web.collector import PAGE_FACTS, Collector, CollectReport

ROME = ZoneInfo("Europe/Rome")
_LOG = logging.getLogger(__name__)
DEFAULT_READING_LIST = Path("config/reading_list.toml")
_PLAN_ORDER = {
    "probable_lineups": 0,
    "match_odds": 1,
    "player_season": 2,
    "team_season": 2,
    "penalty_takers": 2,
}
TAKES_PENALTIES = 0.5
"""An answer describes a player as taking the penalties from this share (mvp-lineup R10.2)."""
SHARE_SHOWN = 0.1
"""An answer explains a share from those listed ahead from here: below it, a sure starter is ahead of him."""
_BETTER_TO_HAVE = {"probable_lineups", "match_odds"}
"""What a lineup goes ahead without, on what's known and with a warning (mvp-lineup R5.5). "X or Y?" asks
first."""
_LATEST = dt.datetime.max.replace(tzinfo=dt.UTC)
REFRESH = (
    "Some facts are missing or stale. For each item read with `read_page`, read its pages best first until "
    "one gives the fact; for an item read with `search`, find a page on a listed site with its search hint. "
    "Submit what the page says with the named tool, with the page's `url` and `fetched_at`, then call "
    "the same tool again."
)

Why = Literal["missing", "stale", "partial"]
"""`partial`: the match's odds show no over/under 2.5, which prices the bonuses (R5.4)."""


class ReadingItem(BaseModel):
    """One fact's entry in `config/reading_list.toml` (design C11; mvp-collect C3.2)."""

    need: str
    submit_tool: str
    pages: list[str] = []
    search: list[str] = []
    patterns: list[str] = []
    """Addresses `read_page` also accepts, reached only through a link or a search (a profile)."""


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
    read_with: Literal["read_page", "search"]
    """`read_page` on the listed pages, best first; or, with no page listed, a search (mvp-collect C11)."""
    collector: str | None = None
    """What Fantadamus's collector tried for this fact, and why it didn't get it (R8.1)."""


class SourceUsed(Source):
    label: str
    """The page's name for the answer's Sources list, e.g. "Fantacalcio.it, table" (mvp-collect R6.3)."""


class Movement(BaseModel):
    """His numbers at an earlier time and the facts that moved them since (mvp-collect R6.1)."""

    since: dt.datetime
    basis: Literal["previous answer", "24 hours earlier"]
    """The user's previous answer that included him, or else 24 hours before this one."""
    p_start: float | None
    p_scores: float | None
    p_clean_sheet: float | None = None
    """A keeper's, in place of P(scores) (mvp-roles R3.5)."""
    p_win: float | None
    """Each value then; None where no answer could be given then."""
    changes: list[str]
    """E.g. "Gazzetta 55% → 90%", "official lineup out: starter", "team xG 1.20 → 1.45"; for a keeper,
    "opponent xG 1.20 → 1.45"."""


class Updated(BaseModel):
    """When the answer's facts were last captured or confirmed unchanged, newest and oldest (R6.2)."""

    newest: dt.datetime
    oldest: dt.datetime


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
    """Whether he's the likeliest to take his club's penalties: at least half are his (mvp-lineup R10.2)."""
    penalty_share: float
    """How much of the penalty term counts for him (mvp-lineup R10.1)."""
    penalties_scored: int
    penalties_taken: int
    appearances: int
    rated_appearances: int
    average_rating: float | None
    goals: int
    assists: int
    goals_conceded: int | None
    """A keeper's; none where his page didn't say (mvp-roles R3.5)."""
    value: OutfieldValue | KeeperValue
    p_start_confidence: Confidence | None
    """How sure his chance of starting (and of a cameo) is (mvp-collect R5.3)."""
    win_confidence: Confidence | None
    """How sure his team's chances and xG are."""
    p_scores_confidence: Confidence | None
    """How sure his chance of scoring, or a keeper's clean sheet, is: the weaker of the two."""
    notes: list[str]
    sources: list[SourceUsed]
    movement: Movement | None = None


class Flip(BaseModel):
    """What would change the order: an outfield leader's p_start or team xG falling below these (R10.4), or a
    keeper's opponent's xG rising above this (mvp-roles R4.1)."""

    player: str
    p_start_below: float | None = None
    team_xg_below: float | None = None
    opponent_xg_above: float | None = None


class Answer(BaseModel):
    message: str
    round: int
    deadline: dt.datetime
    """In Europe/Rome: the kickoff of the round's first match."""
    as_of: dt.datetime
    verdict: Verdict | None
    """None for two roles: each player's outlook, no verdict (mvp-roles R4.2)."""
    flip: Flip | None
    check_before_deadline: list[str]
    rules: StoredRules
    """The league rules this answer used (R12.4)."""
    left_out: list[str] = []
    """What the league uses that this answer's numbers leave out: its rules that can't be priced, with what
    they need, and its formula rules, which count in the full lineup only (mvp-rules R4.3)."""
    updated: Updated
    players: list[PlayerAnswer]


Status = Literal["setup", "choose", "refresh", "answer", "outlooks", "outlook"]


class CompareResult(BaseModel):
    status: Status
    message: str
    setup: SetupStep | None = None
    candidates: dict[str, list[KnownPlayer]] = {}
    refresh: list[RefreshItem] = []
    answer: Answer | None = None


@dataclass(frozen=True)
class Facts:
    fixtures: list[FixtureRow]
    players: Sequence[Any]
    teams: Sequence[Any]
    takers: Sequence[Any]
    views: Sequence[Any]
    outlet_views: Sequence[Any]
    officials: Sequence[Any]
    odds: Sequence[Any]

    @classmethod
    def read(cls, lake: LakeStore, as_of: dt.datetime) -> Facts:
        """The rows captured in the window up to `as_of`: no answer needs older ones (mvp-lineup C4)."""
        since = as_of - FACTS_WINDOW
        return cls(
            fixtures=read_silver(lake, FIXTURES, since, as_of),
            players=read_player_seasons(lake, since, as_of),
            teams=read_silver(lake, TEAM_SEASONS, since, as_of),
            takers=read_silver(lake, PENALTY_TAKERS, since, as_of),
            views=read_silver(lake, LINEUP_VIEWS, since, as_of),
            outlet_views=read_silver(lake, OUTLET_VIEWS, since, as_of),
            officials=read_silver(lake, OFFICIAL_LINEUPS, since, as_of),
            odds=read_silver(lake, ODDS, since, as_of),
        )


def _fresh[R: SilverRow](
    rows: Sequence[R],
    fact: Fact,
    as_of: dt.datetime,
    kickoff: dt.datetime | None = None,
    confirmed: Mapping[str, dt.datetime] | None = None,
    *,
    any_age: bool = False,
) -> list[R]:
    """The rows still fresh at `as_of`. A page's newest read counts from when a later read found it unchanged
    (`confirmed`, by page), since that read stored nothing new (mvp-collect R1.5). With `any_age`, every row
    stored by then counts: what was known, rather than whether to read it again (mvp-review C6)."""
    known = [row for row in rows if row.captured_at <= as_of]
    if any_age:
        return known
    newest: dict[str, dt.datetime] = {}
    for row in known:
        newest[row.source_url] = max(row.captured_at, newest.get(row.source_url, row.captured_at))
    confirmed = confirmed or {}

    def seen(row: R) -> dt.datetime:
        at = confirmed.get(row.source_url)
        return at if at is not None and row.captured_at == newest[row.source_url] < at else row.captured_at

    return [row for row in known if is_fresh(seen(row), fact, as_of=as_of, kickoff=kickoff)]


def _unique(sources: Sequence[Source]) -> list[SourceUsed]:
    return [
        SourceUsed(**source.model_dump(), label=describe(source.source_url))
        for source in sorted(
            set(sources), key=lambda source: (source.captured_at, source.source_url, source.content_sha256)
        )
    ]


@dataclass(frozen=True)
class PlayerFacts:
    """One player with every fact his answer needs; `match` None means he isn't playing this round."""

    player: KnownPlayer
    form: PlayerSeasonRow
    table: TeamSeasonRow
    order: PenaltyOrder
    match: FixtureRow | None
    present: Availability | None
    xg: TeamXg | None
    disagreements: list[str]
    """Where sources differ on his match's kickoff or his club's table (mvp-collect R5.1), and what his club's
    penalty list says about him (mvp-lineup R10.2, R10.4, R10.5)."""
    penalty_share: float
    """His share of his club's penalties (mvp-lineup R10.1)."""


@dataclass(frozen=True)
class _Recent:
    """The rows still fresh at one time, worked out once per kickoff: `_fresh` goes through every row, and a
    squad's players share a few kickoffs (mvp-lineup C4)."""

    as_of: dt.datetime
    confirmed: Mapping[str, Mapping[str, dt.datetime]]
    found: dict[tuple[str, dt.datetime], list[Any]]
    any_age: bool = False

    def of[R: SilverRow](self, rows: Sequence[R], fact: Fact, table: str, kickoff: dt.datetime) -> list[R]:
        key = (table, kickoff)
        if key not in self.found:
            self.found[key] = _fresh(
                rows, fact, self.as_of, kickoff, self.confirmed.get(table), any_age=self.any_age
            )
        return self.found[key]


class _Plan:
    """What's missing, each item once: lineups first, then odds, then season figures, the soonest match
    first."""

    def __init__(self) -> None:
        self._entries: list[tuple[tuple[int, dt.datetime, str], RefreshItem]] = []

    def need(self, item: RefreshItem, kickoff: dt.datetime = _LATEST) -> None:
        if all((existing.fact, existing.about) != (item.fact, item.about) for _, existing in self._entries):
            self._entries.append(((_PLAN_ORDER.get(item.fact, 3), kickoff, item.about), item))

    @property
    def items(self) -> list[RefreshItem]:
        return [item for _, item in sorted(self._entries, key=lambda entry: entry[0])]


@dataclass(frozen=True)
class Gathered:
    """Each player's facts at one time, and what's missing (mvp-lineup C5)."""

    sides: list[PlayerFacts]
    round: int | None
    first_kickoff: dt.datetime | None
    fixtures: list[FixtureRow]
    teams: list[TeamSeasonRow]
    plan: _Plan
    known: list[KnownPlayer]

    @property
    def needed(self) -> list[RefreshItem]:
        """Without these, no number can be given."""
        return [item for item in self.plan.items if item.fact not in _BETTER_TO_HAVE]

    @property
    def better(self) -> list[RefreshItem]:
        """Without these, a number rests on what's known."""
        return [item for item in self.plan.items if item.fact in _BETTER_TO_HAVE]


@dataclass(frozen=True)
class Collected[R]:
    """An answer, and what it rests on once the collector has had its turn."""

    result: R
    when: dt.datetime
    facts: Facts
    tried: Mapping[str, str]
    """What the collector found, by fact, for the plan's items."""


@dataclass(frozen=True)
class Advisor:
    """Everything `compare_players` and `player_outlook` read and write, for one user."""

    lake: LakeStore
    rules: RulesStore
    log: DecisionLog
    clubs: Clubs
    reading: dict[str, ReadingItem]
    user: str
    clock: Clock
    collector: Collector | None = None
    """Reads the round page when its facts are missing or stale (mvp-collect C11)."""
    collect_log: CollectLog | None = None
    """The collector's runs: each is logged, and a read that found a page unchanged keeps its facts fresh."""
    squads: SquadStore | None = None
    """Whether the user has a squad changes where a two-role question points (mvp-lineup R6.2)."""
    scores: CalibrationStore | None = None
    """The rounds scored so far, for the line in the next lineup (mvp-lineup R7.6)."""
    before_answering: Callable[[dt.datetime], object] | None = None
    """Scores a finished round if one is due (mvp-lineup R7.2)."""

    def get_ready(self, now: dt.datetime) -> None:
        """What's due before an answer goes out, once its own read of the pages has shown the next deadline.
        It never stops or changes one, so a failure is logged and left for later."""
        if self.before_answering is None:
            return
        try:
            self.before_answering(now)
        except Exception:
            _LOG.exception("Couldn't score a finished round; it's tried again later")

    def refresh_item(self, fact: str, why: Why, about: str, **values: str) -> RefreshItem:
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
            read_with="read_page" if entry.pages else "search",
        )

    def _match_item(self, fact: str, why: Why, match: FixtureRow) -> RefreshItem:
        home, away = self.clubs.names[match.home], self.clubs.names[match.away]
        return self.refresh_item(fact, why, f"{home} v {away}", home=home, away=away)

    def collect_now(self, facts: Collection[str], now: dt.datetime) -> CollectReport | None:
        """Ask the collector for those of `facts` its pages carry and may read now, and log the run; None if
        there are none (mvp-collect C11)."""
        if self.collector is None:
            return None
        wanted = {
            fact for fact in facts if self.collector.reads(fact) and may_read(fact, self.collect_log, now)
        }
        if not wanted:
            return None
        report = self.collector.collect(facts=sorted(wanted))
        if self.collect_log is not None:
            self.collect_log.append(report)
        return report

    def compare(
        self, first: str, second: str, *, as_of: dt.datetime | None = None, odds_unavailable: bool = False
    ) -> CompareResult:
        """The answer on two players."""
        return self._ask((first, second), as_of, odds_unavailable)

    def outlook(
        self, player: str, *, as_of: dt.datetime | None = None, odds_unavailable: bool = False
    ) -> CompareResult:
        """One player's forecast (mvp-roles R5)."""
        return self._ask((player,), as_of, odds_unavailable)

    def after_collecting[R](
        self,
        as_of: dt.datetime | None,
        ask: Callable[[dt.datetime, Facts, Mapping[str, str] | None], R],
        wanted: Callable[[R], Iterable[str]],
    ) -> Collected[R]:
        """`ask`'s answer, after the collector has read the pages of what it found missing or stale. A replay
        of an earlier `as_of` never collects. The lake's facts are read once, and again only after the
        collector stored something: a season of statistics rows costs 0.8 s a read (mvp-roles C2)."""
        when = (as_of or self.clock()).astimezone(dt.UTC)
        facts = Facts.read(self.lake, when)
        result = ask(when, facts, None)
        tried: Mapping[str, str] = {}
        report = self.collect_now(set(wanted(result)), when) if as_of is None else None
        if report is not None:
            tried = tried_notes(report)
            when = self.clock().astimezone(dt.UTC)
            if any(page.stored for page in report.pages):
                facts = Facts.read(self.lake, when)
            result = ask(when, facts, tried)
        if as_of is None:
            self.get_ready(when)
        return Collected(result, when, facts, tried)

    def _ask(self, names: Sequence[str], as_of: dt.datetime | None, odds_unavailable: bool) -> CompareResult:
        """The answer to a question about one or two players."""

        def ask(when: dt.datetime, facts: Facts, tried: Mapping[str, str] | None) -> CompareResult:
            return self.answer_at(names, when, odds_unavailable=odds_unavailable, facts=facts, tried=tried)

        done = self.after_collecting(as_of, ask, lambda found: [item.fact for item in found.refresh])
        result = done.result
        if result.answer is None:
            return result
        answer = self._with_movement(result.answer, names, odds_unavailable, done.facts)
        self._log(answer)
        return result.model_copy(update={"answer": answer})

    def answer_at(
        self,
        names: Sequence[str],
        as_of: dt.datetime,
        *,
        odds_unavailable: bool = False,
        facts: Facts | None = None,
        tried: Mapping[str, str] | None = None,
    ) -> CompareResult:
        """What the facts known at `as_of` answer, without collecting or logging; `facts`, when given, saves
        reading the lake again."""
        as_of = as_of.astimezone(dt.UTC)
        stored = self.rules.get(self.user)
        if stored is None:
            return CompareResult(
                status="setup",
                message="This user has no league rules yet: ask for them, then call set_league_rules.",
                setup=setup_step(None, lineup=False),
            )
        facts = facts or Facts.read(self.lake, as_of)
        known = known_players(facts.players, as_of)
        unknown: list[RefreshItem] = []
        players: list[KnownPlayer] = []
        candidates: dict[str, list[KnownPlayer]] = {}
        for name in names:
            resolution = resolve(name, known)
            if resolution.candidates:
                candidates[name] = resolution.candidates
            elif resolution.player is None:
                unknown.append(
                    self.refresh_item("player_season", "missing", f"{name}'s season figures", player=name)
                )
            else:
                players.append(resolution.player)
        if candidates:
            return CompareResult(
                status="choose",
                message="A name matches more than one player: ask which.",
                candidates=candidates,
            )
        gathered = self.gather(players, as_of, facts=facts, known=known, odds_unavailable=odds_unavailable)
        for item in unknown:
            gathered.plan.need(item)
        round, first_kickoff, sides = gathered.round, gathered.first_kickoff, gathered.sides
        refresh = gathered.plan.items
        if refresh or round is None or first_kickoff is None or len(sides) != len(names):
            if tried is not None:
                refresh = [
                    item.model_copy(update={"collector": tried[item.fact]}) if item.fact in tried else item
                    for item in refresh
                ]
            return CompareResult(
                status="refresh",
                message=REFRESH,
                refresh=refresh,
            )
        league = league_goals_per_match(gathered.teams, as_of)
        answer = self._answer(sides, known, round, first_kickoff, as_of, stored, league)
        kind = _kind(answer)
        return CompareResult(
            status="answer" if kind == "compare" else kind, message=answer.message, answer=answer
        )

    def gather(
        self,
        players: Sequence[KnownPlayer],
        as_of: dt.datetime,
        *,
        facts: Facts,
        known: list[KnownPlayer],
        odds_unavailable: bool = False,
        any_age: bool = False,
    ) -> Gathered:
        """Each player's facts at `as_of`, and what's missing or stale (mvp-lineup C5); with `any_age`, the
        facts stored by then however old, as a review prices them (mvp-review C6)."""
        confirmed = self.collect_log.confirmed(as_of) if self.collect_log is not None else {}
        plan = _Plan()
        need = plan.need
        recent = _Recent(as_of, confirmed, {}, any_age)
        fresh = functools.partial(_fresh, any_age=any_age)
        seasons = latest_by(facts.players, as_of, key=lambda row: row.player_id)
        forms = {player.player_id: seasons.get(player.player_id) for player in players}

        teams = fresh(facts.teams, "team_season", as_of)
        takers = fresh(
            facts.takers, "penalty_takers", as_of, confirmed=confirmed.get(PENALTY_TAKERS.table.name)
        )
        for rows, found, fact, about in (
            (facts.teams, teams, "team_season", "the Serie A table"),
            (facts.takers, takers, "penalty_takers", "the penalty takers"),
        ):
            if not found:  # every answer needs them, whoever the players turn out to be
                why: Why = "stale" if any(row.captured_at <= as_of for row in rows) else "missing"
                need(self.refresh_item(fact, why, about))
        fixtures = fresh(facts.fixtures, "fixtures", as_of, confirmed=confirmed.get(FIXTURES.table.name))
        round = next_round(fixtures, as_of)
        if round is None:
            stale = next_round(facts.fixtures, as_of) is not None
            need(self.refresh_item("fixtures", "stale" if stale else "missing", "the next round's fixtures"))
        sides: list[PlayerFacts] = []
        for player in players:
            form = forms[player.player_id]
            if form is None or not fresh(
                [form], "player_season", as_of, confirmed=confirmed.get(SEASON_STATS.table.name)
            ):
                about = f"{player.name}'s season figures"
                need(self.refresh_item("player_season", "stale", about, player=player.name, club=player.club))
            table = team_season(teams, player.club, as_of)
            if table is None:
                stale = team_season(facts.teams, player.club, as_of) is not None
                need(self.refresh_item("team_season", "stale" if stale else "missing", "the Serie A table"))
            order = penalty_order(takers, player.club, as_of)
            if order is None:
                stale = penalty_order(facts.takers, player.club, as_of) is not None
                need(
                    self.refresh_item("penalty_takers", "stale" if stale else "missing", "the penalty takers")
                )
            match = fixture(fixtures, player.club, round, as_of) if round is not None else None
            present, xg = (
                self._match_facts(player, match, facts, known, teams, as_of, odds_unavailable, need, recent)
                if match
                else (None, None)
            )
            if form is not None and table is not None and order is not None:
                mates = [mate for mate in known if mate.club == player.club]
                share = penalty_share(
                    player,
                    order,
                    mates,
                    functools.partial(
                        self._starts, match=match, facts=facts, known=known, as_of=as_of, recent=recent
                    ),
                )
                notes = self._disagreements(player, match, fixtures, teams, as_of)
                notes += self._taker_notes(player, order, mates, share, facts.takers, seasons, as_of)
                sides.append(PlayerFacts(player, form, table, order, match, present, xg, notes, share))

        first_kickoff = deadline(fixtures, round, as_of) if round is not None else None
        return Gathered(sides, round, first_kickoff, fixtures, teams, plan, known)

    def _disagreements(
        self,
        player: KnownPlayer,
        match: FixtureRow | None,
        fixtures: Sequence[FixtureRow],
        teams: Sequence[TeamSeasonRow],
        as_of: dt.datetime,
    ) -> list[str]:
        """Where the sources differ on his match's kickoff or his club's table, the one used first (R5.1)."""
        found = [
            disagreement(
                [row for row in teams if row.club == player.club],
                as_of,
                f"{self.clubs.names[player.club]}'s table",
                lambda row: f"{row.played} played, {row.goals_for} scored, {row.goals_against} conceded",
            )
        ]
        if match is not None:
            found.append(
                disagreement(
                    [row for row in fixtures if (row.home, row.away) == (match.home, match.away)],
                    as_of,
                    f"{self.clubs.names[match.home]} v {self.clubs.names[match.away]} kickoff",
                    lambda row: f"{row.kickoff_at.astimezone(ROME):%a %d %b %H:%M}",
                )
            )
        return [f"Sources disagree, the first is used: {note}." for note in found if note is not None]

    def _starts(
        self,
        mate: KnownPlayer,
        match: FixtureRow | None,
        facts: Facts,
        known: list[KnownPlayer],
        as_of: dt.datetime,
        recent: _Recent,
    ) -> float:
        """A listed taker's chance of starting; with no lineup known, nothing says he won't (R10.1)."""
        if match is None:
            return 1.0
        present = availability(
            mate,
            home=match.home,
            away=match.away,
            views=recent.of(facts.views, "probable_lineups", LINEUP_VIEWS.table.name, match.kickoff_at),
            outlet_views=recent.of(
                facts.outlet_views, "probable_lineups", OUTLET_VIEWS.table.name, match.kickoff_at
            ),
            officials=facts.officials,
            players=known,
            as_of=as_of,
        )
        return present.p_start if present is not None else 1.0

    def _taker_notes(
        self,
        player: KnownPlayer,
        order: PenaltyOrder,
        mates: Sequence[KnownPlayer],
        share: float,
        rows: Sequence[PenaltyTakerRow],
        seasons: Mapping[int, PlayerSeasonRow],
        as_of: dt.datetime,
    ) -> list[str]:
        """What an answer should say about his club's penalty list (mvp-lineup R10.2, R10.4, R10.5)."""
        club = self.clubs.names[player.club]
        notes = []
        ahead = takers_ahead(player, order, mates)
        if ahead and share >= SHARE_SHOWN:
            miss = "misses" if len(ahead) == 1 else "miss"
            notes.append(
                f"{player.name} takes {club}'s penalties if {' and '.join(ahead)} {miss} the start: "
                f"they count at {share:.0%}."
            )
        change = order_change(rows, player.club, as_of)
        if change is not None:
            notes.append(
                f"{club}'s penalty order changed on {change.at.astimezone(ROME):%d %b}: "
                f"{', '.join(change.after)} (was {', '.join(change.before)})."
            )
        mismatch = penalty_mismatch(player, order, mates, seasons)
        if mismatch is not None:
            first, other = mismatch.first, mismatch.other
            notes.append(
                f"{club}'s list puts {first.name} first, but {other.name} has taken more penalties this "
                "season: "
                f"{other.penalties_taken} (scored {other.penalties_scored}), against {first.penalties_taken} "
                f"(scored {first.penalties_scored}). The number follows the list."
            )
        return notes

    def _match_facts(
        self,
        player: KnownPlayer,
        match: FixtureRow,
        facts: Facts,
        known: list[KnownPlayer],
        teams: Sequence[TeamSeasonRow],
        as_of: dt.datetime,
        odds_unavailable: bool,
        need: Callable[[RefreshItem, dt.datetime], None],
        recent: _Recent,
    ) -> tuple[Availability | None, TeamXg | None]:
        """His availability and team xG for the match, asking for whatever is missing or stale. Without odds,
        team form gives the xG, for whoever goes ahead without them; "X or Y?" asks for the odds unless told
        there are none."""

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
            recent.of(facts.views, "probable_lineups", LINEUP_VIEWS.table.name, match.kickoff_at),
            recent.of(facts.outlet_views, "probable_lineups", OUTLET_VIEWS.table.name, match.kickoff_at),
        )
        if present is None:
            stale = available(facts.views, facts.outlet_views) is not None
            need(
                self._match_item("probable_lineups", "stale" if stale else "missing", match), match.kickoff_at
            )
        return present, self._match_xg(match, facts, teams, as_of, odds_unavailable, need, recent)

    def _match_xg(
        self,
        match: FixtureRow,
        facts: Facts,
        teams: Sequence[TeamSeasonRow],
        as_of: dt.datetime,
        odds_unavailable: bool,
        need: Callable[[RefreshItem, dt.datetime], None],
        recent: _Recent,
    ) -> TeamXg | None:
        """The match's team xG from its fresh odds, or team form without them, asking for the odds when
        they're missing or stale."""
        fresh_odds = recent.of(facts.odds, "match_odds", ODDS.table.name, match.kickoff_at)
        odds = [row for row in fresh_odds if (row.home, row.away) == (match.home, match.away)]
        xg = team_xg(odds, teams, home=match.home, away=match.away, as_of=as_of)
        if not odds_unavailable and not odds:
            stale = any(
                row.home == match.home and row.away == match.away and row.captured_at <= as_of
                for row in facts.odds
            )
            need(self._match_item("match_odds", "stale" if stale else "missing", match), match.kickoff_at)
        elif not odds_unavailable and all(row.p_over is None for row in odds):
            need(self._match_item("match_odds", "partial", match), match.kickoff_at)
        return xg

    def round_xg(
        self, as_of: dt.datetime, *, facts: Facts
    ) -> tuple[Gathered, list[tuple[FixtureRow, TeamXg | None]]]:
        """The next round's matches, each with its team xG as an answer prices it, and what's missing or
        stale, without gathering a player (mvp-cards C6)."""
        gathered = self.gather([], as_of, facts=facts, known=[])
        if gathered.round is None:
            return gathered, []
        confirmed = self.collect_log.confirmed(as_of) if self.collect_log is not None else {}
        recent = _Recent(as_of, confirmed, {})
        return gathered, [
            (match, self._match_xg(match, facts, gathered.teams, as_of, False, gathered.plan.need, recent))
            for match in matches(gathered.fixtures, as_of)
            if match.round == gathered.round
        ]

    def _answer(
        self,
        sides: list[PlayerFacts],
        known: list[KnownPlayer],
        round: int,
        first_kickoff: dt.datetime,
        as_of: dt.datetime,
        stored: StoredRules,
        league: float,
    ) -> Answer:
        inputs = [model_inputs(side, league) for side in sides]
        values = [
            model_value(part, scoring_for(stored.rules, side.form.role))
            for part, side in zip(inputs, sides, strict=True)
        ]
        players = [self._player_answer(side, value, round) for side, value in zip(sides, values, strict=True)]
        judged = _judged(inputs, scoring_for(stored.rules, sides[0].form.role))
        verdict, flip = judged if judged is not None else (None, None)
        if verdict is not None:
            message = _verdict_message(verdict, sides[0].form.role)
        else:
            message = _outlook_message(players[0]) if len(players) == 1 else self._outlooks_message(sides)
        answer = Answer(
            message=message,
            round=round,
            deadline=first_kickoff.astimezone(ROME),
            as_of=as_of,
            verdict=verdict,
            flip=flip,
            check_before_deadline=[
                f"{part.name} plays in the round's first match ({part.fixture}, "
                f"{part.kickoff:%a %d %b %H:%M} Rome time): his official lineup is out about an hour before "
                "the deadline, so check it then."
                for part in players
                if part.kickoff is not None and part.kickoff == first_kickoff and part.official is None
            ],
            rules=stored,
            left_out=[
                *left_out(stored.rules),
                *(
                    f"{rule.name}: counted in the full lineup, not in this answer"
                    for rule in stored.rules.formula_rules
                ),
            ],
            updated=self._updated(players, as_of),
            players=players,
        )
        return answer

    def _outlooks_message(self, sides: Sequence[PlayerFacts]) -> str:
        """Two roles: that choice is the formation call, which the lineup makes (mvp-lineup R6.2)."""
        who = " and ".join(f"{side.player.name} ({ROLE_WORDS[side.form.role]})" for side in sides)
        has_squad = self.squads is not None and self.squads.get(self.user) is not None
        where = (
            "best_lineup makes it for this squad" if has_squad else "set_squad, then best_lineup, makes it"
        )
        return (
            f"{who} play different roles: a choice between roles is the formation call, and {where}. "
            "Here is each player's outlook."
        )

    def _updated(self, players: list[PlayerAnswer], as_of: dt.datetime) -> Updated:
        """The newest and oldest time the facts were captured or a collector read found them unchanged."""
        worked = self.collect_log.last_worked(as_of) if self.collect_log is not None else {}
        times = [
            max(source.captured_at, worked.get(source.source_url, source.captured_at))
            for part in players
            for source in part.sources
        ]
        return Updated(newest=max(times), oldest=min(times))

    def _with_movement(
        self, answer: Answer, names: Sequence[str], odds_unavailable: bool, facts: Facts
    ) -> Answer:
        """Each player's movement since the user's previous answer that included him, or 24 hours (R6.1)."""
        decisions = [decision for decision in self.log.read() if decision.user == self.user]
        earlier: dict[dt.datetime, CompareResult] = {}
        players = []
        for part in answer.players:
            previous = [
                decision.as_of
                for decision in decisions
                if decision.as_of < answer.as_of
                and any(logged.player_id == part.player_id for logged in decision.players)
            ]
            since = max(previous, default=answer.as_of - dt.timedelta(hours=24))
            if since not in earlier:
                earlier[since] = self.answer_at(names, since, odds_unavailable=odds_unavailable, facts=facts)
            then = earlier[since].answer
            before = next((p for p in then.players if p.player_id == part.player_id), None) if then else None
            basis: Literal["previous answer", "24 hours earlier"] = (
                "previous answer" if previous else "24 hours earlier"
            )
            players.append(part.model_copy(update={"movement": movement(before, part, since, basis)}))
        return answer.model_copy(update={"players": players})

    def _log(self, answer: Answer) -> None:
        """One decision-log line per answer (R14.1; mvp-roles R5.3, R6.3)."""
        verdict = answer.verdict
        self.log.append(
            Decision(
                kind=_kind(answer),
                as_of=answer.as_of,
                logged_at=self.clock(),
                user=self.user,
                round=answer.round,
                players=[
                    logged_player(part.player_id, part.name, part.value, playing=part.fixture is not None)
                    for part in answer.players
                ],
                first=verdict.first if verdict else None,
                second=verdict.second if verdict else None,
                margin=verdict.margin if verdict else None,
                label=verdict.label if verdict else None,
                rules=answer.rules,
                content_hashes=sorted(
                    {source.content_sha256 for part in answer.players for source in part.sources}
                ),
            )
        )

    def _player_answer(
        self, side: PlayerFacts, value: OutfieldValue | KeeperValue, round: int
    ) -> PlayerAnswer:
        match, present, xg = side.match, side.present, side.xg
        notes = list(side.disagreements)
        start_confidence = of_outlets(present) if present is not None else None
        win_confidence = of_odds(xg) if xg is not None else None
        scores_confidence = (
            weaker(start_confidence, win_confidence)
            if start_confidence is not None and win_confidence is not None
            else start_confidence or win_confidence
        )
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
            if present.by_surname:
                written = ", ".join(present.by_surname)
                notes.append(f"The outlets write {written}: matched to {side.player.name} by surname.")
        if xg is not None:
            sources += xg.sources
            if not xg.from_odds:
                notes.append("Team xG comes from regressed team form: no match odds were found.")
            elif not xg.totals:
                notes.append("No over/under 2.5 was found: goal chances come from the 1X2 alone.")
        home = match is not None and match.home == side.player.club
        form = side.form
        if form.role == "P" and form.goals_conceded is None:
            notes.append(f"{side.player.name}'s goals conceded aren't known: an average defence is assumed.")
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
            penalty_taker=side.penalty_share >= TAKES_PENALTIES,
            penalty_share=side.penalty_share,
            penalties_scored=form.penalties_scored,
            penalties_taken=form.penalties_taken,
            appearances=form.appearances,
            rated_appearances=form.rated_appearances,
            average_rating=form.average_rating,
            goals=form.goals,
            assists=form.assists,
            goals_conceded=form.goals_conceded,
            value=value,
            p_start_confidence=start_confidence,
            win_confidence=win_confidence,
            p_scores_confidence=scores_confidence,
            notes=notes,
            sources=_unique(sources),
        )


def movement(
    before: PlayerAnswer | None,
    now: PlayerAnswer,
    since: dt.datetime,
    basis: Literal["previous answer", "24 hours earlier"],
) -> Movement:
    """His numbers `before` (None if no answer could be given then) and the facts that moved them: an outlet's
    view, the official lineup coming out, his team's xG."""
    if before is None:
        return Movement(since=since, basis=basis, p_start=None, p_scores=None, p_win=None, changes=[])
    then = before.value
    changes: list[str] = []
    if now.official is not None and before.official is None:
        changes.append(f"official lineup out: {now.official.status}")
    views = {view.outlet: view for view in before.outlets}
    for view in now.outlets:
        old = views.get(view.outlet)
        if old is None:
            changes.append(f"{view.outlet} now {view.p_start:.0%}")
        elif round(old.p_start, 2) != round(view.p_start, 2):
            changes.append(f"{view.outlet} {old.p_start:.0%} → {view.p_start:.0%}")
    side, xg_then, xg_now = (
        ("opponent xG", before.opponent_xg, now.opponent_xg)
        if isinstance(then, KeeperValue)
        else ("team xG", before.team_xg, now.team_xg)
    )
    if xg_then is not None and xg_now is not None and abs(xg_now - xg_then) >= 0.05:
        changes.append(f"{side} {xg_then:.2f} → {xg_now:.2f}")
    return Movement(
        since=since,
        basis=basis,
        p_start=then.p_start,
        p_scores=then.p_scores if isinstance(then, OutfieldValue) else None,
        p_clean_sheet=then.p_clean_sheet if isinstance(then, KeeperValue) else None,
        p_win=before.p_win,
        changes=changes,
    )


def tried_notes(report: CollectReport) -> dict[str, str]:
    """For each fact the run's pages carry, what was tried, for the refresh items it couldn't fill."""
    tried: dict[str, str] = {}
    for page in report.pages:
        reason = f" ({page.reason})" if page.reason else ""
        said = (
            f"Fantadamus read {page.url}, which doesn't give it yet"
            if page.outcome in {"stored", "unchanged"}
            else f"Fantadamus couldn't read {page.url}: {page.outcome}{reason}"
        )
        tried |= dict.fromkeys(PAGE_FACTS[page.page], said)
    return tried


def model_inputs(side: PlayerFacts, league: float) -> OutfieldInputs | KeeperInputs:
    """His model's inputs; a player without a match has no chance of a rating (R2.3)."""
    home = side.match is not None and side.match.home == side.player.club
    xg, present, form = side.xg, side.present, side.form
    if form.role == "P":
        return KeeperInputs(
            name=side.player.name,
            club=side.player.club,
            rated_appearances=form.rated_appearances,
            average_rating=form.average_rating,
            goals_conceded=form.goals_conceded,
            league_goals_per_match=league,
            opponent_xg=(xg.away_xg if home else xg.home_xg) if xg else 0.0,
            p_start=present.p_start if present else 0.0,
        )
    return OutfieldInputs(
        name=side.player.name,
        role=form.role,
        mantra_role=form.mantra_role,
        appearances=form.appearances,
        rated_appearances=form.rated_appearances,
        average_rating=form.average_rating,
        goals=form.goals,
        assists=form.assists,
        yellow_cards=form.yellow_cards,
        club_goals_per_match=side.table.goals_for / side.table.played if side.table.played else 0.0,
        penalty_share=side.penalty_share,
        penalties_scored=form.penalties_scored,
        team_xg=(xg.home_xg if home else xg.away_xg) if xg else 0.0,
        p_win=(xg.p_home_win if home else xg.p_away_win) if xg else 0.0,
        p_loss=(xg.p_away_win if home else xg.p_home_win) if xg else 0.0,
        p_start=present.p_start if present else 0.0,
        p_cameo=present.p_cameo if present else 0.0,
        opponent_xg=(xg.away_xg if home else xg.home_xg) if xg else None,
    )


def model_value(player: OutfieldInputs | KeeperInputs, scoring: Scoring) -> OutfieldValue | KeeperValue:
    if isinstance(player, KeeperInputs):
        return keepers.value(player, scoring)
    return outfield.value(player, scoring)


def _judged(inputs: Sequence[OutfieldInputs | KeeperInputs], scoring: Scoring) -> tuple[Verdict, Flip] | None:
    """The verdict on two players of one role and what would flip it; None otherwise (mvp-roles R4)."""
    if len(inputs) != 2:
        return None
    a, b = inputs
    if isinstance(a, KeeperInputs) and isinstance(b, KeeperInputs):
        kept = keepers.compare(a, b, scoring)
        return kept.verdict, Flip(player=kept.verdict.first, opponent_xg_above=kept.flip_opponent_xg)
    if isinstance(a, OutfieldInputs) and isinstance(b, OutfieldInputs) and a.role == b.role:
        played = outfield.compare(a, b, scoring)
        flip = Flip(
            player=played.verdict.first,
            p_start_below=played.flip_p_start,
            team_xg_below=played.flip_team_xg,
        )
        return played.verdict, flip
    return None


def _verdict_message(verdict: Verdict, role: str) -> str:
    word = ROLE_WORDS[role]
    first, second = verdict.first, verdict.second
    if verdict.first_plays and verdict.label == "covered":
        return (
            f"Field {first}, the likelier starter. {second}, of the same club, plays exactly when he "
            "doesn't, so the place is covered."
        )
    if not verdict.first_plays:
        message = f"Neither {first} nor {second} will play: field another {word}."
    elif not verdict.second_plays:
        message = f"Start {first}; {second} won't play, so put a fit {word} first on the bench."
    else:
        message = f"Start {first}, put {second} first on the bench."
        if verdict.no_cover_differs:
            message += f" Without bench cover, start {verdict.no_cover_first}."
    return message + f" Margin {verdict.margin:.2f} points: {verdict.label}."


def _outlook_message(part: PlayerAnswer) -> str:
    who, value = f"{part.name} ({ROLE_WORDS[part.role]})", part.value
    if value.p_start + value.p_cameo == 0:
        return f"{who} won't play this round."
    return f"{who}: {value.p_start:.0%} to start, worth about {value.e_start:.1f} if he does."


def _kind(answer: Answer) -> Literal["compare", "outlooks", "outlook"]:
    if answer.verdict is not None:
        return "compare"
    return "outlooks" if len(answer.players) == 2 else "outlook"


def logged_player(
    player_id: int, name: str, value: OutfieldValue | KeeperValue, *, playing: bool
) -> LoggedPlayer:
    """A keeper without a match has no clean sheet to log: he isn't playing."""
    keeper = value if isinstance(value, KeeperValue) and playing else None
    return LoggedPlayer(
        player_id=player_id,
        name=name,
        p_start=value.p_start,
        p_cameo=value.p_cameo,
        p_rating=value.p_rating,
        p_scores=value.p_scores if isinstance(value, OutfieldValue) else None,
        key=value.key,
        p_clean_sheet=keeper.p_clean_sheet if keeper else None,
        expected_conceded=keeper.expected_conceded if keeper else None,
    )
