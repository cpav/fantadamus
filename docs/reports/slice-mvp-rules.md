# Slice report: `mvp-rules`

2026-11-09 · Phase 2, the first slice before going online · **For the owner's sign-off** (task 6.4): merging this report's pull
request records it

A league's rules are now data, read by one engine. Player figures, names and the answers' numbers for a real squad aren't
reproduced here: they stay in private notes.

## What the slice delivered

- **One table of events.** Each event's points, for each role. Classic is a ready-made table with no special path. Four
  events that were stored and never priced now count: a missed penalty, a saved penalty, an own goal and a red card. A
  clean sheet can count for any role, and a decisive goal or a set-piece assist are priced as shares.
- **Formula rules as data.** Who counts, how their pure votes combine, who's left out, a base with stand-in votes, a
  condition on how many are fielded, and bands. Every part is a number or a fixed word, never code. They run in every
  simulated round after substitutions, so they reach the fantasy goals, the thresholds and the formation.
- **The answer under formula rules.** What each rule adds on average, an override's cost with the rules in it, and a close
  call in a role a rule counts says the rule could tip it.
- **The captain.** The captain and vice who bring the most over the rounds, the vice counting when the captain has no
  rating. A named captain starts, keeps the best vice, and shows his cost. A league has one captain rule.
- **Claude as the translator.** A player pastes their rulebook, their Claude turns it into events and formula rules, and
  `set_league_rules` reads back what's priced and what's left out. One setup step asks for whatever a question still needs
  and offers ready-made entries for the defence modifier, the attack modifier and the captain. Every answer names what its
  numbers leave out. [`docs/league-rules.md`](../league-rules.md) says what a rule can be, and the one case that needs code.

## Real data

Round 11 at its lock, from Claude Code, on a copy of the owner's league folder and with a temporary decision log (task 6.1).

- **The owner's league, as stored,** gets the same formation and the same eleven as before the slice. Its expected score is a
  little lower, all of it from the four events now priced. The result is identical to the one after task 1, so tasks 2 to 5
  changed nothing for a league without formula rules.
- **A made-up league on the same squad, with the ready-made defence modifier and captain,** gets a sensible lineup: the same
  formation and eleven, with the modifier adding about a point on average and the captain little, since a pure vote near 6
  earns nothing in its bands. A formation with three defenders gets nothing from the modifier, as it should. The five-defender formation gets the most from it but still ranks
  second. The captain and the vice are a forward and a midfielder among the starters with the highest keys.
- **The read-back of the owner's real rules** names every event correctly, with nothing left out and no setup step needed.
- No bug was found.

| Answer, in CPU seconds | Time | Size |
|---|---:|---:|
| The owner's league, as stored | 1.7 s | 12.6 KB |
| The same squad with a defence modifier and a captain | 2.4 s | 12.8 KB |
| The same squad with a captain and three modifiers (task 4, a busy machine) | 3.2 s | 13.3 KB |
| The invented squad with a captain and three modifiers (AT-12, a busy machine) | 2.1 s | under 15 KB |

The machine was busy on the day: the same answer without rules took 1.4 s two days earlier.

### AT-14: a real rulebook

*To be filled in by the owner's check (task 6.2): a rulebook pasted into a Claude app, what Claude read back, and whether it
matched, without the league's details.*

## Numbers

| Measure | Value |
|---|---|
| Tests | 1,129 (1,039 at the end of `mvp-lineup`) |
| Coverage | 98.7% of lines and 95.6% of branches; the floor is 90% |
| `make check` (19 checks) | about 4.5 minutes on the owner's Mac |
| CI per pull request | 2 to 3.5 minutes, against a 5-minute budget |
| Code | 10,287 lines of product code, 2,506 of checks and hooks, about 18,400 of tests |
| Agent prompt | 11,606 characters, against a 13,000-character budget |

Each code task also broke its own code on purpose, from a green baseline, before its report: 93 breaks across the five tasks,
every one caught by a test once the gaps the first runs found were filled.

## Mutation testing

`make mutate` on the core modules (`engine/*` and calibration), on fast tests only, within its 10-minute limit: **2,138 of
2,205 mutants killed (97.0%)**, against 1,658 of 1,702 (97.4%) at the end of `mvp-lineup`. The run found two real gaps from task 1:
no fast test checked that a first taker's value counts his missed penalties, or a keeper's his saved ones. The pure tests of
AT-2, AT-3 and AT-4 now join the fast selection, and both mutants die.

Every survivor was read, and none changes a result:

| Survivors | Why they're harmless |
|---:|---|
| 24 | `strict=` on a `zip` of lists that are always the same length |
| 12 | `<` against `<=` on a random draw or a bound, where a tie doesn't arise |
| 9 | A default that can't be reached, or one falsy value swapped for another |
| 5 | Odds arithmetic normalised right after, or a tail too small to matter |
| 5 | The captain's path: an argument it never reads, the path without a captain, or a candidate who can never win |
| 4 | A keeper's term multiplied by zero, since a keeper has no cameo |
| 4 | A cache made weaker: the same results, with more work |
| 4 | A starting value reset each round, or marks built and then dropped |

## Acceptance tests

| Test | Proves | Result |
|---|---|---|
| AT-1 | Stored rules need nothing entered again, old log lines read, and the numbers differ only by the four events | Passed |
| AT-2 | A missed penalty, a saved penalty, a red card and an own goal, by hand and over the rounds | Passed |
| AT-3 | A clean-sheet bonus for defenders, on the same simulated goals as the keeper | Passed |
| AT-4 | A set-piece assist and a decisive goal, as rows | Passed |
| AT-5 | The defence modifier on the keeper and the three best defenders, by hand | Passed |
| AT-6 | The attack modifier, by hand | Passed |
| AT-7 | The captain: the table, the vice, the best pair, a named captain's cost | Passed |
| AT-8 | A rule's points reach the fantasy goals and can change the formation | Passed |
| AT-9 | Each rule's worth in the answer and the log; the same inputs, the same result | Passed |
| AT-10 | Left-out rules saved with what they need and named in every answer; the read-back | Passed |
| AT-11 | An impossible rule refused with its reason; a rule can't carry code | Passed |
| AT-12 | A captain and three modifiers in under 3 seconds and 15 KB | Passed on the invented squad; see above for a real one |
| AT-13 | The blank profile, the ready-made entries and the prompt's budget | Passed |
| AT-14 | Manual: a real rulebook becomes the right rules, read back correctly | *The owner's check* |

## Cost

$0. Nothing runs on AWS and no paid service was added (R5.2). No new page is read. A question uses the player's own Claude
plan.

## Open risks

- **Speed with many rules on a real squad.** A captain and three modifiers took 3.2 s on a busy machine, against a 3-second
  budget; about 2.7 s at a normal machine's speed. The design's fallback is ready if a real league needs it: every formation
  for 2,000 rounds, then only the best three.
- **A modifier's worth rests on how much votes vary,** a *(start)* constant. The recalibration slice should check the spread
  of simulated votes against real ones, since bands turn small differences into points.
- **The ready-made entries come from one platform's guides.** Leagues set their own values. The read-back is the check, and
  the prompt tells Claude never to guess a value.
- **Formula rules count in the full lineup only.** "X or Y?" and an outlook say their numbers leave them out.
- **Rules that need the opponent's team** stay left out by name until slice 7.
- **Players must paste the new agent prompt and restart Claude Desktop.** A running server keeps its old code until then.

## Decisions for the owner

1. **Sign off this slice?** Recommendation: yes, once AT-14 is done.
2. **The speed fallback?** Recommendation: not now. Add it only if a real league's answer goes over 3 seconds.
3. **What comes next?** Recalibration is next in `product.md`, but it changes the numbers, so it waits until a real round has
   been answered on this slice's numbers: round 12. Recommendation: start the lineup review in the meantime, since it
   changes no numbers, and take recalibration once round 12 is scored.

## Next

The slices left before going online, in `product.md`'s order: recalibration, the lineup review, match cards, new sources,
alerts, and the rules that need the opponent's team. Then Phase 3: online, with nothing to install.
