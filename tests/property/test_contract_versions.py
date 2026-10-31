"""Property P8: a schema change needs a version bump and a changelog entry; a breaking one, a major bump
(R13.2, R13.3)."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from hypothesis import assume, given
from hypothesis import strategies as st
from scripts.checks.contracts import version_rules

Schema = dict[str, Any]

BASE_SCHEMA: Schema = {
    "additionalProperties": False,
    "properties": {
        "player_id": {"exclusiveMinimum": 0, "title": "Player Id", "type": "integer"},
        "name": {"maxLength": 60, "minLength": 1, "title": "Name", "type": "string"},
        "club": {"minLength": 1, "title": "Club", "type": "string"},
        "role": {"enum": ["P", "D", "C", "A"], "title": "Role", "type": "string"},
    },
    "required": ["player_id", "name", "club", "role"],
    "title": "Player",
    "type": "object",
}


def _props(schema: Schema) -> dict[str, Schema]:
    properties: dict[str, Schema] = schema["properties"]
    return properties


def _add_optional(schema: Schema) -> None:
    _props(schema)["nickname"] = {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}


def _add_required(schema: Schema) -> None:
    _props(schema)["shirt"] = {"type": "integer"}
    schema["required"].append("shirt")


def _remove_club(schema: Schema) -> None:
    _props(schema).pop("club", None)
    schema["required"] = [name for name in schema["required"] if name != "club"]


def _narrow_role(schema: Schema) -> None:
    role = _props(schema)["role"]
    role["enum"] = [value for value in role["enum"] if value != "A"]


def _widen_role(schema: Schema) -> None:
    role = _props(schema)["role"]
    role["enum"] = [*role["enum"], "X"] if "X" not in role["enum"] else role["enum"]


def _club_to_integer(schema: Schema) -> None:
    if "club" in _props(schema):
        _props(schema)["club"]["type"] = "integer"


def _player_id_to_number(schema: Schema) -> None:
    _props(schema)["player_id"]["type"] = "number"


def _shorter_name(schema: Schema) -> None:
    _props(schema)["name"]["maxLength"] = 30


def _allow_empty_name(schema: Schema) -> None:
    _props(schema)["name"]["minLength"] = 0


def _name_optional(schema: Schema) -> None:
    schema["required"] = [name for name in schema["required"] if name != "name"]
    _props(schema)["name"]["default"] = "?"


def _retitle(schema: Schema) -> None:
    schema["title"] = "Player"


# name → (mutation, is it breaking?)
MUTATIONS: dict[str, tuple[Callable[[Schema], None], bool]] = {
    "add_optional": (_add_optional, False),
    "add_required": (_add_required, True),
    "remove_club": (_remove_club, True),
    "narrow_role": (_narrow_role, True),
    "widen_role": (_widen_role, False),
    "club_to_integer": (_club_to_integer, True),
    "player_id_to_number": (_player_id_to_number, False),
    "shorter_name": (_shorter_name, True),
    "allow_empty_name": (_allow_empty_name, False),
    "name_optional": (_name_optional, False),
    "retitle": (_retitle, False),
}

Version = tuple[int, int, int]


def _bump(version: Version, kind: str) -> Version:
    major, minor, patch = version
    return {
        "none": version,
        "patch": (major, minor, patch + 1),
        "minor": (major, minor + 1, 0),
        "major": (major + 1, 0, 0),
        "down": (major, minor, patch - 1) if patch else (major, minor - 1, 0) if minor else (major - 1, 0, 0),
    }[kind]


def _text(version: Version) -> str:
    return ".".join(map(str, version))


@given(
    mutations=st.lists(st.sampled_from(sorted(MUTATIONS)), unique=True, max_size=3),
    base_version=st.tuples(st.integers(0, 3), st.integers(0, 3), st.integers(0, 3)),
    bump=st.sampled_from(["none", "patch", "minor", "major", "down"]),
    has_entry=st.booleans(),
    has_base=st.booleans(),
)
def test_contract_version_rules(
    mutations: list[str], base_version: Version, bump: str, has_entry: bool, has_base: bool
) -> None:
    assume(not (bump == "down" and base_version == (0, 0, 0)))
    current_version = _bump(base_version, bump)
    schema = copy.deepcopy(BASE_SCHEMA)
    for name in mutations:
        MUTATIONS[name][0](schema)
    changed = schema != BASE_SCHEMA
    breaking = any(MUTATIONS[name][1] for name in mutations)

    entries = ["## OtherContract " + _text(current_version)]
    if current_version != base_version:
        entries.append("## Player " + _text(base_version))
    if has_entry:
        entries.append("## Player " + _text(current_version) + " (2026-10-25)")
    changelog = "# Changelog\n\n" + "\n\n- a change\n\n".join(entries) + "\n"

    contract = "sample.player.Player"
    base = {"contract": contract, "version": _text(base_version), "schema": BASE_SCHEMA} if has_base else None
    current = {"contract": contract, "version": _text(current_version), "schema": schema}
    issues = version_rules(base, current, changelog)

    expected_failure = not has_entry or (
        has_base
        and (
            current_version < base_version
            or (changed and current_version == base_version)
            or (breaking and current_version[0] <= base_version[0])
        )
    )
    assert bool(issues) == expected_failure, issues
