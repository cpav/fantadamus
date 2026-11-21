# Implementation Plan: `mvp-fixes` (Phase 2, eleventh slice)

Status: **Approved by the owner, 2026-11-21** · From the approved [requirements](requirements.md) and the
[design](design.md)

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/fx-<n>-<slug>`. Sub-tasks are the steps inside
  it, each with its own test, written first and seen failing (red → green).
- **Before a task**, run `make task-check TASK=<n> SPEC=mvp-fixes`. Task 1's branch makes this spec the default
  (`CURRENT_SPEC` in `scripts/checks/task_check.py`, and `CLAUDE.md`).
- **Work in a worktree, never in `~/Documents/fantadamus`:** the owner's schedule runs from that folder on `main`
  every 15 minutes, and would run a task's code if its branch were checked out there.
- **A ticked box** (`- [x]`) marks a task or step as done; the agent ticks it on the task's branch.
- **The property tests P1–P4 in the design are required.** No task is optional.
- **Each task ends with the task report**; the owner approves the pull request, the agent squash-merges it. After a
  code task merges, the owner quits and reopens Claude Desktop so that its server runs the new code.
- **Breaking the code on purpose:** each code task does it once before its report, from a green baseline, and says what
  it found.
- **Tests for this spec** live in a `fixes/` folder in each test layer.
- **No number may move.** Every earlier acceptance test stays as it is; a task that needs to change one stops and asks.
- **The owner's lake is only ever read as a copy**, from here; a report gives times and counts only.

## Tasks

- [ ] 1. A failed try doesn't count as a read
  - Branch: `fix/fx-1-failed-tries` · Depends on: none · ADRs: none · **Merged before round 13's alerts window**
  - [ ] 1.1 This spec becomes the current one. A robots.txt that gets no answer, a timeout or a server error outside
    the block statuses is remembered for the run and not cached; each of the host's pages fails with "robots.txt
    couldn't be read"; robots.txt is asked once per host per run.
    - _Requirements: R1.1, R1.3_
    - _Test: `tests/unit/fixes/test_fetch.py::test_robots_without_an_answer_fails_the_hosts_pages`,
      `::test_robots_server_error_fails_the_hosts_pages`, `::test_robots_is_asked_once_a_run`,
      `::test_robots_block_status_still_disallows`, `::test_robots_not_found_still_allows_everything`_
  - [ ] 1.2 A page's 4xx outside the block statuses is `missing`, the site's answer; a 5xx outside them is `failed`.
    - _Requirements: R1.1, R1.4_
    - _Test: `tests/unit/fixes/test_fetch.py::test_a_page_the_site_says_is_gone_is_missing`,
      `::test_a_page_server_error_fails`; `tests/unit/fixes/test_collector.py::test_outcomes_by_error`_
  - [ ] 1.3 The collection log counts answered tries: `last_answered` and `last_failed`; lines logged before read as
    they are.
    - _Requirements: R1.2_
    - _Test: `tests/unit/fixes/test_collect_log.py::test_a_failed_try_is_not_the_last_answered`,
      `::test_last_failed`, `::test_old_lines_read_as_they_are`_
  - [ ] 1.4 The cadence and the answers: a failed page is due at the next run; an answer waits `RETRY_AFTER` after a
    failed try; a block still waits for the cadence.
    - _Requirements: R1.2, R1.3, R1.4_
    - _Test: `tests/unit/fixes/test_cadence.py::test_a_failed_page_is_due_at_the_next_run`,
      `::test_an_answer_waits_after_a_failed_try`, `::test_a_block_waits_for_the_cadence`;
      **P1** `tests/property/fixes/test_due.py::test_p1_due_follows_the_last_answered_try`;
      **P2** `tests/property/fixes/test_retry.py::test_p2_one_robots_try_a_run_and_no_page_requested`_
  - [ ] 1.5 The run's report, `collect --report` and the refresh plan's note say a failed page is tried again.
    - _Requirements: R1.5_
    - _Test: `tests/integration/fixes/test_report.py::test_a_failed_page_is_shown_with_its_cause_and_retry`,
      `::test_the_refresh_note_says_it_tries_again`_
  - [ ] 1.6 The proof: the collector on a fake transport that can't reach two hosts, then the next tick; and from here,
    Saturday 21 November's run replayed on a copy of the owner's lake.
    - _Requirements: R1.2, R1.6_
    - _Test: **AT-1** `tests/acceptance/fixes/test_at1_failed_tries.py::test_at1_a_failed_try_is_tried_again_at_the_next_run`;
      **AT-2** `tests/acceptance/fixes/test_at2_polite.py::test_at2_retries_stay_polite`;
      **AT-3** `tests/acceptance/fixes/test_at3_report.py::test_at3_the_report_says_it_tries_again`;
      AT-8's replay in the task report (times and counts)_

- [ ] 2. `collect` takes every fact
  - Branch: `fix/fx-2-collect-facts` · Depends on: 1 · ADRs: none
  - [ ] 2.1 `CollectFact` beside `FACTS`, a test that they agree; `PAGE_NAMES` beside `PAGE_FACTS`; the tool's `fact`
    and description from them.
    - _Requirements: R2.1, R2.2, R2.3_
    - _Test: `tests/unit/fixes/test_collect_facts.py::test_the_literal_is_the_collectors_list`,
      `::test_every_page_with_a_fact_has_a_name`;
      **AT-4** `tests/acceptance/fixes/test_at4_collect.py::test_at4_collect_reads_every_fact`_

- [ ] 3. One list of a player's sources
  - Branch: `fix/fx-3-sources` · Depends on: 1 · ADRs: none
  - [ ] 3.1 `PlayerFacts.sources()`, called by the lineup, the card, the outlook and "X or Y?"; the review's sources
    checked as they are.
    - _Requirements: R3.1, R3.2_
    - _Test: `tests/unit/fixes/test_sources.py::test_news_and_rest_days_are_sources`;
      **P3** `tests/property/fixes/test_sources.py::test_p3_every_fact_present_has_its_source`;
      **AT-5** `tests/acceptance/fixes/test_at5_sources.py::test_at5_a_lineup_names_the_injured_page`,
      `::test_at5_every_answer_names_the_pages_it_shows`_

- [ ] 4. The penalty note says who's out
  - Branch: `fix/fx-4-penalty-note` · Depends on: 1 · ADRs: none
  - [ ] 4.1 "X, first on the list, is out, so Y takes the penalties: counted in full", and the plural; today's note
    otherwise.
    - _Requirements: R4.1, R4.2_
    - _Test: `tests/unit/fixes/test_penalty_note.py::test_everyone_ahead_out`,
      `::test_two_ahead_out`, `::test_someone_ahead_may_start`;
      **AT-6** `tests/acceptance/fixes/test_at6_penalty_note.py::test_at6_the_note_says_who_is_out`_

- [ ] 5. The review keeps the app's total
  - Branch: `feat/fx-5-app-total` · Depends on: 1 · ADRs: none
  - [ ] 5.1 `LoggedReview` gains `app_total` and `app_differs`; `logged` takes them; `Record` counts `app_rounds` and
    `app_matched`; format 7's line.
    - _Requirements: R5.1, R5.2, R5.3_
    - _Test: `tests/unit/fixes/test_review_log.py::test_the_app_total_is_kept`,
      `::test_a_line_from_before_reads`; **P4** `tests/property/fixes/test_record.py::test_p4_the_app_count_follows_the_latest_reviews`;
      **AT-7** `tests/acceptance/fixes/test_at7_app_total.py::test_at7_the_record_says_how_often_the_app_matched`_

- [ ] 6. The docs, the real check and this slice's sign-off
  - Branch: `docs/fx-6-gate` · Depends on: 2, 3, 4, 5 · ADRs: none
  - [ ] 6.1 The player guide, the README and format 7.
    - _Requirements: R6.3_
    - _Test: `tests/unit/fixes/test_docs.py::test_the_guide_says_a_failed_page_is_tried_again`,
      `::test_the_readme_says_collect_takes_any_fact`_
  - [ ] 6.2 From here, on a copy of the owner's lake: every answer compared field by field before and after; only
    sources and penalty notes differ, listed by kind.
    - _Requirements: R1.6, R3, R4_
    - _Test: **AT-8** `python -m tests.real_lake --compare --fields`, its counts in the slice report_
  - [ ] 6.3 `make mutate ONLY=…` on the collection log and the cadence; no new dependency; the slice report.
    - _Requirements: R6.2_
    - _Test: **AT-9** `tests/acceptance/fixes/test_at9_no_new_dependency.py::test_at9_no_new_dependency`; the mutation score
      in `docs/reports/slice-mvp-fixes.md`_
  - [ ] 6.4 **Owner:** sign the slice off.
    - _Requirements: all_
    - _Test: the slice report_
