"""SHEAR_FAIL_GOVERNS active-repair preview evidence boundary.

This module owns the shear-family decision/evidence shape for the active-shear
repair preview that the page still evaluates through its shared evaluator.
It deliberately has no page, Streamlit, CTA rendering, apply routing, or UI
imports.
"""

from __future__ import annotations

from typing import Any

from design_brain.shear_candidate_evaluation import stable_shear_candidate_hash


FAMILY_ID = "SHEAR_FAIL_GOVERNS"
ACTIVE_REPAIR_PREVIEW_SOURCE = "shear_fail_governs_active_repair_preview_boundary"


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def build_shear_fail_active_repair_preview_evidence(
    *,
    updates: dict[str, Any] | None,
    current_shear_utilisation: float | None,
    preview_shear_utilisation: float | None,
    any_fail: bool,
    required_checks_acceptable: bool,
    explicit_preview_failures: bool,
    target_band_eps: float = 0.0,
) -> dict[str, Any]:
    """Return family-owned active-shear repair preview evidence/effects."""

    update_payload = dict(updates or {})
    current_util = _as_float(current_shear_utilisation)
    preview_util = _as_float(preview_shear_utilisation)
    utilisation_improved = bool(
        current_util is not None
        and preview_util is not None
        and preview_util < current_util - float(target_band_eps or 0.0)
    )
    applies = bool(
        update_payload
        and utilisation_improved
        and not bool(any_fail)
        and bool(required_checks_acceptable)
        and not bool(explicit_preview_failures)
    )
    update_hash = stable_shear_candidate_hash(update_payload)
    proof = {
        "family_id": FAMILY_ID,
        "source": ACTIVE_REPAIR_PREVIEW_SOURCE,
        "update_hash": update_hash,
        "current_shear_utilisation": current_util,
        "preview_shear_utilisation": preview_util,
        "utilisation_improved": utilisation_improved,
        "preview_pass": applies,
        "required_checks_acceptable": bool(required_checks_acceptable),
        "no_explicit_preview_failures": not bool(explicit_preview_failures),
        "any_fail": bool(any_fail),
    }
    if not applies:
        return {
            **proof,
            "applies": False,
            "effect_hash": stable_shear_candidate_hash({"applies": False, "proof": proof}),
        }

    effects = {
        "button_contract_effect": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "updates": dict(update_payload),
            "preview_pass": True,
            "expected_util": float(preview_util),
            "blocking_reason": None,
        },
        "item_effect": {
            "family": "shear",
            "check_key": "shear",
            "selected_action_family": "shear",
            "expected_util": float(preview_util),
            "candidate_post_util": float(preview_util),
            "displayed_util": float(preview_util),
        },
        "display_truth_effect": {
            "display_truth_source": "candidate_preview",
            "displayed_util": float(preview_util),
            "displayed_status": "PASS",
            "source_candidate_util": float(preview_util),
            "source_summary_util": float(current_util),
        },
        "candidate_search_evidence_effect": {
            "family": "shear",
            "primary_action_family": "shear",
            "selected_candidate_util": float(preview_util),
            "candidate_post_util": float(preview_util),
            "selected_candidate_updates": dict(update_payload),
            "active_repair_preview_source": ACTIVE_REPAIR_PREVIEW_SOURCE,
            "active_repair_preview_update_hash": update_hash,
        },
        "debug_stamp_effect": {
            "final_binding_active_shear_repair_restamped": True,
            "final_binding_active_shear_repair_expected_util": float(preview_util),
            "final_binding_active_shear_repair_current_util": float(current_util),
            "final_binding_active_shear_repair_family_owned": True,
            "final_binding_active_shear_repair_proof_source": ACTIVE_REPAIR_PREVIEW_SOURCE,
        },
    }
    return {
        **proof,
        "applies": True,
        "effects": effects,
        "effect_hash": stable_shear_candidate_hash(effects),
    }


__all__ = [
    "ACTIVE_REPAIR_PREVIEW_SOURCE",
    "FAMILY_ID",
    "build_shear_fail_active_repair_preview_evidence",
]
