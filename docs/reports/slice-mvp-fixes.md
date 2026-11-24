# Slice report: `mvp-fixes`

2026-11-24 · Phase 2, the eleventh slice, after round 12 · **Waiting for the owner's sign-off**; the owner accepted
mvp-lineup AT-18's new sentence on 2026-11-24 (decision 1)

Round 12 was the first round run end to end on the owner's Mac with the schedule installed, and it found five small
faults. This slice fixes them. A page that got no answer is tried again at the next run, instead of 12 to 24 hours
later; Claude can ask the collector for any of its facts; every answer names every page it shows; a penalty note
says when the taker listed ahead is out; and the review keeps the league app's total, so the season record says how
often it agreed. No number moved: on a copy of the owner's lake, every answer is the same apart from its sources and
penalty notes. Player names and the owner's league aren't reproduced here: the real-data numbers are counts.

## What the slice delivered

| Task | What | Pull request |
|---|---|---|
| 1 | A try that got no answer doesn't count as the page's read: robots.txt that can't be read fails the run's pages, and they are due again at the next run | #159 |
| 2 | The `collect` tool takes every fact the collector reads, and names its pages | #160 |
| 3 | Every answer names every page it shows: the injured and suspended pages in the lineup and the card, and Sources for the overview and the review | #161 |
| 4 | The penalty note says when the taker listed ahead is out | #162, after decision 1 |
| 5 | The review keeps the app's total; the record says in how many rounds it matched | #163 |
| 6 | The docs, the real lake compared field by field, the mutation run and this report | this one |

What building it found, each settled in its task:

- **A robots.txt timeout and a page's 404 had tests of their own** pinning the old handling. Both are behaviours the
  design changes (a timeout is now "couldn't be read", a 404 is `missing`), so the two tests, neither an acceptance
  test, expect the new ones as strictly (task 1). `last_attempt` stays, as four earlier tests use it.
- **The design said the review's sources were already complete.** The review and the round overview had no Sources
  at all; both now do, and the design was corrected (task 3).
- **mvp-lineup's AT-18 expected the old penalty note** for exactly the case R4.1 changes: "if X misses the start: they
  count at 100%". Its new sentence is the one change to an earlier acceptance test, so task 4 waited for the owner,
  who accepted it (decision 1).
- **Asking for a review again without the app's total** would have dropped that round from the count. Each round now
  counts by its latest review that had a total (task 5). The tool writes the record's line itself, since the agent
  prompt is 89 characters under its budget.
- **An answer's "updated" times come from its sources**, so the injured page, now among them, moved them in two
  lineups (task 6): what the answer says about its freshness now covers every page it shows.

## Real data

From Claude Code, on copies of the owner's lake, with nothing fetched and nothing written to `data/local`:

- **Saturday 21 November, replayed (task 1).** The collection log as it stood after the run that the Mac's sleep
  suspended and that resumed with no network. At the schedule's next look, 15 minutes later, the code before the slice
  finds nothing due: two hosts' pages would have waited 12 to 24 hours. With the slice, six facts are due again
  (statistics, penalty takers, table, other competitions, injuries, bans), and an answer an hour later may read the
  statistics, takers and injured pages again.
- **Every answer compared, field by field (AT-8).** The lake as it stood on 24 November, rounds 1 to 12, asked 77
  questions: every logged question again at its own time, and at five times the lineup, the overview, two cards, two
  comparisons, four outlooks and an alerts' check, then the reviews of rounds 11 and 12. Recorded with the code before
  the slice, then asked again with all five fixes (`python -m tests.real_lake --compare --fields`):

  | Kind of change | Changes | Answers |
  |---|---|---|
  | None: identical | | 64 of 77 |
  | Sources | 20 | 8: four overviews and two reviews that had none, two lineups gaining the injured page |
  | The "updated" times, from those sources | 2 | 2 lineups |
  | Penalty notes | 7 | 6: two lineups, two comparisons, two outlooks |
  | New fields, still empty: the record's app counts | 6 | 2 reviews |
  | Anything else | 0 | 0 |

  The code before the slice, compared with itself the same way, gives 77 identical answers.

## Numbers

| Measure | Value |
|---|---|
| Tests | 1,720, 10 of them skipped without the private data, as in CI (1,660 at the start); task 4 adds 4 |
| Coverage | 98.8% of lines and 96.1% of branches; the floor is 90% |
| `make check` (19 checks) | 7.4 minutes on the owner's Mac |
| CI per pull request | 3.2 to 6.2 minutes for this slice's; median 4.3 over the last ten, against a 5-minute budget |
| Code | 17,642 lines of product code (17,442 at the start), 2,506 of checks and hooks, 33,838 of tests, before task 4's net 18 |
| Agent prompt | unchanged, 12,911 characters of 13,000 |
| Dependencies | none added: `pyproject.toml`'s dependencies and `uv.lock` unchanged |

Each task broke its own code on purpose before its report: 11 faults in all, every one caught.

## Mutation testing

`make mutate ONLY='fantadamus.lake.collect_log.x_newest* fantadamus.web.cadence.x_due*
fantadamus.web.cadence.x_may_read_after*'`, with the collection log and the cadence added to the mutation set and
their pure tests beside them, on 2026-11-24:

- **The first run killed 52 of 72.** Nineteen survivors were in `due`'s rules from before this slice, each at its
  edges: the ratings the morning after the round, the other competitions daily in a match week, injuries and bans
  twice a day before the round, and the lineups' last day. `mvp-sources` had tested them only through the lake, which
  `mutmut` can't fork. The twentieth was an answer reading exactly at its interval. Five pure tests now pin each rule
  at its edges.
- **The second killed 71 of 72.** The survivor counted a run only before the as-of instant, not at it; a test now
  asks for a run at its own instant.
- **The third killed 72 of 72 (100%).**
- The rest of the slice goes through the lake, the logs' files or the tools, which `mutmut` can't fork; the
  deliberate faults by hand are its check: 11 of 11 caught.

## Acceptance tests

| Test | Proves | Result |
|---|---|---|
| AT-1 | A run whose robots.txt gets no answer, a timeout or a 500 reports the host's pages as failed, with the cause, and the next scheduled check finds them due; a disallowing robots.txt and a block keep counting, and wait for the cadence | Passed |
| AT-2 | Over runs that keep failing, each page is tried at most once a run, one request a second per host; an answer retries no sooner than 15 minutes after a failed try | Passed |
| AT-3 | The report and `fantadamus collect --report` show failed pages, their cause and that they'll be tried again | Passed |
| AT-4 | The `collect` tool accepts every fact in the collector's list and reads its page; adding a fact to one and not the other fails a test | Passed |
| AT-5 | For each kind of answer, every page whose facts it shows is among its sources; a lineup with an injured player names the injured page | Passed |
| AT-6 | A taker whose listed predecessors are all out gets the "is out" note; one with a doubtful predecessor keeps the share | Passed |
| AT-7 | A review given an app total keeps it in the log; the record counts the matching rounds; a line logged before the slice still reads | Passed |
| AT-8 | On a copy of the owner's lake: Saturday's run replayed leaves the pages due at the next run, and every answer is unchanged apart from its sources and penalty notes | Passed: "Real data" above |
| AT-9 | No new dependency; the docs updated | Passed |

P1 to P4 hold: a page is due exactly when its newest answered try is older than its cadence; robots.txt is asked at
most once a host a run, and an answer never retries sooner than 15 minutes; a player's sources hold every fact
present; the app's count follows each round's latest review with a total, and an old line reads.

## Cost

$0, as estimated: no dependency, service or account. A page that keeps failing is asked at most four times an hour,
each try as polite as before.

## Open risks

- **Claude Desktop runs the code it started with.** After the last merge, `~/Documents/fantadamus` is brought up to
  `main` and Claude Desktop is quit with ⌘Q and opened again, or its answers lack the overview's and review's Sources.
- **A sleeping Mac still misses its runs.** The fix makes a closed lid cost only the time it was closed, not a day;
  only the online version (Phase 3) runs while the Mac is closed.
- **CI is near its budget.** Two of this slice's runs took 5.6 and 6.2 minutes; the median of the last ten is 4.3.
- **One list of facts and pages** for the collector, the tools and the reading list waits for Phase 3 (decision 2 of
  the requirements); a test keeps the `collect` tool and the collector in step until then.
- **The mutation set's guard checks only the folders it lists**, not files named one by one, for tests that reach the
  lake or the tools. This slice's files are pure, and a test whose file imports the harness was left out of the set.

## Decisions for the owner

1. **Accept mvp-lineup's AT-18 new sentence?** Accepted by the owner on 2026-11-24. It expected the old note for
   exactly the case R4.1 changes; the share, the value and where the note appears are unchanged.
2. **Sign off this slice?** Recommendation: yes. Every acceptance test passes, and the real lake shows only the
   changes the slice is for.

After both: `git pull` in `~/Documents/fantadamus`, then quit Claude Desktop with ⌘Q and open it again.

## Next

The Phase 2 report, which follows round 12, then Phase 3. Still open from round 12's test: round 12's calibration
found "getting a rating" overstated for the attackers' cameos, which a recalibration of the cameo share can look at;
and from the review before Phase 3, its decisions 2 and 3.
