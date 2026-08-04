from __future__ import annotations

import math


def derive_concrete_modulus_from_fc(fc_mpa: float) -> float:
    """
    Canonical concrete elastic modulus used by this app.
    Uses the existing project convention Ec = 4700 * sqrt(fc) (MPa).
    """
    fc_safe = max(0.0, float(fc_mpa or 0.0))
    return float(4700.0 * math.sqrt(fc_safe))
