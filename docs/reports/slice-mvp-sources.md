# Slice report: `mvp-sources`

2026-11-15 · Phase 2, the eighth slice · **Awaiting the owner's sign-off**

Fantadamus now reads three new kinds of fact itself, each from a page the owner approved (ADR-0007), with Claude as the
fallback: the Serie A clubs' matches in the other competitions, from Wikipedia; why a player is out and until when, and
who's one booking from a ban, from Fantacalcio.it; and each round's ratings from three desks, from Fantacalcio-Online.
The card and the outlook show rest days, injury and ban detail and a rater's claims as context, and none of it moves a
number. The ratings are kept as evidence for the rating constants. The anytime-scorer odds were researched, and the
owner approved a one-round trial (ADR-0008). Player figures and the owner's league aren't reproduced here: the numbers
below are aggregates.

## What the slice delivered

| Task | What | Pull request |
|---|---|---|
| 1 | The routes: ADR-0007 accepted, the five pages on the reading list and in the registry; Wikipedia read as raw wikitext at `/wiki/{title}?action=raw`, since its robots.txt turns away the API | #127 |
| 2 | The other competitions' fixtures: a reader of `Football box` templates, `OtherFixturesPayload`, silver `other_fixtures`, the collector page and `submit_other_fixtures` | #128 |
| 3 | Rest days on the card and the outlook, with their line and source, read on demand when stale | #129 |
| 4 | Injury and ban detail: rules that turn each injury sentence into a kind, a body part and a return window, the two pages and their submit tools | #130 |
| 5 | The detail on the card, the outlook and the lineup's concerns; one booking from a ban; a disagreement where an outlet has a player starting | #131 |
| 6 | Each round's ratings from three desks, kept in the calibration sets and counted as evidence | #133 |
| 7 | Rater bias with its 90% interval, and its claim on the card and the outlook | #134 |
| 8 | ADR-0008, the anytime-scorer odds compared, and a one-round trial approved on 2026-11-15 | #135 |
| 9 | The budgets with every new fact, the docs, the real check, a mutation run and this report | this PR |

Two speed-ups the owner approved on 2026-11-15 came with it: the timing tests no longer fail on a busy machine (#132),
and DuckDB runs on one thread, as fast for the lake's size and without competing with the tests' workers (#134).

## Real data

Read from Claude Code on `main` on 2026-11-15, after every task had merged, with the fetcher's rules (robots.txt,
one request a second per host, an identifying user agent):

| Page | What it gave | Size |
|---|---|---|
| Wikipedia, Champions League league phase | 144 matches, 32 with a Serie A club | 162 KB of wikitext |
| Wikipedia, Europa League league phase | 144 matches, 16 with a Serie A club | 152 KB |
| Wikipedia, Conference League league phase | 108 matches, 6 with a Serie A club | 125 KB |
| Wikipedia, Coppa Italia | 36 matches, 27 with a Serie A club; 9 waiting for their draws, left out and counted | 38 KB |
| Fantacalcio.it, injured | 64 players in 20 clubs: 55 with a kind of injury, 62 with a return window or "to be assessed" | 153 KB |
| Fantacalcio.it, suspended and diffidati | 2 players banned for round 12, 4 one booking from a ban | 130 KB |
| Fantacalcio-Online, round 11 ratings | 10 matches, 312 players, 936 desk ratings; 311 of the names found a player | 979 KB |

**Every card of round 12**, from the real lake, as a replay that collects and logs nothing:

- 12.6 to 14.9 KB and 1.0 to 1.2 seconds each.
- Each has a rest-days line for both sides, a European week where there is one, a reason on most players out, and the
  new pages in the sources.

The first real card, at 15.1 KB, was over its 15 KB budget. Carrying only each side's rest-days line, as the design
says, brought it to 14.6 KB.

**Round 11's ratings** are stored. Round 12's set is the first to keep them, when it's scored; the sets already kept stay
valid.

## Numbers

| Measure | Value |
|---|---|
| Tests | 1,479 (1,340 at the end of `mvp-recalibrate`) |
| Coverage | 98.7% of lines and 95.9% of branches; the floor is 90% |
| `make check` (19 checks) | 5 to 7 minutes on the owner's Mac, depending on its load; the test suite is most of it |
| CI per pull request | 2.7 to 5.1 minutes, median 3.5 over the last ten, against a 5-minute budget |
| Code | 16,134 lines of product code, 2,506 of checks and hooks, 27,046 of tests |
| Agent prompt | unchanged: the new detail's rendering rules are in the tools' descriptions |
| A card and an outlook with a season of ratings stored (about 27,000 rows) | 0.66 and 0.58 CPU-seconds, against 3 |

Each code task broke its own code on purpose before its report: 75 faults in all, every one caught in the end. The ones
that survived at first showed real gaps:

- an injury page's empty club card that would have kept a recovered player injured, fixed in task 5;
- four missing tests;
- a check that read the context only when the match was already known.

## Mutation testing

`make mutate` on the core modules, on fast tests, on 2026-11-15:

- **4,792 of 4,897 mutants killed (97.9%).** At the end of `mvp-recalibrate` it was 4,712 of 4,820.
- **None of the 105 survivors is in this slice's code.** They're in modules this slice didn't change: the simulation
  (36), the review (30), the player models (9) and others, read in earlier slices as equivalent or accepted.
- **This slice's core functions:** `league_rating` and `waiting` lost 129 of 129 mutants in task 6's run, and
  `with_news` and `card_player` 85 of 88 in task 5's. Those three survivors were a count that's always zero by
  construction, now removed.
- **Outside the mutation set** (`domains/raters.py`, `domains/context.py`, `domains/availability/news.py` and the
  readers): their deliberate faults by hand are their check, every one caught.

## Acceptance tests

| Test | Proves | Result |
|---|---|---|
| AT-1 | Manual: the owner approves the routes' ADR | Passed: ADR-0007 accepted on 2026-11-12 |
| AT-2 | The other competitions' fixtures from an invented page; rest days and European weeks for each side, by hand; shown on a card and an outlook | Passed |
| AT-3 | Injury and ban detail from invented pages; shown on a card, an outlook and a lineup; a disagreement shown; no chance moves | Passed |
| AT-4 | A round's base ratings from two reads by hand, and from the ratings page where the reads don't give them; kept in the set; counted as evidence | Passed |
| AT-5 | Rater bias by hand on invented ratings, with its sample; a claim shown; the expected vote unchanged | Passed |
| AT-6 | Manual: the owner reads the anytime-scorer ADR | Passed: the trial approved on 2026-11-15; it waits for the owner's API key |
| AT-7 | A card and an outlook within their budgets with the new facts; no paid service | Passed |
| AT-8 | Manual: real data from `main`: the new pages read, a card with rest days and injury detail, a round's ratings kept | Passed, as above |

P1 to P5 hold: rest days in order, a match read back, the injury rules' kinds and windows, a rater's bias in its interval
and summing to zero, and no number moved by any new fact.

## Cost

$0, as estimated:

- No paid service and no account; nothing runs on AWS.
- The five pages are read at most daily, the ratings once a round, about 1.5 MB a day at most.

ADR-0008's trial would use 10 to 20 of The Odds API's 500 free credits, once the owner has created the account.

## Open risks

- **A card's size is close to its budget.** Round 12's largest card is 14.9 KB against 15. The slice adds about 700
  bytes to a card, and a club with many players out adds more. If one goes over, the out list's names, which the card's
  `players` already holds, are the next to go.
- **Wikipedia is written by volunteers.** A kickoff can be missing or late, and a knockout round's page appears only after
  its draw: the Champions League's and the cup's next pages must be added to the reading list then.
- **The injury rules read one page's style.** 55 of 64 kinds and 62 of 64 returns on the first real read; the real-page
  check asks for 75% and fails loudly if the page's wording drifts.
- **The ratings evidence starts now.** About 300 rated players a round against the 1,500 the rating constants need: about
  five rounds. A rater's claim needs five matches, so the first ones appear around round 16.
- **The scorer-odds trial waits on the owner.** The Odds API prices soccer player markets only from US bookmakers, so the
  trial may stop after its first credit.
- **Claude Desktop must be restarted** for the new pages and the new detail to reach the owner's answers.

## Decisions for the owner

1. **Sign off this slice?** Recommendation: yes. Every acceptance test has passed, and the real check read every new page.
2. **The trial's key.** Create a free account at the-odds-api.com and put its key in the private configuration file
   (`~/.config/fantadamus/private.toml`), when convenient. Only the owner can create it. The trial runs on the next round
   after.
3. **A share for each kind of cameo**, carried from the last slice: recommended as the first change of the next
   recalibration, once round 12 is scored.

## Next

The last slice before going online, in `product.md`'s order: alerts on the Mac ("the official lineup changes your
call"). Then the full review with Fable 5.2, and Phase 3: online, with nothing to install.
