"""P8: the decision log only grows; earlier lines are never changed (design C12; R14.2)."""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.lake.decision_log import Decision, DecisionLog, LoggedPlayer
from fantadamus.league.rules import CLASSIC, StoredRules

AT = dt.datetime(2026, 10, 26, 10, 0, tzinfo=dt.UTC)
TEMPLATE = Decision(
    as_of=AT,
    logged_at=AT,
    user="user-1",
    round=9,
    players=[LoggedPlayer(player_id=1, name="Alfa Nove", p_start=0.9, p_cameo=0.05, p_scores=0.3, key=7.0)],
    first="Alfa Nove",
    second="Gamma Nove",
    margin=0.4,
    label="lean",
    rules=StoredRules(user="user-1", saved_at=AT, rules=CLASSIC),
    content_hashes=["0" * 64],
)


@given(
    st.lists(st.tuples(st.integers(min_value=0, max_value=70), st.floats(0, 5, allow_nan=False)), max_size=8)
)
def test_p8_log_only_grows(appends: list[tuple[int, float]]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        log = DecisionLog(Path(directory))
        for days, margin in appends:
            before = {path.name: path.read_text(encoding="utf-8") for path in Path(directory).glob("*.jsonl")}
            log.append(TEMPLATE.model_copy(update={"as_of": AT + dt.timedelta(days=days), "margin": margin}))
            after = {path.name: path.read_text(encoding="utf-8") for path in Path(directory).glob("*.jsonl")}
            assert all(after[name].startswith(text) for name, text in before.items())
            assert (
                sum(text.count("\n") for text in after.values())
                == sum(text.count("\n") for text in before.values()) + 1
            )
        assert len(log.read()) == len(appends)
