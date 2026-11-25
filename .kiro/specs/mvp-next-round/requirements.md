# Requirements Document: `mvp-next-round` (after Phase 2, before Phase 3)

Status: **Draft, for the owner's approval** · Workflow: requirements-first · Depends on: `mvp-fixes` (signed off
2026-11-24) · Abbreviation: `nr` · Research: the code on `main`, a copy of the owner's collection log and stored fixtures,
and two approved pages, all read on 2026-11-25 (times and counts below, no names)

## Introduction

The schedule decides when to read lineups and odds, and when the alert window opens, from the next round's matches. The
next round is the first one stored whose deadline, its first kickoff, is still ahead (`next_round`). Once a round kicks off
there is none, until something reads the round page again and finds the next round there. All that brings the schedule back
to that page is the fixtures' own cadence, a week after the page's last answered read (`web/cadence.py`).

A week is too long. Of the four gaps between deadlines since round 9, three were shorter (3 days 20½ hours, and twice
6 days 5¾ hours), so the read comes after the next round has locked. Only the international break (14 days 18 hours) was
longer.

What happens now, in Rome's time:

- **The schedule has known no next round since Saturday 21 November at 15:00**, round 12's deadline, with eight of its ten
  matches still to come. It had last read the round page at 14:13. It has read its other pages as usual since, and not
  this one.
- **Its next read is due on Saturday 28 November at 14:14. Round 13's deadline is Friday 27 November at 20:45**, 17½ hours
  earlier. So it would read no lineup and no odds for round 13, and the alert window, open from Thursday at 20:45, would
  pass without a check.
- **Round 13 could then be skipped altogether.** The page moves on to the next round soon after a deadline: 18 minutes
  after round 11's it hadn't yet, 4 hours 21 minutes after round 10's it had. By Saturday it would most likely show round
  14, so the schedule would never store round 13's fixtures and never score the round.
- **The page already shows round 13.** Read on 25 November, [Fantacalcio-Online's round page][page] and
  [Fantacalcio.it's calendar][calendar] give the same first kickoff.
- **The schedule is otherwise healthy.** From its installation on 18 November to the evening of 25 November it ran 80 times,
  the last with exit code 0. Round 12 was already stored when it was installed, so 21 November was the first time it had to
  find a round by itself.
- **There is a way round it until this lands.** An answer that needs the round reads the page on demand. One question to
  Claude about the next round, or one `fantadamus collect`, makes the round known, and the schedule takes over from there.

The page is one address (`current_round` in `config/reading_list.toml`), so a read a day finds the next round within a day
of the site showing it. On the copy, that read would have been due on Sunday 22 November at 14:14, five days before round
13's deadline. It adds about one read of the page a round to some 45 (the
[review before Phase 3](../../../docs/reports/review-before-phase-3.md)).

**Not in this spec:**

- a Mac that sleeps: the read waits for a run, as every read does. Phase 3 moves the schedule off the Mac;
- a round missed altogether, with no run between one deadline and the next: `fantadamus collect --round N` reads its page,
  as today;
- reading the season's calendar, so that every round is known in August: a new page, its reader and its route, for what
  one more read a round settles;
- any change to a chance, a value, a constant or an answer.

[page]: https://www.fantacalcio-online.com/it/serie-a/2026-2027/probabili-formazioni/ultima-giornata
[calendar]: https://www.fantacalcio.it/serie-a/calendario

## Glossary

| Term | Meaning |
|---|---|
| Deadline | A round's first kickoff (`product.md`); from then on the round is locked |
| Next round | The first stored round whose deadline is ahead (`next_round`) |
| Unknown | No stored round's deadline is ahead. Matches may be: a locked round's later ones, or one postponed from an earlier round |
| Round page | The page at `current_round`, which shows one round at a time and names it in its title |
| Look | A scheduled read of the round page made because the next round is unknown |
| Answered read, failed try | As in `mvp-fixes`: a try that got the site's answer, and one that got none |

## Requirements

### Requirement 1: The schedule looks for the next round

**User Story:** As a player who counts on the schedule, I want it to find the next round by itself soon after one has
locked, so that the round's lineups, odds and alerts are there without my asking first.

- **R1.1** WHILE the next round is unknown THE SYSTEM SHALL count the fixtures as due 24 hours after the round page's last
  answered read, instead of a week (decision 1).
- **R1.2** THE SYSTEM SHALL decide that the next round is unknown from the rounds' deadlines alone. A locked round's later
  matches, and a match postponed from an earlier round, SHALL NOT hold a look back (decision 2).
- **R1.3** THE SYSTEM SHALL keep looking at that pace until a round whose deadline is ahead is stored, however long that
  takes (decision 2).
- **R1.4** WHEN the next round is known, whether a look, an answer or a submission stored it, THE SYSTEM SHALL keep today's
  cadence for every fact: the fixtures weekly, the lineups and odds from 72 hours before each match.
- **R1.5** WHILE the schedule runs and the site answers THE SYSTEM SHALL store the next round within 24 hours and one run
  of the page showing it. A round shown 49 hours before its deadline is then known before its alert window opens.
- **R1.6** A look SHALL store what any read of the page stores, and SHALL change no rule by which a number, an answer or an
  alert is worked out.

### Requirement 2: As polite as today

**User Story:** As the owner, I want looking for a round to follow the rules I approved and to ask little of the site.

- **R2.1** A look SHALL keep `mvp-collect` R2 unchanged: robots.txt, one request a second per host, the allowlist, the user
  agent, a host that blocks stopped for the run, and the page's switch in the reading list (decision 3).
- **R2.2** A run SHALL ask for the round page at most once, whatever is due, and THE SYSTEM SHALL make no look within
  24 hours of an answered read of the page.
- **R2.3** `mvp-fixes` R1 SHALL hold unchanged: a look that failed is tried again at the next run. One that got the site's
  answer, be it a refusal, a block, a page that's gone or one that can't be read, waits its 24 hours (decision 3).
- **R2.4** An answer SHALL read the page on demand by the same rules as today.

### Requirement 3: Proof, order and docs

- **R3.1** This SHALL land in a pull request of its own before round 14's alert window opens. Round 13's is too close to
  promise.
- **R3.2** Each requirement SHALL come with its test written first, on invented pages and a set clock. No earlier
  acceptance test SHALL change, and the slice SHALL need no new dependency, service or account.
- **R3.3** THE SYSTEM SHALL update the cadence's tables (`mvp-collect` R7.1, marked as amended, and `web/cadence.py`) and
  the player guide's step 8.

## Acceptance tests

| Test | Proves | Requirement |
|---|---|---|
| AT-1 | An invented page read every 15 minutes across a deadline, showing the locked round at first and the next one later: the next round is stored at the first run 24 hours after the last answered read, and from then on every fact keeps today's cadence | R1.1, R1.4, R1.5 |
| AT-2 | With the locked round's later matches ahead, and with a match postponed from an earlier round ahead, the look is due all the same | R1.2 |
| AT-3 | A page that shows the locked round for three weeks is read each day, never twice in 24 hours, and stores nothing new; the first look after it changes stores the next round | R1.3, R2.2 |
| AT-4 | A look that gets no answer is due at the next run; a refusal by robots.txt, a block, a page that's gone and an unreadable one wait 24 hours. Each run asks for the page at most once, after robots.txt and a second apart; with its switch off, nothing is asked | R2.1, R2.2, R2.3 |
| AT-5 | Two invented rounds whose deadlines are three days apart: the second is known before its alert window opens, and an official lineup stored in the window sends its alert | R1.5 |
| AT-6 | Over invented rounds, reads and failures: with a next round known, what is due is what is due today; unknown, only the fixtures differ | R1.4, R1.6, R2.4 |
| AT-7 | From here, on a copy of the owner's lake and collection log: after round 12's deadline the look is due on 22 November at 14:14, not on the 28th; every answer of the copy is identical before and after | R1.1, R1.6 |
| AT-8 | No new dependency; the docs updated | R3 |

## Review (Analyze-Requirements style)

- **Ambiguity:** "unknown" goes by deadlines (glossary), not by matches. A locked round's own matches are ahead for up to
  three days and a postponed one for weeks, so going by matches would look late or not at all. "24 hours" counts from the
  last answered read, whoever made it (a run, an answer or the owner), as the cadence counts today.
- **Conflict:** `mvp-collect` R7.1 reads the fixtures weekly; this amends it, and R3.3 puts the note there when the slice
  lands. `mvp-collect` R1.4, no fresh fact fetched: the next round's fixtures are missing, not fresh, and an answer already
  asks for them at once. More reads against politeness: R2.2 caps them. One earlier integration test changes,
  `test_due_reads_only_the_pages_due`: its only round has been played, and it expects the page left alone a day later.
  With a throwaway version of the rule, run here, no other test of the suite fails because of it.
- **Testability:** every requirement has a test, with nothing for the owner to do. The throwaway rule, on invented rounds
  75½ hours apart (a Saturday, then a Tuesday), stored the second one 51¾ hours before its deadline; today's rule stores
  it after. With a page that moves on only 30 hours after the first deadline it was 27¾ hours, still before the window.
- **Dependencies:** `mvp-collect` (the cadence and the round page), `mvp-fixes` (answered reads and failed tries),
  `mvp-alerts` (the window), `mvp-store` (the log is read 14 days back, further than any cadence).

## Decisions for the owner

1. **How often does the schedule look while it knows no next round?** Recommendation: once a day, 24 hours after the round
   page's last answered read, as it already reads five other pages. Two deadlines are about three days apart at the least
   (a weekend round, then a midweek one), so a round found a day after one leaves about a day before the next one's alert
   window. The alternative, every 12 hours, finds a midweek round half a day sooner for one more read a day; the alerts would
   gain only when the Mac sleeps through most of the day the look is due.
2. **From when, and for how long?** Recommendation: from the round's deadline until the next round is stored, with no
   limit. Waiting for the round's last match instead could find a midweek round too late, since after a Monday-night match
   Tuesday's alert window is already open, and a postponed match would hold the look back for weeks. No limit means one
   read of the page a day through the summer break, about three months, as five other pages already cost. The alternative,
   stopping after round 38, saves those reads for one more rule.
3. **Do the politeness rules and the failed-try rules hold unchanged?** Recommendation: yes, both. A look is one more
   reason to read a page the schedule reads already, so robots.txt, one request a second, once a run, a block that waits
   and a failed try made again at the next run (`mvp-fixes` R1) all cover it. The alternative, a failed look that waits a
   day, saves at most four requests an hour while the site is down and can cost a day of a round's news.
