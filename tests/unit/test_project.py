"""Task 3.1: the Python project is pinned to 3.12 and importable from its src layout (R3.1, R3.2)."""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_python_pinned_312() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["requires-python"] == ">=3.12,<3.13"
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12"


def test_src_layout_importable() -> None:
    package = importlib.import_module("fantadamus")
    assert package.__file__ is not None
    assert Path(package.__file__).resolve().is_relative_to(ROOT / "src" / "fantadamus")
