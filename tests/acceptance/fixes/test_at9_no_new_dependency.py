"""mvp-fixes AT-9: no new dependency (R6.2). The docs are checked by `tests/unit/fixes/test_docs.py`
(R6.3)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SLICE = [
    "src/fantadamus/web/fetch.py",
    "src/fantadamus/web/collector.py",
    "src/fantadamus/web/cadence.py",
    "src/fantadamus/lake/collect_log.py",
    "src/fantadamus/cli/__main__.py",
    "src/fantadamus/mcp/advisor.py",
    "src/fantadamus/mcp/tools/collect.py",
    "src/fantadamus/mcp/tools/lineup.py",
    "src/fantadamus/mcp/tools/cards.py",
    "src/fantadamus/mcp/tools/review.py",
    "src/fantadamus/domains/review.py",
    "tests/fixes_facts.py",
    "tests/real_lake.py",
]
"""The modules this slice changed."""


def _imports(module: Path) -> set[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    found = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    found |= {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0
    }
    return {name.split(".")[0] for name in found}


def test_at9_no_new_dependency() -> None:
    """The standard library does all of it: what this slice's modules import is that, pydantic for the models,
    the MCP SDK the tools already used, and the project's own code."""
    allowed = set(sys.stdlib_module_names) | {"pydantic", "mcp", "fantadamus", "tests", "scripts"}
    for module in SLICE:
        assert _imports(ROOT / module) <= allowed, module
