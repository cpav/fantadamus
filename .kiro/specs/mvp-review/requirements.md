# Requirements Document: `mvp-review` (Phase 2, fifth slice)

Status: **Approved by the owner, 2026-11-09**, with all three recommendations · Workflow: requirements-first · Depends on: `mvp-rules` (signed off
2026-11-09) · Abbreviation: `rv` · Method: [`docs/method.md`](../../../docs/method.md) §A7, §A8 · Answers:
[`docs/answer-formats.md`](../../../docs/answer-formats.md), a new format

## Introduction

After a round, a player wants to know whether their choices were good: what they fielded, what Fantadamus advised, what each
difference cost, and whether going against the advice pays off over a season.

The method audits decisions, not results (§A8). A choice is judged by what it was expected to cost when it was made, at the facts
known before the lock. What really happened is shown next to it, never in its place, because one round is mostly luck: a
coin-flip choice that came off isn't a good decision, and a sound one that didn't isn't a bad one.

This slice changes no numbers, so it can start before the next round has been answered (`product.md`'s rule). It reads what a
round already leaves behind, and asks the user only for what they really fielded.

**Not in this spec:**

- recalibrating the *(start)* constants: the next slice, which can use these reviews;
- live scores during a match: out of scope (`product.md`, Further notes);
- the result of a head-to-head match, which needs the opponent's team: the slice for rules that need the opponent;
- per-match ratings from another source, such as newspapers' *pagelle*: the new-sources slice;
- trades, auctions and market values (out of scope for v1).

## Glossary

| Term | Meaning |
|---|---|
| Fielded lineup | What the user really fielded for a round: the eleven, the bench in order and, where the league has one, the captain and vice |
| Advice | The last lineup `best_lineup` gave the user for that team before the round's lock, as the decision log holds it |
| Decision | One difference between the fielded lineup and the advice: a player started in another's place, the formation, the bench order, the captain |
| Expected cost | What a decision was expected to give up, in points and in the chance of each threshold, over the same simulated rounds at the lock's facts: the price of an override (`mvp-lineup` R3.5) |
| Real score | What a lineup really scored under the league's rules: each player's real rating and events, the league's substitutions, its formula rules and its thresholds |
| Paid off | An override's real gain against its expected cost, added up over the rounds |

## What a round leaves behind

Read on 2026-11-09 from the code, the decision log and a recorded copy of the statistics page.

- **The decision log** holds every lineup answer: its as-of time, round, team, formation, starters, bench, expected score,
  threshold chances, an override's cost and the advised starters, what each formula rule added, and the captain and vice. The
  calibration code already finds the last one before a round's lock (`last_told`).
- **The statistics page** (Fantacalcio.it, read daily under ADR-0006) gives each player's season so far: rated games (PV), the
  average rating (MV) and the fantasy average (FM) to two decimals, goals, goals conceded, penalties scored and taken, penalties
  saved (RP), assists, yellow cards and red cards (Esp). Fantadamus reads all of them today except FM, RP and Esp.
- **One round from two reads.** A read after the round less one before it gives his round: whether he got a rating (PV went up
  by one), his rating, and his events. Ratings come in half points, so the difference of the two totals (MV × PV), rounded to the
  half point, is his rating exactly while the rounding of the two averages can't add up to a quarter point: up to about 24
  rated games. FM gives a second, independent reading of the same rating once the standard bonuses are taken off it, which
  settles the rest. The calibration code already finds the reads that bracket a round, and says when there are none.
- **The official lineups** on the round page say who started.
- **What a round doesn't leave behind:** what the user really fielded, which only they know; own goals, which no column counts;
  and anything a fantasy match needs about the opponent.

## Requirements

### Requirement 1: What the user fielded

**User Story:** As a player, I want to tell Fantadamus what I really fielded, in a sentence, so that it can review my round.

- **R1.1** WHEN a user says what they fielded for a round THE SYSTEM SHALL store it privately: the eleven, the bench in order and,
  where the league has a captain, the captain and the vice, with each name resolved against the squad as an override's is.
- **R1.2** WHEN the user says they followed the advice THE SYSTEM SHALL take the advice as what they fielded, and they need name no
  player.
- **R1.3** THE SYSTEM SHALL refuse a fielded lineup that the league's rules couldn't field, such as a formation it doesn't allow,
  with the reason, and store nothing.
- **R1.4** Saving it again for the same round and team SHALL replace it; a league-mate's team can be reviewed too, kept apart as
  its squad is.

### Requirement 2: The real score

**User Story:** As a player, I want the real points of what I fielded and of what was advised, worked out the way my league does.

- **R2.1** THE SYSTEM SHALL work out each player's round from the statistics page read before and after it: whether he got a
  rating, his rating, and his goals, assists, penalties, cards, saved penalties and goals conceded.
- **R2.2** THE SYSTEM SHALL score both the fielded lineup and the advice from those rounds as the league does: the table of
  events, the league's substitutions with the real ratings, the formula rules on the real pure votes, the captain and vice, and
  the thresholds.
- **R2.3** WHERE a round can't be worked out for a player THE SYSTEM SHALL say so and why, and SHALL leave his part out rather
  than guess: no read before or after, two matches between the reads, a rating that doesn't fall on a half point, or a player
  missing from a read. Own goals SHALL be named as not counted.
- **R2.4** A user MAY give their real total from their league's app. THE SYSTEM SHALL show it beside its own, and say so when they
  differ by more than half a point.

### Requirement 3: Each decision and what it cost

**User Story:** As a player, I want each of my choices against the advice, with what it was expected to cost and what it really
did.

- **R3.1** THE SYSTEM SHALL list each decision that differs from the advice: a player started in another's place, the formation,
  the bench order where it decided who came on, and the captain.
- **R3.2** FOR each decision THE SYSTEM SHALL give its expected cost, worked out over the same simulated rounds at the facts known
  before the lock, as an override is priced, and what it really gave: the real points of the one fielded less the one advised,
  after substitutions.
- **R3.3** THE SYSTEM SHALL judge a decision by its expected cost, and show the real result beside it as one round's outcome
  ("expected to cost 0.4; this round it gained 3").
- **R3.4** WHERE the user followed the advice THE SYSTEM SHALL say so, and show the real score against the expected one and its
  range: whether it fell inside eight rounds out of ten, below or above.
- **R3.5** WHERE the user asked for no lineup before the lock THE SYSTEM SHALL replay the advice at the lock from the facts stored
  by then, and say that it did.

### Requirement 4: Whether overrides pay off

**User Story:** As a player, I want to know, over the season, whether going against the advice has paid off.

- **R4.1** THE SYSTEM SHALL log each review, append-only and privately, with the snapshots it used.
- **R4.2** THE SYSTEM SHALL keep a running record for each user and team: the rounds reviewed, the overrides, their total expected
  cost and their total real gain.
- **R4.3** THE SYSTEM SHALL say how much a total can tell yet: over a few rounds the real gain is mostly luck, and the record says
  so rather than declare a winner.

### Requirement 5: The answer, the docs and the limits

**User Story:** As a player, I want the review in the same plain shape as the other answers, quickly.

- **R5.1** THE SYSTEM SHALL answer a review through a tool, in a format added to `docs/answer-formats.md`: the real score against
  the expected one, then each decision, then the record, then what it couldn't count.
- **R5.2** THE SYSTEM SHALL answer within `mvp-lineup`'s budget, 3 seconds and 15 KB.
- **R5.3** THE SYSTEM SHALL read no new page: only more columns (FM, RP and Esp) of the statistics page it already reads, under its
  approved route, and SHALL call no paid service.
- **R5.4** Fielded lineups and reviews SHALL stay in git-ignored private storage. Reports SHALL describe real rounds in general
  terms only.
- **R5.5** THE SYSTEM SHALL update the agent prompt, within its budget, the player guide and the method's §A8.

## Acceptance tests

| Test | What it proves | Requirements |
|---|---|---|
| AT-1 | A fielded lineup by name, "as advised", one the league couldn't field refused, and saving again replacing it | R1 |
| AT-2 | One round from two reads, by hand: a rating on the half point, events, a cameo without a rating, and each reason a round can't be worked out | R2.1, R2.3 |
| AT-3 | A real score by hand: a starter without a rating replaced by the league's rule, the table, a modifier and a captain on real votes, the thresholds | R2.2 |
| AT-4 | Each decision with its expected cost and its real result, by hand, judged by the cost | R3.1 to R3.3 |
| AT-5 | Following the advice: the real score against the expected one and its range; the advice replayed when none was asked | R3.4, R3.5 |
| AT-6 | The record over several rounds, append-only, saying when it's too early to tell | R4 |
| AT-7 | The review in its format, within 3 seconds and 15 KB, from no new page | R5 |
| AT-8 | Manual: the owner's real round reviewed, and its real score checked against the league's app | R2.4, R5.1 |

## Review of these requirements

An Analyze-Requirements pass, before design.

- **A rating late in the season.** The two-read difference is exact up to about 24 rated games; after that, FM's second reading
  has to settle it. Where both readings leave two half points possible, R2.3 leaves the player out. Design should measure how
  often that happens on real reads.
- **Two matches between reads.** A midweek round squeezed between two reads would mix two matches. The round frame already detects
  it; the review must refuse rather than split.
- **A league's app may substitute differently.** Rules on a substitute's rating, a player sent off before getting a rating, or a
  late kickoff can differ from the model's reading. R2.4's cross-check is how a user notices.
- **Expected cost needs the lock's facts.** Pricing a fielded lineup replays `best_lineup` at the lock (its `as_of`), so the facts
  stored after the lock are never used. That's the existing replay, so no new path is needed.
- **The bench as a decision.** A bench order only matters when a substitute came on. R3.1 limits it to those rounds, so a review
  doesn't list orders that changed nothing.
- **Not every league scores like Classic.** The real score uses the league's table and formula rules, as the forecasts do, so a
  custom rule is reviewed the same way it was priced.
- **Privacy.** A fielded lineup says what a named team did. It stays with the squads, in private storage, and never reaches the
  repository or a report.

## Owner decisions

- **2026-11-09:** the owner chose the lineup review as the next slice, ahead of recalibration, which waits for a round answered on
  `mvp-rules`' numbers.
- **2026-11-09, these requirements approved,** with the three recommendations below ("Approve all three").

1. **Where real scores come from.** Recommendation, approved: worked out from the statistics page read before and after each round, as
   above, with the user's own total from their league's app as an optional check. The alternatives are the user typing every
   player's rating, which is slow, or a ratings source with its own route, which belongs to the new-sources slice.
2. **Which advice to compare with.** Recommendation, approved: the last advice the user saw before the lock; and if they asked for none,
   the advice replayed at the lock (R3.5), clearly marked.
3. **How "paid off" is judged.** Recommendation, approved: by expected cost, with the real result beside it and a running total that says
   how much it can tell yet (R3.3, R4.3). Judging by real results alone would reward luck.
