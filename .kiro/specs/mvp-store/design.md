# Design Document: `mvp-store` (Phase 2, tenth slice)

Status: **Approved by the owner, 2026-11-16**, with the recommendation on gold · From the approved [requirements](requirements.md)

## Overview

Two things cost more with every read stored: storing, which rebuilds a whole silver table each time, and answering,
which loads every row of the last 14 days into Python. This design makes a store add its rows to one month's file, and
an answer read each page's newest submission only. Silver can still be rebuilt from bronze at any time, and is, by
itself, whenever a store finds it out of step.

Nothing here changes a number. The rows an answer no longer reads are rows it never used: an older lineup from the same
page for the same match and outlet. Two reading paths stay in the code, everything and what an answer uses, and the
tests hold them to the same answers.

Measured for this design, on generated rows, with DuckDB's own calls and no SQL text beyond column names:

| With a season stored (2,197,800 outlet rows in 9 month files) | Time |
|---|---|
| Appending one read's 2,200 rows to the newest month's file | 0.26 s |
| Reading each page's newest submission for each match and outlet, in stored order | 0.20 s |
| The hashes of one page's newest stored read | 0.04 s |
| Reading the whole window, as today, before its 114,400 rows become Python objects | 0.42 s |
| Generating that season | 3.6 s |

## What it builds on

- `lake/duckdb_store.py`: `LakeStore`, bronze as a file for each submission, silver written to a temporary file and
  renamed into place.
- `domains/facts.py`: `Domain`, `submit`, `submit_many`, `rebuild`, `read_silver`, `last_read`, `latest_by` and
  `latest_submissions`.
- `mcp/advisor.py`: `Facts.read`, the one place an answer reads the lake, and `_fresh`, which decides what still counts.
- `web/collector.py` and `web/cadence.py`: a run stores a page's facts when they differ from its last stored read, and
  stores them again once that read is older than the window, so a current fact always has a read inside it.
- `lake/jsonl.py`: one reader for the four logs.
- `tests/lineup_speed.py`: a timing in CPU seconds, in a process of its own, the fastest of three.

## Components

### C1. Silver in month files (`lake/months.py`, `lake/duckdb_store.py`; R1.2, R1.4, R2.5)

```text
silver/<table>/_table.json              the table: its columns, the domain's rows version, the bronze record its
                                        last row came from, and its file for each month
silver/<table>/<YYYY-MM>.<id>.parquet   the rows captured in that month (UTC), in the order they were stored;
                                        written once, under a name of its own, and never changed
silver/<table>/_storing                 there while a store is under way
silver/<table>.parquet                  the earlier layout: read until the table's first store or rebuild replaces it
```

- A row goes to the month of its `captured_at`. A month holds about 250,000 outlet rows at the scheduled cadence, which
  is what keeps an append at a quarter of a second all season.
- `lake/months.py` is pure: the month of a time, the months a window touches, and whether a table is in step (C3). It
  joins the mutation run.
- A read takes the files of the months its window touches, or every file without a window, and returns rows in stored
  order: by file, then by position in the file. Today's order across files is DuckDB's to choose.
- **`_table.json` is the one switch** (tasks 1 and 2, 2026-11-17). A store writes a month's file anew, under a new
  name, and then `_table.json`, which names the table's files; writing it, by a rename, is the moment the store takes
  effect. A reader takes the files `_table.json` names, and they never change, so it sees the whole table before a
  store or after it, a rebuild's many months included (R1.4). The file a store replaced is removed afterwards: a reader
  that finds one gone reads `_table.json` again. Readers take no lock. The same scheme works on S3, which has no
  rename for a data file.
- Two findings led here. A month's file renamed into place under the same name was read half from each version: DuckDB
  opens a file once for its description and again for its rows (task 1). And a rebuild replaces its months one at a
  time, so a reader in between could have taken one month from before and one from after (task 2).
- `LakeStore.read_table` and `write_table` give way to `read_rows`, `append_rows` and `replace_rows`, which know this
  layout. The `gold` layer they could name was never written and goes with them (open point 1).

### C2. Rows loaded in bulk (`lake/duckdb_store.py`; R1.2)

Rows reach DuckDB through a JSON-lines file beside the table, read with `read_json` and the table's own column types,
then removed. That takes 0.15 s for 17,341 rows, where today's inserts take 3.9 s. A `Table` keeps its name and its
columns and loses its insert statement; bronze, one row at a time, keeps its own.

### C3. A store appends (`domains/facts.py`, `lake/duckdb_store.py`; R1.1, R1.3, R2.1 to R2.3)

A payload is checked and turned into rows before anything is written, as today. Then, holding the lake's lock:

1. **In step?** The table is in step when `_table.json` names the domain's columns and rows version, no `_storing` is
   there, every file it names is there, and there is no file in the earlier layout: code from before the slice,
   still running in a server, would have written one.
2. `_storing` is written.
3. The bronze file is added, or the files of a page's payloads (`submit_many`). Bronze doesn't change otherwise.
4. In step, and the new bronze files sort after the last one the table holds: the new rows are appended to their
   month, in a new file holding that month's rows and then theirs. Otherwise the table is rebuilt (C4), the new bronze
   included.
5. `_table.json` is written, the files it no longer names are removed, and `_storing` goes.

- **The table is always the one a rebuild gives, row for row** (task 2, 2026-11-17). A rebuild reads bronze in its
  files' order, and a file's name starts with the time it was received. Two stores in the same microsecond, or a
  clock set back, give a file that sorts before one already stored: its rows don't belong at the end, so that store
  rebuilds. `_table.json` keeps the last bronze record for this, and the clock is read holding the lock, so that two
  runs at once still append.

- **A stopped run** leaves `_storing` behind, at whichever step it stopped, so the next store rebuilds (R2.1).
- **Two runs at once:** the lock is a file lock from the standard library (`fcntl.flock` on `<lake>/.lock`), held for
  the five steps. The second run waits for the first to finish its store, then finds the table in step and appends
  (R2.2). Readers take no lock.
- **A change of code:** a domain declares `rows_version`, raised when `to_rows` changes what it gives. Other columns or
  another version put the table out of step (R2.3).
- A payload that gives no row still goes through the steps: its bronze file is kept, and nothing is appended.

### C4. Rebuilding (`domains/facts.py`, `domains/tables.py`, `cli/__main__.py`; R2.4, R2.5)

- `rebuild` reads bronze 500 files at a time and writes each month's rows to its JSON-lines file as they're made, so
  its memory doesn't grow with the season. It then loads each month, writes `_table.json`, and removes any file the
  table no longer has, the earlier layout's among them.
- `domains/tables.py` lists the thirteen domains once. `fantadamus rebuild [--table <name>]` rebuilds each, or one,
  under the lock, and prints its bronze records, rows and months. It builds no fetcher, so it can't read a page.
- A lake stored before this slice needs nothing from its user: each table is read in its earlier layout until its
  first store rebuilds it.
- A whole rebuild at season size takes about a minute for the largest table (estimated from today's 319 files). It
  happens after a stopped run or a change of `rows_version`, not on the way to an answer.

### C5. An answer reads what it uses (`lake/duckdb_store.py`, `domains/facts.py`, `mcp/advisor.py`; R3.1 to R3.3, R3.5)

**The read.** `read_rows` gains two things, both done by DuckDB:

- `newest_by`: for each page and each value of the named columns, keep the rows of the newest submission in the
  window, by `captured_at` and then by content hash, as `latest_by` orders them. A tie keeps the whole submission.
  DuckDB compares each row's `{captured, hash}` with its group's maximum: a third faster than `rank()` on the
  largest table today, and the same on a small one (task 3).
- `equals`: keep only the rows whose column has one of the values given.

**Which tables.** A domain names its `newest_by`; five do, the ones that grow with every read:

| Table | Newest for each page and | Read by |
|---|---|---|
| `outlet_views`, `lineup_views` | match and outlet | `availability` |
| `odds` | match and bookmaker | `team_xg` |
| `official_lineups` | match | `availability` |
| `season_stats`, `player_seasons` | player | `known_players`, each player's figures |

The other tables stay as they are: a few hundred rows in a window.

**Why the answer is the same.** `_fresh` and the functions above choose, for each key, the newest row that still
counts. A row left out is older than a kept row of the same page and key, so it's never the newest; it's never fresher,
since only a page's newest read can be confirmed by a later one; and whether a fact is stale or missing asks only if
any row is there. Outlets and bookmakers are grouped by their spelling in the read and by their normalised name after
it, as today, which keeps a superset. A prototype of P4 ran 8,000 random histories through today's `_fresh`,
`availability` and `team_xg`, with ties, repeated content, two pages, confirmed reads and replays of any age: none gave
a different number.

**`Facts`.** `Facts.read(lake, as_of)` reads those five tables that way and keeps its window's start. Its fields get
their row types in place of `Any`.

- **A movement** compares with an earlier time. `Facts.at(lake, earlier)` reads the five tables again as they stood
  then, over the same window, and reuses the others: one or two more reads for an "X or Y?". Every answer goes
  through it, a movement's replay among them, so no answer about an earlier time can use a newer read's rows (task 3,
  2026-11-17). A table none of whose kept rows was captured after that time is already what a read then keeps, and
  isn't read again.
- **Calibration** asks about each match at its own kickoff, so it reads everything: `Facts.read(lake, as_of,
  history=True)`. So does the test that holds the two paths together (P4).
- **Ratings** leave `Facts`. `claims` reads them for `compare_players`, `player_outlook` and `match_card`, with
  `equals` on the clubs asked about. The replay behind a movement shows no claim and reads none.

**The collector and the schedule.**

- `last_read` loaded a domain's whole window to find one page's newest hashes. `LakeStore.newest_hashes` asks DuckDB
  for them: 0.04 s.
- `what_is_due` reads the official lineups of the window, not the whole table: a match it asks about kicks off within
  days.

### C6. Logs read once (`lake/jsonl.py`, `lake/collect_log.py`; R1.5, R3.4)

- `read_lines` keeps what it parsed from a file for as long as the file's size and time are unchanged, and hands out a
  copy. An appended line changes both, so it's seen.
- It can start at a month. The collection log is read from the window's start: an older run can't confirm a row inside
  the window, and can't be the last attempt of a page read at least weekly. Scoring a round reads back to that round.
- The decision, review and alert logs are read whole, once while unchanged, as their answers need them.

### C7. The proof (`tests/season.py`, `tests/lineup_speed.py`, `tests/real_lake.py`; R4.2, R5.1 to R5.3)

- **A season.** `tests/season.py` takes a synthetic round as the harness builds it and writes the season around it with
  DuckDB: the round page's 1,000 stored reads, 60 of them in the window, padded with invented matches to 2,200 rows a
  read; the statistics reads; the ratings; 3,000 collection runs; 1,000 answers. It writes month files and
  `_table.json` as the lake does, and no bronze: a table in step never looks at it.
- **One process.** `python -m tests.lineup_speed --all` builds the round once, copies it for each timing, times every
  budget, the existing six and this slice's, and prints them as JSON. A session fixture runs it once for the whole run,
  behind a file lock so that one worker starts it and the others read its result. Each budget test asserts its own
  number. Today the eight timings start eight processes, each building its own round: 60 s run alone, 93 s inside the
  suite.
- **The wall-clock assertion** in `tests/integration/lineup/test_reads.py` goes; gathering a squad at season size is
  timed in the process instead, still under 1 second.
- **The real lake.** `python -m tests.real_lake --record` asks a copy of the owner's lake every question at five past
  times and keeps the answers under git-ignored `data/private/mvp-store/`; `--compare` asks again and says whether each
  is identical. It prints times and counts only. It is run from here, before task 1 changes anything and after task 5.

### C8. The docs (R5.4)

- `tech.md`: the storage row says month files and appends, and that gold is computed when asked (open point 1).
- `README.md`: `fantadamus rebuild` beside the other commands.
- `lake/duckdb_store.py` and `domains/facts.py`: their own descriptions of the layout and of a store.
- The slice report: the real lake's times before and after, and the suite's.

## Error handling

| Case | What happens |
|---|---|
| A run stops between bronze and silver, or anywhere in a store | `_storing` stays; the next store rebuilds the table |
| Two runs store at once | The second waits for the lock, then appends |
| A store takes effect while an answer reads | The answer reads the files it listed, which don't change; if a store removed one, it lists them again |
| A server still running code from before the slice stores | It writes the earlier layout's file; the next store finds it, and rebuilds |
| `_table.json` is missing, unreadable, or names other columns or another version | Out of step: rebuilt at the next store |
| A table in the earlier layout | Read as before; rebuilt into months at its first store, or by `fantadamus rebuild` |
| A payload that gives no row | Its bronze file is kept; nothing is appended |
| A store's rows fall in two months | Each month gets its new file, and one `_table.json` names both |
| A file left by a stopped run | `_table.json` doesn't name it, so it's never read; removed when the next store takes effect |
| A bronze file that sorts before one already stored | The table is rebuilt, so every row stands where a rebuild puts it |
| A month file removed by hand | Its rows are missing until the table's next store, which rebuilds it, or `fantadamus rebuild` |
| The lock can't be taken or the disk can't be written | The store fails with the reason, as any write does today |

## Correctness properties

Each is a Hypothesis test, required. P2 and P4 are pure and live in `tests/property/store/`. The others write Parquet
files, so they live in `tests/integration/store/`: `make test-fast` runs none of them (the review, finding 5). P4
reduces the rows as P5 holds DuckDB's read to, with each domain's own `newest_by`, so that it also checks the keys the
domains declare (task 3).

- **P1** For any sequence of submissions to a domain, stored one at a time or a page at a time, the table after each
  store holds the rows a rebuild gives, in the same order, and no bronze file has changed.
- **P2** A row is in the file of the month it was captured in, and the files chosen for a window are exactly those
  whose month it touches.
- **P3** A store stopped after any of its steps leaves a lake whose next store ends with the table a rebuild gives.
  A store makes at most six writes, so the test goes through every one: stopped before and after each, for each
  kind of store, on a lake with the table and on one without.
- **P4** For any history of submissions and any time asked about, each player's availability, each match's team xG and
  each player's season figures are the same from the reduced read as from the full one.
- **P5** A reduced read never holds a row captured after the time asked about, and holds for each page and key exactly
  its newest submission by then.

P1 takes over from `tests/property/test_lake.py::test_bronze_append_only`, which moves with it.

## Testing strategy

- **Unit:** the month of a time and the files of a window; in step or not, each way; the log reader's cache; every
  domain listed.
- **Integration:** bulk loading each column type; the layout, the earlier one included; a stopped store, two runs at
  once (two processes on one lake), a raised rows version; the reduced read; the collector's hashes; the season.
- **Acceptance:** AT-1 to AT-7 and AT-9 in `tests/acceptance/store/`, by example; AT-1's and AT-7's properties are P1
  and P4. AT-7 asks every tool both ways on a round with several stored reads, a movement, a review and an alerts'
  check included. Every earlier acceptance test stays as it is.
- **Budgets (AT-2, AT-5):** in the one timing process, at season size.
- **The real lake (AT-8):** from here, on a copy; nothing of it reaches the repository.

Each code task breaks its own code on purpose once before its report. For the budgets, that means forcing the full
read and seeing the season's times fail.

## Cost

$0: no new dependency, service or account (R4.1); DuckDB and the standard library do all of it. A lake at season size
is some tens of megabytes.

## Build order (input to tasks.md)

1. The reference answers from the real lake; silver in month files, loaded in bulk (C1, C2). Stores still rebuild, so
   nothing else changes yet. This spec becomes the current one.
2. A store appends; rebuilding by itself and by command (C3, C4).
3. An answer reads what it uses (C5).
4. Logs read once (C6).
5. The season and the one timing process, with every budget (C7).
6. The docs, the real lake's comparison, the mutation run and the slice report (C8).

## Open points for the owner

Decided by the owner on 2026-11-16, as recommended.

1. **Gold.** The storage code can name a `gold` layer that nothing has ever written, and `tech.md` says answers come
   from stored gold products. Recommendation: remove the unused layer here, and have `tech.md` say that gold is
   computed when asked in the MVP and stored once a measurement asks for it. This slice's read is the measurement that
   came closest, and it didn't need one.
