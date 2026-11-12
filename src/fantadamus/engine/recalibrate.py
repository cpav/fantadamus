"""Recalibrating the starting values from scored rounds (mvp-recalibrate design C2, C4, C5; method §A8).

Pure: a fit works on the pairs a calibration set holds and proposes values. `engine/constants.py` changes only
when the owner approves them."""

from __future__ import annotations

import bisect
import math
import statistics
from collections.abc import Sequence

from pydantic import BaseModel

from fantadamus.engine.constants import START_MAP_WEIGHT

StartMap = tuple[tuple[float, float], ...]
"""The knots of a map from the outlets' consensus to the chance of starting, from (0, 0) to (1, 1)."""
IDENTITY: StartMap = ((0.0, 0.0), (1.0, 1.0))
_BUCKETS = 10
"""The calibration report's."""
_Z = statistics.NormalDist().inv_cdf(0.95)
"""A 90% interval's."""


def mapped(chance: float, knots: StartMap) -> float:
    """The chance through the map, on the straight line between the knots either side."""
    raws = [raw for raw, _ in knots]
    at = bisect.bisect_right(raws, chance)
    if at == len(knots):
        return knots[-1][1]
    (low, below), (high, above) = knots[at - 1], knots[at]
    return below + (chance - low) / (high - low) * (above - below)


def fit_start_map(pairs: Sequence[tuple[float, bool]], *, weight: float = START_MAP_WEIGHT) -> StartMap:
    """A map from (consensus, started) pairs (C2). Each bucket's rate is shrunk toward its mean consensus with
    the weight of `weight` players, then buckets that go down are pooled with the ones before them, each
    weighing its players plus `weight`. The knots are each bucket's mean consensus and fitted rate, between
    (0, 0) and (1, 1)."""
    groups: dict[int, list[tuple[float, bool]]] = {}
    for pair in pairs:
        groups.setdefault(min(int(pair[0] * _BUCKETS), _BUCKETS - 1), []).append(pair)
    blocks: list[tuple[float, float, list[float]]] = []
    """Pooled buckets: their weight, their fitted rate, and each one's mean consensus."""
    for _, group in sorted(groups.items()):
        raw = math.fsum(chance for chance, _ in group) / len(group)
        started = sum(happened for _, happened in group)
        block = (len(group) + weight, (started + weight * raw) / (len(group) + weight), [raw])
        while blocks and blocks[-1][1] > block[1]:
            before = blocks.pop()
            total = before[0] + block[0]
            block = (total, (before[0] * before[1] + block[0] * block[1]) / total, [*before[2], *block[2]])
        blocks.append(block)
    inside = [(raw, rate) for _, rate, raws in blocks for raw in raws if 0.0 < raw < 1.0]
    return (IDENTITY[0], *inside, IDENTITY[-1])


class Rate(BaseModel):
    """A value counted from the evidence, with its sample and a 90% interval (C4, C5)."""

    name: str
    """The constant's, as `engine/constants.py` writes it."""
    value: float
    count: int
    """What it's counted over: players, games or matches."""
    low: float
    high: float


def counted(name: str, events: int, count: int) -> Rate:
    """How often, of `count`, with the Wilson score interval. More events than chances count as all."""
    share = min(events / count, 1.0)
    spread = _Z * _Z / count
    middle = (share + spread / 2) / (1 + spread)
    half = _Z * math.sqrt(share * (1 - share) / count + spread / (4 * count)) / (1 + spread)
    low, high = min(max(middle - half, 0.0), share), max(min(middle + half, 1.0), share)
    return Rate(name=name, value=share, count=count, low=low, high=high)


def cameo_share(rated: Sequence[bool]) -> Rate | None:
    """`CAMEO_SHARE` (C4): how often a defender or midfielder who didn't start, and could have come on, got a
    rating. The statistics page counts rated games only, so a cameo without one can't be seen."""
    return counted("CAMEO_SHARE", sum(rated), len(rated)) if rated else None


def cameo_rated(forwards: Sequence[tuple[float, bool]], share: float) -> Rate | None:
    """`CAMEO_RATED` (C4), from forwards who didn't start and could have come on: each one's chance of
    scoring if he did, and whether he got a rating. He comes on `share` of the time, and his cameo is rated if
    he scores or, if not, `CAMEO_RATED` of the time: solved from how often they got one, with its interval."""
    if not forwards or share <= 0:
        return None
    scoring = math.fsum(chance for chance, _ in forwards) / len(forwards)
    if scoring >= 1:
        return None
    seen = counted("CAMEO_RATED", sum(rated for _, rated in forwards), len(forwards))

    def solved(rate: float) -> float:
        return min(max((rate / share - scoring) / (1 - scoring), 0.0), 1.0)

    return seen.model_copy(
        update={"value": solved(seen.value), "low": solved(seen.low), "high": solved(seen.high)}
    )
