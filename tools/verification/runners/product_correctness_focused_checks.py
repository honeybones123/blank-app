from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.engine import resolve_design_guide_card
from shear_checks_helpers import build_shear_check_rows_from_state
from state_and_helpers import (
    BEAM_STATUS_FAIL,
    SHARED_DEFAULTS,
    get_beam_overall_status,
)
from inputs_page import (
    RESCUE_SEED_LIBRARY,
    _design_guide_dashboard_reasons,
    _design_guide_dashboard_card_html_with_render_model,
    _design_guide_button_contract_enabled,
    _evaluate_auto_design_candidate,
    _fallback_shear_reinforcement_step_updates,
    _generate_escalated_shear_states,
    _generate_local_shear_states,
    _generate_shear_governing_candidates,
    _longitudinal_reo_detailing_failures,
    _normalise_visible_optimisation_contract,
    _normalise_terminal_exact_cleanup_card,
    _publishable_safe_combined_cleanup_row_from_evidence,
    _terminal_exact_cleanup_blocker_should_render_green,
    _terminal_green_card_is_safe,
    _terminal_green_unresolved_strength_families,
    _visible_safe_combined_cleanup_action_from_evidence,
    build_design_guide_card_view_model,
    evaluate_candidate_full,
    evaluate_candidate_fast,
    generate_less_shear_reo_variants,
)


def _base_state() -> dict:
    state = copy.deepcopy(SHARED_DEFAULTS)
    state.update(
        {
            "b": 300.0,
            "D": 600.0,
            "L": 6000.0,
            "fc": 40.0,
            "fsy": 500.0,
            "Ec": 30000.0,
            "Es": 200000.0,
            "cover_side": 40.0,
            "cover_bot": 40.0,
            "cover_top": 40.0,
            "rowgap_bot": 60.0,
            "bot1_layout_mode": "Count",
            "bot1_count": 4,
            "db_bot_1": 16,
            "bot2_layout_mode": "Count",
            "bot2_count": 0,
            "db_bot_2": 16,
            "top1_layout_mode": "Count",
            "top1_count": 2,
            "db_top_1": 12,
            "top2_layout_mode": "Count",
            "top2_count": 0,
            "db_top_2": 12,
            "lig_d": 10.0,
            "lig_legs": 2,
            "s_lig": 200.0,
            "uls_Mstar": 80.0,
            "uls_Vstar": 80.0,
            "Mu_star": 80.0,
            "Vu_star": 80.0,
        }
    )
    return state


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_detailing_fail_rolls_up_to_fail() -> dict:
    status = get_beam_overall_status({"strength_status": "PASS", "detailing_status": "FAIL"})
    _assert(status == BEAM_STATUS_FAIL, f"detailing FAIL rolled up as {status!r}")
    return {"overall_status": status}


def check_ku_fail_prevents_green_design_guide() -> dict:
    decision = resolve_design_guide_card(
        {
            "primary_item": {
                "title": "Design is efficient",
                "guidance_intent": "already_efficient",
                "display_truth": {
                    "display_truth_source": "published_summary",
                    "displayed_util": 1.01,
                    "displayed_within_target_band": False,
                    "source_summary_util": 1.01,
                },
                "button_contract": {},
            },
            "presentation_context": {"any_fail": True, "all_key_pass": False, "governing_action": "bending"},
        },
        summary={
            "statuses": {"bending": "FAIL", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
            "utils": {"bending": 1.01, "shear": 0.5},
            "any_fail": True,
            "all_key_pass": False,
            "worst_util": 1.01,
            "failure_details_by_family": {
                "bending": [
                    {
                        "title": "Ductility limit",
                        "text": "Ductility limit: k_u = 0.363 vs k_u,lim = 0.36",
                    }
                ]
            },
        },
    )
    presentation = decision["presentation"]
    _assert(presentation["critical_status"] == "FAIL", f"expected FAIL card, got {presentation}")
    _assert(not presentation["use_success_style"], "ductility FAIL produced green success styling")
    _assert("Ductility limit" in presentation["subtext"], "specific ductility row was not named")
    return {"status": presentation["critical_status"], "subtext": presentation["subtext"]}


def check_non_capacity_bending_failure_wording() -> dict:
    cases = [
        (
            "ductility",
            "Ductility limit",
            "Ductility limit: k_u = 0.367 vs k_u,lim = 0.36",
            ["Ductility limit", "k_u", "0.367", "0.36"],
            ["neutral axis", "ductile"],
        ),
        (
            "minimum_tensile_reinforcement",
            "Minimum tensile reinforcement",
            "Minimum tensile reinforcement: As,provided = 180 mm2 < As,min = 220 mm2",
            ["Minimum tensile reinforcement", "As,provided", "As,min"],
            ["baseline tensile capacity", "crack robustness", "brittle"],
        ),
        (
            "minimum_design_capacity",
            "Minimum design capacity",
            "Minimum design capacity: phiMu,min = 92.0 kNm > phiMu = 80.0 kNm",
            ["Minimum design capacity", "phiMu,min", "phiMu"],
            ["code minimum design strength", "applied demand is low"],
        ),
        (
            "positive_bending",
            "Flexural strength capacity",
            "Flexural strength capacity: Mu* = 160.0 kNm vs phiMu = 120.0 kNm",
            ["Flexural strength capacity", "Mu*", "phiMu"],
            ["Applied design moment", "design bending capacity"],
        ),
    ]
    details = {}
    for name, title, text, problem_tokens, cause_tokens in cases:
        item = {
            "failure_details_by_family": {
                "bending": [
                    {
                        "title": title,
                        "text": text,
                        "status": "FAIL",
                        "util": 1.02,
                    }
                ]
            },
            "family_status_current": {
                "bending": {"status": "FAIL", "util": 1.02},
                "shear": {"status": "PASS", "util": 0.3},
            },
            "button_contract": {
                "family": "bending",
                "updates": {"D": 650.0},
                "enabled": True,
                "actionable": True,
                "preview_pass": True,
            },
            "updates": {"D": 650.0},
        }
        section, rows = _design_guide_dashboard_reasons(
            item,
            state=_base_state(),
            actionable=True,
            status="FAIL",
        )
        problem = next((row.get("text", "") for row in rows if row.get("label") == "Problem"), "")
        cause = next((row.get("text", "") for row in rows if row.get("label") == "Cause"), "")
        _assert(section == "Why action is required", f"{name} did not render active-fail reason section")
        for token in problem_tokens:
            _assert(token in problem, f"{name} problem text missing {token!r}: {problem!r}")
        for token in cause_tokens:
            _assert(token in cause, f"{name} cause text missing {token!r}: {cause!r}")
        _assert("bending failed" not in problem.lower(), f"{name} used generic bending failed wording: {problem!r}")
        details[name] = {"problem": problem, "cause": cause}
    blocked_item = {
        "family_status_current": {
            "bending": {"status": "FAIL", "util": 1.02},
            "shear": {"status": "PASS", "util": 0.3},
        },
        "family": "bending",
        "exact_blockers_by_family": {
            "bending": {
                "family": "bending",
                "exact_blocker": True,
                "reason": "Ductility repair blocked: trial N20 bottom bars failed Ductility limit.",
                "failed_check_name": "Ductility limit",
                "failed_check_status": "FAIL",
                "failed_check_util": 1.02,
                "failed_check_capacity_or_limit": "k_u,lim = 0.36",
                "repair_search_ran": True,
                "repair_search_exhaustive": True,
            }
        },
    }
    section, rows = _design_guide_dashboard_reasons(
        blocked_item,
        state=_base_state(),
        actionable=False,
        status="error",
    )
    blocker_text = " ".join(str(row.get("text") or "") for row in rows)
    _assert(section == "Why repair is blocked", "blocked active failure did not render blocker section")
    _assert("Ductility repair blocked" in blocker_text, f"exact blocker reason was not shown: {blocker_text!r}")
    _assert("Ductility limit" in blocker_text, f"exact failed row was not preserved: {blocker_text!r}")
    _assert("maximum depth reached" not in blocker_text, f"generic max-depth constraint leaked: {blocker_text!r}")
    _assert("maximum width reached" not in blocker_text, f"generic max-width constraint leaked: {blocker_text!r}")
    details["active_failure_blocker_exact_evidence"] = {"section": section, "text": blocker_text}
    geometry_item = {
        "family_status_current": {
            "bending": {"status": "PASS", "util": 0.9},
            "shear": {"status": "PASS", "util": 0.3},
        },
        "family": "bending",
        "button_contract": {
            "family": "bending",
            "updates": {"D": 650.0},
            "enabled": True,
            "actionable": True,
            "preview_pass": True,
        },
        "updates": {"D": 650.0},
    }
    _section, geometry_rows = _design_guide_dashboard_reasons(
        geometry_item,
        state=_base_state(),
        actionable=True,
        status="action",
    )
    geometry_text = " ".join(str(row.get("text") or "") for row in geometry_rows)
    _assert("preferred 2:1 proportion guidance" in geometry_text, f"D/b advisory wording missing: {geometry_text!r}")
    _assert("kept near 2:1" not in geometry_text, f"D/b wording overclaimed guarantee: {geometry_text!r}")
    _assert("D/b requirement" not in geometry_text, f"D/b wording implied hard requirement: {geometry_text!r}")
    _assert("D/b constraint" not in geometry_text, f"D/b wording implied hard constraint: {geometry_text!r}")
    details["db_ratio_advisory_wording"] = {"section": _section, "text": geometry_text}
    return details


def check_low_bending_util_without_evidence_not_green() -> dict:
    decision = resolve_design_guide_card(
        {
            "primary_item": {
                "title": "Design is efficient",
                "guidance_intent": "already_efficient",
                "display_truth": {
                    "display_truth_source": "published_summary",
                    "displayed_util": 0.9,
                    "displayed_within_target_band": True,
                    "source_summary_util": 0.9,
                },
                "button_contract": {},
            },
            "presentation_context": {"any_fail": False, "all_key_pass": True, "governing_action": "shear"},
            "candidate_search_evidence": {},
        },
        summary={
            "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
            "utils": {"bending": 0.45, "shear": 0.9, "crack": 0.0, "deflection": 0.0},
            "any_fail": False,
            "all_key_pass": True,
            "worst_util": 0.9,
        },
    )
    presentation = decision["presentation"]
    _assert(not presentation["use_success_style"], "low bending util without family proof produced green card")
    _assert(
        decision["debug"]["decision_reason"] != "selected_already_efficient",
        "low bending util without cleanup proof selected already_efficient",
    )
    return {"theme": presentation["theme"], "terminal_state": presentation.get("design_guide_terminal_state")}


def check_invalid_longitudinal_candidate_rejected() -> dict:
    state = _base_state()
    state.update({"b": 200.0, "cover_side": 40.0, "lig_d": 10.0, "bot1_count": 6, "db_bot_1": 20})
    failures = _longitudinal_reo_detailing_failures(state)
    _assert(failures, "invalid longitudinal layout did not produce spacing/detailing failure")
    candidate = evaluate_candidate_full(
        state,
        source="focused_invalid_longitudinal_reo_candidate",
        label="Invalid longitudinal reo candidate",
        action_type="apply_resolved_candidate",
        updates={"bot1_count": 6, "db_bot_1": 20},
    )
    overview = dict(candidate.get("overview") or {})
    _assert(overview.get("any_fail") is True, f"invalid reo candidate did not fail overview: {overview}")
    _assert(candidate.get("is_compliant") is False, "invalid reo candidate remained compliant")
    return {"failures": failures, "rejection_reason": candidate.get("rejection_reason")}


def check_wide_two_bar_longitudinal_spacing_rejected() -> dict:
    state = _base_state()
    state.update(
        {
            "b": 730.0,
            "bw": 730.0,
            "cover_side": 40.0,
            "lig_d": 10.0,
            "bot1_count": 2,
            "bot_row_1_bars": 2,
            "db_bot_1": 16,
            "bot_row_1_dia": 16,
            "top1_count": 3,
            "top_row_1_bars": 3,
            "db_top_1": 12,
            "top_row_1_dia": 12,
        }
    )
    failures = _longitudinal_reo_detailing_failures(state)
    _assert(
        any("300 mm maximum" in str(reason) for reason in failures),
        f"wide two-bar longitudinal row did not fail max c/c spacing: {failures}",
    )
    candidate = evaluate_candidate_full(
        state,
        source="focused_wide_two_bar_longitudinal_spacing",
        label="Wide two-bar longitudinal spacing",
        action_type="apply_resolved_candidate",
        updates={"b": 730.0, "bw": 730.0, "bot1_count": 2, "bot_row_1_bars": 2},
    )
    overview = dict(candidate.get("overview") or {})
    _assert(overview.get("any_fail") is True, f"wide two-bar spacing did not fail overview: {overview}")
    _assert(candidate.get("is_compliant") is False, "wide two-bar spacing candidate remained compliant")
    return {"failures": failures, "rejection_reason": candidate.get("rejection_reason")}


def check_zero_vu_invalid_shear_links_fail_detailing() -> dict:
    state = _base_state()
    state.update({"uls_Vstar": 0.0, "Vu_star": 0.0, "lig_d": 10.0, "lig_legs": 1, "s_lig": 1000.0})
    pack = build_shear_check_rows_from_state(state)
    rows = list(pack.get("rows") or [])
    failing = [
        row for row in rows
        if str(row.get("title") or "") == "Shear link detailing"
        and str(row.get("status") or "").upper() == "FAIL"
    ]
    _assert(failing, "Vu=0 invalid shear links did not fail detailing")
    _assert(str(pack.get("summary_status") or "").upper() == "FAIL", f"summary did not fail: {pack.get('summary_status')}")
    return {"summary_status": pack.get("summary_status"), "reason": pack.get("summary_reason")}


def check_zero_vu_no_links_not_flagged_as_invalid_link_detailing() -> dict:
    state = _base_state()
    state.update({"uls_Vstar": 0.0, "Vu_star": 0.0, "lig_d": 0.0, "lig_legs": 0, "s_lig": 200.0})
    pack = build_shear_check_rows_from_state(state)
    rows = list(pack.get("rows") or [])
    link_rows = [
        row for row in rows
        if str(row.get("title") or "") == "Shear link detailing"
    ]
    _assert(link_rows, "missing Shear link detailing row for zero-link case")
    link_status = str(link_rows[0].get("status") or "").upper()
    _assert(link_status != "FAIL", f"zero Vu/no-links was flagged as failed link detailing: {link_rows[0]}")
    _assert(
        str(pack.get("summary_governing_source") or "") != "shear_link_detailing",
        f"zero Vu/no-links incorrectly governed by link detailing: {pack.get('summary_reason')}",
    )
    return {
        "link_detailing_status": link_rows[0].get("status"),
        "summary_status": pack.get("summary_status"),
        "summary_governing_source": pack.get("summary_governing_source"),
    }


def check_auto_design_rejects_invalid_shear_link_spacing() -> dict:
    state = _base_state()
    state.update(
        {
            "D": 650.0,
            "uls_Vstar": 200.0,
            "Vu_star": 200.0,
            "lig_d": 16.0,
            "lig_legs": 2,
            "s_lig": 475.0,
            "shear_required_spacing_mm": 430.0,
        }
    )
    fast = evaluate_candidate_fast(
        state,
        {
            "seed_overview": {"statuses": {}, "utils": {}, "packs": {}},
            "actions": {"Mu": state["Mu_star"], "Vu": state["Vu_star"]},
        },
    )
    full = evaluate_candidate_full(
        state,
        source="focused_invalid_shear_link_spacing_candidate",
        label="Invalid shear link spacing candidate",
        action_type="apply_resolved_candidate",
        updates={"lig_d": 16, "lig_legs": 2, "s_lig": 475.0},
    )
    for label, candidate in (("fast", fast), ("full", full)):
        overview = dict((candidate or {}).get("overview") or {})
        _assert(overview.get("any_fail") is True, f"{label} invalid shear spacing did not fail overview: {overview}")
        _assert(candidate.get("is_compliant") is False, f"{label} invalid shear spacing remained compliant")
        _assert(
            str((overview.get("statuses") or {}).get("shear") or "").upper() == "FAIL",
            f"{label} invalid shear spacing did not fail shear status: {overview.get('statuses')}",
        )
        _assert(
            "Shear link detailing" in json.dumps(overview.get("failure_details_by_family") or {}, default=str),
            f"{label} invalid shear spacing did not publish shear-link blocker evidence",
        )
    ordering = _assert_shear_diameter_before_legs_order()
    return {
        "fast_rejection_reason": fast.get("rejection_reason"),
        "full_rejection_reason": full.get("rejection_reason"),
        "full_failure_details": (full.get("overview") or {}).get("failure_details_by_family"),
        "diameter_before_legs_order": ordering,
    }


def check_zero_bending_live_shear_cleanup_can_reduce_dia_legs_before_spacing_limit() -> dict:
    state = _base_state()
    state.update(
        {
            "b": 600.0,
            "bw": 600.0,
            "D": 350.0,
            "Mu_star": 0.0,
            "uls_Mstar": 0.0,
            "Vu_star": 300.0,
            "uls_Vstar": 300.0,
            "bot1_count": 3,
            "bot_row_1_bars": 3,
            "db_bot_1": 20.0,
            "bot_row_1_dia": 20.0,
            "top1_count": 2,
            "top_row_1_bars": 2,
            "db_top_1": 10.0,
            "top_row_1_dia": 10.0,
            "lig_d": 16.0,
            "lig_legs": 3,
            "s_lig": 250.0,
        }
    )
    variants = list(generate_less_shear_reo_variants({"state": state}, {}) or [])
    target_state = next(
        (
            variant
            for variant in variants
            if int(variant.get("lig_d") or -1) == 12
            and int(variant.get("lig_legs") or -1) == 2
            and abs(float(variant.get("s_lig") or 0.0) - 200.0) <= 1e-9
        ),
        None,
    )
    _assert(
        target_state is not None,
        "zero-bending/live-shear cleanup did not generate the N12-2 @ 200 candidate before spacing-limit blockers",
    )
    candidate = evaluate_candidate_full(
        target_state,
        source="focused_zero_bending_live_shear_cleanup_candidate",
        label="Zero bending live shear cleanup candidate",
        action_type="apply_resolved_candidate",
        updates={"lig_d": 12, "lig_legs": 2, "s_lig": 200.0},
    )
    overview = dict(candidate.get("overview") or {})
    utils = dict(overview.get("utils") or {})
    statuses = dict(overview.get("statuses") or {})
    shear_util = float(utils.get("shear") or 0.0)
    _assert(candidate.get("is_compliant") is True, f"N12-2 @ 200 cleanup candidate was rejected: {candidate.get('rejection_reason')}")
    _assert(0.88 <= shear_util <= 0.95, f"N12-2 @ 200 cleanup candidate shear util outside target band: {shear_util}")
    _assert(
        all(str(status or "").upper() == "PASS" for status in statuses.values()),
        f"N12-2 @ 200 cleanup candidate did not pass all overview families: {statuses}",
    )
    return {
        "variant_count": len(variants),
        "selected": {"lig_d": 12, "lig_legs": 2, "s_lig": 200.0},
        "shear_util": shear_util,
        "statuses": statuses,
    }


def check_terminal_exact_cleanup_stop_is_not_blue_blocker() -> dict:
    exact = {
        "bending": {
            "family": "bending",
            "exact_blocker": True,
            "search_ran": True,
            "search_exhaustive": True,
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "target_band_search_ran": True,
            "target_band_search_exhaustive": True,
            "current_util": 0.0,
            "failed_check_name": "practical minimum geometry and bottom reinforcement",
            "failed_check_status": "BLOCKED_BY_PRACTICAL_MINIMUM",
            "failed_check_util": 0.0,
            "failed_check_demand": 0.0,
            "failed_check_capacity_or_limit": "b >= 250 mm, D >= 300 mm, 3-N10 bottom bars",
            "reason": "The section is already at the practical minimum geometry and bottom reinforcement floor.",
            "why_reduction_would_hurt_other_design_elements": "The section is already at the practical minimum geometry and bottom reinforcement floor.",
            "attempted_candidate_count": 2,
            "previewed_candidate_count": 2,
            "safe_candidate_count": 0,
            "executable_candidate_count": 0,
            "target_band_candidate_count": 0,
            "executable_target_band_candidate_count": 0,
        },
        "shear": {
            "family": "shear",
            "exact_blocker": True,
            "search_ran": True,
            "search_exhaustive": True,
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "target_band_search_ran": True,
            "target_band_search_exhaustive": True,
            "current_util": 0.0,
            "failed_check_name": "minimum shear reinforcement floor",
            "failed_check_status": "BLOCKED",
            "failed_check_util": 0.0,
            "failed_check_demand": "no shear demand",
            "failed_check_capacity_or_limit": "no shear links active",
            "reason": "Shear links are already removed; no further shear-link cleanup is available.",
            "why_reduction_would_hurt_other_design_elements": "Shear links are already removed; no further shear-link cleanup is available.",
            "attempted_candidate_count": 1,
            "previewed_candidate_count": 1,
            "safe_candidate_count": 0,
            "executable_candidate_count": 0,
            "target_band_candidate_count": 0,
            "executable_target_band_candidate_count": 0,
        },
    }
    overview = {
        "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": 0.0, "shear": 0.0, "crack": 0.0, "deflection": 0.0},
        "any_fail": False,
        "any_warn": False,
        "all_key_pass": True,
        "worst_util": 0.0,
    }
    item = {
        "title_main": "Design is efficient - no further safe cleanup available",
        "title": "Design is efficient - no further safe cleanup available",
        "status": "PASS",
        "bucket": "pass",
        "guidance_intent": "already_efficient",
        "design_guide_terminal_state": "optimal",
        "post_click_design_guide_state": "accepted_green",
        "terminal_cleanup_state": "optimal",
        "primary_card_actionable": False,
        "button_contract": {"enabled": False, "actionable": False, "updates": {}},
        "exact_blockers_by_family": exact,
        "post_click_exact_blockers_by_family": exact,
        "primary_action": "Bending and shear stop reasons are published by family.",
        "display_truth": {
            "display_truth_source": "published_summary",
            "displayed_util": 0.0,
            "displayed_within_target_band": False,
            "source_summary_util": 0.0,
        },
    }
    vm = build_design_guide_card_view_model(
        item,
        overview,
        {"exact_blockers_by_family": exact, "post_click_exact_blockers_by_family": exact},
        state=_base_state(),
        item_bucket="pass",
        use_success_style=True,
        display_title="Design is efficient - no further safe cleanup available",
        actionable=False,
    )
    title = str(vm.get("title") or vm.get("title_main") or "")
    _assert("cleanup blocked" not in title.lower(), f"accepted exact-stop card was restamped blue: {title!r}")
    _assert(str(vm.get("status") or "").upper() != "BLOCKED", f"accepted exact-stop status became BLOCKED: {vm}")
    _assert(str(vm.get("tone") or "") == "pass", f"accepted exact-stop was not green/pass styled: {vm}")
    details_exact = dict((vm.get("details") or {}).get("exact_blockers_by_family") or {})
    _assert({"bending", "shear"}.issubset(details_exact), "accepted exact-stop did not preserve family exact blockers")
    return {"title": title, "status": vm.get("status"), "tone": vm.get("tone"), "families": sorted(details_exact)}


def check_shear_only_terminal_exact_cleanup_stop_is_not_blue_blocker() -> dict:
    exact = {
        "shear": {
            "family": "shear",
            "exact_blocker": True,
            "search_ran": True,
            "search_exhaustive": True,
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "target_band_search_ran": True,
            "target_band_search_exhaustive": True,
            "current_util": 0.75,
            "failed_check_name": "final accepted shear utilisation threshold",
            "failed_check_status": "below_final_accepted_threshold",
            "failed_check_util": 0.75,
            "failed_check_demand": 300.0,
            "failed_check_capacity_or_limit": 0.85,
            "reason": "No executor-backed shear cleanup candidate reaches the final accepted threshold while preserving all required checks.",
            "why_reduction_would_hurt_other_design_elements": "No executor-backed shear cleanup candidate reaches the final accepted threshold while preserving all required checks.",
            "attempted_candidate_count": 12,
            "previewed_candidate_count": 12,
            "safe_candidate_count": 0,
            "executable_candidate_count": 0,
            "target_band_candidate_count": 0,
            "executable_target_band_candidate_count": 0,
        }
    }
    overview = {
        "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": 0.92, "shear": 0.75, "crack": 0.0, "deflection": 0.0},
        "any_fail": False,
        "any_warn": False,
        "all_key_pass": True,
        "worst_util": 0.92,
    }
    item = {
        "family": "shear",
        "check_key": "shear",
        "title_main": "Shear cleanup blocked by final efficiency threshold",
        "title": "Shear cleanup blocked by final efficiency threshold",
        "status": "EFFICIENCY",
        "bucket": "efficiency",
        "guidance_intent": "specific_blocker",
        "primary_card_actionable": False,
        "button_contract": {"enabled": False, "actionable": False, "updates": {}, "family": "shear"},
        "exact_blockers_by_family": exact,
        "post_click_exact_blockers_by_family": exact,
        "primary_action": "Open for engineering detail.",
    }
    should_render_green = _terminal_exact_cleanup_blocker_should_render_green(
        item,
        overview,
        item["button_contract"],
        exact,
    )
    _assert(should_render_green, "shear-only exact-stop blocker did not qualify for terminal green normalisation")
    normalised, contract = _normalise_terminal_exact_cleanup_card(
        item,
        overview,
        item["button_contract"],
        exact,
    )
    _assert("cleanup blocked" not in str(normalised.get("title") or "").lower(), f"shear-only card stayed blocked: {normalised}")
    _assert(str(normalised.get("status") or "").upper() == "PASS", f"shear-only status not PASS: {normalised}")
    _assert(str(normalised.get("terminal_cleanup_state") or "") == "optimal", f"shear-only terminal state not optimal: {normalised}")
    _assert(not bool(contract.get("enabled")), f"terminal exact-stop should not publish a CTA: {contract}")
    _assert("shear" in dict(normalised.get("exact_blockers_by_family") or {}), "shear exact blocker was dropped")
    return {
        "title": normalised.get("title"),
        "status": normalised.get("status"),
        "terminal_cleanup_state": normalised.get("terminal_cleanup_state"),
        "families": sorted(dict(normalised.get("exact_blockers_by_family") or {})),
    }


def check_terminal_green_requires_resolved_strength_families() -> dict:
    overview = {
        "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": 0.58, "shear": 0.57, "crack": 0.0, "deflection": 0.0},
        "any_fail": False,
        "any_warn": False,
        "all_key_pass": True,
        "worst_util": 0.58,
    }
    unresolved = _terminal_green_unresolved_strength_families(
        overview,
        {
            "family_status_current": {
                "bending": {"status": "PASS", "util": 0.58},
                "shear": {"status": "PASS", "util": 0.57},
            }
        },
        state=_base_state(),
    )
    _assert(unresolved == ["bending", "shear"], f"unresolved low-util families not detected: {unresolved}")
    _assert(
        not _terminal_green_card_is_safe(overview, {}, state=_base_state()),
        "terminal green was allowed without exact blockers for low-util strength families",
    )

    fail_rows_safe = _terminal_green_card_is_safe(
        {"statuses": {"bending": "PASS", "shear": "PASS"}, "utils": {"bending": 0.92, "shear": 0.9}},
        {"family_status_current": {"shear": {"status": "FAIL", "util": 1.1}}},
        state=_base_state(),
    )
    _assert(not fail_rows_safe, "terminal green was allowed while source family row still showed FAIL")
    return {"unresolved_without_blockers": unresolved, "fail_row_safe": fail_rows_safe}


def check_disabled_action_cleanup_blocker_html_obeys_terminal_policy() -> dict:
    exact = {
        "bending": {
            "family": "bending",
            "exact_blocker": True,
            "cleanup_search_exhaustive": True,
            "target_band_search_exhaustive": True,
            "failed_check_name": "final accepted bending utilisation threshold",
            "failed_check_status": "below_final_accepted_threshold",
            "failed_check_util": 0.76,
            "failed_check_demand": 120.0,
            "failed_check_capacity_or_limit": 0.85,
            "reason": "No executor-backed bending cleanup candidate reaches the final accepted threshold while preserving all required checks.",
            "executable_candidate_count": 0,
            "executable_target_band_candidate_count": 0,
        },
        "shear": {
            "family": "shear",
            "exact_blocker": True,
            "cleanup_search_exhaustive": True,
            "target_band_search_exhaustive": True,
            "failed_check_name": "final accepted shear utilisation threshold",
            "failed_check_status": "below_final_accepted_threshold",
            "failed_check_util": 0.47,
            "failed_check_demand": 80.0,
            "failed_check_capacity_or_limit": 0.85,
            "reason": "No executor-backed shear cleanup candidate reaches the final accepted threshold while preserving all required checks.",
            "executable_candidate_count": 0,
            "executable_target_band_candidate_count": 0,
        },
    }
    overview = {
        "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": 0.76, "shear": 0.47, "crack": 0.0, "deflection": 0.0},
        "any_fail": False,
        "any_warn": False,
        "all_key_pass": True,
        "worst_util": 0.76,
        "family_status_current": {
            "bending": {"status": "PASS", "util": 0.76},
            "shear": {"status": "PASS", "util": 0.47},
            "crack": {"status": "PASS", "util": 0.0},
            "deflection": {"status": "PASS", "util": 0.0},
        },
    }
    details = {
        "title": "Bending and shear cleanup blocked",
        "status": "EFFICIENCY",
        "bucket": "efficiency",
        "guidance_intent": "specific_blocker",
        "primary_card_actionable": False,
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "updates": {},
            "blocking_reason": "Exact cleanup stop evidence is published by family.",
        },
        "current_overview": overview,
        # Regression shape from the browser replay: the visible item was a
        # shear-only blocker, while the full overview/evidence still proved a
        # safe combined bending + shear cleanup action.
        "family_status_current": {"shear": overview["family_status_current"]["shear"]},
        "exact_blockers_by_family": exact,
        "post_click_exact_blockers_by_family": exact,
        "blocker_attempts_by_family": exact,
        "candidate_search_evidence": {
            "cleanup_search_exhaustive": True,
            "target_band_search_exhaustive": True,
            "exact_blockers_by_family": exact,
        },
    }
    should_render_green = _design_guide_should_render_passing_terminal_exact_stop(
        details,
        overview,
        details,
        None,
        contract=details["button_contract"],
        exact_blockers=exact,
        state=_base_state(),
    )
    _assert(should_render_green, "policy helper did not accept pass-current terminal cleanup stop")
    html = _design_guide_dashboard_card_html_with_render_model(
        {
            "status": "action",
            "pill": "ACTION",
            "title": "Bending and shear cleanup blocked",
            "summary_line": "Open for engineering detail.",
            "governing_label": "Bending 0.76 / Shear 0.47",
            "details": details,
            "cta": {"enabled": False},
            "current": [
                {"family": "bending", "label": "Bending", "value": "0.76", "status": "PASS", "tone": "green"},
                {"family": "shear", "label": "Shear", "value": "0.47", "status": "PASS", "tone": "green"},
            ],
            "reasons": [],
        },
        card_class="fast-guidance-item efficiency dg-card--action",
        source="product_correctness_terminal_cleanup_stop",
    )
    _assert("dg-card--pass" in html, "disabled action terminal stop did not render as pass card")
    _assert("data-testid='design-guide-status-pill'>PASS" in html, "terminal stop status pill is not PASS")
    _assert("Bending and shear cleanup blocked" not in html.split("data-testid='design-guide-title'", 1)[1][:200], "collapsed title stayed blocked")
    _assert("No executor-backed bending cleanup candidate" in html, "bending stop reason was dropped")
    _assert("No executor-backed shear cleanup candidate" in html, "shear stop reason was dropped")
    return {"html_contains_pass": "dg-card--pass" in html, "families": sorted(exact)}


def check_publishable_safe_combined_cleanup_candidate_must_not_render_blocked() -> dict:
    state = _base_state()
    state.update(
        {
            "b": 350.0,
            "D": 350.0,
            "uls_Mstar": 115.0,
            "Mu_star": 115.0,
            "uls_Vstar": 30.8,
            "Vu_star": 30.8,
            "bot_row_count": 1,
            "bot1_count": 3,
            "bot_row_1_bars": 3,
            "db_bot_1": 24,
            "bot_row_1_dia": 24,
            "lig_d": 0,
            "lig_legs": 0,
            "s_lig": 200.0,
        }
    )
    overview = {
        "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": 0.76, "shear": 0.47, "crack": 0.0, "deflection": 0.0},
        "any_fail": False,
        "any_warn": False,
        "all_key_pass": True,
        "worst_util": 0.76,
        "family_status_current": {
            "bending": {"status": "PASS", "util": 0.76},
            "shear": {"status": "PASS", "util": 0.47},
        },
    }
    updates = {
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 150.0,
        "bot_row_count": 1,
        "bot_row_1_bars": 4,
        "bot_row_1_dia": 20,
        "bot1_count": 4,
        "db_bot_1": 20,
    }
    evidence = {
        "search_scope": "combined_best_safe_shear_plus_bending_cleanup",
        "candidate_search_exhaustive": True,
        "candidate_rows": [
            {
                "candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
                "title": "Shear and bending cleanup - one-click optimisation",
                "proposed_updates": dict(updates),
                "preview_statuses": {
                    "bending": "PASS",
                    "shear": "PASS",
                    "crack": "PASS",
                    "deflection": "PASS",
                },
                "preview_pass": True,
                "safe_executor_backed": True,
                "is_executable": True,
                "preview_util": 0.807,
                "affected_family": "combined",
            }
        ],
        "safe_executor_backed_candidates_count": 1,
    }
    debug_sink = {"candidate_search_evidence": dict(evidence)}
    stale_blocked_item = {
        "title": "Bending and shear cleanup blocked",
        "title_main": "Bending and shear cleanup blocked",
        "family": "shear",
        "check_key": "shear",
        "status": "EFFICIENCY",
        "guidance_intent": "specific_blocker",
        "primary_card_actionable": False,
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "family": "shear",
            "updates": {},
            "preview_pass": False,
            "blocking_reason": "Shear links are already removed.",
        },
        "family_status_current": overview["family_status_current"],
        "candidate_search_evidence": {"family": "shear", "best_safe_candidate_applied": True},
        "exact_blockers_by_family": {
            "shear": {
                "family": "shear",
                "exact_blocker": True,
                "cleanup_search_exhaustive": True,
                "failed_check_name": "minimum shear reinforcement floor",
                "reason": "Shear links are already removed.",
                "executable_target_band_candidate_count": 0,
            }
        },
    }
    row = _publishable_safe_combined_cleanup_row_from_evidence(evidence, state)
    _assert(row, "publishable combined candidate row was not detected")
    action_item = _visible_safe_combined_cleanup_action_from_evidence(
        stale_blocked_item,
        overview,
        state,
        debug_sink=debug_sink,
    )
    _assert(isinstance(action_item, dict), "safe combined candidate was not promoted to an action item")
    contract = dict(action_item.get("button_contract") or {})
    _assert(_design_guide_button_contract_enabled(contract), f"promoted combined candidate contract disabled: {contract}")
    _assert("cleanup blocked" not in str(action_item.get("title") or "").lower(), f"promoted action stayed blocked: {action_item}")
    _assert(contract.get("candidate_id") == "combined_best_safe_shear_plus_bending_cleanup", f"wrong candidate id: {contract}")
    _assert(set(contract.get("updates") or {}) & {"lig_d", "lig_legs", "s_lig"}, "promoted updates did not include shear links")
    _assert(set(contract.get("updates") or {}) & {"bot_row_1_bars", "bot_row_1_dia", "bot1_count", "db_bot_1"}, "promoted updates did not include bottom reo")

    normalised = _normalise_visible_optimisation_contract(
        stale_blocked_item,
        state=state,
        overview=overview,
        debug_sink=debug_sink,
    )
    normalised_contract = dict((normalised or {}).get("button_contract") or {})
    _assert(
        _design_guide_button_contract_enabled(normalised_contract),
        f"normal visible handoff did not publish safe combined candidate: {normalised_contract}",
    )

    nested_evidence = {
        "family": "shear",
        "best_safe_candidate_applied": True,
        "shear_cleanup_evidence": dict(evidence),
    }
    nested_row = _publishable_safe_combined_cleanup_row_from_evidence(nested_evidence, state)
    _assert(nested_row, "nested publishable combined candidate row was not detected")
    nested_item = dict(stale_blocked_item)
    nested_item["candidate_search_evidence"] = {"family": "shear", "best_safe_candidate_applied": True}
    nested_normalised = _normalise_visible_optimisation_contract(
        nested_item,
        state=state,
        overview=overview,
        debug_sink={"candidate_search_evidence": dict(nested_evidence)},
    )
    nested_contract = dict((nested_normalised or {}).get("button_contract") or {})
    _assert(
        _design_guide_button_contract_enabled(nested_contract),
        f"nested visible handoff did not publish safe combined candidate: {nested_contract}",
    )
    return {
        "candidate_id": normalised_contract.get("candidate_id"),
        "nested_candidate_id": nested_contract.get("candidate_id"),
        "updates": normalised_contract.get("updates"),
    }


def check_terminal_no_further_cleanup_must_render_green() -> dict:
    exact = {
        "bending": {
            "family": "bending",
            "exact_blocker": True,
            "cleanup_search_exhaustive": True,
            "target_band_search_exhaustive": True,
            "failed_check_name": "final accepted bending utilisation threshold",
            "reason": "No further bending cleanup is available.",
            "executable_target_band_candidate_count": 0,
        },
        "shear": {
            "family": "shear",
            "exact_blocker": True,
            "cleanup_search_exhaustive": True,
            "target_band_search_exhaustive": True,
            "failed_check_name": "minimum shear reinforcement floor",
            "reason": "No further shear cleanup is available.",
            "executable_target_band_candidate_count": 0,
        },
    }
    overview = {
        "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": 0.76, "shear": 0.47},
        "any_fail": False,
        "all_key_pass": True,
    }
    item = {
        "title": "Bending and shear cleanup blocked",
        "status": "EFFICIENCY",
        "guidance_intent": "specific_blocker",
        "primary_card_actionable": False,
        "button_contract": {"enabled": False, "actionable": False, "updates": {}},
        "exact_blockers_by_family": exact,
        "post_click_exact_blockers_by_family": exact,
    }
    _assert(
        _terminal_exact_cleanup_blocker_should_render_green(item, overview, item["button_contract"], exact),
        "terminal exact-stop did not qualify for green normalisation",
    )
    normalised, contract = _normalise_terminal_exact_cleanup_card(item, overview, item["button_contract"], exact)
    _assert(str(normalised.get("status") or "").upper() == "PASS", f"terminal exact stop did not render PASS: {normalised}")
    _assert("cleanup blocked" not in str(normalised.get("title") or "").lower(), f"terminal exact stop stayed blocked: {normalised}")
    _assert(not _design_guide_button_contract_enabled(contract), f"terminal exact stop published CTA: {contract}")
    preserved = dict(normalised.get("exact_blockers_by_family") or {})
    _assert({"bending", "shear"}.issubset(preserved), "terminal exact stop dropped blocker evidence")
    return {"title": normalised.get("title"), "families": sorted(preserved)}


def _active_failure_policy_fixture() -> tuple[dict, dict, dict]:
    overview = {
        "statuses": {"bending": "FAIL", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": 1.12, "shear": 0.70},
        "any_fail": True,
        "all_key_pass": False,
        "family_status_current": {
            "bending": {"status": "FAIL", "util": 1.12},
            "shear": {"status": "PASS", "util": 0.70},
            "crack": {"status": "PASS", "util": 0.0},
            "deflection": {"status": "PASS", "util": 0.0},
        },
    }
    exact = {
        "bending": {
            "family": "bending",
            "exact_blocker": True,
            "cleanup_search_exhaustive": True,
            "failed_check_name": "Flexural strength capacity",
            "reason": "Bending repair is blocked by ductility.",
            "executable_target_band_candidate_count": 0,
        }
    }
    item = {
        "title": "Bending repair blocked",
        "title_main": "Bending repair blocked",
        "family": "bending",
        "check_key": "bending",
        "status": "FAIL",
        "bucket": "fail",
        "guidance_intent": "specific_blocker",
        "primary_card_actionable": False,
        "button_contract": {"enabled": False, "actionable": False, "updates": {}, "family": "bending"},
        "exact_blockers_by_family": exact,
        "family_status_current": overview["family_status_current"],
    }
    return overview, exact, item


def check_locked_active_failure_blocker_stays_blocked_with_exact_proof() -> dict:
    overview, exact, item = _active_failure_policy_fixture()
    should_render_green = _terminal_exact_cleanup_blocker_should_render_green(
        item,
        overview,
        item["button_contract"],
        exact,
    )
    _assert(not should_render_green, "active failure blocker qualified for terminal green")
    _assert(
        not _terminal_green_card_is_safe(overview, item, state=_base_state(), exact_blockers=exact),
        "active failure was marked terminal safe",
    )
    state = _base_state()
    state["optimisation_lock_geometry"] = True
    vm = build_design_guide_card_view_model(
        item,
        overview,
        {},
        state=state,
        item_bucket="fail",
        display_title="Bending repair blocked",
        actionable=False,
    )
    _assert(vm["pill"] == "BLOCKED", f"locked exact blocker did not stay BLOCKED: {vm}")
    _assert("repair blocked" in vm["title"].lower(), f"locked exact blocker title changed unexpectedly: {vm}")
    preserved = dict(vm.get("details", {}).get("exact_blockers_by_family") or {})
    _assert("bending" in preserved, "locked active failure blocker dropped exact proof")
    return {"green_allowed": should_render_green, "pill": vm["pill"], "title": vm["title"]}


def check_unlocked_active_failure_without_apply_cta_fails_policy() -> dict:
    overview, exact, item = _active_failure_policy_fixture()
    state = _base_state()
    state["optimisation_lock_geometry"] = False
    try:
        build_design_guide_card_view_model(
            item,
            overview,
            {},
            state=state,
            item_bucket="fail",
            display_title="Bending repair blocked",
            actionable=False,
        )
    except RuntimeError as exc:
        text = str(exc)
        _assert("unlocked active failure" in text.lower(), f"wrong policy failure text: {text}")
        _assert("apply cta" in text.lower(), f"policy failure does not require Apply CTA: {text}")
        return {"policy_failure": text}
    raise AssertionError("unlocked active failure without Apply CTA rendered a user-facing card")


def check_stale_blocker_cannot_override_unlocked_safe_repair_candidate() -> dict:
    overview, exact, item = _active_failure_policy_fixture()
    state = _base_state()
    state["optimisation_lock_geometry"] = False
    updates = {"bot_row_1_bars": 5, "bot1_count": 5}
    contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "updates": dict(updates),
        "preview_pass": True,
        "expected_util": 0.94,
        "source_candidate_id": "safe_bending_repair_candidate",
        "candidate_id": "safe_bending_repair_candidate",
    }
    debug_payload = {
        "displayed_guidance_intent_items": [
            {
                "title": "Bending capacity is low - one-click repair",
                "family": "bending",
                "check_key": "bending",
                "action_type": "apply_resolved_candidate",
                "button_contract": dict(contract),
                "displayed_util": 0.94,
            }
        ]
    }
    vm = build_design_guide_card_view_model(
        item,
        overview,
        debug_payload,
        state=state,
        item_bucket="fail",
        display_title="Bending repair blocked",
        actionable=True,
    )
    _assert(vm.get("cta", {}).get("enabled"), f"safe repair candidate was not actionable: {vm}")
    _assert(vm.get("cta", {}).get("payload_id") == "safe_bending_repair_candidate", f"wrong repair candidate: {vm}")
    _assert("blocked" not in vm["title"].lower(), f"safe repair candidate stayed blocked: {vm}")
    _assert(vm["pill"] == "ACTION", f"safe repair candidate did not render ACTION: {vm}")
    return {"pill": vm["pill"], "title": vm["title"], "candidate": vm.get("cta", {}).get("payload_id")}


def check_rescue_seed_updates_include_canonical_reo_mirrors() -> dict:
    seed = dict(((RESCUE_SEED_LIBRARY.get("combined") or {}).get("extreme")) or {})
    updates = dict(seed.get("updates") or {})
    required_equal_pairs = [
        ("bot1_count", "bot_row_1_bars"),
        ("db_bot_1", "bot_row_1_dia"),
        ("top1_count", "top_row_1_bars"),
        ("db_top_1", "top_row_1_dia"),
    ]
    required_canonical_fields = [
        "bot_row_count",
        "bot_row_1_bars",
        "bot_row_1_dia",
        "top_row_count",
        "top_row_1_bars",
        "top_row_1_dia",
    ]
    for key in required_canonical_fields:
        _assert(key in updates, f"combined rescue seed missing canonical field {key}")
    legacy_projection_present = True
    for legacy_key, canonical_key in required_equal_pairs:
        _assert(canonical_key in updates, f"combined rescue seed missing {canonical_key}")
        if legacy_key in updates:
            _assert(
                updates.get(legacy_key) == updates.get(canonical_key),
                f"combined rescue seed {legacy_key}={updates.get(legacy_key)!r} "
                f"does not match {canonical_key}={updates.get(canonical_key)!r}",
            )
        else:
            legacy_projection_present = False
    _assert(updates.get("bot_row_count") == 1, "combined rescue seed missing canonical bottom row count")
    _assert(updates.get("top_row_count") == 1, "combined rescue seed missing canonical top row count")
    return {
        "seed": seed.get("key"),
        "bottom": [updates.get("bot_row_1_bars"), updates.get("bot_row_1_dia")],
        "top": [updates.get("top_row_1_bars"), updates.get("top_row_1_dia")],
        "legacy_projection_present": legacy_projection_present,
    }


def check_unlocked_combined_fail_rescue_seed_previews_pass() -> dict:
    state = _base_state()
    state.update(
        {
            "b": 300.0,
            "D": 500.0,
            "L": 5800.0,
            "fc": 32.0,
            "bot1_count": 3,
            "db_bot_1": 20,
            "bot_row_1_bars": 3,
            "bot_row_1_dia": 20,
            "top1_count": 2,
            "db_top_1": 10,
            "top_row_1_bars": 2,
            "top_row_1_dia": 10,
            "lig_d": 0,
            "lig_legs": 0,
            "s_lig": 250.0,
            "uls_Mstar": 850.0,
            "uls_Vstar": 850.0,
            "Mu_star": 850.0,
            "Vu_star": 850.0,
            "optimisation_lock_geometry": False,
        }
    )
    updates = dict(((RESCUE_SEED_LIBRARY.get("combined") or {}).get("extreme") or {}).get("updates") or {})
    candidate = _evaluate_auto_design_candidate(
        state,
        updates=updates,
        source="focused_unlocked_combined_fail_rescue_seed",
        label="Unlocked combined fail rescue seed",
        action_type="apply_resolved_candidate",
    )
    overview = dict(candidate.get("overview") or {})
    _assert(overview.get("all_key_pass") is True, f"rescue seed did not pass all checks: {overview}")
    _assert(overview.get("any_fail") is False, f"rescue seed still has failing checks: {overview}")
    return {
        "statuses": dict(overview.get("statuses") or {}),
        "utils": dict(overview.get("utils") or {}),
        "updates": {
            key: updates.get(key)
            for key in ("b", "D", "bot_row_1_bars", "bot_row_1_dia", "lig_d", "lig_legs", "s_lig")
        },
    }


def _first_index(rows: list, predicate, label: str) -> int:
    for idx, row in enumerate(rows):
        if predicate(row):
            return idx
    raise AssertionError(f"missing {label}")


def _assert_shear_diameter_before_legs_order() -> dict:
    state = _base_state()
    state.update({"lig_d": 10, "lig_legs": 2, "s_lig": 200.0, "Vu_star": 260.0, "uls_Vstar": 260.0})
    mode_config = {"search_strategy": "balanced"}
    local_states = _generate_local_shear_states(state, mode_config, band=0, limit=40)
    local_dia_idx = _first_index(
        local_states,
        lambda s: int(s.get("lig_d") or 0) > 10 and int(s.get("lig_legs") or 0) == 2,
        "local larger-diameter candidate",
    )
    local_legs_idx = _first_index(
        local_states,
        lambda s: int(s.get("lig_d") or 0) == 10 and int(s.get("lig_legs") or 0) > 2,
        "local more-legs candidate",
    )
    _assert(local_dia_idx < local_legs_idx, f"local shear states tried legs before diameter: {local_dia_idx=} {local_legs_idx=}")

    escalated = _generate_escalated_shear_states(state, severity_band="moderate")
    escalated_dia_idx = _first_index(
        escalated,
        lambda row: int((row[1] or {}).get("lig_d") or 0) > 10 and int((row[1] or {}).get("lig_legs") or 0) == 2,
        "escalated larger-diameter candidate",
    )
    escalated_legs_idx = _first_index(
        escalated,
        lambda row: int((row[1] or {}).get("lig_d") or 0) == 10 and int((row[1] or {}).get("lig_legs") or 0) > 2,
        "escalated more-legs candidate",
    )
    _assert(
        escalated_dia_idx < escalated_legs_idx,
        f"escalated shear states tried legs before diameter: {escalated_dia_idx=} {escalated_legs_idx=}",
    )

    _, meta = _generate_shear_governing_candidates(
        state,
        {"overview": {"utils": {"shear": 1.25}}},
        mode_config,
    )
    order = list(meta.get("shear_candidate_family_order") or [])
    _assert("larger_dia" in order and "more_legs" in order, f"missing shear families in order: {order}")
    _assert(
        order.index("larger_dia") < order.index("more_legs"),
        f"shear-governing order does not prefer diameter before legs: {order}",
    )

    fallback_first = _fallback_shear_reinforcement_step_updates(state)
    _assert(fallback_first and set(fallback_first) == {"lig_d"}, f"fallback did not increase diameter first: {fallback_first}")
    max_dia_state = dict(state)
    max_dia_state.update({"lig_d": 24, "lig_legs": 2})
    fallback_after_dia = _fallback_shear_reinforcement_step_updates(max_dia_state)
    _assert(
        fallback_after_dia and set(fallback_after_dia) == {"lig_legs"},
        f"fallback did not move to legs after diameter catalogue was exhausted: {fallback_after_dia}",
    )
    return {
        "local_larger_dia_index": local_dia_idx,
        "local_more_legs_index": local_legs_idx,
        "escalated_larger_dia_index": escalated_dia_idx,
        "escalated_more_legs_index": escalated_legs_idx,
        "shear_governing_family_order": order,
        "fallback_first": fallback_first,
        "fallback_after_diameter_exhausted": fallback_after_dia,
    }


def main() -> int:
    checks = [
        ("green_design_guide_card_cannot_coexist_with_visible_fail_row", check_detailing_fail_rolls_up_to_fail),
        ("ku_fails_but_design_guide_not_pass", check_ku_fail_prevents_green_design_guide),
        ("non_capacity_bending_failure_wording_names_specific_row", check_non_capacity_bending_failure_wording),
        ("low_bending_utilisation_requires_reduced_geometry_or_reo_cleanup_proof", check_low_bending_util_without_evidence_not_green),
        ("non_compliant_longitudinal_reo_spacing_candidate_rejected", check_invalid_longitudinal_candidate_rejected),
        ("wide_two_bar_longitudinal_spacing_rejected", check_wide_two_bar_longitudinal_spacing_rejected),
        ("vu_zero_invalid_shear_ligs_still_fail_detailing", check_zero_vu_invalid_shear_links_fail_detailing),
        ("vu_zero_no_links_not_flagged_as_invalid_link_detailing", check_zero_vu_no_links_not_flagged_as_invalid_link_detailing),
        ("auto_design_rejects_invalid_shear_link_spacing", check_auto_design_rejects_invalid_shear_link_spacing),
        (
            "zero_bending_live_shear_cleanup_reduces_dia_legs_before_spacing_limit",
            check_zero_bending_live_shear_cleanup_can_reduce_dia_legs_before_spacing_limit,
        ),
        (
            "terminal_exact_cleanup_stop_is_green_not_blue_blocker",
            check_terminal_exact_cleanup_stop_is_not_blue_blocker,
        ),
        (
            "shear_only_terminal_exact_cleanup_stop_is_green_not_blue_blocker",
            check_shear_only_terminal_exact_cleanup_stop_is_not_blue_blocker,
        ),
        (
            "terminal_green_requires_resolved_strength_families",
            check_terminal_green_requires_resolved_strength_families,
        ),
        (
            "publishable_safe_combined_cleanup_candidate_must_not_render_blocked",
            check_publishable_safe_combined_cleanup_candidate_must_not_render_blocked,
        ),
        (
            "terminal_no_further_cleanup_must_render_green",
            check_terminal_no_further_cleanup_must_render_green,
        ),
        (
            "locked_active_failure_blocker_stays_blocked_with_exact_proof",
            check_locked_active_failure_blocker_stays_blocked_with_exact_proof,
        ),
        (
            "unlocked_active_failure_without_apply_cta_fails_policy",
            check_unlocked_active_failure_without_apply_cta_fails_policy,
        ),
        (
            "stale_blocker_cannot_override_unlocked_safe_repair_candidate",
            check_stale_blocker_cannot_override_unlocked_safe_repair_candidate,
        ),
        (
            "rescue_seed_updates_include_canonical_reo_mirrors",
            check_rescue_seed_updates_include_canonical_reo_mirrors,
        ),
        (
            "unlocked_combined_fail_rescue_seed_previews_pass",
            check_unlocked_combined_fail_rescue_seed_previews_pass,
        ),
    ]
    results = []
    for name, fn in checks:
        results.append({"name": name, "result": "PASS", "details": fn()})
    print(json.dumps({"status": "PASS", "checks": results}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
