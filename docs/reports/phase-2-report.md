# Phase 2 report: the whole advisor, slice by slice

2026-11-24 · Specs `mvp-collect` to `mvp-fixes`, eleven slices · **Signed off by the owner on 2026-11-24** ("Sign off
Phase 2")

Phase 2 took Fantadamus from one question about two forwards to every feature the MVP plans before going online. It now
collects the round's facts itself, on a schedule; answers "X or Y?" for every role; picks the full lineup under a league's
own rules; puts a match on one screen; reviews a fielded lineup after the round; learns from the rounds it scores; and tells
the owner's Mac when the news changes the lineup. It was built in eleven slices between 30 October and 24 November 2026,
each its own spec with its own report and the owner's sign-off, and it ended with round 12 run end to end on the owner's
Mac.

Player figures, names and the owner's league aren't reproduced here: the real-data numbers are counts and scores.

## What Phase 2 delivered

- **Fantadamus collects for itself.** A polite fetcher reads eleven kinds of fact from three sites, Fantacalcio-Online,
  Fantacalcio.it and Wikipedia, when an answer needs them and on a launchd schedule every 15 minutes. Claude reads only
  what the collector couldn't, through `read_page` and the submit tools.
- **Every role.** "X or Y?" for any two players of one role, and one player's outlook, as forecasts: how sure each number
  is, how it moved since the last answer, and where it came from.
- **The full lineup under a league's own rules.** The eleven, the bench in order, the formation and the captain, simulated
  over 10,000 rounds for the expected score and the chance of each threshold. A league's rules are data: a table of events
  by role, and formula rules such as the modifiers, which the player's Claude translates from the rulebook and reads back.
- **Match cards and the round at a glance,** with rest days, European fixtures, injuries and bans as context that moves no
  number.
- **The review after a round:** the real score the way the league scores it, what each choice against the advice was
  expected to cost and what it did, and the league app's total beside the count.
- **Calibration.** Every published chance is logged and scored once its round is over, beside the market's, and
  `fantadamus recalibrate` proposes starting values for the owner to approve. The first two were approved on 12 November.
- **Alerts.** A notification on the Mac when, in the last day before a round, a scheduled run's news changes the user's
  lineup.
- **Speed for a season.** A store adds its rows instead of rebuilding its table, and an answer reads only what it uses. At
  a season's size a read is stored in 0.47 s and a lineup answers in 0.70 s, against budgets of 2 and 3 seconds.

## The slices

| Slice | What it added | Signed off | Pull requests |
|---|---|---|---|
| [`mvp-collect`](slices-mvp-collect-and-roles.md) | The polite fetcher, the round page's reader, `read_page`, `collect` and the schedule; answers as forecasts | 2026-11-04 | #24 to #42 |
| [`mvp-roles`](slices-mvp-collect-and-roles.md) | Every role: the statistics page, each role's priors, the keeper model, `player_outlook` | 2026-11-04 | #43 to #53 |
| [`mvp-lineup`](slice-mvp-lineup.md) | Squads and rules, `best_lineup` simulated, overrides, a round that scores itself, the penalty takers watched, `make mutate` | 2026-11-07 | #54 to #80 |
| [`mvp-rules`](slice-mvp-rules.md) | A league's rules as data: one table of events, formula rules, the captain, Claude as the rulebook's translator | 2026-11-09 | #81 to #89 |
| [`mvp-review`](slice-mvp-review.md) | `review_round`: the real score, each decision's expected cost and real result, the record of overrides | 2026-11-11 | #90 to #100 |
| [`mvp-cards`](slice-mvp-cards.md) | `match_card` and `round_overview`; the table's record and form | 2026-11-11 | #101 to #113 |
| [`mvp-recalibrate`](slice-mvp-recalibrate.md) | Calibration sets, the starting map, checks where a value wasn't fitted, the market beside ours | 2026-11-12 | #114 to #124 |
| [`mvp-sources`](slice-mvp-sources.md) | Other competitions and rest days, injury and ban detail, three desks' ratings and rater bias; ADRs 0007 and 0008 | 2026-11-15 | #125 to #136 |
| [`mvp-alerts`](slice-mvp-alerts.md) | The check after a scheduled run, and a notification through macOS's own `osascript` | 2026-11-18 | #137 to #142, #155 |
| [`mvp-store`](slice-mvp-store.md) | Silver in month files that a store appends to; an answer reads each page's newest submission | 2026-11-18 | #145 to #154 |
| [`mvp-fixes`](slice-mvp-fixes.md) | The five faults round 12 found | 2026-11-24 | #157 to #164 |

Between them: four follow-ups to Phase 1 (#20 to #23), and the docs brought up to date before round 12 (#156).
The [review before Phase 3](review-before-phase-3.md) came in with `mvp-store`'s requirements (#145). 141 pull requests
were merged, #20 to #164.

## Real rounds

| Round | What it tested |
|---|---|
| 10 | The first round scored: only the chance of starting, since nothing had been read before its kickoffs ([its report](calibration-round-10.md)) |
| 11, 6 to 9 November | Every role, and the full lineup on the owner's real squad and rules: the owner's eleven matched the advice in 10 of 11 places. After it, from Claude Code on its stored facts: the first review, the cards, the alerts replayed and the first recalibration |
| 12, 21 to 23 November | The whole product, end to end on the owner's Mac with the schedule installed |

### Round 12, end to end

The schedule was installed on the owner's Mac on 18 November, and round 12 was asked about, played, reviewed and scored the
way the MVP is meant to run:

- **The answers.** From 18 to 21 November the owner asked Claude Desktop for the lineup, comparisons, an outlook, a card
  and the overview. Every number Claude gave matched the decision log's.
- **The schedule** ran every 15 minutes while the Mac was awake. The Mac slept through much of the three days before the
  lock, and launchd skips the runs a sleeping Mac misses.
- **One real alert,** seven hours before the lock, after a run that stored new lineups: six changes to the owner's call.
  The owner saw it.
- **After the round,** the owner reviewed the fielded lineup with the league app's total, and the round was scored on
  24 November.

It found five faults, none of them in the numbers. `mvp-fixes` fixed them:

| Fault | Fixed in |
|---|---|
| A run that woke from sleep with no network couldn't read robots.txt, and that failed try counted as the pages' read: two sites' pages would have waited 12 to 24 hours | #159 |
| The `collect` tool took 6 of the collector's 11 facts, and its description named three pages | #160 |
| A lineup quoted injury detail without the injured page among its sources, and the overview and the review had no sources | #161 |
| A penalty note didn't say when the taker listed ahead was out | #162 |
| The review compared the league app's total but didn't keep it, so the season couldn't count how often they agreed | #163 |

On a copy of the owner's lake, 64 of 77 answers were identical after the fixes, and the other 13 changed only where the
fixes meant them to: sources, the "updated" times that follow from them, penalty notes, and the review's new fields.

## Calibration

Every chance an answer gives is logged and scored once its round is over (method §A8). Each cell gives the Brier score,
where lower is better; the score of always guessing the round's average; and how many players it covers. Round 10's report
is [committed](calibration-round-10.md); rounds 11 and 12 are scored privately, beside the lake, and summarised here.

**The model, on every player:**

| Chance | Round 10 | Round 11 | Round 12 |
|---|---|---|---|
| Starting | 0.117 against 0.243, 527 | 0.104 against 0.245, 506 | 0.096 against 0.242, 531 |
| Getting a rating | not scored: nothing was read before its kickoffs | 0.137 against 0.250, 538 | 0.134 against 0.250, 538 |
| Scoring, if he starts | | 0.084 against 0.083, 196 | 0.089 against 0.103, 198 |
| A keeper's clean sheet, if he starts | | 0.159 against 0.160, 20 | 0.168 against 0.210, 20 |

**What users were told,** in the answers they asked for: in round 12, starting 0.128 against 0.227 over 106 chances, a
rating 0.144 against 0.213 over 107, and scoring 0.076 against 0.087 over 62; in round 11, starting 0.113 against 0.212
over 36. One override was logged, in round 12.

**The market:** the match chances from the odds held before each kickoff, as the cards show them, over ten matches a
round.

| Chance | Round 11 | Round 12 |
|---|---|---|
| A home win | 0.178 against 0.240 | 0.160 against 0.240 |
| A draw | 0.205 against 0.210 | 0.155 against 0.160 |
| An away win | 0.142 against 0.210 | 0.120 against 0.160 |
| A side's clean sheet, 20 sides | 0.159 against 0.160 | 0.168 against 0.210 |
| Three goals or more | 0.284 against 0.250 | 0.206 against 0.240 |
| Both teams score | 0.285 against 0.240 | 0.250 against 0.240 |

Round 10 has none: no odds were stored before its kickoffs. Ten matches say little; they're the yardstick for later
rounds. The players' chances of scoring have no market beside them yet: the anytime-scorer odds trial (ADR-0008) waits
for the owner's API key.

**The chance of starting, by bucket:** the chance said on average, then the share that started, then how many players.

| Said | Round 10 | Round 11 | Round 12 |
|---|---|---|---|
| 0 to 10% | 1% → 3%, 116 | 0% → 0%, 71 | 4% → 2%, 175 |
| 10 to 20% | 17% → 3%, 36 | 17% → 4%, 45 | 14% → 9%, 67 |
| 20 to 30% | 25% → 4%, 52 | 25% → 7%, 69 | 24% → 26%, 19 |
| 30 to 40% | 33% → 25%, 53 | 32% → 11%, 57 | 35% → 32%, 25 |
| 40 to 50% | 44% → 46%, 41 | 44% → 24%, 37 | 45% → 50%, 14 |
| 50 to 60% | 55% → 64%, 25 | 55% → 57%, 14 | 57% → 44%, 16 |
| 60 to 70% | 65% → 35%, 23 | 65% → 82%, 28 | 62% → 57%, 35 |
| 70 to 80% | 74% → 72%, 29 | 75% → 75%, 24 | 75% → 72%, 40 |
| 80 to 90% | 86% → 81%, 47 | 86% → 83%, 48 | 85% → 89%, 28 |
| 90 to 100% | 91% → 92%, 105 | 92% → 93%, 113 | 92% → 96%, 112 |

Round 12 is the first round scored after the starting map approved on 12 November, and the first it wasn't fitted on.
Between 10% and 40%, where rounds 10 and 11 said about a quarter and about one player in eleven started, round 12 said 21%
on average and 17% started, each bucket within 6 points. At the top the outlets were right all along.

**The chance of getting a rating, by bucket:**

| Said | Round 11 | Round 12 |
|---|---|---|
| 0 to 10% | 0% → 5%, 103 | 2% → 5%, 118 |
| 10 to 20% | 17% → 6%, 34 | 11% → 0%, 2 |
| 20 to 30% | 21% → 0%, 1 | |
| 30 to 40% | 30% → 100%, 1 | 37% → 16%, 19 |
| 40 to 50% | 47% → 14%, 14 | 43% → 30%, 27 |
| 50 to 60% | 54% → 44%, 39 | 55% → 28%, 100 |
| 60 to 70% | 64% → 34%, 98 | 65% → 50%, 32 |
| 70 to 80% | 74% → 61%, 46 | 75% → 72%, 39 |
| 80 to 90% | 85% → 94%, 51 | 84% → 86%, 66 |
| 90 to 100% | 94% → 95%, 151 | 95% → 96%, 135 |

The middle is overstated in both rounds. In round 12, 100 players were given 50 to 60% and 28 got a rating; 93 of them
were defenders and midfielders unlikely to start, whose chance rests on the share of cameos (decision 3). Scoring and clean
sheets were no better than the average in round 11 and a little better in round 12, on small samples.

## The exit gate

| Criterion (`quality.md`) | Evidence | Result |
|---|---|---|
| Each slice's acceptance tests pass | 119 acceptance tests in the eleven slices, each in its slice report | Met, with one manual test closed on a gap the owner accepted at sign-off (below) |
| All six of method §A9 | Tests 2, 4 and 6 in Phase 1; test 3, and test 6 for defenders, in `mvp-roles`; tests 1 and 5 in `mvp-lineup` | Met |
| A calibration report for at least one real round | [Round 10's](calibration-round-10.md), and rounds 11 and 12 above | Met |
| The phase report: tests, coverage, quality, cost, open risks and a mutation run | This report | Signed off on 2026-11-24 |

- **The gap: `mvp-collect` AT-10,** a real question on each player's Mac before and after an official lineup, ran on the
  owner's Mac only. The second player hasn't installed Fantadamus; Phase 3 removes the install.
- **Closed with round 12: `mvp-alerts` AT-5,** a notification on the owner's Mac. The sample showed on 18 November, and the
  owner saw the schedule's real alert of 21 November (confirmed on 2026-11-24).

Two manual tests were closed from Claude Code on round 11's stored facts, at the owner's request (2026-11-11):
`mvp-review` AT-8 and `mvp-cards` AT-11. One earlier acceptance test changed, with the owner's yes: `mvp-lineup` AT-18's
expected penalty note (2026-11-24).

## Numbers

| Measure | End of Phase 1 | End of Phase 2 |
|---|---|---|
| Tests | 487 | 1,724: 1,714 pass, and 10 are skipped without the private data, as in CI |
| Coverage | 98.4% of lines, 94.1% of branches | 98.8% of lines, 96.1% of branches; the floor is still 90% |
| `make check` (19 checks) | about 100 s | 9¼ minutes on the owner's Intel Mac on 24 November, 8 of them the tests; 7.4 minutes for `mvp-fixes`' report |
| `make test-fast` | 18 s, at the end of Phase 0 | 34 s, against 20 |
| CI per pull request | 73 to 100 s | 190 to 385 s over the last ten; the median is 257 s against the 5-minute budget, and three went over it |
| Code | 3,634 lines of product code, 2,506 of checks and hooks, 6,010 of tests | 17,660, 2,506 and 33,917 |
| MCP tools | 9 | 22: ten that answer, read or set up, and twelve submit tools |
| Agent prompt | | 12,911 characters, against a 13,000-character budget |

**Quality.** All 19 checks pass on `main`: among them strict types, 15 versioned contracts, the identity scan of the tree,
the secret scan of the whole history and the dependency audit. No threshold moved in Phase 2: coverage's floor is 90% of
lines and of branches, the gate's Hypothesis profile runs 500 examples, and CI's budget is 5 minutes. One rule changed,
with the owner's approval on 2026-11-18 (#153): a budget test's wait for the shared timing process counts apart from its
two-minute limit, which still applies to each test's own code. Three suppressions were added, each with its reason and the
owner's approval date: the real-page tests skipped where the pages aren't saved (S-013), the simulation's seeded generator
(S-014) and the alerts' fixed `osascript` command (S-015).

## Mutation testing

`make mutate` on the core modules, on fast tests only, once, on 2026-11-24. The whole set finished in 8 minutes, inside
its 10-minute limit.

| Mutants | Count |
|---|---:|
| Made, in `engine/*`, calibration, the review, the cards, the recalibration, the alerts, the month files, the collection log and the cadence | 5,603 |
| Caught: killed, and one that timed out | 5,316 |
| Survived | 125 |
| Not reached by any fast test: the cadence's parts that read the lake, whose check is deliberate faults by hand | 162 |

**5,316 of the 5,441 mutants the fast tests reach are caught (97.7%),** against 4,792 of 4,897 (97.9%) at the last full
run, in `mvp-sources`. Of the 125 survivors:

- **110 are in code that hasn't changed since its slice read them** and found each equivalent or harmless: the simulation
  (37, one more than at the last full run, with its code unchanged), the review's older code (29), the alerts (10),
  calibration (9), the player models (9), and 16 across the odds, the recalibration, the captain, the lineup's arrangement,
  the ranking and the cards. They are the kinds the slice reports list, such as `strict=` on a `zip` of lists that are
  always the same length, or `<` against `<=` where a tie doesn't arise.
- **15 are in review code added after the last full run,** by `mvp-alerts` (#139) and `mvp-fixes` (#163), and were read
  for this report, each applied to the code and run against the slower tests:
  - 8 are caught by tests outside the fast selection: the app total kept in the review log and counted in the record
    (`tests/property/fixes/test_record.py`, `tests/unit/fixes/test_review_log.py` and `mvp-fixes` AT-7);
  - 5 change nothing: `>` against `>=` at the record's margin, on a float (2); a lineup's team, which is never empty (1);
    and conditions on fields that are always set together (2);
  - **2 are a real gap:** no test builds an alert's baseline from an override answer, so the chances of starting that
    advice carries are untested. They only say why a call changed, never whether it did (`mvp-alerts` R2.3): dropped, an
    alert's "why" would lose them; set to nothing, that check would fail.

Both gaps are small test changes: the two pure test files join the mutation set's selection, and one fast test checks an
override's advice. They wait for a spec, with the gate changes of decision 1.

## Cost

$0. Nothing runs on AWS, no paid service was added and no account was created. Every question uses the player's own
Claude plan: an answer is at most about 15 KB, about 5,000 tokens, and loading the 22 tools costs about 17,000 tokens a
conversation (the review before Phase 3, §10). ADR-0008's trial would use 10 to 20 of The Odds API's 500 free credits, once
the owner has created the account.

## Decisions taken in Phase 2

The owner's, besides each slice's requirements, design, tasks and sign-off:

- **2026-10-30 and 10-31:** Fantadamus collects the round's facts itself (ADR-0006); the MVP is Phases 1 to 3, and Phase 2
  starts with collection.
- **2026-11-06 and 11-07:** every feature in scope is built before going online; live forecasts, pundit consensus and
  Mantra leave the MVP; a league's rules become data, in place of a slice for the modifiers and the captain.
- **2026-11-11:** rules that need the opponent's team are dropped; manual acceptance tests close on past rounds where they
  can; a full review with Fable 5.2 runs before Phase 3.
- **2026-11-12:** the first recalibration, the starting map and the yellow-card prior; ADR-0007, the new pages.
- **2026-11-15:** ADR-0008, a one-round trial of anytime-scorer odds.
- **2026-11-16:** the review's first finding becomes `mvp-store`, before the schedule is installed.
- **2026-11-18:** the budget tests' wait; the schedule installed; alerts on each role's first bench place.
- **2026-11-24:** `mvp-lineup` AT-18's new penalty note.

## Open risks

1. **CI is at its budget.** The median of the last ten pull requests is 257 s against 300, and three went over: 334 to
   385 s. `make check` takes 7½ to 9¼ minutes on the owner's Mac, and `make test-fast` 34 s against 20. Each slice added
   tests that go through the tools, and their set-up is what costs (the review, §7). Decision 1.
2. **The chance of a rating is overstated for players unlikely to start,** in both rounds that could score it. It feeds
   every bench order and every cameo's value. Decision 3.
3. **One Mac.** The second player hasn't installed Fantadamus; a sleeping Mac misses its runs; and Claude Desktop keeps the
   code it started with until it's quit and reopened. Phase 3 removes all three.
4. **Budgets nearly spent.** The agent prompt is at 12,911 of 13,000 characters, and round 12's largest card at 14.9 of
   15 KB.
5. **Small samples.** Three rounds scored, and ten matches a round for the market. The penalty rates wait for 30 penalties
   (22 at the last proposal), the rating constants for about five rounds of ratings, and each rater's claim for five
   matches.
6. **One fact is declared in about ten places** (the review's finding 3). A test keeps the `collect` tool and the collector
   in step until Phase 3 makes one registry of facts and pages.
7. **Carried from Phase 0:** the cryptography allowlist must be renewed by 2027-01-26.

## Decisions for the owner

1. **Make the gate faster, first.** CI is at its budget (risk 1). The review's decision 2 proposes two gate changes:
   disk-bound property tests run 100 examples in the pull-request gate and 500 at phase gates (R9), and `sqlfluff` and the
   two Phase 0 tests of ruff and mypy leave the pull-request gate (R12). Neither removes a check of the product. Its R8, a
   through-the-tools test that pays for its question and not its set-up, is the larger saving and changes no rule.
   **Recommendation:** yes to both, made with R8 and the mutation set's two gaps as the first step of Phase 3, before
   Phase 3 adds tests of its own.
2. **Phase 3's platform.** The review's decision 3: the MVP's own layout on S3, DuckDB inside a Lambda, EventBridge
   Scheduler for the collection and SNS for the alerts, with Iceberg, Glue, Athena, Lake Formation and Step Functions
   waiting for a measurement that asks for them; `tech.md` says so, and ADR-0003 records it. The owner's lake is 4.5 MB
   after round 12, and `mvp-store` already writes it the way S3 works: a file written once, and one file naming each
   table's files. **Recommendation:** yes. Phase 3's first question is then whether the approved sites accept requests
   from AWS addresses; finding out needs a deploy, so it waits for your approval.
3. **A share for each kind of cameo.** For players unlikely to start, the chance of a rating rests on `CAMEO_SHARE`: 0.5
   today, fitted at 0.248 on rounds 10 and 11 but on 183 of the 200 players it needs. Round 12 confirms the overstatement.
   The share can't simply be lowered: of the outfield players who didn't start, attackers got a rating 41% of the time over
   rounds 11 and 12 (71 players), midfielders 31% (169) and defenders 22% (143), so one share doesn't fit both kinds of
   cameo. **Recommendation:** a small recalibration spec next, before Phase 3: attackers' cameos get a share of their own
   in place of `CAMEO_RATED` (amending `mvp-recalibrate` R3.1), and both shares are fitted on rounds 10 to 12 and proposed
   to you value by value, as the first recalibration was.

## Next

The owner signed Phase 2 off on 2026-11-24, and the README and `product.md` record it. Next come the three decisions
above, then the cameo shares if decision 3 is taken, and Phase 3: Fantadamus online, so that a player installs nothing.
