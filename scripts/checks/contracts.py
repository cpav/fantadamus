"""Fail when a data contract drifts from its committed schema or changes without the right version bump
(R13.1 to R13.3).

1. Every contract's schema document (name, version, JSON Schema) must equal its committed file under
   `src/fantadamus/contracts/schemas/`; `--write` regenerates them.
2. Against the base branch: a changed schema needs a higher version, and a breaking change (a property
   removed or renamed, newly required, a type, value set or bound narrowed) needs a higher major version.
3. Every contract's current version needs a `## <Contract> <version>` heading in the CHANGELOG.md next to
   its module.

The base is $FANTADAMUS_BASE_REF if set, else origin/main if it exists, else main.

Usage: python -m scripts.checks.contracts [--write]
"""

from __future__ import annotations

import argparse
import inspect
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from fantadamus.contracts.base import SCHEMA_DIR, SEMVER_PATTERN, all_contracts
from scripts.checks._common import CheckResult, report, run_command
from scripts.checks.thresholds import base_ref

ROOT = Path(__file__).resolve().parents[2]
NAME = "contracts"
MAX_DEPTH = 32

Doc = Mapping[str, Any]
Schema = Mapping[str, Any]
Version = tuple[int, int, int]
BaseLoader = Callable[[str], str | None]


def render(doc: Doc) -> str:
    """The committed form of a schema document: sorted keys, two-space indent, trailing newline."""
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def parse_version(text: object) -> Version | None:
    match = re.fullmatch(SEMVER_PATTERN.strip("^$"), text) if isinstance(text, str) else None
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


# --- Breaking-change classification -------------------------------------------------------------------
# `_narrowings(old, new)` lists the ways `new` rejects something `old` accepted. When it can't prove a change
# is safe it reports it, so an unusual change errs towards needing a major bump.


def _resolve(schema: object, root: Schema) -> Schema:
    if isinstance(schema, bool):
        return {} if schema else {"enum": []}
    node: Any = schema
    for _ in range(MAX_DEPTH):
        ref = node.get("$ref") if isinstance(node, Mapping) else None
        if not isinstance(ref, str) or not ref.startswith("#/"):
            break
        node = root
        for part in ref[2:].split("/"):
            node = node[part]
    return node if isinstance(node, Mapping) else {}


def _alternatives(schema: object, root: Schema) -> list[Schema]:
    resolved = _resolve(schema, root)
    for key in ("anyOf", "oneOf"):
        if key in resolved:
            return [alt for option in resolved[key] for alt in _alternatives(option, root)]
    return [resolved]


def _types(schema: Schema) -> set[str] | None:
    declared = schema.get("type")
    if declared is None:
        return None
    return {declared} if isinstance(declared, str) else set(declared)


def _values(schema: Schema) -> list[Any] | None:
    if "const" in schema:
        return [schema["const"]]
    enum = schema.get("enum")
    return list(enum) if enum is not None else None


def _bound(schema: Schema, inclusive: str, exclusive: str) -> tuple[float, bool] | None:
    """The tighter of an inclusive and an exclusive bound, as (value, is_exclusive)."""
    bounds = [(float(schema[key]), key == exclusive) for key in (inclusive, exclusive) if key in schema]
    if not bounds:
        return None
    lower = inclusive == "minimum"
    # For a lower bound, tighter means larger, or equal and exclusive; for an upper bound, smaller.
    return max(bounds) if lower else min(bounds, key=lambda bound: (bound[0], not bound[1]))


def _bound_narrowed(old: tuple[float, bool] | None, new: tuple[float, bool] | None, lower: bool) -> bool:
    if new is None:
        return False
    if old is None:
        return True
    if new[0] != old[0]:
        return new[0] > old[0] if lower else new[0] < old[0]
    return new[1] and not old[1]


def _compare(old: Schema, new: Schema, roots: tuple[Schema, Schema], path: str, depth: int) -> list[str]:
    reasons: list[str] = []
    old_types, new_types = _types(old), _types(new)
    if new_types is not None:
        accepted = new_types | ({"integer"} if "number" in new_types else set())
        lost = sorted((old_types or {"any"}) - accepted)
        if lost:
            reasons.append(f"{path}: type {', '.join(lost)} no longer accepted")
    old_values, new_values = _values(old), _values(new)
    if new_values is not None:
        dropped = [value for value in old_values or ["any value"] if value not in new_values]
        if dropped:
            reasons.append(f"{path}: {json.dumps(dropped, ensure_ascii=False)} no longer accepted")
    for key in ("minLength", "minItems", "minProperties"):
        if new.get(key, 0) > old.get(key, 0):
            reasons.append(f"{path}: {key} raised to {new[key]}")
    for key in ("maxLength", "maxItems", "maxProperties"):
        if new.get(key, math.inf) < old.get(key, math.inf):
            reasons.append(f"{path}: {key} lowered to {new[key]}")
    for inclusive, exclusive, lower in (
        ("minimum", "exclusiveMinimum", True),
        ("maximum", "exclusiveMaximum", False),
    ):
        if _bound_narrowed(_bound(old, inclusive, exclusive), _bound(new, inclusive, exclusive), lower):
            reasons.append(f"{path}: {'lower' if lower else 'upper'} bound tightened")
    for key in ("pattern", "format", "multipleOf"):
        if key in new and new[key] != old.get(key):
            reasons.append(f"{path}: {key} changed to {new[key]!r}")
    reasons.extend(_compare_object(old, new, roots, path, depth))
    if "items" in new:
        reasons.extend(_narrowings(old.get("items", {}), new["items"], roots, f"{path}[]", depth + 1))
    return reasons


def _compare_object(
    old: Schema, new: Schema, roots: tuple[Schema, Schema], path: str, depth: int
) -> list[str]:
    reasons: list[str] = []
    old_properties, new_properties = old.get("properties", {}), new.get("properties", {})
    for name, schema in old_properties.items():
        if name not in new_properties:
            reasons.append(f"{path}.{name}: removed")
        else:
            reasons.extend(_narrowings(schema, new_properties[name], roots, f"{path}.{name}", depth + 1))
    newly_required = sorted(set(new.get("required", [])) - set(old.get("required", [])))
    reasons.extend(f"{path}.{name}: newly required" for name in newly_required)
    if old.get("additionalProperties", True) is not False and new.get("additionalProperties", True) is False:
        reasons.append(f"{path}: additional properties no longer accepted")
    return reasons


def _narrowings(
    old: object, new: object, roots: tuple[Schema, Schema], path: str, depth: int = 0
) -> list[str]:
    if depth > MAX_DEPTH:
        return [f"{path}: too deeply nested to compare"]
    old_alternatives, new_alternatives = _alternatives(old, roots[0]), _alternatives(new, roots[1])
    if len(old_alternatives) == 1 and len(new_alternatives) == 1:
        return _compare(old_alternatives[0], new_alternatives[0], roots, path, depth)
    for option in old_alternatives:
        if all(_compare(option, candidate, roots, path, depth) for candidate in new_alternatives):
            return [f"{path}: a previously accepted alternative is no longer accepted"]
    return []


def breaking_changes(old: Schema, new: Schema) -> list[str]:
    """Every way the new schema rejects data the old one accepted."""
    return _narrowings(old, new, (old, new), "$")


# --- Version rules -------------------------------------------------------------------------------------


def _has_entry(changelog: str, contract: str, version: str) -> bool:
    heading = rf"^##\s+{re.escape(contract)}\s+{re.escape(version)}(?:\s|$)"
    return re.search(heading, changelog, flags=re.MULTILINE) is not None


def version_rules(base: Doc | None, current: Doc, changelog: str) -> list[str]:
    """The R13 issues for one contract, given its base document (None if new) and its changelog text."""
    name = str(current["contract"])
    short = name.rsplit(".", 1)[-1]
    version = parse_version(current.get("version"))
    if version is None:
        return [f"{name}: __version__ {current.get('version')!r} is not a semantic version"]
    issues: list[str] = []
    if not _has_entry(changelog, short, str(current["version"])):
        issues.append(f"{name}: no changelog heading '## {short} {current['version']}'")
    if base is None:
        return issues
    base_version = parse_version(base.get("version")) or (0, 0, 0)
    shown = f"{base.get('version')} → {current['version']}"
    if version < base_version:
        issues.append(f"{name}: version went backwards ({shown})")
    elif base["schema"] != current["schema"]:
        if version == base_version:
            issues.append(f"{name}: schema changed without a version bump (still {current['version']})")
        else:
            breaking = breaking_changes(base["schema"], current["schema"])
            if breaking and version[0] <= base_version[0]:
                issues.append(f"{name}: breaking change needs a major bump ({shown}): " + "; ".join(breaking))
    return issues


# --- I/O -----------------------------------------------------------------------------------------------


def _git_loader(ref: str, schema_dir: Path) -> BaseLoader:
    relative = schema_dir.relative_to(ROOT).as_posix()

    def load(filename: str) -> str | None:
        shown = run_command(["git", "-C", str(ROOT), "show", f"{ref}:{relative}/{filename}"])
        return shown.stdout if shown.returncode == 0 else None

    return load


def _changelog(contract: type) -> str:
    path = Path(inspect.getfile(contract)).parent / "CHANGELOG.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def check(
    *, write: bool = False, schema_dir: Path = SCHEMA_DIR, load_base: BaseLoader | None = None
) -> CheckResult:
    contracts = {f"{contract.contract_name()}.json": contract for contract in all_contracts()}
    if write:
        schema_dir.mkdir(parents=True, exist_ok=True)
        for filename, contract in contracts.items():
            (schema_dir / filename).write_text(render(contract.schema_document()), encoding="utf-8")
        for orphan in schema_dir.glob("*.json"):
            if orphan.name not in contracts:
                orphan.unlink()
    issues: list[str] = []
    for filename, contract in contracts.items():
        path = schema_dir / filename
        if not path.is_file() or path.read_text(encoding="utf-8") != render(contract.schema_document()):
            issues.append(f"{filename} is out of date")
    orphans = sorted(path.name for path in schema_dir.glob("*.json") if path.name not in contracts)
    if orphans:
        issues.append("schema files without a contract: " + ", ".join(orphans))
    if issues:
        issues.append("run `uv run python -m scripts.checks.contracts --write`, then review the diff")
    loader = load_base or _git_loader(base_ref(), schema_dir)
    for filename, contract in contracts.items():
        base_text = loader(filename)
        base = json.loads(base_text) if base_text else None
        issues.extend(version_rules(base, contract.schema_document(), _changelog(contract)))
    if issues:
        return CheckResult(NAME, ok=False, message="; ".join(issues))
    return CheckResult(NAME, ok=True, message=f"{len(contracts)} contracts")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="regenerate the committed schema files")
    args = parser.parse_args(argv)
    return report(check(write=args.write))


if __name__ == "__main__":
    raise SystemExit(main())
