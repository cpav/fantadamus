# Implementation Plan: `mvp-next-round` (after Phase 2, before Phase 3)

Status: **Draft, for the owner's approval** · From the approved [requirements](requirements.md) and the
[design](design.md)

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/nr-<n>-<slug>`. Sub-tasks are the steps inside
  it, each with its own test, written first and seen failing (red → green).
- **Before a task**, run `make task-check TASK=<n> SPEC=mvp-next-round`. Task 1's branch makes this spec the default
  (`CURRENT_SPEC` in `scripts/checks/task_check.py`, its test of the default, and `CLAUDE.md`).
- **Work in a worktree, never in `~/Documents/fantadamus`:** the owner's schedule runs from that folder on `main`.
- **Tests for this spec** live in a `next_round/` folder in each test layer, with `tests/next_round_harness.py`.
- **No earlier acceptance test changes.** The two earlier tests that do are in the design (C2); a task that finds
  another stops and asks.
- **The owner's lake is only ever read as a copy**, from here; a report gives times and counts only.
- **After task 1 merges,** `~/Documents/fantadamus` is brought up to `main`. Claude Desktop needs no restart: no answer's
  code changes.

## Tasks

- [ ] 1. The fixtures daily
  - Branch: `fix/nr-1-daily-fixtures` · Depends on: none · ADRs: none · **Merged before round 14's alert window opens**
  - [ ] 1.1 This spec becomes the current one. The harness, and the tests of what changes, seen failing on the weekly
    fixtures.
    - _Requirements: R1.1, R1.2, R1.3, R1.5, R2.2, R2.3_
    - _Test: **P1** `tests/property/next_round/test_cadence.py::test_p1_due_a_day_after_the_last_answered_read`;
      **P2** `::test_p2_the_next_round_is_read_within_a_day_and_a_run`;
      **AT-1** `tests/acceptance/next_round/test_at1_found_in_time.py::test_at1_the_next_round_is_found_in_time`;
      **AT-2** `tests/acceptance/next_round/test_at2_no_stored_fixture.py::test_at2_no_stored_fixture_holds_it_back`;
      **AT-3** `tests/acceptance/next_round/test_at3_keeps_looking.py::test_at3_it_keeps_looking`;
      **AT-5** `tests/acceptance/next_round/test_at5_alert.py::test_at5_a_round_three_days_on_is_found_and_alerts`_
  - [ ] 1.2 `_ALWAYS["fixtures"]` daily, and the cadence's table in `web/cadence.py`; the two earlier tests that say
    weekly, as the design's C2 changes them.
    - _Requirements: R1.1, R1.4, R3.2_
    - _Test: `tests/unit/collect/test_cadence.py::test_cadence_table`;
      `tests/integration/roles/test_two_pages.py::test_due_reads_only_the_pages_due`_
  - [ ] 1.3 What stays as it is: robots.txt, one request a second, once a run, failed tries, the switch, every other
    fact's cadence and an answer's own reads.
    - _Requirements: R1.4, R2.1, R2.2, R2.3, R2.4_
    - _Test: **AT-4** `tests/acceptance/next_round/test_at4_polite.py::test_at4_a_failed_read_is_tried_again_at_the_next_run`,
      `::test_at4_each_run_asks_once_after_robots_and_a_second_apart`, `::test_at4_switched_off_nothing_is_asked`;
      **AT-6** `tests/acceptance/next_round/test_at6_the_rest_unchanged.py::test_at6_every_other_fact_keeps_its_cadence`,
      `::test_at6_an_answer_reads_as_today`_
  - [ ] 1.4 The docs: `mvp-collect` R7.1 marked as amended, the player guide's step 8; no new dependency.
    - _Requirements: R3.2, R3.3_
    - _Test: **AT-8** `tests/acceptance/next_round/test_at8_docs.py::test_at8_no_new_dependency`,
      `::test_at8_the_docs_say_daily`_

- [ ] 2. The real check and this slice's sign-off
  - Branch: `docs/nr-2-gate` · Depends on: 1 · ADRs: none
  - [ ] 2.1 From here, on a copy of the owner's lake: the replay after round 12's deadline with `main`'s code and with
    task 1's, and every answer compared before and after.
    - _Requirements: R1.1, R1.5_
    - _Test: **AT-7** the replay and `python -m tests.real_lake --record`, then `--compare`; times and counts in the
      slice report_
  - [ ] 2.2 The deliberate faults by hand (the design's testing strategy) and the slice report.
    - _Requirements: R3.2_
    - _Test: `docs/reports/slice-mvp-next-round.md`, with each fault and the test that caught it_
  - [ ] 2.3 **Owner:** sign the slice off.
    - _Requirements: all_
    - _Test: the slice report_
