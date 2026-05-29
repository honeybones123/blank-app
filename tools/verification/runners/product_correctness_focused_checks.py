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
    _design_guide_dashboard_reasons,
    _fallback_shear_reinforcement_step_updates,
    _generate_escalated_shear_states,
    _generate_local_shear_states,
    _generate_shear_governing_candidates,
    _longitudinal_reo_detailing_failures,
    evaluate_candidate_full,
    evaluate_candidate_fast,
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
    _assert("spacing/detailing" in str(candidate.get("rejection_reason") or ""), "missing spacing/detailing rejection reason")
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
        ("vu_zero_invalid_shear_ligs_still_fail_detailing", check_zero_vu_invalid_shear_links_fail_detailing),
        ("vu_zero_no_links_not_flagged_as_invalid_link_detailing", check_zero_vu_no_links_not_flagged_as_invalid_link_detailing),
        ("auto_design_rejects_invalid_shear_link_spacing", check_auto_design_rejects_invalid_shear_link_spacing),
    ]
    results = []
    for name, fn in checks:
        results.append({"name": name, "result": "PASS", "details": fn()})
    print(json.dumps({"status": "PASS", "checks": results}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
