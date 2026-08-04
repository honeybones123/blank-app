"""Build the session-owned authoritative result from pure guidance data.

The legacy guidance calculator remains the injected compute implementation for
now, but publication is assembled here, before rendering. Renderers receive
the canonical publication as data and do not need to rebuild it.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from application.contracts.design_brain import (
    AuthoritativeDesignResult,
    EngineeringInputSnapshot,
    build_authoritative_design_result,
)
from application.family_ladder_dispatch_policy import resolve_family_ladder_dispatch
from application.whole_beam_family_restamp_policy import restamp_primary_guidance_family_from_whole_beam
from inputs_application.legacy_design_brain_adapter import (
    build_final_design_guide_publication,
    classify_family_from_whole_beam_evidence,
    family_strategy_for,
)


def _mapping(value: Any) -> dict[str, Any]:
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def _suppress_unapproved_family_candidate(
    *,
    guidance_items: list[dict[str, Any]],
    primary: dict[str, Any],
    action_payload: dict[str, Any],
    button_contract: dict[str, Any],
    resolved_candidate: dict[str, Any],
    selected_updates: dict[str, Any],
    selected_candidate: dict[str, Any] | None,
    family: Any,
    guidance_debug: Mapping[str, Any],
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any] | None,
]:
    """Fail closed when a generic projection bypasses a family ladder.

    All nonterminal families use the same approved family-ladder contract.
    Presentation/local-cleanup code can still produce a plausible update row,
    but that row is not an application candidate unless it carries the
    contract proof emitted by the selected family runtime.  Suppressing the
    row here preserves the evidence and publishes a controlled blocker rather
    than allowing the live pipeline to raise after rendering has started.
    """

    family_id = str(family or "").strip()
    if not family_id or not selected_updates:
        return (
            guidance_items,
            primary,
            action_payload,
            button_contract,
            resolved_candidate,
            selected_updates,
            selected_candidate,
        )
    dispatch = resolve_family_ladder_dispatch(
        {
            "selected_family_id": family_id,
            "classification_passed": True,
        },
        strategy_lookup=family_strategy_for,
    )
    if not dispatch.should_run_family_ladder:
        return (
            guidance_items,
            primary,
            action_payload,
            button_contract,
            resolved_candidate,
            selected_updates,
            selected_candidate,
        )
    evidence = _mapping(
        resolved_candidate.get("candidate_search_evidence")
        or primary.get("candidate_search_evidence")
        or action_payload.get("candidate_search_evidence")
        or guidance_debug.get("candidate_search_evidence")
    )

    def _candidate_field(key: str) -> Any:
        for source in (selected_candidate, resolved_candidate, primary, evidence):
            if isinstance(source, Mapping) and source.get(key) is not None:
                return source.get(key)
        return None

    proof_ok = (
        _candidate_field("candidate_contract_approved") is True
        and str(_candidate_field("candidate_contract_id") or "").strip()
        == str(dispatch.candidate_contract_id or "").strip()
        and str(_candidate_field("candidate_generation_policy_id") or "").strip()
        == str(dispatch.generation_policy_id or "").strip()
        and str(_candidate_field("candidate_evaluation_policy_id") or "").strip()
        == str(dispatch.evaluation_policy_id or "").strip()
        and str(_candidate_field("candidate_selection_policy_id") or "").strip()
        == str(dispatch.selection_policy_id or "").strip()
        and str(_candidate_field("candidate_source_stage") or "").strip().startswith(
            "family_ladder:"
        )
    )
    if proof_ok:
        return (
            guidance_items,
            primary,
            action_payload,
            button_contract,
            resolved_candidate,
            selected_updates,
            selected_candidate,
        )

    # Keep candidate-search evidence for the blocker/debug surface, but make
    # every actionable projection inert before publication or Apply assembly.
    primary = dict(primary)
    primary["family_ladder_candidate_suppressed"] = True
    primary["family_ladder_candidate_suppression_reason"] = (
        "unapproved_live_finalist"
    )
    primary["updates"] = {}
    action_payload = dict(action_payload)
    action_payload.update(
        {
            "updates": {},
            "resolved_candidate_updates": {},
            "candidate_id": None,
            "source_candidate_id": None,
            "family_ladder_candidate_suppressed": True,
            "candidate_search_evidence": dict(evidence),
        }
    )
    primary["action_payload"] = action_payload
    button_contract = dict(button_contract)
    button_contract.update(
        {
            "updates": {},
            "candidate_id": None,
            "source_candidate_id": None,
            "enabled": False,
            "actionable": False,
            "blocking_reason": "no approved family candidate was emitted",
        }
    )
    primary["button_contract"] = button_contract
    primary["resolved_candidate_updates"] = {}
    primary["candidate_id"] = None
    primary["source_candidate_id"] = None
    primary["resolved_candidate"] = {}
    if guidance_items:
        guidance_items = [dict(item) for item in guidance_items]
        guidance_items[0] = primary
    selected_updates = {}
    selected_candidate = None
    resolved_candidate = {}
    return (
        guidance_items,
        primary,
        action_payload,
        button_contract,
        resolved_candidate,
        selected_updates,
        selected_candidate,
    )


def _family_from_guidance_evidence(
    *,
    primary: Mapping[str, Any],
    guidance_debug: Mapping[str, Any],
) -> str | None:
    """Resolve active strength ownership from explicit post-selection evidence."""

    explicit_family = ""
    for key in (
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "family",
    ):
        value = str(primary.get(key) or "").strip()
        if value and value.lower() not in {"combined", "bending", "shear", "general"}:
            explicit_family = value
            if value.upper() not in {"BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS"}:
                return value
            break

    selector_text = " ".join(
        str(primary.get(key) or "").strip().lower()
        for key in (
            "check_key",
            "family_id",
            "guidance_intent",
            "title_main",
            "title",
            "status",
            "bucket",
        )
    )
    if any(token in selector_text for token in ("serviceability", "crack", "deflection")):
        return "SERVICEABILITY_GOVERNS"

    overview = _mapping(guidance_debug.get("overview"))
    statuses = _mapping(overview.get("statuses"))
    utils = _mapping(overview.get("utils"))
    bending_fail = str(statuses.get("bending") or "").strip().upper() == "FAIL"
    shear_fail = str(statuses.get("shear") or "").strip().upper() == "FAIL"
    action_payload = _mapping(primary.get("action_payload"))
    button_contract = _mapping(primary.get("button_contract"))
    resolved_candidate = _mapping(primary.get("resolved_candidate"))
    updates = _mapping(
        button_contract.get("updates")
        or action_payload.get("resolved_candidate_updates")
        or action_payload.get("updates")
        or resolved_candidate.get("updates")
    )
    try:
        shear_utilisation = float(utils.get("shear")) if utils.get("shear") is not None else None
    except (TypeError, ValueError):
        shear_utilisation = None
    classified = classify_family_from_whole_beam_evidence(
        {
            "bending_state": "FAIL" if bending_fail else "TARGET",
            "shear_state": (
                "FAIL"
                if shear_fail
                else "OVERDESIGNED"
                if shear_utilisation is not None and shear_utilisation < 0.85
                else "TARGET"
            ),
            "bending_utilisation": utils.get("bending"),
            "shear_utilisation": shear_utilisation,
            "can_strengthen_bending": bool(
                set(updates)
                & {
                    "D",
                    "b",
                    "bw",
                    "bot1_count",
                    "bot2_count",
                    "db_bot_1",
                    "db_bot_2",
                    "bot_row_1_bars",
                    "bot_row_2_bars",
                    "bot_row_1_dia",
                    "bot_row_2_dia",
                }
            ),
            "can_strengthen_shear": bool(set(updates) & {"lig_d", "lig_legs", "s_lig"}),
        }
    )
    classified_family = str(classified.get("selected_family_id") or "").strip()
    if classified_family in {
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    }:
        return classified_family
    if bending_fail and shear_fail:
        return "COMBINED_BENDING_SHEAR_FAIL"
    if bending_fail:
        return "BENDING_FAIL_GOVERNS"
    if shear_fail:
        return "SHEAR_FAIL_GOVERNS"
    return explicit_family or None


def _terminal_family_from_guidance(
    *,
    primary: Mapping[str, Any],
    guidance_debug: Mapping[str, Any],
    resolved_inputs: Mapping[str, Any] | None,
) -> str | None:
    sources = (primary, guidance_debug, resolved_inputs or {})
    candidate_evidence = _mapping(
        guidance_debug.get("candidate_search_evidence")
        or primary.get("candidate_search_evidence")
    )
    family_owned_exact_blockers = _mapping(
        candidate_evidence.get("post_click_exact_blockers_by_family")
        or candidate_evidence.get("exact_blockers_by_family")
        or guidance_debug.get("post_click_exact_blockers_by_family")
        or guidance_debug.get("exact_blockers_by_family")
        or primary.get("post_click_exact_blockers_by_family")
        or primary.get("exact_blockers_by_family")
    )
    if (
        family_owned_exact_blockers
        and bool(candidate_evidence.get("family_ladder_exhausted"))
        and candidate_evidence.get("legacy_fallback_allowed") is False
    ):
        # A family ladder that has exhausted without the legacy fallback is a
        # family-owned blocker, not generic target-band completion. Returning
        # None lets the explicit selected family flow through unchanged.
        return None
    exact_stop = any(
        bool(source.get("exact_stop_proof"))
        or bool(source.get("exact_stop_proven"))
        or bool(source.get("exact_stop_available"))
        for source in sources
    )
    terminal_state = next(
        (
            str(source.get("design_guide_terminal_state") or source.get("terminal_state") or "").strip().lower()
            for source in sources
            if str(source.get("design_guide_terminal_state") or source.get("terminal_state") or "").strip()
        ),
        "",
    )
    primary_status = str(primary.get("status") or primary.get("display_state") or "").strip().upper()
    button_contract = _mapping(primary.get("button_contract"))
    no_action = not bool(
        button_contract.get("enabled")
        or button_contract.get("actionable")
        or button_contract.get("updates")
        or primary.get("updates")
    )
    if exact_stop and no_action:
        return "EXACT_STOP_PROVEN"
    if no_action and (
        terminal_state in {"optimal", "very_low_demand", "target_band_reached"}
        or (
            primary_status == "PASS"
            and bool(guidance_debug.get("target_band_with_eps_passed"))
        )
    ):
        return "TARGET_BAND_REACHED"
    return None


@dataclass(frozen=True)
class GuidanceAuthorityResolution:
    """Pure selection/family facts shared by pipeline and publication.

    This is deliberately upstream of the final publication model.  It keeps
    the live pipeline from re-parsing a guidance payload differently from the
    result adapter that builds the card and Apply command.
    """

    payload: dict[str, Any]
    guidance_items: tuple[dict[str, Any], ...]
    guidance_debug: dict[str, Any]
    recommendation_result: dict[str, Any]
    primary: dict[str, Any]
    button_contract: dict[str, Any]
    resolved_candidate: dict[str, Any]
    selected_updates: dict[str, Any]
    selected_candidate: dict[str, Any] | None
    selected_candidate_absence: dict[str, Any] | None
    governing_family: str | None
    family_outcome: str | None
    family_restamp: dict[str, Any]


def resolve_guidance_authority(
    *,
    guidance_payload: Mapping[str, Any] | None,
    family_override: str | None = None,
    resolved_inputs: Mapping[str, Any] | None = None,
) -> GuidanceAuthorityResolution:
    """Resolve the one family/candidate identity used by every live stage."""

    payload = _mapping(guidance_payload)
    guidance_items = [
        deepcopy(item)
        for item in list(payload.get("guidance_items") or [])
        if isinstance(item, Mapping)
    ]
    guidance_debug = _mapping(payload.get("debug_trace"))
    guidance_items, guidance_debug, family_restamp = (
        restamp_primary_guidance_family_from_whole_beam(
            guidance_items,
            guidance_debug,
            family_classifier=classify_family_from_whole_beam_evidence,
        )
    )
    recommendation_result = _mapping(payload.get("recommendation_result"))
    primary = _mapping(guidance_items[0] if guidance_items else {})
    action_payload = _mapping(primary.get("action_payload"))
    button_contract = _mapping(primary.get("button_contract"))
    resolved_candidate = _mapping(primary.get("resolved_candidate"))
    selected_updates = _mapping(
        action_payload.get("updates")
        or button_contract.get("updates")
        or resolved_candidate.get("updates")
    )
    selected_candidate = resolved_candidate or recommendation_result or None
    action_explicitly_blocked = bool(
        button_contract
        and (
            button_contract.get("enabled") is False
            or button_contract.get("actionable") is False
            or bool(button_contract.get("blocking_reason"))
        )
    )
    if action_explicitly_blocked:
        # Candidate search evidence may describe a technically valid option,
        # but a disabled executor contract is not an Apply candidate. Keep
        # the evidence while publishing a typed no-candidate outcome so that
        # selection, publication, and Apply agree.
        selected_updates = {}
        selected_candidate = None
    terminal_family = _terminal_family_from_guidance(
        primary=primary,
        guidance_debug=guidance_debug,
        resolved_inputs=resolved_inputs,
    )
    evidence_family = terminal_family or (
        family_restamp.get("to_family")
        if family_restamp.get("restamped")
        else _family_from_guidance_evidence(
            primary=primary,
            guidance_debug=guidance_debug,
        )
    ) or (
        primary.get("selected_family_id")
        or primary.get("family")
        or button_contract.get("family")
        or resolved_candidate.get("family")
        or guidance_debug.get("governing_family")
    )
    override_family = str(family_override or "").strip()
    if terminal_family:
        family = terminal_family
    else:
        family = (
            evidence_family
            if (
                override_family.upper()
                in {"BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS"}
                and str(evidence_family or "").strip().upper()
                in {
                    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
                    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
                }
            )
            else override_family or evidence_family
        )
    (
        guidance_items,
        primary,
        action_payload,
        button_contract,
        resolved_candidate,
        selected_updates,
        selected_candidate,
    ) = _suppress_unapproved_family_candidate(
        guidance_items=guidance_items,
        primary=primary,
        action_payload=action_payload,
        button_contract=button_contract,
        resolved_candidate=resolved_candidate,
        selected_updates=selected_updates,
        selected_candidate=selected_candidate,
        family=family,
        guidance_debug=guidance_debug,
    )
    outcome = (
        primary.get("status")
        or guidance_debug.get("guidance_branch")
        or guidance_debug.get("design_guide_terminal_state")
    )
    absence = None
    if selected_candidate is None:
        absence = {
            "reason": guidance_debug.get("stop_reason")
            or guidance_debug.get("user_visible_no_action_reason")
            or "no_selected_guidance_candidate",
            "family": family,
        }
    return GuidanceAuthorityResolution(
        payload=payload,
        guidance_items=tuple(guidance_items),
        guidance_debug=guidance_debug,
        recommendation_result=recommendation_result,
        primary=primary,
        button_contract=button_contract,
        resolved_candidate=resolved_candidate,
        selected_updates=selected_updates,
        selected_candidate=selected_candidate,
        selected_candidate_absence=absence,
        governing_family=str(family).strip() if family is not None else None,
        family_outcome=str(outcome).strip() if outcome is not None else None,
        family_restamp=_mapping(family_restamp),
    )


def build_authoritative_design_result_from_guidance_payload(
    *,
    engineering_snapshot: EngineeringInputSnapshot,
    guidance_payload: Mapping[str, Any] | None,
    family_override: str | None = None,
    resolved_inputs: Mapping[str, Any] | None = None,
    engineering_calculations: Mapping[str, Any] | None = None,
    authority_resolution: GuidanceAuthorityResolution | None = None,
) -> AuthoritativeDesignResult:
    """Build an authority result from explicit existing guidance data."""

    resolution = authority_resolution or resolve_guidance_authority(
            guidance_payload=guidance_payload,
            family_override=family_override,
            resolved_inputs=resolved_inputs,
        )
    payload = resolution.payload
    guidance_items = list(resolution.guidance_items)
    guidance_debug = resolution.guidance_debug
    recommendation_result = resolution.recommendation_result
    primary = resolution.primary
    button_contract = resolution.button_contract
    resolved_candidate = resolution.resolved_candidate
    selected_updates = resolution.selected_updates
    selected_candidate = resolution.selected_candidate
    family = resolution.governing_family
    outcome = resolution.family_outcome
    absence = resolution.selected_candidate_absence
    publication_family = str(family or "").strip() or None
    publication_item = {
        **primary,
        "authoritative_family_override": publication_family,
        "family": publication_family or primary.get("family"),
        "selected_family_id": publication_family or primary.get("selected_family_id"),
        "published_family_id": publication_family or primary.get("published_family_id"),
        "cta_family_id": publication_family or primary.get("cta_family_id"),
        "apply_payload_family_id": publication_family or primary.get("apply_payload_family_id"),
        "button_contract": {
            **button_contract,
            "family": publication_family or button_contract.get("family"),
            "selected_family_id": publication_family or button_contract.get("selected_family_id"),
            "published_family_id": publication_family or button_contract.get("published_family_id"),
            "cta_family_id": publication_family or button_contract.get("cta_family_id"),
            "apply_payload_family_id": publication_family or button_contract.get("apply_payload_family_id"),
        },
    }
    publication_debug = {
        **guidance_debug,
        "family_utils": (
            _mapping(guidance_debug.get("family_utils"))
            or _mapping(_mapping(guidance_debug.get("overview")).get("utils"))
        ),
        "authoritative_family_override": publication_family,
        "selected_family_id": publication_family or guidance_debug.get("selected_family_id"),
        "published_family_id": publication_family or guidance_debug.get("published_family_id"),
        "cta_family_id": publication_family or guidance_debug.get("cta_family_id"),
    }
    publication = build_final_design_guide_publication(
        item=publication_item,
        debug=publication_debug,
        publication_reason="authoritative_application_compute",
    )
    publication_dict = publication.to_dict()
    cta_model = publication.cta.to_dict()
    display_model = publication.display.to_dict()
    evidence_model = publication.evidence.to_dict()
    verifier_model = publication.verifier_payload.to_dict()
    verifier_payload = _mapping(verifier_model.get("payload"))
    apply_payload = _mapping(cta_model.get("apply_payload_summary"))
    if apply_payload:
        apply_payload = {
            **apply_payload,
            "family": publication.selected_family,
            "resolved_candidate_family_tag": publication.selected_family,
            "resolved_candidate_subfamilies": list(
                selected_candidate.get("subfamilies") or []
            ) if isinstance(selected_candidate, Mapping) else [],
            "action_type": cta_model.get("action_type"),
            "resolved_candidate_action_type": cta_model.get("action_type"),
            "resolved_candidate_label": cta_model.get("label"),
            "guidance_change_lines": list(primary.get("guidance_change_lines") or []),
            "resolved_candidate_updates": dict(apply_payload.get("updates") or {}),
            "candidate_id": (
                apply_payload.get("candidate_id")
                or cta_model.get("source_candidate_id")
                or publication.published_item_id
            ),
            "source_candidate_id": (
                apply_payload.get("source_candidate_id")
                or cta_model.get("source_candidate_id")
                or publication.published_item_id
            ),
            "authoritative_publication_hash": publication.publication_hash,
        }
    canonical_payload = {
        "guidance_items": guidance_items,
        "guidance_debug": guidance_debug,
        "recommendation_result": recommendation_result,
        "final_design_guide_publication": publication_dict,
        "final_publication_verifier_payload": verifier_payload,
        "final_publication_publication_hash": publication.publication_hash,
        "final_publication_authority_hash": publication.publication_hash,
        "publication_hash": publication.publication_hash,
        "authoritative_publication_source": "application.guidance_result_adapter",
        "authoritative_publication_evidence": evidence_model,
    }
    # Design Brain publishes recommendations; it must not silently replace the
    # complete, revision-matched engineering packs already calculated for the
    # same snapshot. The explicit engineering handoff wins over any reduced
    # overview carried in guidance debug data.
    current_calculations = {
        **_mapping(guidance_debug.get("overview")),
        **_mapping(engineering_calculations),
    }
    if isinstance(resolved_inputs, Mapping):
        current_calculations = {
            **current_calculations,
            "resolved_inputs": dict(resolved_inputs),
        }
    return build_authoritative_design_result(
        engineering_snapshot=engineering_snapshot,
        current_calculations=current_calculations,
        governing_family=str(family).strip() if family is not None else None,
        family_contract_version=str(guidance_debug.get("family_contract_version") or "") or None,
        family_outcome=str(outcome).strip() if outcome is not None else None,
        selected_candidate=selected_candidate,
        selected_candidate_absence=absence,
        selected_updates=selected_updates,
        candidate_evaluation=_mapping(guidance_debug.get("candidate_search_evidence")),
        candidate_acceptance_proof=_mapping(
            guidance_debug.get("candidate_acceptance_proof")
            or guidance_debug.get("acceptance_proof")
        ),
        blocker_or_exhaustion_proof=_mapping(
            guidance_debug.get("exact_blockers_by_family")
            or guidance_debug.get("post_click_exact_blockers_by_family")
            or guidance_debug.get("candidate_search_evidence")
        ),
        final_publication=canonical_payload,
        display_model=display_model,
        cta_model=cta_model,
        apply_payload=apply_payload,
    )


def guidance_payload_from_authoritative_design_result(
    result: AuthoritativeDesignResult | None,
) -> dict[str, Any]:
    if not isinstance(result, AuthoritativeDesignResult):
        return {}
    return _mapping(result.final_publication)


__all__ = [
    "GuidanceAuthorityResolution",
    "build_authoritative_design_result_from_guidance_payload",
    "guidance_payload_from_authoritative_design_result",
    "resolve_guidance_authority",
]
