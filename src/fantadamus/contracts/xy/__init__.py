"""Contracts of the `mvp-x-or-y` slice: one per submit tool, each with its quality rules (design C2, R8)."""

from __future__ import annotations

from collections.abc import Iterable

from fantadamus.core.names import name_key


def once_each(names: Iterable[str], twice: str) -> None:
    """Raise `twice` (formatted with the first spelling) when two names match ignoring case and accents."""
    seen: dict[str, str] = {}
    for name in names:
        key = name_key(name)
        if key in seen:
            raise ValueError(twice.format(name=seen[key]))
        seen[key] = name
