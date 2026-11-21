# Requirements Document: `mvp-fixes` (Phase 2, eleventh slice)

Status: **Draft, awaiting the owner's approval** · Workflow: requirements-first · Depends on: `mvp-store` (signed off
2026-11-18) · Abbreviation: `fx` · Research: the test of round 12 on the owner's Mac and lake, 18 to 21 November 2026
(times and counts below, no names)

## Introduction

Round 12 was the first round run end to end with every Phase 2 slice, the schedule installed and the owner's own
questions in Claude Desktop. Every number Claude gave matched the one Fantadamus logged. The test found five faults.
None changed a number on the day, but the first will keep costing news for as long as the schedule runs on a Mac that
sleeps. This slice fixes all five, the first before round 13.

What happened:

- **A read that failed for want of a network held the next one back for up to a day.** The schedule runs only while
  the Mac is awake: 19 runs from Wednesday afternoon to Saturday morning, and not one read on Friday. On Saturday a run started
  in a maintenance wake at 06:01, read the round page, was suspended by sleep for two hours and resumed in an
  11-second wake at 08:02 with no network. Two hosts' robots.txt couldn't be fetched, so the fetcher allowed nothing
  on those hosts for the run (`web/fetch.py`), and their nine pages were logged as "disallowed", with "robots.txt
  disallows" as the reason. The schedule and the answers count any try as a page's read, whatever came of it
  (`CollectLog.last_attempt`, used by `web/cadence.py`), so the statistics, penalty-takers and table pages weren't
  due again for 24 hours, the injured and suspended pages for 12, and a question at 09:03 couldn't read them either.
  Read by hand at 09:34, every page answered, and both robots.txt files allowed the pages as before.
- **Claude can't ask for five of the eleven facts.** The `collect` tool takes 6 facts and its description names 3
  pages (`mcp/tools/collect.py`); the collector reads 11 (`FACTS` in `web/collector.py`). "Refresh the injuries" has
  no tool to call.
- **The lineup's sources leave out the injury page.** A lineup says why a player is out and when he's back, from
  Fantacalcio.it's injured and suspended pages, but its sources don't name them (`sources_of` in
  `mcp/tools/lineup.py`). The match card does.
- **A penalty note hides why a share is whole.** When everyone listed ahead of a taker is out, the note reads "Y takes
  the club's penalties if X misses the start: they count at 100%" (`mcp/advisor.py`). It reads as a condition when
  it's a fact: X is out.
- **The review forgets the app's total.** `review_round` compares the user's total from their league's app with its
  own count, but only in the answer: the review log (`LoggedReview`) doesn't keep it, so the season's agreement can't
  be told.

**Not in this spec:**

- keeping the Mac awake, or moving the schedule off it: Phase 3;
- one registry of facts and pages (the review's R5): the smallest fix here, the registry with Phase 3 (decision 2);
- any change to a chance, a value or a constant: answers change only in the sources and notes named here.

## Glossary

| Term | Meaning |
|---|---|
| Try | A run's attempt at a page, whatever came of it |
| The site's answer | A response from the page's host: the page itself (stored, unchanged, rejected or unreadable), a refusal by its robots.txt, or a block (the fetcher's block statuses: 401, 403, 407, 429, 451, 503) |
| Failed try | A try with no site's answer: a network error, a timeout, another server error (500, 502, 504), or a page not requested because its host's robots.txt got one of those |
| Cadence | How often the schedule reads each fact (`web/cadence.py`); an answer has its own shortest interval per page |

## Requirements

### Requirement 1: A failed try doesn't count as a read

**User Story:** As a player whose Mac sleeps and wakes through the day, I want a page that couldn't be reached to be
read again soon, so that a bad moment at waking doesn't cost a day's news.

- **R1.1** IF a host's robots.txt gets no answer, a timeout or a server error outside the block statuses THEN THE
  SYSTEM SHALL report each of that host's pages in the run as failed, saying that robots.txt couldn't be read and why,
  not as disallowed. A robots.txt the site serves, a 404 or 410 for it, and a block status keep today's handling.
- **R1.2** WHEN the schedule decides what is due, and WHEN an answer decides whether it may read a page, THE SYSTEM
  SHALL count only tries that got the site's answer. A page whose last try failed SHALL be due again at the next
  scheduled run, and an answer may read it again 15 minutes after the failed try (decision 1).
- **R1.3** THE SYSTEM SHALL stay as polite while retrying as it is today (`mvp-collect` R2): one request a second per
  host, robots.txt honoured, and at most one try of a page in a scheduled run.
- **R1.4** A block SHALL keep counting as a try: a site that says stop isn't asked again before the page's cadence.
- **R1.5** The run's report and `fantadamus collect --report` SHALL show the failed pages as failed, with the cause,
  and say they will be tried again.
- **R1.6** This SHALL change no stored fact and no number: a page read after a failure is stored like any other read.

### Requirement 2: Claude can ask for every fact

**User Story:** As a player who asks "refresh the injuries", I want Claude to have a tool for it, not only for the
round page.

- **R2.1** THE `collect` tool SHALL accept every fact the collector reads, from the collector's own list, and its
  description SHALL name every page it reads.
- **R2.2** A test SHALL fail if the tool's facts and the collector's differ.
- **R2.3** A fact read once a round, the ratings, SHALL be read for the round just played, as
  `fantadamus collect --fact` reads it. The agent prompt needs no change, so nobody pastes it again.

### Requirement 3: Every page an answer shows is in its sources

**User Story:** As a player, I want every fact in an answer traced to the page it came from (`product.md`, trust and
provenance).

- **R3.1** WHEN an answer says why a player is out or banned, or when he's back, THE SYSTEM SHALL name the injured or
  suspended page it came from among the answer's sources, with when it was read, as the match card does.
- **R3.2** THE same SHALL hold for every answer and every page whose facts it shows: the lineup, "X or Y?", the
  outlook, the card, the overview and the review.

### Requirement 4: A penalty note says why

**User Story:** As a player reading a warning, I want to be told that a taker's share is whole because the man ahead of
him is out, not to work it out.

- **R4.1** WHEN everyone listed ahead of a taker is out THE note SHALL say so, naming them: "X, first on the list, is
  out, so Y takes the penalties: counted in full."
- **R4.2** WHEN anyone listed ahead may start, the note SHALL keep today's form, with the share.

### Requirement 5: The review keeps the app's total

**User Story:** As a player, I want to know over the season how often Fantadamus's count of my score agrees with my
league's app, and when it doesn't.

- **R5.1** WHEN a review is given the user's app total THE SYSTEM SHALL keep it in the review log, with whether it
  differed from its own count by more than `APP_GAP`.
- **R5.2** THE season record SHALL say in how many reviewed rounds the app's total matched, from the first round with
  one (decision 3).
- **R5.3** Reviews logged before this slice SHALL still read, with no app total.

### Requirement 6: Proof, order and docs

- **R6.1** Requirement 1 SHALL land first, in its own pull request, before round 13's alerts window opens.
- **R6.2** Each fix SHALL come with its test written first, and the slice SHALL need no new dependency, service or
  account.
- **R6.3** THE SYSTEM SHALL update the player guide where it describes the schedule and what to do when something
  goes wrong, and the README's `collect` line.

## Acceptance tests

| Test | Proves | Requirement |
|---|---|---|
| AT-1 | A run whose robots.txt gets no answer, a timeout or a 500 reports the host's pages as failed, with the cause, and the next scheduled check finds them due; a disallowing robots.txt and a block keep counting, and wait for the cadence | R1.1, R1.2, R1.4 |
| AT-2 | Over runs that keep failing, each page is tried at most once a run, one request a second per host; an answer retries no sooner than 15 minutes after a failed try | R1.2, R1.3 |
| AT-3 | The report and `fantadamus collect --report` show failed pages, their cause and that they'll be tried again | R1.5 |
| AT-4 | The `collect` tool accepts every fact in the collector's list and reads its page; adding a fact to one and not the other fails a test | R2 |
| AT-5 | For each kind of answer, every page whose facts it shows is among its sources; a lineup with an injured player names the injured page | R3 |
| AT-6 | A taker whose listed predecessors are all out gets the "is out" note; one with a doubtful predecessor keeps the share | R4 |
| AT-7 | A review given an app total keeps it in the log; the record counts the matching rounds; a line logged before the slice still reads | R5 |
| AT-8 | From here, on a copy of the owner's lake: Saturday's run replayed with its unreachable robots.txt leaves the pages due at the next run, and every answer of the copy is unchanged apart from the sources and notes named here | R1.2, R1.6 |
| AT-9 | No new dependency; the docs updated | R6.2, R6.3 |

## Review (Analyze-Requirements style)

- **Ambiguity:** "the site's answer" and "failed try" are in the glossary, by status. "Unchanged apart from the sources
  and notes" is the tool's structured result, compared field by field.
- **Conflict:** retrying sooner against politeness (R1.2, R1.3). A failed try asked nothing of the page, or got no
  answer; at most one try a run means at most four an hour per page while it keeps failing, the rate the round page is
  already read at before a kickoff. A block still waits for the cadence (R1.4).
- **Testability:** every requirement has a test. Saturday's failure is replayed from the collection log (AT-8), with
  nothing for the owner to do.
- **Dependencies:** `mvp-collect` (the fetcher, the collector, the cadence), `mvp-sources` (the injured and suspended
  pages), `mvp-lineup` (the penalty notes), `mvp-review` (the review log).

## Decisions for the owner

1. **How soon is a page that failed tried again?** Recommendation: at the next scheduled run, 15 minutes later while
   the Mac is awake, and by an answer 15 minutes after the failed try. That's at most four tries an hour per page while
   it keeps failing, each as polite as today. The alternative, waiting an hour after a failure, can cost an hour of news
   after every bad wake.
2. **How far does the `collect` fix go?** Recommendation: the smallest fix, here: the tool takes the collector's own
   list of facts and names its pages, with a test that they agree. The review's one registry of facts and pages (its
   R5) waits for Phase 3, where adding a page changes anyway.
3. **Should the review's season record say how often your app agreed?** Recommendation: yes, one line ("your app's
   total matched in 4 of 5 rounds"), once a round has an app total. The log keeps the numbers either way.
