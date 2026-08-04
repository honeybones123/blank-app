"""Application-owned publication-truth gates for shear recommendations."""

from __future__ import annotations

from typing import Any, Mapping

from inputs_application.state_utils import guidance_state_snapshot
from inputs_application.shear_truth_overlay import (
    build_normalized_shear_truth_overlay,
)
from state_and_helpers import normalize_final_published_shear_truth


CURRENT_SHEAR_TRUTH_SESSION_KEYS: tuple[str, ...] = (
    "shear_design_status",
    "shear_envelope_status",
    "shear_truth_status",
    "shear_truth_reason",
    "shear_truth_util_governing",
    "shear_truth_web_util_governing",
    "shear_truth_util_source",
    "shear_truth_web_util_source",
    "shear_truth_governing_check_name",
    "shear_truth_governing_reason",
    "shear_truth_governing_source",
    "shear_util_governing",
    "shear_util_min",
    "final_shear_status_source",
    "final_shear_truth_resolved",
    "final_shear_truth_failure_reason",
    "final_shear_spacing_reason",
    "final_shear_publication_path",
    "final_shear_truth_bundle_complete",
    "shear_required_spacing_mm",
    "shear_effective_spacing_mm",
    "shear_governing_spacing_source",
    "published_result_spacing_mm",
    "published_result_spacing_meaning",
    "shear_provided_input_spacing_mm",
    "shear_input_spacing_mm",
    "shear_sectional_check_spacing_mm",
    "V_eq_kN",
    "Vu_star",
    "uls_Vstar",
    "load_Vstar_proxy",
    "shear_Vu_total_kN",
    "phi_Vu_cap",
    "phi_Vu_max_kN",
    "phiVu_max",
    "phi_vu_max",
)


def current_normalized_shear_truth(
    state: Mapping[str, Any] | None,
    *,
    session_state: Mapping[str, Any],
) -> dict[str, Any]:
    merged = guidance_state_snapshot(state)
    for key in CURRENT_SHEAR_TRUTH_SESSION_KEYS:
        if key in session_state:
            merged[key] = session_state.get(key)
    merged.update(normalize_final_published_shear_truth(merged))
    return merged


def overlay_current_normalized_shear_truth(
    state: Mapping[str, Any] | None,
    *,
    session_state: Mapping[str, Any],
) -> dict[str, Any]:
    """Overlay live publication truth while preserving the exact base snapshot."""
    base_state = dict(state or {})
    session_overlay = {
        key: session_state.get(key)
        for key in CURRENT_SHEAR_TRUTH_SESSION_KEYS
        if key in session_state
    }
    normalized_overlay = normalize_final_published_shear_truth(
        {**base_state, **session_overlay}
    )
    snapshot = build_normalized_shear_truth_overlay(
        base_state=base_state,
        session_shear_truth_values=session_overlay,
        normalized_shear_truth_values=normalized_overlay,
    )
    return dict(snapshot.merged_state)


def combined_underdesign_shear_truth_gate(
    working_state: dict,
    *,
    overview: dict | None,
    session_state: Mapping[str, Any],
    efficiency_classification: str | None = None,
) -> dict:
    resolved_overview = overview if isinstance(overview, dict) else {}
    resolved_state = overlay_current_normalized_shear_truth(
        guidance_state_snapshot(working_state),
        session_state=session_state,
    )
    truth_resolved = resolved_state.get("final_shear_truth_resolved")
    failure_reason = str(
        resolved_state.get("final_shear_truth_failure_reason") or ""
    ).strip()
    classification = str(efficiency_classification or "").strip().lower()
    if not classification and bool(resolved_overview.get("any_fail")):
        classification = "failing"
    all_key_pass = bool(resolved_overview.get("all_key_pass"))
    combined_condition = classification == "failing" or not all_key_pass
    blocked = bool(combined_condition and truth_resolved is False)
    reason = (
        failure_reason or "final_shear_truth_unresolved"
    ) if blocked else None
    return {
        "combined_underdesign_shear_truth_block_active": blocked,
        "combined_underdesign_shear_truth_block_reason": reason,
        "combined_underdesign_shear_strengthening_suppressed": blocked,
        "combined_underdesign_truth_gate_source": "combined_underdesign_shear_truth_gate",
        "combined_underdesign_truth_gate_classification": classification or None,
        "combined_underdesign_truth_gate_all_key_pass": all_key_pass,
        "combined_underdesign_truth_gate_final_shear_truth_resolved": truth_resolved,
    }


__all__ = [
    "CURRENT_SHEAR_TRUTH_SESSION_KEYS",
    "combined_underdesign_shear_truth_gate",
    "current_normalized_shear_truth",
    "overlay_current_normalized_shear_truth",
]
