"""Canonical optimisation configuration shared by app and verifiers."""

from __future__ import annotations


TARGET_UTILISATION_BAND = {
    "balanced": {
        "low": 0.88,
        "high": 0.95,
    },
}


def get_target_utilisation_band(goal: str = "balanced") -> tuple[float, float]:
    band = TARGET_UTILISATION_BAND.get(goal) or TARGET_UTILISATION_BAND["balanced"]
    return float(band["low"]), float(band["high"])


def target_band_payload(goal: str = "balanced") -> dict[str, object]:
    low, high = get_target_utilisation_band(goal)
    return {
        "goal": goal or "balanced",
        "target_low": low,
        "target_high": high,
        "source": "canonical_config",
    }
