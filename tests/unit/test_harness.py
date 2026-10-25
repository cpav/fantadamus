"""Task 5: the test harness: layer markers, network blocking and Hypothesis profiles (R7)."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest
from hypothesis import settings
from pytest_socket import SocketBlockedError
from scripts.checks import thresholds

from tests import hypothesis_profiles
from tests.conftest import LAYERS, layer_of


def test_markers_applied_by_directory(request: pytest.FixtureRequest) -> None:
    assert request.node.get_closest_marker("unit") is not None
    assert layer_of("tests/integration/test_x.py") == "integration"
    assert layer_of("tests/property/sub/test_y.py") == "property"
    assert layer_of("tests/test_root.py") is None
    assert set(LAYERS) == {"unit", "property", "contract", "integration", "acceptance", "infra"}


def test_network_blocked_in_unit_tests() -> None:
    with (
        pytest.warns(UserWarning, match="A test tried to use socket"),
        pytest.raises(SocketBlockedError),
    ):
        socket.create_connection(("127.0.0.1", 9), timeout=1)


def test_profile_selection() -> None:
    expected_ci = thresholds.load_current()["hypothesis_ci_examples"]["value"]
    assert settings.get_profile("ci").max_examples == expected_ci
    assert settings.get_profile("dev").max_examples == hypothesis_profiles.DEV_EXAMPLES
    active = os.environ.get("HYPOTHESIS_PROFILE", "dev")
    assert settings().max_examples == settings.get_profile(active).max_examples


def test_failure_prints_reproduction(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2]))
    pytester.makeconftest("from tests.hypothesis_profiles import load\nload('ci')\n")
    pytester.makepyfile(
        "from hypothesis import given, strategies as st\n"
        "@given(st.integers())\n"
        "def test_fails(n: int) -> None:\n"
        "    assert n < 10\n"
    )
    result = pytester.runpytest_subprocess("-p", "no:cacheprovider")
    result.assert_outcomes(failed=1)
    output = result.stdout.str()
    assert "Failing test case" in output or "Falsifying example" in output
    assert "n=10" in output, "the shrunk example is reported"
    assert "@reproduce_failure" in output, "the reproduction blob is reported"
