# Claude Code hook payloads (fixtures)

Example hook events in the shape documented by Claude Code's
[hooks reference](https://code.claude.com/docs/en/hooks), as recorded in ADR-0001 (task 2.2). They feed
the `HookEvent` parser tests (task 9.1) and the hook-logic tests (tasks 9.2–9.4).

- **Synthetic:** every ID, path and command is made up, so these files may be public (R2.9).
- **Compared with a live session** on 2026-10-25 (task 9.7): every field in these files appears in the
  live payloads, which add a few more (`effort`, `prompt_id`, `scratchpad_dir`, and per event
  `duration_ms`, `background_tasks`, `last_assistant_message`, `session_crons`). The parser keeps unknown
  fields, so these files stay the documented minimum. See `docs/reports/gate-selftest-2026-10-25.md`.
