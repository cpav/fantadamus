"""Every starting value the method marks (start), with where it comes from (design C8).

Calibration from the decision log (method §A8) changes this file and nothing else.
"""

from __future__ import annotations

# Availability (R3.2 to R3.4, design C5)
P_START_STARTER = 0.90  # an outlet lists him among the starters
P_START_BENCH = 0.05  # an outlet lists him on the bench, or doesn't mention him
CAMEO_SHARE = 0.5  # p_cameo = 0.5 * (1 - p_start) for an available player
DISPUTED_SPREAD = 0.30  # outlets at least this far apart mark him disputed
