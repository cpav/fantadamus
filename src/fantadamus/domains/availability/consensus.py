"""From outlets' lineups to p_start and p_cameo (design C5; R3.2 to R3.4, R4.2).

Each outlet gives one view of a player: a starter 0.90, his share in a ballottaggio, 0.05 on the bench or not
mentioned at all, 0 if unavailable. p_start is their mean; the spread between outlets marks him disputed.
An official lineup replaces all of that.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from fantadamus.domains.facts import Source
from fantadamus.engine.constants import CAMEO_SHARE, DISPUTED_SPREAD, P_START_BENCH, P_START_STARTER

Listed = Literal["starter", "ballottaggio", "bench", "unavailable"]
Status = Literal[Listed, "not listed"]
OfficialStatus = Literal["starter", "bench", "not listed"]

_P_START: dict[str, float] = {
    "starter": P_START_STARTER,
    "bench": P_START_BENCH,
    "not listed": P_START_BENCH,
    "unavailable": 0.0,
}


class OutletView(BaseModel):
    model_config = ConfigDict(frozen=True)

    outlet: str
    status: Status
    p_start: float
    source: Source
    rivals: list[str] = []
    """The others in his ballottaggio, as the outlet writes them."""


class OfficialView(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: OfficialStatus
    source: Source


class Availability(BaseModel):
    model_config = ConfigDict(frozen=True)

    p_start: float
    p_cameo: float
    spread: float
    """Highest outlet view minus lowest."""
    disputed: bool
    outlets: list[OutletView]
    official: OfficialView | None


def outlet_view(
    outlet: str, status: Status, share: float | None, source: Source, rivals: Sequence[str] = ()
) -> OutletView:
    """One outlet's view of a player; `share` is his ballottaggio percentage."""
    if status == "ballottaggio":
        if share is None:
            raise ValueError("a ballottaggio view needs the player's share")
        p_start = share / 100
    else:
        p_start = _P_START[status]
    return OutletView(outlet=outlet, status=status, p_start=p_start, source=source, rivals=sorted(rivals))


def combine(outlets: Sequence[OutletView], official: OfficialView | None = None) -> Availability:
    """The consensus of the outlets, unless the official lineup is out."""
    ordered = sorted(
        outlets, key=lambda view: (view.outlet, view.source.captured_at, view.status, view.p_start)
    )
    values = [view.p_start for view in ordered]
    spread = round(max(values) - min(values), 9) if values else 0.0
    if official is not None:
        p_start = 1.0 if official.status == "starter" else 0.0
        p_cameo = CAMEO_SHARE if official.status == "bench" else 0.0
        disputed = False
    elif values:
        p_start = math.fsum(values) / len(values)
        unavailable = any(view.status == "unavailable" for view in ordered)
        p_cameo = 0.0 if unavailable else CAMEO_SHARE * (1 - p_start)
        disputed = len(values) >= 2 and spread >= DISPUTED_SPREAD
    else:
        raise ValueError("no outlet views and no official lineup")
    return Availability(
        p_start=p_start, p_cameo=p_cameo, spread=spread, disputed=disputed, outlets=ordered, official=official
    )
