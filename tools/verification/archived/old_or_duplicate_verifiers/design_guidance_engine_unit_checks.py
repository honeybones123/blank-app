"""Fast checks for the pure Design Guide engine.

These are a small guardrail only. The browser real-user ladder remains the
authority for product behaviour.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_guidance_engine import (
    normalise_design_guide_candidate,
    resolve_design_guide_decision,
    select_target_band_winner,
)
from optimisation_config import target_band_payload


FORBIDDEN_VISIBLE = (
    "no directly executable one-click update is attached",
    "candidate is not attached",
    "under the current rules",
    "available move set did not preserve all governing checks",
    "manual review suggested",
    "review manually",
    "current card is advisory because",
    "no executable candidate attached",
)


def _raw_item(
    intent: str,
    *,
    title: str,
    family: str,
    current_util: float,
    display_util: float,
    source: str,
    updates: dict[str, Any] | None = None,
    blocker: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updates = dict(updates or {})
    preview_pass = bool(updates and blocker is None)
    return {
        "title_main": title,
        "guidance_intent": intent,
        "check_key": family,
        "action_type": "apply_resolved_candidate" if updates else None,
        "button_contract": {
            "actionable": bool(updates),
            "action_type": "apply_resolved_candidate" if updates else None,
            "family": family,
            "updates": updates,
            "preview_pass": preview_pass,
            "expected_util": display_util,
            "blocking_reason": blocker,
            "source_candidate_id": "unit-candidate" if updates else None,
        },
        "display_truth": {
            "display_truth_source": source,
            "displayed_util": display_util,
            "displayed_status": "PASS" if display_util <= 1.0 else "FAIL",
            "displayed_within_target_band": 0.88 <= display_util <= 0.95,
            "target_low": 0.88,
            "target_high": 0.95,
            "source_summary_util": current_util,
            "source_candidate_util": display_util if source == "candidate_preview" else None,
        },
        "candidate_search_evidence": dict(evidence or {}),
    }


def _decision(
    item: dict[str, Any],
    *,
    current_util: float,
    any_fail: bool = False,
    all_key_pass: bool = True,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    family = str(item.get("check_key") or "bending")
    return resolve_design_guide_decision(
        current_state={"design_optimisation_goal": "balanced"},
        summary={
            "worst_util": current_util,
            "any_fail": bool(any_fail),
            "any_warn": False,
            "all_key_pass": bool(all_key_pass),
            "statuses": {
                "bending": "FAIL" if any_fail and family == "bending" else "PASS",
                "shear": "FAIL" if any_fail and family == "shear" else "PASS",
            },
            "utils": {family: current_util},
        },
        raw_items=[item],
        candidate_evidence=evidence or item.get("candidate_search_evidence") or {},
        target_band=target_band_payload("balanced"),
        context={
            "goal": "balanced",
            "headline": item.get("title_main"),
            "governing_action": family,
            "guidance_intent": item.get("guidance_intent"),
            "button_label": "Apply Recommendation",
            "primary_item_has_actionable_updates": bool(
                (item.get("button_contract") or {}).get("updates")
            ),
            "any_fail": bool(any_fail),
            "any_warn": False,
            "all_key_pass": bool(all_key_pass),
            "overdesigned": str(item.get("guidance_intent")) == "efficiency_tightening",
            "in_target_band": 0.88 <= current_util <= 0.95,
            "near_limit_util": False,
            "terminal_optimal": str(item.get("guidance_intent")) == "already_efficient",
            "terminal_very_low_demand": False,
            "passive_underband_no_action": False,
        },
    )


def _valid_outside_evidence() -> dict[str, Any]:
    return {
        "candidate_search_exhaustive": True,
        "target_low": 0.88,
        "target_high": 0.95,
        "total_candidates_considered": 6,
        "safe_executor_backed_candidates_count": 2,
        "target_band_candidate_count": 0,
        "selected_candidate_id": "unit-candidate",
        "selected_candidate_title": "Closest safe option found",
        "selected_candidate_util": 0.61,
        "selected_candidate_distance_to_band": 0.27,
        "closest_safe_candidate_id": "unit-candidate",
        "closest_safe_candidate_title": "Closest safe option found",
        "closest_safe_candidate_util": 0.61,
        "closest_safe_candidate_distance_to_band": 0.27,
        "best_target_band_candidate_id": None,
        "best_target_band_candidate_title": None,
        "best_target_band_candidate_util": None,
        "target_band_candidates": [],
        "rejected_target_band_candidates": [],
        "rejected_target_band_candidate_reasons": [],
        "outside_target_band_allowed": True,
        "outside_target_band_allowed_reason": (
            "available catalogue increments cannot hit the target band exactly"
        ),
        "outside_target_band_allowed_category": "discrete_increment_limit",
    }


def _candidate(
    candidate_id: str,
    *,
    util: float,
    updates: dict[str, Any],
    title: str | None = None,
    family: str = "bending",
    preview_pass: bool = True,
    blocking_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "title": title or candidate_id,
        "family": family,
        "action_type": "apply_resolved_candidate",
        "updates": dict(updates),
        "preview_util": util,
        "preview_pass": bool(preview_pass),
        "blocking_reason": blocking_reason,
        "overview": {"all_key_pass": bool(preview_pass), "statuses": {"bending": "PASS", "shear": "PASS"}},
    }


def _winner(candidates: list[dict[str, Any]], *, exhaustive: bool = True) -> dict[str, Any]:
    return select_target_band_winner(
        raw_candidates=candidates,
        current_state={"design_optimisation_goal": "balanced"},
        summary={"worst_util": 0.42, "any_fail": False, "all_key_pass": True},
        target_band=target_band_payload("balanced"),
        context={
            "goal": "balanced",
            "candidate_search_exhaustive": bool(exhaustive),
            "searched_families": ["geometry", "bending", "combined", "shear"],
            "missing_families": [] if exhaustive else ["combined", "shear"],
        },
    )


def _no_forbidden_copy(result: dict[str, Any]) -> bool:
    card = dict(result.get("card") or {})
    text = " ".join(str(card.get(k) or "") for k in ("title", "body", "change_text", "why_text"))
    lower = text.lower()
    return not any(phrase in lower for phrase in FORBIDDEN_VISIBLE)


def main() -> int:
    cases = []

    normalised = normalise_design_guide_candidate(
        _candidate("normalised-target", util=0.91, updates={"D": 450}),
        0.88,
        0.95,
    )
    cases.append(
        (
            "candidate_normalisation_marks_target_safe",
            {"normalised": normalised},
            lambda r: (
                r["normalised"]["executor_backed"]
                and r["normalised"]["safe"]
                and r["normalised"]["inside_target_band"]
                and r["normalised"]["distance_to_target_band"] == 0.0
            ),
        )
    )

    inside_winner = _winner(
        [
            _candidate("outside", util=0.61, updates={"D": 600}),
            _candidate("inside", util=0.91, updates={"D": 450}),
        ],
    )
    cases.append(
        (
            "candidate_inside_target_wins_over_outside",
            inside_winner,
            lambda r: (
                r["selection_status"] == "target_band_candidate_selected"
                and r["selected_candidate"]["candidate_id"] == "inside"
                and r["candidate_search_evidence"]["target_band_candidate_count"] == 1
                and not r["candidate_search_evidence"]["outside_target_band_allowed"]
            ),
        )
    )

    outside_winner = _winner(
        [
            _candidate("far", util=0.42, updates={"D": 700}),
            _candidate("closest", util=0.61, updates={"D": 600}),
        ],
    )
    cases.append(
        (
            "only_outside_candidates_selects_closest_with_evidence",
            outside_winner,
            lambda r: (
                r["selection_status"] == "closest_safe_candidate_selected"
                and r["selected_candidate"]["candidate_id"] == "closest"
                and r["candidate_search_evidence"]["target_band_candidate_count"] == 0
                and r["candidate_search_evidence"]["outside_target_band_allowed"]
                and r["candidate_search_evidence"]["outside_target_band_allowed_category"]
                == "discrete_increment_limit"
            ),
        )
    )

    outside_non_exhaustive = _winner(
        [_candidate("closest", util=0.61, updates={"D": 600})],
        exhaustive=False,
    )
    cases.append(
        (
            "outside_target_partial_search_not_allowed",
            outside_non_exhaustive,
            lambda r: (
                r["selection_status"] == "closest_safe_candidate_selected"
                and not r["candidate_search_evidence"]["candidate_search_exhaustive"]
                and not r["candidate_search_evidence"]["outside_target_band_allowed"]
            ),
        )
    )

    bend = _raw_item(
        "required_fix",
        title="Bending capacity is low",
        family="bending",
        current_util=1.08,
        display_util=0.91,
        source="candidate_preview",
        updates={"bot1_count": 4},
    )
    cases.append(
        (
            "bending_required_fix",
            _decision(bend, current_util=1.08, any_fail=True, all_key_pass=False),
            lambda r: (
                r["card"]["intent"] == "required_fix"
                and r["card"]["family"] == "bending"
                and r["button_contract"]["enabled"]
                and "bending" in r["card"]["title"].lower()
            ),
        )
    )

    shear = _raw_item(
        "required_fix",
        title="Shear capacity is low",
        family="shear",
        current_util=1.12,
        display_util=0.92,
        source="candidate_preview",
        updates={"s_lig": 150.0},
    )
    cases.append(
        (
            "shear_required_fix",
            _decision(shear, current_util=1.12, any_fail=True, all_key_pass=False),
            lambda r: (
                r["card"]["intent"] == "required_fix"
                and r["card"]["family"] == "shear"
                and r["button_contract"]["enabled"]
                and "shear" in (r["card"]["title"] + " " + r["card"]["body"]).lower()
            ),
        )
    )

    below_target = _raw_item(
        "efficiency_tightening",
        title="Final tightening - reduce conservative reinforcement",
        family="bending",
        current_util=0.62,
        display_util=0.90,
        source="candidate_preview",
        updates={"D": 450},
    )
    cases.append(
        (
            "safe_below_target_with_target_band_candidate",
            _decision(below_target, current_util=0.62),
            lambda r: (
                r["card"]["intent"] == "efficiency_tightening"
                and r["button_contract"]["enabled"]
                and r["target_band_outcome"]["lands_in_target_band"]
            ),
        )
    )

    outside_no_evidence = _raw_item(
        "efficiency_tightening",
        title="Bending reserve is high",
        family="bending",
        current_util=0.42,
        display_util=0.61,
        source="candidate_preview",
        updates={"bot1_count": 3},
    )
    cases.append(
        (
            "outside_target_without_evidence_blocks",
            _decision(outside_no_evidence, current_util=0.42),
            lambda r: (
                r["card"]["intent"] == "specific_blocker"
                and not r["button_contract"]["enabled"]
            ),
        )
    )

    evidence = _valid_outside_evidence()
    outside_with_evidence = _raw_item(
        "efficiency_tightening",
        title="Closest safe option found - target band blocked",
        family="bending",
        current_util=0.42,
        display_util=0.61,
        source="candidate_preview",
        updates={"bot1_count": 3},
        evidence=evidence,
    )
    cases.append(
        (
            "outside_target_with_evidence_allowed",
            _decision(outside_with_evidence, current_util=0.42, evidence=evidence),
            lambda r: (
                r["card"]["intent"] == "efficiency_tightening"
                and r["button_contract"]["enabled"]
                and r["target_band_outcome"]["allowed_blocker_category"] == "discrete_increment_limit"
            ),
        )
    )

    efficient = _raw_item(
        "already_efficient",
        title="Design is efficient - further reductions would weaken capacity",
        family="bending",
        current_util=0.91,
        display_util=0.91,
        source="published_summary",
    )
    cases.append(
        (
            "already_in_target_terminal",
            _decision(efficient, current_util=0.91),
            lambda r: (
                r["card"]["intent"] == "already_efficient"
                and r["card"]["use_success_style"]
                and not r["button_contract"]["enabled"]
            ),
        )
    )

    terminal_candidate = _raw_item(
        "already_efficient",
        title="Design is efficient - target band achieved",
        family="shear",
        current_util=0.91,
        display_util=0.91,
        source="published_summary",
    )
    cleanup_candidate = _candidate(
        "bending-cleanup",
        util=0.92,
        updates={"bot1_count": 3, "db_bot_1": 24},
        title="Reduce conservative bottom reinforcement",
        family="bending",
    )
    cleanup_candidate["net_efficiency_delta"] = 24.0 * 24.0
    local_cleanup_decision = resolve_design_guide_decision(
        current_state={"design_optimisation_goal": "balanced", "b": 350, "D": 500, "bot1_count": 4, "db_bot_1": 24},
        summary={
            "worst_util": 0.91,
            "governing_util": 0.91,
            "governing_family": "shear",
            "governing_check": "shear",
            "any_fail": False,
            "all_key_pass": True,
            "statuses": {"bending": "PASS", "shear": "PASS"},
            "utils": {"bending": 0.25, "shear": 0.91},
        },
        raw_items=[terminal_candidate, cleanup_candidate],
        raw_candidates=[terminal_candidate, cleanup_candidate],
        target_band=target_band_payload("balanced"),
        context={"goal": "balanced", "all_key_pass": True, "any_fail": False, "governing_action": "shear"},
    )
    cases.append(
        (
            "in_target_terminal_blocked_by_safe_local_cleanup",
            local_cleanup_decision,
            lambda r: (
                r["card"]["intent"] == "optional_cleanup"
                and r["button_contract"]["enabled"]
                and r["safe_local_cleanup_count"] > 0
                and r["terminal_state_blocked_by_local_cleanup"] is True
                and "bending" in r["materially_overprovided_families"]
            ),
        )
    )

    no_cleanup_decision = resolve_design_guide_decision(
        current_state={"design_optimisation_goal": "balanced"},
        summary={
            "worst_util": 0.91,
            "governing_util": 0.91,
            "governing_family": "shear",
            "governing_check": "shear",
            "any_fail": False,
            "all_key_pass": True,
            "statuses": {"bending": "PASS", "shear": "PASS"},
            "utils": {"bending": 0.25, "shear": 0.91},
        },
        raw_items=[terminal_candidate],
        raw_candidates=[terminal_candidate],
        target_band=target_band_payload("balanced"),
        context={"goal": "balanced", "all_key_pass": True, "any_fail": False, "governing_action": "shear"},
    )
    cases.append(
        (
            "in_target_terminal_requires_no_safe_local_cleanup_reason",
            no_cleanup_decision,
            lambda r: (
                r["card"]["intent"] == "already_efficient"
                and not r["button_contract"]["enabled"]
                and r["safe_local_cleanup_count"] == 0
                and r["terminal_state_reason"] == "governing_in_target_no_safe_local_cleanup"
            ),
        )
    )

    blocker = _raw_item(
        "advisory_warning",
        title="Specific blocker",
        family="bending",
        current_util=0.62,
        display_util=0.62,
        source="published_summary",
        blocker="no material candidate reached target",
    )
    cases.append(
        (
            "generic_fallback_wording_absent",
            _decision(blocker, current_util=0.62),
            _no_forbidden_copy,
        )
    )

    results = []
    failures = []
    for case_id, result, check in cases:
        ok = bool(check(result))
        results.append({"case_id": case_id, "verdict": "PASS" if ok else "FAIL", "result": result})
        if not ok:
            failures.append(case_id)
    print(json.dumps({"total": len(cases), "failures": failures, "cases": results}, indent=2, default=str))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
