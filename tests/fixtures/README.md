# Test fixtures

Inputs for tests, one folder per source or purpose. The repository is public, so a fixture is committed only
if it may be redistributed (R2.9, `structure.md`); everything else lives in git-ignored `data/private/`.

| Folder | What | Why it may be public |
|---|---|---|
| `hooks/` | Claude Code hook events | Synthetic: made-up IDs, paths and commands ([README](hooks/README.md)) |
| `xy/` | One synthetic page per `mvp-x-or-y` fact contract | Synthetic: invented clubs (`Alfa`, `Beta`…), players (`Alfa Nove`…), outlet and bookmaker |
| `skeleton/` | The walking skeleton's payload (three players) and its allowlist | Synthetic: invented players (`Giocatore Uno`…) and clubs (`Squadra Alfa`, `Beta`), "read" from `example.org`, a domain reserved for documentation |

No fixture holds a real league member's name, team or roster, or a FantaCreator's identity (R2.10, R16.9).
