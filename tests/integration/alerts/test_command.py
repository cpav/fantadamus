"""mvp-alerts task 3.2: `fantadamus collect --due --user` checks for alerts after a run, and an error in the
check never fails the run; `fantadamus alerts` prints the log and `--test` sends a sample (design C7; R1.1,
R3.4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fantadamus.cli import __main__ as cli
from fantadamus.cli.notify import CONFIG_VAR
from fantadamus.domains.alerts import Change
from fantadamus.lake.alert_log import AlertLine, AlertLog
from fantadamus.mcp.alerts import Checked
from fantadamus.web.collector import CollectReport, PageReport
from tests.alerts_data import AT, LATER, a_call

RUN = CollectReport(
    started_at=AT,
    finished_at=AT,
    round=None,
    due=["official_lineups"],
    pages=[PageReport(url="https://example.org/round", outcome="stored", stored={"official_lineups": 22})],
)


@pytest.fixture
def scheduled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    """A scheduled run that stored an official lineup, no private configuration, and the check recorded."""
    seen: dict[str, Any] = {}
    monkeypatch.setattr(cli, "collect_due", lambda collector, log: RUN)
    monkeypatch.setenv(CONFIG_VAR, str(tmp_path / "private.toml"))

    def check(
        advisor: Any, alerts: AlertLog, report: CollectReport, notify: Any, *, enabled: bool
    ) -> Checked:
        seen.update(user=advisor.user, report=report, enabled=enabled, alerts=alerts.root)
        return Checked("sent", "Alert sent: Start Costa instead of Bianchi.")

    monkeypatch.setattr(cli, "check_alerts", check)
    return seen


def _collect(tmp_path: Path) -> int:
    return cli.main(["collect", "--due", "--lake", str(tmp_path / "local" / "lake"), "--user", "user-1"])


def test_the_check_runs_after_a_run_that_stored(
    scheduled: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _collect(tmp_path) == 0
    assert scheduled == {
        "user": "user-1",
        "report": RUN,
        "enabled": True,
        "alerts": tmp_path / "local" / "alerts",
    }
    out = capsys.readouterr().out
    assert out.index("Due: official_lineups") < out.index(
        "Alerts: Alert sent: Start Costa instead of Bianchi."
    )


def test_the_switch_reaches_the_check(
    scheduled: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "private.toml").write_text("[alerts]\nenabled = false\n", encoding="utf-8")
    assert _collect(tmp_path) == 0
    assert scheduled["enabled"] is False
    assert "Alerts are switched off in the private configuration." in capsys.readouterr().out


def test_an_error_in_the_check_isnt_the_runs(
    scheduled: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def broken(*_: Any, **__: Any) -> Checked:
        raise RuntimeError("the lake is locked")

    monkeypatch.setattr(cli, "check_alerts", broken)
    assert _collect(tmp_path) == 0
    assert "Alerts: the check failed (RuntimeError: the lake is locked)" in capsys.readouterr().out


def test_nothing_due_checks_nothing(
    scheduled: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cli, "collect_due", lambda collector, log: None)
    assert _collect(tmp_path) == 0
    assert scheduled == {}


def test_the_log_printed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log = AlertLog(tmp_path / "local" / "alerts")
    kept = {"logged_at": AT, "user": "user-1", "team": "mine", "round": 12, "call": a_call()}
    log.append(
        AlertLine.model_validate({"kind": "baseline", "reason": "no lineup was told this round"} | kept)
    )
    sent = {
        "kind": "alert",
        "logged_at": LATER,
        "changes": [Change("swap", now=11, before=2, role="D")],
        "subtitle": "Official lineup out",
        "text": "Start Costa instead of Bianchi.",
        "delivered": False,
        "reason": "osascript took more than 5 seconds",
    }
    log.append(AlertLine.model_validate(kept | sent))
    assert cli.main(["alerts", "--lake", str(tmp_path / "local" / "lake")]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "2026-11-21 08:00 UTC, round 12: call kept to compare with (no lineup was told this round)",
        "2026-11-21 11:00 UTC, round 12: Official lineup out. Start Costa instead of Bianchi. "
        "(not shown: osascript took more than 5 seconds)",
    ]
    assert cli.main(["alerts", "--lake", str(tmp_path / "elsewhere" / "lake")]) == 0
    assert "No alert yet" in capsys.readouterr().out


def test_a_sample_sent(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    sent: list[tuple[str, str, str]] = []

    def shown(title: str, subtitle: str, text: str) -> str | None:
        sent.append((title, subtitle, text))
        return None

    monkeypatch.setattr(cli, "notify", shown)
    assert cli.main(["alerts", "--test"]) == 0
    assert sent == [
        ("Fantadamus", "Alerts are on", "A change of your lineup's call will reach you like this.")
    ]
    assert "Sent" in capsys.readouterr().out
    monkeypatch.setattr(cli, "notify", lambda *_: "osascript isn't on this computer: alerts need a Mac")
    assert cli.main(["alerts", "--test"]) == 1
    assert "Not shown: osascript isn't on this computer: alerts need a Mac" in capsys.readouterr().out
