"""Inputs summary state/cache coordination."""

from __future__ import annotations

import copy
from typing import Any, Callable


def render_inputs_summary_state_cache(
    *,
    ss: dict,
    mark: Callable[[str], None],
    resolved_inputs_summary_state_fn: Callable[[], tuple[dict, dict]],
    resolve_design_actions_fn: Callable[[dict], dict],
    design_guide_fp_fn: Callable[[dict], Any],
    hc_try_fn: Callable[[str, Callable[[], Any]], Any],
    build_bending_pack_fn: Callable[[dict], Any],
    build_shear_pack_fn: Callable[[dict], Any],
    build_crack_pack_fn: Callable[[dict], Any],
    build_deflection_pack_fn: Callable[[dict], Any],
    authoritative_packs: dict[str, Any] | None = None,
):
    summary_state, summary_state_debug = resolved_inputs_summary_state_fn()
    summary_state_debug = {
        **dict(summary_state_debug),
        "final_shear_truth_normalized_source": ss.get("_final_shear_truth_normalized_source"),
        "final_shear_truth_normalized_latest": dict(ss.get("_final_shear_truth_normalized_latest") or {}),
        "final_shear_truth_bundle_complete": summary_state.get("final_shear_truth_bundle_complete"),
        "shear_truth_status": summary_state.get("shear_truth_status"),
        "final_shear_truth_resolved": summary_state.get("final_shear_truth_resolved"),
        "final_shear_truth_failure_reason": summary_state.get("final_shear_truth_failure_reason"),
        "published_result_spacing_mm": summary_state.get("published_result_spacing_mm"),
        "published_result_spacing_meaning": summary_state.get("published_result_spacing_meaning"),
    }
    complete_authoritative_packs = bool(
        isinstance(authoritative_packs, dict)
        and all(
            isinstance(authoritative_packs.get(family), dict)
            for family in ("bending", "shear", "crack", "deflection")
        )
    )
    summary_state_debug["summary_pack_source"] = (
        "authoritative_calculation_packs"
        if complete_authoritative_packs
        else "legacy_summary_rebuild"
    )
    ss["_inputs_summary_debug_bundle"] = dict(summary_state_debug)
    ss["_inputs_summary_consume_audit"] = {
        "summary_state_source": summary_state_debug.get("summary_state_source"),
        "summary_shared_only_mode": summary_state_debug.get("summary_shared_only_mode"),
        "summary_shared_only_reason": summary_state_debug.get("summary_shared_only_reason"),
        "summary_overlay_count": summary_state_debug.get("overlay_count"),
        "summary_shared_vs_widget_diffs": dict(summary_state_debug.get("summary_shared_vs_widget_diffs") or {}),
        "summary_shear": {
            "s_lig": summary_state.get("s_lig"),
            "lig_d": summary_state.get("lig_d"),
            "lig_legs": summary_state.get("lig_legs"),
        },
        "summary_longitudinal": {
            "Ast_bot": summary_state.get("Ast_bot"),
            "d": summary_state.get("d"),
            "bot1_count": summary_state.get("bot1_count"),
            "db_bot_1": summary_state.get("db_bot_1"),
        },
        "summary_shear_truth_bundle": {
            "final_shear_truth_normalized_source": ss.get("_final_shear_truth_normalized_source"),
            "final_shear_truth_normalized_latest": dict(ss.get("_final_shear_truth_normalized_latest") or {}),
            "final_shear_truth_bundle_complete": summary_state.get("final_shear_truth_bundle_complete"),
            "shear_truth_status": summary_state.get("shear_truth_status"),
            "final_shear_truth_resolved": summary_state.get("final_shear_truth_resolved"),
            "final_shear_truth_failure_reason": summary_state.get("final_shear_truth_failure_reason"),
            "published_result_spacing_mm": summary_state.get("published_result_spacing_mm"),
            "published_result_spacing_meaning": summary_state.get("published_result_spacing_meaning"),
        },
        "cache_version": ss.get("_summary_cache_version"),
        "cache_action_fp_present": ss.get("_summary_cache_action_fp") is not None,
        "results_version": int(ss.get("results_version", 0) or 0),
    }
    results_version = int(ss.get("results_version", 0) or 0)
    summary_resolved_actions = resolve_design_actions_fn(summary_state)
    summary_design_guide_fp = design_guide_fp_fn(summary_state)
    summary_resolved_action_fp = (
        summary_resolved_actions.get("Mu_pos"),
        summary_resolved_actions.get("Mu_neg"),
        summary_resolved_actions.get("Vu"),
        summary_resolved_actions.get("SLS_M"),
        summary_resolved_actions.get("SLS_V"),
    )
    summary_action_fp = (
        summary_design_guide_fp,
        summary_resolved_action_fp,
        float(summary_state.get("Mu_star", summary_state.get("uls_Mstar", 0.0)) or 0.0),
        float(summary_state.get("Vu_star", summary_state.get("uls_Vstar", 0.0)) or 0.0),
        float(summary_state.get("Tu_star", 0.0) or 0.0),
        float(summary_state.get("sls_Mstar", 0.0) or 0.0),
        float(summary_state.get("sls_Vstar", 0.0) or 0.0),
        float(summary_state.get("sigma_sr", summary_state.get("sigma_s_sls", 0.0)) or 0.0),
        tuple(
            sorted(
                (
                    str(key),
                    str(value),
                )
                for key, value in dict((summary_state_debug or {}).get("summary_shared_vs_widget_diffs") or {}).items()
            )
        ),
    )
    summary_cache_version = ss.get("_summary_cache_version")
    summary_cache_action_fp = ss.get("_summary_cache_action_fp")
    summary_cache_miss = bool(
        summary_cache_version != results_version or summary_cache_action_fp != summary_action_fp
    )
    if complete_authoritative_packs:
        # The stored engineering result owns the truth. Copy it because the
        # legacy presentation adapter annotates rows for routing and status.
        ss["_bend_pack"] = copy.deepcopy(authoritative_packs["bending"])
        ss["_shear_pack"] = copy.deepcopy(authoritative_packs["shear"])
        ss["_crack_pack"] = copy.deepcopy(authoritative_packs["crack"])
        ss["_defl_pack"] = copy.deepcopy(authoritative_packs["deflection"])
        ss["_summary_cache_version"] = results_version
        ss["_summary_cache_action_fp"] = summary_action_fp
    elif summary_cache_miss:
        ss["_bend_pack"] = hc_try_fn(
            "summary.build_bending_pack", lambda: build_bending_pack_fn(summary_state)
        )
        ss["_shear_pack"] = hc_try_fn(
            "summary.build_shear_pack", lambda: build_shear_pack_fn(summary_state)
        )
        ss["_crack_pack"] = hc_try_fn(
            "summary.build_crack_pack", lambda: build_crack_pack_fn(summary_state)
        )
        ss["_defl_pack"] = hc_try_fn(
            "summary.build_deflection_pack", lambda: build_deflection_pack_fn(summary_state)
        )
        ss["_summary_cache_version"] = results_version
        ss["_summary_cache_action_fp"] = summary_action_fp
    bend_pack = ss.get("_bend_pack")
    shear_pack = ss.get("_shear_pack")
    crack_pack = ss.get("_crack_pack")
    defl_pack = ss.get("_defl_pack")
    mark("summary_packs")
    return summary_state, summary_state_debug, bend_pack, shear_pack, crack_pack, defl_pack


__all__ = ["render_inputs_summary_state_cache"]
