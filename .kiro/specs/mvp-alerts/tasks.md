# Implementation Plan: `mvp-alerts` (Phase 2, ninth slice)

Status: **Approved by the owner, 2026-11-15** · From the approved [requirements](requirements.md) and the [design](design.md)

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/al-<n>-<slug>`. Sub-tasks are the steps inside it, each with its own
  test, written first and seen failing (red → green).
- **Before a task**, run `make task-check TASK=<n> SPEC=mvp-alerts`. Task 1's branch makes this spec the default (`CURRENT_SPEC` in
  `scripts/checks/task_check.py`, and `CLAUDE.md`).
- **A ticked box** (`- [x]`) marks a task or step as done; the agent ticks it on the task's branch.
- **The property tests P1–P5 in the design are required.** No task is optional.
- **Each task ends with the task report**; the owner approves the pull request, the agent squash-merges it.
- **Breaking the code on purpose:** each code task does it once before its report, from a green baseline, and says what it found.
- **Tests for this spec** live in an `alerts/` folder in each test layer. Squads, lineups and alerts are invented; a real alert never reaches
  the repository, fixtures or committed logs.
- **No real check from a branch:** the scheduled run on the owner's Mac uses `main`.

## Tasks

- [x] 1. The call, what changed, why, and the text
  - Branch: `feat/al-1-call` · Depends on: none · ADRs: none
  - [x] 1.1 A call from a lineup answer and from a logged one; `last_advice` also gives each player's chance of starting. This spec
    becomes the current one.
    - _Requirements: R2.1_
    - _Test: `tests/unit/alerts/test_call.py::test_a_call_from_a_lineup`, `::test_a_call_from_a_logged_answer`,
      `::test_an_override_is_compared_by_its_advice`, `::test_the_first_on_the_bench_in_each_role`;
      `tests/unit/review/test_advice.py::test_last_advice_keeps_the_chances`_
  - [x] 1.2 What changed: the eleven in pairs, the formation, the captain and vice, each role's first bench place; nothing for chances
    alone or the bench below its first places.
    - _Requirements: R2.1, R2.3_
    - _Test: `tests/unit/alerts/test_changes.py::test_each_kind_of_change`, `::test_a_new_formation_leaves_lone_changes`,
      `::test_chances_alone_change_nothing`, `::test_lower_on_the_bench_changes_nothing`;
      **P2** `tests/property/alerts/test_changes.py::test_p2_changes_are_empty_exactly_both_ways`_
  - [x] 1.3 Why, from the facts read after the call compared, the official lineup first; the text, within `ALERT_CHARACTERS`.
    - _Requirements: R2.2, R3.1_
    - _Test: `tests/unit/alerts/test_cause.py::test_the_official_lineup_first`, `::test_the_injury_and_ban_pages`,
      `::test_the_probable_lineups`, `::test_otherwise_the_newest_facts`; `tests/unit/alerts/test_text.py::test_the_shape`,
      `::test_more_changes_are_counted`; **P5** `tests/property/alerts/test_text.py::test_p5_every_change_named_or_counted`_

- [x] 2. The check and the alert log
  - Branch: `feat/al-2-check` · Depends on: 1 · ADRs: none
  - [x] 2.1 The alert log, append-only under `data/local/alerts/`.
    - _Requirements: R3.2, R4.2_
    - _Test: `tests/unit/alerts/test_alert_log.py::test_lines_are_appended_and_read_back`, `::test_a_month_per_file`,
      `::test_it_lives_under_the_git_ignored_folder`_
  - [x] 2.2 The check: something new, the window, the league, the call replayed, the baseline, the changes and the alert, with a fake
    notifier; `make_advisor` shared with `serve`.
    - _Requirements: R1.1–R1.3, R2.2, R3.1–R3.3_
    - _Test: **AT-1** `tests/acceptance/alerts/test_alert.py::test_at1_an_official_lineup_benches_a_starter`;
      **AT-2** `tests/acceptance/alerts/test_nothing_sent.py::test_at2_outside_the_window`, `::test_at2_after_the_deadline`,
      `::test_at2_without_a_squad`, `::test_at2_without_a_baseline`, `::test_at2_chances_alone`, `::test_at2_nothing_new_stored`,
      `::test_at2_a_squad_saved_after_the_baseline`; **AT-3** `tests/acceptance/alerts/test_once.py::test_at3_not_sent_twice`,
      `::test_at3_a_change_back_is_sent`; **P1** `tests/property/alerts/test_check.py::test_p1_nothing_outside_the_window`;
      **P3** `::test_p3_one_alert_for_the_same_facts`; **P4** `::test_p4_a_change_back_alerts_again`; also
      `tests/unit/alerts/test_decide.py`, `tests/unit/alerts/test_news.py`, `tests/unit/alerts/test_cause.py::test_a_fact_that_doesnt_explain_the_move_isnt_its_cause`,
      `tests/acceptance/alerts/test_alert.py::test_at1_a_notification_the_mac_refuses_is_logged`, `::test_at1_no_alert_when_the_facts_dont_give_a_lineup`,
      `tests/acceptance/alerts/test_nothing_sent.py::test_at2_the_window_edges`, `tests/acceptance/alerts/test_once.py::test_at3_only_this_round_this_user_and_this_team`_
    - A cause names a fact only if it explains the move: for the player who lost his place, benched, out or less likely to start;
      for the one who took it, starting or likelier to. Found by the first test run, where a benched forward's cause was "the
      official lineup starts him".

- [x] 3. Sending it, the command line and the switch
  - Branch: `feat/al-3-send` · Depends on: 2 · ADRs: none
  - [x] 3.1 `notify` through `/usr/bin/osascript`, the text as arguments, a timeout, the reason on failure; the suppression proposed
    in `docs/quality/suppressions.md` with its approval date blank.
    - _Requirements: R3.1, R4.1_
    - _Test: `tests/unit/alerts/test_notify.py::test_the_text_goes_in_as_arguments`, `::test_a_failure_returns_its_reason`,
      `::test_a_timeout_returns_its_reason`, `::test_the_runner_runs_a_command_and_waits_for_it`_
    - S-015 recorded with the owner's approval of design decision 1 (2026-11-15, "approve all three").
  - [x] 3.2 `collect --due --user` runs the check after the run, and its error never fails the run; `fantadamus alerts` and
    `--test`; the switch in the private configuration.
    - _Requirements: R1.1, R3.4_
    - _Test: `tests/integration/alerts/test_command.py::test_the_check_runs_after_a_run_that_stored`, `::test_an_error_in_the_check_isnt_the_runs`,
      `::test_the_log_printed`, `::test_a_sample_sent`; **AT-2** `tests/acceptance/alerts/test_nothing_sent.py::test_at2_the_switch_off`;
      `tests/unit/alerts/test_switch.py::test_on_without_the_file`, `::test_off_with_the_switch`, `::test_on_when_the_file_cant_be_read`,
      `::test_on_with_the_switch_on_or_absent`, `::test_on_with_a_switch_that_isnt_true_or_false`;
      `tests/integration/alerts/test_command.py::test_the_switch_reaches_the_check`, `::test_nothing_due_checks_nothing`_
  - [x] 3.3 The budget: a check on the synthetic round, timed.
    - _Requirements: R4.1_
    - _Test: **AT-4** `tests/acceptance/alerts/test_budget.py::test_at4_a_check_in_budget`, `::test_at4_no_install_and_no_account`_
    - 0.73 CPU-seconds for a check with all 10,000 simulated rounds, against 10.

- [ ] 4. The docs, a real check and this slice's sign-off
  - Branch: `docs/al-4-gate` · Depends on: 1, 2, 3 · ADRs: none
  - [x] 4.1 The docs: answer formats, the player guide's step 8, `product.md`.
    - _Requirements: R5.1_
    - _Test: **AT-6** `tests/unit/test_repo_hygiene.py::test_answer_formats_show_alerts`, `::test_the_guide_lets_notifications_through`,
      `::test_player_guide_schedule` (the schedule passes `--user`)_
  - [ ] 4.2 **Owner:** on the Mac, `fantadamus alerts --test`, and let the notification through; then one from a real scheduled run
    in the last day before a round, or a replayed one.
    - _Requirements: R3.1 (AT-5)_
    - _Test: recorded in the report, without the squad's names_
    - From `main` on 2026-11-15: `fantadamus alerts --test` was taken by macOS; round 11's last day, replayed read-only,
      would have sent 4 alerts. Left to the owner: seeing the notification, installing the schedule, and a real alert
      in round 12's last day.
  - [x] 4.3 A mutation run on the new core functions, with survivors read; the slice report: tests, coverage, quality, cost, open risks
    and the acceptance tests.
    - _Requirements: R4.1; phase gate (`quality.md`)_
    - _Test: the report exists with every section; `make check` green on `main`_
    - `domains/alerts.py` joins the mutation set with its pure tests: 403 of 413 mutants killed, after nine tests for the
      gaps the first run showed (`tests/unit/alerts/test_call.py`, `test_cause.py`, `test_text.py`, `test_decide.py`);
      the 10 left change nothing.
  - [ ] 4.4 **Owner:** sign off this slice.
    - _Requirements: Phase gate (`quality.md`)_
    - _Test: sign-off recorded in the report_
