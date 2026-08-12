"""Report terminal and triggered Design Brain performance evidence."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from statistics import median
from time import perf_counter

from inputs_v2.application.design_brain_service import DesignBrainService
from inputs_v2.application.design_guide_orchestrator import DesignGuideOrchestrator
from inputs_v2.domain.beam_inputs import (
    ActionInputs,
    BeamInputs,
    LongitudinalReinforcement,
)


def _at_bending_utilisation(utilisation: float) -> BeamInputs:
    baseline = BeamInputs(
        width_mm=300.0,
        depth_mm=500.0,
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=24),
    ).validated()
    result = DesignBrainService()._calculator.calculate_current(baseline).result
    assert result is not None
    capacity = float(result.families["bending"]["phi_Mu_kNm"])
    return replace(
        baseline,
        actions=ActionInputs(bending_moment_knm=utilisation * capacity),
    ).validated()


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * percentile + 0.999999))
    return ordered[index]


def _measure(inputs: BeamInputs, repetitions: int) -> dict[str, object]:
    elapsed: list[float] = []
    last_decision = None
    for _ in range(repetitions):
        started = perf_counter()
        last_decision = DesignGuideOrchestrator().decide(inputs)
        elapsed.append((perf_counter() - started) * 1000.0)
    assert last_decision is not None
    evidence = last_decision.search_evidence
    return {
        "repetitions": repetitions,
        "median_ms": round(median(elapsed), 3),
        "p95_ms": round(_percentile(elapsed, 0.95), 3),
        "worst_ms": round(max(elapsed), 3),
        "generated_candidates": int(
            getattr(evidence, "generated_candidates", evidence.candidates_attempted)
        ),
        "cache_hits": int(evidence.cache_hits),
        "full_evaluations": int(
            getattr(evidence, "full_evaluations", evidence.cache_misses)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="runtime")
    parser.add_argument("--ordinary-runs", type=int, default=31)
    parser.add_argument("--triggered-runs", type=int, default=7)
    args = parser.parse_args()
    report = {
        "label": args.label,
        "ordinary_non_triggered": _measure(
            _at_bending_utilisation(0.90), args.ordinary_runs
        ),
        "triggered_fast": _measure(
            _at_bending_utilisation(0.40), args.triggered_runs
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
