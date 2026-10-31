"""The submit tools' allowlist (`config/sources.toml`) matches the source registry (Spec 0 task 8.4, R16.11),
and the reading list (`config/reading_list.toml`) stays on it (mvp-x-or-y task 1.3, R11.1)."""

from __future__ import annotations

import re
import string
import tomllib
from pathlib import Path
from typing import Any

import pytest

from fantadamus.core.urls import host_allowed
from fantadamus.mcp.server import load_allowed_hosts

ROOT = Path(__file__).resolve().parents[2]
SUBMIT_TOOLS = {
    "submit_fixtures",
    "submit_probable_lineups",
    "submit_official_lineup",
    "submit_match_odds",
    "submit_player_season",
    "submit_team_season",
    "submit_penalty_takers",
}
PLACEHOLDERS = {"home", "away", "club", "player"}


def _reading_list() -> dict[str, dict[str, Any]]:
    facts: dict[str, dict[str, Any]] = tomllib.loads(
        (ROOT / "config" / "reading_list.toml").read_text(encoding="utf-8")
    )["facts"]
    return facts


def test_allowlist_is_the_registry_reading_list() -> None:
    registry = (ROOT / "docs" / "source-registry.md").read_text(encoding="utf-8")
    row = next(
        line for line in registry.splitlines() if line.startswith("| `fantacalcio.it` (terms risk accepted)")
    )
    allowed_cell = row.split("|")[1]
    assert set(load_allowed_hosts(ROOT / "config" / "sources.toml")) == set(
        re.findall(r"`([^`]+)`", allowed_cell)
    )


@pytest.mark.parametrize(
    "content",
    [
        "allowed_hosts = []",
        'allowed_hosts = ["https://example.org"]',
        'allowed_hosts = ["Example.org"]',
        "x = 1",
    ],
)
def test_malformed_allowlist_fails(tmp_path: Path, content: str) -> None:
    path = tmp_path / "sources.toml"
    path.write_text(content + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="allowed_hosts"):
        load_allowed_hosts(path)


def test_reading_list_pages_are_allowed() -> None:
    hosts = load_allowed_hosts(ROOT / "config" / "sources.toml")
    for fact, entry in _reading_list().items():
        pages: list[str] = entry.get("pages", [])
        searches: list[str] = entry.get("search", [])
        assert pages or searches, fact
        for page in pages + entry.get("patterns", []):
            assert host_allowed(page, hosts), (fact, page)
        for search in searches:
            sites = re.findall(r"site:([^/\s]+)", search)
            assert sites, (fact, search)
            assert all(host_allowed(f"https://{site}/", hosts) for site in sites), (fact, search)
        for text in pages + searches:
            fields = {field for _, field, _, _ in string.Formatter().parse(text) if field is not None}
            assert fields <= PLACEHOLDERS, (fact, text)


def test_reading_list_covers_each_submit_tool() -> None:
    tools = [entry["submit_tool"] for entry in _reading_list().values()]
    assert sorted(tools) == sorted(SUBMIT_TOOLS)


def test_reading_list_has_fallbacks() -> None:
    """mvp-x-or-y task 10.1 (R11.4): no fact rests on one page, and Wikipedia never comes first."""
    for fact, entry in _reading_list().items():
        pages: list[str] = entry.get("pages", [])
        searches: list[str] = entry.get("search", [])
        assert len(pages) + len(searches) >= 2, fact
        assert searches, fact
        assert not (pages and "wikipedia.org" in pages[0]), fact
