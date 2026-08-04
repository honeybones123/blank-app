"""Typed target-band next-hop refinement for the one-click transaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class OneClickNextHopRuntime:
    target_util_min: float
    target_util_max: float
    fail_status: Any
    max_local_candidates_per_iteration: int
    optimisation_goal_resolver: Callable[..., Any]
    resolve_precheck: Callable[..., dict]
    candidate_target_domains_for_band: Callable[..., list[str]]
    build_auto_design_context: Callable[..., dict]
    generate_smaller_geometry_variants: Callable[..., list[dict]]
    generate_less_bottom_reo_variants: Callable[..., list[dict]]
    generate_less_shear_reo_variants: Callable[..., list[dict]]
    generate_simpler_layout_variants: Callable[..., list[dict]]
    shear_governing_truth_allows_overdesign_cleanup: Callable[..., Any]
    shear_cleanup_possible: Callable[[dict | None], bool]
    make_candidate_key: Callable[[dict], tuple]
    select_best_refinement_candidate: Callable[..., dict | None]
    build_canonical_design_state_pack: Callable[[dict], dict]
    evaluate_candidate_full: Callable[..., dict | None]
    attach_eval_target_domains: Callable[..., dict]
    has_unresolved_spacing_envelope_fail: Callable[[dict | None], bool]


def generate_compliant_refinement_candidates(
    current_candidate: dict,
    mode_config: dict,
    context: dict,
    *,
    runtime: OneClickNextHopRuntime,
) -> list[dict]:
    candidates: dict[tuple, dict] = {}
    generators = (
        (
            runtime.generate_smaller_geometry_variants,
            (current_candidate, mode_config),
        ),
        (
            runtime.generate_less_bottom_reo_variants,
            (current_candidate, mode_config, context),
        ),
    )
    for generator, args in generators:
        for candidate_state in generator(*args):
            candidates[runtime.make_candidate_key(candidate_state)] = (
                candidate_state
            )
    overview = current_candidate.get("overview")
    shear_pack = (
        (((overview or {}) if isinstance(overview, dict) else {})
        .get("packs") or {})
        .get("shear") or {}
    )
    truth_ok, _ = (
        runtime.shear_governing_truth_allows_overdesign_cleanup(
            shear_pack if isinstance(shear_pack, dict) else {}
        )
    )
    if (
        runtime.shear_cleanup_possible(
            dict(current_candidate.get("state") or {})
        )
        and not bool(context.get("disable_shear_cleanup_candidates"))
        and truth_ok
    ):
        for candidate_state in runtime.generate_less_shear_reo_variants(
            current_candidate,
            mode_config,
        ):
            candidates[runtime.make_candidate_key(candidate_state)] = (
                candidate_state
            )
    for candidate_state in runtime.generate_simpler_layout_variants(
        current_candidate,
        mode_config,
        context,
    ):
        candidates[runtime.make_candidate_key(candidate_state)] = (
            candidate_state
        )
    candidates.pop(
        runtime.make_candidate_key(
            current_candidate.get("state") or {}
        ),
        None,
    )
    return list(candidates.values())[
        : max(int(runtime.max_local_candidates_per_iteration), 1)
    ]


def one_click_best_next_hop_improving_candidate(
    current_eval: dict | None,
    mode_config: dict,
    *,
    runtime: OneClickNextHopRuntime,
) -> dict | None:
    precheck = runtime.resolve_precheck(
        current_eval,
        mode_config,
        default_target_min=runtime.target_util_min,
        default_target_max=runtime.target_util_max,
        fail_status=runtime.fail_status,
        optimisation_goal_resolver=runtime.optimisation_goal_resolver,
    )
    if not bool(precheck.get("allowed")):
        return None
    overview = dict(precheck.get("overview") or {})
    current_distance = precheck.get("current_distance")
    current_state = dict(precheck.get("current_state") or {})
    current_target_domains = list(
        runtime.candidate_target_domains_for_band(current_eval) or []
    )
    context = runtime.build_auto_design_context(
        current_state,
        mode_config,
        reference_overview=overview,
    )
    candidate_states = generate_compliant_refinement_candidates(
        current_eval or {},
        mode_config,
        context,
        runtime=runtime,
    )
    return runtime.select_best_refinement_candidate(
        candidate_states=candidate_states,
        current_eval=current_eval,
        current_state=current_state,
        current_distance=current_distance,
        current_target_domains=current_target_domains,
        mode_config=mode_config,
        state_pack_fn=runtime.build_canonical_design_state_pack,
        evaluator_fn=runtime.evaluate_candidate_full,
        target_domain_attachment_fn=runtime.attach_eval_target_domains,
        spacing_envelope_fail_fn=(
            runtime.has_unresolved_spacing_envelope_fail
        ),
        source="one_click_budget_stop_probe",
        label="Budget stop probe",
        action_type="one_click",
        default_target_min=runtime.target_util_min,
        default_target_max=runtime.target_util_max,
        fail_status=runtime.fail_status,
        optimisation_goal_resolver=runtime.optimisation_goal_resolver,
    )


def one_click_budget_stop_has_better_next_hop(
    current_eval: dict | None,
    mode_config: dict,
    *,
    runtime: OneClickNextHopRuntime,
) -> bool:
    return (
        one_click_best_next_hop_improving_candidate(
            current_eval,
            mode_config,
            runtime=runtime,
        )
        is not None
    )


__all__ = [
    "OneClickNextHopRuntime",
    "generate_compliant_refinement_candidates",
    "one_click_best_next_hop_improving_candidate",
    "one_click_budget_stop_has_better_next_hop",
]
