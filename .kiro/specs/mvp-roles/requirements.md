# Requirements Document: `mvp-roles` (Phase 2, second slice)

Status: **Approved by the owner, 2026-11-03**; R1.1, R7.2 and AT-1 **amended the same day** with the design,
**the amendment approved the same day**; R4.4 added 2026-11-04, for the owner's review · Workflow: requirements-first · Depends on:
`mvp-x-or-y` and `mvp-collect` (built; code for this slice started before `mvp-collect`'s sign-off, owner decision
2026-11-03) · Method: [`docs/method.md`](../../../docs/method.md) §A3, §A4 and §A6 · Answers:
[`docs/answer-formats.md`](../../../docs/answer-formats.md), formats 1 and 4

## Introduction

Fantadamus answers "X or Y?" for forwards only. A lineup has a keeper, three to five defenders and three to five
midfielders too, and those are the questions the owner and the friend ask every round. This slice extends the
answer to every role, adds one player's outlook ("Will he start? Is he worth it?"), and reads every player's
season figures at once, from one page, so that the full-lineup slice after it has the figures for a whole squad.

It builds on what exists: the round page already carries every role's probable and official lineups, the odds
fit already gives both teams' expected goals, and the forward model is the method's model for every outfield
player with different priors. Keepers are the one new model (method §A6).

**Not in this spec:** the full lineup, the bench order, the formation call and the simulation (the next slice,
with method §A9 tests 1 and 5); a choice between two roles, which is the formation call; the defence modifier
and other league options beyond bonuses and maluses; Mantra leagues; match cards; live forecasts and alerts;
per-minute data and each player's own substitute record (`bench_impact`).

## Glossary

Spec-wide terms are in `product.md`; `mvp-x-or-y`'s and `mvp-collect`'s terms apply. Here:

| Term | Meaning |
|---|---|
| Statistics page | Fantacalcio.it's `/statistiche-serie-a`: one table with every Serie A player's season so far |
| Outlook | One player's forecast for the round: will he start, what he's worth if he does, and how sure that is |
| Mantra role | The finer role Fantacalcio.it gives each player (for example `Pc` centre-forward, `T` attacking midfielder, `Dd` right-back); the priors are set by it |
| Skill (keeper) | A keeper's average rating with his goals conceded added back, so that his defence's work isn't counted as his (method §A6) |
| Clean sheet | A match in which the keeper's team concedes no goals |

## Sources

All on the allowlist; robots.txt allows the statistics page (checked 2026-11-03, when it was fetched once to see
its layout, kept in the git-ignored `data/private/pages/`).

| Fact | Read exactly by Fantadamus | Read by Claude through `read_page` |
|---|---|---|
| Players' season figures, every role | **New:** Fantacalcio.it's statistics page (R1) | The statistics page itself, then each player's Fantacalcio.it profile (`mvp-collect`'s pages) |
| Probable and official lineups, every role | Fantacalcio-Online round page (unchanged) | Unchanged |
| Odds, and from them each side's expected goals and clean-sheet chance | Fantacalcio-Online round page (unchanged) | Unchanged |
| League table, penalty takers | None (unchanged) | Unchanged |

The statistics page gives, per player: his profile link (and so his ID), his club, his Classic role and Mantra
roles, rated appearances, average rating (MV), fantamedia, goals, goals conceded, penalties scored and taken,
penalties saved, assists, and yellow and red cards. It doesn't give appearances without a rating.

## Requirements

### Requirement 1: Every player's season figures, from one page

**User Story:** As a player, I want every player's figures read once for everyone, so that a question about any
player, or a whole squad, doesn't wait for Claude to read a profile per player.

- **R1.1** THE SYSTEM SHALL read the statistics page with a reader of its own and store every player's season
  figures as one record per read, with the page's URL, through the same flow as `mvp-collect`'s collector
  (`submitted_by` `collector`). Answers SHALL read them as they read the season figures Claude submits.
- **R1.2** THE SYSTEM SHALL take from each row: the player's ID (from his profile link), name, club, Classic role,
  first Mantra role, rated appearances, average rating, goals, goals conceded, penalties scored and taken,
  assists and yellow cards. It SHALL ignore the fantamedia: the method prices bonuses apart from the vote
  (§A4).
- **R1.3** WHERE a player's figures come from the statistics page, which gives no appearances without a rating,
  THE SYSTEM SHALL count his appearances as his rated appearances, and the answer SHALL speak of rated games.
- **R1.4** THE SYSTEM SHALL read the statistics page once a day in `fantadamus collect --due`, and WHEN an answer
  needs a player's season figures older than 48 hours, it SHALL read the page first, within the same 60
  seconds as the round page (`mvp-collect` R1.3). The freshness target for season figures becomes 48 hours, so
  that a round's ratings count before the next round. This amends `mvp-collect` R7.1, under which season
  figures weren't scheduled.
- **R1.5** WHEN the page's figures are unchanged since its last stored read THE SYSTEM SHALL store nothing new
  and count the read as their refresh (`mvp-collect` R1.4, R1.5).
- **R1.6** IF the statistics page can't be fetched or read, or a read is missing any of the 20 clubs or has a club
  without a keeper, THEN THE SYSTEM SHALL store nothing from it, and the season figures of the players the answer needs
  SHALL go into the refresh plan, with the statistics page and their profiles to read through `read_page`
  (`mvp-collect` R8.1). A single row that fails validation SHALL be left out and named in the report, and the
  rest stored.

### Requirement 2: Defenders and midfielders

**User Story:** As a player, I want a defender or a midfielder priced with the same arithmetic as a forward, with
his own role's priors, so that every answer is consistent and testable.

- **R2.1** THE SYSTEM SHALL value every outfield player with the forward model (`mvp-x-or-y` R9: the expected
  vote, goal and assist shares shrunk toward a prior, the penalty term, the yellow card, the cameo, the key),
  with the priors of his first Mantra role *(start)*:

  | First Mantra role | Goal share | Assist share | Minutes share if he starts | Cameo |
  |---|---|---|---|---|
  | `Pc` centre-forward | 0.30 | 0.11 | 0.85 | priced, as for forwards |
  | `A` second striker | 0.20 | 0.11 | 0.85 | priced |
  | `W` wide forward | 0.15 | 0.11 | 0.85 | priced |
  | `T` attacking midfielder | 0.15 | 0.11 | 0.80 | priced |
  | `C` central midfielder, `M` holding midfielder | 0.06 | 0.08 | 0.85 † | 5.5 |
  | `E` wing-back | 0.04 | 0.08 | 0.85 † | 5.5 |
  | `Dd`, `Ds` full-back | 0.03 | 0.06 | 0.95 | 5.5 |
  | `Dc`, `B` centre-back | 0.05 | 0.02 | 0.95 | 5.5 |

  † The method gives no minutes share for these roles; 0.85 lies between its 0.80 and 0.95. Every value here is
  a starting value, recalibrated from the decision log (method §A8).

- **R2.2** WHERE a player's Mantra role is unknown THE SYSTEM SHALL use his Classic role's usual one: `A` for a
  forward (the forward model's 0.20 today), `C` for a midfielder and `Dc` for a defender.
- **R2.3** THE SYSTEM SHALL shrink defenders' goal and assist shares with a prior weight of 25 team goals, and
  every other outfield player's with 15 (method §A4).
- **R2.4** WHERE a player of any role is his club's first penalty taker THE SYSTEM SHALL add the penalty term
  (0.15 × 0.78) times his own minutes share to his E[goals].
- **R2.5** WHERE the league sets the goal bonus per role THE SYSTEM SHALL use the bonus of the player's Classic
  role.
- **R2.6** THE SYSTEM SHALL value a forward whose first Mantra role is `Pc`, `A`, `W` or unknown exactly as before
  this slice, given the same facts. A forward listed first as `T` moves from the forward model's default to the
  attacking midfielder's priors.

### Requirement 3: Keepers

**User Story:** As a player, I want a keeper judged on his own work and his match, not on his defence's season,
so that a good keeper behind a leaky defence isn't marked down twice.

- **R3.1** THE SYSTEM SHALL compute a keeper's E_start = expected vote + clean sheet × P(clean sheet) + goal
  conceded × expected goals conceded, with the signed values of the user's league rules, so a goal conceded at
  −1 lowers the score (method §A6).
- **R3.2** THE SYSTEM SHALL take a keeper's expected goals conceded as the opponent's expected goals, and
  P(clean sheet) as the chance the opponent scores none, both from the same fit of the match's odds (or, without
  odds, from regressed team form, flagged as `mvp-x-or-y` R5.3 does).
- **R3.3** THE SYSTEM SHALL compute his skill as average rating + 0.35 × goals conceded per rated appearance,
  shrunk with weight n / (n + 9) toward 6.0 + 0.35 × the league's goals per team per match (from the table),
  where n is his rated appearances; and his expected vote as skill − 0.35 × expected goals conceded *(start)*.
  An average keeper behind an average defence is then expected at 6.0.
- **R3.4** THE SYSTEM SHALL give keepers no cameo (p_cameo = 0) *(start)*: a keeper comes on only when the starter
  is hurt or sent off. His key is then his E_start.
- **R3.5** THE SYSTEM SHALL return, for a keeper, P(clean sheet), the expected goals conceded and his skill, in
  place of the chance to score.
- **R3.6** IF two keepers in an "X or Y?" play for the same club THEN THE SYSTEM SHALL say that one plays exactly
  when the other doesn't: field the likelier starter, and the other covers him exactly (method §A6).

### Requirement 4: "X or Y?" for every role

**User Story:** As a player, I want "X or Y?" for any two players of the same role, in the same shape as the
forwards' answer.

- **R4.1** WHEN both players have the same Classic role THEN `compare_players` SHALL answer as it does for
  forwards (`mvp-x-or-y` R10, `mvp-collect` R6): the verdict with the bench advice, the margin and its label,
  the verdict without bench cover, what would flip it, what to check before the deadline, the movement, the
  update times and the sources. For keepers, what would flip it is the p_start or the opponent's expected goals
  at which the order changes.
- **R4.2** IF the two players have different Classic roles THEN `compare_players` SHALL return each player's
  outlook (R5) and no verdict, and say that a choice between roles is the formation call, which comes with the
  full lineup.
- **R4.3** IF a player has no chance of a rating THEN the answer SHALL name his role in its advice: "put a fit
  defender first on the bench" (`mvp-x-or-y` R10.7).
- **R4.4** IF no row of an outlet's lineup names a player, and a row has his surname and he is the only club-mate
  with it, THEN THE SYSTEM SHALL count that row as his, and the answer SHALL say he was matched by surname. An outlet's "ANGUISSA A" is the statistics page's "Zambo Anguissa"; without this he
  gets the 5% of a player nobody mentions.

### Requirement 5: One player's outlook

**User Story:** As a player, I want to ask about one player ("Will he start? Is he worth it?") and get his
forecast in a few lines.

- **R5.1** THE SYSTEM SHALL provide an MCP tool `player_outlook` that returns, for one player of any role: his
  p_start with each outlet's value, the confidence and his ballottaggio rivals; his expected score if he starts
  and his key; P(scores), or for a keeper P(clean sheet) and the expected goals conceded; whether he takes the
  penalties; his form; his match's context; the movement since the user's previous answer about him or 24 hours
  earlier; when the facts were updated; what to check before the deadline; and the sources.
- **R5.2** `player_outlook` SHALL collect first, fall back to a refresh plan and ask for the league rules exactly
  as `compare_players` does (`mvp-collect` R1.3, R8.1; `mvp-x-or-y` R11, R12.3).
- **R5.3** THE SYSTEM SHALL log each outlook in the decision log like an answer (method §A8): the as-of time, the
  player, every published probability, his key, the rules used and the content hashes of the facts used.

### Requirement 6: Contracts, quality and the log

**User Story:** As the owner, I want the new figures validated like every other fact, so that a bad read is
rejected rather than priced.

- **R6.1** THE SYSTEM SHALL add goals conceded to the `player_season` contract as an optional field, with a minor
  version bump and a changelog entry, so that profiles submitted by Claude stay valid.
- **R6.2** THE SYSTEM SHALL reject a row in which a player who isn't a keeper has conceded goals, or a keeper has
  conceded more than 10 goals per rated appearance, with the reason.
- **R6.3** THE SYSTEM SHALL log, for a keeper, P(clean sheet) and the expected goals conceded with the other
  published probabilities (method §A8).

### Requirement 7: The agent prompt and the docs

**User Story:** As a player, I want my Claude to know what Fantadamus can now answer, and to answer it in the
owner's shapes.

- **R7.1** THE SYSTEM SHALL tell Claude, in the agent prompt, that "X or Y?" works for any two players of the same
  role and `player_outlook` for any player, that the full lineup and the formation aren't supported yet, and
  how to render answer formats 1 and 4, with a keeper's clean-sheet chance in place of the chance to score.
- **R7.2** THE SYSTEM SHALL add the statistics page to the reading list (first for season figures) and to the
  source registry.

## Acceptance tests

| ID | Acceptance test | Proves |
|---|---|---|
| AT-1 | Method §A9 test 3, at the method's own weights: two keepers of equal skill, whose clubs conceded 6 and 9 in five matches, differ by about +0.9 on raw team form, by about 0.3 on regressed team form, and by under 0.1 once the odds price both matches alike | R3.2, R3.3 |
| AT-2 | Two keepers with the same skill behind different defences (average 6.0 conceding 2 per game, 6.35 conceding 1 per game, in the same number of games) get the same expected vote in the same match | R3.3 |
| AT-3 | A keeper facing an opponent expected to score about 1.0 has a clean-sheet chance of about 37%, from the same fit as his team's chance to win | R3.1, R3.2 |
| AT-4 | Without goals or games, a `T`'s goal share is 0.15, a `C`'s 0.06 and a full-back's 0.03 with a weight of 25; and a forward's values are the same as before this slice | R2.1 to R2.3, R2.6 |
| AT-5 | Method §A9 test 6 for two defenders: X ahead if he plays but only about 55% to get a rating, each with a cameo of 5.5, gives "start X, Y first on the bench", and the answer without bench cover differs | R2.1, R4.1 |
| AT-6 | From a synthetic statistics page served by a local test server, one collection stores every player's season figures with the page's URL; a second run stores nothing new; a page missing a club stores nothing, and the refresh plan lists the season figures with the pages to read through `read_page` | R1 |
| AT-7 | A defender and a midfielder in one "X or Y?" get two outlooks, no verdict, and the formation-call message | R4.2 |
| AT-8 | Two keepers of the same club: the answer fields the likelier starter and says the other covers him exactly | R3.6 |
| AT-9 | From a lake with league rules, `player_outlook` answers in one call after the collector runs, with the sources, update times and movement, and adds one log entry | R5 |
| AT-10 | Manual: the owner asks a real "X or Y?" for keepers, defenders and midfielders, and one player's outlook, in Claude Desktop; the season figures come from the statistics page | All |

## Owner decisions

- **2026-11-03:** the owner asked to write this spec's requirements now, while `mvp-collect`'s real round runs; no
  code for it until `mvp-collect` is signed off.
- **2026-11-03:** these requirements approved, with two choices:
  - Fantadamus reads the statistics page itself, with a reader of its own (R1.1), and the user's Claude is the
    fallback. This makes a second reader, for this page only, beside the round page's (`mvp-collect`'s "one
    reader" decision of 2026-10-31). One request a day gives every player's figures to every user, and the full
    lineup will need a whole squad's.
  - A question between two roles gets both players' outlooks and no verdict (R4.2) until the full lineup's
    formation call.
  - The starting values the method doesn't give (R2.1's †, the assist priors' split, R3.3's prior, R3.4) are
    calibrated from the decision log like the others.
- **2026-11-03, with the design:** the owner approved three corrections:
  - R1.1: the statistics page is stored as one record per read, not one per player, which would have put about
    45,000 files in bronze by May;
  - R7.2: no data-product catalog, since none exists yet;
  - AT-1 restated at the method's own weights: regressing five matches with n / (n + 12) keeps 5/17 of a raw
    gap, so the two keepers come within 0.1 only once the odds price their matches alike.
- **2026-11-03, later:** the owner started this slice's tasks before `mvp-collect`'s sign-off. `mvp-collect`'s
  real round (its task 8) is deferred, and both slices are tested together in a real round once this one is
  built. This replaces the first decision above.
- **2026-11-04, building task 5:** asking on the saved real pages showed a first-choice midfielder at 5% to start
  against the outlets' 90–95%, because they write his compound surname in part, and a verdict of "clear" that
  should have been "lean". R4.4 added; proposed to the owner with the task's report.
