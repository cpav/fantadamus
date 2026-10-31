"""mvp-collect task 2.2: a small HTML tree for the readers (design C2; R3.4)."""

from __future__ import annotations

from fantadamus.web import html

PAGE = """<!doctype html><html><head><title>Round 10</title><script>var x = "<td>no</td>";</script></head>
<body>
  <section class="prb-squadra prb-squadra--home"><h2 class="prb-squadra__nome">Alfa</h2>
    <table class="prb-tabella"><caption> Probabili titolari </caption>
      <thead><tr><th class="prb-tabella__fonte" title="Uno">U</th>
        <th class="prb-tabella__fonte" title="Due">D</th></tr></thead>
      <tbody><tr><th class="prb-tabella__chi"><span class='role role-a'>A</span>
        <span class="prb-nome">ROSSI<small>M</small></span></th>
        <td class="prb-cella"><span data-original-title="Probabilita&#039; Uno">90%</span></td>
        <td class="prb-cella"><span>55%</span></td></tr></tbody>
    </table>
    <p>first<br>second<img src="x.png"> &amp; third
  </section>
</body></html>"""


def test_find_by_class_and_text() -> None:
    root = html.parse(PAGE)
    section = root.find("section", class_="prb-squadra--home")
    assert section is not None
    assert section.has_class("prb-squadra")
    assert (header := section.find(class_="prb-squadra__nome")) is not None
    assert header.text() == "Alfa"
    assert [cell.attr("title") for cell in section.find_all("th", class_="prb-tabella__fonte")] == [
        "Uno",
        "Due",
    ]
    caption = section.find("caption")
    assert caption is not None
    assert caption.text() == "Probabili titolari"
    row = section.find("tbody")
    assert row is not None
    name = row.find(class_="prb-nome")
    assert name is not None
    assert name.text() == "ROSSI M"
    assert [cell.text() for cell in row.find_all("td", class_="prb-cella")] == ["90%", "55%"]
    assert row.find("span", class_="role-a") is not None
    tooltip = row.find_all("span")[2]
    assert tooltip.attr("data-original-title") == "Probabilita' Uno"
    paragraph = section.find("p")
    assert paragraph is not None
    assert (
        paragraph.text() == "first second & third"
    )  # void tags close themselves, unclosed tags end with their parent
    assert "var x" not in root.text()  # script contents aren't text
    assert root.find("missing") is None
