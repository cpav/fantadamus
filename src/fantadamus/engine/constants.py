"""Every starting value the method marks (start), with where it comes from (design C8).

Calibration from the decision log (method §A8) changes this file and nothing else.
"""

from __future__ import annotations

# Availability (R3.2 to R3.4, design C5)
P_START_STARTER = 0.90  # an outlet lists him among the starters
P_START_BENCH = 0.05  # an outlet lists him on the bench, or doesn't mention him
CAMEO_SHARE = 0.5  # p_cameo = 0.5 * (1 - p_start) for an available player
DISPUTED_SPREAD = 0.30  # outlets at least this far apart mark him disputed

# Many sources, compared (mvp-collect R5.3, design C12)
ODDS_DISPUTED_SPREAD = 0.10  # odds pages' de-margined 1X2 at least this far apart are disputed

# Team xG from the betting lines (R5.2, R5.3, method §A4 and §A5, design C7)
DIXON_COLES_RHO = -0.10  # the low-score correction; negative adds 0-0 and 1-1 draws
MAX_GOALS = 10  # a team's goals counted up to this in the 1X2
XG_RANGE = (0.20, 4.00)  # the team xG searched
TEAM_FORM_WEIGHT = 12  # regressed team form weighs n / (n + 12) matches, without odds

# The forward model (R9, method §A4)
VOTE_BASELINE = 6.0  # a forward's expected vote before his own ratings count
VOTE_WEIGHT = 10  # k_vote: his average counts n / (n + 10) of rated appearances
FIXTURE_EFFECT = 0.3  # the vote moves 0.3 x (P(win) - P(loss))
SHARE_WEIGHT = 15  # W: shares shrink toward the prior with the weight of 15 team goals
GOAL_SHARE_PRIOR = {"Pc": 0.30, "A": 0.20, "W": 0.15}  # by Mantra role
GOAL_SHARE_PRIOR_UNKNOWN = 0.20  # any other or no Mantra role
ASSIST_SHARE_PRIOR = 0.11  # attackers
MINUTES_START = 0.85  # a forward's minutes share if he starts
MINUTES_CAMEO = 0.28  # and if he comes on
PENALTY_RATE = 0.15  # P(his team gets a penalty) per match
PENALTY_CONVERSION = 0.78
YELLOW_PRIOR = 0.15  # yellow cards per appearance, before his own count
YELLOW_WEIGHT = 10  # appearances' weight of that prior
CAMEO_GOAL_VALUE = 9.8  # a cameo with a goal
CAMEO_RATED = 0.6  # a cameo without a goal gets a rating this often
CAMEO_RATING = 5.75  # and is worth this

# The answer (R10.2, method §A7)
COIN_FLIP = 0.15  # a margin below this is a coin flip
CLEAR = 0.5  # above this, clear; in between, a lean

# Freshness (R7.3): how long a fact counts, and the tighter target within a day of the match
FRESH_FOR_HOURS = {
    "probable_lineups": 12,
    "match_odds": 24,
    "player_season": 7 * 24,
    "team_season": 7 * 24,
    "penalty_takers": 7 * 24,
    "fixtures": 7 * 24,
}
FRESH_NEAR_MATCH_HOURS = {"probable_lineups": 3, "match_odds": 6}
NEAR_MATCH_HOURS = 24
