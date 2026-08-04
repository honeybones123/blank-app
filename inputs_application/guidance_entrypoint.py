"""Bridge-independent production entrypoint for Inputs guidance computation."""

from __future__ import annotations

from functools import partial
from typing import Any, Callable

from design_brain.design_guide_controller import (
    build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence,
)
from inputs_application.efficiency_classification import (
    identify_materially_overprovided_non_governing_families,
)
from inputs_application.engineering_predicates import parse_util_value
from inputs_application.geometry_search_policy import (
    design_mode_config,
    design_optimisation_goal,
)
from inputs_application.guidance_runtime_provider import (
    build_guidance_runtime_provider,
)
from inputs_application.guidance_runtime_contracts import (
    GuidanceEntrypointRuntime,
    ServiceabilityPreflightRuntime,
)
from inputs_application.mixed_width_cleanup_promotion import (
    MixedWidthCleanupPromotionRuntime,
    promote_shear_fail_bending_overdesign_width_cleanup,
)
from inputs_application.policy_constants import (
    EFFICIENCY_TARGET_UTIL_MAX,
    EFFICIENCY_TARGET_UTIL_MIN,
)
from inputs_application.serviceability_preflight import (
    serviceability_governs_preflight_payload,
)
from inputs_page_modules.design_overview_adapter import (
    collect_design_overview,
)
from inputs_page_modules.guidance_compute import (
    GuidanceComputeRuntime,
    _application_evaluate_auto_design_candidate,
    _bind_guidance_compute_runtime,
    _overview_required_checks_acceptable,
    build_guidance_compute_runtime,
    compute_design_guidance_items,
)
from inputs_page_modules.recommendation_candidate_adapter import (
    evaluate_full_candidate,
)


def build_guidance_entrypoint_runtime(
    *,
    st_module: Any,
    os_module: Any,
    sys_module: Any,
) -> GuidanceEntrypointRuntime:
    compute_runtime = build_guidance_compute_runtime(
        build_guidance_runtime_provider(st_module)
    )
    collect_overview = partial(
        collect_design_overview,
        session_state=st_module.session_state,
    )
    evaluate_full = partial(
        evaluate_full_candidate,
        session_state=st_module.session_state,
    )
    evaluate_auto_design = partial(
        _application_evaluate_auto_design_candidate,
        evaluate_candidate_full=evaluate_full,
    )
    return GuidanceEntrypointRuntime(
        compute_runtime=compute_runtime,
        st_module=st_module,
        os_module=os_module,
        sys_module=sys_module,
        serviceability_preflight=partial(
            serviceability_governs_preflight_payload,
            runtime=ServiceabilityPreflightRuntime(
                collect_design_overview=collect_overview,
                parse_util_value=parse_util_value,
                build_no_repair_blocker=(
                    build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence
                ),
            ),
        ),
        mixed_width_cleanup_promotion=partial(
            promote_shear_fail_bending_overdesign_width_cleanup,
            runtime=MixedWidthCleanupPromotionRuntime(
                target_util_min=float(EFFICIENCY_TARGET_UTIL_MIN),
                target_util_max=float(EFFICIENCY_TARGET_UTIL_MAX),
                identify_materially_overprovided_families=(
                    identify_materially_overprovided_non_governing_families
                ),
                design_mode_config=design_mode_config,
                design_optimisation_goal=design_optimisation_goal,
                evaluate_auto_design_candidate=evaluate_auto_design,
                overview_required_checks_acceptable=(
                    _overview_required_checks_acceptable
                ),
                parse_util_value=parse_util_value,
            ),
        ),
    )


def compute_inputs_guidance(
    runtime: GuidanceEntrypointRuntime,
    state: dict,
    *,
    guidance_debug_verbose: bool | None = None,
    debug_enabled: bool = False,
    request_kind: str = "design_guide",
) -> dict:
    # Preflight may return without entering ``compute_design_guidance_items``.
    # Bind the frozen runtime first so downstream publication helpers have the
    # same owners available on both the preflight and normal compute routes.
    _bind_guidance_compute_runtime(
        runtime=runtime.compute_runtime,
        st_module=runtime.st_module,
        os_module=runtime.os_module,
        sys_module=runtime.sys_module,
    )
    preflight = run_guidance_preflight(runtime, state)
    if preflight is not None:
        return preflight
    payload = run_guidance_compute(
        runtime,
        state,
        guidance_debug_verbose=guidance_debug_verbose,
        debug_enabled=debug_enabled,
        request_kind=request_kind,
    )
    return run_guidance_postprocess(runtime, payload, state)


def run_guidance_preflight(
    runtime: GuidanceEntrypointRuntime,
    state: dict,
) -> dict | None:
    """Run the serviceability gate before expensive Design Brain computation."""

    return runtime.serviceability_preflight(state)


def run_guidance_compute(
    runtime: GuidanceEntrypointRuntime,
    state: dict,
    *,
    guidance_debug_verbose: bool | None,
    debug_enabled: bool,
    request_kind: str,
) -> dict:
    """Compute guidance items from the already-bound runtime and state snapshot."""

    return compute_design_guidance_items(
        runtime.compute_runtime,
        runtime.st_module,
        runtime.os_module,
        runtime.sys_module,
        state,
        guidance_debug_verbose=guidance_debug_verbose,
        debug_enabled=debug_enabled,
        request_kind=request_kind,
    )


def run_guidance_postprocess(
    runtime: GuidanceEntrypointRuntime,
    payload: dict,
    state: dict,
) -> dict:
    """Apply post-compute guidance promotion without recomputing engineering truth."""

    return runtime.mixed_width_cleanup_promotion(payload, state=state)


__all__ = [
    "GuidanceEntrypointRuntime",
    "build_guidance_entrypoint_runtime",
    "compute_inputs_guidance",
    "run_guidance_compute",
    "run_guidance_postprocess",
    "run_guidance_preflight",
]
