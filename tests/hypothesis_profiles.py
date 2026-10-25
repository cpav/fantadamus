"""Hypothesis profiles (R7.3, R7.5).

`ci` is thorough and used by `make check`, locally and in CI; its example count is the gate threshold
`hypothesis_ci_examples` in config/thresholds.toml, so the ratchet protects it. `dev` is fast and used by
`make test-fast`. Both print the `@reproduce_failure` blob when a property fails.
"""

from __future__ import annotations

import os

from hypothesis import settings
from scripts.checks import thresholds

DEV_EXAMPLES = 50


def _ci_examples() -> int:
    value = thresholds.load_current()["hypothesis_ci_examples"]["value"]
    if not isinstance(value, int):
        raise TypeError(f"hypothesis_ci_examples must be an integer, got {value!r}")
    return value


def register() -> None:
    settings.register_profile("ci", max_examples=_ci_examples(), deadline=None, print_blob=True)
    # No per-example deadline in either profile: with tests running in parallel, wall-clock deadlines
    # fail at random. Slow tests are caught by the per-test timeout instead (pyproject.toml).
    settings.register_profile("dev", max_examples=DEV_EXAMPLES, deadline=None, print_blob=True)


def load(name: str | None = None) -> None:
    """Register both profiles and load `name`, else $HYPOTHESIS_PROFILE, else `dev`."""
    register()
    settings.load_profile(name or os.environ.get("HYPOTHESIS_PROFILE", "dev"))
