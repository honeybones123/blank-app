"""Application-owned Design Guide state projection helpers."""

from __future__ import annotations

from typing import Mapping

from inputs_application.action_source_control import (
    authoritative_action_source_projection,
)


_STALE_SOLVER_KEYS = {
    "pending_recommendation", "_solver_result", "_one_click_run_feedback",
    "_bend_pack", "_shear_pack", "_crack_pack", "_defl_pack",
    "_summary_cache_version", "_summary_cache_action_fp",
    "_final_shear_truth_normalized_source", "_final_shear_truth_normalized_latest",
}
_STALE_SHEAR_PUBLICATION_KEYS = {
    "shear_design_status", "shear_envelope_status", "shear_truth_status",
    "shear_truth_reason", "shear_truth_util_governing", "shear_truth_web_util_governing",
    "shear_truth_util_source", "shear_truth_web_util_source",
    "shear_truth_governing_check_name", "shear_truth_governing_reason",
    "shear_truth_governing_source", "shear_util_governing", "shear_util_min",
    "final_shear_status_source", "final_shear_truth_resolved", "final_shear_truth_failure_reason",
    "final_shear_spacing_reason", "final_shear_publication_path", "final_shear_truth_bundle_complete",
    "shear_required_spacing_mm", "shear_effective_spacing_mm", "shear_governing_spacing_source",
    "published_result_spacing_mm", "published_result_spacing_meaning", "shear_provided_input_spacing_mm",
    "shear_input_spacing_mm", "shear_sectional_check_spacing_mm", "V_eq_kN", "shear_Vu_total_kN",
    "phi_Vu_cap", "phi_Vu_max_kN", "phiVu_max", "phi_vu_max", "shear_Vuc_kN", "shear_Vus_kN",
    "shear_k_v", "shear_theta_v_deg", "shear_theta_v_rad",
}
_DESIGN_GUIDE_PROOF_KEYS = {
    "exact_stop_available", "exact_stop_proven", "exact_stop_proof", "locked_no_repair",
    "locked_repair_blocked", "all_repair_paths_locked", "repair_blocked_by_lock",
    "no_valid_repair_available", "repair_required", "reinforcement_lock", "reo_locked",
    "shear_lock", "geometry_lock",
}
_AUTO_DESIGN_GOVERNING_KEYS = (
    "design_optimisation_goal", "optimisation_lock_geometry", "sec_shape", "b", "bw", "tw", "D",
    "fc", "fsy", "Ec", "Es", "phi_bend", "phi_shear", "cover_top", "cover_bot", "cover_side",
    "rowgap_top", "rowgap_bot", "Ast_top", "Tu_star", "P_star", "lig_d", "lig_legs", "s_lig",
    "bot_row_count", "bot1_layout_mode", "bot1_count", "db_bot_1", "bot2_layout_mode", "bot2_count",
    "db_bot_2", "bot_row_1_mode", "bot_row_1_bars", "bot_row_1_spacing", "bot_row_1_dia",
    "bot_row_2_mode", "bot_row_2_bars", "bot_row_2_spacing", "bot_row_2_dia",
)


def build_guidance_state_snapshot(
    state: dict | None = None,
    *,
    result_keys: set[str] | tuple[str, ...],
    shared_defaults: Mapping[str, object],
) -> dict:
    snapshot = dict(state or {})
    proof_values = {key: snapshot.get(key) for key in _DESIGN_GUIDE_PROOF_KEYS if key in snapshot}
    # Load Analysis actions are derived engineering inputs while that source is
    # selected, even though several compatibility aliases still live in the
    # historical RESULT_KEYS registry.  Preserve that committed projection
    # across stale-result cleanup; otherwise the summary/calculation boundary
    # silently falls back to zero manual actions after a page change.
    load_analysis_actions = authoritative_action_source_projection(snapshot)
    for key in set(result_keys) | _STALE_SOLVER_KEYS | _STALE_SHEAR_PUBLICATION_KEYS:
        snapshot.pop(key, None)
    snapshot.update(proof_values)
    snapshot.update(load_analysis_actions)
    for key, default in dict(shared_defaults).items():
        snapshot.setdefault(key, default)
    return snapshot


def build_auto_design_governing_fingerprint(
    state: Mapping[str, object] | None,
    *,
    actions: Mapping[str, object],
) -> tuple:
    source = dict(state or {})
    fingerprint = [(key, str(source.get(key))) for key in _AUTO_DESIGN_GOVERNING_KEYS]
    fingerprint.extend([
        ("resolved_Mu", str(actions.get("Mu"))),
        ("resolved_Vu", str(actions.get("Vu"))),
        ("resolved_Nu", str(actions.get("Nu"))),
        ("resolved_SLS_M", str(actions.get("SLS_M"))),
        ("resolved_SLS_V", str(actions.get("SLS_V"))),
        ("resolved_source", str(actions.get("source"))),
    ])
    return tuple(fingerprint)


__all__ = ["build_auto_design_governing_fingerprint", "build_guidance_state_snapshot"]
