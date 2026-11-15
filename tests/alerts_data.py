"""Invented calls for the alerts' tests (mvp-alerts): a squad of twelve, its roles and names."""

from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any

from fantadamus.contracts.types import Role
from fantadamus.domains.alerts import Call, call_of

AT = dt.datetime(2026, 11, 21, 8, 0, tzinfo=dt.UTC)
LATER = AT + dt.timedelta(hours=3)

ROLES: dict[int, Role] = {
    1: "P",
    2: "D",
    3: "D",
    4: "D",
    5: "C",
    6: "C",
    7: "C",
    8: "A",
    9: "A",
    10: "P",
    11: "D",
    12: "D",
    13: "C",
    14: "A",
}
NAMES = {
    1: "Rossi",
    2: "Bianchi",
    3: "Verdi",
    4: "Neri",
    5: "Russo",
    6: "Gallo",
    7: "Conti",
    8: "Greco",
    9: "Bruno",
    10: "Marino",
    11: "Costa",
    12: "Fontana",
    13: "Rizzo",
    14: "Lombardi",
}


def a_call(**changes: Any) -> Call:
    """The 3-4-3 the user saw: 1 in goal, 2-4 at the back, 5-7 and 13 in midfield, 8, 9 and 14 up front;
    11 then 12 the defenders off the bench."""
    settings: dict[str, Any] = {
        "round": 12,
        "formation": "3-4-3",
        "starters": [1, 2, 3, 4, 5, 6, 7, 13, 8, 9, 14],
        "bench": [10, 11, 12],
        "roles": ROLES,
        "captain": 8,
        "vice": 9,
        "chances": dict.fromkeys(ROLES, 0.8),
        "at": AT,
    }
    return call_of(**(settings | changes))


def moved(call: Call, **changes: Any) -> Call:
    return dataclasses.replace(call, **changes)
