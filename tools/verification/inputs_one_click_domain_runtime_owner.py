"""Prove permanent one-click domain scoring helpers preserve exact parity."""

from __future__ import annotations

import contextlib
from copy import deepcopy
import io
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_application.guidance_entrypoint import (
            build_guidance_entrypoint_runtime,
        )
        from inputs_application.one_click_runtime_provider import (
            build_partial_one_click_runtime_provider,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    guidance = build_guidance_entrypoint_runtime(
        st_module=bridge.st,
        os_module=os,
        sys_module=sys,
    )
    provider = build_partial_one_click_runtime_provider(
        st_module=bridge.st,
        guidance_runtime=guidance,
    )
    recipe = find_named_case("R3A_M300_V400")
    assert recipe is not None
    state = build_state(recipe["changes"])
    mode_config = bridge._design_mode_config("balanced")
    current = bridge._evaluate_auto_design_candidate(
        deepcopy(state),
        source="one_click_domain_runtime_current",
    )
    candidate = bridge._evaluate_auto_design_candidate(
        deepcopy(state),
        updates={"D": float(state["D"]) + 50.0},
        source="one_click_domain_runtime_candidate",
    )
    assert isinstance(current, dict)
    assert isinstance(candidate, dict)

    unary = (
        "_one_click_domain_total_distance",
        "_one_click_domain_max_distance",
        "_one_click_required_domain_progress",
        "_one_click_required_domains_satisfied",
    )
    checked = 0
    for name in unary:
        owned = getattr(provider, name)(
            deepcopy(current),
            deepcopy(mode_config),
        )
        compatibility = getattr(bridge, name)(
            deepcopy(current),
            deepcopy(mode_config),
        )
        assert owned == compatibility, (name, owned, compatibility)
        checked += 1

    for domain in ("bending", "shear"):
        owned = provider._one_click_domain_needs_cleanup(
            deepcopy(current),
            domain,
            deepcopy(mode_config),
        )
        compatibility = bridge._one_click_domain_needs_cleanup(
            deepcopy(current),
            domain,
            deepcopy(mode_config),
        )
        assert owned == compatibility, (domain, owned, compatibility)
        checked += 1

    owned = provider._one_click_step_improves(
        deepcopy(candidate),
        deepcopy(current),
        deepcopy(mode_config),
    )
    compatibility = bridge._one_click_step_improves(
        deepcopy(candidate),
        deepcopy(current),
        deepcopy(mode_config),
    )
    assert owned == compatibility, (owned, compatibility)
    checked += 1

    for name, args in (
        (
            "_candidate_in_target_band",
            (deepcopy(current), deepcopy(mode_config)),
        ),
        ("_candidate_state_signature", (deepcopy(current),)),
        ("_rescue_mode_default_debug", ()),
        ("_rescue_mode_seed_order", ("medium",)),
        (
            "_rescue_mode_path_improved",
            (
                deepcopy(candidate),
                deepcopy(current),
                deepcopy(mode_config),
            ),
        ),
        (
            "_one_click_strict_target_band_ok",
            (
                deepcopy(current.get("overview") or {}),
                deepcopy(mode_config),
            ),
        ),
        (
            "_candidate_target_domains_for_band",
            (
                {
                    **deepcopy(current),
                    "target_domains_for_band": [
                        "flexure",
                        "shear",
                        "bending",
                    ],
                },
            ),
        ),
        (
            "_one_click_target_domains_for_eval",
            (["bending"], {"lig_d": 12}),
        ),
        (
            "_candidate_objective_util",
            (deepcopy(current),),
        ),
        (
            "_candidate_target_band_distance",
            (deepcopy(current), deepcopy(mode_config)),
        ),
        (
            "is_valid_progress_while_failing",
            (deepcopy(candidate), deepcopy(current)),
        ),
        (
            "_build_recommendation_envelope",
            (),
        ),
        (
            "_requires_full_coverage_for_primary_one_click",
            (deepcopy(current.get("overview") or {}),),
        ),
        (
            "_design_guide_candidate_family",
            ({"action_type": "apply_geometry_recommendation"},),
        ),
        (
            "_governing_focus_from_overview",
            (deepcopy(current.get("overview") or {}),),
        ),
        (
            "_current_design_guide_fail_fingerprint",
            (deepcopy(current.get("overview") or {}),),
        ),
        (
            "_candidate_failure_coverage_summary",
            (deepcopy(state), deepcopy(candidate)),
        ),
        (
            "_build_canonical_design_state_pack",
            (deepcopy(state),),
        ),
        (
            "_trace_compact_overview_dict",
            (deepcopy(current.get("overview") or {}),),
        ),
        (
            "_trace_compact_shared_geom_reo",
            (deepcopy(state),),
        ),
        (
            "_normalise_invalid_shear_state_updates",
            (
                {
                    **deepcopy(state),
                    "lig_legs": 2,
                    "lig_d": 0,
                    "s_lig": 0.0,
                },
                {},
            ),
        ),
        (
            "_one_click_seed_target_domains_from_eval",
            (deepcopy(current), deepcopy(mode_config)),
        ),
        (
            "_one_click_tightening_mode_active",
            (deepcopy(current), deepcopy(mode_config)),
        ),
        (
            "_one_click_still_materially_under_target",
            (deepcopy(current), deepcopy(mode_config)),
        ),
        (
            "_one_click_trace_eval_domain_payload",
            (deepcopy(current), deepcopy(mode_config)),
        ),
        (
            "_one_click_mixed_direction_rank_adjustment",
            (
                deepcopy(current),
                deepcopy(candidate),
                "bending_under_shear_over",
                deepcopy(mode_config),
            ),
        ),
        (
            "_one_click_candidate_is_shear_governing_for_prune",
            (),
        ),
        (
            "_rescue_mode_eval_for_result",
            ({"final_state_preview": deepcopy(state)},),
        ),
        (
            "_shear_preview_for_updates",
            (
                deepcopy(state),
                {"lig_d": 12, "lig_legs": 2, "s_lig": 175.0},
            ),
        ),
        (
            "_stage3_final_published_shear_truth_bundle",
            (
                {
                    **deepcopy(state),
                    "shear_truth_status": "PASS",
                    "final_shear_truth_resolved": True,
                },
            ),
        ),
        (
            "_one_click_mixed_direction_classification",
            (deepcopy(current), deepcopy(mode_config)),
        ),
        (
            "_one_click_update_direction_summary",
            (
                deepcopy(state),
                {"D": float(state["D"]) + 50.0},
            ),
        ),
        (
            "_one_click_attach_eval_target_domains",
            (),
        ),
        (
            "_one_click_committable_candidate_eval",
            (),
        ),
        (
            "_rescue_mode_validate_seed",
            (
                deepcopy(state),
                {"D": float(state["D"]) + 50.0},
            ),
        ),
        (
            "_one_click_build_user_visible_no_action_fields",
            (
                "no_actionable_candidates",
                {
                    "governing_domain": "shear",
                    "rejected_as_spacing_too_weak": 2,
                },
            ),
        ),
        (
            "_one_click_in_band_shear_cleanup_candidate_allowed",
            (
                deepcopy(current),
                deepcopy(candidate),
                {"s_lig": 175.0},
                deepcopy(mode_config),
            ),
        ),
        (
            "_rescue_mode_should_enter",
            (),
        ),
        (
            "_one_click_collect_actionable_guidance_candidates",
            (),
        ),
        (
            "_one_click_in_band_shear_cleanup_deferral",
            (
                deepcopy(state),
                deepcopy(current),
                deepcopy(mode_config),
            ),
        ),
        (
            "_sanitize_shared_update_bundle",
            (
                {
                    "D": 550.0,
                    "_private": "drop",
                    "not_shared": "drop",
                },
            ),
        ),
        (
            "_one_click_has_unresolved_spacing_envelope_fail",
            (
                {
                    "overview": {
                        "packs": {
                            "shear": {
                                "summary_governing_source": (
                                    "spacing_envelope"
                                ),
                                "summary_governing_status": "FAIL",
                            }
                        }
                    }
                },
            ),
        ),
        (
            "_one_click_directional_tie_key",
            (0.5, 0.6, deepcopy(mode_config)),
        ),
        (
            "_one_click_exhaustion_next_hop_allowed",
            (
                deepcopy(current),
                {"candidate": deepcopy(candidate)},
                deepcopy(mode_config),
            ),
        ),
        (
            "_stage3_remaining_issue_class_from_overview_state",
            (
                {
                    "shear_design_status": "INVALID",
                    "final_shear_truth_resolved": False,
                },
                {"statuses": {"shear": "PASS"}},
            ),
        ),
    ):
        if name == "_build_recommendation_envelope":
            kwargs = {
                "updates": {"D": 500.0},
                "source": "parity",
                "required_domains": "bending",
            }
            owned = getattr(provider, name)(**kwargs)
            compatibility = getattr(bridge, name)(**kwargs)
        elif name == "_sanitize_shared_update_bundle":
            owned = getattr(provider, name)(
                *args,
                source="parity",
            )
            compatibility = getattr(bridge, name)(
                *args,
                source="parity",
            )
        elif name == "_normalise_invalid_shear_state_updates":
            owned = getattr(provider, name)(
                *args,
                source="parity",
            )
            compatibility = getattr(bridge, name)(
                *args,
                source="parity",
            )
        elif name == "_one_click_candidate_is_shear_governing_for_prune":
            kwargs = {
                "family_hint": "shear_spacing",
                "norm_updates": {"s_lig": 175.0},
            }
            owned = getattr(provider, name)(**kwargs)
            compatibility = getattr(bridge, name)(**kwargs)
        elif name == "_one_click_attach_eval_target_domains":
            owned_eval = deepcopy(current)
            compatibility_eval = deepcopy(current)
            getattr(provider, name)(
                owned_eval,
                ["bending", "shear"],
                deepcopy(mode_config),
            )
            getattr(bridge, name)(
                compatibility_eval,
                ["bending", "shear"],
                deepcopy(mode_config),
            )
            owned = owned_eval
            compatibility = compatibility_eval
        elif name == "_one_click_committable_candidate_eval":
            kwargs = {
                "source": "committable_parity",
                "label": "Increase depth",
                "action_type": "increase_depth",
            }
            owned = getattr(provider, name)(
                deepcopy(state),
                {"D": float(state["D"]) + 50.0},
                **kwargs,
            )
            compatibility = getattr(bridge, name)(
                deepcopy(state),
                {"D": float(state["D"]) + 50.0},
                **kwargs,
            )
        elif name == "_rescue_mode_should_enter":
            kwargs = {
                "state": deepcopy(state),
                "init_eval": deepcopy(current),
                "final_eval": deepcopy(candidate),
                "final_pass": False,
                "final_updates": {},
                "stop_reason": "no_actionable_candidates",
                "mode_config": deepcopy(mode_config),
            }
            owned = getattr(provider, name)(**deepcopy(kwargs))
            compatibility = getattr(bridge, name)(**deepcopy(kwargs))
        elif name == "_one_click_collect_actionable_guidance_candidates":
            kwargs = {
                "debug_enabled": False,
                "trace_run_id": None,
                "trace_step": 1,
            }
            owned = getattr(provider, name)(
                deepcopy(state),
                **kwargs,
            )
            compatibility = getattr(bridge, name)(
                deepcopy(state),
                **kwargs,
            )
        else:
            owned = getattr(provider, name)(*args)
            compatibility = getattr(bridge, name)(*args)
        assert owned == compatibility, (name, owned, compatibility)
        checked += 1

    rescue_kwargs = {
        "solve": {
            "one_click_solver_debug": {
                "rescue_mode_entered": True,
                "rescue_mode_effective_seed_found": True,
            }
        },
        "current_fail_keys": ["bending", "shear"],
        "candidate_for_commit": {"state": deepcopy(state)},
        "candidate_commit_meta": {
            "reason": "candidate_preview_has_fail_status",
            "covered_fail_keys": ["bending"],
            "remaining_fail_keys": ["shear"],
        },
        "solver_final_updates": {"D": float(state["D"]) + 50.0},
        "seed_eval": deepcopy(current),
    }
    owned_rescue = provider._rescue_bootstrap_partial_commit_allowed(
        **deepcopy(rescue_kwargs)
    )
    compatibility_rescue = bridge._rescue_bootstrap_partial_commit_allowed(
        **deepcopy(rescue_kwargs)
    )
    assert owned_rescue == compatibility_rescue
    checked += 1

    audit = {
        "post_commit_matches_intended_updates": True,
        "post_commit_live_worst_util": 0.95,
        "post_commit_live_statuses": {
            "bending": "PASS",
            "shear": "PASS",
        },
    }
    owned_audit = provider._one_click_commit_audit_passes(deepcopy(audit))
    compatibility_audit = bridge._one_click_commit_audit_passes(
        deepcopy(audit)
    )
    assert owned_audit == compatibility_audit
    checked += 1

    trace_kwargs = {
        "run_id": "parity-run",
        "action_signature": "increase_depth",
        "goal": "balanced",
        "starting_worst_util": 1.1,
        "ending_worst_util": 0.95,
        "stop_reason": "target_band",
        "winner_label": "Increase depth",
        "final_updates": {"D": 550.0},
    }
    owned_trace = provider._design_guide_trace_compare_meta(
        **deepcopy(trace_kwargs)
    )
    compatibility_trace = bridge._design_guide_trace_compare_meta(
        **deepcopy(trace_kwargs)
    )
    assert owned_trace == compatibility_trace
    checked += 1

    owned_efficiency = provider.compute_efficiency_tightening_state(
        deepcopy(state)
    )
    compatibility_efficiency = bridge.compute_efficiency_tightening_state(
        deepcopy(state)
    )
    assert owned_efficiency == compatibility_efficiency
    checked += 1

    evaluate_kwargs = {
        "updates": {"D": float(state["D"]) + 50.0},
        "source": "one_click_owned_evaluation_parity",
        "label": "Candidate",
        "action_type": "increase_depth",
    }
    owned_evaluation = provider._evaluate_auto_design_candidate(
        deepcopy(state),
        **deepcopy(evaluate_kwargs),
    )
    compatibility_evaluation = bridge._evaluate_auto_design_candidate(
        deepcopy(state),
        **deepcopy(evaluate_kwargs),
    )
    assert owned_evaluation == compatibility_evaluation
    checked += 1

    assert provider.RESCUE_SEED_LIBRARY == bridge.RESCUE_SEED_LIBRARY
    checked += 1

    print(
        "PASS: permanent one-click domain helpers have exact "
        f"{checked}/58 scoring, rescue, envelope, evaluation, commit, tracing, and progress parity"
    )


if __name__ == "__main__":
    main()
