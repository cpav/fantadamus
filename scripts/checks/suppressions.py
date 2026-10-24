"""Each suppression names its rule, gives a reason and has an approved register row.

Requirements: R6.1 to R6.4, R6.6, R6.7.

Suppressions found:
- Python comments (read with `tokenize`, so text inside strings never counts): `# noqa: CODE` and
  `# type: ignore[code]`. The reason is `# reason: …` after the codes, or a `# reason: …` line above.
- pytest skips (read from the syntax tree): `pytest.mark.skip`, `skipif`, `xfail`, `pytest.skip`,
  `pytest.xfail`. The reason is their `reason=` argument, or a first positional string.
- Terraform comments: `#checkov:skip=CKV_…:reason` and `# tflint-ignore: rule` with a `# reason: …`.
- Configuration: ruff's `per-file-ignores` in pyproject.toml; their reason is the register row.
- File allowlists: `.gitleaks.toml` entries need a `description`; `config/audit-allowlist.toml`
  entries need a `reason`.

Each one needs a row in docs/quality/suppressions.md with the same path and rule and an approval date,
and every row must still match a suppression.
"""

from __future__ import annotations

import ast
import io
import re
import subprocess
import tokenize
import tomllib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.checks._common import CheckResult, report

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "docs" / "quality" / "suppressions.md"

_NOQA = re.compile(r"^noqa\b(?::\s*(?P<codes>[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*))?")
_TYPE_IGNORE = re.compile(r"^type:\s*ignore\b(?:\[(?P<codes>[a-z0-9-]+(?:\s*,\s*[a-z0-9-]+)*)\])?")
_REASON = re.compile(r"^reason:\s*(?P<text>\S.*)$")
_CHECKOV = re.compile(r"#\s*checkov:skip=(?P<code>CKV2?_[A-Z0-9]+_\d+)(?::(?P<reason>.*\S))?")
_TFLINT = re.compile(r"#\s*tflint-ignore:\s*(?P<codes>[a-z0-9_]+(?:\s*,\s*[a-z0-9_]+)*)")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SKIPS = {("mark", "skip"), ("mark", "skipif"), ("mark", "xfail"), ("pytest", "skip"), ("pytest", "xfail")}


@dataclass(frozen=True)
class Suppression:
    """One suppression: where it is, which rule it silences (None if unnamed), and its reason."""

    path: str
    line: int
    rule: str | None
    reason: str | None


@dataclass(frozen=True)
class RegisterRow:
    """One row of the suppression register."""

    id: str
    path: str
    rule: str
    approved: str


def _segments(comment: str) -> list[str]:
    return [part.strip() for part in comment.split("#") if part.strip()]


def _reason_in(segments: Sequence[str]) -> str | None:
    for segment in segments:
        match = _REASON.match(segment)
        if match:
            return match.group("text").strip()
    return None


def find_in_python(path: str, source: str) -> list[Suppression]:
    """Find `noqa`, `type: ignore` and pytest skips in Python source."""
    found: list[Suppression] = []
    comments: dict[int, str] = {}
    code_lines: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            comments[token.start[0]] = token.string
        elif token.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
            code_lines.add(token.start[0])
    for line, comment in sorted(comments.items()):
        segments = _segments(comment)
        reason = _reason_in(segments)
        above = comments.get(line - 1)
        if reason is None and above is not None and (line - 1) not in code_lines:
            reason = _reason_in(_segments(above))
        for segment in segments:
            for pattern in (_NOQA, _TYPE_IGNORE):
                match = pattern.match(segment)
                if match is None:
                    continue
                codes = match.group("codes")
                rules: list[str | None] = [c.strip() for c in codes.split(",")] if codes else [None]
                found.extend(Suppression(path, line, rule, reason) for rule in rules)
    found.extend(_find_skips(path, source))
    return found


def _find_skips(path: str, source: str) -> list[Suppression]:
    found: list[Suppression] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call | ast.Attribute):
            continue
        target = node.func if isinstance(node, ast.Call) else node
        if not isinstance(target, ast.Attribute) or not isinstance(target.value, ast.Name | ast.Attribute):
            continue
        owner = target.value.attr if isinstance(target.value, ast.Attribute) else target.value.id
        if (owner, target.attr) not in _SKIPS:
            continue
        reason: str | None = None
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "reason" and isinstance(keyword.value, ast.Constant):
                    reason = str(keyword.value.value)
            first = node.args[0] if node.args else None
            if reason is None and isinstance(first, ast.Constant) and isinstance(first.value, str):
                reason = first.value
        rule = "xfail" if "xfail" in target.attr else "skip"
        found.append(Suppression(path, node.lineno, rule, reason or None))
    return _dedupe_calls(found)


def _dedupe_calls(found: list[Suppression]) -> list[Suppression]:
    """A decorator call yields both the Call and its Attribute; keep the one with a reason if any."""
    best: dict[tuple[str, int, str | None], Suppression] = {}
    for item in found:
        key = (item.path, item.line, item.rule)
        if key not in best or (best[key].reason is None and item.reason is not None):
            best[key] = item
    return list(best.values())


def find_in_terraform(path: str, source: str) -> list[Suppression]:
    """Find checkov and tflint skips in Terraform source."""
    found: list[Suppression] = []
    lines = source.splitlines()
    for number, text in enumerate(lines, start=1):
        for match in _CHECKOV.finditer(text):
            found.append(Suppression(path, number, match.group("code"), match.group("reason")))
        tflint = _TFLINT.search(text)
        if tflint:
            reason = _reason_in(_segments(text.split("tflint-ignore", 1)[1]))
            if reason is None and number > 1:
                reason = _reason_in(_segments(lines[number - 2]))
            codes = [c.strip() for c in tflint.group("codes").split(",")]
            found.extend(Suppression(path, number, code, reason) for code in codes)
    return found


def find_per_file_ignores(pyproject: str) -> list[Suppression]:
    """Each ruff per-file-ignores entry is a suppression whose reason lives in the register."""
    data = tomllib.loads(pyproject)
    ignores = data.get("tool", {}).get("ruff", {}).get("lint", {}).get("per-file-ignores", {})
    return [Suppression(glob, 0, code, "see register") for glob, codes in ignores.items() for code in codes]


def find_in_allowlists(path: str, text: str) -> list[Suppression]:
    """gitleaks entries need a description; dependency-audit entries need a reason."""
    data = tomllib.loads(text)
    if path.endswith(".gitleaks.toml"):
        return [
            Suppression(
                path,
                0,
                str(entry.get("id") or entry.get("description") or "allowlist"),
                entry.get("description"),
            )
            for entry in data.get("allowlists", [])
        ]
    return [
        Suppression(path, 0, str(entry.get("id")), entry.get("reason")) for entry in data.get("ignore", [])
    ]


def parse_register(text: str) -> list[RegisterRow]:
    """Read the register's table rows: ID, `path`, tool `rule`, reason, approval date."""
    rows: list[RegisterRow] = []
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5 or not re.match(r"^S-\d+$", cells[0]):
            continue
        path = re.search(r"`([^`]+)`", cells[1])
        rule = re.search(r"`([^`]+)`", cells[2])
        rows.append(
            RegisterRow(
                id=cells[0],
                path=path.group(1) if path else cells[1],
                rule=rule.group(1) if rule else cells[2],
                approved=cells[4],
            )
        )
    return rows


def problems(found: Iterable[Suppression], rows: Sequence[RegisterRow]) -> list[str]:
    """Everything wrong with these suppressions against this register."""
    found = list(found)
    issues: list[str] = []
    by_key = {(row.path, row.rule): row for row in rows}
    for item in found:
        where = f"{item.path}:{item.line}" if item.line else item.path
        if item.rule is None:
            issues.append(f"{where}: suppression names no rule (R6.1)")
            continue
        if not item.reason:
            issues.append(f"{where}: suppression of {item.rule} gives no reason (R6.2)")
        row = by_key.get((item.path, item.rule))
        if row is None:
            issues.append(f"{where}: {item.rule} has no register row in docs/quality/suppressions.md (R6.3)")
        elif not _DATE.match(row.approved):
            issues.append(f"{row.id} ({item.rule} in {item.path}) has no approval date from the owner (R6.7)")
    used = {(item.path, item.rule) for item in found}
    issues.extend(
        f"{row.id} ({row.rule} in {row.path}) matches no suppression; remove the row (R6.4)"
        for row in rows
        if (row.path, row.rule) not in used
    )
    return sorted(set(issues))


def _tracked_files(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],  # noqa: S607  # reason: git from PATH, as in every developer shell and CI runner
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.splitlines()


def check(root: Path = ROOT) -> CheckResult:
    found: list[Suppression] = []
    for name in _tracked_files(root):
        path = root / name
        if not path.is_file():
            continue
        if name.endswith(".py"):
            found.extend(find_in_python(name, path.read_text(encoding="utf-8")))
        elif name.endswith((".tf", ".tftest.hcl")):
            found.extend(find_in_terraform(name, path.read_text(encoding="utf-8")))
        elif name == "pyproject.toml":
            found.extend(find_per_file_ignores(path.read_text(encoding="utf-8")))
        elif name in (".gitleaks.toml", "config/audit-allowlist.toml"):
            found.extend(find_in_allowlists(name, path.read_text(encoding="utf-8")))
    issues = problems(found, parse_register(REGISTER.read_text(encoding="utf-8")))
    if issues:
        return CheckResult("suppressions", ok=False, message="; ".join(issues))
    return CheckResult("suppressions", ok=True)


if __name__ == "__main__":
    raise SystemExit(report(check()))
