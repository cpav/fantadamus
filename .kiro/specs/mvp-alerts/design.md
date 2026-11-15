# Design Document: `mvp-alerts` (Phase 2, ninth slice)

Status: **Approved by the owner, 2026-11-15**, with all three recommendations · From the approved [requirements](requirements.md)

## Overview

An alert answers one question nobody asked: has the news since I last looked changed my lineup? The scheduled run already
reads the round's pages every 15 minutes when something is due. After a run that stored a new official lineup, a probable
lineup or a line of the injured or suspended pages, inside the last 24 hours before the deadline, Fantadamus works the
user's lineup out again on the facts then, compares its call with the one the user last saw, and, if the call has changed,
sends one notification on the Mac saying what changed and why.

Nothing here changes a number. The lineup is the one `best_lineup` would give, replayed on stored facts the way the review
already replays the advice at the lock, so it neither collects nor logs. The only new things are a comparison, a sentence,
a log and a call to macOS.

## What it builds on

- `web/cadence.py`: `collect_due`, the scheduled run, and its `CollectReport`, which says per page which silver tables
  stored new rows.
- `mcp/tools/lineup.py`: `squad_at` prices the squad on the facts stored by a time without collecting, and
  `replayed_lineup` gives the lineup `best_lineup` would have given on them, logging nothing (mvp-review C5).
- `domains/review.py`: `last_advice`, the last lineup the user was told before the lock, with the advice behind an
  override.
- `domains/fixtures/gold.py`: `next_round` and `deadline`.
- `mcp/advisor.py`: `PlayerFacts`, with the official lineup's status, the outlets' chance of starting and the injured and
  suspended pages' news, each with its source and read time.
- `league/`: the rules and squads, each saved with a time.

## Components

### C1. The call and what changed (`domains/alerts.py`; R2.1, R2.3)

Pure. A `Call` is what an alert compares, from a lineup answer or a logged one:

- the round, the formation, the eleven (by player ID), the captain and vice where the league has them;
- the first bench place in each role, from the bench in its order and each player's role;
- each squad player's chance of starting, which the cause uses (C2), never the comparison;
- its time: when the facts behind it were read.

`changes(before, after)` lists what differs, eleven first:

1. **The eleven.** Each player who left it is paired with one of the same role who came in; what can't be paired (a new
   formation moves a place from one role to another) stays a lone "out" or "in".
2. **The formation.**
3. **The captain, then the vice.**
4. **Each role's first bench place**, keeper, defenders, midfielders, forwards. A move further down the bench isn't a change.

Two calls that differ only in their chances, or in the bench below its first places, have no changes (R2.3).

### C2. Why (`domains/alerts.py`; R2.2)

Pure. Each change is about one player whose news explains it: the starter who left the eleven, the captain or the first on
the bench who lost his place; for a player who came in without one leaving, that player. Of his facts read **after the
call compared**, the first that applies is the cause:

1. **The official lineup:** "the official lineup has Rossi on the bench", "leaves Rossi out of the squad".
2. **The injured or suspended page:** "the injury page has Rossi out: thigh muscle injury", "Rossi is banned".
3. **The probable lineups:** "the probable lineups give Rossi 40% to start, from 75%", from the two calls' chances.
4. **Otherwise**, as for a formation that changes on the odds: "on the newest lineups and odds".

The run's pages give the subtitle, the strongest cause first: "Official lineup out", "Injury news", "Probable lineups".

### C3. The notification (`domains/alerts.py`; R3.1)

Pure. One notification per changed call, in the answer formats' plain style, the action first and the cause after:

```text
Fantadamus · Round 12
Official lineup out
Start Bianchi instead of Rossi: the official lineup has Rossi on the bench. Verdi is now your first defender off the bench.
```

- A pair: "Start Bianchi instead of Rossi", then its cause. A lone change: "Start Bianchi" or "Bench Rossi", with its cause.
- The formation: "Play 4-4-2 instead of 3-5-2." The captain: "Captain Bianchi instead of Rossi." The bench: "Verdi is now
  your first defender off the bench."
- At most `ALERT_CHARACTERS` *(start)*: 240, the length a Mac shows when the notification is opened; the rest are counted:
  "And 2 more changes: ask for your lineup."
- Names are the squad's own spellings; nothing else about the squad is in it.

### C4. The check (`mcp/alerts.py`; R1, R3.2, R3.3)

`check_alerts(advisor, squads, alerts, report, notify)` runs after a scheduled run, for the user's own squad only. In
order, each step stopping the check with the reason printed to the schedule's log:

1. **Something new.** The run stored rows in one of `ALERT_TABLES`: the official lineups, the outlets' views, the injured
   and the suspended pages (decision 1). A page that only confirms what was stored isn't new (R4.1).
2. **The window.** The next round's deadline is known, and now falls in the last `ALERT_WINDOW_HOURS` *(start)*: 24
   before it (R1.3).
3. **The league.** Rules with a lineup and the user's own squad are stored (R1.3).
4. **The call now.** `squad_at` on the facts stored by now, then `replayed_lineup`. An answer that isn't a lineup (it
   needs facts the pages haven't given) stops here: nothing is guessed.
5. **The baseline**, the newer of the round's last line in the alert log and `last_advice` before the deadline. Without
   one, or when the squad or the rules were saved after it, the call now is logged as the baseline and nothing is sent
   (R1.2): a call the user changed themself isn't news.
6. **The changes** (C1). None: nothing is sent, and the baseline stays, so a slow drift of chances is still measured from
   what the user saw.
7. **The alert.** The text (C2, C3), the notification, and a line in the alert log with the new call, which becomes the
   baseline. The same change can't be sent twice, since the next check compares with it; a call that changes back is a
   change (R3.3).

`last_advice` gains each player's chance of starting from the logged answer, so that a baseline from the decision log has
the chances C2 compares.

### C5. The alert log (`lake/alert_log.py`; R3.2, R4.2)

Append-only JSON lines at `data/local/alerts/<YYYY-MM>.jsonl`, git-ignored, like the decision log. A line has its kind
(`baseline` or `alert`), its time, the user, the team, the round, the call, the changes, the text, and whether macOS took
the notification, with the reason if not. A notification that couldn't be shown is logged and not retried: its call is
still the baseline, and `fantadamus alerts` shows it.

### C6. Sending it (`cli/notify.py`; R3.1, R4.1, R4.2)

`notify(title, subtitle, text)` runs `/usr/bin/osascript` with a fixed script that reads its three arguments: the text is
passed as arguments, never put into the script, so a name can't change what runs. A 5-second timeout; it returns the
reason when it fails (not a Mac, a timeout, an error), and never raises. Nothing to install and no account.

This is the first subprocess in the product code, so ruff's `S603` needs one rule-specific suppression on that line, with
its entry in `docs/quality/suppressions.md` (decision 1). Tests pass a fake runner, so CI never calls macOS.

### C7. The command line and the switch (`cli/__main__.py`, `mcp/server.py`; R3.4)

- `fantadamus collect --due` gains `--user`, as `serve` has: whose squad and rules to check. After the run and the round's
  scoring it calls the check, and an error in the check is printed and never fails the collection.
- `fantadamus alerts` prints the round's alert log; `fantadamus alerts --test` sends a sample notification, so a player
  can let them through once (AT-5).
- **The switch:** `[alerts] enabled = false` in the private configuration (`$FANTADAMUS_PRIVATE_CONFIG`, by default
  `~/.config/fantadamus/private.toml`) turns alerts off; without it they're on (decision 3). Read by the CLI and passed
  in, so the logic stays free of I/O.
- `mcp/server.py`'s `make_advisor` builds the advisor for both `serve` and the check, so that they can't drift apart.

### C8. The docs (R5.1)

- `docs/answer-formats.md`: "Alerts" leaves "Later" for a section of its own, with C3's shape.
- `docs/player-setup.md`, step 8: the schedule passes `--user`; how to let notifications through (`fantadamus alerts
  --test`, then System Settings → Notifications → Script Editor); the switch.
- `product.md`: the delivery table marks the slice.

## Error handling

| Case | What happens |
|---|---|
| No fixtures for the next round, or no deadline | No check: outside the window |
| The replayed answer isn't a lineup | No alert; the reason in the schedule's log |
| A player of the baseline left the squad | The squad was saved after it: a new baseline, nothing sent |
| macOS refuses or times out | Logged with the reason; the call is still the baseline; the run carries on |
| The private configuration can't be read | Alerts stay on, and the schedule's log says why |
| Two runs at once | launchd starts one at a time; a check reads both logs as they are |

## Correctness properties

Each is a Hypothesis test, required, in `tests/property/alerts/`:

- **P1** No alert outside the window, at or after the deadline, without a squad or rules, or with the switch off, whatever
  the facts.
- **P2** `changes(call, call)` is empty; `changes(a, b)` is empty exactly when `changes(b, a)` is; calls that differ only in
  chances or below each role's first bench place have none.
- **P3** Two checks on the same facts send at most one alert.
- **P4** A call that changes and changes back sends two alerts.
- **P5** Every changed player is named in the text or counted in "more changes", and the text fits in `ALERT_CHARACTERS`.

## Testing strategy

- **Unit:** the call from a lineup and from a logged answer; each kind of change; each cause; the text; the switch's
  reading; the notifier's arguments, with a fake runner.
- **Integration:** a synthetic round on a temporary lake: a run that stores an official lineup benching a starter sends one
  alert and logs it; the alert log read back.
- **Acceptance:** AT-1 to AT-4 and AT-6 in `tests/acceptance/alerts/`; AT-5 by hand on the owner's Mac.
- **Budget (AT-4):** a check on the synthetic round, timed as `tests/lineup_speed.py` times a lineup, within
  `ALERT_SECONDS` *(start)*: 10.

Squads, lineups and alerts in tests are invented; a real alert never reaches the repository.

## Cost

$0: no paid service, no account, no install, nothing on AWS. A check is a lineup on stored facts, a few seconds at most,
and runs only after a run that stored lineups or news in the last day before a round: about 10 a round.

## Build order (input to tasks.md)

1. The call, its changes, the cause and the text (C1 to C3), pure; this spec becomes the current one.
2. The check and the alert log (C4, C5), with a fake notifier.
3. Sending it, the command line and the switch (C6, C7), and the budget.
4. The docs (C8), the real check on the owner's Mac, and the slice report.

## Open points for the owner

All three decided by the owner on 2026-11-15, as recommended.

1. **One suppression.** Calling `osascript` needs ruff's `S603` silenced on that one line (S-015). Recommendation: approve:
   the command is fixed, the path absolute, and the text goes in as arguments, never as code.
2. **The baseline after you ask.** The requirements' glossary says the baseline is "the last one alerted, or else the last
   lineup told". Recommendation: take whichever is newer, so that asking for your lineup after an alert resets what's
   compared. This changes the glossary's wording, in this pull request.
3. **Alerts on by default** once the schedule runs, off with the switch. Recommendation: yes.
