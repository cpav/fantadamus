# Golden files

Reviewed outputs that tests compare against, byte for byte (R16.6). A difference fails the test with a diff.
If a change is intended, review the new output, update the file in the same pull request, and say why in
its description.

| File | What | Why it may be public |
|---|---|---|
| `skeleton/role_counts.json` | Gold `skeleton_role_counts` for `tests/fixtures/skeleton/rows.json` | Derived only from that synthetic fixture |

The same redistribution rule applies as for fixtures ([tests/fixtures/README.md](../fixtures/README.md)).
