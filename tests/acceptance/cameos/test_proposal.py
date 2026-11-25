"""AT-5 (mvp-cameos R3.1): the proposal lists both shares with their evidence and checks, holds `CAMEO_RATED`,
and changes nothing."""

from __future__ import annotations

import datetime as dt

import pytest

from fantadamus.domains.recalibration import propose, render_proposal
from fantadamus.engine import constants
from tests.cameos_rows import flat, priced

pytestmark = pytest.mark.usefixtures("start_values")  # worked out by hand on a share of 0.5

MADE = dt.datetime(2026, 11, 24, 14, 0, tzinfo=dt.UTC)


def test_at5_both_shares_listed() -> None:
    rows = [
        *(flat(11, index % 4, index, rated=index % 5 == 0) for index in range(240)),
        *(priced(11, index % 4, 5000 + index, rated=(index // 4) % 4 == 0) for index in range(128)),
    ]
    today = (constants.CAMEO_SHARE, constants.CAMEO_SHARE_PRICED, constants.CAMEO_RATED)
    proposal = propose({11: rows}, [], [], made_at=MADE)
    _, share, share_priced = proposal.fitted
    assert (share.name, share.old, share.check.proposed) == ("CAMEO_SHARE", 0.5, True)
    assert share.new == pytest.approx(0.2)
    assert (share_priced.name, share_priced.old, share_priced.check.proposed) == (
        "CAMEO_SHARE_PRICED",
        0.5,
        False,
    )
    assert share_priced.new == pytest.approx(0.25 / 0.64)
    assert share_priced.check.why == "below its minimum sample: 128 of 200"

    lines = render_proposal(proposal).splitlines()
    assert "CAMEO_SHARE: proposed: it improves the Brier score wherever it wasn't fitted" in lines
    assert "CAMEO_SHARE_PRICED: not proposed: below its minimum sample: 128 of 200" in lines
    evidence = "  evidence: 128 players with a priced cameo who didn't start and could have come on"
    assert f"{evidence} (its minimum: 200)" in lines
    assert "  CAMEO_RATED: held at the method's 60% (mvp-cameos R1.4)" in lines
    assert today == (constants.CAMEO_SHARE, constants.CAMEO_SHARE_PRICED, constants.CAMEO_RATED)
