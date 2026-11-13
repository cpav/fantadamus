# Design Document: `mvp-sources` (Phase 2, eighth slice)

Status: **Approved by the owner, 2026-11-12**, with both open points · From the approved [requirements](requirements.md) ·
Route: [ADR-0007](../../../docs/adr/0007-mvp-reads-other-competitions-injuries-and-ratings.md) (accepted with this design)

## Overview

Three new facts reach Fantadamus from pages it reads itself, on ADR-0006's rules, each with Claude as the fallback: the
other competitions' fixtures, from Wikipedia; injury and ban detail, from Fantacalcio.it; and each round's ratings from
three desks, from Fantacalcio-Online. They're shown as context on the cards, the outlook and the lineup, and kept as
evidence; no number moves (decision 2). A fourth piece, the anytime-scorer odds, is research only: an ADR and a trial plan.

## What it builds on

- `web/collector.py`: the page kinds Fantadamus reads itself (`round`, `statistics`, `takers`, `table`), each with its
  reader in `web/readers/`, its switch in `config/reading_list.toml` and its cadence in `web/cadence.py`.
- The submit tools (`mcp/tools/submit.py`) and `read_page`: Claude's fallback, on the same contracts.
- `domains/review.py`'s `player_round`: a player's rating in a round, recovered exactly from two statistics reads.
- `domains/calibration.py`'s `SetRow` and `domains/recalibration.py`'s `waiting`.
- `domains/cards.py` (`Out`, `CardPlayer`), the lineup's `Concern`, and the outlook's `CompareResult`.

## Components

### C1. The routes (ADR-0007, the registry, the reading list; R1)

ADR-0007 records the five pages, their robots.txt and terms as read on 2026-11-12, and their cadence. The source
registry's reading list and "What we read for each need" gain them, and `config/reading_list.toml`'s `[collector]` gains
an address for each; the task that builds a page's reader adds its switch:

| Key | Page | Page kind |
|---|---|---|
| `other_competitions` | Wikipedia's raw wikitext, `/wiki/{title}?action=raw`, one page per competition: robots.txt turns away `/w/`, where the MediaWiki API is *(corrected in task 1)* | `other_fixtures` |
| `injuries` | `fantacalcio.it/infortunati-serie-a` | `injuries` |
| `suspensions` | `fantacalcio.it/squalificati-e-diffidati-campionato-serie-a` | `suspensions` |
| `ratings` | `fantacalcio-online.com/it/serie-a/2026-2027/voti/{round}-giornata` | `ratings` |

A knockout round's Wikipedia page appears after its draw; its title is added to the list then.

### C2. The other competitions' fixtures (`web/readers/wiki_fixtures.py`, `domains/fixtures/`; R2.1)

- **Reader.** Each match is a `{{#invoke:Football box|main …}}` template. The reader takes `date` from its `{{Start
  date|Y|M|D}}`, or from plain text ("8 August 2026") as the Coppa Italia's page writes it, `time` (`HH:MM`, Italian time, as the page's prose says: UEFA's and the cup's times are CET or CEST) and
  `team1` and `team2` from their links; the score where it's played. A match without a date or a time ("TBD") is left
  out.
- **Contract.** `OtherFixturesPayload` (1.0.0): the competition and its matches, each with `kickoff_at`, `home`, `away`.
  A Serie A club is resolved through `config/clubs.toml`, which gains the Wikipedia spellings ("Inter Milan"); other
  clubs keep their names.
- **Silver.** `other_fixtures`: one row per match with at least one Serie A club.
- **Submit tool.** `submit_other_fixtures`, on the same contract, for Claude's fallback.

### C3. Rest days (`domains/context.py`, pure; R2.2, R2.3)

`rest_days(club, kickoff, serie_a, other) -> RestDays` for one side of a Serie A match:

- `previous` and `next`: the club's nearest matches before and after, in any competition, with their competition;
- `days_since` and `days_to`, in whole days between kickoffs in Italian time;
- `european_week`: either is a European match within `EUROPEAN_WEEK_DAYS` *(start)*: 3.

The card's `CardSide` and the outlook gain it. The line: "Inter played Wednesday in the Champions League: 3 days'
rest." No number moves (decision 2).

### C4. Injury and ban detail (`web/readers/fcit_unavailable.py`, `domains/availability/`; R3.1)

- **Reader, injuries.** By club, each entry a name and a sentence. Rules turn the sentence into facts, and the sentence
  isn't kept:
  - the kind: a muscle injury (*lesione*, *distrazione*, *stiramento*, *elongazione*, *affaticamento*), a knock
    (*contusione*, *trauma*, *botta*), a fracture, a ligament injury (*legamento*, *crociato*), surgery (*operato*,
    *intervento*), illness (*febbre*, *influenza*, *virus*), a national-team injury (*Nazionale*), else "other";
  - the body part, from a short list (thigh, calf, knee, ankle, adductor, hamstring, foot, shoulder, back, other);
  - the return window: "back from early, mid, the second half of or late {month}" (*rientro*/*recuperabile dalla
    inizio, metà, seconda metà, fine di …*), "out for about N days, weeks or months" (*stop di circa N …*, counted from
    the date the sentence gives, else from the read), "to be assessed" (*da valutare*), else none.
- **Reader, bans.** By club: who's banned and the round he misses ("*squalificato nella 12a giornata*"), and who's one
  booking from a ban.
- **Contracts.** `InjuriesPayload` and `SuspensionsPayload` (1.0.0); **silver** `injuries` and `suspensions`;
  **submit tools** `submit_injuries` and `submit_suspensions`.
- Names resolve among the club's players, as the round page's do.

### C5. Detail on the answers (`domains/cards.py`, `mcp/tools/lineup.py`, the outlook; R3.2, R3.3)

- `Out` gains `reason` and `back` ("thigh muscle injury", "back late November"); a banned player's reason is "banned
  for round 12".
- `CardPlayer` and the outlook gain `one_booking_from_a_ban`.
- The lineup's `Concern` gains `reason`.
- **A disagreement:** a player an outlet lists to start while the injury or ban page lists him out is shown as such,
  on the card and the outlook ("an outlet has him starting; Fantacalcio.it's injury page has him out"). His chance of
  starting doesn't change (R3.3).

The rendering rules go into the tools' descriptions, not the agent prompt (12,911 of its 13,000 characters).

### C6. Per-match ratings (`web/readers/fco_ratings.py`, `domains/ratings/`; R4)

- **Reader.** By match, each player row: his role, his name, when he came on or off, and three numbers: the
  Fantacalcio.it, Roma and Torino desks' base ratings. "s.v." (seen, no rating) and "–" (not yet published) are kept apart.
- **Contract** `RatingsPayload` (1.0.0); **silver** `match_ratings`, one row per player, match and desk; **submit tool**
  `submit_ratings`.
- **In the calibration set.** `SetRow` gains `rating: float | None` and `rating_from: Literal["reads", "page"] | None`:
  the league's rating recovered from the statistics reads around the round where `player_round` gives it exactly,
  otherwise the Fantacalcio.it desk's from `match_ratings`. Old sets stay valid.
- **As evidence.** `waiting`'s rating group gains `have`, the rows with a rating, against `MINIMUM_SAMPLE["ratings"]`
  *(start)*: 1,500. Fitting the rating constants is a later recalibration's (R4.3).

### C7. Rater bias (`domains/raters.py`, pure; R5)

`desk_bias(rows) -> list[Bias]`, for each player and desk, over the matches all three desks rated:

- the bias is the mean of the desk's rating minus the other two desks' mean, with its count and a 90% interval (the
  mean plus or minus 1.645 standard errors);
- a claim when the bias is at least `RATER_BIAS_SHOWN` *(start)*: 0.25, over at least `RATER_BIAS_MATCHES` *(start)*: 5
  matches.

The outlook and the card's player show the claim ("Fantacalcio.it rates him 0.3 above the other desks, over 9 matches").
His expected vote doesn't change (R5.3).

### C8. Anytime-scorer odds, researched (ADR-0008; R6)

ADR-0008 compares:

- **The Odds API's** `player_goal_scorer_anytime` for Serie A: US bookmakers only, one request per match at a credit per
  market and region, about 20 of the free 500 credits a round, and an account in the owner's name;
- **betting-news pages** on the reading list, where they give scorer prices;
- **any other found**, with its coverage, cost and terms.

It sets out how the method uses them (§A4: a large gap between our chance of scoring and the market's is a flag, never
averaged) and a one-round trial for the owner to approve. No code.

### C9. Freshness, cadence and budgets (`engine/constants.py`, `web/cadence.py`; R7)

| Fact | Fresh for | Read |
|---|---|---|
| Other competitions | a week; a day in a week with a match | weekly, daily in a match week |
| Injuries and bans | 24 hours; 12 in the last 48 before a round | daily, twice a day near a round |
| Ratings | once a round | the morning after it, and when the round is scored |

A card stays within 3 seconds and 15 KB: a rest-days line for each side, and a reason only for the players it lists as
out. No paid service, no account (R7.2).

### C10. The docs (R8)

The source registry and the reading list; `docs/answer-formats.md`, where rest days move from "Later" into format 5,
with the injury detail and the raters' claims; method §A8; the player guide.

## Error handling

| Condition | Behaviour |
|---|---|
| A page blocked, changed or unreadable | Its facts aren't stored; Claude's refresh plan names it, as for every page |
| A Wikipedia match without a date or time | Left out; the card shows the previous and next matches it has |
| An injury sentence the rules can't place | Kept as "out, detail on the page", with the link |
| A name that doesn't resolve | Left out, and counted in the read's report |
| A round whose reads don't recover a rating | The ratings page's Fantacalcio.it rating, marked as such |

## Correctness properties

These Hypothesis tests are required:

| # | Property | Requirements |
|---|---|---|
| P1 | Rest days are never negative, and the previous match is before the kickoff and the next after it | R2.2 |
| P2 | A Football box template's match, written by a generator, is read back the same | R2.1 |
| P3 | The injury rules give a known kind or "other", and a return window, if any, after the read | R3.1 |
| P4 | A desk's bias lies in its interval, and the three desks' biases for a player sum to zero | R5.1 |
| P5 | The new facts move no chance of starting and no expected score | R3.3, R5.3, decision 2 |

## Testing strategy

- **Unit and property**, in `tests/unit/sources/` and `tests/property/sources/`: the readers on invented pages in the
  real layouts, rest days, the injury rules and the bias.
- **Integration**, in `tests/integration/sources/`: each page through the collector, its submit tool, and a card and an
  outlook with the new facts.
- **Acceptance**, in `tests/acceptance/sources/`: AT-2 to AT-5 and AT-7 automated; AT-1, AT-6 and AT-8 by hand.

The real pages can't be committed: tests use invented pages with the same layout.

## Cost

$0. Five more pages, read at most daily, one request a second per host; no paid service and no account.

## Build order (input to tasks.md)

1. **The routes:** ADR-0007 accepted, the registry and reading list; this spec current.
2. **The other competitions' fixtures:** the reader, contract, page and submit tool.
3. **Rest days** on the card and the outlook.
4. **Injury and ban detail:** the readers, contracts, pages and submit tools.
5. **The detail on the answers,** and the disagreement.
6. **Per-match ratings:** the reader, contract, page and submit tool; the league's rating in the sets; the evidence
   counted.
7. **Rater bias** and its claims.
8. **The anytime-scorer odds ADR.**
9. **A real check and sign-off:** budgets, docs, a real round, a mutation run and the slice report.

## Open points for the owner

Both approved on 2026-11-12 ("Approve all").

1. **Injury sentences read by rules.** Recommendation: Fantadamus turns each sentence into a kind, a body part and a
   return window by rules, and keeps no prose; what the rules can't place shows as "detail on the page", with the link.
   The alternative is Claude reading them, which needs a player's Claude every day.
2. **When a rater's bias is shown.** Recommendation: 0.25 of a rating point or more, over at least 5 matches all three
   desks rated, both *(start)* values for a later recalibration.
