"""mvp-fixes task 2.1: the `collect` tool takes the collector's own list of facts and names every page it can
read (design C5; R2.1, R2.2)."""

from __future__ import annotations

from typing import get_args

from fantadamus.mcp.tools.collect import DESCRIPTION
from fantadamus.web.collector import FACTS, PAGE_FACTS, PAGE_NAMES, CollectFact


def test_the_literal_is_the_collectors_list() -> None:
    """Adding a fact to the collector and not to the tool, or the other way round, fails here."""
    assert get_args(CollectFact) == FACTS


def test_every_page_with_a_fact_has_a_name() -> None:
    """A finished round's page is read only to score the round, never through the tool."""
    assert set(PAGE_NAMES) == set(PAGE_FACTS) - {"finished_round"}
    for kind, name in PAGE_NAMES.items():
        assert name in DESCRIPTION, kind
