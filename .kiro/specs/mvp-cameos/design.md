# Design Document: `mvp-cameos` (after Phase 2, before Phase 3)

Status: **Approved by the owner, 2026-11-24**, with its open point ("Approve, start task 1") · From the approved [requirements](requirements.md) (2026-11-24, both
recommendations)

## Overview

Two shares instead of one. A player's chance of a cameo is formed where his availability is worked out, and a share for
his kind of cameo is passed in there, so every answer, card, alert, review and calibration set uses it without the engine
changing. The recalibration fits the two shares apart, checks each where it wasn't fitted, and lists each on its own;
`CAMEO_RATED` keeps the method's 60% and leaves the proposal. Until the owner approves a value, both shares are 0.5 and
every answer is what it was.

## What it builds on

- **Where the chance of a cameo is formed** (`domains/availability/consensus.py`): `combine` gives an available player
  `CAMEO_SHARE × (1 − p_start)`, and a player on an official bench `CAMEO_SHARE`. `availability()` in
  `domains/availability/gold.py` calls it, from `Advisor.gather` (twice) and from `mcp/calibrate.py`; a lineup without
  any outlet's view uses `_assumed` in `mcp/tools/lineup.py`.
- **Where his kind is known** (`engine/outfield.py`): `priors(role, mantra_role).priced_cameo`. The engine multiplies the
  chance of coming on by the chance of a rating once on: 1 for a flat cameo, `cameo_rating(...)` for a priced one.
- **The fit** (`domains/recalibration.py`, `engine/recalibrate.py`): `cameo_rates` fits `CAMEO_SHARE` from the benched
  players with a flat cameo, then tries `CAMEO_RATED`; `rerated` and `check_cameos` check them together, against one
  minimum of 200. Each calibration set row keeps `priced_cameo` and `p_scores_cameo`, which is all the new fit needs.

## Components

### C1. A share for each kind (`engine/constants.py`, `engine/outfield.py`; R1.1, R1.3)

- `CAMEO_SHARE_PRICED = 0.5` beside `CAMEO_SHARE`, each with a comment saying what it counts.
- `cameo_share(role, mantra_role) -> float` in `engine/outfield.py`, next to `priors`: the priced share when
  `priors(...).priced_cameo`, else the flat one. It reads both constants from `engine/constants.py` when it's called, so
  that a test can set them in one place.

### C2. The share passed where the chance is formed (`consensus.py`, `availability/gold.py`, callers; R1.1, R1.2)

- `combine(outlets, official, *, share=CAMEO_SHARE)` and `availability(..., share=CAMEO_SHARE)`: the share replaces the
  constant in both formulas, and the official bench gets the share itself.
- The callers that price a player pass `cameo_share(role, mantra_role)` from his season row: `Advisor.gather` for the
  player it prices, `_assumed`, and `mcp/calibrate.py` for the calibration sets. A penalty taker's chance of starting
  (`Advisor._p_start`) doesn't use the chance of a cameo, so it keeps the default.
- The default keeps every existing caller and test as it is. With both shares at 0.5 nothing differs, byte for byte.

### C3. Both shares fitted (`engine/recalibrate.py`, `domains/recalibration.py`; R1.4, R2.1, R2.2)

- `cameo_share(rated)` as today, for the flat kind.
- `cameo_share_priced(forwards)`: for each benched player with a priced cameo, his chance of a rating once on is
  `k = g + (1 − g) × CAMEO_RATED`, with `g` his chance of scoring once on. The share is the ratings that happened over
  the sum of `k`, and its 90% interval is the rated proportion's interval scaled the same way. None without evidence, or
  outside 0 to 1, with the reason.
- `cameo_rates` returns both shares, each with its own `missing` reason. `cameo_rated` goes, and `CAMEO_RATED` is listed
  under what waits: "held at the method's 60% (`mvp-cameos` R1.4)".

### C4. Each share checked on its own (`domains/recalibration.py`; R2.3, R2.4)

- `rerated(row, rating, flat, priced)`: a row's chance of a rating with the new shares. Its cameo part scales by
  `priced / CAMEO_SHARE_PRICED` when its cameo is priced, else by `flat / CAMEO_SHARE`; nothing else changes.
- `check_cameos` becomes two checks, `CAMEO_SHARE` and `CAMEO_SHARE_PRICED`. Each is fitted without each round or half,
  scored on the held-out rows of its kind only, and decided against its own minimum: 200 benched players of its kind
  (`MINIMUM_SAMPLE["cameos"]`, now per kind).
- `_TODAY` and `_EVIDENCE` name the two shares: "players with a flat cameo who didn't start and could have come on",
  and the same with a priced cameo.

### C5. The proposal and an approved share (`cli`, `docs/calibration-log.md`, `tests/conftest.py`; R3)

- `fantadamus recalibrate` needs no change of its own: it prints and keeps whatever the checks give, now two shares.
- An approved share lands as `mvp-recalibrate`'s did: the constant in `engine/constants.py`, an entry in the calibration
  log, and the `start_values` fixture setting it back to 0.5 for the tests worked out by hand.
- What it moves: round 12's stored facts at its lock, replayed with the approved value, the owner's lineup and the
  round's ten cards, counts and averages only, as `tests/acceptance/recalibrate/test_moves.py` does for the starting map.

### C6. The docs (R4.2)

Method §A4 gives both shares and what each counts. The calibration log gets its entry with each approved value, and the
constants' comments say what each share means.

## Error handling

- A share the evidence can't give (none benched of its kind, or a value outside 0 to 1) isn't proposed, with the reason,
  as today.
- A calibration set row without `priced_cameo` (written before `mvp-recalibrate`) counts toward neither share.

## Correctness properties

| # | Property | Requirement |
|---|---|---|
| P1 | For any chance of starting and either kind, the chance of a cameo is the kind's share × (1 − p_start), and the share alone on an official bench | R1.1 |
| P2 | With both shares equal, every chance formed equals today's for any outlets and official lineup | R1.3 |
| P3 | `rerated` with today's shares gives back each row's chance; a row of one kind doesn't move when only the other kind's share changes | R2.3 |
| P4 | The priced share fitted on rows made with a known share gives that share back, within its interval | R2.2 |

## Testing strategy

- **Unit, by hand:** `cameo_share(role, mantra_role)` for each role; `combine` with a share; both fits on invented sets
  (AT-3); the per-kind checks and their minimums (AT-4).
- **Property:** P1 to P4, in `tests/property/cameos/`, pure.
- **Acceptance:** AT-1 (a flat and a priced cameo by hand, before and after a share changes, through `best_lineup`); AT-2
  (`python -m tests.real_lake --compare`, on a copy of the owner's lake, every answer identical with both shares at 0.5);
  AT-5 (the proposal from stored facts); AT-7 (what an approved share moves on round 12).
- **Earlier tests that change with R1.4:** in `mvp-recalibrate`, the AT-3 tests of the cameo rates
  (`tests/acceptance/recalibrate/test_rates.py`: `CAMEO_RATED` fitted, "one share doesn't fit both") and the AT-6 tests
  of the cameo check (`test_checks.py`: the check named "CAMEO_SHARE and CAMEO_RATED", the fitted cameo rating checked),
  with their unit and property tests. They test the fit that R1.4 replaces, so they become tests of the two shares; no
  number moves. Found in task 1: AT-5's test of what waits (`test_checks.py::test_at5_what_waits`) lists every
  constant, so `CAMEO_SHARE_PRICED` waits there until task 2 fits it, and `CAMEO_RATED` joins it in task 2
  (accepted by the owner on 2026-11-24). Found in task 2: AT-8's tests of the proposal
  (`test_proposal.py::test_at8_the_proposal`, `::test_at8_the_proposal_in_words`) name the retired fit's "not
  counted" line and the cameo evidence, so they name the two shares' instead.
- **Mutation:** `make mutate ONLY=…` on the new and changed functions in `engine/recalibrate.py`,
  `domains/recalibration.py` and `engine/outfield.py`.

## Cost

$0: no dependency, service or account, and no page read. A proposal takes about two seconds, as today.

## Build order (input to tasks.md)

1. The share by kind (C1, C2): no number moves; AT-1, AT-2, P1, P2.
2. Both shares fitted and checked (C3, C4): AT-3, AT-4, P3, P4.
3. The real proposal on the rounds scored, and the owner's approval of each share (C5): AT-5, AT-6.
4. The approved value, what it moves, the docs, a mutation run and the slice report (C5, C6): AT-7, AT-8.

## Open points for the owner

One, approved with the design on 2026-11-24: approving this design also approves changing `mvp-recalibrate`'s AT-3 and AT-6 cameo tests, as listed under
"Testing strategy". They test the `CAMEO_RATED` fit that R1.4 retires. The two decisions were taken with the requirements.
