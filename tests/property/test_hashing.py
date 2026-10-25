"""Property P2: content_sha256 is equal iff the canonical JSON is equal (R16.2)."""

from __future__ import annotations

import json
import random

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.core.hashing import canonical_json, content_sha256

JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=10),
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=6), children, max_size=4)
    ),
    max_leaves=12,
)


@given(value=JSON, rnd=st.randoms(use_true_random=False))
def test_hash_canonical(value: object, rnd: random.Random) -> None:
    def shuffled(obj: object) -> object:
        if isinstance(obj, dict):
            items = list(obj.items())
            rnd.shuffle(items)
            return {key: shuffled(item) for key, item in items}
        if isinstance(obj, list):
            return [shuffled(item) for item in obj]
        return obj

    reordered = shuffled(value)
    assert content_sha256(reordered) == content_sha256(value)
    assert canonical_json(json.loads(json.dumps(value, indent=2))) == canonical_json(value)


@given(a=JSON, b=JSON)
def test_different_content_different_hash(a: object, b: object) -> None:
    assert (content_sha256(a) == content_sha256(b)) == (canonical_json(a) == canonical_json(b))
