"""Task 8.4: the submit tools' allowlist (`config/sources.toml`) matches the source registry (R16.11)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fantadamus.mcp.server import load_allowed_hosts

ROOT = Path(__file__).resolve().parents[2]


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
