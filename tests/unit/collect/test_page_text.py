"""mvp-collect task 3.2: a page's readable text for Claude (design C3.2; R3.2)."""

from __future__ import annotations

from fantadamus.web.html import parse
from fantadamus.web.text import page_text, parts

URL = "https://www.example.org/classifica"
PAGE = """<html><head><title>Serie A</title></head><body>
<nav><a href="/menu">Menu</a><ul><li>Home</li></ul></nav>
<main>
  <h1>Classifica</h1>
  <p>Aggiornata al <b>30 ottobre</b>.</p>
  <table>
    <caption>Serie A</caption>
    <thead><tr><th>Squadra</th><th>G</th></tr></thead>
    <tbody><tr><td><a href="/serie-a/squadre/alfa">Alfa</a></td><td>9</td></tr></tbody>
  </table>
  <h2>Note</h2>
  <ul><li>Primo</li><li>Secondo <a href="/altro">altro</a></li>
    <li><a href="/serie-a/squadre/beta"><img src="beta.png"></a></li></ul>
  <form><label>Cerca</label><input name="q"></form>
  <aside>Pubblicità</aside>
  <footer>Cookie</footer>
</main>
<footer>Fuori</footer>
</body></html>"""


def follow(address: str) -> bool:
    return address.startswith("https://www.example.org/serie-a/squadre/")


def test_tables_links_and_menus() -> None:
    assert page_text(parse(PAGE), URL, follow).splitlines() == [
        "# Classifica",
        "Aggiornata al 30 ottobre.",
        "Serie A",
        "Squadra | G",
        "Alfa (https://www.example.org/serie-a/squadre/alfa) | 9",
        "## Note",
        "- Primo",
        "- Secondo altro",
    ]
    without_main = "<body><h3>Rigoristi</h3><div>Alfa: <span>Nove</span>, Dieci</div></body>"
    assert page_text(parse(without_main), URL, follow).splitlines() == ["### Rigoristi", "Alfa: Nove, Dieci"]


def test_long_text_in_parts() -> None:
    lines = [f"riga {n} " + "x" * 30 for n in range(100)]
    text = "\n".join(lines)
    split = parts(text, size=400)
    assert all(len(part) <= 400 for part in split)
    assert "\n".join(split).splitlines() == lines  # split between lines, nothing lost or repeated
    assert len(split) == 10  # nine 40-character lines a part, the last part shorter
    assert parts("y" * 900, size=400) == ["y" * 400, "y" * 400, "y" * 100]  # a line longer than a part
    assert parts("", size=400) == [""]
