# Requirements Document: `mvp-recalibrate` (Phase 2, seventh slice)

Status: **Approved by the owner, 2026-11-11**, with all three recommendations · Workflow: requirements-first · Depends on: `mvp-cards` (signed off
2026-11-11) · Abbreviation: `rc` · Method: [`docs/method.md`](../../../docs/method.md) §A2 to §A8

## Introduction

The method's numbers marked *(start)* were starting values: reasoned guesses, to be calibrated from logged predictions (§A8).
Two scored rounds now show where some of them are off. This slice turns the calibration into evidence-backed changes:

- each change is fitted on rounds and checked on a round it wasn't fitted on;
- the owner approves each change before it lands, and it's logged;
- a value without enough evidence yet stays as it is, and the report says how far it is from enough.

Unlike the last three slices, this one changes the numbers. `product.md`'s rule would make it wait for a round answered on
`mvp-rules`' numbers; the owner chose to start it on the rounds already scored (2026-11-11).

**Not in this spec:**

- the market's player-level chances, such as anytime-scorer odds: they need a new source, in the new-sources slice;
- raters' bias, per-match ratings and pundits;
- changing a value automatically: every change is proposed, then approved;
- trades, auctions and market values (out of scope for v1).

## Glossary

| Term | Meaning |
|---|---|
| *(start)* constant | A value in `engine/constants.py` the method marks as a starting guess |
| Calibration set | For one scored round, each player's published chance and what happened, by kind of chance: starting, getting a rating, scoring if he started, a clean sheet if he started |
| Held-out check | A change fitted without one round (or one set of matches) and scored on it |
| Reliability | How far each probability bucket's average chance is from how often it happened |
| Calibration map | A monotone function from a raw chance to a calibrated one |

## What the evidence says

Read on 2026-11-11 from the stored calibration reports of rounds 10 and 11, as aggregates. The model's chances were scored on
every player the round page lists, at the facts held before his kickoff.

| Chance | Evidence | What it shows |
|---|---|---|
| Starting | 1,033 players over rounds 10 and 11 | Overstated from 10% to 30% in both rounds: said 17%, 25%, 33%; happened 3–4%, 4–7%, 11–25%. At 40%, 44% said, and 24% happened in round 11, 46% in round 10. Right at the top: said 91–92%, happened 92–93% |
| Getting a rating | 538 players, round 11 | The 60–70% bucket said 64%, and 34% happened, over 98 players: the chance of a cameo with a rating looks too high |
| Scoring, if he started | 196 players, round 11 | Close to the buckets, but no better than guessing the average yet |
| Clean sheet, if he started | 20 keepers, round 11 | Too few to say anything |

Season-level rates the statistics page measures directly, such as penalties per match and how many are scored, can be
counted from its own totals, without waiting for more rounds.

## Requirements

### Requirement 1: The evidence

**User Story:** As the owner, I want every scored round to leave the evidence a recalibration needs, kept privately.

- **R1.1** FOR each scored round THE SYSTEM SHALL keep its calibration set, rebuilt from the stored facts and the official
  sheets as the round's report scores them. That's each player's chance and outcome for each kind of chance, and also, for
  each player who didn't start, whether he got a rating. *(Amended 2026-11-11: the statistics page counts rated games only,
  so a substitute who came on without a rating can't be told from one who didn't come on.)*
- **R1.2** Calibration sets SHALL stay in git-ignored private storage. Only aggregates reach the repository.
- **R1.3** A round's set SHALL be rebuilt the same way whenever asked: the same facts give the same set.

### Requirement 2: The chance of starting

**User Story:** As a player, I want a 25% to start to mean 25%.

- **R2.1** THE SYSTEM SHALL fit a calibration map from the outlets' consensus to the chance of starting, on the scored rounds:
  monotone, and shrunk toward no change where a bucket has few players.
- **R2.2** WHEN the map is approved THE SYSTEM SHALL apply it wherever a chance of starting is formed from the outlets, so
  that every answer uses it alike. An official lineup still settles the chance.

### Requirement 3: Cameos

**User Story:** As a player, I want the chance that a substitute comes on and gets a rating to match what happens.

- **R3.1** THE SYSTEM SHALL estimate from the calibration sets how often a player who didn't start got a rating: for
  defenders and midfielders, `CAMEO_SHARE`; for forwards, given that share, `CAMEO_RATED`. Each comes with its sample size.
  *(Amended 2026-11-11, as R1.1.)*

### Requirement 4: Rates the season itself measures

**User Story:** As the owner, I want the rates the statistics page counts to come from it, not from a guess.

- **R4.1** THE SYSTEM SHALL count league-wide, from the latest statistics read and the table: penalties awarded per match,
  how many are scored, of the misses how many were saved, and yellow and red cards per rated game by role, each with its
  sample size. These are `PENALTY_RATE`, `PENALTY_CONVERSION`, `PENALTY_SAVED_SHARE`, `YELLOW_PRIOR` and `RED_RATE`.

### Requirement 5: What waits

**User Story:** As the owner, I want a value changed only when the evidence is enough.

- **R5.1** EACH *(start)* constant this slice doesn't change SHALL keep its value, and the report SHALL say what evidence it
  needs and how much there is. That covers scoring shares, clean sheets, vote noise, the keeper's β and the rest.
- **R5.2** THE SYSTEM SHALL NOT change a value whose evidence is below its minimum sample, set in the design.

### Requirement 6: Checked where it wasn't fitted

**User Story:** As the owner, I want proof that a change helps before I approve it.

- **R6.1** FOR each proposed change to a fitted value (the starting map and the cameo rates) THE SYSTEM SHALL give its
  held-out check: fitted without a round, or without a set of matches when there's one round, and scored on it. It SHALL
  give the Brier score and the reliability before and after. The season's rates (R4.1) are counts, not forecasts: each
  SHALL carry its count and a 90% interval instead. *(Amended 2026-11-11.)*
- **R6.2** A fitted change that doesn't improve its held-out Brier score SHALL NOT be proposed.

### Requirement 7: The market's chances beside ours

**User Story:** As the owner, I want to see how much is just the match's own uncertainty.

- **R7.1** EACH round's calibration report SHALL also score the match-level chances the odds give, the same way and beside
  the players' ones: a win, a draw and a loss, three goals or more, both teams to score, and each side's clean sheet.

### Requirement 8: Proposed, approved, logged

**User Story:** As the owner, I want to approve each change and see its history.

- **R8.1** THE SYSTEM SHALL produce a recalibration proposal on request, from the command line. It SHALL give each value to
  change, its old and new value, its evidence and sample, and its held-out effect. It SHALL change nothing itself.
- **R8.2** WHEN the owner approves a proposal THE change SHALL land as one pull request to `engine/constants.py`, with an entry
  in a calibration log in the repository: the date, the rounds, each value's old and new value and its evidence, as
  aggregates only.
- **R8.3** A change SHALL be reversible by the same route.

### Requirement 9: What it moves

**User Story:** As a player, I want to know how the advice moves when the numbers change.

- **R9.1** FOR an approved proposal THE SYSTEM SHALL show, on a past round's facts, what the change moves: the lineup, its
  expected score and its thresholds, and the chances on the cards. The shape of every answer stays the same.

### Requirement 10: The docs and the limits

**User Story:** As the owner, I want the method to say what's calibrated and from what.

- **R10.1** THE SYSTEM SHALL update `docs/method.md`: each calibrated value replaces its *(start)* mark with the date and the
  evidence.
- **R10.2** THE SYSTEM SHALL read no new page and call no paid service. Every answer SHALL stay within its budget.

## Acceptance tests

| Test | What it proves | Requirements |
|---|---|---|
| AT-1 | A round's calibration set rebuilt the same way twice; its counts match the round's report; cameos counted | R1 |
| AT-2 | A starting map, by hand: monotone, shrunk where a bucket is thin, applied where a chance is formed; an official lineup still settles it | R2 |
| AT-3 | Cameo rates from invented outcomes, by hand, with their samples | R3 |
| AT-4 | Season rates from an invented statistics read, by hand, with their samples | R4 |
| AT-5 | A value below its minimum sample is kept, and the report says how far it is | R5 |
| AT-6 | A held-out check on invented rounds; a change that doesn't help isn't proposed | R6 |
| AT-7 | The market's match-level chances scored beside the players' in a round's report | R7 |
| AT-8 | The proposal command changes nothing, and lists each value with its evidence; an approved change and its log entry | R8 |
| AT-9 | What an approved change moves on a past round's lineup and cards | R9 |
| AT-10 | Manual: the owner reads the proposal on rounds 10 and 11 and approves or turns down each change | R6, R8 |

## Review of these requirements

An Analyze-Requirements pass, before design.

- **Two rounds is little.** Starting has 1,033 players over two rounds: enough for a coarse map, not a fine one. Getting a
  rating and scoring have one round each. R2.1's shrinkage and R5.2's minimum samples keep a thin bucket from moving a number
  much.
- **Starting is the outlets' percentages.** The model's chance of starting is their consensus, so the map calibrates the
  outlets. Calibrating each outlet on its own needs more rounds; it can come later.
- **The held-out check with one round.** Rating and cameo evidence is one round. R6.1 then holds out a set of matches rather
  than a round, a weaker check that the proposal says it used.
- **Season rates aren't calibration from predictions.** They're counts from the statistics page. They're still evidence, and
  R4 keeps them apart from the fitted values in the report.
- **The market here is the same model.** The team-level chances come from the same odds the model is fitted to. R7 shows the
  match's own uncertainty, not a rival forecast. The player-level market waits for anytime-scorer odds.
- **Changing the numbers changes old answers' replays.** A replay at an earlier `as_of` uses today's constants, so it no
  longer reproduces what was told then. The decision log keeps what was told, and the calibration scores the log, not
  replays. Design should say so where a review or a report replays.
- **Privacy.** Calibration sets are derived from third-party pages. They stay private, and the repository gets aggregates
  only (R1.2, R8.2).

## Owner decisions

- **2026-11-11:** the owner chose to start recalibration on the rounds already scored, not waiting for round 12.
- **2026-11-11, these requirements approved** with the three recommendations below ("perfect, start calibration").
- **2026-11-11, the design approved** with both of its open points ("Approve, start task 1"): R1.1 and R3.1 now say "got a
  rating without starting", and R6.1 and R6.2 apply to the fitted values, the season's rates carrying counts and intervals.

1. **Which values now.** Recommendation, approved: the chance of starting (a map on the outlets' consensus, 1,033 players), cameos (538
   players), and the rates the season counts itself. Scoring shares, clean sheets and vote noise wait, with their minimum
   samples. The alternative is all of them now, on thin evidence.
2. **The market beside ours.** Recommendation, approved: score the match-level chances from the odds now (R7). The player-level market
   comes with the new-sources slice's anytime-scorer odds. The alternative is to wait and do both together.
3. **How a change lands.** Recommendation, approved: the command proposes, the owner approves each change, and it lands as one pull
   request with a calibration log entry of aggregates. Never automatic.
