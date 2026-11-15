"""mvp-alerts task 2.1: the alert log, append-only under `data/local/alerts/` (design C5; R3.2, R4.2)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from fantadamus.domains.alerts import Change
from fantadamus.lake.alert_log import DEFAULT_ROOT, AlertLine, AlertLog
from tests.alerts_data import AT, a_call


def _line(when: dt.datetime, kind: str = "alert") -> AlertLine:
    return AlertLine.model_validate(
        {
            "kind": kind,
            "logged_at": when,
            "user": "user-1",
            "team": "mine",
            "round": 12,
            "call": a_call(captain=None),
            "changes": [Change("swap", now=11, before=2, role="D")],
            "title": "Fantadamus · Round 12",
            "subtitle": "Official lineup out",
            "text": "Start Costa instead of Bianchi.",
            "delivered": False,
            "reason": "not a Mac",
        }
    )


def test_lines_are_appended_and_read_back(tmp_path: Path) -> None:
    log = AlertLog(tmp_path)
    first, second = _line(AT), _line(AT + dt.timedelta(hours=1), kind="baseline")
    log.append(first)
    log.append(second)
    assert log.read() == [first, second]
    assert log.read()[0].call == a_call(captain=None)


def test_a_month_per_file(tmp_path: Path) -> None:
    log = AlertLog(tmp_path)
    log.append(_line(AT))
    log.append(_line(AT + dt.timedelta(days=15)))
    assert sorted(path.name for path in tmp_path.iterdir()) == ["2026-11.jsonl", "2026-12.jsonl"]


def test_it_lives_under_the_git_ignored_folder() -> None:
    assert Path("data/local/alerts") == DEFAULT_ROOT
