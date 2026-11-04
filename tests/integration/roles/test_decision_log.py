"""mvp-roles task 5.4: a keeper's chances in the decision log, and answers without a verdict; earlier lines
still read (design C11; R5.3, R6.3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from fantadamus.lake.decision_log import Decision, DecisionLog, LoggedPlayer
from fantadamus.league.rules import CLASSIC, StoredRules

AT = dt.datetime(2026, 11, 3, 8, 0, tzinfo=dt.UTC)
RULES = StoredRules(user="user-1", saved_at=AT, rules=CLASSIC)


def test_keeper_probabilities_logged(tmp_path: Path) -> None:
    log = DecisionLog(tmp_path)
    keeper = LoggedPlayer(
        player_id=1,
        name="Uno",
        p_start=0.9,
        p_cameo=0.0,
        p_scores=None,
        key=5.4,
        p_clean_sheet=0.33,
        expected_conceded=1.1,
    )
    log.append(
        Decision(
            kind="outlook",
            as_of=AT,
            logged_at=AT,
            user="user-1",
            round=11,
            players=[keeper],
            rules=RULES,
            content_hashes=[],
        )
    )
    [read] = log.read()
    assert (read.kind, read.first, read.margin, read.label) == ("outlook", None, None, None)
    assert (read.players[0].p_clean_sheet, read.players[0].expected_conceded) == (0.33, 1.1)


def test_earlier_lines_read(tmp_path: Path) -> None:
    rules = RULES.model_dump_json()
    (tmp_path / "2026-10.jsonl").write_text(
        '{"as_of": "2026-10-30T10:00:00Z", "logged_at": "2026-10-30T10:00:00Z", "user": "user-1", '
        '"round": 10, "players": [{"player_id": 1, "name": "Nove", "p_start": 0.9, "p_cameo": 0.05, '
        '"p_scores": 0.3, "key": 7.1}], '
        f'"first": "Nove", "second": "Sette", "margin": 0.4, "label": "lean", "rules": {rules}, '
        '"content_hashes": []}\n',
        encoding="utf-8",
    )
    [earlier] = DecisionLog(tmp_path).read()
    assert (earlier.kind, earlier.first, earlier.label) == ("compare", "Nove", "lean")
    assert (earlier.players[0].p_scores, earlier.players[0].p_clean_sheet) == (0.3, None)
