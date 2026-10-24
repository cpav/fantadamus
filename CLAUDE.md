# Fantadamus

This project is spec-driven. The specs use Kiro's file layout, but Kiro itself isn't used: Claude Code is
the only coding agent. The steering files are the source of truth:

@.kiro/steering/product.md
@.kiro/steering/tech.md
@.kiro/steering/structure.md
@.kiro/steering/quality.md

Specs live in `.kiro/specs/<spec>/` (requirements.md → design.md → tasks.md). Work only on the current
spec's approved documents, one task at a time, and stop after each task report. Before each task, run
`make task-check TASK=<id>` (from task 9.5 on); until then, check the task's dependencies, requirement IDs,
tests and ADRs by hand.
