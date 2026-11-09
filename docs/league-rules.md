# League rules

There's no single Fantacalcio rulebook: each league writes its own. Fantadamus holds a league's rules as data, read by
one engine, so a new league needs no new code wherever the simulation already has what a rule measures. This page is
what a rule can be. Your Claude does the translating: paste your rulebook, or fill in the
[league profile](league-profile-template.md), and it calls `set_league_rules`, which reads back what's priced and
what's left out. Check that reading: a value Claude guessed is a wrong number in every answer.

A league's rules have three parts: a table of **events**, **formula rules** for modifiers and the captain, and what a
**lineup** needs (thresholds, the bench, substitutions and formations).

## Events

One row for each thing the league scores: the `event`, its `points` (a bonus from 0 to 10, a malus from −10 to 0) and
the `roles` it applies to (P, D, C, A). For different values by role, give one row per value. An event left out isn't
scored. Fantacalcio Classic is a ready-made table, offered as the starting choice.

| Event | What it is | How Fantadamus prices it |
|---|---|---|
| `goal` | A goal scored | His share of his team's expected goals (method §A4) |
| `decisive_goal` | A goal that wins or draws the match, on top of the goal's own points | A share of his goals *(start)* |
| `assist` | An assist | His share of his team's expected assists |
| `set_piece_assist` | An assist from a set piece, in place of the assist's points | A share of his assists *(start)* |
| `penalty_scored` | A penalty scored, in place of the goal bonus | His share of his club's penalties, by the takers' list |
| `penalty_missed` | A penalty missed | The same share, times the chance of a miss |
| `penalty_saved` | A penalty saved, for keepers | The opponents' penalties, times the chance of a save |
| `own_goal` | An own goal | A rate per rated game for each role *(start)* |
| `yellow_card` | A yellow card | His own rate of yellow cards |
| `red_card` | A red card | A rate per rated game for each role *(start)* |
| `goal_conceded` | Each goal conceded, usually a keeper's | The opponent's expected goals in the same match |
| `clean_sheet` | A clean sheet, usually a keeper's | The chance the opponent doesn't score |

## Formula rules

A formula rule works on a round's **pure votes**: the ratings alone, without bonuses or maluses. It's worked out in
every simulated round after substitutions, so a substitute who came on counts, and its points join the team's score
before the goal thresholds. Every part is a number or a fixed word, never code:

- `name`: what the league calls it.
- `who`: the roles it counts, as units, or `captain`. A unit has its `role`, optionally its `best` n by pure vote,
  and optionally `at_least` and `at_most`: the rule gives points only when that many of the role are fielded.
- `combine`: `average` or `sum` the votes, or take `each` player on his own.
- `leave_out`: `nobody`, or `bonus_or_goal`, a player who scored, conceded or saved a penalty.
- `base`: how many players the rule counts. With more, it keeps the best; with fewer, it fills the gap with the
  `stand_in` votes (*voti d'ufficio*), the first for the first missing player and the second for the rest. Without
  stand-in votes it averages those present.
- `bands`: rising values and the points each gives, from that value up to the next band's. Below the first, none.

A cameo's pure vote is 5.5 for a flat cameo, 5.75 for a rated one and 6.8 with a goal. A league has one captain rule.
The answer says what each rule adds on average in the lineup, and a close call in a role a rule counts says the rule
could tip it.

## Worked examples

**Defence modifier** (ready-made): the keeper and the three best defenders, averaged, only with at least four
defenders fielded.

```json
{"name": "defence modifier", "who": [{"role": "P"}, {"role": "D", "best": 3, "at_least": 4}], "combine": "average",
 "bands": [{"from_value": 6.0, "points": 1}, {"from_value": 6.5, "points": 3}, {"from_value": 7.0, "points": 6}]}
```

A keeper on 6.5 and defenders on 7, 6.5, 6 and 5.5: the best three are 7, 6.5 and 6, so (6.5 + 7 + 6.5 + 6) / 4 =
6.5, which gives +3. With three defenders fielded it gives nothing.

**With stand-in votes**: the same, but counting four whatever happens, with 5 for the first missing player and 4.5 for
the rest: add `"base": 4, "stand_in": [5.0, 4.5]`. A keeper on 7 and two defenders on 7 give (7 + 7 + 7 + 5) / 4 = 6.5.

**Attack modifier** (ready-made): each forward who didn't score, on his own.

```json
{"name": "attack modifier", "who": [{"role": "A"}], "combine": "each", "leave_out": "bonus_or_goal",
 "bands": [{"from_value": 6.5, "points": 0.5}, {"from_value": 7.0, "points": 1}, {"from_value": 7.5, "points": 1.5},
           {"from_value": 8.0, "points": 2}]}
```

Forwards on 6.5, 7 and 8, the last of whom scored: 0.5 + 1 = +1.5.

**Captain** (ready-made): the captain's pure vote, his vice's when he has none; if neither has one, the rule's
stand-in vote, and without one no points. From −2.5 below 4 to +2.5 from 8.5, by half points, and nothing from 6 to
6.49: `{"name": "captain", "who": "captain", "combine": "each", "bands": [...]}`. Fantadamus recommends the captain
and the vice who bring the most over the simulated rounds; name your own and it says what that costs.

**A midfield sum**: the midfielders' votes added up, +1 from 24 and +2 from 26:
`{"name": "midfield sum", "who": [{"role": "C"}], "combine": "sum", "bands": [{"from_value": 24, "points": 1},
{"from_value": 26, "points": 2}]}`. Four midfielders on 6, 6.5, 6.5 and 6 make 25: +1.

## What's left out

Some rules need something the simulation doesn't have. They go in `other_rules`, each as a name with what it needs,
such as "home factor: needs the opponent's team", and every answer says its score leaves them out:

- anything measured against the opponent's team: the classic defence modifier, the midfield modifier, the home factor,
  the rule of 59, and draw or superiority bonuses (a later slice);
- fair play, the one common rule that measures something other than the pure vote;
- any event Fantadamus has no estimate for, such as player of the match.

## Adding an event with a new estimate

This is the one case that still needs code: an event the engine can't estimate from what it already simulates. For
example, player of the match would need how often a player is his match's best.

1. Add it to `EventName` and `EVENT_MEANINGS`, and to `_BONUSES` if it's a bonus, in
   `src/fantadamus/contracts/xy/league.py`, with a version bump and a CHANGELOG entry.
2. Give `Scoring` a field in `src/fantadamus/engine/rank.py`, and fill it in `scoring_for` in
   `src/fantadamus/league/rules.py`.
3. Estimate it: an expected count per start in `src/fantadamus/engine/outfield.py` or `keepers.py`, its points in
   `src/fantadamus/engine/points.py`, and any constant in `src/fantadamus/engine/constants.py`, marked *(start)*. If
   it should move the spread and not only the mean, draw it in `src/fantadamus/engine/simulate.py`.
4. Write the method's line in `docs/method.md`, add it to the league profile and this page, and test it by hand and
   with the properties that a row for one role changes no other and that a player's mean still matches his value.
