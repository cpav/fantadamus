# Design Document: `mvp-recalibrate` (Phase 2, seventh slice)

Status: **Approved by the owner, 2026-11-11**, with both open points · From the approved [requirements](requirements.md)

## Overview

The calibration already scores every player's chances after a round (`mcp/calibrate.py`, the "model on everyone"). This slice
keeps what it scores, player by player, so that a later fit can use it. On the rounds kept, it fits three things: a map for the
chance of starting, the cameo rates, and the rates the season counts itself. It checks each one where it wasn't fitted, and
proposes the changes that help, with their evidence. Nothing changes a number until the owner approves a proposal and it
lands as a pull request to `engine/constants.py`, which the constants module says is calibration's to change.

The fitting is pure and runs on stored evidence only: no page is read.

## What it builds on

- `mcp/calibrate.py`: `Calibrator.score` runs the model on every player the round page lists, at the facts held before his
  kickoff, against what happened.
- `domains/calibration.py`: `Tally`, `add_outcomes`, `outcome_of` and `scored_chance` (the Brier score and the buckets).
- `domains/availability/consensus.py`: `combine` forms the chance of starting from the outlets' views. An official lineup
  replaces it.
- `engine/outfield.py` and `engine/keepers.py`: a cameo's chance of a rating is `CAMEO_SHARE × (1 − p_start)` for a defender
  or a midfielder. An attacker's is that times his cameo's chance of a rating (`CAMEO_RATED`, or 1 if he scores).
- `domains/review.py`: the team's goals against in a round, from its keepers' rows in two statistics reads.
- `domains/odds/gold.py`: `team_xg`, the match's chances from the odds.

## Components

### C1. Calibration sets (`domains/calibration.py`, `lake/calibration_store.py`; R1)

`Tally` keeps, besides its pairs, one `SetRow` per player it scores:

- the round, the club, the role and the match;
- the **raw** consensus of the outlets, before any map;
- each chance the model gave: starting, a rating, scoring and a clean sheet;
- what happened: started, rated, scored, and a clean sheet, or the reason it isn't known;
- whether his cameo is priced as an attacker's, by his first Mantra role, or flat *(added in task 4)*.

`Calibrator.score` stores the model set's rows with the round's report, as `round-<n>.set.json` beside `round-<n>.json` in the
private calibration folder. The report itself is unchanged. `fantadamus calibrate --round <n> --again` rebuilds both, the same
way every time.

**What can be seen.** The statistics page counts rated games only, so a substitute who came on without a rating can't be told
from one who didn't come on. A set therefore records "rated without starting", not "came on". R1.1 and R3.1 say so (open point 1,
approved).

### C2. The starting map (`engine/recalibrate.py`, pure; R2.1)

`fit_start_map(rows) -> StartMap` works on (raw consensus, started) pairs:

1. Group them into the ten buckets the report uses.
2. Shrink each bucket's rate toward its own mean raw chance, with a prior weight of `START_MAP_WEIGHT` players
   *(start)*: 20. A bucket with five players moves a fifth of the way; one with a hundred, most of it.
3. Make the shrunk rates monotone by pooling adjacent violators (isotonic regression), each bucket weighing its
   players plus the prior's 20. Shrinking first keeps the map monotone: shrunk after pooling, a thin bucket can
   fall below a heavy one before it. Pooling never moves a bucket further from no change than shrinking did.
4. The map is the piecewise-linear line through (0, 0), each bucket's (mean raw, fitted rate), and (1, 1).
   *(Order corrected in task 2, 2026-11-12.)*

`START_MAP` in `engine/constants.py` holds the knots. Until a proposal is approved it's the identity, so this slice's code
changes no number on its own.

### C3. The map applied (`domains/availability/consensus.py`; R2.2)

`combine` applies `START_MAP` to the consensus before it becomes `p_start`, and the cameo follows from the mapped chance. An
official lineup still replaces both. `combine` also keeps the raw consensus on `Availability` (`raw_p_start`), so that a
calibration set records it and a later fit doesn't compound on the map.

### C4. Cameo rates (`engine/recalibrate.py`, pure; the rows picked in `domains/recalibration.py`; R3)

From the rows of players who didn't start, whose rating is known, and to whom the model gave a chance of coming on:

- **`CAMEO_SHARE`**, from the defenders and midfielders whose cameo is flat: how often they got a rating. In the model, a player who doesn't
  start gets a rated cameo `CAMEO_SHARE` of the time whatever his chance of starting, so this doesn't lean on that chance
  being calibrated.
- **`CAMEO_RATED`**, from those whose cameo is priced (forwards and attacking midfielders), with that share: such a cameo
  is rated if he scores, or `CAMEO_RATED` of the time if not, so it's solved from how often they got a rating and their mean
  chance of scoring as a cameo.

Each comes with its count and a 90% interval (Wilson's). *(Corrected in task 3, 2026-11-12: the share was the rated cameos
over the sum of `1 − p_start`, which a miscalibrated chance of starting would bias.)*

### C5. Season rates (`domains/recalibration.py`, counted with `engine/recalibrate.py`; R4)

From the latest statistics read and the table, league-wide:

| Constant | Count |
|---|---|
| `PENALTY_RATE` | penalties taken over team matches played |
| `PENALTY_CONVERSION` | penalties scored over taken |
| `PENALTY_SAVED_SHARE` | penalties saved over missed (taken − scored) |
| `YELLOW_PRIOR` | yellow cards over appearances, outfield players, as the model applies it |
| `RED_RATE` | red cards over rated games, by role |

Each comes with its count and a 90% interval. These are counts, not predictions. They get no held-out Brier score (C6), and
the proposal keeps them in a section of their own (open point 2, approved).

### C6. Held-out checks and minimum samples (`domains/recalibration.py`, pure; R5, R6)

- **The folds:** each round held out in turn; with one round, each half of its matches, alternating in the set's order.
  *(Corrected in task 4: alternating by kickoff needs a kickoff the set doesn't keep, and any split that ignores the
  outcomes does.)*
- **Starting:** fit the map without the held-out part, then score that part's raw chances through today's map and through
  the fitted one, by Brier score and reliability. With two rounds, that's two checks, and the map is proposed only if both
  improve.
- **Cameos:** the same folds. Every known chance of a rating in the held-out part is scored as it was and with the fitted
  rates: a cameo's part of the chance scales with the share and, if it's priced, with `CAMEO_RATED`.
- **Minimum samples** *(start)*, in `MINIMUM_SAMPLE`, below which a value isn't proposed:
  - starting: 300 players;
  - cameos: 200 non-starters;
  - penalties: 30;
  - cards: 300 rated games a role;
  - scoring shares: 500 started players;
  - clean sheets: 100 keepers.
- **What waits:** every *(start)* constant this slice doesn't fit is listed with the evidence it needs and how much there is.
  That includes the scoring shares, clean sheets, vote noise and the keeper's β.

### C7. The market's chances beside ours (`domains/calibration.py`, `mcp/calibrate.py`; R7)

For each match, from the odds held before its kickoff (`team_xg`), the chances as its card shows them (`match_numbers`):

- a home win, a draw and an away win;
- three goals or more and both teams to score, where the odds priced them;
- each side's clean sheet.

A match priced from team form, with no odds, isn't the market and is named instead. The score comes from each side's goals
against, read from its keepers' rows in the two statistics reads, as the review reads them (`domains/review.py`'s
`goals_against`, shared with it); a match without either club's official lineup wasn't played. The chances go in a third
set of the round's report, `market`, beside `told` and `model`. Old reports without it stay valid.

### C8. The proposal (`cli/__main__.py`, `domains/recalibration.py`; R8)

`fantadamus recalibrate [--rounds 10 11]` reads the stored sets (every round's by default), the latest statistics read and
the table. It reads no page. It prints a proposal:

- each fitted value with today's and the fitted one, its evidence and count against its minimum, and each held-out check's
  Brier score and reliability gap before and after (the gap: how far each bucket's mean chance is from how often it
  happened, weighted by its players; the buckets themselves are in the kept proposal);
- the season's rates, in their own section, each with its 90% interval;
- what couldn't be counted, and why;
- what waits, with the evidence it needs and how much there is.

It keeps the full proposal, privately, as `proposal.json` beside the sets. It never touches `engine/constants.py`.

### C9. An approved change (`engine/constants.py`, `docs/calibration-log.md`, `docs/method.md`; R8.2, R8.3, R9, R10)

The owner approves the values one by one. The approved ones land as one pull request:

- the new values in `engine/constants.py`;
- an entry in `docs/calibration-log.md` with the date, the rounds, each value's old and new value, its evidence and its
  held-out effect, as aggregates only;
- `docs/method.md` with the *(start)* mark replaced by the date.

The pull request shows what the change moves on round 11's facts at its lock: the lineup, its expected score and thresholds,
and the cards' chances, before and after, in general terms. A later proposal reverts a value the same way.

**Replays.** A replay at an earlier `as_of` uses today's constants, so after a change it no longer reproduces what was told
then. The decision log keeps what was told, and the calibration scores the log. A review works its expected costs out at
the lock on today's constants; `docs/method.md` §A8 and the player guide say so.

## Error handling

| Condition | Behaviour |
|---|---|
| A round without a stored set | `recalibrate` names it, and fits on the rest |
| Fewer rounds than a leave-one-out check needs | The split by matches, said so |
| A value below its minimum sample | Not proposed; listed with the evidence it needs |
| A held-out Brier score that doesn't improve | Not proposed; listed with its effect |
| A statistics read without the newer columns | The rates it can't count are named |

## Correctness properties

These Hypothesis tests are required:

| # | Property | Requirements |
|---|---|---|
| P1 | A fitted map is monotone, maps [0, 1] into [0, 1], and passes through (0, 0) and (1, 1) | R2.1 |
| P2 | With no evidence, or only thin buckets, the map stays within the shrinkage's reach of the identity; with none at all it is the identity | R2.1, R5.2 |
| P3 | A change whose held-out Brier score doesn't improve is never proposed | R6.2 |
| P4 | A round's calibration set is the same whatever order its facts were stored in, and rebuilding it gives the same set | R1.3 |
| P5 | Every estimated rate lies in its interval and within [0, 1] | R3.1, R4.1 |

## Testing strategy

- **Unit, in `tests/unit/recalibrate/`:** C2 to C6 by hand, on invented rows and reads.
- **Property, in `tests/property/recalibrate/`:** P1 to P5.
- **Integration, in `tests/integration/recalibrate/`:** a set stored and rebuilt, the map applied in `combine`, the market set,
  and the command, on the invented rounds of `tests/lineup_harness.py`.
- **Acceptance, in `tests/acceptance/recalibrate/`:** AT-1 to AT-9 automated, AT-10 by hand.

Rows, reads and rounds in tests are invented. A real set or proposal never reaches the repository.

## Cost

$0. No page is read and nothing runs on AWS. A fit runs on a few thousand stored rows.

## Build order (input to tasks.md)

1. **Calibration sets:** kept with each round's report, and rebuilt the same way. This spec becomes the current one.
2. **The starting map:** the fit, and `combine` applying it, as the identity until approved.
3. **Cameos and the season's rates.**
4. **Held-out checks and minimum samples.**
5. **The market's chances beside ours.**
6. **The proposal command.**
7. **The real proposal and the approved change:** on rounds 10 and 11, the owner's AT-10, then the change, the log, the method,
   and what it moves.
8. **A real check and sign-off:** a mutation run and the slice report.

## Open points for the owner

Both approved on 2026-11-11, and the requirements amended.

1. **"Came on" can't be seen.** The statistics page counts rated games only. Recommendation: amend R1.1 and R3.1 to "rated
   without starting", and estimate `CAMEO_SHARE` from defenders and midfielders and `CAMEO_RATED` from forwards (C4).
2. **Season rates get no held-out Brier score.** They're counts, not predictions. Recommendation: amend R6.1 to fitted values,
   and give each rate its count and a 90% interval instead (C5).
