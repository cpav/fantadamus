"""AT-1 (mvp-cameos R1.1, R1.2): each kind of cameo by hand, through `best_lineup`: a flat cameo takes the
flat share and a priced one the priced share, before and after a share changes, and on an official bench."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.availability.consensus import OfficialView, combine, outlet_view
from fantadamus.engine import constants
from fantadamus.engine.outfield import cameo_share, priors
from tests.cards_data import OUTLETS, source
from tests.lineup_harness import CLUBS, LINES, a_round, player_id
from tests.xy_harness import NOW

pytestmark = pytest.mark.anyio

ROLES = {player_id(club, word): role for club in CLUBS for word, (role, _) in LINES.items()}
PRICED = {
    player_id(club, word): role != "P" and priors(role, mantra).priced_cameo
    for club in CLUBS
    for word, (role, mantra) in LINES.items()
}


async def test_at1_each_kind_by_hand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(constants, "CAMEO_SHARE", 0.5)
    async with a_round(tmp_path) as here:
        await here.ask()
        monkeypatch.setattr(constants, "CAMEO_SHARE", 0.3)
        monkeypatch.setattr(constants, "CAMEO_SHARE_PRICED", 0.7)
        here.clock.now = NOW + dt.timedelta(minutes=1)
        await here.ask()
        before, after = here.log.read()
    was = {player.player_id: player for player in before.players}
    now = {player.player_id: player for player in after.players}
    flat = [id for id, player in was.items() if ROLES[id] != "P" and not PRICED[id] and player.p_cameo > 0]
    priced = [id for id, player in was.items() if PRICED[id] and player.p_cameo > 0]
    assert flat
    assert priced
    for id in flat:  # a flat cameo is rated whenever he comes on: the share of his chance of not starting
        assert now[id].p_start == was[id].p_start
        assert was[id].p_cameo == pytest.approx(0.5 * (1 - was[id].p_start))
        assert now[id].p_cameo == pytest.approx(0.3 * (1 - now[id].p_start))
    for id in priced:  # a priced one comes on on the priced share, then is rated as the method's outcomes say
        assert now[id].p_start == was[id].p_start
        assert now[id].p_cameo == pytest.approx(was[id].p_cameo * 0.7 / 0.5)


def test_at1_an_official_bench(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(constants, "CAMEO_SHARE", 0.3)
    monkeypatch.setattr(constants, "CAMEO_SHARE_PRICED", 0.7)
    views = [outlet_view(outlet, "percentage", 60, source()) for outlet in OUTLETS]
    bench = OfficialView(status="bench", source=source())
    assert combine(views, bench, share=cameo_share("A", "Pc")).p_cameo == 0.7
    assert combine(views, bench, share=cameo_share("C", "C")).p_cameo == 0.3
