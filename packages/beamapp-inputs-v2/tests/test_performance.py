from statistics import median
from time import perf_counter

from inputs_v2.application.input_commands import UpdateFirstSlice, apply_input_command
from dataclasses import replace

from inputs_v2.application.design_brain_service import DesignBrainService
from inputs_v2.application.design_brain.search_profile import SearchProfile
from inputs_v2.application.design_guide_orchestrator import DesignGuideOrchestrator
from inputs_v2.domain.beam_inputs import ActionInputs, BeamInputs, LayoutMode, LongitudinalReinforcement
from inputs_v2.presentation.view_models.input_diagram import build_input_diagram_view_model


def test_command_and_diagram_hot_path_is_sub_second_in_process() -> None:
    current = BeamInputs()
    started = perf_counter()
    for bars in (6, 7, 8, 9, 10):
        current = apply_input_command(current, UpdateFirstSlice(400, 600, LayoutMode.COUNT, bars, 150, 20, 40))
        view = build_input_diagram_view_model(current)
        assert view.source_revision == current.revision
    elapsed_ms = (perf_counter() - started) * 1000
    assert elapsed_ms < 750, f"hot path took {elapsed_ms:.1f} ms"


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


def test_already_balanced_design_has_no_search_runtime_regression() -> None:
    current = _at_bending_utilisation(0.90)
    started = perf_counter()

    decision = DesignGuideOrchestrator().decide(current)

    elapsed_ms = (perf_counter() - started) * 1000.0
    assert decision.search_evidence.candidates_attempted == 0
    assert decision.search_evidence.cache_misses == 0
    assert decision.search_evidence.elapsed_ms >= 0.0
    assert elapsed_ms < 100.0, f"balanced terminal path took {elapsed_ms:.1f} ms"


def test_triggered_fast_search_reports_bounded_work_and_elapsed_time() -> None:
    current = _at_bending_utilisation(0.40)
    timings_ms: list[float] = []
    decisions = []
    for _sample in range(3):
        started = perf_counter()
        decisions.append(DesignGuideOrchestrator().decide(current))
        timings_ms.append((perf_counter() - started) * 1000.0)

    for decision in decisions:
        assert 0 < decision.search_evidence.candidates_attempted <= 2500
        assert decision.search_evidence.cache_misses <= 2500
        assert decision.search_evidence.elapsed_ms > 0.0
    # GitHub-hosted Linux runners are materially slower than the local
    # developer/runtime environment for this Python equilibrium workload. The
    # search itself remains bounded by the candidate and cache-miss assertions
    # above; this wall-clock guard only accounts for runner variance.
    # Use the same deterministic guard locally and in CI. Developer machines
    # commonly have one or more live Streamlit verification servers running;
    # a tighter local-only threshold made the suite sensitive to unrelated
    # host contention rather than candidate expansion. Comparative 5% median,
    # p95 and worst-case regression reporting remains a separate release gate.
    median_limit_ms = 1250.0
    worst_limit_ms = 2000.0
    measured_median_ms = median(timings_ms)
    measured_worst_ms = max(timings_ms)
    assert measured_median_ms < median_limit_ms, (
        f"triggered Fast search median was {measured_median_ms:.1f} ms "
        f"(limit {median_limit_ms:.1f} ms; samples={timings_ms!r})"
    )
    assert measured_worst_ms < worst_limit_ms, (
        f"triggered Fast search worst case was {measured_worst_ms:.1f} ms "
        f"(limit {worst_limit_ms:.1f} ms; samples={timings_ms!r})"
    )


def test_configured_consecutive_infeasible_limit_records_safe_capacity_stop() -> None:
    baseline = BeamInputs(
        width_mm=500.0,
        depth_mm=600.0,
        bottom=LongitudinalReinforcement(bars=8, diameter_mm=28),
    ).validated()
    result = DesignBrainService()._calculator.calculate_current(baseline).result
    assert result is not None
    capacity = float(result.families["bending"]["phi_Mu_kNm"])
    current = replace(
        baseline,
        actions=ActionInputs(bending_moment_knm=0.40 * capacity),
    ).validated()

    decision = DesignGuideOrchestrator(
        SearchProfile(max_consecutive_infeasible=2)
    ).decide(current)

    reinforcement_stage = next(
        stage
        for stage in decision.search_evidence.stages
        if stage.stage_id == "reduce_bottom_reinforcement"
    )
    assert reinforcement_stage.stop_reason == "monotonic_bending_capacity_ceiling_proven"
    assert reinforcement_stage.candidates_attempted < 40
    assert decision.apply_allowed
