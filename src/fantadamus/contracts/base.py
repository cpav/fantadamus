"""The contract base class and the registry of contracts (R13.1).

A contract is a frozen, strict pydantic model with a `__version__` class attribute. Its JSON Schema is
committed under `schemas/`, and `scripts/checks/contracts.py` fails when it drifts or when a change lacks
the version bump and changelog entry it needs (R13.2, R13.3).
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

PACKAGE = __name__.rpartition(".")[0]
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
SEMVER_PATTERN = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"


class Contract(BaseModel):
    """Base for every data contract: immutable, no extra fields, no silent type coercion."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    __version__: ClassVar[str]

    @classmethod
    def contract_name(cls) -> str:
        """Module path below the package plus the class name, e.g. `skeleton.player.SkeletonPlayer`."""
        return f"{cls.__module__.removeprefix(PACKAGE + '.')}.{cls.__qualname__}"

    @classmethod
    def schema_document(cls) -> dict[str, Any]:
        """What is committed for this contract: its name, version and JSON Schema."""
        return {
            "contract": cls.contract_name(),
            "version": cls.__version__,
            "schema": cls.model_json_schema(),
        }


class Part(BaseModel):
    """A nested part of a contract (a match, a team): same rules, versioned with the contract holding it."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


def all_contracts() -> list[type[Contract]]:
    """Every contract defined in the `fantadamus.contracts` package, sorted by name."""
    package = importlib.import_module(PACKAGE)
    for module in pkgutil.walk_packages(package.__path__, PACKAGE + "."):
        importlib.import_module(module.name)
    found: set[type[Contract]] = set()
    pending = list(Contract.__subclasses__())
    while pending:
        contract = pending.pop()
        pending.extend(contract.__subclasses__())
        if contract.__module__.startswith(PACKAGE + "."):
            found.add(contract)
    return sorted(found, key=lambda contract: contract.contract_name())
