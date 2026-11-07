# Design Document: `mvp-rules` (Phase 2, fourth slice)

Status: **Draft for the owner's approval** · From the approved [requirements](requirements.md)

## Overview

A league's rules become data, read by one engine. A league's events go in a table that the player models read, and its formula
rules run inside the simulated rounds that already draw every player's vote. A player's Claude does the translating, and the tools
validate the result and say what they priced.

The slice adds no page, source or paid service. Rules stored today keep working, and a league that sets nothing new gets today's
numbers, apart from the four events that were never priced.

**What was measured first** (real squad, real round, on the owner's Mac): a full answer takes 1.8 seconds, of which the
simulation is 0.7. Three formula rules, evaluated in each of 70,000 arrangement-rounds, add about 0.8 seconds, for about 2.5 in
all. So they can run in the same loop, with no special machinery.

## What it builds on

- `contracts/xy/league.py`: `LeagueRules` 1.1.0, ten fixed values, and `other_rules`.
- `league/rules.py`: `scoring_for`, which passes six of the ten values to the models.
- `engine/outfield.py`, `engine/keepers.py`: each player's value, key and chance of scoring.
- `engine/simulate.py`: `draw_rounds` draws each round once for the squad, and `field` scores every arrangement on it.
- `mcp/tools/lineup.py`: arrangements, overrides, warnings and the answer. `mcp/tools/league.py`: `set_league_rules`.

## Components

### C1. The rules contract (`contracts/xy/league.py`; R1.1, R1.6, R2.1, R2.4)

`LeagueRules` 1.2.0 only adds, so stored rules load unchanged. Today's ten values stay as the base of the table, with two new lists:

```python
class EventRow(Part):
    event: EventName  # the ten of today, plus set_piece_assist and decisive_goal
    points: float  # -10 to 10
    roles: list[Role]  # empty means every role that event applies to


class Band(Part):
    from_value: float  # this value and up, until the next band
    points: float  # -10 to 10


class Unit(Part):
    role: Role
    best: int | None  # his role's best n by the measure; None counts all of them


class FormulaRule(Part):
    name: Name
    who: list[Unit] | Literal["captain"]
    measure: Literal["pure_vote", "yellow_cards"]
    combine: Literal["average", "sum", "each"]
    leave_out: Literal["nobody", "bonus_or_goal"]
    base: int | None  # how many the unit counts
    stand_in: tuple[float, float] | None  # for the first missing, and for the rest
    only_when_fielded: int | None
    bands: list[Band]  # rising; below the first, no points
```

`LeagueRules` gains `events: list[EventRow] = []` and `formula_rules: list[FormulaRule] = []`. `other_rules` stays, now holding each
left-out rule's name and what it needs.

**No rule can carry code.** Every field is a number or a fixed word, `Part` forbids extra fields, and nothing is evaluated.
Validators refuse bands that don't rise, a `leave_out` with a measure it can't apply to, `each` with a `base`, and a keeper-only
event on another role, each with its reason.

The parts follow Fantacalcio-Online's own builder, so a rule from a real rulebook fits as written. For example, the *Gazzetta*
defence modifier is `who=[{role: P}, {role: D, best: 3}]`, `pure_vote`, `average`, `base=4`, and fair play is every role,
`yellow_cards`, `sum`, `only_when_fielded=11`, with bands that give the bonus at zero.

### C2. The table of events (`league/rules.py`, `engine/rank.py`; R1.1, R1.2, R1.5)

`scoring_for(rules, role)` builds `Scoring` from the table: the base values, then any row for that role. `Scoring` gains
`penalty_missed`, `penalty_saved`, `own_goal`, `red` and an outfield player's `clean_sheet` and `goal_conceded`, which are zero unless a
row sets them.

**A share-based event is one row of one table** (`engine/constants.py`), an event, its base and a share, with no logic of its own:

| Event | Of | Share *(start)* | Effect on a base event's worth | Where the share comes from |
|---|---|---:|---|---|
| Decisive goal | Goals | 0.20 | Added on top | The odds model: about 0.57 decisive goals in a match of 3 goals |
| Set-piece assist | Assists | 0.25 | Replaces the assist's value | The rough share of Serie A's goals from dead balls, excluding penalties |

The models then read one effective value for a goal or an assist, so these rows add no draws. The recalibration slice owns the numbers.

### C3. The four unpriced events (`engine/outfield.py`, `engine/keepers.py`, `engine/constants.py`; R1.3, R1.6)

| Event | Expected per start | Starting values *(start)* | Worth to a typical player |
|---|---|---|---|
| Penalty missed | Rate × (1 − conversion) × minutes × his share | The existing 0.15 and 0.78 | About −0.09 for a first taker |
| Penalty saved | Opponents' rate × (1 − conversion) × share of misses saved | 0.80 of misses (7 of 8 so far this season) | About +0.08 for every keeper |
| Red card | A rate per rated game, by role | D 0.005, C 0.003, A 0.002, P 0.001 (this season: 9 in 2,882) | About −0.005 |
| Own goal | A rate per rated game, by role | D 0.005, others 0.001 (22 in a recent season) | About −0.01 for a defender |

**They enter the simulation as expected values, not draws.** Each is too rare to change the spread, and a fixed term keeps the same
random stream, so a league that sets nothing new can be compared with today's numbers exactly (AT-1). A player's simulated mean still
matches his model (P4 of `mvp-lineup`).

A cameo's goal is worth `6.8 + the league's goal value` instead of a fixed 9.8, which assumed +3: another hard-coded rule found while
reading the code.

### C4. An outfield role's clean sheet (`engine/outfield.py`, `engine/simulate.py`; R1.4)

`OutfieldInputs` gains the opponent's xG, and a defender's `E_start` adds the clean-sheet chance and goals conceded at the league's
values, when a row sets them. In the simulation an `Outfielder` knows which side it's on, so it reads the opponent's goals from the same
draw as his keeper: the link is the one that already ties a striker's goal to the keeper who concedes it.

### C5. Formula rules (`engine/formula.py`; R2.1, R2.2)

A pure module with one job. Given a rule and who was fielded this round, it returns the points:

1. Take the players in the unit: all, or the best n by the measure.
2. Leave out anyone the rule excludes, and fill any gap up to `base` with the stand-in votes.
3. If `only_when_fielded` isn't met, there are no points.
4. Combine them, or take each on his own, and look the value up in the bands with `bisect`.

**The simulation supplies what it needs.** `draw_rounds` also yields a light mark per player when a league has formula rules: his pure
vote, whether he was booked, and whether he scored, conceded or saved a penalty. A cameo's pure vote is 5.5 for a flat cameo, 5.75 for a
priced one and 6.8 with a goal. A league without formula rules builds no marks and pays nothing.

**After substitutions.** `field` already returns the moves, so the fielded eleven is known. Fantacalcio-Online adds modifier totals to the
team score before goals are worked out, and describes the total as including bench players who came on, so that's the order here. Each
arrangement keeps a running total per rule, which gives what each is worth on average (R3.2).

### C6. The captain (`engine/formula.py`, `mcp/tools/lineup.py`; R3.3)

The captain's points depend on who is captain, not on who else plays, so they don't need a pass per candidate. During the rounds, the
loop keeps each of the top five starters' band points by key. At the end, each arrangement takes its best candidate as captain and the
next as vice, with the vice's points on the rounds the captain has no rating, and adds that array to its totals before summarising.
That's about 50,000 lookups, and it needs no second pass over the rounds.

`best_lineup` gains `captain`, which names a player and shows the cost as any override does. The answer names the captain and the vice.

### C7. The answer and the log (`mcp/tools/lineup.py`, `lake/decision_log.py`; R3.1, R3.2, R3.4, R3.5)

- **`Lineup`** gains `rules_worth` (each formula rule's average in this lineup) and `captain` and `vice`. `Simulated` carries the rule
  totals, so overrides and the formation comparison include them.
- **`Decision`** gains optional `rules_worth` and `captain`, so that what was told is logged.
- **A close call that a rule could tip (R3.5):** when a coin-flip call is about a player in a formula rule's unit, the call says so, for
  example "the defence modifier could tip this". There's no search over combinations, as the owner decided.
- **The order stays by key.** Formations are compared with the rules included, so a modifier can change the formation (AT-8).

### C8. The translator (`mcp/tools/league.py`, `league/rules.py`, `docs/`; R2.3, R2.5, R4, R5.3)

- **`set_league_rules`** returns `SavedRules`: the stored rules, `priced` (every event and formula rule that counts) and `left_out`
  (each name and what it needs). Its schema's field descriptions carry the vocabulary, so the agent prompt needs only one more sentence;
  it has fewer than 500 characters of budget left.
- **Ready-made entries:** `READY_MADE` in `league/rules.py` holds the *Gazzetta* defence modifier, the attack modifier, the captain and
  fair play at the researched values, and they're offered in the setup step's `also`, replacing today's three names.
- **The agent prompt and profile:** paste the rulebook, translate it into these forms, read back `priced` and `left_out`, and never guess a
  value. Rules that need the opponent, or have no estimate, go in `other_rules` with what they need. The profile's "Other rules" section
  points to the same.
- **`docs/league-rules.md`:** what a rule can be, with worked examples, and the one case that needs code: an event with a new estimate
  (R5.3).
- **Method:** §A1 and §A7 say formula rules run in the simulated rounds; §A4 and §A6 gain the four events.

## Error handling

| Condition | Behaviour |
|---|---|
| An impossible rule | Refused with the reason; nothing stored |
| A rule that needs the opponent, or has no estimate | Saved in `other_rules` with what it needs, and named in every answer |
| Rules stored by an earlier version | Read as they are, with no rows and no formula rules |
| A unit with nobody and no stand-in vote | The rule gives no points that round |
| The captain and the vice both without a rating | The rule's stand-in vote applies; without one, no points |
| A named captain who isn't in the squad | Refused with the reason, like any override |

## Correctness properties

These Hypothesis tests are required:

| # | Property | Requirements |
|---|---|---|
| P1 | A value in a band gets that band's points, for any rising bands, and below the first band there are none | R2.1 |
| P2 | A formula rule whose bands are all zero leaves every round's total as it was | R2.2 |
| P3 | A row for one role never changes another role's values | R1.1 |
| P4 | Over many rounds, a player's mean still matches his model's value with the new events, for any table | R1.2 |
| P5 | The same inputs give the same results with any rules | R3.4 |
| P6 | Stored rules of the earlier version load, and give the same `Scoring` apart from the four events | R1.6 |
| P7 | A captain's points never exceed the top band or fall below the bottom one, and the recommended captain is never worse over the rounds than another candidate | R3.3 |

## Testing strategy

- **Unit, in `tests/unit/rules/`:** the table, each of the four events, the share-based events, and `formula.py` by hand on known votes.
- **Property, in `tests/property/rules/`:** P1 to P7.
- **Integration, in `tests/integration/rules/`:** the tools end to end on the invented squad from `tests/lineup_harness.py`.
- **Acceptance, in `tests/acceptance/rules/`:** AT-1 to AT-13, automated, and AT-14 by hand.
- **Mutation:** `engine/formula.py` falls under `engine/*`, and the new fast test folders join the mutation run's selection.

Rules and squads in tests are invented. A real rulebook or league name never reaches the repository.

## Cost

$0. No new pages or requests. The answer grows by a few hundred bytes per rule; the rulebook's translation uses the player's own Claude plan.

## Build order (input to tasks.md)

1. **The table of events:** the contract, the four events, an outfield clean sheet and share-based events.
2. **Formula rules, pure:** the contract's rules, `formula.py`.
3. **In the simulation and the answer:** marks, rule totals, the formation comparison, overrides, what each is worth.
4. **The captain.**
5. **The translator:** the read-back, ready-made entries, the prompt, the profile and the docs.
6. **A real check and this slice's sign-off.**

## Open points for the owner

None need a decision now. Three calls the agent made, for the owner to overrule if they disagree:

- **Rare events as expected values, not draws:** simpler and cheaper, and today's numbers stay comparable.
- **Starting values for the new events:** set from this season's figures and published counts; recalibration owns them from here.
- **If the budget gets tight:** score every formation over the first 2,000 rounds and keep only the best three after that. It isn't needed on
  today's measurements, so it isn't built.
