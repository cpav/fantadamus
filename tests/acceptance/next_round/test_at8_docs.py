"""mvp-next-round AT-8: no new dependency, and the docs say the round page is read daily (R3.2, R3.3)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SLICE = ["src/fantadamus/web/cadence.py", "tests/next_round_harness.py"]
"""The modules this slice changed or added."""


def _text(*parts: str) -> str:
    """The file's text, its lines joined wherever they break."""
    return " ".join(ROOT.joinpath(*parts).read_text(encoding="utf-8").split())


def _imports(module: Path) -> set[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    found = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    found |= {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0
    }
    return {name.split(".")[0] for name in found}


def test_at8_no_new_dependency() -> None:
    allowed = set(sys.stdlib_module_names) | {"fantadamus", "tests"}
    for module in SLICE:
        assert _imports(ROOT / module) <= allowed, module


def test_at8_the_docs_say_daily() -> None:
    cadence = _text("src", "fantadamus", "web", "cadence.py")
    assert "| Fixtures | Daily: the round page" in cadence
    collect = _text(".kiro", "specs", "mvp-collect", "requirements.md")
    assert "| Fixtures | Daily |" in collect
    assert "| Fixtures | Weekly |" not in collect
    assert "Amended by `mvp-next-round` R1.1" in collect
    guide = _text("docs", "player-setup.md").split("## 8.", 1)[1].split("## ", 1)[0]
    assert "at least once a day, so that it finds the next round as soon as the site shows it" in guide
