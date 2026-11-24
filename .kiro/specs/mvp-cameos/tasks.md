# Implementation Plan: `mvp-cameos` (after Phase 2, before Phase 3)

Status: **Approved by the owner, 2026-11-24** · From the approved [requirements](requirements.md) and the
[design](design.md)

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/cs-<n>-<slug>`. Sub-tasks are the steps inside
  it, each with its own test, written first and seen failing (red → green).
- **Before a task**, run `make task-check TASK=<n> SPEC=mvp-cameos`. Task 1's branch makes this spec the default
  (`CURRENT_SPEC` in `scripts/checks/task_check.py`, and `CLAUDE.md`).
- **Work in a worktree, never in `~/Documents/fantadamus`:** the owner's schedule runs from that folder on `main`.
- **Tests for this spec** live in a `cameos/` folder in each test layer.
- **No number moves until the owner approves a share** (task 3). Earlier acceptance tests change only as the design
  lists them.
- **The owner's lake is only ever read as a copy**, from here; a report gives times and counts only.

## Tasks

- [ ] 1. A share for each kind of cameo
  - Branch: `feat/cs-1-share-by-kind` · Depends on: none · ADRs: none
  - [ ] 1.1 This spec becomes the current one. `CAMEO_SHARE_PRICED = 0.5`; `cameo_share(role, mantra_role)` gives the
    share of his kind.
    - _Requirements: R1.1, R1.3_
    - _Test: `tests/unit/cameos/test_share.py::test_each_role_gets_its_kinds_share`,
      `::test_both_shares_start_at_a_half`_
  - [ ] 1.2 `combine` and `availability` take the share; `Advisor.gather`, `_assumed` and the calibration sets pass his
    kind's.
    - _Requirements: R1.1, R1.2_
    - _Test: `tests/unit/cameos/test_share.py::test_combine_uses_the_share`, `::test_an_official_bench_gets_the_share`;
      `tests/property/cameos/test_share.py::test_p1_the_chance_of_a_cameo`, `::test_p2_equal_shares_change_nothing`;
      **AT-1** `tests/acceptance/cameos/test_share.py::test_at1_each_kind_by_hand`_
  - [ ] 1.3 On a copy of the owner's lake, every answer is identical with both shares at 0.5.
    - _Requirements: R1.3_
    - _Test: **AT-2** `python -m tests.real_lake --compare`, from here_

- [ ] 2. Both shares fitted and checked
  - Branch: `feat/cs-2-two-shares` · Depends on: 1 · ADRs: none
  - [ ] 2.1 `cameo_share_priced`, and `cameo_rates` gives both shares; `CAMEO_RATED` is held and listed as waiting.
    - _Requirements: R1.4, R2.1, R2.2_
    - _Test: **AT-3** `tests/acceptance/cameos/test_fit.py::test_at3_both_shares_by_hand`,
      `::test_at3_cameo_rated_is_held`; `tests/property/cameos/test_fit.py::test_p4_the_share_comes_back`_
  - [ ] 2.2 `rerated` by kind; two checks, each held out on its kind's rows and decided against its own minimum.
    - _Requirements: R2.3, R2.4_
    - _Test: **AT-4** `tests/acceptance/cameos/test_checks.py::test_at4_held_out_by_round_and_half`,
      `::test_at4_below_its_minimum`; `tests/property/cameos/test_checks.py::test_p3_rerated_by_kind`_
  - [ ] 2.3 `mvp-recalibrate`'s AT-3 and AT-6 cameo tests, and their unit and property tests, become tests of the two
    shares, as the design lists.
    - _Requirements: R1.4_
    - _Test: the changed tests in `tests/acceptance/recalibrate/test_rates.py` and `test_checks.py`_

- [ ] 3. The proposal and the owner's approval
  - Branch: `test/cs-3-proposal` · Depends on: 2 · ADRs: none
  - [ ] 3.1 `fantadamus recalibrate` on the rounds scored, from stored facts only: both shares listed, nothing changed.
    - _Requirements: R3.1_
    - _Test: **AT-5** `tests/acceptance/cameos/test_proposal.py::test_at5_both_shares_listed`; the real proposal from
      here, counts only_
  - [ ] 3.2 **Owner:** read the proposal and approve or turn down each share.
    - _Requirements: R3.1_
    - _Test: **AT-6**, recorded in the slice report_

- [ ] 4. The approved share, the docs and this slice's sign-off
  - Branch: `feat/cs-4-approved` · Depends on: 3 · ADRs: none
  - [ ] 4.1 Each approved share in `engine/constants.py`, its calibration log entry, the `start_values` fixture.
    - _Requirements: R3.2_
    - _Test: **AT-7** `tests/acceptance/cameos/test_moves.py::test_at7_the_log_has_the_value`_
  - [ ] 4.2 What it moves on round 12's stored facts: the owner's lineup and the ten cards, counts and averages only.
    - _Requirements: R3.3_
    - _Test: **AT-7** `tests/acceptance/cameos/test_moves.py::test_at7_what_it_moves`_
  - [ ] 4.3 Method §A4 and the constants' comments; no new dependency; a mutation run on the changed functions; the
    slice report.
    - _Requirements: R4.1, R4.2_
    - _Test: **AT-8** `tests/acceptance/cameos/test_docs.py::test_at8_no_new_dependency`, `::test_at8_the_method_has_both`_
  - [ ] 4.4 **Owner:** sign the slice off.
    - _Requirements: all_
    - _Test: the slice report_
