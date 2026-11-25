"""AT-8: no new dependency, and the method and the constants say what each share means (mvp-cameos R4.1,
R4.2). That the method marks the approved value with its date is checked by
`tests/unit/test_repo_hygiene.py::test_method_marks_each_calibrated_value`."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from fantadamus.engine import constants

ROOT = Path(__file__).resolve().parents[3]
SLICE = [
    "src/fantadamus/domains/availability/consensus.py",
    "src/fantadamus/domains/availability/gold.py",
    "src/fantadamus/domains/recalibration.py",
    "src/fantadamus/engine/outfield.py",
    "src/fantadamus/engine/recalibrate.py",
    "src/fantadamus/mcp/advisor.py",
    "src/fantadamus/mcp/calibrate.py",
    "src/fantadamus/mcp/tools/lineup.py",
    "tests/cameos_rows.py",
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


def test_at8_no_new_dependency() -> None:
    allowed = set(sys.stdlib_module_names) | {"pydantic", "mcp", "fantadamus", "tests"}
    for module in SLICE:
        assert _imports(ROOT / module) <= allowed, module


def test_at8_the_method_has_both() -> None:
    """The method's cameo value (§A4) says what each share counts, and both values are the code's."""
    method = (ROOT / "docs" / "method.md").read_text(encoding="utf-8")
    cameo = " ".join(method.split("**Cameo value.**")[1].split("## A5.")[0].split())
    for part in (
        "is counted with a rating",
        f"{constants.CAMEO_SHARE:.3f} of the time he doesn't start",
        "`CAMEO_SHARE`",
        "is counted as coming on at all",
        f"{constants.CAMEO_SHARE_PRICED:.1f} *(start: `CAMEO_SHARE_PRICED`)*",
    ):
        assert part in cameo, part
    source = (ROOT / "src" / "fantadamus" / "engine" / "constants.py").read_text(encoding="utf-8")
    assert "How often a player who doesn't start comes on, by his kind of cameo" in source
