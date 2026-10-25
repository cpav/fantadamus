# Gate self-test report, 2026-10-25

Task 14 adds the automated gate scenarios to this report. For now it holds the live check of the agent
hooks from task 9.7 (R20.3, R17.8), which can't run in CI because it needs Claude Code itself.

## Agent hooks, live in Claude Code (task 9.7)

- **Where:** the Claude Code desktop app (version 2.1.308) on the owner's Mac, in the session that built
  task 9, on branch `feat/ef-9-agent-hooks`. There is no `origin` remote, so the rules from before the
  remote go-ahead apply.
- **Who:** the agent ran each step; the owner watched the session.
- **Payloads** were recorded as field names only, never values, in `.git/fantadamus-hook-shapes.jsonl`.

| Gate | Bad change | Expected | Observed | Result |
|---|---|---|---|---|
| Hooks load | `.claude/settings.json` written during the session | Picked up without a restart (ADR-0001) | The guard ran from the second tool call after the write | Pass |
| Guard: push | `git push origin feat/ef-9-agent-hooks` | Blocked, with the reason returned to the agent | Blocked: "`git push` is blocked until the owner gives the remote go-ahead (task 15)" | Pass |
| Guard: deploy | `make deploy` | Blocked, with the reason returned | Blocked: "`make deploy` is a deploy, which only the owner runs after seeing the plan" | Pass |
| Edit hook | A Python file written with an undefined name | ruff's finding returned to the agent | "ruff still reports problems in scratch_red_stop.py: F821 Undefined name" | Pass |
| Stop hook, first attempt | Turn ended with that file in place | Exit 2 with `FAIL lint`, the agent keeps working | The hook ran 820 s; Claude Code cancelled it past its 630 s limit and the turn ended with no feedback | **Fail**, fixed in `0fe9aca` |
| Stop hook, after the fix | The same | The same | Exit 2 after about two minutes: `FAIL lint`, `18 passed, 1 failed`, and the path of the full log; the agent kept working | Pass |

Not run live:

- **A write to the private configuration**, so as not to touch the owner's file. AT-8 covers it by running
  the guard exactly as `.claude/settings.json` wires it.
- **A second red stop** (`stop_hook_active`), which lets the turn end with a visible error. Unit tests and
  AT-8 cover it.

### The first stop attempt

The session transcript records the `Stop` hook as cancelled (`timedOut`) after 820,735 ms against a
630,000 ms limit. Two things went wrong:

1. **`make check` ran past 10 minutes inside the hook.** The same hook run by hand took 138 s, and the
   second live attempt about two minutes, so the cause of the slow first run is unknown.
2. **The hook's own 600 s limit didn't stop it.** `subprocess.run` killed only `make` and then waited for
   its children, which still held the output pipes open.

The fix, in `0fe9aca`:

- **The whole job is stopped.** `run_command` now runs a timed command in its own process group and kills
  the whole group on timeout.
- **A timeout says where it hung.** The hook names the check that was running from the output so far.
- **The full output is kept** in `.git/fantadamus-stop-check.log`, because Claude Code shows only the
  summary.

If a slow run happens again, the hook reports which check hung.

### Payloads against the fixtures

Every field in `tests/fixtures/hooks/` appears in the live payloads. The live payloads add these fields,
which the parser keeps:

| Event | Fields only seen live |
|---|---|
| All | `effort`, `prompt_id`, `scratchpad_dir` |
| `PostToolUse` | `duration_ms` |
| `Stop` | `background_tasks`, `last_assistant_message`, `session_crons` |

A Bash call's `tool_input` may also carry `timeout`.

### The exit-code contract

These match ADR-0001; its 2026-10-25 amendment records them.

- Exit 2 blocks a `PreToolUse` call and returns stderr to the agent.
- After `PostToolUse`, exit 2 returns stderr to the agent; the tool has already run.
- On `Stop`, exit 2 keeps the turn going, with stderr as the agent's next input.
- A hook that runs past its `timeout` is cancelled, and a cancelled `Stop` hook ends the turn silently.
