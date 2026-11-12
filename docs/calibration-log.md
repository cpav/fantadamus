# Calibration log

Each change to a starting value in `engine/constants.py`, from a `fantadamus recalibrate` proposal the owner
approved (mvp-recalibrate R8). Newest first. Aggregates only: no player, club or league is named. A change is
undone the same way: a later proposal, approved, and an entry here.

## 2026-11-12: rounds 10 and 11

Approved by the owner on 2026-11-12, from the proposal on rounds 10 and 11, run from stored facts only.

| Value | Old | New | Evidence | Where it wasn't fitted |
|---|---|---|---|---|
| `START_MAP` | the identity | 0.007 to 0.015, 0.169 to 0.063, 0.249 to 0.085, 0.326 to 0.196, 0.440 to 0.376, 0.553 to 0.594, 0.647 to 0.619, 0.747 to 0.739, 0.856 to 0.827, 0.913 to 0.925 | 1,033 players whose start is known, over two rounds; the knots rounded to three decimals | round 10: Brier 0.117 to 0.116, reliability gap 0.069 to 0.048; round 11: Brier 0.104 to 0.099, reliability gap 0.089 to 0.064 |
| `YELLOW_PRIOR` | 0.150 | 0.116 | 310 yellow cards in 2,682 outfield appearances, in the statistics read made with the table on 2026-11-04; 90% between 0.106 and 0.126 | a count, not a forecast |

The outlets overstated the chances between about 10% and 40%: a quarter-chance started about one time in eleven.
At the top they were right.

### What it moves

On round 11's stored facts, at its lock:

- **A lineup:** the owner's keeps its formation and captain; one starter changes, and the bench order with
  it. The expected score rises by about a tenth of a point, and each threshold's chance by under a point.
- **The cards:** 299 players' chances of starting move by 0.03 on average and by 0.16 at most. None crosses
  50%, so no likely eleven and no disputed place changes; three of the ten cards reorder their likeliest
  scorers. The match numbers don't move.
- **The answers' shape** stays the same.

### Not changed

- `CAMEO_SHARE`: fitted at 0.248, but on 183 of the 200 players it needs. Held out on half of round 11's
  matches, it lowers the Brier score from 0.136 to 0.120 and from 0.138 to 0.116. It waits for round 12.
- `CAMEO_RATED`: not fitted. Benched attackers got a rating about twice as often as benched defenders and
  midfielders, more than one share allows: one share doesn't fit both kinds of cameo.
- `PENALTY_RATE` (0.110) and `PENALTY_CONVERSION` (0.636): 22 of the 30 penalties they need.
- `PENALTY_SAVED_SHARE` and `RED_RATE`: the stored statistics reads don't count them yet.
- The rest waits, with the evidence each needs, as `fantadamus recalibrate` lists it.
