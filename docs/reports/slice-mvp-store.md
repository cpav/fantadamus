# Slice report: `mvp-store`

2026-11-17 · Phase 2, the tenth slice, before the schedule is installed · **Awaiting the owner's sign-off**

Storing a read and reading for an answer now cost what is new, not what is already stored, so that the schedule can
run every 15 minutes for a whole season. A store adds its rows to one month's file instead of rebuilding its table,
and an answer reads each page's newest submission instead of every row of its 14 days. No number moved: every answer
of a copy of the owner's lake is identical, byte for byte, before and after. The real-data numbers here are times and
counts only.

## What the slice delivered

| Task | What | Pull request |
|---|---|---|
| 1 | Silver in month files, loaded in bulk; the real lake's answers recorded before any change | #147 |
| 2 | A store appends, under a lock; it rebuilds by itself when a table is out of step; `fantadamus rebuild`; `_table.json` as the one switch | #148 |
| 3 | An answer reads each page's newest submission; ratings only for a claim, for its clubs; the collector and the schedule read less | #149 |
| 4 | Logs parsed once while unchanged, and the collection log read from the window | #150 |
| 5 | A season generated around the synthetic round, and one timing process for every budget | #151 |
| 6 | The docs, the real lake compared, the mutation run and this report | this one |

What the tests found, each fixed in its task:

- **A file renamed into place could be read half from each version.** DuckDB opens a file once for its description
  and again for its rows. The reader test of task 1 caught a read whose rows came from the file that replaced it.
- **A rebuild replaced its months one at a time**, so a reader in between could take one month from before and one
  from after (task 2). Now a month's file is written once under its own name, and `_table.json`, which names the
  table's files, is the one switch: a reader sees the whole table before or after. It is also how S3 works, which
  has no rename.
- **An answer about an earlier time could use a newer read's rows** once a read keeps only the newest (task 3). Every
  answer now goes through `Facts.at`, which reads the growing tables again as they stood then. A movement is the
  common case.
- **A server still running code from before the slice** writes the old one-file table. The next store finds that file
  and rebuilds, so nothing it stored is lost (task 2).
- Three tests didn't exercise what they claimed until the breaks showed it (task 3): AT-6's compare had no earlier
  answer to replay, P4 used its own copy of the domains' keys, and AT-7 scored the round only once.

## Real data

On a copy of the owner's lake, taken before task 1, with nothing fetched and nothing written to `data/local`:

- **The 73 answers are identical** to those recorded before the slice: every logged question again, at its own time,
  and at five past times the lineup, the overview, comparisons, cards, outlooks and an alerts' check, with two rounds'
  reviews. Both as the lake is stored today, in the earlier layout, and once every table has been rebuilt into month
  files (21,982 rows in 13 tables), which it will be after its first store.
- **Time,** CPU seconds, both versions run back to back on the same Mac:

  | Tool | Answers | Before | After, rebuilt |
  |---|---|---|---|
  | `best_lineup` | 5 | 3.29 | 2.77 |
  | `compare_players` | 23 | 4.23 | 5.07 |
  | `player_outlook` | 23 | 4.69 | 5.22 |
  | `match_card` | 10 | 4.56 | 3.93 |
  | `round_overview` | 5 | 0.90 | 0.74 |
  | `review_round` | 2 | 1.27 | 1.08 |
  | Alerts' check | 5 | 1.36 | 1.11 |
  | Every answer | 73 | 20.3 | 19.9 |

  Today's lake is small, and it costs about the same. A comparison or an outlook now reads the growing tables a second
  time, as they stood when the answer it moves from was given: 20 to 40 ms each. The gain is at season size, below.

## At season size

`tests/season.py` grows a season around the synthetic round: the round page's 1,000 stored reads, 60 of them in the
answer's window, 2,200 rows each (2.2 million rows); 250 reads of the statistics page; two reads of each round's
ratings; 3,000 collection runs and 1,000 answers. Its largest month holds 272,800 rows. Timed in CPU seconds, the
fastest of three, in one process:

| Measure | Time | Budget | Before the slice |
|---|---|---|---|
| Storing one read of the round page: 60 bronze files and its rows | 0.47 s | 2 s | about 4 s on today's lake, growing with each read |
| The schedule's check, nothing due | 0.03 s | 1 s | three whole tables read |
| Reading the lake for an answer | 0.13 s | 1 s | 1.85 s, forcing the whole window |
| Gathering a squad's facts, 25 players | 0.06 s | 1 s | 0.41 s, forcing the whole window |
| `best_lineup` | 0.70 s | 3 s | 3.15 s, forcing the whole window |
| `compare_players` | 0.42 s | 3 s | 3.70 s, forcing the whole window |
| `player_outlook`, `match_card`, `round_overview`, `review_round` | 0.38, 0.41, 0.14, 0.76 s | 3 s | 2.64, 2.59, 1.90, 2.13 s |
| The alerts' check | 0.66 s | 10 s | |

A reader that kept reading while a store went on saw the table before it or after it, never anything else. "Before
the slice" is this code with every answer forced to read its whole window: the break on purpose of task 5, where a
lineup and a comparison go over their budget.

## Numbers

| Measure | Value |
|---|---|
| Tests | 1,659 (1,569 at the end of `mvp-alerts`) |
| Coverage | 98.8% of lines and 96.2% of branches; the floor is 90% |
| `make check` (19 checks) | 5:45 to 8:00 on the owner's Mac, quiet to busy (7:35 to 7:58 before the slice, on another day) |
| The test step, back to back, before and after | 310 s and 347 s of wall clock; 1,113 s and 1,303 s summed |
| CI's check job on this slice's pull requests | 219 to 370 s; the median of the last ten is 294 s against 300 |
| The timing process | 52 s alone, every budget and the season included, against 60 s for the eight processes it replaces; started as the run begins |

Each code task broke its own code on purpose before its report: 70 faults in all, and every one was caught in the end.
Ten survived at first, and each now has a test. In task 1: rows in DuckDB's own order, a window without its first
instant, a stray file. In task 2: a pre-slice server's file. In task 3: the six above, two of which P4 catches only at
the gate's 500 examples.

## Mutation testing

`make mutate ONLY='fantadamus.lake.months*'`, with the pure module and its fast tests added to the mutation set, on
2026-11-17:

- **The first run killed 36 of 38.** One survivor changed the error's wording, which a test matched only in part. The
  other changed a default no caller uses: the default is gone and the test matches the whole message.
- **The second run killed 37 of 37 (100%).**
- The store, the reads and the logs go through DuckDB or files, which `mutmut` can't fork; their deliberate faults by
  hand are their check: 70 of 70 caught.

## Acceptance tests

| Test | Proves | Result |
|---|---|---|
| AT-1 | After every store, through the tools, each table holds the rows a rebuild gives; bronze unchanged | Passed |
| AT-2 | At season size a read is stored in 0.47 s and the schedule checks in 0.03 s; a reader sees before or after | Passed |
| AT-3 | A run stopped between bronze and silver, two runs at once (two processes), and a domain whose rows changed each end with the table a rebuild gives | Passed |
| AT-4 | `fantadamus rebuild` rebuilds every table or one, sends no request; a lake in today's layout answers after it, bronze untouched | Passed |
| AT-5 | At season size every answer and the alerts' check within budget, the reading in 0.13 s, gathering a squad in 0.06 s | Passed |
| AT-6 | The ratings read only for the three answers that show a claim, only their clubs; each log once for an answer | Passed |
| AT-7 | Every tool, a movement, a review with its calibration and an alert, the same both ways, on a round read five times | Passed |
| AT-8 | The owner's lake: 73 answers identical at the five times; times and counts only | Passed |
| AT-9 | No new dependency: DuckDB and the standard library | Passed; the gate's time is below |
| AT-10 | The docs: `tech.md`'s storage row and gold, the README's commands from the command line's own list | Passed |

P1 to P5 hold: appending gives what a rebuild gives (500 random histories, ties and clocks set back among them); a
row is in its month and a window reads exactly its months; a store stopped after any of its writes is healed by the
next (all 72 ways); the reduced read gives the same availability, team xG and season figures as the full one, with
each domain's own key (500 histories); and a reduced read holds each page's newest submission and nothing later.

## Cost

$0, as estimated: no new dependency, service or account. The generated season's silver tables take 4.7 MB of
Parquet, its 2.2 million rows compressed well by repeated values; a real season's will be larger, and still small.
Nothing runs on AWS.

## Open risks

- **The gate is slower** (decision 2). The slice's own tests cost about 150 seconds of test time. Locally the test
  step went from 310 to 347 seconds, measured back to back at a quiet moment. On CI the last three check jobs took 359
  to 370 seconds, and the median of the last ten, 294, will pass the 300 of the budget.
- **The shared timing process can outlast a budget test's two-minute limit** on a busy Mac (decision 2). It takes
  about a minute alone and took 2.5 minutes at a load average of 11. It now starts as the run begins, and a failure
  is read once rather than run again by each test, but a budget test that comes before it has finished waits for it
  within its own limit. At that load, every budget test of one run failed on that limit.
- **A comparison or an outlook reads twice** when its movement looks back: 20 to 40 ms on today's lake, and part of
  why property tests through the tools got slower.
- **The lock is this Mac's.** Two machines writing one lake on S3 need another kind of lock: Phase 3's storage design.
- **A full rebuild at season size takes about a minute,** after a stopped run or a change of a domain's rows version.
  Answers read the table as it was until the rebuild takes effect.
- **The Claude app's server keeps the code it started with.** Until it restarts, it stores in the earlier layout; the
  next store with this code rebuilds, so nothing is lost, but the server's answers are the old code's.

## Decisions for the owner

1. **Sign off this slice?** Recommendation: yes. Every acceptance test passes, the season's budgets hold with room,
   and the owner's lake answers identically.
2. **The gate: its time, and the timing process's wait.** Two changes only you can approve:
   - *The wait.* Let a budget test's wait for the shared timing process count apart from its two-minute limit, with
     pytest-timeout's `func_only`: the two minutes still apply to each test's own code, and the process keeps a
     15-minute limit of its own, so a hang still fails with its reason: a few lines in `tests/conftest.py`. In letter
     it relaxes `quality.md`'s rule that any single test over two minutes fails, which is why it waited for you.
     Without it, the gate can fail on a busy Mac. Recommendation: approve it. **Approved by the owner on 2026-11-18,**
     and made on `test/st-wait-limit`, with `quality.md`'s rule saying so.
   - *The time.* The slice didn't keep the gate as fast as before (R5.2): 37 seconds more locally, and CI will pass its
     5-minute median. Recommendation: accept it for this slice, and do the review's decision 2 next, before Phase 3:
     its cheaper through-the-tools tests, tests in their layer and retired self-referring tests take back minutes. The
     other way, fewer examples for P1 and P5, is a gate change too.
3. **Install the schedule** (the requirements' decision 1). Recommendation: yes, now. First quit and reopen Claude
   Desktop, so that its server runs this code. Then follow the player guide's step 8, with your name and the folder
   your copy lives in. The first store after that rebuilds each table into month files, a few seconds each on today's
   lake.

## Next

The review's decisions 2 (the gate) and 3 (Phase 3's platform), then Phase 3: online, with nothing to install.
