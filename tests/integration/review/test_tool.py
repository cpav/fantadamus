"""mvp-review task 7.1: `review_round` through the tools, status by status (design C8; R1, R5.1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from fantadamus.web.fetch import Response
from tests.collect_harness import STATS_ROUTE
from tests.lineup_harness import AFTER_THE_ROUND, SQUAD, Round, a_round, finished, stats_after_rated
from tests.roles_data import stats_row
from tests.xy_harness import classic_with

pytestmark = pytest.mark.anyio


async def review(here: Round, **options: Any) -> dict[str, Any]:
    result = await here.client.call_tool("review_round", {"round": 10, **options})
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


async def test_statuses(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        advised = (await here.ask())["lineup"]
        early = await review(here)
        assert early["status"] == "not_ready"
        assert "finishes" in early["message"]

        finished(here)
        asked = await review(here)
        assert asked["status"] == "fielded"
        assert "as_advised" in asked["message"]

        unknown = await review(here, starters=["Nessuno Mai"])
        assert unknown["status"] == "refused"
        assert "Nessuno Mai" in unknown["message"]

        eleven = [player["name"] for player in advised["starters"]]
        two = await review(here, starters=["Uno", *eleven[1:]])  # Alfa Uno, Gamma Uno or Beta Uno?
        assert two["status"] == "choose"
        assert "Uno" in two["unresolved"]

        short = await review(here, starters=eleven[:10])
        assert short["status"] == "refused"

        reviewed = await review(here, as_advised=True)
        assert reviewed["status"] == "review", reviewed
        assert reviewed["review"]["choices"] == []
        again = await review(here)  # what was fielded is stored: no need to say it again
        assert again["status"] == "review"


async def test_no_statistics_after_the_round(tmp_path: Path) -> None:
    """The page can't be read, so no read after the round is stored: it says to ask again later."""
    async with a_round(tmp_path) as here:
        await here.ask()
        finished(here)
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(500, {}, b"")
        result = await review(here, as_advised=True)
    assert result["status"] == "not_ready"
    assert "statistics" in result["message"]


def _logged(tmp_path: Path) -> int:
    return sum(
        len(log.read_text(encoding="utf-8").splitlines()) for log in (tmp_path / "lake" / "reviews").glob("*")
    )


async def test_a_replay_reads_stores_and_logs_nothing(tmp_path: Path) -> None:
    """`as_of` replays an earlier time: it reads no page, keeps no lineup and logs no review."""
    async with a_round(tmp_path) as here:
        advised = (await here.ask())["lineup"]
        finished(here)
        pages = len(here.web.calls)
        early = await review(here, as_advised=True, as_of=AFTER_THE_ROUND.isoformat())
        assert early["status"] == "not_ready"  # no read after the round was stored by then, and none is made
        assert len(here.web.calls) == pages
        assert (await review(here, as_advised=True))["status"] == "review"
        logged = _logged(tmp_path)

        here.clock.now = AFTER_THE_ROUND + dt.timedelta(hours=2)
        into = advised["bench"][0]
        out = next(player for player in advised["starters"] if player["role"] == into["role"])
        other = await review(  # one swap, as a replay of an hour earlier
            here,
            starters=[into["name"] if p["name"] == out["name"] else p["name"] for p in advised["starters"]],
            bench=[out["name"] if p["name"] == into["name"] else p["name"] for p in advised["bench"]],
            as_of=(AFTER_THE_ROUND + dt.timedelta(hours=1)).isoformat(),
        )
        assert other["status"] == "review"
        assert _logged(tmp_path) == logged
        kept = await review(here)
    assert kept["review"]["choices"] == []  # still the lineup kept before the replay


async def test_a_defenders_clean_sheet_from_his_clubs_keeper(tmp_path: Path) -> None:
    """A league that gives defenders a clean sheet: the review reads each one's team's goals against from his
    club's keeper's rows, before and after the round."""
    async with a_round(tmp_path) as here:
        rules = classic_with(clean_sheet={"keeper": 1.0, "defender": 1.0}, lineup=None)
        assert not (await here.client.call_tool("set_league_rules", {"rules": rules})).is_error
        advised = (await here.ask())["lineup"]
        finished(here, stats_after_rated(conceded={"Alfa": 1}))
        result = await review(here, as_advised=True)
    found = result["review"]
    assert "clean sheets" not in found["not_counted"]
    starters = advised["starters"]
    kept_clean = sum(1 for player in starters if player["role"] == "D" and player["club"] != "Alfa")
    keeper = next(player for player in starters if player["role"] == "P")
    expected = 11 * 6.5 + kept_clean + (-1.0 if keeper["club"] == "Alfa" else 1.0)
    assert found["real"] == pytest.approx(expected)


async def test_after_the_squad_changed(tmp_path: Path) -> None:
    """A player advised for the round has left the squad since: the advice is still priced with him."""
    async with a_round(tmp_path) as here:
        advised = (await here.ask())["lineup"]
        gone = next(player["name"] for player in advised["bench"] if player["role"] == "D")
        await here.set_squad(*[name for name in SQUAD if name != gone], "Beta Due")
        finished(here)
        result = await review(here, as_advised=True)
    assert result["status"] == "review", result
    assert result["review"]["choices"] == []


async def test_a_player_nobody_knew_when_the_advice_was_given(tmp_path: Path) -> None:
    """A newcomer on the statistics page after the round, fielded: his choice can't be priced, so the review
    says why instead of answering."""
    async with a_round(tmp_path) as here:
        advised = (await here.ask())["lineup"]
        newcomer = stats_row("Alfa", "C", "C", 8099, name="Alfa Nuovo")
        finished(here, stats_after_rated(newcomers=[newcomer]))
        collector = here.calibrator.collector
        assert collector is not None
        here.collect_log.append(collector.collect(facts=["player_season"]))
        eleven = [player["name"] for player in advised["starters"]]
        dropped = next(name for name in SQUAD if name.endswith("Dodici") and name not in eleven)
        await here.set_squad(*[name for name in SQUAD if name != dropped], "Alfa Nuovo")
        out = next(player["name"] for player in advised["starters"] if player["role"] == "C")
        bench = [player["name"] for player in advised["bench"] if player["name"] != dropped]
        result = await review(
            here, starters=["Alfa Nuovo" if name == out else name for name in eleven], bench=bench
        )
    assert result["status"] == "refused", result
    assert "Alfa Nuovo" in result["message"]


async def test_what_it_cant_review(tmp_path: Path) -> None:
    """A round with no fixtures stored, and a team with no squad."""
    async with a_round(tmp_path, squad=False) as here:
        finished(here)
        no_squad = await review(here, as_advised=True)
        assert no_squad["status"] == "refused"
        assert "squad" in no_squad["message"]
        await here.set_squad()
        later = await here.client.call_tool("review_round", {"round": 30, "as_advised": True})
    assert later.structured_content is not None
    assert later.structured_content["status"] == "not_ready"
    assert "round 30" in later.structured_content["message"]
