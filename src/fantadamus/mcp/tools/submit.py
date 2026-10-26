"""The submit tools: Claude reads an approved page and submits what it says (ADR-0005; design C2, C3).

Each tool takes the page's facts as its contract, so Claude sees the schema, plus where and when the page was
read. A rejected submission (a contract or quality rule, a host off the allowlist, an unknown club) is an
error whose text says why, and nothing is stored.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import AwareDatetime

from fantadamus.contracts.base import Contract
from fantadamus.contracts.xy.fixtures import FixturesPayload
from fantadamus.contracts.xy.lineups import OfficialLineupPayload, ProbableLineupPayload
from fantadamus.contracts.xy.season import PenaltyTakersPayload, PlayerSeasonPayload, TeamSeasonPayload
from fantadamus.core.clock import Clock
from fantadamus.core.clubs import Clubs
from fantadamus.domains import facts
from fantadamus.domains.availability.silver import LINEUP_VIEWS, OFFICIAL_LINEUPS
from fantadamus.domains.facts import Domain, Receipt
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.domains.season.silver import PENALTY_TAKERS, PLAYER_SEASONS, TEAM_SEASONS
from fantadamus.lake.duckdb_store import LakeStore

PROVENANCE = (
    "`source_url` is the page you read, which must be on the reading list; `captured_at` is when you read it "
    "and `published_at` when the page was published, if it says, both with a time zone. Write names as the "
    "page writes them. A rejected submission stores nothing and the error says why."
)


def register(
    server: MCPServer,
    store: LakeStore,
    *,
    allowed_hosts: Sequence[str],
    clock: Clock,
    submitted_by: str,
    clubs: Clubs,
) -> None:
    """Add the submit tools to `server`, storing into `store` as `submitted_by`."""
    hosts = tuple(allowed_hosts)

    def submit(
        domain: Domain[Any, Any],
        payload: Contract,
        source_url: str,
        captured_at: AwareDatetime,
        published_at: AwareDatetime | None,
    ) -> Receipt:
        try:
            return facts.submit(
                store,
                domain,
                payload,
                source_url=source_url,
                captured_at=captured_at,
                published_at=published_at,
                allowed_hosts=hosts,
                clock=clock,
                submitted_by=submitted_by,
                clubs=clubs,
            )
        except ValueError as rejection:  # the reason reaches Claude; other errors stay on the server
            raise ToolError(str(rejection)) from rejection

    @server.tool(
        description="Submit one round's matches and kickoff times from Wikipedia's Serie A season page. "
        + PROVENANCE
    )
    def submit_fixtures(
        payload: FixturesPayload,
        source_url: str,
        captured_at: AwareDatetime,
        published_at: AwareDatetime | None = None,
    ) -> Receipt:
        return submit(FIXTURES, payload, source_url, captured_at, published_at)

    @server.tool(
        description="Submit a player's Serie A season so far from his Fantacalcio.it profile: appearances, "
        "rated appearances, media voto, goals, assists, yellow cards, penalties and roles. " + PROVENANCE
    )
    def submit_player_season(
        payload: PlayerSeasonPayload,
        source_url: str,
        captured_at: AwareDatetime,
        published_at: AwareDatetime | None = None,
    ) -> Receipt:
        return submit(PLAYER_SEASONS, payload, source_url, captured_at, published_at)

    @server.tool(
        description="Submit the Serie A table from Wikipedia's season page: each club's matches played and "
        "goals for and against. " + PROVENANCE
    )
    def submit_team_season(
        payload: TeamSeasonPayload,
        source_url: str,
        captured_at: AwareDatetime,
        published_at: AwareDatetime | None = None,
    ) -> Receipt:
        return submit(TEAM_SEASONS, payload, source_url, captured_at, published_at)

    @server.tool(
        description="Submit each club's penalty takers, first choice first, from Fantacalcio.it's "
        "rigoristi page. " + PROVENANCE
    )
    def submit_penalty_takers(
        payload: PenaltyTakersPayload,
        source_url: str,
        captured_at: AwareDatetime,
        published_at: AwareDatetime | None = None,
    ) -> Receipt:
        return submit(PENALTY_TAKERS, payload, source_url, captured_at, published_at)

    @server.tool(
        description="Submit one outlet's probable lineups for one match, from Fantacalcio.it's probabili "
        "formazioni, Fantacalcio-Online's or SOS Fanta's page: each team's 11 expected starters, the "
        "ballottaggi with their percentages, the bench and the unavailable players. Submit each outlet "
        "separately, naming it in `outlet`. " + PROVENANCE
    )
    def submit_probable_lineups(
        payload: ProbableLineupPayload,
        source_url: str,
        captured_at: AwareDatetime,
        published_at: AwareDatetime | None = None,
    ) -> Receipt:
        return submit(LINEUP_VIEWS, payload, source_url, captured_at, published_at)

    @server.tool(
        description="Submit the official lineups of one match, from Fantacalcio.it's or SOS Fanta's "
        "formazioni ufficiali article, out about an hour before kickoff: both teams' starters and "
        "benches. " + PROVENANCE
    )
    def submit_official_lineup(
        payload: OfficialLineupPayload,
        source_url: str,
        captured_at: AwareDatetime,
        published_at: AwareDatetime | None = None,
    ) -> Receipt:
        return submit(OFFICIAL_LINEUPS, payload, source_url, captured_at, published_at)
