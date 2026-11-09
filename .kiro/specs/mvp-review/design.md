# Design Document: `mvp-review` (Phase 2, fifth slice)

Status: **Approved by the owner, 2026-11-09** · From the approved [requirements](requirements.md)

## Overview

A review answers one question after a round: were my choices good? It takes what the user fielded, the advice they were given,
and what really happened, and it judges each difference by what it was expected to cost when it was made (method §A8).

Nothing here changes a number Fantadamus forecasts. The review reads three things a round already leaves behind (the decision
log, the statistics page read before and after the round, and the official lineups) and one thing only the user knows: what they
fielded. It reuses the engine for the arithmetic: the league's substitutions, its formula rules and its thresholds work the same
on real ratings as on simulated ones, and an expected cost is priced the way an override already is.

## What it builds on

- `domains/calibration.py`: the round's frame, the statistics reads that bracket a round (`statistics_reads`), the last advice
  logged before a lock, and each club's official sheet.
- `engine/simulate.py`: `plan` and `field` apply the league's substitutions to one round's scores; `simulate` prices
  arrangements over the same simulated rounds; `fantasy_goals` turns a score into fantasy goals.
- `engine/formula.py`: `formula_points` works out a formula rule, and the captain, on a round's marks.
- `mcp/tools/lineup.py`: pricing the squad at an `as_of`, building arrangements, and an override's cost.
- `lake/decision_log.py`: every lineup answer, with its starters, bench, formation, captain and vice.
- `league/squads.py`: private per-user storage, with a league-mate's team kept apart.

## Components

### C1. Three more columns (`contracts/xy/season.py`, `web/readers/fcit_stats.py`, `domains/season/silver.py`; R2.1, R5.3)

The statistics page already read daily has three columns Fantadamus doesn't read: FM (the fantasy average), RP (penalties saved)
and Esp (red cards). `PlayerSeason` gains `fantasy_average`, `penalties_saved` and `red_cards`, each optional so that rows
stored before stay valid, which makes `SeasonStatsPayload` 1.1.0 and `PlayerSeasonPayload` 1.2.0: minor versions. The reader reads them, the silver row keeps them, and the source registry's reading
list names them. It's the same page and the same route (ADR-0006), so no ADR is needed.

### C2. One round from two reads (`domains/review.py`; R2.1, R2.3)

Pure. `player_round(before, after)` returns what one player did in the round, or why that isn't known:

1. **Rated or not.** Rated games went up by one: he got a rating. By none: he didn't. By more: two matches between the reads, so
   nothing is known.
2. **The rating.** The difference of the two totals (average × rated games) is his rating, give or take the averages' rounding:
   at most 0.005 × each read's rated games. Ratings fall on half points, so if one half point lies within that, it's the
   rating. While it's ambiguous (late in the season), FM gives a second reading: its difference less Fantacalcio.it's standard
   bonuses for the events below. A half point both readings allow is the rating; otherwise the rating isn't known.
3. **The events:** the differences in goals, assists, penalties scored and taken (a miss is one taken and not scored), yellow
   and red cards, saved penalties and goals conceded. A count that went down means the page corrected itself, and nothing is
   known.
4. **An own goal** has no column. Where the rating is pinned by the averages and FM is two points short of it, that's an own
   goal; otherwise own goals are named as not counted.

A player missing from either read, or with no read on one side, is unknown with that reason.

### C3. The real score (`domains/review.py`; R2.2)

Pure. `real_score(rounds, plan, rules)` scores one arrangement the way the league does:

- each rated player's points: his rating, plus his events at the league's table for his role (`scoring_for`). A clean sheet is
  zero goals conceded with a rating, where the table scores it for his role. A decisive goal and a set-piece assist have no
  column, so they're named as not counted where the league scores them;
- the league's substitutions, by `field` on those points, with None for a player without a rating;
- the league's formula rules on the real marks: the pure vote is the rating, and "scored or conceded" is read from the events.
  The captain's points come from the captain's rating, or the vice's when he has none, or the stand-in vote;
- the thresholds, by `fantasy_goals`.

An unknown player can't be scored. If one is in an arrangement's eleven or comes into play, its real score is unknown, and the
review says which players made it so.

### C4. What the user fielded (`league/fielded.py`, `mcp/tools/review.py`; R1)

`FieldedStore` keeps, privately beside the squads, one fielded lineup per user, team and round: the formation, the starters,
the bench in order, the captain and the vice, and whether it was "as advised". Names resolve against the squad as an override's
do, with `choose` for an ambiguous one and `refused` for one not in the squad. A lineup the league couldn't field (a formation
it doesn't allow, too many players, a bench longer than the league's) is refused with the reason. Saving again replaces.

### C5. The advice (`mcp/tools/review.py`; R3.4, R3.5)

The advice is the last lineup answer logged for that user and team before the round's lock, read from the decision log. If there
is none, the review replays `best_lineup` at the lock (its `as_of`, which doesn't log) and marks the advice as replayed.

### C6. Each decision and what it cost (`domains/review.py`, `mcp/tools/review.py`; R3.1 to R3.3)

`decisions(advice, fielded, real)` lists the differences, in this order:

- **a player in another's place:** the fielded-only and advised-only players of each role, paired best key first;
- **the formation,** when the lines differ: the players left over once each role is paired;
- **the bench order,** only for a role whose first substitute really came on, when the user's order put someone else first;
- **the captain or the vice,** when they differ.

**Expected cost.** Each decision is priced on its own: the advice, and the advice with only that decision applied, over the same
simulated rounds at the lock's facts (`simulate` on arrangements built from the lists, with the league's formula rules). So is the
fielded lineup as a whole, against the advice, which gives the total. All arrangements share one simulation, so a review costs
one simulation of a few arrangements. It never uses a fact stored after the lock.

**Real result.** The same pairs, scored by C3: the advice with only that decision applied, less the advice. A decision whose
players can't be scored says so.

The decisions' parts needn't add up to the total, because substitutions and modifiers link players. The total is given too, and
the answer says so when the parts don't add up.

### C7. The record (`lake/review_log.py`; R4)

Each review is appended, privately, to a JSON-lines log like the decision log: the round, team, as-of time, the snapshots used
(content hashes), the advice's and the fielded lineup's expected and real scores, and each decision's expected cost and real
result. A later review of the same round and team supersedes the earlier one when the record adds up; nothing is deleted.

The record for a user and team: rounds reviewed, overrides, their total expected cost and their total real gain. It also says
how much the gain can tell: the per-round gains' spread gives a margin of about two standard errors. Until the gain is outside
that margin, the record says it's still mostly luck. With fewer than three rounds it says it's too early.

### C8. The answer and the docs (`mcp/tools/review.py`, `docs/`; R2.4, R5)

`review_round(round, team, as_advised, starters, bench, formation, captain, vice, app_total, as_of)` stores what's given and
returns a `ReviewResult`:

| Status | When |
|---|---|
| `fielded` | Nothing stored for that round and team: ask what they fielded, or whether it was as advised |
| `choose` / `refused` | A name to settle, or a lineup the league couldn't field |
| `not_ready` | The round hasn't finished, or no statistics read after it is stored yet: it says when to ask again |
| `review` | The review |

The review: the real score and fantasy goals against the expected ones and their range (inside eight rounds out of ten, below
or above); the user's app total beside it if given, flagged when they differ by more than half a point; each decision with its
expected cost and real result; the advice's real score; the record; and what couldn't be counted, by name. Before it answers,
the review asks the collector for a statistics read if none is stored after the round, as the calibration does.

`docs/answer-formats.md` gains format 7, the review. The agent prompt gains one section, within its budget; the player guide and
method §A8 say how a review reads.

## Error handling

| Condition | Behaviour |
|---|---|
| No statistics read after the round | `not_ready`, after one try to read the page |
| Two matches between the reads, a count that went down, a rating on no half point | That player is unknown, with the reason |
| An unknown player in an eleven, or coming on | That lineup's real score is unknown, with who made it so; expected costs still given |
| No advice before the lock | The advice is replayed at the lock and marked so |
| A fielded lineup the league couldn't field | `refused`, with the reason; nothing stored |
| The user's app total differs by more than half a point | Shown, with the likely causes: a substitution the app made differently, an own goal, a late correction |

## Correctness properties

These Hypothesis tests are required:

| # | Property | Requirements |
|---|---|---|
| P1 | From any two reads made of a real round, with any averages' rounding up to 24 rated games, the rating found is the real one | R2.1 |
| P2 | A round is never invented: a rated-games difference other than 0 or 1, or a count that went down, always gives "unknown" | R2.3 |
| P3 | Following the advice gives no decision and a real gain of zero | R3.1, R3.4 |
| P4 | A decision's expected cost is the same however the decisions are ordered, and the fielded lineup's total cost is the same whichever way it's priced | R3.2 |
| P5 | Appending a review never changes an earlier line, and the record of the same reviews is the same whatever their order | R4.1, R4.2 |

## Testing strategy

- **Unit, in `tests/unit/review/`:** C2 and C3 by hand, on invented reads and invented squads.
- **Property, in `tests/property/review/`:** P1 to P5.
- **Contract:** the statistics reader against a synthetic page with the three new columns.
- **Integration, in `tests/integration/review/`:** the tool end to end on the invented round of `tests/lineup_harness.py`, with
  reads before and after it.
- **Acceptance, in `tests/acceptance/review/`:** AT-1 to AT-7 automated, AT-8 by hand.

Squads, reads and fielded lineups in tests are invented. A real lineup or review never reaches the repository.

## Cost

$0. No new page, no paid service and nothing on AWS. A review is one simulation of a few arrangements and two reads of the lake,
inside the lineup's budget.

## Build order (input to tasks.md)

1. **The three columns:** contract, reader, silver, the reading list.
2. **One round from two reads:** pure, with its properties.
3. **The real score:** pure, on the engine's `field` and `formula_points`.
4. **The fielded lineup and the advice:** the store, names, "as advised", the replay at the lock.
5. **Decisions and their costs:** the shared simulation at the lock, and each real result.
6. **The record:** the log and the running totals.
7. **The answer and the docs:** the tool, format 7, the prompt, the guide, the method.
8. **A real check and sign-off:** the owner's round reviewed against their league's app (AT-8).

## Open points for the owner

Approved with the design on 2026-11-09.

1. **Round 11 can be reviewed only in part.** Its reads were stored before the three new columns, so red cards, saved
   penalties and own goals can't be counted for it, and late ratings can't use FM. Recommendation, approved: build on round 11's reads, and
   take AT-8 on round 12, the first round read with all the columns.
