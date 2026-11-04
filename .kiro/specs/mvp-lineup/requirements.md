# Requirements Document: `mvp-lineup` (Phase 2, third slice)

Status: **Approved by the owner, 2026-11-04**, with the amendment to R5.5 and R5.6; R1.5, R2.1, R2.3, R3.3 to R3.5, R4.4
and AT-6, AT-7, AT-10 amended the same day from the owner's league notes, **for the owner's review** · Workflow: requirements-first · Depends on: `mvp-x-or-y`,
`mvp-collect` and `mvp-roles` (signed off) · Method: [`docs/method.md`](../../../docs/method.md) §A1 to §A3, §A7, §A8,
§A9 tests 1 and 5 · Answers: [`docs/answer-formats.md`](../../../docs/answer-formats.md), formats 2, 3 and 6

## Introduction

Fantadamus prices every player and answers "X or Y?" within a role. The owner's main question is bigger: "who do I
field?" This slice answers it. Given the user's squad and the league's full rules, it picks the eleven, the bench in
order and the formation, simulates the round under the league's real substitution rules, and reports the expected
score and the chance of reaching each goal threshold. It's the last slice before Phase 2's gate, so it also delivers
the first calibration report.

It adds no new source. The round page and the statistics page already give every player of a squad at once.

**Not in this spec:**

- anything that needs the opponent's team: the home factor, the draw, superiority and humiliation bonuses, the rule
  of 59, and modifiers that compare two teams or act on the opponent. The answer is about the user's own score;
- Mantra leagues;
- modifiers, including the defence modifier and the captain (R2.3);
- trades, auctions and market values (out of scope for v1);
- match cards, live forecasts and alerts: later specs;
- the online endpoint: Phase 3.

## Glossary

Spec-wide terms are in `product.md`; the earlier slices' terms apply. Here:

| Term | Meaning |
|---|---|
| Squad | The players a user owns in their league, kept privately per user |
| Goal thresholds | The table that turns a team's score into fantasy goals: 66 points is one goal, then the league's next steps |
| Fantasy goals | The goals a team's score converts to; what the method optimises (§A1) |
| Substitution mode | How a player without a rating is replaced: same role only, role first then bench order, or bench order first |
| Formation change | Whether a substitution may change the formation, if the result is one the league allows |
| Worth of a choice | What choosing X over Y adds in expected points when the bench covers both (R8) |

## What leagues can set

There is no single official rulebook: Fantacalcio.it says each league writes its own, and offers a template.

| Setting | Most common values | Sources |
|---|---|---|
| Goal thresholds | First at 66 in almost every league. Then a preset table (66, 72, 77, 81, 85, 89…) or a fixed step of 6 (66, 72, 78…) | Fantacalcio-Online's guide to goal bands |
| Bench size | Open; 11 is Fantacalcio-Online's default and 7 the next most used | Fantacalcio-Online, substitutions guide |
| Substitutions per match | 4, then 3, then 5 | Same |
| Substitution mode | Role first then bench order (about half), same role only (about 40%), bench order first (rare) | Same |
| Formation change | Allowed in about 60% of leagues; it comes with the substitution mode | Same |
| Allowed formations | 3-4-3, 3-5-2, 4-3-3, 4-4-2, 4-5-1, 5-3-2, 5-4-1 | [Fantacalcio.it's league template](https://www.fantacalcio.it/regolamenti/leghe-private) |
| Squad | 25 players: 3 keepers, 8 defenders, 8 midfielders, 6 forwards | Fantacalcio-Online's rules guide |
| Defence modifier (not built, R2.3) | Optional; the most used modifier. Most common table: keeper and 3 best defenders, pure votes averaged: 6.00 gives +1, 6.50 +3, 7.00 +6 | Fantacalcio-Online's defence-modifier guide |
| Captain (not built, R2.3) | Optional. The captain's pure vote gives −2.5 to +2.5 in half-point bands, 0 from 6 to 6.49 | Fantacalcio-Online's captain guide |
| League format | Head to head, where thresholds decide; or total points, where they don't matter | Fantacalcio.it's league template |

## Requirements

### Requirement 1: The squad

**User Story:** As a player, I want to give my squad once, so that "who do I field?" needs nothing else from me.

- **R1.1** THE SYSTEM SHALL provide an MCP tool `set_squad` that takes the user's players by name and stores them by
  player ID, privately per user and never in the repository. Calling it again SHALL replace the squad.
- **R1.2** IF a name matches several players or none THEN `set_squad` SHALL store nothing and return every such name,
  with the candidates, so that Claude can ask the user.
- **R1.3** THE SYSTEM SHALL return the squad it stored, by role, and SHALL say if it can't field a formation the league
  allows, for example with no keeper.
- **R1.4** WHEN a stored player is no longer listed at any club THE SYSTEM SHALL say so in the answer and leave him out
  of the eleven.
- **R1.5** THE SYSTEM SHALL keep several squads per user, by team name, so that a player can also ask on behalf of a
  league-mate. They share the user's league rules. Without a name, the squad is the user's own.

### Requirement 2: The league's full rules

**User Story:** As a player, I want my league's own rules used, so that the eleven is right for my league.

- **R2.1** THE SYSTEM SHALL let `set_league_rules` also take: the league format (head to head or total points), the
  goal thresholds, the bench size, the substitutions per match, the substitution mode, the allowed formations, the vote a
  player without a rating keeps if the league gives one, and any other rules the league uses (R2.3).
- **R2.2** IF a user asks for a lineup and any of those is unset THEN THE SYSTEM SHALL return the setup step for just
  those settings, offering the most common values above. It SHALL never assume them. Users who set only bonuses and
  maluses SHALL keep getting "X or Y?" answers.
- **R2.3** WHERE a league uses rules this spec leaves out, such as a modifier or a home factor, THE SYSTEM SHALL take their
  names, and every lineup SHALL say that its score doesn't include them.
- **R2.4** IF a value is impossible (thresholds not rising, a formation that isn't eleven players with one keeper, a
  bench too small for a keeper and one of each role) THEN `set_league_rules` SHALL reject it with the reason.

### Requirement 3: The eleven, the bench and the formation

**User Story:** As a player, I want the best eleven and the bench in order, so that I can copy them into my league
before the lock.

- **R3.1** THE SYSTEM SHALL provide an MCP tool `best_lineup` with the same steps as the other tools first: the setup
  step, collecting, and one refresh plan of what's missing.
- **R3.2** THE SYSTEM SHALL, for each allowed formation, field the top of each role by key, and put the rest on the
  bench by key within each role (method §A3), up to the bench size.
- **R3.3** THE SYSTEM SHALL treat a club's keepers as one place: it fields the likelier starter, whatever their keys, and
  puts the other first among the bench keepers, since he plays exactly when the starter doesn't (method §A6).
- **R3.4** THE SYSTEM SHALL recommend the formation with the most expected fantasy goals, or, in a total-points league,
  the highest expected score. IF the top formations are within about 0.15 points THEN it SHALL call that a coin flip and
  say which has the higher ceiling, since variance helps an underdog (§A7).
- **R3.5** `best_lineup` SHALL take players the user wants to start or leave out, and a formation, and return that lineup
  with its cost against the recommendation, in expected points and in the chance of each threshold (method §A8).

### Requirement 4: The simulation

**User Story:** As a player, I want the chance of reaching each threshold, because one goal more or less decides a
head-to-head match.

- **R4.1** THE SYSTEM SHALL simulate each allowed formation with the league's real rules: role for role or as its mode
  says, the first bench player with a rating, the substitution cap, a keeper replaced only by a keeper, and a formation
  change only into an allowed formation (method §A7).
- **R4.2** THE SYSTEM SHALL draw each player's outcome from his chances: he starts, comes on with a rating, which blocks
  his substitute (§A2), or has no rating. It SHALL add noise to the vote, draw goals and assists as Poisson counts, and
  draw yellow cards.
- **R4.3** THE SYSTEM SHALL draw each match's goals once, so that a striker's goal and the goal conceded by the opposing
  keeper are the same event (§A7, §A9 test 5).
- **R4.4** THE SYSTEM SHALL apply the league's goal thresholds to each simulated score.
- **R4.5** THE SYSTEM SHALL report, for each allowed formation: the expected score, the range it falls in eight rounds out
  of ten, the expected fantasy goals, and the chance of reaching each threshold.
- **R4.6** THE SYSTEM SHALL give the same answer for the same facts, and SHALL answer within 3 seconds for a 25-player
  squad and seven formations on the owner's Mac.

### Requirement 5: The answer

**User Story:** As a player, I want the lineup at a glance, in the same forecast shape as the other answers.

- **R5.1** `best_lineup` SHALL return what answer format 2 shows: the formation, the expected score and range, the
  threshold chances; each starter's match, chance of starting and its confidence, value, chance of scoring or clean
  sheet, and penalty duty; and the bench in order.
- **R5.2** THE SYSTEM SHALL return the two or three calls that matter: the formation, from comparing the marginal players
  (§A7), and the closest choices between a starter and the player behind him, with what each is worth (R8).
- **R5.3** THE SYSTEM SHALL return who is out or doubtful and whether the bench covers him, the most likely scorers, what
  moved since the user's previous lineup, and what to check before the lock (§A7).
- **R5.4** THE SYSTEM SHALL list each source once for the whole answer, and SHALL keep the answer under 15 KB for a
  25-player squad. A player's full breakdown stays with `player_outlook`.
- **R5.5** THE SYSTEM SHALL answer from the best data it has, and SHALL warn about every number that rests on something
  more basic, naming the match or player and what it affects: a match priced from the 1X2 without over/under, or from
  team form without odds; a player no outlet lists, at the default chance; a player without rated games, on his role's
  priors; a keeper whose goals conceded aren't known; an outlet's name matched by surname.
- **R5.6** WHERE better data could be read THE SYSTEM SHALL list it with the answer, with its pages and search hints, as
  a refresh plan does. Claude SHALL try once to read it and ask again. If it can't get it, the answer stands with its
  warning: the lineup is never held back for it.

### Requirement 6: The bench order and the formation call on their own

**User Story:** As a player, I want to ask just "which formation?" or "how should I order my bench?" and get a short
answer.

- **R6.1** THE SYSTEM SHALL return, with the lineup, the comparison of the allowed formations (format 3) and the reason
  for each bench place (format 6), so that Claude can answer either question alone from one call.
- **R6.2** WHERE a user with a squad asks about two players of different roles, THE SYSTEM SHALL say that `best_lineup`
  answers it, as the formation call. `compare_players` itself stays as it is.

### Requirement 7: The decision log and calibration

**User Story:** As the owner, I want the forecasts scored against what happened, so that the starting values get better
(method §A8), and because Phase 2's gate needs it.

- **R7.1** WHEN `best_lineup` answers THE SYSTEM SHALL append to the decision log: the as-of time, the recommended lineup
  and formation, each starter's published chances, the threshold chances, the rules used and the content hashes.
- **R7.2** THE SYSTEM SHALL provide `fantadamus calibrate --round N`, which scores the round's logged chances against
  what happened: chance of starting against the official lineups, chance of scoring and of a clean sheet against what
  the statistics page's figures gained over the round. It SHALL report the Brier score and reliability by probability
  bucket (§A8).
- **R7.3** THE SYSTEM SHALL report which logged chances it couldn't score, and why, and SHALL store no page text.

### Requirement 8: What a choice is worth

**User Story:** As a player, I want the margin to say what the choice is really worth, so that "clear" means clear.

- **R8.1** THE SYSTEM SHALL keep ordering players by the key (§A3). It SHALL give the margin of a choice as the difference
  in keys times both players' chances of a rating, because the choice only matters when both get one, and SHALL set the
  label from that. This amends `mvp-x-or-y` R10.2.
- **R8.2** WHERE one of the two players has no chance of a rating THE SYSTEM SHALL keep the "won't play" advice, with the
  difference in keys as today.

### Requirement 9: The agent prompt and the docs

**User Story:** As a player, I want my Claude to know it can now pick my lineup.

- **R9.1** THE SYSTEM SHALL tell Claude, in the agent prompt, how to use `set_squad` and `best_lineup` and how to answer
  in formats 2, 3 and 6.
- **R9.2** THE SYSTEM SHALL say in the README and the player guide what Fantadamus now answers, and how a player gives
  their squad and rules.

## Acceptance tests

| ID | Acceptance test | Proves |
|---|---|---|
| AT-1 | Method §A9 test 1: a brute force over every ordering of random squads shows that sorting by the key is optimal in 100% of cases | R3.2 |
| AT-2 | Method §A9 test 5: a striker's goal against the user's own keeper nets the goal bonus less what the keeper loses, and less again if it breaks the clean sheet; the link narrows the spread and raises the chance of the first threshold. The method's "about +2.5 and +1.5" depend on how much a goal lifts the scorer's rating, which it doesn't give: the design checks them | R4.3 |
| AT-3 | A league's substitution rules: role for role, first bench player with a rating, the cap, a cameo with a rating blocking his substitute, a keeper replaced only by a keeper, a formation change only into an allowed formation | R4.1, R4.2 |
| AT-4 | Thresholds: known scores convert to the right fantasy goals on both preset tables, and the chance of each threshold matches a hand-worked case | R4.4, R4.5 |
| AT-5 | The formation falls out of the marginal players: a strong third forward over a weak fourth defender picks 3-4-3; a head-to-head and a total-points league can differ | R3.4, R5.2 |
| AT-6 | The bench is in key order within each role; of two keepers of one club the likelier starter is fielded, even with the lower key, and the other is first on the bench; the lineup comes from one call with its sources once | R3.2, R3.3, R5.1, R5.4 |
| AT-7 | `set_squad` resolves names, returns candidates and unknown names, stores nothing then, and replaces the squad on a second call; a league-mate's squad is kept apart under its team name; the files sit under the git-ignored data folder | R1 |
| AT-8 | A user with only bonuses and maluses still gets "X or Y?", and gets the setup step for just the missing settings on `best_lineup`; an impossible value is rejected | R2 |
| AT-9 | The same facts give the same lineup; a 25-player squad and seven formations take under 3 seconds; the answer is under 15 KB | R4.6, R5.4 |
| AT-10 | An override: forcing a player into the eleven, or another formation, returns that lineup with its cost in points and threshold chances; a league rule this spec leaves out is named in the answer | R2.3, R3.5 |
| AT-11 | Worth of a choice: a 12% backup keeper ahead of a 92% starter on the key is a coin flip, not "clear"; the order doesn't change | R8 |
| AT-12 | `fantadamus calibrate` on a scripted round gives the right Brier scores and buckets, and names what it couldn't score | R7 |
| AT-14 | A squad with a player in a match without over/under gets its lineup in one call, with a warning naming the match and the pages that could improve it; once better odds are submitted, the warning goes and the numbers use them. A player without rated games and one no outlet lists each get their warning | R5.5, R5.6 |
| AT-13 | Manual: the owner gives a real squad and rules in Claude Desktop, and gets a lineup for a real round to compare with their own choice | All |

Method §A9 is then complete: tests 2, 3, 4 and 6 passed in earlier slices.

## Owner decisions

- **2026-11-04:** the owner signed off `mvp-collect` and `mvp-roles` and asked to move on to close Phase 2.

- **2026-11-04:** these requirements approved, with three decisions:
  1. **Which rules to build (R2):** settled by the owner's league notes, kept outside this public repository: no defence
     modifier and no captain, thresholds from 66 with a fixed step, a long bench, substitutions role for role. So R2.3
     drops both modifiers, and a league that uses one gets a line saying the score leaves it out. The second player's
     league isn't known yet.
  2. **What a choice is worth (R8):** approved. Method §A9 test 6 now reads "lean" rather than "clear".
  3. **A lineup and basic data (R5.5, R5.6):** the agent proposed answering from the 1X2 and saying so. The owner wants
     the best statistics, or a warning when the answer rests on something basic. So Claude tries once for better data,
     and any number left on basic data carries a warning, wider than over/under alone.
- **2026-11-04, from the same notes, for the owner's review:** a player also asks on behalf of league-mates (R1.5); a
  club's keepers are one place, because on a real squad an unrated backup had the higher key (R3.3); a close call says
  which option has the higher ceiling (R3.4); and an override's cost is given once, as the method asks (R3.5).
