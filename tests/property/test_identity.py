"""Property P7: identity matching ignores case, accents and spacing, and its output never shows the match."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from hypothesis import assume, given
from hypothesis import strategies as st
from scripts.checks import identities as ids

WORD = st.text(alphabet="abcdefghilmnoprstuvz", min_size=3, max_size=10)
ACCENTS = {"a": "à", "e": "é", "i": "ì", "o": "ò", "u": "ù"}


@st.composite
def variant(draw: st.DrawFn, words: list[str]) -> str:
    """The same name with random case, accents and spacing."""
    out = []
    for word in words:
        chars = [
            (ACCENTS.get(c, c) if draw(st.booleans()) else c).upper() if draw(st.booleans()) else c
            for c in word
        ]
        out.append("".join(chars))
    return (" " * draw(st.integers(1, 3))).join(out)


@given(data=st.data(), words=st.lists(WORD, min_size=1, max_size=3))
def test_identity_normalisation(data: st.DataObject, words: list[str]) -> None:
    identity = " ".join(words)
    written = data.draw(variant(words))
    line = f"intro — {unicodedata.normalize('NFC', written)} — outro"
    env = {"FANTADAMUS_CREATOR_IDENTITIES": identity}
    assert not ids.check_lines([("notes.md", 7, line)], env=env, config=Path("/absent")).ok


@given(words=st.lists(WORD, min_size=1, max_size=2))
def test_identity_output_redacted(words: list[str]) -> None:
    identity = " ".join(words)
    assume(identity not in "notes.md:7 fantacreator identity found at")
    env = {"FANTADAMUS_CREATOR_IDENTITIES": identity}
    result = ids.check_lines([("notes.md", 7, f"see {identity} here")], env=env, config=Path("/absent"))
    assert not result.ok
    assert identity not in result.message.casefold()
