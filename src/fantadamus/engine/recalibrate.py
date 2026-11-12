"""Recalibrating the starting values from scored rounds (mvp-recalibrate design C2; method §A8).

Pure: a fit works on the pairs a calibration set holds and proposes values. `engine/constants.py` changes only
when the owner approves them."""

from __future__ import annotations

import bisect
import math
from collections.abc import Sequence

from fantadamus.engine.constants import START_MAP_WEIGHT

StartMap = tuple[tuple[float, float], ...]
"""The knots of a map from the outlets' consensus to the chance of starting, from (0, 0) to (1, 1)."""
IDENTITY: StartMap = ((0.0, 0.0), (1.0, 1.0))
_BUCKETS = 10
"""The calibration report's."""


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
