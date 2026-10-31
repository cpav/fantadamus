"""P1: bronze is append-only, and rebuilding silver never touches it (engineering-foundation R16.3), with
real fixture records and the facts rebuild. It moved here from the walking skeleton, retired on 2026-10-31."""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from fantadamus.contracts.envelope import BronzeEnvelope
from fantadamus.contracts.xy.fixtures import FixturesPayload
from fantadamus.core.hashing import content_sha256
from fantadamus.domains import facts
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.lake.duckdb_store import LakeStore
from tests.xy_harness import CLUBS

T0 = dt.datetime(2026, 10, 25, 10, 0, tzinfo=dt.UTC)

fixtures = st.builds(
    lambda round_, clubs, hours: FixturesPayload.model_validate(
        {
            "round": round_,
            "matches": [
                {"home": clubs[0], "away": clubs[1], "kickoff_at": T0 + dt.timedelta(hours=hours)},
                {"home": clubs[2], "away": clubs[3], "kickoff_at": T0 + dt.timedelta(hours=hours + 3)},
            ],
        }
    ),
    st.integers(1, 38),
    st.permutations(["Alfa", "Beta", "Gamma", "Delta"]),
    st.integers(24, 96),
)
submissions = st.lists(
    st.tuples(
        fixtures,
        st.sampled_from(["https://example.org/a", "https://www.example.org/b"]),
        st.integers(0, 3).map(lambda hours: T0 - dt.timedelta(hours=hours)),
    ),
    min_size=1,
    max_size=4,
)


def _envelope(payload: FixturesPayload, source_url: str, captured_at: dt.datetime) -> BronzeEnvelope:
    data = payload.model_dump(mode="json")
    return BronzeEnvelope(
        source=FIXTURES.source,
        source_url=source_url,
        published_at=None,
        captured_at=captured_at,
        received_at=T0,  # one time for all, so file names collide and must still never overwrite
        content_sha256=content_sha256(data),
        contract_version=payload.__version__,
        submitted_by="user-1",
        payload=data,
    )


# Each example writes Parquet files, whose timing varies with the disk: no per-example deadline. The example
# count still comes from the profile.
@settings(deadline=None)
@given(batch=submissions, repeat=st.booleans())
def test_bronze_append_only(batch: list[tuple[FixturesPayload, str, dt.datetime]], repeat: bool) -> None:
    with tempfile.TemporaryDirectory() as root:
        store = LakeStore(Path(root))
        written: dict[Path, bytes] = {}
        for payload, source_url, captured_at in batch + (batch[:1] if repeat else []):
            bronze_id = store.append_bronze(_envelope(payload, source_url, captured_at))
            files = store.bronze_files(FIXTURES.source)
            assert {path: path.read_bytes() for path in written} == written
            assert len(files) == len(written) + 1
            assert bronze_id in {path.stem for path in files}
            written.update({path: path.read_bytes() for path in files})
        facts.rebuild(store, FIXTURES, CLUBS)  # rebuilding silver from every record leaves bronze untouched
        assert {path: path.read_bytes() for path in written} == written
        assert len(facts.read_silver(store, FIXTURES)) == 2 * len(written)
