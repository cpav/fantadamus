"""AT-3 (mvp-cameos R1.4, R2.1, R2.2): both shares fitted by hand on invented sets, with their samples and
intervals; `CAMEO_RATED` is held at the method's 60%, never fitted."""

from __future__ import annotations

import math

import pytest

from fantadamus.domains.recalibration import cameo_rates, waiting
from fantadamus.engine import constants
from tests.cameos_rows import ONCE_ON, flat, priced, row

Z = 1.6448536269514722
"""A 90% interval's: the normal distribution's 95th percentile."""


def _wilson(events: int, count: int) -> tuple[float, float]:
    """The Wilson score interval, written out."""
    share = events / count
    middle = (share + Z * Z / (2 * count)) / (1 + Z * Z / count)
    half = Z / (1 + Z * Z / count) * math.sqrt(share * (1 - share) / count + Z * Z / (4 * count * count))
    return middle - half, middle + half


def test_at3_both_shares_by_hand() -> None:
    """CAMEO_SHARE: 3 of 10 benched defenders and midfielders got a rating, 0.3. CAMEO_SHARE_PRICED: 9 of
    60 benched forwards and attacking midfielders did, each with a 10% chance of scoring once on, so one who
    comes on is rated 0.1 + 0.9 x 0.6 = 0.64 of the time, and the share is 0.15 / 0.64."""
    rows = [
        *(flat(10, 0, index, rated=index < 3) for index in range(10)),
        *(
            priced(10, 0, 100 + index, rated=index < 9, role="C" if index == 59 else "A")
            for index in range(60)
        ),
        row(10, 0, 200, role="A", priced=True, rated=True),  # no chance of scoring once on was held
        row(10, 0, 201, role="P", rated=True),  # a keeper's cameo isn't the model's
        row(10, 0, 202, rated=True, started=True, p_start=0.9),  # he started
    ]
    fitted = cameo_rates(rows)
    share, share_priced = fitted.rates
    assert (share.name, share.value, share.count, share.events) == ("CAMEO_SHARE", 0.3, 10, 3)
    assert [share.low, share.high] == pytest.approx(list(_wilson(3, 10)))
    assert (share_priced.name, share_priced.count, share_priced.events) == ("CAMEO_SHARE_PRICED", 60, 9)
    assert share_priced.value == pytest.approx(0.15 / ONCE_ON)
    assert [share_priced.low, share_priced.high] == pytest.approx(
        [bound / ONCE_ON for bound in _wilson(9, 60)]
    )
    assert fitted.missing == []


def test_at3_a_share_the_evidence_cant_give() -> None:
    nobody = cameo_rates([row(10, 0, 1, role="P", rated=True)])
    assert nobody.rates == []
    assert nobody.missing == [
        "CAMEO_SHARE: no player with a flat cameo who didn't start and could have come on",
        "CAMEO_SHARE_PRICED: no player with a priced cameo who didn't start and could have come on",
    ]
    often = [priced(10, 0, index, rated=index < 7) for index in range(10)]  # 0.7 rated, more than 0.64 allows
    assert cameo_rates(often).missing == [
        "CAMEO_SHARE: no player with a flat cameo who didn't start and could have come on",
        "CAMEO_SHARE_PRICED: more of them got a rating than any share allows",
    ]


def test_at3_cameo_rated_is_held() -> None:
    rows = [
        *(flat(10, 0, index, rated=index < 3) for index in range(10)),
        *(priced(10, 0, 100 + index, rated=index < 9) for index in range(60)),
    ]
    assert [rate.name for rate in cameo_rates(rows).rates] == ["CAMEO_SHARE", "CAMEO_SHARE_PRICED"]
    assert constants.CAMEO_RATED == 0.6
    waits = {name: wait.needs for wait in waiting(rows) for name in wait.names}
    assert waits["CAMEO_RATED"] == "held at the method's 60% (mvp-cameos R1.4)"
    assert "CAMEO_SHARE_PRICED" not in waits
