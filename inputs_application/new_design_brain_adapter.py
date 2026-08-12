"""Adapter for the isolated Inputs V2 Design Brain.

This module is the only Runtime boundary that knows how to load the V2
implementation. Pages, stores, jobs, and Apply code receive only the
application-owned ``DesignBrainRequest``/``DesignBrainExecution`` contracts.

Calculation-only consumers use ``v2_engineering_calculation_adapter`` and do
not import this concrete Design Brain boundary.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from application.contracts.design_brain import (
    AuthoritativeDesignResult,
    EngineeringInputSnapshot,
    build_authoritative_design_result,
    stable_authority_hash,
)
from application.design_brain_port import DesignBrainExecution, DesignBrainRequest
from application.v2_source_manifest import source_manifest_hash
from inputs_application.v2_engineering_calculation_adapter import (
    V2_ENGINEERING_CALCULATION_CONTRACT_VERSION,
    _actions_used_projection,
    _beam_inputs_from_snapshot,
    _mapping,
    _resolved_inputs_projection,
    _v2_api as _v2_calculation_api,
    _v2_summary_packs,
)


_REQUIRED_V2_DESIGN_BRAIN_CONTRACT_VERSION = 2


def _require_compatible_v2_design_brain_contract(version: object) -> None:
    if version != _REQUIRED_V2_DESIGN_BRAIN_CONTRACT_VERSION:
        raise RuntimeError(
            "Installed beamapp-inputs-v2 is incompatible with this Runtime "
            f"(Design Brain contract {version!r}; required "
            f"{_REQUIRED_V2_DESIGN_BRAIN_CONTRACT_VERSION}). Reinstall the "
            "Runtime package from packages/beamapp-inputs-v2."
        )


def _v2_api():
    """Extend the calculation facts with the selected Design Brain contracts."""

    api = _v2_calculation_api()
    try:
        from inputs_v2 import (  # noqa: PLC0415
            RUNTIME_DESIGN_BRAIN_CONTRACT_VERSION,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Installed beamapp-inputs-v2 predates the required Runtime Design "
            "Brain contract. Reinstall packages/beamapp-inputs-v2."
        ) from exc
    _require_compatible_v2_design_brain_contract(
        RUNTIME_DESIGN_BRAIN_CONTRACT_VERSION
    )
    from inputs_v2.application.design_guide_orchestrator import (  # noqa: PLC0415
        DesignGuideOrchestrator,
    )
    from inputs_v2.application.engineering_advice import (  # noqa: PLC0415
        EngineeringAdviceResult,
        EngineeringCheck,
        clause_reference,
        effects_for_changes,
        format_engineering_advice,
        verified_changes,
    )
    from inputs_v2.presentation.view_models.design_brain_card import (  # noqa: PLC0415
        build_design_brain_card_view_model,
    )

    api.update(
        {
            "DesignGuideOrchestrator": DesignGuideOrchestrator,
            "clause_reference": clause_reference,
            "EngineeringAdviceResult": EngineeringAdviceResult,
            "EngineeringCheck": EngineeringCheck,
            "effects_for_changes": effects_for_changes,
            "format_engineering_advice": format_engineering_advice,
            "verified_changes": verified_changes,
            "build_design_brain_card_view_model": build_design_brain_card_view_model,
        }
    )
    return api


def _proposal_updates(
    proposal: Any,
    row_counts: tuple[int, ...],
    row_diameters_mm: tuple[float, ...] = (),
) -> dict[str, Any]:
    values = asdict(proposal)
    rows = tuple(row_counts) or (int(values.get("bottom_bars", 0)),)
    diameters = (
        tuple(float(value) for value in row_diameters_mm)
        if len(row_diameters_mm) == len(rows)
        else tuple(float(values.get("bottom_diameter_mm", 0.0)) for _ in rows)
    )
    updates: dict[str, Any] = {
        "b": values.get("width_mm"),
        "D": values.get("depth_mm"),
        "L": values.get("span_mm"),
        "sec_shape": values.get("section_shape"),
        "bot_row_count": len(rows),
        "bot_row_1_bars": rows[0],
        "bot_row_1_spacing": values.get("bottom_spacing_mm"),
        "bot_row_1_dia": diameters[0],
        "cover_bot": values.get("bottom_cover_mm"),
        "top_bars": values.get("top_bars"),
        "top_spacing": values.get("top_spacing_mm"),
        "db_top": values.get("top_diameter_mm"),
        "cover_top": values.get("top_cover_mm"),
        "lig_d": values.get("shear_diameter_mm"),
        "lig_legs": values.get("shear_legs"),
        "s_lig": values.get("shear_spacing_mm"),
    }
    if len(rows) > 1:
        updates.update(
            {
                "bot_row_2_bars": rows[1],
                "bot_row_2_spacing": values.get("bottom_spacing_mm"),
                "bot_row_2_dia": diameters[1],
            }
        )
    return {key: value for key, value in updates.items() if value is not None}



def _calculation_owned_check_metadata(
    calculation: Any,
    check_id: str,
) -> dict[str, Any] | None:
    """Find V2's calculation-owned metadata for one engineering check.

    Clause references must be projected from the calculation result, rather
    than reconstructed in the Runtime adapter.  That keeps the V2 calculation
    the single authority for both the check and its AS 3600 reference.
    """

    for family in getattr(calculation, "families", {}).values():
        if not isinstance(family, Mapping):
            continue
        metadata = family.get("check_metadata", {})
        if not isinstance(metadata, Mapping):
            continue
        reference = metadata.get(check_id)
        if isinstance(reference, Mapping):
            return dict(reference)
    return None


def _clause_metadata(api: Mapping[str, Any], calculation: Any) -> dict[str, Any]:
    checks = (
        "bending_capacity",
        "bending_ductility",
        "shear_strength",
        "short_term_deflection",
        "long_term_deflection",
        "general_crack_control",
        "direct_crack_width",
        "durability_cover",
    )
    references = []
    for check_id in checks:
        reference = api["clause_reference"](
            check_id,
            _calculation_owned_check_metadata(calculation, check_id),
        )
        if reference is not None:
            references.append(asdict(reference))
    return {"standard": "AS 3600", "edition": "2018", "references": references}


def _v2_display_projection(
    *,
    api: Mapping[str, Any],
    current: Any,
    decision: Any,
) -> dict[str, Any]:
    """Serialize V2's own card view model without recreating its decisions."""

    card = api["build_design_brain_card_view_model"](decision, current)
    advice = decision.advice
    return {
        "state_class": card.state_class,
        "badge": card.badge,
        "heading": card.heading,
        "governing_utilisation": card.governing_utilisation,
        "show_apply": card.show_apply,
        "advice_text": api["format_engineering_advice"](advice),
        "changes": [asdict(change) for change in advice.recommended_changes],
        "effects": list(advice.engineering_effects),
        "apply_allowed": bool(advice.apply_allowed),
        "current_failing": any(check.status == "fail" for check in advice.current_checks),
    }



def _neutral_publication_projection(
    *,
    family: str,
    reason: str,
    decision_status: str,
    apply_allowed: bool,
    selected_entry_condition_id: str,
    matched_families: tuple[str, ...],
    classification_reason_code: str,
    candidate_payload: Mapping[str, Any],
    updates: Mapping[str, Any],
    clause_metadata: Mapping[str, Any],
    source_revision: int,
    source_hash: str,
    v2_display: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the application publication shape without importing V1 types.

    The page renderer consumes the neutral ``AuthoritativeDesignResult`` but
    historically expects a nested final-publication/CTA/display projection.
    Keep that compatibility shape here, at the replacement boundary, so the
    V2 implementation does not leak native objects or force the page to call
    the legacy Design Brain formatter.
    """

    family_id = str(family or "").strip() or "UNKNOWN"
    reason_text = str(reason or "").strip() or "no_design_action"
    v2_display_map = dict(v2_display or {})
    authoritative_status = str(decision_status or "").strip().upper()
    if authoritative_status not in {"ACTION", "PASS", "BLOCKED", "INPUT_REQUIRED"}:
        raise ValueError(f"unsupported authoritative decision status: {decision_status!r}")
    typed_apply_allowed = bool(apply_allowed)
    if typed_apply_allowed != (authoritative_status == "ACTION"):
        raise ValueError("Apply authority must exactly match the ACTION decision status")
    if (
        "apply_allowed" in v2_display_map
        and bool(v2_display_map["apply_allowed"]) != typed_apply_allowed
    ):
        raise ValueError("card Apply state differs from the typed family decision")
    update_map = dict(updates or {}) if typed_apply_allowed else {}
    candidate_id = str(candidate_payload.get("candidate_id") or "").strip() or None
    action_type = "apply_resolved_candidate" if typed_apply_allowed and update_map else None
    if typed_apply_allowed and action_type is None:
        raise ValueError("ACTION publication requires exact resolved candidate updates")
    if typed_apply_allowed and candidate_id is None:
        raise ValueError("ACTION publication requires an exact resolved candidate ID")
    outcome_state = authoritative_status
    # The standalone V2 card renders the governing enum identifier verbatim.
    # Preserve that exact answer surface in Runtime instead of title-casing it
    # during neutral publication projection.
    display_title = family_id
    apply_payload = {
        "updates": dict(update_map),
        "resolved_candidate_updates": dict(update_map),
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "family": family_id,
        "resolved_candidate_family_tag": family_id,
        "action_type": action_type,
        "resolved_candidate_action_type": action_type,
        "source_input_revision": int(source_revision),
        "source_engineering_hash": source_hash,
        "v2_source_hash": source_hash,
        "review_before_apply": True,
    }
    apply_payload["state_fingerprint"] = stable_authority_hash(
        {"source_revision": source_revision, "source_hash": source_hash, "updates": update_map}
    )
    apply_payload["render_fingerprint"] = stable_authority_hash(
        {"family": family_id, "candidate_id": candidate_id, "updates": update_map}
    )
    cta_model = {
        "enabled": bool(action_type),
        "actionable": bool(action_type),
        "apply_allowed": bool(action_type),
        "label": "Apply recommendation" if action_type else None,
        "action_type": action_type,
        "family": family_id,
        "updates": dict(update_map),
        "source_candidate_id": candidate_id,
        "apply_payload_summary": dict(apply_payload),
        "disabled_reason": None if action_type else reason_text,
        "review_before_apply": True,
        "product_driving": True,
    }
    cta_model["button_contract_hash"] = stable_authority_hash(cta_model)
    v2_state_class = str(v2_display_map.get("state_class") or outcome_state.lower())
    v2_badge = str(v2_display_map.get("badge") or outcome_state)
    v2_advice_text = str(v2_display_map.get("advice_text") or "")
    v2_heading = str(v2_display_map.get("heading") or family_id)
    v2_governing_utilisation = float(v2_display_map.get("governing_utilisation") or 0.0)
    # Presentation may describe the current state, but publication authority
    # comes only from the typed family decision.
    publication_outcome_state = outcome_state
    display_model = {
        "title": display_title,
        "badge": v2_badge,
        "summary": v2_advice_text or reason_text.replace("_", " "),
        "status": v2_badge,
        "bucket": v2_state_class,
        "colour_state": v2_state_class,
        "card_class": f"inputs-v2-design-guide-item {v2_state_class}",
        "display_state": v2_badge,
        "blocker_explanation": None if action_type else reason_text.replace("_", " "),
        "clause_metadata": dict(clause_metadata),
        "selected_family_id": family_id,
        "selected_entry_condition_id": selected_entry_condition_id,
        "classification_reason_code": classification_reason_code,
        "matched_families": list(matched_families),
        "v2_state_class": v2_state_class,
        "v2_badge": v2_badge,
        "v2_advice_text": v2_advice_text,
        "v2_heading": v2_heading,
        "v2_governing_utilisation": v2_governing_utilisation,
        "v2_show_apply": bool(v2_display_map.get("show_apply", apply_allowed)),
        "v2_no_design_actions": bool(v2_display_map.get("no_design_actions")),
        "v2_changes": list(v2_display_map.get("changes") or []),
        "v2_apply_allowed": bool(v2_display_map.get("apply_allowed", apply_allowed)),
        "renderer_driving": True,
    }
    display_model["final_card_model_hash"] = stable_authority_hash(display_model)
    item = {
        "title": display_title,
        "title_main": display_title,
        "summary": display_model["summary"],
        "status": publication_outcome_state,
        "outcome_state": publication_outcome_state,
        "family": family_id,
        "selected_family_id": family_id,
        "selected_entry_condition_id": selected_entry_condition_id,
        "classification_reason_code": classification_reason_code,
        "published_family_id": family_id,
        "cta_family_id": family_id,
        "apply_payload_family_id": family_id,
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "updates": dict(update_map),
        "resolved_candidate_updates": dict(update_map),
        "action_payload": dict(apply_payload),
        "button_contract": dict(cta_model),
    }
    evidence = {
        "published_item_id": candidate_id,
        "selected_family": family_id,
        "selected_entry_condition_id": selected_entry_condition_id,
        "classification_reason_code": classification_reason_code,
        "matched_families": list(matched_families),
        "publication_reason": reason_text,
        "blocker_reason": None if action_type else reason_text,
        "candidate_search_evidence": {
            "candidate_id": candidate_id,
            "accepted": bool(action_type),
            "source_revision": int(source_revision),
            "source_hash": source_hash,
        },
        "target_band_proof": {"low": 0.85, "high": 1.0},
        "clause_metadata": dict(clause_metadata),
    }
    publication_base = {
        "published_item_id": candidate_id,
        "selected_family": family_id,
        "selected_family_id": family_id,
        "selected_entry_condition_id": selected_entry_condition_id,
        "classification_reason_code": classification_reason_code,
        "matched_families": list(matched_families),
        "published_family_id": family_id,
        "cta_family_id": family_id,
        "outcome_state": publication_outcome_state,
        "post_click_design_guide_state": publication_outcome_state,
        "publication_reason": reason_text,
        "blocker_reason": None if action_type else reason_text,
        "source_hash": source_hash,
        "source_revision": int(source_revision),
        "guidance_items": [item],
        "display": dict(display_model),
        "cta": dict(cta_model),
        "evidence": dict(evidence),
        "verifier_payload": {
            "outcome_state": publication_outcome_state,
            "selected_family_id": family_id,
            "selected_entry_condition_id": selected_entry_condition_id,
            "classification_reason_code": classification_reason_code,
            "published_family_id": family_id,
            "cta_family_id": family_id,
            "candidate_id": candidate_id,
            "source_input_revision": int(source_revision),
            "source_engineering_hash": source_hash,
            "review_before_apply": True,
        },
        "apply_payload": dict(apply_payload),
    }
    publication_hash = stable_authority_hash(publication_base)
    publication = {**publication_base, "publication_hash": publication_hash}
    verifier_payload = {
        **dict(publication_base["verifier_payload"]),
        "publication_hash": publication_hash,
        "final_publication_authority_hash": publication_hash,
    }
    display_model = {**display_model, "publication_hash": publication_hash}
    cta_model = {**cta_model, "publication_hash": publication_hash}
    return {
        "publication": publication,
        "display_model": display_model,
        "cta_model": cta_model,
        "apply_payload": apply_payload,
        "verifier_payload": verifier_payload,
        "publication_hash": publication_hash,
    }



class NewDesignBrainAdapter:
    """Adapt the isolated V2 orchestrator to the neutral application port."""

    def run(self, request: DesignBrainRequest) -> DesignBrainExecution:
        # Streamlit can retain a fragment callback while reloading an
        # application module. In that narrow case the callback may carry an
        # equivalent request object created by the previous module instance.
        # Keep the neutral port strict at the service boundary, but accept the
        # same typed request structurally here so a development reload cannot
        # turn a valid widget edit into a Design Brain crash.
        if not isinstance(request, DesignBrainRequest) and not all(
            hasattr(request, field)
            for field in (
                "engineering_snapshot",
                "input_revision",
                "family_hint",
                "resolved_inputs",
                "engineering_calculations",
                "debug_enabled",
            )
        ):
            raise TypeError("request must be a DesignBrainRequest")
        if request.input_revision is None:
            raise ValueError("V2 adapter requires an input revision")
        api = _v2_api()
        v2_source_manifest = source_manifest_hash()
        current, row_counts, serviceability_loads = _beam_inputs_from_snapshot(
            request.engineering_snapshot,
            api,
            int(request.input_revision),
            request.resolved_inputs,
        )
        has_design_actions = any(
            (
                current.actions.bending_moment_knm,
                current.actions.torsion_knm,
                current.actions.shear_force_kn,
                abs(current.actions.axial_force_kn),
            )
        )
        if has_design_actions:
            # This is the exact decision contract consumed by V2's own card.
            # The former Runtime path called ``preview`` and then rebuilt the
            # status/badge/heading independently, which caused card and
            # acceptance differences whenever V2 changed.
            decision = api["DesignGuideOrchestrator"]().decide(current)
            candidate = decision.candidate
            before = decision.current_result
            after = decision.proposed_result or before
            accepted = bool(decision.apply_allowed)
            family = str(decision.family.value)
            reason = str(decision.reason)
            decision_status = str(decision.status.value)
            selected_entry_condition_id = str(
                decision.classification.selected_entry_condition_id
            )
            matched_families = tuple(
                str(item.value) for item in decision.classification.matched_families
            )
            classification_reason_code = str(
                decision.classification.reason_code
            )
            decision_search_evidence = asdict(decision.search_evidence)
            changed_fields = tuple(decision.changed_fields)
            v2_display = _v2_display_projection(
                api=api,
                current=current,
                decision=decision,
            )
        else:
            # V2 deliberately does not run its Design Guide with no actions.
            # It shows a separate waiting card while the ordinary engineering
            # calculation remains available to the summary region.
            candidate = None
            before = api["CalculationCoordinator"](
                api["EngineeringCalculator"]()
            ).calculate_current(current).result
            if before is None:
                raise ValueError("V2 calculation did not produce a current no-load result")
            after = before
            accepted = False
            family = "NO_DESIGN_ACTIONS"
            reason = "no_design_actions"
            decision_status = "INPUT_REQUIRED"
            selected_entry_condition_id = "no_design_actions_entered"
            matched_families = ("INPUT_REQUIRED",)
            classification_reason_code = "no_design_actions_entered"
            decision_search_evidence = {}
            changed_fields = ()
            v2_display = {
                "state_class": "empty",
                "badge": "NO LOADS",
                "heading": "Design Brain waiting for actions",
                "governing_utilisation": 0.0,
                "show_apply": False,
                "apply_allowed": False,
                "no_design_actions": True,
                "advice_text": (
                    "No design actions entered. Add loads and the Design Brain "
                    "will check and optimise your beam."
                ),
                "changes": [],
                "effects": [],
                "current_failing": False,
            }
        # V2 deliberately leaves ``row_counts`` empty for candidates whose
        # authoritative proposal changes only the total bottom-bar count
        # (for example the shear-failure ladder).  Passing the current input
        # rows as a fallback changes the displayed V2 proposal back to the
        # old count at the Runtime Apply boundary.  Let _proposal_updates
        # derive the one-row arrangement from proposal.bottom_bars instead.
        updates = (
            _proposal_updates(
                candidate.proposal,
                candidate.row_counts,
                candidate.row_diameters_mm,
            )
            if candidate is not None and accepted
            else {}
        )
        candidate_payload = (
            {
                "candidate_id": candidate.candidate_id,
                "source_revision": candidate.source_revision,
                "source_hash": candidate.source_hash,
                "rationale": candidate.rationale,
                "row_counts": list(candidate.row_counts),
                "row_diameters_mm": list(candidate.row_diameters_mm),
                "proposal": asdict(candidate.proposal),
            }
            if candidate is not None
            else {}
        )
        publication_projection = _neutral_publication_projection(
            family=family,
            reason=reason,
            decision_status=decision_status,
            apply_allowed=accepted,
            selected_entry_condition_id=selected_entry_condition_id,
            matched_families=matched_families,
            classification_reason_code=classification_reason_code,
            candidate_payload=candidate_payload,
            updates=updates,
            clause_metadata=_clause_metadata(api, before),
            source_revision=int(request.input_revision),
            source_hash=request.engineering_snapshot.engineering_hash,
            v2_display=v2_display,
        )
        # The neutral result contract carries the canonical publication in the
        # same envelope as the legacy path.  UI/store consumers intentionally
        # read ``final_design_guide_publication`` from that envelope; exposing
        # only the V2 publication body here makes a valid ready job look like
        # an empty Design Guide (and consequently hides its Apply CTA).
        publication_body = {
            **publication_projection["publication"],
            "source": "inputs_v2",
            "v2_source_revision": before.source_revision,
            "v2_source_manifest_hash": v2_source_manifest,
            "final_publication_verifier_payload": publication_projection["verifier_payload"],
            "final_publication_authority_hash": publication_projection["publication_hash"],
            "final_publication_display_hash": publication_projection["display_model"].get(
                "final_card_model_hash"
            ),
            "final_publication_cta_hash": publication_projection["cta_model"].get(
                "button_contract_hash"
            ),
        }
        canonical_publication = {
            # Compatibility aliases keep diagnostics and non-rendering stores
            # able to inspect the publication without knowing its nested UI
            # shape.  Renderers still consume the canonical nested body below.
            "selected_family": publication_body.get("selected_family"),
            "selected_family_id": publication_body.get("selected_family_id"),
            "outcome_state": publication_body.get("outcome_state"),
            "source_revision": publication_body.get("source_revision"),
            "source_hash": publication_body.get("source_hash"),
            "guidance_items": list(publication_body.get("guidance_items") or []),
            "guidance_debug": {
                "source": "inputs_v2",
                "family_contract_version": "inputs_v2.family.v1",
                "selected_family_id": family,
            },
            "recommendation_result": {
                "source": "inputs_v2",
                "family": family,
                "accepted": accepted,
            },
            "final_design_guide_publication": publication_body,
            "final_publication_verifier_payload": publication_projection["verifier_payload"],
            "final_publication_publication_hash": publication_projection["publication_hash"],
            "final_publication_authority_hash": publication_projection["publication_hash"],
            "publication_hash": publication_projection["publication_hash"],
            "authoritative_publication_source": "inputs_v2",
            "authoritative_publication_evidence": dict(publication_body.get("evidence") or {}),
        }
        # Design Brain owns the recommendation/publication fields and V2 now
        # also publishes the revision-matched summary packs.  The Runtime
        # renderer can consume those packs without rebuilding legacy checks.
        current_calculations = {
            **dict(request.engineering_calculations or {}),
            "source": "inputs_v2",
            "calculation_contract_version": V2_ENGINEERING_CALCULATION_CONTRACT_VERSION,
            "actions_used": _actions_used_projection(current),
            "resolved_inputs": _resolved_inputs_projection(
                request.resolved_inputs,
                current,
            ),
            "v2_source_manifest_hash": v2_source_manifest,
            "v2_source_revision": before.source_revision,
            "v2_source_hash": before.source_hash,
            "v2_status": before.status,
            "v2_summary": before.summary,
            "families": dict(before.families),
            "packs": _v2_summary_packs(
                current=current,
                families=before.families,
            ),
            # Batch Design is a consumer of the V2 proposal, not a second
            # calculator.  Publish the already-verified post-proposal packs
            # beside the current packs so batch rows can report the exact
            # result V2 selected, without re-deriving a candidate in Runtime.
            "proposed_packs": _v2_summary_packs(
                current=current,
                families=after.families,
            ),
            "serviceability_loads": serviceability_loads,
            "proposed_families": dict(after.families),
        }
        result = build_authoritative_design_result(
            engineering_snapshot=request.engineering_snapshot,
            current_calculations=current_calculations,
            governing_family=family,
            selected_entry_condition_id=selected_entry_condition_id,
            matched_families=matched_families,
            classification_reason_code=classification_reason_code,
            family_contract_version="inputs_v2.family.v1",
            family_outcome=decision_status,
            selected_candidate=candidate_payload if accepted else None,
            selected_candidate_absence=None if accepted else {
                "reason": reason,
                "candidate_id": candidate_payload.get("candidate_id"),
            },
            selected_updates=updates if accepted else {},
            candidate_evaluation={
                "accepted": accepted,
                "changed_fields": list(changed_fields),
                "target_low": 0.85,
                "target_high": 1.0,
                "before": dict(before.families),
                "after": dict(after.families),
                "family_search_evidence": decision_search_evidence,
            },
            candidate_acceptance_proof={
                "source_revision_matches": candidate is None or candidate.source_revision == current.revision,
                "source_hash_matches": candidate is None or candidate.source_hash == current.content_hash,
                "v2_source_manifest_hash": v2_source_manifest,
                "reinforcement_fit": dict(after.families.get("reinforcement_fit", {})),
                "review_before_apply": True,
                "decision_status": decision_status,
                "selected_entry_condition_id": selected_entry_condition_id,
                "classification_reason_code": classification_reason_code,
            },
            blocker_or_exhaustion_proof={
                "reason": reason,
                "accepted": accepted,
                "family": family,
                "decision_status": decision_status,
                "selected_entry_condition_id": selected_entry_condition_id,
                "classification_reason_code": classification_reason_code,
                "search_evidence": decision_search_evidence,
                "v2_source_manifest_hash": v2_source_manifest,
            },
            final_publication=canonical_publication,
            display_model=publication_projection["display_model"],
            cta_model=publication_projection["cta_model"],
            apply_payload=publication_projection["apply_payload"],
        )
        return DesignBrainExecution(
            result=result,
            stage_trace=("v2.input_mapping", "v2.family_classification", "v2.candidate_preview", "v2.neutral_projection"),
            pipeline_applied=True,
            bypass_reason=None if accepted else reason,
            input_revision=int(request.input_revision),
        )


__all__ = [
    "NewDesignBrainAdapter",
]
