"""Data-quality rules for the walking skeleton (C10).

Spec 0 needs one rule: `player_id` is unique within one payload. Rules run on candidate rows before they
reach silver; rows that break a rule are kept out and the violation is reported. Rendering rules for AWS
Glue Data Quality arrives with Spec 1.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    """One broken rule: which rule, the offending key, the payload indices involved, and why."""

    rule: str
    key: dict[str, Hashable]
    indices: tuple[int, ...]
    message: str


@dataclass(frozen=True)
class UniqueRule:
    """`column` must be unique within each group of `scope` columns."""

    name: str
    scope: tuple[str, ...]
    column: str
    scope_label: str

    def check(self, rows: Iterable[Mapping[str, Hashable]]) -> list[Violation]:
        """Every duplicated key, in a stable order. Each row carries its payload `index`."""
        columns = (*self.scope, self.column)
        groups: dict[tuple[Hashable, ...], list[int]] = {}
        for row in rows:
            index = row["index"]
            if not isinstance(index, int):
                raise TypeError(f"row index must be an int, got {index!r}")
            groups.setdefault(tuple(row[column] for column in columns), []).append(index)
        violations = [
            Violation(
                rule=self.name,
                key=dict(zip(columns, key, strict=True)),
                indices=tuple(sorted(indices)),
                message=f"{self.column} {key[-1]} appears {len(indices)} times in {self.scope_label}",
            )
            for key, indices in groups.items()
            if len(indices) > 1
        ]
        return sorted(violations, key=lambda violation: tuple(map(str, violation.key.values())))


UNIQUE_PLAYER_PER_PAYLOAD = UniqueRule(
    name="unique_player_id", scope=("bronze_id",), column="player_id", scope_label="one payload"
)
