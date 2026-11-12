# Implementation Plan: `mvp-sources` (Phase 2, eighth slice)

Status: **Approved by the owner, 2026-11-12** · From the approved [requirements](requirements.md) and the [design](design.md)

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/so-<n>-<slug>`. Sub-tasks are the steps inside it, each with its own
  test, written first and seen failing (red → green).
- **Before a task**, run `make task-check TASK=<n> SPEC=mvp-sources`. Task 1's branch makes this spec the default (`CURRENT_SPEC` in
  `scripts/checks/task_check.py`, and `CLAUDE.md`).
- **A ticked box** (`- [x]`) marks a task or step as done; the agent ticks it on the task's branch.
- **The property tests P1–P5 in the design are required.** No task is optional.
- **Each task ends with the task report**; the owner approves the pull request, the agent squash-merges it.
- **Breaking the code on purpose:** each code task does it once before its report, from a green baseline, and says what it found.
- **Tests for this spec** live in a `sources/` folder in each test layer. Pages are invented in the real layouts; a real page never reaches
  the repository.
- **No real page is read from a branch:** a task's real check runs from `main` after it merges.

## Tasks

- [ ] 1. The routes
  - Branch: `docs/so-1-routes` · Depends on: none · ADRs: none
  - [ ] 1.1 **Owner:** accept ADR-0007.
    - _Requirements: AT-1 (R1.1)_
    - _Test: recorded in the ADR_
  - [ ] 1.2 The source registry and the reading list record the five pages; this spec becomes the current one.
    - _Requirements: R1.1, R8.1_
    - _Test: `tests/unit/test_sources_config.py::test_every_collector_page_is_allowed`;
      `tests/unit/checks/test_task_check.py::test_default_is_the_current_spec`_

- [ ] 2. The other competitions' fixtures
  - Branch: `feat/so-2-other-fixtures` · Depends on: 1 · ADRs: ADR-0007
  - [ ] 2.1 The Wikipedia reader on Football box templates, the contract, the silver table, the collector page with its switch and cadence,
    and `submit_other_fixtures`.
    - _Requirements: R1.2, R2.1, R7.1_
    - _Test: `tests/unit/sources/test_wiki_fixtures.py`; **P2** `tests/property/sources/test_wiki_fixtures.py::test_p2_a_match_read_back`;
      `tests/contract/test_sources_contracts.py::test_other_fixtures_payload`;
      `tests/integration/sources/test_other_fixtures_page.py::test_read_stored_and_switched_off`_

- [ ] 3. Rest days
  - Branch: `feat/so-3-rest-days` · Depends on: 2 · ADRs: none
  - [ ] 3.1 `rest_days` for each side of a match, on the card and in the outlook, with its line and its source.
    - _Requirements: R2.2, R2.3_
    - _Test: **AT-2** `tests/acceptance/sources/test_rest_days.py::test_at2_rest_days_by_hand`, `::test_at2_on_the_card_and_the_outlook`;
      **P1** `tests/property/sources/test_rest_days.py::test_p1_rest_days_in_order`_

- [ ] 4. Injury and ban detail
  - Branch: `feat/so-4-unavailable` · Depends on: 1 · ADRs: ADR-0007
  - [ ] 4.1 The injury and ban readers with their rules, the contracts, the silver tables, the two collector pages with their switches and
    cadence, and `submit_injuries` and `submit_suspensions`.
    - _Requirements: R1.2, R3.1, R7.1_
    - _Test: `tests/unit/sources/test_fcit_unavailable.py`; **P3** `tests/property/sources/test_injury_rules.py::test_p3_a_known_kind_and_a_later_return`;
      `tests/contract/test_sources_contracts.py::test_injuries_and_suspensions_payloads`;
      `tests/integration/sources/test_unavailable_pages.py::test_read_stored_and_switched_off`_

- [ ] 5. The detail on the answers
  - Branch: `feat/so-5-detail` · Depends on: 4 · ADRs: none
  - [ ] 5.1 The reason and the return on the card's out list, the lineup's concerns and the outlook; one booking from a ban; the
    disagreement; no chance moves.
    - _Requirements: R3.2, R3.3_
    - _Test: **AT-3** `tests/acceptance/sources/test_detail.py::test_at3_detail_on_the_answers`, `::test_at3_one_booking_from_a_ban`,
      `::test_at3_a_disagreement`; **P5** `tests/property/sources/test_no_number_moves.py::test_p5_context_moves_nothing`_

- [ ] 6. Per-match ratings
  - Branch: `feat/so-6-ratings` · Depends on: 1 · ADRs: ADR-0007
  - [ ] 6.1 The ratings reader for three desks, the contract, the silver table, the collector page with its switch and cadence, and
    `submit_ratings`.
    - _Requirements: R1.2, R4.2, R7.1_
    - _Test: `tests/unit/sources/test_fco_ratings.py`; `tests/contract/test_sources_contracts.py::test_ratings_payload`;
      `tests/integration/sources/test_ratings_page.py::test_read_stored_and_switched_off`_
  - [ ] 6.2 The league's rating in each calibration set, from the reads or the page; `fantadamus recalibrate` counts it as evidence.
    - _Requirements: R4.1, R4.3_
    - _Test: **AT-4** `tests/acceptance/sources/test_ratings.py::test_at4_from_two_reads_by_hand`, `::test_at4_from_the_page`,
      `::test_at4_counted_as_evidence`_

- [ ] 7. Rater bias
  - Branch: `feat/so-7-raters` · Depends on: 6 · ADRs: none
  - [ ] 7.1 `desk_bias` with its interval; the claim on the outlook and the card; the expected vote unchanged.
    - _Requirements: R5.1, R5.2, R5.3_
    - _Test: **AT-5** `tests/acceptance/sources/test_raters.py::test_at5_bias_by_hand`, `::test_at5_a_claim_shown`,
      `::test_at5_the_expected_vote_unchanged`; **P4** `tests/property/sources/test_raters.py::test_p4_bias_in_its_interval`_

- [ ] 8. Anytime-scorer odds, researched
  - Branch: `docs/so-8-scorer-odds` · Depends on: none · ADRs: none
  - [ ] 8.1 A new ADR, the eighth: the routes compared, with each one's coverage, cost and terms, how the method uses them, and a one-round trial plan.
    - _Requirements: R6.1, R6.2_
    - _Test: the ADR exists with every section_
  - [ ] 8.2 **Owner:** read ADR-0008, and approve or turn down the trial.
    - _Requirements: AT-6 (R6)_
    - _Test: recorded in the ADR_

- [ ] 9. A real check and this slice's sign-off
  - Branch: `docs/so-9-gate` · Depends on: 2, 3, 4, 5, 6, 7, 8 · ADRs: none
  - [ ] 9.1 The budgets with the new facts, and the docs: answer formats, method §A8, the player guide.
    - _Requirements: R7.2, R8.1_
    - _Test: **AT-7** `tests/acceptance/sources/test_budgets.py::test_at7_a_card_and_an_outlook_in_budget`;
      `tests/unit/test_repo_hygiene.py::test_answer_formats_show_rest_days`_
  - [ ] 9.2 Real data from Claude Code on `main`: the new pages read, a card with rest days and injury detail, a round's ratings kept.
    - _Requirements: R1.2, R2.3, R3.2, R4.1 (AT-8)_
    - _Test: what each page gave, its time and size, in the report without players' figures_
  - [ ] 9.3 A mutation run on the core modules, with survivors read; the slice report: tests, coverage, quality, cost, open risks and the
    acceptance tests.
    - _Requirements: R7.2; phase gate (`quality.md`)_
    - _Test: the report exists with every section; `make check` green on `main`_
  - [ ] 9.4 **Owner:** sign off this slice.
    - _Requirements: Phase gate (`quality.md`)_
    - _Test: sign-off recorded in the report_
