"""AT-6 of mvp-store: the ratings are read only for the three answers that show a claim, and only the rows of
the clubs they are about; each log is read once for an answer (R3.3, R3.4)."""

from __future__ import annotations

import contextlib
import datetime as dt
from collections.abc import Collection, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from fantadamus.domains.ratings.silver import MATCH_RATINGS
from fantadamus.lake import jsonl
from fantadamus.lake.duckdb_store import LakeStore, Table
from tests.acceptance.sources.test_raters import _stored as stored_ratings
from tests.lineup_harness import Round, a_round
from tests.xy_harness import NOW

pytestmark = pytest.mark.anyio

Equals = Mapping[str, Collection[object]] | None
AT = NOW + dt.timedelta(hours=1)
"""An hour after the round's pages were read and the lineup was given: its answer is the previous one."""


@contextlib.contextmanager
def ratings_read(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Equals]]:
    """Each read of the ratings, by the values it asked for."""
    read_rows = LakeStore.read_rows
    seen: list[Equals] = []

    def recording(
        self: LakeStore,
        table: Table,
        since: dt.datetime | None = None,
        until: dt.datetime | None = None,
        *,
        newest_by: Sequence[str] = (),
        equals: Equals = None,
    ) -> list[dict[str, object]]:
        if table.name == MATCH_RATINGS.table.name:
            seen.append(equals)
        return read_rows(self, table, since, until, newest_by=newest_by, equals=equals)

    with monkeypatch.context() as patched:
        patched.setattr(LakeStore, "read_rows", recording)
        yield seen


async def _asked(here: Round, tool: str, **args: Any) -> dict[str, Any]:
    result = await here.client.call_tool(tool, {**args, "as_of": AT.isoformat()})
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


async def test_at6_ratings_only_where_a_claim_is_shown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with a_round(tmp_path) as here:
        await stored_ratings(here.client)
        await here.ask()  # the round's pages read, and the squad's lineup given
        asked: list[tuple[str, dict[str, Any]]] = [
            ("compare_players", {"first": "Beta Nove", "second": "Delta Nove"}),
            ("player_outlook", {"player": "Beta Nove"}),
            ("match_card", {"club": "Alfa"}),
            ("best_lineup", {}),
            ("round_overview", {}),
        ]
        reads, found = {}, {}
        for tool, args in asked:
            with ratings_read(monkeypatch) as seen:
                found[tool] = await _asked(here, tool, **args)
            reads[tool] = len(seen)
    for tool in ("compare_players", "player_outlook"):  # each replayed the lineup's time, and answered there
        moved = [player["movement"] for player in found[tool]["answer"]["players"]]
        assert all(move["basis"] == "previous answer" and move["p_start"] is not None for move in moved)
    # Once for each answer that shows a claim: the movement's replay shows none and reads none.
    assert reads == {
        "compare_players": 1,
        "player_outlook": 1,
        "match_card": 1,
        "best_lineup": 0,
        "round_overview": 0,
    }


async def test_at6_only_the_clubs_asked_about(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async with a_round(tmp_path) as here:
        await stored_ratings(here.client)
        await here.ask()
        with ratings_read(monkeypatch) as seen:
            compared = await _asked(here, "compare_players", first="Alfa Nove", second="Gamma Nove")
            outlook = await _asked(here, "player_outlook", player="Alfa Nove")
            card = await _asked(here, "match_card", club="Gamma")
    assert seen == [{"club": ["alfa", "gamma"]}, {"club": ["alfa"]}, {"club": ["delta", "gamma"]}]
    claims = {player["name"]: player.get("raters") for player in compared["answer"]["players"]}
    assert claims["Alfa Nove"]
    assert outlook["answer"]["players"][0]["raters"] == claims["Alfa Nove"]
    assert all("raters" not in player for player in card["card"]["players"])  # Alfa's ratings weren't read


async def test_at6_each_log_once_for_an_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An "X or Y?" with a movement asks the collection log four times and the decision log once: each of
    their files is parsed once."""
    async with a_round(tmp_path) as here:
        await here.ask()  # the round's pages read, and the squad's lineup given
        monkeypatch.setattr(jsonl, "_PARSED", {})
        parse = jsonl._parse
        parsed: list[str] = []

        def counting(path: Path, model: type[BaseModel]) -> list[BaseModel]:
            parsed.append(str(path.relative_to(tmp_path)))
            return parse(path, model)

        monkeypatch.setattr(jsonl, "_parse", counting)
        compared = await _asked(here, "compare_players", first="Beta Nove", second="Delta Nove")
    assert compared["answer"]["players"][0]["movement"]["basis"] == "previous answer"
    assert sorted(parsed) == sorted(set(parsed))  # each file once
    assert {Path(found).parent.name for found in parsed} >= {"collect", "decisions"}
