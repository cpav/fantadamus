# Requirements Document: `mvp-rules` (Phase 2, fourth slice)

Status: **Approved by the owner, 2026-11-07**, with all three recommendations · Workflow: requirements-first · Depends on: `mvp-lineup` (signed off 2026-11-07) ·
Abbreviation: `ru` · Method: [`docs/method.md`](../../../docs/method.md) §A1, §A4, §A6 · Answers:
[`docs/answer-formats.md`](../../../docs/answer-formats.md)

## Introduction

There's no single Fantacalcio rulebook: each league writes its own. Today every rule Fantadamus knows is a fixed field and its own
lines of code, so each new one means building it by hand. Worse, four of the ten rules it asks for are stored and never priced,
and nothing says so: a missed penalty, a saved penalty, an own goal and a red card.

The owner asked for rules to be as flexible as possible without crafting each one in code (2026-11-07). This slice makes a league's
rules **data**, read by one general engine:

1. **One table of events:** what each event is worth, for each role. The basics have no special place: Classic is a ready-made table, like
   any other league's.
2. **Formula rules:** who counts, how their pure votes combine, and bands that turn the result into points. The defence
   modifier and the captain become two entries, not two features.
3. **Claude as the translator:** a player pastes their rulebook, their Claude turns it into these two forms, and the tools validate
   it and say what's priced and what's left out.

Anything that doesn't fit is saved by name, and every answer says its score leaves it out, as it does today.

**Not in this spec:**

- anything that needs the opponent's team, such as the classic and midfield modifiers, the home factor, the rule of 59 and draw or
  superiority bonuses. It's a later slice, and it should add the opponent's score as one more input to the same formulas;
- Mantra leagues, which are out of the MVP (`product.md`, Further notes);
- a fair-play bonus, the one common rule that measures something other than the pure vote: it's named as left out until a league needs it;
- recalibrating the constants: the next slice;
- choosing the players by the modifiers: the order within a role stays by key (R3.5);
- trades, auctions and market values (out of scope for v1).

## Glossary

| Term | Meaning |
|---|---|
| Event | Something a player does in a match that a league gives points for, such as a goal or a yellow card |
| Pure vote | A player's rating alone, without bonuses or maluses |
| Formula rule | A rule worked out from several players or one measure after a simulated round: a modifier, or the captain |
| Band | A range of values and the points it gives |
| Stand-in vote | The vote a formula rule counts for a player missing from its unit (*voto d'ufficio*) |

## What leagues can set

The vocabulary comes from what the platforms and templates actually offer, read on 2026-11-07.

**Single events.** Bonuses and maluses can be set by value and by role, and the values differ between leagues: for example, a
penalty scored and a penalty missed are ±2.5 in one standard and +3 and −3 in another.

| Event | Common values | Fantadamus today |
|---|---|---|
| Goal, assist, yellow card, goal conceded, clean sheet, penalty scored | +3, +1, −0.5, −1, +1, +2.5 to +3 | Priced |
| Penalty missed, penalty saved, own goal, red card | −2.5 to −3, +2.5 to +3, −2, −1 | **Stored, never priced** |
| Set-piece assist | +0.5, or the same as an assist | Not known |
| Decisive goal, for a win or a draw | +1, optional | Not known |
| Player of the match | +0.5, optional | Not known |
| Assist split into gold, standard and soft | Each +1 by default | Not known |

**Formula rules.** Fantacalcio-Online builds its own custom modifiers from a fixed set of parts: the unit, the base number of players,
stand-in votes, a sum, an average or the best three plus the keeper, a per-player form that can exclude scorers, a condition on how
many are fielded, and bands. Votes are always pure. Its totals go into the team score before goals are worked out.

| Rule | Who counts | Measure and how combined | Bands | Needs the opponent? |
|---|---|---|---|---|
| Defence modifier, *Gazzetta* | Keeper and 3 best defenders | Pure vote, average | 6.00 +1, 6.50 +3, 7.00 +6 | No |
| Defence modifier, classic | Defenders | Pure vote, average | From +2 to −3, on the opponent | **Yes** |
| Midfield modifier | Midfielders | Pure vote, sum, against theirs | By the difference, ±0.5 to ±4 | **Yes** |
| Attack modifier | Each forward who didn't score | Pure vote, each | 6.50 +0.5 up to 8.00 +2 | No |
| Keeper's vote | The keeper | Pure vote | The same bands | No |
| Captain | The chosen player | Pure vote | From −2.5 below 4 to +2.5 from 8.50; 0 from 6 to 6.49 | No |
| Fair play (left out for now) | Everyone fielded | No player booked, with eleven rated | A flat bonus | No |

Modifiers can be combined, and their effects add up.

**Sources:**
[how a custom modifier is built](https://www.fantacalcio-online.com/it/pro/modificatori-pro/amp),
[choosing modifiers](https://www.fantacalcio-online.com/it/regole/modificatori-consigli-guida-fantacalcio-esempi/amp),
[defence](https://www.fantacalcio-online.com/it/regole/guida-modificatore-difesa/amp),
[midfield](https://www.fantacalcio-online.com/it/regole/guida-modificatore-centrocampo/amp),
[attack](https://www.fantacalcio-online.com/it/regole/guida-modificatore-attacco),
[captain](https://www.fantacalcio-online.com/it/regole/regola-capitano-modificatore-come-funziona),
[Fantacalcio-Online's rules](https://www.fantacalcio-online.com/en/regole/regolamento-fantacalcio-guida-completa/amp),
[Fantacalcio.it's template for private leagues](https://www.fantacalcio.it/regolamenti/leghe-private).

## Requirements

### Requirement 1: A table of events

**User Story:** As a player, I want every event my league scores to count, at my league's value for each role.

- **R1.1** THE SYSTEM SHALL hold every event a league scores in one table: an event, the points, and the roles they apply to. Any event's
  value MAY differ by role. An event not in a league's table SHALL NOT be scored. Classic SHALL be a ready-made table, with no special
  path through the code.
- **R1.2** THE SYSTEM SHALL price every event in a league's table in a player's value, in the key and in the simulation. A rule
  it holds and doesn't price SHALL NOT exist: if an event has no estimate, it's named as left out (R4.3).
- **R1.3** THE SYSTEM SHALL price the four events it stores today:
  - a penalty missed, for a taker, from his share of the penalties and the chance of a miss;
  - a penalty saved, for a keeper, from the chance his opponents get one and that he saves it;
  - a red card and an own goal, from a starting rate for each role.
- **R1.4** THE SYSTEM SHALL price a clean sheet for an outfield role when a league gives one, from the same fit and the same simulated
  goals as the keeper's.
- **R1.5** THE SYSTEM SHALL price an event that's a share of a known one, such as a set-piece assist or a decisive goal, as a *(start)* share of
  that event's expected count.
- **R1.6** THE SYSTEM SHALL read rules stored in the earlier form, and the decision log lines that hold them, as the same table, with nothing to
  enter again. A league's numbers SHALL stay as they are today, apart from the four events of R1.3.

### Requirement 2: Formula rules

**User Story:** As a player, I want my league's modifiers and captain to count, without anyone writing code for them.

- **R2.1** THE SYSTEM SHALL hold a formula rule as data, always on pure votes:
  - **who counts:** a role or several, the captain, or the best n of a role, with or without the keeper;
  - **how they combine:** a sum, an average, or each player on his own;
  - **who is left out:** nobody, or a player who scored, conceded or saved a penalty, as the league sets it;
  - **the base:** how many players the unit counts, and the stand-in votes for the first missing and for the rest;
  - **a condition:** optionally, only when exactly that many are fielded;
  - **the bands:** rising values, and the points each gives.
- **R2.2** THE SYSTEM SHALL work out every formula rule in each simulated round, after substitutions, from that round's simulated
  votes, and SHALL add its points to the team score before the fantasy goals are worked out.
- **R2.3** THE SYSTEM SHALL offer ready-made entries for the common rules: the *Gazzetta* defence modifier, the attack modifier and the
  captain, at the values above. A user can change any value.
- **R2.4** THE SYSTEM SHALL run no code from a rule: a rule is data, checked against its contract. It SHALL refuse an impossible rule
  with the reason and store nothing, for example bands that don't rise, or points outside the league's range.
- **R2.5** WHERE a rule needs something the simulation doesn't have, such as the opponent's team, THE SYSTEM SHALL treat it as left out
  (R4.3), saying what it needs.

### Requirement 3: The answer under formula rules

**User Story:** As a player, I want to see what my league's rules are worth this round, and how they change my lineup.

- **R3.1** THE SYSTEM SHALL include formula rules in the expected score, the chance of each threshold and the comparison of
  formations.
- **R3.2** THE SYSTEM SHALL say what each formula rule adds on average in this lineup, so that it's bounded, logged and visible.
- **R3.3** WHERE a league uses a captain THE SYSTEM SHALL recommend a captain and a vice from the simulated rounds, by the points
  they'd bring, and a user MAY name their own, with the cost in points as for any override. If the captain has no rating the vice
  counts; if neither has, the rule's stand-in vote applies.
- **R3.4** THE SYSTEM SHALL keep the same result for the same facts and rules, and an override's cost SHALL include the formula rules.
- **R3.5** THE SYSTEM SHALL keep ordering each role by the key, and the formation falls out of the simulation. Since a formula rule can
  make a player's value depend on his team-mates, the answer SHALL say when a marginal choice is close enough for the rule to
  matter, rather than search every combination.

### Requirement 4: Claude as the translator

**User Story:** As a player, I want to paste my league's rulebook and have my Claude set it up, then check what it understood.

- **R4.1** THE SYSTEM SHALL describe the events and formula rules in `set_league_rules`'s schema, and SHALL have one setup step, which asks for
  whatever a question still needs and offers the ready-made entries, so that a player's Claude can translate a rulebook without any parser
  of ours.
- **R4.2** WHEN rules are saved THE SYSTEM SHALL return what's priced and what's left out, and the agent prompt SHALL tell Claude to read
  that back to the user and never to guess a value.
- **R4.3** THE SYSTEM SHALL save a rule it can't express by name, with what it would need, and every answer SHALL say its score leaves
  it out.
- **R4.4** THE SYSTEM SHALL keep the rulebook's text out of storage: only the structured rules and the names of what's left out.
- **R4.5** THE SYSTEM SHALL update the blank league profile and the player guide, and keep the agent prompt within what a Project takes.

### Requirement 5: Cost and limits

**User Story:** As a player, I want answers as fast as today's, whatever my league's rules.

- **R5.1** THE SYSTEM SHALL answer within AT-9's budget of `mvp-lineup`, 3 seconds and 15 KB, for a 25-player squad, seven formations, a
  captain and three modifiers.
- **R5.2** THE SYSTEM SHALL read no new page and call no paid service.
- **R5.3** THE SYSTEM SHALL document how to add an event with a new estimate, as the one case that still needs code.

## Acceptance tests

| Test | What it proves | Requirements |
|---|---|---|
| AT-1 | A league with stored rules needs nothing entered again, old lines in the decision log still read, and its numbers differ only by the four newly priced events, by hand | R1.2, R1.3, R1.6 |
| AT-2 | By hand: a first taker's missed-penalty term, a keeper's saved penalty, a red card and an own goal, in the value and over many simulated rounds | R1.2, R1.3 |
| AT-3 | A league with a clean-sheet bonus for defenders: a defender's value rises by that chance times the points, on the same simulated goals as his keeper; a goal value per role still works | R1.1, R1.4 |
| AT-4 | A set-piece assist and a decisive goal, by hand, set as rows | R1.5 |
| AT-5 | The *Gazzetta* defence modifier, by hand on known votes: the best three and the keeper, each band, a stand-in for a missing defender, and the condition on how many are fielded | R2.1, R2.2 |
| AT-6 | The attack modifier, by hand: each forward on his own, with a scorer left out | R2.1 |
| AT-7 | The captain, by hand: the table; the vice when the captain has no rating; the recommended captain beats the others over the rounds; naming another gives its cost | R3.3 |
| AT-8 | A rule's points reach the fantasy goals: thresholds move, a formation can change because of a modifier, and a total-points league still works | R2.2, R3.1 |
| AT-9 | Each rule's average contribution is in the answer, and the same inputs give the same result | R3.2, R3.4 |
| AT-10 | A rule that needs the opponent, and one with no estimate, are saved as left out with what they need, and named in every answer; `set_league_rules` returns what's priced and what isn't | R2.5, R4.2, R4.3 |
| AT-11 | An impossible rule is refused with its reason, and nothing is stored; a rule can't carry code | R2.4 |
| AT-12 | A 25-player squad, seven formations, a captain and three modifiers answer in under 3 seconds and 15 KB | R5.1 |
| AT-13 | The blank profile names the new settings and the ready-made entries, holds no user's details, and the prompt stays within its budget | R4.1, R4.5 |
| AT-14 | Manual: a rulebook pasted into a Claude app becomes the right rules, read back correctly, with what's left out named | R4 |

## Owner decisions

- **2026-11-07:** the owner asked for league rules to be as flexible as possible without crafting each one in code, and approved this
  slice in place of building the defence modifier and the captain by hand, ahead of recalibration.
- **2026-11-07, these requirements approved,** with three decisions:
  1. **Share-based events:** set-piece assists and decisive goals go in now. Player of the match and the three kinds of assist stay left out until
     a league needs them, because there's nothing to base them on.
  2. **The captain:** the tool recommends a captain and a vice from the simulated rounds, and the user can overrule it, as with any override.
  3. **How far the lineup adapts to a modifier:** it orders by the key and compares formations, as today, and says when a choice is close enough to
     matter (R3.5). Trying swaps can come later, if a real league shows it's worth the time.
- **2026-11-07, one table:** the owner asked whether the basics and custom rules follow one pattern, and whether the setup could be simpler. The
  draft kept ten fixed fields with rows laid over them, which is two ways of saying one thing. So the requirements now have one table, with Classic
  as a ready-made entry, and one setup step. Fair play is left out, which makes the pure vote the only measure.
- **2026-11-07, the slices:** the owner confirmed that Mantra, live forecasts and pundit consensus are out of the MVP, and that everything else in
  `product.md`'s list comes before going online.
