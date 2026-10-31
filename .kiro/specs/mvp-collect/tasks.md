# Implementation Plan: `mvp-collect` (Phase 2, first slice)

Status: **Approved by the owner, 2026-10-31; amended the same day** for the amended requirements and design
(tasks 3, 4.2, 6.1, 6.3 and 7.1), **the amendment approved the same day** · Date: 2026-10-30 · From the approved
[requirements](requirements.md) and [design](design.md)

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/mc-<n>-<slug>`. Sub-tasks are the
  steps inside it, each with its own test, written first and seen failing (red → green).
- Before a task, `make task-check TASK=<n>` (this spec is the default) checks that its dependencies are
  ticked, that every step names its requirements and test, and that its ADRs are Accepted.
- A ticked box (`- [x]`) marks a task or step as done; the agent ticks it on the task's branch.
- The property tests P1–P7 in the design are **required**. No task is optional.
- Each task ends with the task report; the owner approves the pull request, the agent squash-merges it.
- **Tests for this spec** live in a `collect/` folder in each test layer. Pages are synthetic copies of the
  real pages' structure with invented clubs and players, built by `tests/collect_pages.py`. Tests never touch
  the internet: the fetcher, the collector and `read_page` run against a local server on 127.0.0.1.
- **The order:** 1 and 2 can go in either order, then 3, 4, then 5 and 7 in either order, then 6, then 8.

## Tasks

- [x] 1. Outlet percentages: contracts, silver and availability
  - Branch: `feat/mc-1-outlet-views` · Depends on: none · ADRs: ADR-0006
  - [x] 1.1 `OutletLineupPayload` 1.0.0 and `MatchOddsPayload` 1.2.0 (`over_2_5_percent`), with their quality
    rules, schema snapshots and changelog entries
    - _Requirements: R4.1, R3.1_
    - _Test: `tests/contract/test_collect_contracts.py::test_outlet_lineup_rules`, `::test_odds_with_percent_over`_
  - [x] 1.2 The `outlet_views` domain and the `submit_outlet_lineup` tool; odds silver takes P(over 2.5) from a
    page's percentage when it gives no over/under odds
    - _Requirements: R4.1, R4.2, R8.1_
    - _Test: `tests/integration/collect/test_outlet_views.py::test_outlet_lineup_bronze_to_silver`,
      `::test_percent_over_feeds_the_fit`_
  - [x] 1.3 Availability over percentages: an outlet's percentage is its view, the newest read of each outlet
    counts once across both tables, unavailable lists give no cameo, an official lineup overrides
    - _Requirements: R4.1, R4.2, R4.3_
    - _Test: `tests/unit/collect/test_percent_consensus.py::test_percentages_are_views`, `::test_same_outlet_counts_once`;
      **P5** `tests/property/collect/test_percent_consensus.py::test_p5_percent_consensus`;
      **AT-4** `tests/acceptance/collect/test_collect.py::test_at4_four_outlets_disputed`_

- [x] 2. Polite fetching
  - Branch: `feat/mc-2-fetcher` · Depends on: none · ADRs: ADR-0004, ADR-0006
  - [x] 2.1 The fetcher: the allowlist before any request, robots.txt cached once a day per host, one request a
    second per host, the user agent, blocks and bot checks stop the host, one attempt with a timeout
    - _Requirements: R2.1, R2.2, R2.3_
    - _Test: `tests/unit/collect/test_fetch.py::test_allowlist_robots_and_blocks`;
      **P1** `tests/property/collect/test_fetch.py::test_p1_one_request_per_second`,
      **P2** `::test_p2_robots_never_broken`;
      **AT-2** `tests/acceptance/collect/test_fetching.py::test_at2_disallowed_never_requested`,
      **AT-3** `::test_at3_rate_and_too_many_requests`_
  - [x] 2.2 The HTML tree on `html.parser`: find by tag and class, text, attributes
    - _Requirements: R3.4_
    - _Test: `tests/unit/collect/test_html.py::test_find_by_class_and_text`_

- [x] 3. Reading pages
  - Branch: `feat/mc-3-readers` · Depends on: 1, 2 · ADRs: ADR-0006
  - [x] 3.1 Fantacalcio-Online's round page: fixtures, odds and the chance of 3+ goals with the page's update time,
    four outlets' percentages per team (the page's average skipped), official lineups once confirmed, the
    unavailable list; clubs and names mapped as submissions are
    - _Requirements: R3.1, R3.5, R4.2_
    - _Test: `tests/unit/collect/test_read_fco.py::test_round_page_facts`, `::test_page_average_skipped`,
      `::test_official_lineup_when_confirmed`, `::test_dash_means_not_listed`, `::test_outlet_short_of_eleven_left_out`,
      `::test_no_odds_yet`;
      **P4** `tests/property/collect/test_readers.py::test_p4_partial_pages_fail`_
  - [x] 3.2 Page text and `read_page`: the reading list's pages and patterns, only those fetched; the main
    content as headings, lines, table rows and followable links, menus skipped, long text in parts; the result
    names the fetch time and each fact's submit tool, and stores nothing
    - _Requirements: R3.2, R3.3, R2.4_
    - _Test: `tests/unit/collect/test_page_text.py::test_tables_links_and_menus`, `::test_long_text_in_parts`;
      `tests/integration/collect/test_read_page.py::test_read_then_submit`, `::test_unlisted_address_refused`,
      `::test_long_page_in_parts`;
      **P8** `tests/property/collect/test_read_page.py::test_p8_only_listed_addresses`;
      **AT-11** `tests/acceptance/collect/test_read_page.py::test_at11_page_added_in_config_only`_
  - [x] 3.3 An optional check of the round-page reader and page text on real pages saved under
    `data/private/pages/` (skipped, with a registered reason, when there are none)
    - _Requirements: R3.4_
    - _Test: `tests/contract/test_real_pages.py::test_reading_saved_pages`_

- [x] 4. The collector
  - Branch: `feat/mc-4-collector` · Depends on: 3 · ADRs: ADR-0006
  - [x] 4.1 `facts.submit_many`: every payload checked first, one bronze record each, one silver rebuild per
    domain, failures reported without stopping the rest
    - _Requirements: R1.1, R1.4_
    - _Test: `tests/integration/collect/test_submit_many.py::test_one_rebuild_per_domain`_
  - [x] 4.2 The collector: the round page planned from needs (fetched once per run), read, stored as
    `collector` with fetch and page times, a report; its address and the switch-off in configuration (the
    60-second budget moved to 6.1, where `compare_players` sets it, 2026-10-31)
    - _Requirements: R1.1, R1.4, R2.4, R2.5, R3.4_
    - _Test: `tests/integration/collect/test_collector.py::test_collect_round_from_local_pages`,
      `::test_switched_off_source`, `::test_failures_named`;
      `tests/unit/collect/test_read_fco.py::test_round_from_the_page`;
      `tests/unit/test_sources_config.py::test_collector_page_is_allowed`;
      **AT-1** `tests/acceptance/collect/test_collect.py::test_at1_one_collection_stores_everything`,
      **AT-6** `::test_at6_unexpected_layout_falls_back`;
      **P3** `tests/property/collect/test_collect.py::test_p3_same_pages_store_nothing_new`_
  - [x] 4.3 The collection log, the `collect` tool and `fantadamus collect` with `--round` and `--report`
    - _Requirements: R1.2, R8.2_
    - _Test: `tests/integration/collect/test_collect_tool.py::test_tool_and_command_report`,
      `::test_report_shows_last_run`_

- [ ] 5. Many sources, compared
  - Branch: `feat/mc-5-sources` · Depends on: 4 · ADRs: ADR-0006
  - [ ] 5.1 Fixtures and the table come from the highest-ranked fresh source; disagreements between sources are
    listed for the answer
    - _Requirements: R5.1_
    - _Test: `tests/unit/collect/test_sources.py::test_ranked_source_wins`, `::test_disagreements_listed`;
      **AT-7** `tests/acceptance/collect/test_answer.py::test_at7_kickoff_disagreement_shown`_
  - [ ] 5.2 Confidence for every published probability: sources, spread and "agree", "disputed" or "one
    source"; odds averaged across pages
    - _Requirements: R5.2, R5.3_
    - _Test: `tests/unit/collect/test_sources.py::test_confidence_labels`_

- [ ] 6. The forecast answer
  - Branch: `feat/mc-6-forecast` · Depends on: 4, 5 · ADRs: ADR-0006
  - [ ] 6.1 `compare_players` asks the collector first, within 60 seconds; the refresh plan keeps only what it
    couldn't get or doesn't read, each item naming `read_page` and its pages, and saying what was tried and why
    that failed
    - _Requirements: R1.3, R8.1_
    - _Test: `tests/integration/collect/test_compare_collects.py::test_missing_facts_collected_first`,
      `::test_failures_named_in_plan`;
      **AT-5** `tests/acceptance/collect/test_answer.py::test_at5_one_call_answer`_
  - [ ] 6.2 Movement since the user's previous answer (or 24 hours) with the facts that changed, the last update,
    and labelled sources
    - _Requirements: R6.1, R6.2, R6.3_
    - _Test: `tests/integration/collect/test_forecast.py::test_movement_since_last_answer`,
      `::test_updated_and_sources`;
      **AT-8** `tests/acceptance/collect/test_answer.py::test_at8_movement_named`;
      **P6** `tests/property/collect/test_forecast.py::test_p6_no_new_facts_no_movement`_
  - [ ] 6.3 The agent prompt answers as a forecast in the owner's shape, with Sources at the bottom, and reads
    pages through `read_page` instead of browsing; the server serves the `collect` and `read_page` tools
    - _Requirements: R6.4, R1.2, R3.2_
    - _Test: `tests/integration/xy/test_server.py::test_prompt_has_forecast_shape`, `::test_served_tools`_

- [ ] 7. The schedule
  - Branch: `feat/mc-7-schedule` · Depends on: 4 · ADRs: ADR-0006
  - [ ] 7.1 The cadence of the round page's facts and `fantadamus collect --due`
    - _Requirements: R7.1_
    - _Test: `tests/unit/collect/test_cadence.py::test_cadence_table`;
      **P7** `tests/property/collect/test_cadence.py::test_p7_due_stays_due`;
      **AT-9** `tests/acceptance/collect/test_schedule.py::test_at9_due_collects_exactly_whats_due`_
  - [ ] 7.2 The launchd step in `docs/player-setup.md`
    - _Requirements: R7.2_
    - _Test: `tests/unit/test_repo_hygiene.py::test_player_guide_schedule`_

- [ ] 8. The real round and the slice gate
  - Branch: `docs/mc-8-report` · Depends on: 6, 7 · ADRs: ADR-0006
  - [ ] 8.1 **Owner:** with the second player, ask a real "X or Y?" on each Mac, before and after an official
    lineup; only `compare_players` should be called
    - _Requirements: AT-10; R1.3, R6.4, R7.2_
    - _Test: what each answer used and the collection log, recorded in the slice report (no page text)_
  - [ ] 8.2 Short slice report in `docs/reports/`: tests, coverage, acceptance tests, the collection log's
    record, open risks
    - _Requirements: R8.2, slice gate (`quality.md`)_
    - _Test: the report exists with every section; `make check` green on `main`_
  - [ ] 8.3 **Owner:** sign off the slice → the next slice may start
    - _Requirements: Slice gate (`quality.md`)_
    - _Test: sign-off recorded in the slice report_
