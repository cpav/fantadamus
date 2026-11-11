# Implementation Plan: `mvp-recalibrate` (Phase 2, seventh slice)

Status: **Draft for the owner's approval, 2026-11-11** · From the approved [requirements](requirements.md) and the [design](design.md)

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/rc-<n>-<slug>`. Sub-tasks are the steps inside it, each with its own
  test, written first and seen failing (red → green).
- **Before a task**, run `make task-check TASK=<n> SPEC=mvp-recalibrate`. Task 1's branch makes this spec the default (`CURRENT_SPEC` in
  `scripts/checks/task_check.py`, and `CLAUDE.md`).
- **A ticked box** (`- [x]`) marks a task or step as done; the agent ticks it on the task's branch.
- **The property tests P1–P5 in the design are required.** No task is optional.
- **Each task ends with the task report**; the owner approves the pull request, the agent squash-merges it.
- **Breaking the code on purpose:** each code task does it once before its report, from a green baseline, and says what it found.
- **Tests for this spec** live in a `recalibrate/` folder in each test layer. Rows, reads and rounds are invented; a real calibration set or
  proposal never reaches the repository.
- **No number changes until task 7:** tasks 1 to 6 keep every constant as it is, and the starting map as the identity.

## Tasks

- [ ] 1. Calibration sets
  - Branch: `feat/rc-1-sets` · Depends on: none · ADRs: none
  - [ ] 1.1 Each scored round's model set kept player by player, privately, with the raw consensus, each chance and what happened, "rated
    without starting" included; rebuilt the same way on `--again`. This spec becomes the current one.
    - _Requirements: R1.1, R1.2, R1.3_
    - _Test: **AT-1** `tests/acceptance/recalibrate/test_sets.py::test_at1_kept_with_the_report`, `::test_at1_rebuilt_the_same`,
      `::test_at1_the_counts_match_the_report`, `::test_at1_rated_without_starting`; **P4** `tests/property/recalibrate/test_sets.py::test_p4_same_set`;
      `tests/unit/test_repo_hygiene.py::test_private_data_is_ignored` (the sets' path)_

- [ ] 2. The starting map
  - Branch: `feat/rc-2-map` · Depends on: 1 · ADRs: none
  - [ ] 2.1 The fit: buckets, pooled to be monotone, shrunk toward the identity, through (0, 0) and (1, 1). `engine/recalibrate.py` joins the
    mutation run.
    - _Requirements: R2.1_
    - _Test: **AT-2** `tests/acceptance/recalibrate/test_map.py::test_at2_a_map_by_hand`, `::test_at2_a_thin_bucket_barely_moves`;
      **P1** `tests/property/recalibrate/test_map.py::test_p1_monotone_and_anchored`, **P2** `::test_p2_no_evidence_no_change`_
  - [ ] 2.2 `combine` applies `START_MAP`, the identity until approved, and keeps the raw consensus; an official lineup still settles it.
    - _Requirements: R2.2_
    - _Test: **AT-2** `::test_at2_applied_where_the_chance_is_formed`, `::test_at2_the_official_lineup_still_settles_it`;
      `tests/integration/recalibrate/test_map_applied.py::test_the_identity_changes_no_answer`_

- [ ] 3. Cameos and the season's rates
  - Branch: `feat/rc-3-rates` · Depends on: 2 · ADRs: none
  - [ ] 3.1 `CAMEO_SHARE` from defenders and midfielders and `CAMEO_RATED` from forwards; the penalty, conversion, save and card rates from a
    statistics read and the table; each with its count and interval.
    - _Requirements: R3.1, R4.1_
    - _Test: **AT-3** `tests/acceptance/recalibrate/test_rates.py::test_at3_cameos_by_hand`; **AT-4** `::test_at4_season_rates_by_hand`,
      `::test_at4_a_read_without_the_newer_columns`; **P5** `tests/property/recalibrate/test_rates.py::test_p5_rates_within_bounds`_

- [ ] 4. Held-out checks and minimum samples
  - Branch: `feat/rc-4-checks` · Depends on: 3 · ADRs: none
  - [ ] 4.1 Leave a round out, or half the matches with one round; the Brier score and reliability before and after; a value below its
    minimum sample, or that doesn't help where it wasn't fitted, isn't proposed; what waits is listed with what it needs.
    - _Requirements: R5.1, R5.2, R6.1, R6.2_
    - _Test: **AT-5** `tests/acceptance/recalibrate/test_checks.py::test_at5_below_its_minimum`, `::test_at5_what_waits`; **AT-6**
      `::test_at6_held_out_by_round`, `::test_at6_held_out_by_matches`, `::test_at6_no_help_no_proposal`; **P3**
      `tests/property/recalibrate/test_checks.py::test_p3_never_proposed_without_help`_

- [ ] 5. The market's chances beside ours
  - Branch: `feat/rc-5-market` · Depends on: 4 · ADRs: none
  - [ ] 5.1 Each round's report gains a `market` set: a win, a draw and a loss, three goals or more, both teams to score and each side's
    clean sheet, from the odds before kickoff, against the goals the keepers' rows show; old reports still read.
    - _Requirements: R7.1_
    - _Test: **AT-7** `tests/acceptance/recalibrate/test_market.py::test_at7_the_market_set_by_hand`, `::test_at7_old_reports_still_read`;
      `tests/integration/recalibrate/test_market_scored.py::test_a_round_scores_the_market`_

- [ ] 6. The proposal command
  - Branch: `feat/rc-6-proposal` · Depends on: 5 · ADRs: none
  - [ ] 6.1 `fantadamus recalibrate`: each value with its old and new value, evidence, count and held-out effect; the season's rates apart;
    what waits; the full proposal kept privately; `engine/constants.py` untouched.
    - _Requirements: R8.1_
    - _Test: **AT-8** `tests/acceptance/recalibrate/test_proposal.py::test_at8_the_proposal`, `::test_at8_changes_nothing`;
      `tests/integration/recalibrate/test_command.py::test_recalibrate_on_invented_rounds`_

- [ ] 7. The real proposal and the approved change
  - Branch: `feat/rc-7-applied` · Depends on: 6 · ADRs: none
  - [ ] 7.1 The proposal on rounds 10 and 11 from Claude Code, on `main`'s code; its aggregates in the pull request.
    - _Requirements: R6.1, R6.2, R8.1_
    - _Test: the proposal's aggregates in the task report, without players' figures_
  - [ ] 7.2 **Owner:** read the proposal, and approve or turn down each value.
    - _Requirements: AT-10 (R6, R8)_
    - _Test: recorded in the report_
  - [ ] 7.3 The approved values in `engine/constants.py`, an entry in `docs/calibration-log.md`, `docs/method.md` and the player guide; what the
    change moves on round 11's facts at its lock, in general terms.
    - _Requirements: R8.2, R8.3, R9.1, R10.1, R10.2_
    - _Test: **AT-8** `::test_at8_an_approved_change_and_its_log`; **AT-9** `tests/acceptance/recalibrate/test_moves.py::test_at9_what_it_moves`;
      `tests/unit/test_repo_hygiene.py::test_method_marks_each_calibrated_value`_

- [ ] 8. A real check and this slice's sign-off
  - Branch: `docs/rc-8-gate` · Depends on: 7 · ADRs: none
  - [ ] 8.1 A mutation run on the core modules, with survivors read; the slice report: tests, coverage, quality, cost, open risks and the
    acceptance tests.
    - _Requirements: R10.2; phase gate (`quality.md`)_
    - _Test: the report exists with every section; `make check` green on `main`_
  - [ ] 8.2 **Owner:** sign off this slice.
    - _Requirements: Phase gate (`quality.md`)_
    - _Test: sign-off recorded in the report_
