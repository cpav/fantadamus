# Requirements Document: `mvp-alerts` (Phase 2, ninth slice)

Status: **Approved by the owner, 2026-11-15**, with all three recommendations · Workflow: requirements-first · Depends on: `mvp-sources` · Abbreviation: `al` ·
Method: [`docs/method.md`](../../../docs/method.md) §A7, §A8 · Answers: [`docs/answer-formats.md`](../../../docs/answer-formats.md)

## Introduction

The last slice before going online (`product.md`, 2026-11-11): **"the official lineup changes your call"**, as a
notification on the user's Mac from the scheduled run. Once online, a notification service such as Amazon SNS takes over
(Phase 3, not this slice).

What already exists:

- **The scheduled run.** `fantadamus collect --due`, started by launchd every 15 minutes (`docs/player-setup.md`, step 8),
  reads what's due: the official lineups every 15 minutes in the 75 minutes before each kickoff; the probable lineups
  every 3 hours on the last day; and the injured and suspended pages twice a day in the last two days.
- **The advice.** `best_lineup` works out the user's eleven, bench and formation from the stored squad and rules, and the
  decision log keeps every lineup it told the user.

What's missing is a run that, having stored something new, works the advice out again and tells the user when it has
changed, without being asked.

**A round locks at its first kickoff**, while most official lineups come out an hour before their own match, after the
lock. So an official lineup can change the call only for the round's first matches. The probable lineups and the injury
page change it more often in the last day, so they alert too (decision 1).

**Not in this spec:** notifications once online (Phase 3); alerts about a league-mate's squad; live alerts during a match
(not planned, `product.md`); trades, auctions and market values.

## Glossary

| Term | Meaning |
|---|---|
| The call | The advised eleven, its formation, the captain and vice where the league has them, and the first bench place in each role |
| Alert window | From `ALERT_WINDOW_HOURS` *(start)*: 24 before the round's deadline, until the deadline |
| Baseline | The call last compared: the newer of the last one alerted and the last lineup told to the user in the round (design decision 2, for approval) |

## Requirements

### Requirement 1: The check

**User Story:** As a player, I want to know when fresh news changes my lineup before the deadline, without asking.

- **R1.1** WHEN a scheduled run stores a new fact inside the alert window THE SYSTEM SHALL work out the user's call again,
  on the facts then, as `best_lineup` would, logging nothing to the decision log.
- **R1.2** THE SYSTEM SHALL compare it with the baseline. Without one (no lineup told this round), the first call becomes
  the baseline and nothing is sent.
- **R1.3** No check SHALL run outside the window, after the deadline, or without a stored squad and league rules.

### Requirement 2: What changes the call

- **R2.1** A change SHALL be any of: a player into or out of the eleven, the formation, the captain or vice, or the first
  bench place in a role.
- **R2.2** Each change SHALL name its cause from what was stored since the baseline: an official lineup, an outlet's
  probable lineup, or the injured or suspended page (as decision 1 allows).
- **R2.3** A change of chances alone, the call unchanged, SHALL NOT alert.

### Requirement 3: The alert

- **R3.1** THE SYSTEM SHALL send one notification on the user's Mac per change of the call, in the answer formats'
  shape: "Round 12 · Official lineup out: Rossi on the bench. Start Bianchi; your first defender off the bench comes in."
- **R3.2** It SHALL be kept in a local alert log, with its time, the round, the change and its cause; the new call becomes
  the baseline.
- **R3.3** The same change SHALL NOT be sent twice; a call that changes back SHALL be sent as a change.
- **R3.4** A switch in the user's private configuration SHALL turn alerts off.

### Requirement 4: Cost, time and privacy

- **R4.1** A check SHALL add at most `ALERT_SECONDS` *(start)*: 10 to a scheduled run, and run only when something new was
  stored. No paid service, no account, no install beyond what macOS has.
- **R4.2** Notifications and the alert log stay on the user's Mac; nothing about the squad reaches the repository or a
  log outside `data/`.

### Requirement 5: The docs

- **R5.1** THE SYSTEM SHALL update `docs/answer-formats.md` (alerts leave "Later" for a format of their own), the player
  guide (how to let notifications through, and the switch) and `product.md`'s delivery table.

## Acceptance tests

| Test | Proves | Requirement |
|---|---|---|
| AT-1 | A scheduled run that stores an official lineup inside the window, benching a starter of the call, sends one alert naming him and his cover | R1, R2, R3 |
| AT-2 | Nothing sent: outside the window, after the deadline, without a squad, with the switch off, with no baseline, or when only the chances moved | R1.2, R1.3, R2.3, R3.4 |
| AT-3 | The same change isn't sent twice; a change back is sent | R3.3 |
| AT-4 | A check stays within its time on the synthetic round; no install, no account | R4 |
| AT-5 | Manual: on the owner's Mac, a notification from a real scheduled run, or a replayed one | R3.1 |
| AT-6 | The docs updated | R5 |

## Review (Analyze-Requirements style)

- **Ambiguity:** "your call" is defined in the glossary (the eleven, the formation, the captains, each role's first bench
  place); the bench below its first places doesn't alert.
- **Conflict:** an official lineup usually arrives after the lock; the introduction says so, and decision 1 decides
  whether earlier news alerts.
- **Testability:** each requirement maps to an acceptance test; the notification itself is checked by hand (AT-5), its
  text and its sending by test.
- **Dependencies:** the scheduled run (`mvp-collect`), the lineup (`mvp-lineup`), the injured and suspended pages
  (`mvp-sources`).

## Decisions for the owner

All three decided by the owner on 2026-11-15, as recommended.

1. **What alerts?** Recommendation: official lineups, **and** the probable lineups and the injury and ban pages inside the
   last 24 hours. An official lineup alone would alert only for the round's first matches, since the rest come out after
   the lock.
2. **What counts as a change of the call?** Recommendation: the eleven, the formation, the captain and vice, and each
   role's first bench place, as in the glossary. Moves further down the bench don't alert.
3. **How it reaches you.** Recommendation: macOS's own notifications (`osascript`, nothing to install), with the change in
   the text. The alternative, `terminal-notifier`, opens Claude Desktop on a click but needs Homebrew.
