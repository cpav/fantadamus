"""mvp-store task 1.1: the real lake's answers are kept where git ignores them, and a run prints times and
counts only (design C7; R3.5, R4.2)."""

from __future__ import annotations

from tests import real_lake
from tests.real_lake import Question, Result, asked_once, report_lines

ANSWER = '{"player": "Mario Rossi", "p_start": 0.87}'
RESULTS = [
    Result(0, "compare_players", "ok", len(ANSWER), 0.4321, ANSWER),
    Result(1, "best_lineup", "refused", 12_345, 1.5, ANSWER),
]


def test_the_answers_are_kept_where_git_ignores_them() -> None:
    ignored = (real_lake.ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "data/private/" in ignored
    for kept in (real_lake.SNAPSHOT, real_lake.ANSWERS, real_lake.PLAN):
        assert kept.relative_to(real_lake.ROOT).parts[:3] == ("data", "private", "mvp-store")
    assert real_lake.LOCAL == real_lake.ROOT / "data" / "local"  # only ever copied from


def test_only_times_and_counts_are_printed() -> None:
    assert report_lines(RESULTS) == [
        "00 compare_players ok: 42 bytes, 0.43 s",
        "01 best_lineup refused: 12,345 bytes, 1.50 s",
        "2 answers, 1.9 CPU-seconds",
    ]
    compared = report_lines(RESULTS, same=[True, False])
    assert compared == [
        "00 compare_players ok: 42 bytes, 0.43 s, identical",
        "01 best_lineup refused: 12,345 bytes, 1.50 s, DIFFERENT",
        "2 answers, 1.9 CPU-seconds",
        "1 identical, 1 different",
    ]
    assert not any("Rossi" in line or "0.87" in line for line in compared)


def test_a_question_is_asked_once() -> None:
    at = "2026-11-08T11:00:00+00:00"
    lineup = Question("best_lineup", at, {})
    outlook = Question("player_outlook", at, {"player": "Rossi"})
    assert asked_once([outlook, lineup, Question("player_outlook", at, {"player": "Rossi"}), lineup]) == [
        outlook,
        lineup,
    ]
