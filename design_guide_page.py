"""Design Guide page adapter.

This module owns the Streamlit page mounting boundary for the Design Guide.
The heavy controller/solver callbacks still live in ``inputs_page`` for now,
but routing the UI entrypoints through this file gives the page a stable home
for the staged extraction.
"""

from __future__ import annotations

from collections.abc import Callable
import html
import time
from typing import Any


TraceFn = Callable[..., None]
RenderPanelFn = Callable[..., None]
DebugSidebarFn = Callable[[], None]


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _proof_backed_placeholder_card(st_module: Any) -> dict | None:
    """Return a single exact-blocker card when final-panel proof already exists."""
    try:
        bundle = st_module.session_state.get("_design_guide_debug_bundle")
    except Exception:
        bundle = None
    if not isinstance(bundle, dict):
        return None
    intent = str(bundle.get("primary_guidance_intent") or bundle.get("primary_card_intent") or "").strip()
    if intent != "specific_blocker":
        return None
    contract = bundle.get("primary_button_contract") or bundle.get("button_contract") or {}
    if isinstance(contract, dict) and bool(contract.get("enabled") or contract.get("actionable")):
        return None
    exact_blockers = (
        bundle.get("post_click_exact_blockers_by_family")
        or bundle.get("exact_blockers_by_family")
        or {}
    )
    target_band_blocked = bool(
        isinstance(contract, dict)
        and (
            contract.get("target_band_contract_blocked")
            or str(contract.get("blocking_reason") or "").strip()
            == "cleanup_target_band_not_proven"
        )
    )
    if (not isinstance(exact_blockers, dict) or not exact_blockers) and not target_band_blocked:
        return None
    family = ""
    if isinstance(contract, dict):
        family = str(contract.get("family") or "").strip().lower()
    if family not in {"bending", "shear", "crack", "deflection", "combined"}:
        family = str(next(iter(exact_blockers), "design") if isinstance(exact_blockers, dict) and exact_blockers else "combined").strip().lower()
    blocker = (
        exact_blockers.get(family)
        if isinstance(exact_blockers, dict) and family in exact_blockers
        else (next(iter(exact_blockers.values()), {}) if isinstance(exact_blockers, dict) and exact_blockers else {})
    )
    blocker = blocker if isinstance(blocker, dict) else {}
    decision_trace = bundle.get("design_guide_decision_trace") or {}
    decision_trace = decision_trace if isinstance(decision_trace, dict) else {}
    candidate_evidence = bundle.get("candidate_search_evidence") or {}
    candidate_evidence = candidate_evidence if isinstance(candidate_evidence, dict) else {}
    if target_band_blocked and not exact_blockers and not candidate_evidence:
        return None
    family_utils: dict[str, float] = {}
    for family_name, util_key in (
        ("bending", "bending_util"),
        ("shear", "shear_util"),
    ):
        util_value = _as_float(
            (bundle.get("family_utils") or {}).get(family_name)
            if isinstance(bundle.get("family_utils"), dict)
            else None
        )
        if util_value is None:
            util_value = _as_float(decision_trace.get(util_key))
        if util_value is not None:
            family_utils[family_name] = float(util_value)
    material_families = [
        str(value or "").strip().lower()
        for value in list(bundle.get("materially_overprovided_families") or [])
        if str(value or "").strip()
    ]
    if not material_families:
        floor = _as_float(bundle.get("final_accepted_min_family_util")) or 0.85
        material_families = [
            family_name
            for family_name, util_value in sorted(family_utils.items())
            if util_value < floor
        ]
    truth = bundle.get("primary_display_truth") or {}
    truth = truth if isinstance(truth, dict) else {}
    if target_band_blocked:
        util = (
            decision_trace.get("worst_util")
            or decision_trace.get("governing_util")
            or (max(family_utils.values()) if family_utils else None)
            or truth.get("source_summary_util")
            or truth.get("source_post_commit_util")
        )
    else:
        util = truth.get("displayed_util")
    if util is None:
        util = blocker.get("current_util") or blocker.get("failed_check_util")
    reason = ""
    if isinstance(contract, dict):
        reason = str(contract.get("blocking_reason") or "").strip()
    if not reason:
        reason = str(
            blocker.get("reason")
            or blocker.get("why_reduction_would_hurt_other_design_elements")
            or "The exact cleanup search was exhausted and no executor-backed update preserved every required check."
        ).strip()
    if target_band_blocked and reason == "cleanup_target_band_not_proven":
        reason = (
            "No Apply button is published because the cleanup proof does not keep every required "
            "family inside the target utilisation range."
        )
    title = str(bundle.get("primary_card_title") or bundle.get("final_primary_title") or "").strip()
    if target_band_blocked and (
        not title
        or title == "Cleanup is advisory for this design state"
        or "further reduction reaches target range" in title.lower()
        or "one-click optimisation" in title.lower()
    ):
        title = "Bending and shear cleanup blocked"
    if not title or title.lower().startswith("cleanup blocked"):
        label = {
            "bending": "Bending cleanup",
            "shear": "Shear cleanup",
            "crack": "Crack control cleanup",
            "deflection": "Deflection cleanup",
            "combined": "Design cleanup",
        }.get(family, "Design cleanup")
        title = f"{label} blocked by exact engineering limit"
    search_ran = _as_bool(
        bundle.get("local_cleanup_search_ran")
        or candidate_evidence.get("local_cleanup_search_ran")
        or candidate_evidence.get("cleanup_search_ran")
    )
    search_exhaustive = _as_bool(
        bundle.get("local_cleanup_search_exhaustive")
        or candidate_evidence.get("local_cleanup_search_exhaustive")
        or candidate_evidence.get("candidate_search_exhaustive")
        or candidate_evidence.get("cleanup_search_exhaustive")
    )
    safe_count = bundle.get("safe_local_cleanup_count")
    if safe_count is None:
        safe_count = candidate_evidence.get("safe_local_cleanup_count")
    if safe_count is None:
        safe_count = candidate_evidence.get("safe_executor_backed_candidates_count")
    if target_band_blocked and candidate_evidence:
        safe_count = 0
    executable_count = bundle.get("executable_safe_cleanup_count")
    if executable_count is None:
        executable_count = candidate_evidence.get("executable_safe_cleanup_count")
    if executable_count is None:
        executable_count = candidate_evidence.get("executable_target_band_candidate_count")
    if target_band_blocked and candidate_evidence:
        executable_count = 0
    inventory_count = (
        candidate_evidence.get("candidate_inventory_count")
        or candidate_evidence.get("local_cleanup_candidate_inventory_count")
        or len(list(candidate_evidence.get("candidate_rows") or []))
        or len(list(candidate_evidence.get("safe_executor_backed_candidates") or []))
    )
    if target_band_blocked and not exact_blockers:
        blocker_family = material_families[0] if material_families else family
        exact_blockers = {
            blocker_family: {
                "family": blocker_family,
                "reason": reason,
                "cleanup_search_ran": search_ran,
                "cleanup_search_exhaustive": search_exhaustive,
                "target_band_contract_blocked": True,
            }
        }
    return {
        "title": title,
        "family": family,
        "util": util,
        "reason": reason,
        "target_band_contract_blocked": target_band_blocked,
        "local_cleanup_search_ran": search_ran,
        "local_cleanup_search_exhaustive": search_exhaustive,
        "safe_local_cleanup_count": safe_count,
        "executable_safe_cleanup_count": executable_count,
        "candidate_inventory_count": inventory_count,
        "materially_overprovided_families": material_families,
        "family_utils": family_utils,
        "exact_blocker_families": sorted(str(key).lower() for key in dict(exact_blockers).keys()),
    }


def _render_proof_backed_card(st_module: Any, proof_card: dict) -> None:
    util = proof_card.get("util")
    util_text = ""
    try:
        util_text = f" <span class='fast-guidance-title-util'>(utilisation = {float(util):.2f})</span>"
    except Exception:
        util_text = ""
    title = html.escape(str(proof_card.get("title") or "Design cleanup blocked"))
    reason = html.escape(str(proof_card.get("reason") or "Exact blocker evidence is available."))
    family_utils = proof_card.get("family_utils") if isinstance(proof_card.get("family_utils"), dict) else {}
    attrs = {
        "data-testid": "design-guide-card",
        "data-guidance-intent": "specific_blocker",
        "data-target-band-contract-blocked": proof_card.get("target_band_contract_blocked"),
        "data-local-cleanup-search-ran": proof_card.get("local_cleanup_search_ran"),
        "data-local-cleanup-search-exhaustive": proof_card.get("local_cleanup_search_exhaustive"),
        "data-safe-local-cleanup-count": proof_card.get("safe_local_cleanup_count"),
        "data-executable-safe-cleanup-count": proof_card.get("executable_safe_cleanup_count"),
        "data-candidate-inventory-count": proof_card.get("candidate_inventory_count"),
        "data-materially-overprovided-families": ",".join(
            str(value).strip().lower()
            for value in list(proof_card.get("materially_overprovided_families") or [])
            if str(value).strip()
        ),
        "data-exact-blocker-families": ",".join(
            str(value).strip().lower()
            for value in list(proof_card.get("exact_blocker_families") or [])
            if str(value).strip()
        ),
        "data-family-util-bending": family_utils.get("bending"),
        "data-family-util-shear": family_utils.get("shear"),
    }
    attr_text = " ".join(
        f"{html.escape(str(name), quote=True)}=\"{html.escape(str(value), quote=True)}\""
        for name, value in attrs.items()
        if value is not None
    )
    st_module.markdown(
        f"<div class='fast-guidance-item warn' {attr_text}>"
        "<div class='fast-guidance-head'>"
        "<span class='fast-guidance-badge warn'>NEXT</span>"
        "<span class='fast-guidance-title-wrap'>"
        f"<span class='fast-guidance-title'>{title}</span>{util_text}"
        "</span></div>"
        f"<div class='fast-guidance-reason'><strong>Why</strong><br>{reason}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_proof_pending_shell(st_module: Any) -> None:
    """Render a CTA-free Design Guide placeholder while proof/search is running."""
    applying = bool(st_module.session_state.get("_design_guide_component_apply_in_flight"))
    chips = ("Strength", "Detailing", "Serviceability", "Cleanup options")
    chips_html = "".join(
        f"<span class='dg-proof-pending-chip'>{html.escape(label)}</span>"
        for label in chips
    )
    title = "Applying one-click design..." if applying else "Checking design guidance&hellip;"
    subtext = (
        "Updating the beam inputs, recalculating checks, and preparing the final Design Guide result."
        if applying
        else "Reviewing strength, detailing, serviceability, and cleanup options."
    )
    shell_class = "dg-proof-pending-shell applying" if applying else "dg-proof-pending-shell"
    st_module.markdown(
        f"<section class='{shell_class}' data-testid='design-guide-proof-pending' "
        "aria-live='polite' aria-busy='true'>"
        "<div class='dg-proof-pending-eyebrow'>Design Guide</div>"
        f"<div class='dg-proof-pending-title'>{title}</div>"
        "<div class='dg-proof-pending-subtext'>"
        f"{html.escape(subtext)}"
        "</div>"
        "<div class='dg-proof-pending-bar' aria-hidden='true'>"
        "<span class='dg-proof-pending-bar-fill'></span></div>"
        f"<div class='dg-proof-pending-chips'>{chips_html}</div>"
        "</section>",
        unsafe_allow_html=True,
    )


def _has_final_design_guide_publication_payload(st_module: Any) -> bool:
    try:
        bundle = st_module.session_state.get("_design_guide_debug_bundle")
    except Exception:
        bundle = None
    if not isinstance(bundle, dict):
        return False
    payload = bundle.get("final_publication_verifier_payload")
    if not isinstance(payload, dict):
        return False
    if str(payload.get("publication_hash") or "").strip():
        return True
    state = str(
        payload.get("outcome_state")
        or payload.get("status")
        or payload.get("publication_status")
        or ""
    ).strip().upper()
    return state in {"PASS", "ACTION", "BLOCKED", "ERROR"}


def _should_skip_pre_widget_placeholder(st_module: Any) -> bool:
    try:
        if bool(st_module.session_state.get("_design_guide_component_apply_in_flight")):
            return True
    except Exception:
        pass
    return False


def render_pre_widget_placeholder(
    st_module: Any,
    slot: Any,
    *,
    render_heading: bool = True,
    render_pending_shell: bool = True,
) -> None:
    """Mount the lightweight Design Guide placeholder before inputs widgets."""
    if _should_skip_pre_widget_placeholder(st_module):
        return
    with slot.container():
        if render_heading:
            st_module.markdown("### Design Guide")
        proof_card = _proof_backed_placeholder_card(st_module)
        if isinstance(proof_card, dict):
            _render_proof_backed_card(st_module, proof_card)
            return
        if not render_pending_shell:
            return
        _render_proof_pending_shell(st_module)


def render_final_panel(
    st_module: Any,
    *,
    slot: Any,
    sync_callbacks: dict,
    inputs_render_audit: dict[str, str] | None,
    inputs_detailed_mode: bool,
    fast_focus_section: str | None,
    render_panel: RenderPanelFn,
    trace: TraceFn,
    render_panel_accepts_sync_callbacks: bool = True,
) -> None:
    """Replace the placeholder with the proof-backed Design Guide panel."""
    slot.empty()
    with slot.container():
        trace_started = time.perf_counter()
        if not render_panel_accepts_sync_callbacks:
            render_panel(
                inputs_render_audit=inputs_render_audit,
                fast_focus_section=fast_focus_section if inputs_detailed_mode else None,
            )
            mode = "detailed" if inputs_detailed_mode else "fast"
        elif inputs_detailed_mode:
            render_panel(
                sync_callbacks,
                inputs_render_audit,
                fast_focus_section=fast_focus_section,
            )
            mode = "detailed"
        else:
            render_panel(sync_callbacks, inputs_render_audit)
            mode = "fast"
        trace(
            "render_inputs.render_fast_design_guidance_panel",
            duration_ms=round((time.perf_counter() - trace_started) * 1000.0, 2),
            mode=mode,
            timing="after_core_inputs_widgets",
        )


def render_debug_sidebar(render_sidebar: DebugSidebarFn) -> None:
    """Render the Design Guide debug sidebar through the page boundary."""
    render_sidebar()
