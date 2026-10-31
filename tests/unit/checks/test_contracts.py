"""Task 8.2: the contract-version check (R13.1 to R13.3)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from scripts.checks import contracts
from scripts.checks._common import CheckResult

from fantadamus.contracts.base import SCHEMA_DIR
from fantadamus.contracts.xy.fixtures import FixturesPayload

FIXTURES = "xy.fixtures.FixturesPayload.json"


@pytest.fixture
def schema_dir(tmp_path: Path) -> Path:
    copy = tmp_path / "schemas"
    shutil.copytree(SCHEMA_DIR, copy)
    return copy


def _no_base(_: str) -> str | None:
    return None


def test_committed_schemas_pass(schema_dir: Path) -> None:
    result = contracts.check(schema_dir=schema_dir, load_base=_no_base)
    assert result.ok, result.message


def test_stale_or_missing_schema_fails_with_the_fix(schema_dir: Path) -> None:
    (schema_dir / FIXTURES).write_text("{}\n", encoding="utf-8")
    (schema_dir / "envelope.BronzeEnvelope.json").unlink()
    result = contracts.check(schema_dir=schema_dir, load_base=_no_base)
    assert not result.ok
    assert f"{FIXTURES} is out of date" in result.message
    assert "envelope.BronzeEnvelope.json is out of date" in result.message
    assert "--write" in result.message


def test_orphan_schema_fails_and_write_repairs(schema_dir: Path) -> None:
    (schema_dir / "gone.Old.json").write_text("{}\n", encoding="utf-8")
    (schema_dir / FIXTURES).write_text("{}\n", encoding="utf-8")
    assert (
        "schema files without a contract: gone.Old.json"
        in contracts.check(schema_dir=schema_dir, load_base=_no_base).message
    )
    assert contracts.check(write=True, schema_dir=schema_dir, load_base=_no_base).ok
    assert not (schema_dir / "gone.Old.json").exists()


def _base_with(**changes: Any) -> contracts.BaseLoader:
    def load(filename: str) -> str | None:
        doc = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        if filename == FIXTURES:
            doc.update(changes)
        return json.dumps(doc)

    return load


def test_unchanged_base_passes(schema_dir: Path) -> None:
    assert contracts.check(schema_dir=schema_dir, load_base=_base_with()).ok


def test_schema_change_without_bump_fails(schema_dir: Path) -> None:
    old_schema = FixturesPayload.model_json_schema() | {"title": "Old title"}
    result = contracts.check(schema_dir=schema_dir, load_base=_base_with(schema=old_schema))
    assert not result.ok
    assert "schema changed without a version bump (still 1.0.0)" in result.message


def test_breaking_change_with_minor_bump_fails() -> None:
    old = {"properties": {"shirt": {"type": "integer"}}}
    base = {"contract": "a.B", "version": "1.0.0", "schema": old}
    current = {"contract": "a.B", "version": "1.1.0", "schema": {"properties": {}}}
    assert contracts.version_rules(base, current, "## B 1.1.0\n") == [
        "a.B: breaking change needs a major bump (1.0.0 → 1.1.0): $.shirt: removed"
    ]


def test_major_bump_and_backwards_version(schema_dir: Path) -> None:
    old_schema = FixturesPayload.model_json_schema()
    old_schema["properties"] = old_schema["properties"] | {"shirt": {"type": "integer"}}
    assert contracts.check(schema_dir=schema_dir, load_base=_base_with(version="0.1.0", schema=old_schema)).ok
    result = contracts.check(schema_dir=schema_dir, load_base=_base_with(version="2.0.0"))
    assert "version went backwards (2.0.0 → 1.0.0)" in result.message


def test_missing_changelog_entry_and_bad_version() -> None:
    current = {"contract": "a.B", "version": "1.0.0", "schema": {}}
    assert contracts.version_rules(None, current, "## B 0.9.0\n") == [
        "a.B: no changelog heading '## B 1.0.0'"
    ]
    assert contracts.version_rules(None, current, "## B 1.0.0 (2026-10-25)\n") == []
    bad = current | {"version": "1.0"}
    assert contracts.version_rules(None, bad, "") == ["a.B: __version__ '1.0' is not a semantic version"]


def test_git_loader_reads_the_base_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> Any:
        calls.append(args)
        found = args[-1].endswith(FIXTURES)
        return type("Done", (), {"returncode": 0 if found else 128, "stdout": "{}" if found else ""})()

    monkeypatch.setattr(contracts, "run_command", fake_run)
    load = contracts._git_loader("main", SCHEMA_DIR)
    assert load(FIXTURES) == "{}"
    assert load("missing.json") is None
    assert calls[0][-1] == f"main:src/fantadamus/contracts/schemas/{FIXTURES}"


def _s(**schema: Any) -> dict[str, Any]:
    return schema


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (_s(type="integer"), _s(type="number"), []),
        (_s(type="number"), _s(type="integer"), ["$: type number no longer accepted"]),
        (_s(), _s(type="string"), ["$: type any no longer accepted"]),
        (_s(type=["string", "null"]), _s(type="string"), ["$: type null no longer accepted"]),
        (_s(const="a"), _s(enum=["a", "b"]), []),
        (_s(type="string"), _s(type="string", enum=["a"]), ['$: ["any value"] no longer accepted']),
        (_s(minimum=0), _s(exclusiveMinimum=0), ["$: lower bound tightened"]),
        (_s(exclusiveMinimum=0), _s(minimum=0), []),
        (_s(), _s(maximum=10), ["$: upper bound tightened"]),
        (_s(maximum=10), _s(maximum=5), ["$: upper bound tightened"]),
        (_s(maximum=10), _s(exclusiveMaximum=10), ["$: upper bound tightened"]),
        (_s(maxItems=3), _s(), []),
        (_s(minItems=0), _s(minItems=1), ["$: minItems raised to 1"]),
        (_s(pattern="^a"), _s(pattern="^b"), ["$: pattern changed to '^b'"]),
        (
            _s(items={"type": "string"}),
            _s(items={"type": "integer"}),
            ["$[]: type string no longer accepted"],
        ),
        (
            _s(properties={}),
            _s(properties={}, additionalProperties=False),
            ["$: additional properties no longer accepted"],
        ),
        (
            _s(anyOf=[{"type": "string"}, {"type": "null"}]),
            _s(anyOf=[{"type": "null"}, {"type": "string"}, {"type": "integer"}]),
            [],
        ),
        (
            _s(anyOf=[{"type": "string"}, {"type": "null"}]),
            _s(type="string"),
            ["$: a previously accepted alternative is no longer accepted"],
        ),
        (
            _s(properties={"a": {"$ref": "#/$defs/A"}}, **{"$defs": {"A": {"type": "string"}}}),
            _s(properties={"a": {"$ref": "#/$defs/A"}}, **{"$defs": {"A": {"type": "integer"}}}),
            ["$.a: type string no longer accepted"],
        ),
        (_s(properties={"a": True}), _s(properties={"a": False}), ['$.a: ["any value"] no longer accepted']),
    ],
)
def test_breaking_change_classification(
    old: dict[str, Any], new: dict[str, Any], expected: list[str]
) -> None:
    assert contracts.breaking_changes(old, new) == expected


def test_self_referencing_schema_stops() -> None:
    looping = {"$ref": "#/$defs/A", "$defs": {"A": {"$ref": "#/$defs/A"}}}
    assert contracts.breaking_changes(looping, looping) == []
    nested: dict[str, Any] = {"type": "array"}
    deep = nested
    for _ in range(contracts.MAX_DEPTH + 2):
        deep["items"] = {"type": "array"}
        deep = deep["items"]
    assert contracts.breaking_changes(nested, nested) == [
        "$" + "[]" * (contracts.MAX_DEPTH + 1) + ": too deeply nested to compare"
    ]


def test_main_writes_and_reports(monkeypatch: pytest.MonkeyPatch, schema_dir: Path) -> None:
    seen: dict[str, Any] = {}

    def fake_check(*, write: bool = False) -> CheckResult:
        seen["write"] = write
        return CheckResult("contracts", ok=True)

    monkeypatch.setattr(contracts, "check", fake_check)
    assert contracts.main(["--write"]) == 0
    assert seen == {"write": True}
