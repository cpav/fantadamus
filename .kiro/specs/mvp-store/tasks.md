# Implementation Plan: `mvp-store` (Phase 2, tenth slice)

Status: **Draft, for the owner's approval** · From the approved [requirements](requirements.md) and the [design](design.md)

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/st-<n>-<slug>`. Sub-tasks are the steps inside it, each with its own
  test, written first and seen failing (red → green).
- **Before a task**, run `make task-check TASK=<n> SPEC=mvp-store`. Task 1's branch makes this spec the default (`CURRENT_SPEC` in
  `scripts/checks/task_check.py`, and `CLAUDE.md`).
- **A ticked box** (`- [x]`) marks a task or step as done; the agent ticks it on the task's branch.
- **The property tests P1–P5 in the design are required.** No task is optional.
- **Each task ends with the task report**; the owner approves the pull request, the agent squash-merges it.
- **Breaking the code on purpose:** each code task does it once before its report, from a green baseline, and says what it found.
- **Tests for this spec** live in a `store/` folder in each test layer. A test that writes Parquet files is an integration test, a
  property included, so that `make test-fast` runs none of them.
- **No number may move.** Every earlier acceptance test stays as it is; a task that needs to change one stops and asks.
- **The owner's lake is only ever read as a copy**, from here; its answers stay under git-ignored `data/private/mvp-store/`, and a
  report gives times and counts only.

## Tasks

- [ ] 1. Silver in month files, loaded in bulk
  - Branch: `feat/st-1-months` · Depends on: none · ADRs: none
  - [ ] 1.1 From here, before anything changes: the answers of a copy of the owner's lake at five past times, kept privately. This
    spec becomes the current one.
    - _Requirements: R3.5, R4.2_
    - _Test: `python -m tests.real_lake --record`, its times and counts in the task report;
      `tests/unit/store/test_real_lake.py::test_the_answers_are_kept_where_git_ignores_them`, `::test_only_times_and_counts_are_printed`_
  - [ ] 1.2 The month of a row and the files of a window, pure.
    - _Requirements: R1.2, R3.2_
    - _Test: `tests/unit/store/test_months.py::test_a_row_goes_to_the_month_it_was_captured_in`, `::test_the_files_of_a_window`,
      `::test_without_a_window_every_file`; **P2** `tests/property/store/test_months.py::test_p2_a_window_reads_exactly_its_months`_
  - [ ] 1.3 Rows loaded in bulk from a JSON-lines file, typed by the table's own columns; a table loses its insert statement.
    - _Requirements: R1.2_
    - _Test: `tests/integration/store/test_bulk_load.py::test_every_type_comes_back_as_it_went_in`, `::test_rows_keep_their_order`,
      `::test_the_temporary_file_is_gone`_
  - [ ] 1.4 A table is a folder of month files with `_table.json`; a read takes its window's files, in stored order; a rebuild
    writes the months from bronze, 500 files at a time; a table in the earlier layout is read until then. A store still rebuilds.
    - _Requirements: R1.4, R2.5_
    - _Test: `tests/integration/store/test_layout.py::test_a_rebuild_writes_a_file_for_each_month`, `::test_a_window_reads_only_its_months`,
      `::test_rows_come_back_in_stored_order`, `::test_the_earlier_layout_is_read_until_a_rebuild_replaces_it`,
      `::test_a_rebuild_reads_bronze_in_batches`; `tests/integration/test_atomic_writes.py::test_a_reader_never_sees_half_a_month`_

- [ ] 2. A store appends
  - Branch: `feat/st-2-append` · Depends on: 1 · ADRs: none
  - [ ] 2.1 In step or not, pure: the columns, the rows version, a store under way, the earlier layout.
    - _Requirements: R2.1, R2.3_
    - _Test: `tests/unit/store/test_in_step.py::test_in_step`, `::test_each_way_out_of_step`_
  - [ ] 2.2 A store, under the lake's lock: `_storing`, the bronze files, the rows appended to their month when the table is in
    step, `_table.json`. Bronze never changes.
    - _Requirements: R1.1, R1.3, R2.2_
    - _Test: **AT-1** `tests/acceptance/store/test_append.py::test_at1_the_table_a_rebuild_gives`;
      **P1** `tests/integration/store/test_append.py::test_p1_appending_gives_what_a_rebuild_gives` (it takes over from
      `tests/property/test_lake.py::test_bronze_append_only`); `::test_a_payload_without_rows_keeps_its_bronze`,
      `::test_rows_of_two_months_go_to_two_files`; **AT-3** `tests/acceptance/store/test_silver_stays_right.py::test_at3_two_runs_at_once_keep_both`_
  - [ ] 2.3 A store rebuilds a table that's out of step: an earlier store stopped, at any step; other columns; another rows version.
    - _Requirements: R2.1, R2.3_
    - _Test: **P3** `tests/integration/store/test_stopped.py::test_p3_a_stopped_store_is_healed_by_the_next`;
      **AT-3** `tests/acceptance/store/test_silver_stays_right.py::test_at3_a_run_stopped_between_bronze_and_silver`,
      `::test_at3_a_domain_whose_rows_changed`_
  - [ ] 2.4 `fantadamus rebuild [--table <name>]`, from the one list of domains; a lake in the earlier layout answers after it.
    - _Requirements: R2.4, R2.5_
    - _Test: **AT-4** `tests/acceptance/store/test_rebuild_command.py::test_at4_every_table_or_one`, `::test_at4_no_request_is_sent`,
      `::test_at4_a_lake_in_the_earlier_layout_answers_after_it`; `tests/unit/store/test_domains.py::test_every_domain_is_listed_once`_

- [ ] 3. An answer reads what it uses
  - Branch: `feat/st-3-read` · Depends on: 2 · ADRs: none
  - [ ] 3.1 A read can keep each page's newest submission for a domain's key, and only some values of a column.
    - _Requirements: R3.2, R3.5_
    - _Test: **P5** `tests/integration/store/test_newest.py::test_p5_the_newest_submission_and_nothing_later`;
      `::test_a_tie_keeps_the_whole_submission`, `::test_only_the_values_asked_for`, `::test_stored_order_is_kept`_
  - [ ] 3.2 `Facts` reads the five growing tables that way, with its window and real row types; a movement reads them again as they
    stood; calibration reads everything.
    - _Requirements: R3.2, R3.5_
    - _Test: **P4** `tests/integration/store/test_same_answers.py::test_p4_the_same_numbers_both_ways`;
      **AT-7** `tests/acceptance/store/test_same_answers.py::test_at7_every_tool_answers_the_same_both_ways`,
      `::test_at7_a_movement_is_the_same`, `::test_at7_a_review_and_a_check_are_the_same`;
      `tests/integration/store/test_facts.py::test_calibration_reads_everything`, `::test_a_movement_reads_the_same_window`_
  - [ ] 3.3 The ratings are read only for an answer that shows a claim, and only its clubs'.
    - _Requirements: R3.3_
    - _Test: **AT-6** `tests/acceptance/store/test_reads.py::test_at6_ratings_only_where_a_claim_is_shown`,
      `::test_at6_only_the_clubs_asked_about`_
  - [ ] 3.4 The collector asks for a page's newest stored hashes, and the schedule's check reads the window's official lineups.
    - _Requirements: R1.2, R1.5_
    - _Test: `tests/integration/store/test_collector_reads.py::test_the_newest_reads_hashes`, `::test_what_is_due_reads_the_window`;
      `tests/property/collect/test_collect.py::test_p3_same_pages_store_nothing_new` stays as it is_

- [ ] 4. Logs read once
  - Branch: `feat/st-4-logs` · Depends on: 3 · ADRs: none
  - [ ] 4.1 A log's file is parsed once while it's unchanged, and a read can start at a month.
    - _Requirements: R3.4_
    - _Test: `tests/unit/store/test_logs.py::test_a_file_is_parsed_once_while_unchanged`, `::test_an_appended_line_is_seen`,
      `::test_a_read_from_a_month_skips_older_files`, `::test_a_caller_cant_change_what_is_kept`_
  - [ ] 4.2 The collection log is read from the window's start, and scoring a round reads back to that round; an answer reads each
    log once.
    - _Requirements: R1.5, R3.4_
    - _Test: **AT-6** `tests/acceptance/store/test_reads.py::test_at6_each_log_once_for_an_answer`;
      `tests/integration/store/test_collect_log.py::test_only_the_windows_months`, `::test_scoring_a_round_reads_back_to_it`_

- [ ] 5. Season size, in one timing process
  - Branch: `test/st-5-budgets` · Depends on: 4 · ADRs: none
  - [ ] 5.1 A generated season around a synthetic round: month files, `_table.json`, the logs.
    - _Requirements: R5.1_
    - _Test: `tests/integration/store/test_season.py::test_the_season_has_its_size`, `::test_the_round_still_answers`_
  - [ ] 5.2 One process times every budget, and each budget test reads its own number from it.
    - _Requirements: R5.1, R5.2_
    - _Test: `tests/integration/store/test_timings.py::test_one_process_for_a_whole_run`; unchanged in what they assert:
      `tests/acceptance/lineup/test_lineup.py::test_at9_fast`, `tests/acceptance/rules/test_simulation.py::test_at12_a_squad_with_rules_stays_in_budget`,
      `tests/acceptance/review/test_answer.py::test_at7_in_budget`, `tests/acceptance/cards/test_answer.py::test_at10_in_budget`,
      `tests/acceptance/sources/test_budgets.py::test_at7_a_card_and_an_outlook_in_budget`, `tests/acceptance/alerts/test_budget.py::test_at4_a_check_in_budget`_
  - [ ] 5.3 The season's budgets: a store, the schedule's check, the reading, gathering a squad, every answer and an alerts' check.
    The wall-clock assertion gives way.
    - _Requirements: R1.2, R1.4, R1.5, R3.1, R3.2, R5.3_
    - _Test: **AT-2** `tests/acceptance/store/test_budgets.py::test_at2_a_read_stored_in_two_seconds`, `::test_at2_nothing_due_checked_in_a_second`,
      `::test_at2_a_reader_in_between_sees_before_or_after`; **AT-5** `::test_at5_every_answer_in_budget`, `::test_at5_reading_in_a_second`,
      `::test_at5_gathering_a_squad_in_a_second`; `tests/integration/lineup/test_reads.py::test_a_whole_squad_reads_quickly` loses its timing_
  - [ ] 5.4 No new dependency, and the gate's time before and after.
    - _Requirements: R4.1, R5.2_
    - _Test: **AT-9** `tests/acceptance/store/test_budgets.py::test_at9_no_new_dependency`; the suite's summed time and `make check`'s,
      on `main` before task 1 and on this branch, in the task report_

- [ ] 6. The docs, the real lake and this slice's sign-off
  - Branch: `docs/st-6-gate` · Depends on: 5 · ADRs: none
  - [ ] 6.1 The docs: `tech.md`'s storage row, the README's commands, the lake's own descriptions.
    - _Requirements: R5.4_
    - _Test: **AT-10** `tests/unit/test_repo_hygiene.py::test_the_readme_names_every_command` (from the command line's own list)_
  - [ ] 6.2 From here: the answers of a copy of the owner's lake, compared with task 1.1's, and its times before and after.
    - _Requirements: R2.5, R3.5, R4.2, R5.4_
    - _Test: **AT-8** `python -m tests.real_lake --compare`: identical at the five times; recorded in the report, times and counts only_
  - [ ] 6.3 A mutation run on the new pure functions (`lake/months.py`), with survivors read; the slice report: tests, coverage, quality,
    cost, open risks and the acceptance tests.
    - _Requirements: R5.4; phase gate (`quality.md`)_
    - _Test: the report exists with every section; `make check` green on `main`_
  - [ ] 6.4 **Owner:** sign off this slice. The schedule can then be installed (`docs/player-setup.md`, step 8).
    - _Requirements: Phase gate (`quality.md`)_
    - _Test: sign-off recorded in the report_
