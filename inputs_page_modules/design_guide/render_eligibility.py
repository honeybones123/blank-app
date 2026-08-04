"""Design Guide slot render eligibility contract.

This module owns only the page-slot eligibility decision. It does not own
publication, CTA, Apply routing, family selection, or engineering results.
"""

from __future__ import annotations

from typing import Any, Mapping


def _truthy_mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _normalise_active_failures(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = []
    return tuple(str(item or "").strip() for item in values if str(item or "").strip())


def should_render_design_guide_slot_from_publication_eligibility(
    *,
    inputs_has_design_actions_or_loads: bool,
    browser_test_mode: bool = False,
    selected_family_id: Any = None,
    active_failures: Any = None,
    invalid_input_state: bool = False,
    blocker_state: bool = False,
    final_publication: Mapping[str, Any] | None = None,
    debug_bundle: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a trace-backed Design Guide slot eligibility decision."""

    publication = _truthy_mapping(final_publication)
    bundle = _truthy_mapping(debug_bundle)
    cta = _truthy_mapping(publication.get("cta"))
    active_failure_values = _normalise_active_failures(
        active_failures
        or bundle.get("active_failures")
        or bundle.get("active_failure_keys")
    )
    selected_family = str(
        selected_family_id
        or publication.get("selected_family_id")
        or publication.get("published_family_id")
        or cta.get("family")
        or cta.get("family_id")
        or bundle.get("selected_family_id")
        or bundle.get("published_family_id")
        or ""
    ).strip()
    outcome_state = str(
        publication.get("outcome_state")
        or publication.get("status")
        or publication.get("publication_status")
        or ""
    ).strip().upper()
    publication_hash = str(publication.get("publication_hash") or "").strip()
    contract_required_design_brain_eligibility = bool(
        selected_family
        or active_failure_values
        or invalid_input_state
        or blocker_state
        or outcome_state
        or publication_hash
    )
    current_page_gate = bool(browser_test_mode or inputs_has_design_actions_or_loads)
    should_render = bool(current_page_gate or contract_required_design_brain_eligibility)
    if current_page_gate:
        render_eligibility_classification = "A"
        render_eligibility_reason = "page gate allows render"
    elif contract_required_design_brain_eligibility:
        render_eligibility_classification = "C"
        render_eligibility_reason = "page gate blocks render but Design Brain has publication reason"
    else:
        render_eligibility_classification = "B"
        render_eligibility_reason = "page gate blocks render but Design Brain has no publication reason"
    return {
        "schema": "design_guide_render_eligibility_trace.v1",
        "slot_eligibility_adapter_evaluated_trace_only": False,
        "slot_eligibility_adapter_used": True,
        "slot_eligibility_adapter_product_driving": True,
        "trace_only": False,
        "product_behaviour_changed": False,
        "inputs_has_design_actions_or_loads": bool(inputs_has_design_actions_or_loads),
        "browser_test_mode": bool(browser_test_mode),
        "current_page_gate": bool(current_page_gate),
        "contract_required_design_brain_eligibility": bool(contract_required_design_brain_eligibility),
        "selected_family_id": selected_family or None,
        "active_failures": list(active_failure_values),
        "invalid_input_state": bool(invalid_input_state),
        "blocker_state": bool(blocker_state),
        "final_publication_outcome_state": outcome_state or None,
        "final_publication_publication_hash": publication_hash or None,
        "should_render_design_guide_slot": bool(should_render),
        "render_eligibility_reason": render_eligibility_reason,
        "render_eligibility_classification": render_eligibility_classification,
        "classification_legend": {
            "A": "page gate allows render",
            "B": "page gate blocks render but Design Brain has no publication reason",
            "C": "page gate blocks render but Design Brain has publication reason",
            "D": "browser/test state unavailable",
        },
    }


__all__ = ["should_render_design_guide_slot_from_publication_eligibility"]
