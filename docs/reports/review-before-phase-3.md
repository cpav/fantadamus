# Review before Phase 3

**Date:** 2026-11-16 · **Asked for:** simplification, reuse, scale; whether what was built makes sense in the
plan; tests, speed, self-referring tests and dead code · **Run with:** Fable 5.2 (`product.md`, delivery order)

Nothing in the repository was changed by this review except this file. Every number below was measured,
except where it says it is a guess: on the owner's Mac (Intel i5, 8 threads), from GitHub's record of the last
ten CI runs, and on a private copy of `data/local` (timings and counts only; no names).

**What was read:** all of `src/` (only `domains/recalibration.py`, the second half of `domains/review.py` and
the Wikipedia reader were skimmed); every test harness and about twenty test files across the layers; the
checks and hooks under `scripts/` (skimmed); the steering files, the method, the README and each ADR's status.
Every spec's task list was cross-checked by script against its requirement IDs and the tests it names. The
specs' requirements and designs, the ADRs' bodies and the answer formats were not re-read.

## The short version

The product code is in good shape where it matters most: the engine is small, pure and tested by hand-worked
numbers, there is almost no dead code, and the discipline (strict types, contracts, provenance, as-of reads) is
real. Seven findings follow. The first must be fixed before the schedule is installed, and the next three
before going online.

| # | Finding | Evidence | When |
|---|---|---|---|
| 1 | **Storing a read re-inserts all of history, row by row.** | 4.3 s today for one stored lineup read, on 319 files; a third to half a second more after every stored read; minutes by the end of the season | **Before the schedule is installed** |
| 2 | **Every answer loads whole tables into Python.** | Reading takes 364 ms of a 557 ms "X or Y?"; it grows with every read in the 14-day window | Soon after |
| 3 | **One fact is declared in about ten places.** | The injuries page touched 12 source and config files, 7 of them only to register it | Before Phase 3 |
| 4 | **The application lives inside the MCP adapter and is wired twice.** | 3,400 lines of logic under `mcp/`; 90 test files run on the harness's own copy of the wiring, 1 on the real one | Before Phase 3 |
| 5 | **The gate is all tests, and their set-up is what costs.** | Tests are 305 s of CI's 317 s; a through-the-tools test pays 0.9 s of set-up for a 0.2 s question | Any time |
| 6 | **Some tests check themselves.** | 230 lines of "the doc contains this phrase", while the README is five slices behind and green | Any time |
| 7 | **The plan describes a platform this product doesn't need.** | The lake is 2.4 MB after three weeks; no gold table has ever been written | Before Phase 3's ADRs |

Seventeen recommendations follow, in order, each with its steps and how to know it's done. Three decisions are
the owner's; they are at the end.

## What is in good shape

- **The engine** (`engine/`, 1,600 lines): pure, seeded, standard library only, one function per formula, its
  constants in one file. Its unit tests work the numbers out by hand rather than by calling the code again.
- **Dead code:** a static audit of every definition found none in `src/` or `scripts/`, and three small
  functions used only by tests (section 6). Of about 10,000 statements, some 120 are never executed, most of
  them the readers' "this page is broken" branches.
- **Discipline:** `mypy --strict` clean on 460 files, ten registered suppressions, one `TODO`, versioned
  contracts with committed schemas, an injected clock everywhere, append-only bronze and logs, provenance on
  every row.
- **Real pages:** the contract tests run the readers on pages saved under `data/private/` where they exist. That
  is the right answer to "fixtures can't be committed".
- **The trail:** every slice has requirements, design, tasks and a report, and the code cites them. Every
  requirement ID a task list cites exists, and of the 892 test names the ten slices' task lists cite, 888 still
  exist.
- **The method and the code agree:** the *(start)* and calibrated values in `docs/method.md`, about twenty-five
  compared, are the ones in `engine/constants.py`.

## Findings

### 1. Storing a read re-inserts all of history

`facts.submit` and `facts.submit_many` end with `rebuild` (`domains/facts.py:152`, `:213`): every bronze record
of the domain is read, validated, turned into rows again and inserted into DuckDB with parameters, 200 rows a
statement (`lake/duckdb_store.py:83`). The insert is the cost.

| On a copy of the real lake | Time |
|---|---|
| Rebuild `outlet_views` (319 bronze files, 17,341 rows) | **4.3 s**, 3.9 s of it in the insert |
| The same rows loaded in bulk (a temporary JSON-lines file, `read_json`, write Parquet) | 0.15 s |
| One read's 2,170 rows appended to the existing Parquet file | 0.05 s |

When any outlet's lineup changes, the collector stores all of the page's outlet payloads again: 29 to 40 files
and 1,600 to 2,200 rows a time (`web/collector.py:248`). So each stored change makes every later store a third
to half a second slower. The lake has seen 28 collection runs, 9 of which stored lineups. With the schedule
running (by the cadence table, the round page is read some 45 times a round), 15 to 30 stored changes a round
is a fair guess. On that guess a store would take 15 to 30 seconds after two rounds and three to six minutes by
the end of the season, on a schedule that fires every 15 minutes. A question that triggers a collection waits
for it too.

### 2. Every answer loads whole tables into Python

`Facts.read` (`mcp/advisor.py:297`) reads twelve silver tables, each row through a pydantic model. Today:

| On a copy of the real lake | Time |
|---|---|
| `Facts.read` (17,341 outlet rows in the window) | 364 ms |
| "X or Y?" with the facts already read | 149 ms |
| "X or Y?" as a tool call makes it | 557 ms |
| The owner's lineup: reading, gathering and pricing the squad | 711 ms |
| The owner's lineup: seven formations over 10,000 rounds, and the answer | 763 ms |

Three things make it grow:

- The window holds **every read** of the last 14 days, and Python then picks each outlet's latest
  (`latest_submissions`). On the guess above the window would hold 60,000 to 120,000 outlet rows: one to two
  seconds of reading per answer, and the gathering that goes through those rows grows with it.
- `availability()` works out each outlet's latest lineup **once per player** (`domains/availability/gold.py:127`):
  29 calls for a lineup, more than 50 for a match card, each going through every row of the match.
- The season's ratings are read **whole, for every answer** (`advisor.py:313`), though only the outlook and the
  card show a rater's claim. The collection log is parsed whole several times per answer
  (`lake/collect_log.py:32`, once for each fact `may_read` is asked about); it's 28 lines today and would be
  thousands with a schedule.

The simulation is not the problem: 10,000 rounds for seven formations take three quarters of a second.

### 3. One fact is declared in about ten places

To add a page, these all change: its contract; a `Domain` with a row model and two hand-written SQL strings
(`domains/*/silver.py`); the `Fact` literal (`domains/freshness.py`); two freshness tables
(`engine/constants.py`); several of the nine cadence tables (`web/cadence.py:37-90`); and in `web/collector.py` a
`*_FACTS` constant, the `PageKind` literal, `PAGE_FACTS`, `page_of`, two config fields, a `*_submissions`
function, a clause in `reads()`, a clause in `collect()` and a `_x_page` method; then a submit tool
(`mcp/tools/submit.py`), a label (`domains/sources.py`), a field in `Facts`, and two tables in
`config/reading_list.toml`.

PR #130 (injuries and bans) touched 12 source and config files. Five held new knowledge: the contract and a
date type, the reader and its rules, the silver rows. The other seven were registration.

One of those copies has already fallen behind. The `collect` tool accepts six facts
(`mcp/tools/collect.py:28-35`); the collector reads eleven (`web/collector.py:79`). So Claude can't ask for the
table, the injured or suspended pages, the other competitions or the ratings, and the tool's description still
names three pages. The test harness shows the same strain: `round_collector` takes twenty parameters, thirteen
of them a switch or two for each page (`tests/collect_harness.py:127-149`).

The same thing has three names: the fact (`probable_lineups`, `official_lineups`), the bronze source
(`outlet_lineup`, `official_lineup`) and the table (`outlet_views`, `official_lineups`). And every contract
lives under `contracts/xy/`, the first slice's name, where `structure.md` says `contracts/<domain>/`.

### 4. The application lives inside the MCP adapter, and is wired twice

- `mcp/advisor.py` (1,310 lines) and `mcp/tools/lineup.py`, `cards.py` and `review.py` (2,136 lines) hold the
  gathering of facts, the pricing, the simulation's orchestration, the answers' wording and the logging. About
  250 of those lines register tools. The command line, the alerts and the calibration import the tool modules
  as libraries.
- Each tool is a closure over one user's `Advisor`. That fits one process per user on a Mac. A remote server
  gets its user with each request.
- **Paths are worked out in many places.** Eight modules each name a folder under `data/local`; `mcp/server.py` and
  `cli/__main__.py` derive `lake.root.parent / "collect"`, `"calibration"`, `"reviews"`, `"decisions"`,
  `"league"` and `"alerts"` between them. They don't agree: `serve` takes its rules and decision log from the
  default folders whatever `--lake` says (`cli/__main__.py:52-53`), while the alerts' check and `calibrate` take
  them from beside the lake (`:106`, `:164-165`). With the default lake it's the same place; with any other, the
  server and the scheduled check would read different rules.
- **The tests assemble their own server.** `tests/xy_harness.py:59-111` registers the tools and builds the
  `Advisor` by hand, a copy of `build_advisor` (`mcp/server.py:122-185`) that keeps the stores in different
  folders and leaves two tools out. 90 test files run on that copy; one (`integration/xy/test_server.py`) runs
  on the real wiring. A tool wrongly wired in `build_advisor` would pass almost every test.
- Three pairs of packages import each other (`domains` and `lake`, `lake` and `web`, `domains` and `league`):
  each log's model lives in one package and its file in another.

### 5. Duplicated logic

| What | Where | Why it matters |
|---|---|---|
| Gathering one player's facts | `advisor.gather` and `calibrate._score_match` (`mcp/calibrate.py:351-432`) | The model that is scored and the model that answers can drift apart without a test noticing |
| What a player's events are worth | `engine/points.py` ("the one place") and `review._points` (`domains/review.py:294-333`) | A new event needs both, and `scoring_for` |
| Classic's values | `league/rules.py:34-47` and `domains/review.py:40-47` | Two copies of the same eight numbers |
| "By his name, or else by his surname" | `availability/gold.py:114`, `availability/news.py:103`, `raters.py:99`, `calibration.py:308`, `cards.py:267`, `mcp/calibrate.py:197` and `:390` | Seven copies of the matching rule, in two spellings |
| The likeliest scorers | `tools/lineup.py:486` (the chance if he starts, `SCORERS_SHOWN`) and `domains/cards.py:440` (starting or coming on, `SCORERS`) | The same player gets two "chances to score"; `p_scores` means one thing in the outlook and the lineup and another in the card |
| Resolving names within a squad | `tools/lineup.py:846`, `league/fielded.py:120`, `league/squads.py:90` | Three copies of found, ambiguous, unknown |
| The caveats about a player's facts, and their sources | `advisor.py:1077-1107` and `tools/lineup.py:504-575` | The same sentences written twice |
| "What the collector tried" on a refresh item | `advisor.py:654`, `tools/lineup.py:762`, `tools/cards.py:226`, `:455` | Four copies of one line |
| Writing a JSON file atomically | `league/rules.py:286`, `squads.py:74`, `fielded.py:82`, `lake/calibration_store.py:60` | Four copies; each must move to S3 |
| Appending a line to a month's log | `lake/alert_log.py`, `decision_log.py`, `review_log.py` | Three identical classes |
| One-domain "submissions" and one-payload "facts" | Seven functions in `web/collector.py:206-238`, seven dataclasses in `web/readers/` | The same two lines, seven times each |
| A reader's skeleton | Seven readers: check the title, read each club or row and name the ones that fail, check that the whole holds together | The same fifteen lines and messages, seven times |
| Constants | `ROME` ×5, the four roles ×4, role words ×2, English month names ×2, Italian ones ×2, `_BEFORE_THE_LOCK` ×2, the report's ten buckets ×2, the 90% interval's z ×2 | Small, but they are how copies start |

### 6. Dead code and leftovers

| What | Where |
|---|---|
| Used only by tests | `player_form` (`domains/season/gold.py:35`), `draw_rounds` (`engine/simulate.py:216`), `recommended` (`engine/simulate.py:490`) |
| A layer nothing writes | `Layer = Literal["silver", "gold"]` (`lake/duckdb_store.py:34`): no gold table has ever been written |
| A check with nothing to check | `sqlfluff`: the repository has no `.sql` file; its config, its pre-commit hook and its dependency stay |
| `Facts` typed as `Sequence[Any]` | `mcp/advisor.py:282-294`: the twelve tables lose their row types, so `mypy --strict` can't help there |
| `finished_round` in the wrong place | It's about fixtures, lives in `domains/calibration.py`, and makes `web/` import calibration |
| Stale docstrings | `cli/__main__.py:1-9` (lost its line breaks), `web/readers/__init__.py` ("There is one"), `scripts/checks/task_check.py:4` ("`mvp-lineup`"), `scripts/hooks/stop_check.py:3` ("about 10 seconds"), `scripts/checks/hook_config.py:6` ("10-minute limit"; it is two) |
| Rules that can't fire | The guard's "before the remote go-ahead" rules (`scripts/hooks/guard.py:160-205`): the remote has existed since October |
| The walking skeleton | Retired on 2026-10-31; `BronzeEnvelope` still gives `skeleton` as its example, and its three files are still in the owner's `data/local/lake` |
| Tests importing tests | Seven imports of data or helpers from another test module, two of them in `tests/lineup_speed.py` |

### 7. Tests: where the time goes

1,569 tests; 28,500 lines against 16,800 of product code.

| Run | Time |
|---|---|
| CI, `make check` (run 43766697604) | 317 s, tests 305 s of it |
| CI, the last ten runs | 184 to 334 s, median 238 s, four over the 300 s budget |
| This Mac, the suite without coverage | 4 min 06 s quiet, 5 min 05 s busy |
| This Mac, the suite with coverage on, as `make check` runs it | **7 min 33 s**, and one timing test failed |
| `make test-fast` (the Stop hook) | **39 s**; `quality.md` says under 20 |

| Layer | Tests | Summed time | Share |
|---|---|---|---|
| Unit | 783 | 11 s | 1% |
| Contract | 113 | 25 s | 3% |
| Integration | 224 | 212 s | 24% |
| Property | 104 | 316 s | 35% |
| Acceptance | 345 | 336 s | 37% |

- **304 tests take a second or more, and they are 92% of the time.** 246 tests go through an in-process MCP
  client: 504 s.
- **Their set-up is the cost, not their question.** Alone on a quiet machine, the lineup harness takes 0.47 s to
  set up and 0.44 s for the first question, which collects the pages; any later question takes 0.14 to 0.20 s.
  Under a profiler, the set-up is mostly registering 20 tools (their JSON schemas are generated again for every
  test), the client checking each tool's output schema on its first call, and writing 20 Parquet files.
  Copying a finished lake takes 0.02 s.
- **Coverage nearly doubles it.** The same suite used 810 CPU-seconds without the tracer and 1,576 with it. On
  this Mac the full `make check` is therefore about eight minutes, where CI's faster machine takes five.
  Coverage's faster core can't be used: it can't measure branches on Python 3.12 (tried; coverage 7.17 falls
  back with a warning).
- **One timing test can fail on a busy machine.** `test_a_whole_squad_reads_quickly`
  (`tests/integration/lineup/test_reads.py:202`) asserts that gathering a squad takes under one second of wall
  clock, inside the traced suite. It took 1.02 s in the run above and failed. The other budget tests time CPU
  seconds in a process of their own, which is why they don't.
- **Six budget tests take 93 s.** Each starts a process, builds a round and times an answer three times.
- **17 tests under `tests/property` reach the disk or the tools** (112 s). Four aren't Hypothesis tests:
  `test_p5_context_moves_nothing` asks for 112 outlooks to show something the types already guarantee, since
  the model's inputs have no field for news or rest. That is why `make test-fast` is at twice its budget.
- **339 tests (22%) test the tooling and the repository itself** (checks, hooks, the workflow, the docs), in
  45 s.

### 8. Tests that check themselves

- **Phrase tests.** `tests/unit/test_repo_hygiene.py` has about 230 lines asserting that the README, the guide,
  the prompt and the answer formats contain given phrases ("Built in `mvp-lineup`", "Start Costa instead of
  Bianchi", "Amazon SNS"). Each was written from the sentence it checks. They break on any rewording and they
  don't notice staleness: the README stops at `mvp-lineup`, names 7 of the 10 tools that aren't submit tools
  (`match_card`, `round_overview` and `review_round` are missing) and says Fantadamus reads three pages, and
  every test is green.
- **Mirror tests.** A test asserts that the mutation settings equal a list written out again in the test
  (`test_repo_hygiene.py:299-306`); another that `make check`'s commands equal the literals beside them
  (`acceptance/test_local_gates.py:71-78`). Changing the setting means changing its copy.
- **Tests of other people's tools.** `test_at1_format_lint_gate` and `test_at2_type_gate` hand ruff and mypy a
  bad file to prove that ruff and mypy work. They were Phase 0's acceptance tests; Phase 0 was signed off on
  2026-10-26.
- **A parallel wiring** (section 4): most tests check a server the product doesn't run.
- **Pinned constants.** The `start_values` fixture (`tests/conftest.py:74-91`) puts the two calibrated values
  back to their starting ones for 20 hand-worked modules, by patching the three modules that imported them.
  Each newly calibrated constant must be added by hand, and a module that imported it by value is missed
  silently.
- **Glue tested against fakes.** `integration/alerts/test_command.py` replaces `collect_due` and `check_alerts`
  and asserts what the fakes received. That is fine for ten lines of glue, but it is why the path mismatch in
  section 4 went unseen.

What is **not** self-referring: the engine's unit tests, the hand-worked acceptance tests, the contract tests on
recorded pages, and the workflow's policy tests (actions pinned, read-only permissions, no
`pull_request_target`).

### 9. The plan against what was built

- **Gold.** `tech.md` says questions are answered from precomputed gold data products. The lake has never
  written one: `domains/*/gold.py` are functions run per question over silver. For two users that is simpler
  and right; the steering should say so, and section 2 is where precomputing first pays.
- **v1's platform.** `tech.md` spends much of its length on Iceberg, Glue, Athena, Lake Formation, Step
  Functions and data mesh. The lake is 2.4 MB after three weeks; a season is tens of megabytes. Athena answers
  in seconds and can't serve a chat. `structure.md` says "no new tooling or machinery unless a feature needs it
  now".
- **`structure.md`** lists nine paths that don't exist (`.github/rulesets/main.json`, `docs/data-products/`,
  `src/fantadamus/quality/`, `scripts/smoke/`, `scripts/selftest/`, `infra/`, `tests/golden/`, `tests/infra/`,
  `private.example.toml`). `quality.md` lists checks that don't run (data-quality rules, infrastructure, the IAM
  self-test, moto).
- **`engineering-foundation`** was signed off on 2026-10-26 with 18 boxes still open (tasks 10 to 12 and 16: the
  ADRs for IaC and the account, the bootstrap, the stack, the first deploy). They moved to Phase 3 in the
  re-plan, but not in the file.
- **The README** is five slices behind (section 8).
- **Specs that don't exist.** The steering files, the method and the agent prompt refer twenty times to
  `decision-engine`, `chat-agent`, `data-foundation`, "Spec 0" and "Spec 1": the plan from before the re-plan of
  2026-10-26. None is under `.kiro/specs/`. `engineering-foundation`'s task list still names 20 test files that
  were never written, for the AWS work and the retired skeleton.
- **What Phase 3 must settle that the code doesn't yet:** whether the sites accept collection from AWS addresses
  (ADR-0006 approved it from the user's Mac); two users writing the same files; the user arriving with each
  request; remote MCP sign-in.

### 10. What the tools cost each conversation

| Sent to the model when the tools load | Characters |
|---|---|
| The agent prompt (12,911 of its 13,000 budget) | 13,104 |
| 22 tool descriptions | 15,708 |
| 22 input schemas | 38,485 |
| **Total** | **67,297, about 17,000 tokens** |
| Output schemas, if the client passes them on | 98,738 more |

The twelve submit tools are 36,000 of those characters. They exist for the fallback: since ADR-0006 Fantadamus
reads each fact's page itself, and Claude only fills what it couldn't.

## Recommendations, in order

Sizes: **S** one small pull request, **M** one pull request, **L** several.

### A. Before the schedule is installed

**R1. Store the new rows, not the whole table.** (S to M)

1. In `facts.submit` and `submit_many`, append the rows of the payloads just stored to the silver file: DuckDB
   reads the old file and the new rows and writes the file again, without old rows passing through Python.
2. In `duckdb_store.fill`, load rows in bulk (a temporary JSON-lines file and `read_json` with the table's
   column types, static SQL) in place of parameterised inserts.
3. Keep `rebuild` for when a contract or `to_rows` changes, as `fantadamus rebuild [--table]`.

*Done when* a property test shows that appending gives the same table as rebuilding, for any order of
submissions, and a timing test stores one read into a table of 200,000 rows in under a second.

**R2. Read only what an answer uses.** (M)

1. Let DuckDB pick each outlet's latest submission for a match at `as_of` (one query with a window function), so
   that Python sees one read's rows; the movement since the last answer is one more query at that time.
2. Work out a match's latest lineups once per `gather`, not once per player (keep them in `_Recent`).
3. Read the ratings only for the outlook and the card, or keep the raters' bias as a small table rebuilt when
   ratings are stored. That would be the first gold table.
4. Read a log's months as needed: `last` reads the newest file, `confirmed` and `last_worked` the months in the
   window; parse each file once per answer.

*Done when* a timing test shows a lineup's reading time unchanged with 60 stored reads of the round page in the
window.

### B. Before Phase 3: one application, thin adapters

**R3. One object that knows where everything is.** (M)

1. `Files(root)`: read, write atomically, append a line, list. The only code that touches the disk for private
   state; the S3 version has the same four methods.
2. `JsonFile[Model]` and `JsonlLog[Model]` on top of it replace the four atomic writers and three log classes.
3. `Stores.at(home)` builds the lake, rules, squads, fielded lineups, decision log, collection log, robots
   cache, calibration store, review log and alert log. The command line and the server take one `--home`.

*Done when* `grep -rn "root.parent" src` finds nothing, no module outside storage names `data/local`, and one
test runs `serve`, `collect --due` and `calibrate` on a home that isn't the default and each finds the others'
files.

**R4. Move the application out of `mcp/`, and wire it once.** (L, mechanical)

1. A package `advice/`: `facts.py` (`Facts`, `gather`, freshness, the refresh plan), `compare.py`, `lineup.py`,
   `cards.py`, `review.py`, `alerts.py`, `calibrate.py`.
2. `mcp/` keeps `server.py` and one `tools.py`: each tool is its description and three lines that take the
   request's application and call the use case. The user is an argument of the call, not of the server.
3. `build_app(stores, config, clock, transport)` is the one wiring. The test harness calls it with a fake
   transport and a clock, and loses its own `register` calls.

*Done when* the harness has no `register(` call, a test compares `list_tools()` with the documented list, and
the real answers on a copy of the lake are byte-identical before and after (as PR #73 checked).

**R5. One registry of facts and pages.** (L; with R4 or after)

1. `Domain` carries what is scattered: the fact's name, its submit description, its freshness, its cadence.
2. `PageSpec(kind, config key, reader, domains)` in one table; the collector's `reads()`, `collect()`, six
   page methods and eight submissions functions become one loop. Readers return one `Read[P]`.
3. A table's two SQL strings are derived from its row model.
4. One name per fact, for the fact, the bronze folder and the table. Contracts move to `contracts/<domain>/`.
5. The `collect` tool's list of facts, the command line's and the harness's switches come from the registry.

*Done when* adding a page changes its contract, its reader, one registry entry and the reading list, and a
test fails if the `collect` tool and the collector disagree about which facts can be read.

**R6. One way to gather, one way to price.** (M)

1. `gather` takes `officials: bool`; calibration uses it in place of `_score_match`'s copy.
2. `event_points(values, counts)` over the league's event names serves the model (expected counts), the
   simulation (drawn) and the review (real). The fantasy average's values come from `CLASSIC`.

*Done when* `calibrate.py` no longer calls `availability`, `penalty_share` or `penalty_order` itself, and adding
an event to `EventName` fails one test until it is priced in one place.

**R7. The small merges of section 5 and the leftovers of section 6.** (S, several)

`named(name, mates)` in `players/resolve.py`, for the seven copies of "by name, or else by surname";
`resolve_all(names, players)`; `noted(items, tried)`; `PlayerFacts.sources()` and `caveats()`; one definition
of the likeliest scorers, and one meaning for `p_scores` (name the card's `p_scores_in_match`); the readers'
shared skeleton in `web/readers/__init__.py`; the shared constants in `core/`; `finished_round` to
`fixtures/gold.py`; real row types on `Facts`; the three test-only functions out of `src/`; the unused layer;
the guard's go-ahead rules; the docstrings.

### C. Tests

**R8. Make a through-the-tools test cost its question.** (M)

1. A finished lake built once per worker for each harness variant, and copied for each test (0.02 s).
2. After R4, tests call the use case and read `model_dump(mode="json")`; `integration/xy/test_server.py` and one
   test per tool keep going through the protocol.
3. One process for the six budget tests: `python -m tests.lineup_speed --all` prints every timing, a session
   fixture reads them, each acceptance test asserts its own. `test_a_whole_squad_reads_quickly` joins them, in
   CPU seconds, and stops failing on a busy machine.

*Expected*, to be measured after step 1: about half of the suite's time. Coverage's share falls with it; its
faster core needs a newer Python than 3.12, which is a question for Phase 3, not for now.

**R9. Put each test in the layer it is.** (S)

Move the 17 disk-bound tests out of `tests/property`; restate as pure the ones whose property is about a pure
function (as-of on `latest_by` and `_fresh`; "context moves nothing" on the model's inputs). `make test-fast`
returns to its 20 seconds. Whether a disk-bound property may run fewer than 500 examples is decision 2.

**R10. Replace the phrase tests with tests derived from the code.** (S)

Keep: the git-ignore checks, the prompt's budget, the JSON and plist blocks that must parse, every event named
in the rules guide, every calibrated constant marked in the method. Add: every tool the server lists is named in
the README, the prompt and the player guide. Delete: the phrase lists and the mirror tests.

**R11. Constants as a value.** (M)

A frozen `Constants` in `engine/constants.py` with two instances, `CALIBRATED` and `STARTING`. Engine functions
take `constants=CALIBRATED`; hand-worked tests pass `STARTING`; a recalibration check passes its candidate. The
`start_values` fixture goes, and a newly calibrated value changes one file.

**R12. Retire what tests the tools.** (S; decision 2)

`sqlfluff` with its config, hook and dependency, until a `.sql` file exists. The two Phase 0 acceptance tests of
ruff and mypy move to a `make selftest` run at phase gates.

### D. The plan and the docs

**R13. Say what gold is.** (S) In `tech.md`: gold is computed on read in the MVP and materialised where a
measurement asks (R2 step 3 is the first). Drop the unused layer, or use it there.

**R14. Size v1's platform to the data.** (S to write; decision 3) Phase 3 as: the same Parquet layout on S3,
DuckDB inside the Lambda, EventBridge Scheduler calling one collection Lambda, SNS for alerts, each user's JSON
under a prefix with conditional writes. Iceberg, Glue, Athena, Lake Formation and Step Functions wait for a
measurement that asks for them. Before designing: fetch the approved pages once from a Lambda, to learn whether
the sites accept it; if they don't, collection stays on the owner's Mac and syncs.

**R15. Bring the steering and the README up to date.** (S) Remove or mark the nine paths and the checks that
don't exist; replace the twenty references to specs that don't exist; move `engineering-foundation`'s open
tasks, and the tests they name, to Phase 3's spec; rewrite the README's status from `product.md`'s table; fix
the five docstrings and the `collect` tool's description.

**R16. Cut what the tools cost.** (M) One `submit_facts(fact, payload, source_url, captured_at)` in place of
twelve tools; `read_page` already names the facts a page carries, and returns each one's shape and guidance
with them, so Claude gets a schema when it needs it. About 8,000 tokens less per conversation, and no new tool
per source. Then look at one real conversation's request: if Claude Desktop passes output schemas to the model,
return the large answers without one.

**R17. Restart the server.** The server attached to this review's session lists 19 tools; the code has 22
(`submit_injuries`, `submit_suspensions` and `submit_ratings` are missing), so it was started before PR #130.
Restart the Claude app to get them, and the alerts' code with them.

## Decisions for the owner

1. **Do R1 and R2 now, as a small slice of their own, before the schedule is installed; then R3 to R7 as the
   first step of Phase 3.** Recommended: yes. Without R1 the schedule slows itself down within two rounds.
2. **Two changes to the gates:** disk-bound property tests run 100 examples in the pull-request gate and 500 at
   phase gates (R9); `sqlfluff` and the two tests of ruff and mypy leave the pull-request gate (R12).
   Recommended: yes to both; neither removes a check of the product.
3. **Phase 3's platform is the MVP's layout on S3 with DuckDB in a Lambda (R14), and `tech.md` says so.**
   Recommended: yes, recorded in ADR-0003.

## How to repeat the measurements

```bash
# Every test's time, with the thorough profile
HYPOTHESIS_PROFILE=ci uv run --frozen pytest -n 4 --dist worksteal --junitxml=junit.xml

# The inner loop
time make test-fast

# CI's last runs
gh run list --workflow ci.yml --limit 10 --json createdAt,updatedAt,conclusion
```

The other numbers came from a copy of `data/local` and six throwaway scripts: a static audit with `ast`, the
answers' timings, a profile of one rebuild, a comparison of bulk loading, the harness's cost and the tools'
sizes. They aren't in the repository; the timing tests R1 and R2 ask for would take their place.
