# Phase 1 report: "X or Y?" for forwards

2026-10-26 · Spec `mvp-x-or-y` · **Awaiting the owner's sign-off** (task 8.3)

## What Phase 1 delivered

The first thin slice answers "X or Y?" for two forwards in the owner's own Claude Desktop, end to end:

- **Seven submit tools.** Fixtures, a player's season, the league table, penalty takers, probable lineups,
  official lineups and match odds. Each takes its versioned contract with its quality rules, checks the
  page's host and the clubs, and stores the fact in bronze and silver with its provenance.
- **The method for forwards** ([method](../method.md) §A3, §A4), in tested Python:
  - availability, from the outlets' consensus or the official lineup;
  - team xG fitted from the betting lines (Poisson with the Dixon–Coles correction), or regressed team form
    when there are no odds;
  - shares, expected goals and assists, the priced cameo and the key;
  - the verdict, its margin, the verdict without bench cover, and what would flip it.
- **League rules.** Each user sets them once in Claude, with the Classic values offered.
- **`compare_players`.** It returns the setup step, the candidates, one refresh plan of everything missing
  or stale, or the answer with its breakdown and sources.
- **The decision log.** Every answer appends one line, the start of calibration (method §A8).
- **`fantadamus serve` for Claude Desktop**, with the agent prompt as its instructions and the setup in the
  README.

## The first real round (AT-11)

On 2026-10-26 the owner added the server to Claude Desktop, set the league's rules (Classic) and asked a real
"X or Y?" between two forwards of the same club for round 9. Claude read the pages in the refresh plan and
submitted six facts, and `compare_players` answered.

| Check | Result |
|---|---|
| Rules set from Claude Desktop | Yes: Classic values, stored under the owner's pseudonymous ID |
| Facts stored | 6: two profiles, the penalty takers, the league table, the round's fixtures, one outlet's probable lineups |
| Sites they came from | `www.fantacalcio.it` (4), `it.wikipedia.org` (2): all on the reading list; none rejected for their host |
| Odds | None found on the listed betting previews; the answer used regressed team form and said so |
| Answer | A clear verdict: one player was listed injured (p_start 0, no cameo), so the other started |
| Decision log | One entry: both players' p_start, p_cameo, P(scores) and keys, the verdict, the rules and six content hashes |

Player figures and the answer's numbers aren't reproduced here: they derive from third-party pages, and this
repository is public.

## Numbers

| Measure | Value |
|---|---|
| Tests | 487 (408 at the end of Phase 0) |
| Coverage | 98.4 % of lines and 94.1 % of branches; the floor is 90 % |
| `make check` (19 checks) | about 100 s on the owner's Intel Mac (about 80 s before this phase's property tests) |
| CI per pull request | 73 to 100 s, against a 5-minute budget |
| Code | 3,634 lines of product code, 2,506 of checks and hooks, 6,010 of tests |

## Acceptance tests

| Test | Proves | Result |
|---|---|---|
| AT-1 | Method §A9.2: the tie at 6.54, and the ranking that ignores the bench rejected | Passed |
| AT-2 | Method §A9.4: a centre-forward about 32 % to score, a rotation striker about 12 %; the first ranks ahead | Passed |
| AT-3 | Method §A9.6: start X, Y first on the bench; without bench cover, Y | Passed |
| AT-4 | Scripted collection, from an empty lake to an answer with sources | Passed |
| AT-5 | An official lineup overrides three disagreeing outlets | Passed |
| AT-6 | Two outlets at 0.90 and 0.50 give 0.70, disputed | Passed |
| AT-7 | Bad submissions rejected with the reason, nothing stored | Passed |
| AT-8 | An earlier as-of time ignores later facts | Passed |
| AT-9 | One log entry per answer, never changed | Passed |
| AT-10 | The setup step, the rules used, out-of-range values rejected | Passed |
| AT-11 | The owner's real round in Claude Desktop | Passed, 2026-10-26 |

Properties P1 to P8 from the design all hold.

## Cost

$0. Everything runs on the owner's Mac, and collection uses the owner's own Claude plan.

## Decisions taken in Phase 1

All small and reversible, each logged in its pull request:

- **Storage.**
  - One shared ingest flow for every fact.
  - Silver keeps every submission; gold is read as-of, not stored.
  - Lineup names are resolved when read, so a name becomes a player once his profile arrives.
- **The team xG fit.** A coarse grid, then a halving search, using the Dixon–Coles closed forms: about 6 ms
  per fit.
- **League rules.** Every value is required; the penalty term is priced at the league's penalty-scored
  value.
- **The refresh plan** asks for everything already known to be needed. The `odds_unavailable` flag lets
  Claude ask for an answer from team form after finding no odds.

## Found in the real round

1. **Claude answered from the web until told to use the tools.** Its first reply cited news sites and never
   called Fantadamus. Naming the tool fixed it. Decision 2 below.
2. **The collector's clock ran ahead.** Claude stamped facts a few minutes after the server received them,
   so `compare_players` saw them as not yet read. Fixed in PR #17: a capture after receipt counts as the
   receipt time.
3. **An injured player was put "first on the bench".** R10.1's sentence always benches the second player,
   even one with no chance of a rating. Decision 1 below.
4. **The deadline was misread.** The answer's deadline is the round's first kickoff, as R2.2 defines it, but
   Claude presented it next to the players' own match. Each player's kickoff is in the answer. The agent
   prompt could say which is which; that goes in with decision 2.
5. **Thin coverage.** Claude read one outlet's lineups and found no odds on the listed previews. The answer
   worked as designed (one fresh outlet is enough, and team form stood in, flagged), but it rests on less
   than the method would like. Decision 3 below.

## Decisions for the owner

1. **When the second player can't play, say so.** For example: "start X; Y isn't playing, so put a fit
   forward first on the bench." **Recommendation: yes.** It's a one-line change to R10.1, then the code;
   it goes first in the next slice.
2. **Make Claude use Fantadamus without being told.** Create a Claude Project called "Fantadamus" with the
   agent prompt as its instructions, and say in the prompt which time is the round's deadline.
   **Recommendation: yes.** There is no code, only a README step and two lines in the prompt.
3. **Odds when the previews have nothing.** Either keep the flagged team-form fallback, or add another odds
   page to the reading list, after checking its terms. **Recommendation: keep the fallback for now**, and
   look at odds coverage with the next slice.

## Open risks and follow-ups

1. **`make check` is slower:** about 100 s, from about 80 s. The long pole is Phase 0's lake property test
   (25 s); trim it before it grows.
2. **The agent prompt names tools from later specs** (`get_round_context`, `best_lineup`…). Claude coped,
   but the prompt should match what exists.
3. **Carried from Phase 0:**
   - the creator-name placeholder is still in use;
   - the cryptography allowlist must be renewed by 2027-01-26;
   - the presentation pages show 25 October figures.
4. **Mutation testing** joins the phase gate from Phase 2 (`quality.md`).

## Next

After sign-off, Phase 2's next slice gets its own small spec. The first candidates are keepers and
defenders, then the full lineup with the bench. Decision 1, if approved, goes in first.
