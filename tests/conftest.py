"""Shared pytest setup: layer markers, network blocking, Hypothesis profiles (R7.1 to R7.5)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from scripts.checks._common import run_command

from tests import hypothesis_profiles

pytest_plugins = ["pytester"]

hypothesis_profiles.load()

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ("unit", "property", "contract", "integration", "acceptance")
NO_NETWORK = frozenset({"unit", "property"})

Git = Callable[..., str]


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


@pytest.fixture
def git_repo(tmp_path: Path) -> tuple[Path, Git]:
    """An empty git repository with a local identity, and a `git(*args)` helper that returns stdout."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> str:
        completed = run_command(["git", "-C", str(repo), *args])
        assert completed.returncode == 0, completed.stderr
        return completed.stdout

    git("init", "-q", "-b", "main")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.org")
    git("config", "commit.gpgsign", "false")
    return repo, git


@pytest.fixture(scope="module")
def start_values() -> Iterator[None]:
    """The values calibrated on 2026-11-12 back at their starting values (see docs/calibration-log.md), for a
    test module that works its numbers out by hand on those: the chance of starting as the outlets' plain
    mean, and 0.15 yellow cards per appearance. The calibrated values are checked through the tools in
    tests/acceptance/recalibrate/test_moves.py, and against the log in test_proposal.py."""
    from fantadamus.domains import recalibration
    from fantadamus.domains.availability import consensus
    from fantadamus.engine import outfield
    from fantadamus.engine.recalibrate import IDENTITY

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(consensus, "START_MAP", IDENTITY)
        patch.setattr(recalibration, "START_MAP", IDENTITY)
        patch.setattr(outfield, "YELLOW_PRIOR", 0.15)
        yield
