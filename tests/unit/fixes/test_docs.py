"""mvp-fixes task 6.1: the player guide says a page that couldn't be reached is tried again at the next run,
the README says `collect` takes any fact the collector reads, and format 7 has the app's line, with the review
and the overview ending on their sources (design C9; R6.3)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _text(*parts: str) -> str:
    """The file's text, its lines joined wherever they break."""
    return " ".join(ROOT.joinpath(*parts).read_text(encoding="utf-8").split())


def test_the_guide_says_a_failed_page_is_tried_again() -> None:
    schedule, trouble = _text("docs", "player-setup.md").split("## If something goes wrong", 1)
    assert "is tried again at the next run" in schedule
    assert "a closed lid costs only the time it was closed" in schedule
    assert "shows a page as failed" in trouble


def test_the_readme_says_collect_takes_any_fact() -> None:
    assert "`--fact` takes any of the facts the collector reads" in _text("README.md")


def test_format_7_says_how_often_the_app_matched() -> None:
    formats = _text("docs", "answer-formats.md")
    review = formats.split("## 7. The review", 1)[1].split("## 8.", 1)[0]
    assert "Your app's total matched in 3 of 4 rounds." in review
    assert "Sources:" in review
    overview = formats.split("### The round overview", 1)[1].split("## 6.", 1)[0]
    assert "Sources:" in overview
