"""Shared pytest setup: layer markers, network blocking, Hypothesis profiles (R7.1 to R7.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import hypothesis_profiles

pytest_plugins = ["pytester"]

hypothesis_profiles.load()

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ("unit", "property", "contract", "integration", "acceptance", "infra")
NO_NETWORK = frozenset({"unit", "property"})


def layer_of(path: str | Path) -> str | None:
    """The layer a test file belongs to: the directory directly under tests/, if it is a layer."""
    parts = Path(path).parts
    if "tests" not in parts:
        return None
    index = parts.index("tests")
    if len(parts) > index + 2 and parts[index + 1] in LAYERS:
        return parts[index + 1]
    return None


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test with its layer, so `pytest -m <layer>` selects it, and block sockets where required."""
    for item in items:
        layer = layer_of(item.path.relative_to(ROOT))
        if layer is None:
            continue
        item.add_marker(getattr(pytest.mark, layer))
        if layer in NO_NETWORK:
            item.add_marker(pytest.mark.disable_socket)


@pytest.fixture
def repo_root() -> Path:
    """The repository root."""
    return ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    """Recorded payloads, synthetic data and CSVs shared by tests."""
    return ROOT / "tests" / "fixtures"
