# Claude Code hook payloads (fixtures)

Example hook events in the shape documented by Claude Code's
[hooks reference](https://code.claude.com/docs/en/hooks), as recorded in ADR-0001 (task 2.2). They feed
the `HookEvent` parser tests (task 9.1) and the hook-logic tests (tasks 9.2–9.4).

- **Synthetic:** every ID, path and command is made up, so these files may be public (R2.9).
- **Documented, not yet observed:** task 9.7 compares them with payloads from a live Claude Code session
  and updates them if the shapes differ.
