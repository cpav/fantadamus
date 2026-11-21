"""mvp-fixes task 3.1: a player's sources are every page whose facts his answer shows, the injured or
suspended page and the other competitions' pages included (design C6; R3.1, R3.2)."""

from __future__ import annotations

from tests.fixes_facts import facts, page_names, rested


def test_news_and_rest_days_are_sources() -> None:
    assert page_names(facts(news=True).sources(rested())) == {
        "statistics",
        "table",
        "takers",
        "round",
        "outlet-0",
        "outlet-1",
        "odds",
        "injuries",
        "cup",
    }


def test_without_news_or_rest_days_neither_is_a_source() -> None:
    assert page_names(facts().sources()) == {
        "statistics",
        "table",
        "takers",
        "round",
        "outlet-0",
        "outlet-1",
        "odds",
    }


def test_no_match_no_match_sources() -> None:
    assert page_names(facts(match=False, outlets=0, odds=False).sources()) == {
        "statistics",
        "table",
        "takers",
    }
