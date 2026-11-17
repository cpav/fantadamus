"""mvp-store task 2.4: every domain is listed once, in the one list `fantadamus rebuild` goes through
(design C4; R2.4)."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

import fantadamus.domains
from fantadamus.domains.facts import Domain
from fantadamus.domains.tables import BY_TABLE, DOMAINS


def _defined() -> list[Domain[Any, Any]]:
    """Every domain a module under `fantadamus.domains` holds, each once however many import it."""
    found: dict[int, Domain[Any, Any]] = {}
    for info in pkgutil.walk_packages(fantadamus.domains.__path__, "fantadamus.domains."):
        for value in vars(importlib.import_module(info.name)).values():
            if isinstance(value, Domain):
                found[id(value)] = value
    return list(found.values())


def test_every_domain_is_listed_once() -> None:
    defined = _defined()
    assert sorted(domain.table.name for domain in DOMAINS) == sorted(domain.table.name for domain in defined)
    assert {id(domain) for domain in DOMAINS} == {id(domain) for domain in defined}
    assert len(DOMAINS) == 13
    assert len({domain.table.name for domain in DOMAINS}) == 13  # a table each
    assert len({domain.source for domain in DOMAINS}) == 13  # and a bronze folder each
    assert list(BY_TABLE.items()) == [(domain.table.name, domain) for domain in DOMAINS]
