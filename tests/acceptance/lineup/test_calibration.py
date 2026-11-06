"""AT-12: a finished round scores itself at the next question, once, on both sets; the next lineup carries the
line, and `fantadamus calibrate` prints the report (R7.2 to R7.6)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.cli import __main__ as cli
from fantadamus.domains.calibration import Scored
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, ROUND_ROUTE, STATS_ROUTE
from tests.collect_pages import FcoMatch, fco_name, fco_round_page
from tests.lineup_harness import Round, a_round, stats_after, the_next_round

pytestmark = pytest.mark.anyio

ROUND_10 = "/probabili-formazioni/10-giornata"
AFTER = dt.datetime(2026, 11, 1, 5, 0, tzinfo=dt.UTC)  # 12 hours after the round's last kickoff
STARTER = (0.9 + 0.9 + 0.95 + 0.9) / 4  # the outlets' default for a listed starter
BENCH = (0.1 + 0.3 + 0.05 + 0.3) / 4  # and for a listed bench player


def _chance(chances: list[Scored], name: str) -> Scored:
    return next(chance for chance in chances if chance.chance == name)


def _said(chance: Scored) -> float:
    return sum(bucket.said * bucket.count for bucket in chance.buckets)


async def test_at12_a_round_scores_itself(tmp_path: Path) -> None:
    finished = fco_round_page(
        FcoMatch("Alfa", "Beta", confirmed=True),
        FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", confirmed=True),
    )
    async with a_round(tmp_path) as here:
        before = (await here.ask())["lineup"]
        assert before["last_round"] is None
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, finished.encode())
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now = AFTER
        result = await here.ask()
        assert result["status"] == "lineup", result
        report = here.scores.get(10)
        assert report is not None
        calls = [url for url, _, _ in here.web.calls].count(f"{here.base}{ROUND_10}")
        again = await here.ask()
    assert calls == 1
    assert [url for url, _, _ in here.web.calls].count(f"{here.base}{ROUND_10}") == 1  # once

    # The next lineup says how it went, and nothing else about it changed.
    assert result["lineup"]["round"] == 11
    assert "Round 10's forecasts" in result["lineup"]["last_round"]
    assert again["lineup"]["last_round"] == result["lineup"]["last_round"]

    # The model on everyone. In each of the 4 clubs, 11 listed starters started, 2 listed bench players
    # didn't, and the one the page lists as out didn't: 56 players at the outlets' chances, by hand.
    starting = _chance(report.model.scored, "Starting")
    assert starting.count == 4 * 14
    expected = (44 * (1 - STARTER) ** 2 + 8 * BENCH**2) / 56
    assert starting.brier == pytest.approx(expected, abs=0.001)
    assert starting.baseline == pytest.approx((44 / 56) * (12 / 56), abs=0.001)

    # What users were told: the squad's 25 players, from the one lineup before kickoff.
    told = _chance(report.told.scored, "Starting")
    assert told.count == 25
    assert told.brier == pytest.approx(
        sum((1 - STARTER) ** 2 if name.split()[1] != "Dodici" else BENCH**2 for name in here.squad_names)
        / 25,
        abs=0.001,
    )

    # From what the statistics page gained: Alfa Nove and Beta Nove scored; the Alfa keeper conceded,
    # Gamma's didn't.
    scoring = _chance(report.model.scored, "Scoring, if he started")
    assert scoring.count == 4 * 8 + 4 * 2  # the outfield starters of 4 clubs: 10 each
    assert sum(bucket.happened * bucket.count for bucket in scoring.buckets) == pytest.approx(2, abs=0.01)
    clean = _chance(report.model.scored, "Clean sheet, if he started")
    assert clean.count == 4
    assert sum(bucket.happened * bucket.count for bucket in clean.buckets) == pytest.approx(3, abs=0.01)
    rated = _chance(report.model.scored, "Getting a rating")
    assert rated.count == 4 * 14
    assert sum(bucket.happened * bucket.count for bucket in rated.buckets) == pytest.approx(44, abs=0.01)
    assert _said(rated) > _said(starting)  # a cameo gets a rating too
    assert _chance(report.told.scored, "Getting a rating").count == 25


async def test_at12_an_official_lineup_never_feeds_the_model(tmp_path: Path) -> None:
    """The lineup comes out before kickoff, and an answer logs it. What the user was told counts it; the model
    on everyone is scored on the forecast, so it doesn't."""
    live = fco_round_page(
        FcoMatch("Alfa", "Beta", confirmed=True),
        FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", confirmed=True),
    )
    async with a_round(tmp_path) as here:
        await here.ask()
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, live.encode())
        here.clock.now = dt.datetime(2026, 10, 31, 13, 0, tzinfo=dt.UTC)  # an hour before the first kickoff
        await here.ask()
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, live.encode())
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now = AFTER
        await here.ask()
        assert here.scores.get(10) is None  # that answer read the statistics under a day ago, so this waits
        assert ROUND_10 not in " ".join(url for url, _, _ in here.web.calls)
        here.clock.now += dt.timedelta(hours=9)
        await here.ask()
        report = here.scores.get(10)
    assert report is not None
    model = _chance(report.model.scored, "Starting")
    told = _chance(report.told.scored, "Starting")
    assert model.brier > 0.005  # not the 0 an official lineup would give
    assert told.brier == pytest.approx(0.0, abs=0.001)  # they were told, an hour before: certain, and right


async def test_at12_what_cant_be_scored_is_named(tmp_path: Path) -> None:
    """No read of the statistics page after the round, in time: what needs one is named, with the reason."""
    finished = fco_round_page(
        FcoMatch("Alfa", "Beta", confirmed=True),
        FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", confirmed=True),
    )
    async with a_round(tmp_path) as here:
        await here.ask()
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, finished.encode())
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(500, {}, b"")
        here.clock.now = dt.datetime(2026, 11, 7, 15, 0, tzinfo=dt.UTC)  # the next round has begun
        await here.ask()
        report = here.scores.get(10)
    assert report is not None
    assert _chance(report.model.scored, "Starting").count == 56
    reasons = {entry.reason: entry.count for entry in report.model.unscored}
    assert reasons["Getting a rating: no statistics read after the round"] == 56
    assert not [chance for chance in report.model.scored if chance.chance == "Getting a rating"]


async def test_at12_starting_needs_only_the_page(tmp_path: Path) -> None:
    """With nothing read before kickoff, the finished page's own percentages still give Starting, and the rest
    is named as unscored (design C10)."""
    finished = fco_round_page(
        FcoMatch("Alfa", "Beta", confirmed=True),
        FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", confirmed=True),
    )
    async with a_round(tmp_path) as here:
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, finished.encode())
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, finished.encode())
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now = AFTER
        await here.ask()
        report = here.scores.get(10)
    assert report is not None
    starting = _chance(report.model.scored, "Starting")
    assert starting.count == 56
    assert starting.brier == pytest.approx((44 * (1 - STARTER) ** 2 + 8 * BENCH**2) / 56, abs=0.001)
    assert [chance.chance for chance in report.model.scored] == ["Starting"]
    assert {entry.reason: entry.count for entry in report.model.unscored} == {
        "Chances other than starting: no facts held before his kickoff": 56
    }


async def test_at12_the_command_prints_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`fantadamus calibrate` prints the stored report, scores a round that hasn't been, and recomputes with
    `--again`."""
    finished = fco_round_page(
        FcoMatch("Alfa", "Beta", confirmed=True),
        FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", confirmed=True),
    )
    async with a_round(tmp_path) as here:
        await here.ask()
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, finished.encode())
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now = AFTER
        monkeypatch.setattr(cli, "_calibrator", lambda _: here.calibrator)
        lake = ["--lake", str(tmp_path / "lake")]

        assert cli.main(["calibrate", "--round", "12", *lake]) == 1
        assert "Round 12 hasn't finished" in capsys.readouterr().out

        here.clock.now = AFTER - dt.timedelta(minutes=1)
        assert cli.main(["calibrate", "--round", "10", *lake]) == 1
        assert "Round 10 hasn't finished" in capsys.readouterr().out
        assert _reads(here) == 0
        here.clock.now = AFTER

        assert cli.main(["calibrate", "--round", "10", *lake]) == 0
        printed = capsys.readouterr().out
        assert "Round 10" in printed
        assert "The model on everyone" in printed
        assert _reads(here) == 1
        scored = here.scores.get(10)
        assert scored is not None
        # It read the statistics page itself: no question had, since the round.
        assert _chance(scored.model.scored, "Getting a rating").count == 56

        assert cli.main(["calibrate", "--round", "10", *lake]) == 0
        assert capsys.readouterr().out == printed
        assert _reads(here) == 1  # stored, so nothing is read

        here.clock.now += dt.timedelta(minutes=16)
        assert cli.main(["calibrate", "--round", "10", "--again", *lake]) == 0
        assert _reads(here) == 2


async def test_at12_the_schedule_scores_it_too(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`collect --due` does what a question would, with nobody asking, and only once."""
    async with a_round(tmp_path) as here:
        await here.ask()
        here.routes[f"{here.base}{ROUND_10}"] = Response(
            200,
            HTML,
            fco_round_page(
                FcoMatch("Alfa", "Beta", confirmed=True),
                FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", confirmed=True),
            ).encode(),
        )
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now = AFTER
        monkeypatch.setattr(cli, "_calibrator", lambda _: here.calibrator)
        monkeypatch.setattr(cli, "_collector", lambda *_: here.calibrator.collector)
        command = ["collect", "--due", "--lake", str(tmp_path / "lake")]

        assert cli.main(command) == 0
        assert "Round 10 scored." in capsys.readouterr().out
        assert here.scores.get(10) is not None
        assert cli.main(command) == 0
        assert "scored" not in capsys.readouterr().out


async def test_at12_overrides_counted_at_their_stated_cost(tmp_path: Path) -> None:
    """How many this round, and what each said it cost. Whether they paid off comes with the review."""
    async with a_round(tmp_path) as here:
        advised = (await here.ask())["lineup"]
        dropped = max(advised["starters"], key=lambda player: player["value"])["name"]
        chosen = (await here.ask(leave_out=[dropped]))["lineup"]
        cost = chosen["override"]["cost"]
        assert cost > 0
        [*_, logged] = here.log.read()
        here.log.append(logged.model_copy(update={"round": 9}))  # another round's doesn't count

        here.routes[f"{here.base}{ROUND_10}"] = Response(
            200,
            HTML,
            fco_round_page(
                FcoMatch("Alfa", "Beta", confirmed=True),
                FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", confirmed=True),
            ).encode(),
        )
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now = AFTER
        await here.ask()
        report = here.scores.get(10)
    assert report is not None
    assert report.overrides == 1
    assert report.override_cost == pytest.approx(cost, abs=0.01)


async def test_at12_a_name_written_two_ways_counts_once(tmp_path: Path) -> None:
    """The page before kickoff and the finished one can write him differently: he's still one player."""
    finished = fco_round_page(
        FcoMatch("Alfa", "Beta", confirmed=True),
        FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", confirmed=True),
    )
    assert fco_name("Alfa Nove") in finished
    finished = finished.replace(fco_name("Alfa Nove"), "Nove A.")
    async with a_round(tmp_path) as here:
        await here.ask()
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, finished.encode())
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now = AFTER
        await here.ask()
        report = here.scores.get(10)
    assert report is not None
    assert _chance(report.model.scored, "Starting").count == 56


async def test_at12_a_name_nobody_knows_is_named_as_unscored(tmp_path: Path) -> None:
    """A player the page lists and the statistics page doesn't: he's counted among what couldn't be scored,
    never dropped in silence (R7.3)."""
    finished = fco_round_page(
        FcoMatch("Alfa", "Beta", confirmed=True),
        FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", confirmed=True),
    ).replace(fco_name("Alfa Dodici"), fco_name("Nessuno Sconosciuto"))
    async with a_round(tmp_path) as here:
        await here.ask()
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, finished.encode())
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now = AFTER
        await here.ask()
        report = here.scores.get(10)
    assert report is not None
    assert {entry.reason: entry.count for entry in report.model.unscored}[
        "Everything: on the round's page but not on the statistics page"
    ] == 1


def _reads(here: Round) -> int:
    return [url for url, _, _ in here.web.calls].count(f"{here.base}{ROUND_10}")
