# Requirements Document: `mvp-cameos` (after Phase 2, before Phase 3)

Status: **Approved by the owner, 2026-11-24**, with both recommendations · Workflow: requirements-first · Depends on: `mvp-recalibrate` (signed off
2026-11-12) · Abbreviation: `cs` · Research: the calibration sets of rounds 11 and 12 (counts below, no names); the
[Phase 2 report](../../../docs/reports/phase-2-report.md)'s decision 3, taken by the owner on 2026-11-24

## Introduction

A player who doesn't start can still come on and get a rating: his cameo (method §A2). Every lineup leans on it. It
decides what a doubtful starter's bench cover is worth and where a substitute sits on the bench. Today one constant,
`CAMEO_SHARE = 0.5`, sets everyone's chance of a cameo, 0.5 × (1 − p_start), and it means two things:

- **A flat cameo** (defenders and most midfielders): the chance of coming on *and* getting a rating, worth a flat 5.5.
- **A priced cameo** (forwards and attacking midfielders): the chance of coming on. Once on, a goal is worth about 9.8,
  and without one he gets a rating 60% of the time (`CAMEO_RATED`, method §A4).

Rounds 11 and 12 scored the chance of a rating against what happened, for the players who didn't start and could have
come on:

| Kind of cameo | Players | Got a rating | The model's chance, on average |
|---|---:|---:|---:|
| Flat | 255 | 61 (24%) | 50% |
| Priced | 128 | 52 (41%) | 31% |

One share can't fit both: the first wants about a quarter, the second more than today's half. `mvp-recalibrate` saw
this on rounds 10 and 11. It fitted `CAMEO_SHARE` from the flat cameos (0.248, on 183 of the 200 players it needs) and
couldn't fit `CAMEO_RATED`: with the flat share, a priced cameo would need a rating more than 100% of the time. In round
12 the calibration's bucket for a rating at 50 to 60% held 100 players, of whom 28 got one; 88 of them had a flat cameo.

The owner decided on 2026-11-24 to give each kind of cameo its own share, fitted on the rounds scored and approved value
by value, as the first recalibration was. Like `mvp-recalibrate`, this slice changes the numbers only through a proposal
the owner approves.

## Glossary

| Term | Meaning |
|---|---|
| Flat cameo | A cameo worth a flat value: every outfield role whose `ROLE_PRIORS` entry has `priced_cameo` False |
| Priced cameo | A cameo with three outcomes, a goal, a rating without a goal or no rating: the roles with `priced_cameo` True (Pc, A, W, T) |
| Benched | A player who didn't start and could have come on: the calibration sets' rule today (not started, his rating known, a chance of a rating above his chance of starting) |
| Cameo share | How often a benched player comes on: with a rating, for a flat cameo; at all, for a priced one |

## Requirements

### Requirement 1: A share for each kind of cameo

**User Story:** As a player, I want a substitute's chance of a cameo to match what happens for his kind of cameo, so that
the bench order and the cover a doubtful starter gets are priced right.

- **R1.1** THE SYSTEM SHALL give a player with a priced cameo the chance of a cameo `CAMEO_SHARE_PRICED` × (1 − p_start),
  and a player with a flat cameo `CAMEO_SHARE` × (1 − p_start); on an official bench, the share of his kind alone.
- **R1.2** THE SYSTEM SHALL use the share of his kind wherever a chance of a cameo is formed: the outlets' consensus, an
  official lineup and a lineup without any outlet's view, so that every answer, card, alert, review and calibration set
  uses it alike.
- **R1.3** `CAMEO_SHARE_PRICED` SHALL start at today's 0.5, so that the slice changes no number until a proposal is
  approved.
- **R1.4** `CAMEO_RATED` SHALL keep the method's 60% and no longer be fitted: the priced share takes its place in the
  proposal (decision 1).

### Requirement 2: Both shares fitted and checked

**User Story:** As the owner, I want each share changed only on enough evidence, checked where it wasn't fitted.

- **R2.1** THE SYSTEM SHALL fit `CAMEO_SHARE` from the benched players with a flat cameo, as today: the share of them who
  got a rating.
- **R2.2** THE SYSTEM SHALL fit `CAMEO_SHARE_PRICED` from the benched players with a priced cameo: the share that, with
  each one's chance of scoring once on and `CAMEO_RATED`, gives as many ratings as happened.
- **R2.3** Each share SHALL come with its sample and its 90% interval, and SHALL be checked where it wasn't fitted, by
  round or by half a round's matches, as `mvp-recalibrate` R6 checks every value. It is proposed only with its minimum
  sample and only if it helps everywhere it was held out.
- **R2.4** Each share SHALL need 200 benched players of its kind, as `CAMEO_SHARE` does today (decision 2). One that
  hasn't enough is listed with what it waits for, as every value is.

### Requirement 3: The owner approves each share

**User Story:** As the owner, I want to see each share's evidence and what it moves before it changes my lineup.

- **R3.1** `fantadamus recalibrate` SHALL list both shares with their evidence and checks, and change nothing
  (`mvp-recalibrate` R8).
- **R3.2** An approved share SHALL land as a pull request with an entry in the calibration log. The tests worked out by
  hand on the starting values SHALL keep them (the `start_values` fixture).
- **R3.3** WHEN a share is approved, THE SYSTEM SHALL show what it moves on round 12's stored facts at its lock: the
  owner's lineup (formation, eleven, bench order, expected score) and the round's cards (chances of a rating, likeliest
  scorers), with the shape of every answer unchanged.

### Requirement 4: Proof and docs

- **R4.1** Each requirement SHALL come with its test written first. The slice SHALL need no new dependency, service or
  account, and read no page.
- **R4.2** Method §A4, the calibration log and `engine/constants.py` SHALL say what each share means.

## Acceptance tests

| Test | Proves | Requirement |
|---|---|---|
| AT-1 | The chance of a cameo for each kind, by hand: a flat and a priced cameo at the same chance of starting, before and after a share changes, and on an official bench | R1.1, R1.2 |
| AT-2 | With both shares at 0.5, every answer on a copy of the owner's lake is identical to today's | R1.3 |
| AT-3 | Both shares fitted by hand on invented sets, with their samples and intervals; `CAMEO_RATED` no longer fitted | R1.4, R2.1, R2.2 |
| AT-4 | Held out by round and by half a round; a share below its minimum isn't proposed, and says how far it is | R2.3, R2.4 |
| AT-5 | The proposal on the rounds scored, from stored facts only: both shares listed, nothing changed | R3.1 |
| AT-6 | Manual: the owner reads the proposal and approves or turns down each share | R3.1 |
| AT-7 | An approved share: its calibration log entry, what it moves on round 12's facts, the answers' shape unchanged | R3.2, R3.3 |
| AT-8 | No new dependency; the docs updated | R4 |

## Review (Analyze-Requirements style)

- **Ambiguity:** the two kinds follow `ROLE_PRIORS`, and "benched" is the calibration sets' existing rule.
- **Conflict:** for a priced cameo, how often he comes on and how often he is rated once on can't be told apart from
  rated games alone. Holding `CAMEO_RATED` at the method's value settles it (decision 1).
- **Testability:** every requirement has a test; the only manual one is the owner's approval.
- **Dependencies:** `mvp-recalibrate` (the sets, the checks, the proposal, the log), `mvp-roles` (`ROLE_PRIORS`),
  `mvp-lineup` (the simulation's three outcomes).

## Decisions for the owner

Both decided by the owner on 2026-11-24, as recommended ("Approve both").

1. **For forwards and attacking midfielders, fit how often they come on, and keep 60% rated once on?** Recommendation:
   yes. Rated games can't tell the two apart. The 60% follows from how ratings are given (a short cameo goes unrated)
   and is steadier than how often a coach brings a forward on. On rounds 11 and 12 the fit would be about 0.65, against
   0.5 today. The alternative, keeping 0.5 and fitting the rating instead, would need about 80% rated once on.
2. **The same 200 players for each share?** Recommendation: yes. The flat share has 255 now and can be proposed at once.
   The priced share has 128, about 64 a round, so it waits until about round 14 and is listed as waiting until then. The
   alternative, a lower minimum for the priced share, would change it now on a wider interval: about 0.53 to 0.76.
