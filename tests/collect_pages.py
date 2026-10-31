"""Synthetic pages with the real pages' structure (class names, captions, attributes) and invented clubs and
players, for the reader's tests. Real pages can't be committed to a public repository (mvp-collect design)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from tests.xy_harness import WORDS

OUTLETS = ("Fantacalcio.it", "Gazzetta", "SOS Fanta", "Sky")


def squad(club: str) -> list[str]:
    """Fourteen invented players, `<Club> Uno` to `<Club> Quattordici`: 11 starters, 2 on the bench, 1 out."""
    return [f"{club} {word}" for word in WORDS]


def fco_name(name: str) -> str:
    """Fantacalcio-Online writes the surname in capitals, then the initial: `NOVE<small>A</small>`."""
    first, surname = name.split(" ", 1)
    return f"{surname.upper()}<small>{first[0]}</small>"


@dataclass
class FcoMatch:
    home: str
    away: str
    kickoff: str = "31/10/2026 15:00"
    odds: tuple[str, str, str] | None = ("2,10", "3,30", "3,60")  # None: no odds shown yet
    over3: str = "53%"
    updated: str = "quote aggiornate il 30 ottobre alle 18:13"
    percents: Mapping[str, tuple[int | None, ...]] = field(default_factory=dict)  # None: the outlet's dash
    confirmed: bool = False
    lineups: bool = True  # False: the teams' sections are there, their tables not published yet


def _role(letter: str) -> str:
    return f"<span class='role role-{letter.lower()}'>{letter}</span>"


def _fco_row(name: str, percents: tuple[int | None, ...], confirmed: bool) -> str:
    cells = "".join(
        f'<td class="prb-cella"><span data-original-title="Probabilita&#039; x">{p}%</span></td>'
        if p is not None
        else '<td class="prb-cella prb-cella--vuota">\u2013</td>'
        for p in percents
    )
    given = [p for p in percents if p is not None]
    average = round(sum(given) / len(given))
    return (
        f'<tr><th scope="row" class="prb-tabella__chi">{_role("A")} '
        f'<span class="prb-nome">{fco_name(name)}</span></th>{cells}'
        f'<td class="prb-cella prb-cella--media"><span>{average}%</span></td>'
        f'<td class="prb-cella prb-tabella__conferma">{"&#10003;" if confirmed else " "}</td></tr>'
    )


def _fco_table(caption: str, rows: str) -> str:
    sources = "".join(
        f'<th scope="col" class="prb-tabella__fonte " title="{outlet}">{outlet[:3]}</th>'
        for outlet in OUTLETS
    )
    average = (
        '<th scope="col" class="prb-tabella__fonte prb-tabella__fonte--media " '
        'title="Tutte le fonti">Media*</th>'
    )
    confirmed = (
        '<th scope="col" class="prb-tabella__fonte prb-tabella__conferma">'
        '<span class="sr-only">Confermato</span><span aria-hidden="true">Uff.</span></th>'
    )
    return (
        f'<table class="prb-tabella"><caption class="sr-only">{caption}</caption>'
        f'<thead><tr><th scope="col">Titolare</th>{sources}{average}{confirmed}</tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )


def _fco_team(club: str, side: str, match: FcoMatch) -> str:
    heading = f'<section class="prb-squadra prb-squadra--{side}"><h2 class="prb-squadra__nome">{club}</h2>'
    if not match.lineups:
        return f"{heading}</section>"
    players = squad(club)
    starters = "".join(
        _fco_row(name, match.percents.get(name, (90, 90, 95, 90)), match.confirmed) for name in players[:11]
    )
    bench = "".join(
        _fco_row(name, match.percents.get(name, (10, 30, 5, 30)), False) for name in players[11:13]
    )
    out = (
        '<div class="prb-fuori"><p class="prb-fuori__titolo">Indisponibili</p>'
        f'<ul class="prb-fuori__elenco"><li class="prb-fuori__riga">{_role("A")} '
        f'<span class="prb-nome">{fco_name(players[13])}</span> '
        '<span class="fco-etichetta">Infortunato</span></li></ul></div>'
    )
    return (
        f"{heading}{_fco_table('Probabili titolari: percentuale per redazione', starters)}"
        f"{_fco_table('Probabile panchina: percentuale per redazione', bench)}{out}</section>"
    )


def _fco_header(match: FcoMatch) -> str:
    return (
        '<header class="prb-incontro"><div class="prb-incontro__lato">'
        f'<span class="prb-incontro__nome">{match.home}</span></div>'
        '<div class="prb-incontro__centro"><p class="prb-incontro__punteggio">0<span>:</span>0</p>'
        '<p class="prb-incontro__stato">Non iniziata</p>'
        f'<p class="prb-incontro__data">{match.kickoff}</p></div>'
        '<div class="prb-incontro__lato prb-incontro__lato--ospite">'
        f'<span class="prb-incontro__nome">{match.away}</span></div></header>'
    )


def _fco_summary(match: FcoMatch) -> str:
    labels = (f"1 · {match.home}", "X · pareggio", f"2 · {match.away}")
    boxes = "".join(
        f'<div class="stp-qbox"><div class="stp-qlab">{label}</div><div class="stp-qval">{odd}</div></div>'
        for label, odd in zip(labels, match.odds or (), strict=False)
    )
    return (
        f'<div class="prb-sintesi"><div class="prb-sintesi__quote">{boxes}</div>'
        '<ul class="prb-sintesi__mercati">'
        f"<li><span>Gol attesi</span> <b>3 o più</b> <i>{match.over3}</i></li>"
        f'<li class="prb-sintesi__ora">{match.updated}</li></ul></div>'
    )


def fco_round_page(*matches: FcoMatch, round: int | None = 10) -> str:
    """Fantacalcio-Online's round page: its title naming the round, the match tabs, one tab pane per match."""
    tabs = "".join(
        f'<li class="nav-item"><a class="prb-partita nav-link" href="#lineup-{i}">{m.home} - {m.away}</a>'
        "</li>"
        for i, m in enumerate(matches)
    )
    panes = "".join(
        f'<div class="tab-pane" id="lineup-{i}">{_fco_header(m)}{_fco_summary(m)}'
        f'<div class="prb-squadre">{_fco_team(m.home, "home", m)}{_fco_team(m.away, "away", m)}</div></div>'
        for i, m in enumerate(matches)
    )
    title = f"<title>Probabili Formazioni Serie A 2026/2027 - {round}ª Giornata</title>" if round else ""
    return (
        f"<html><head>{title}</head><body>"
        f'<ul class="nav">{tabs}</ul><div class="tab-content">{panes}</div></body></html>'
    )
