"""Mutation checks for the super-verification local-cleanup GREEN gate."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.super_verification import parse_real_user_terminal_case


def _base_payload() -> dict:
    terminal = {
        "case_id": "BENDING_LOW_SHEAR_IN_TARGET_TERMINAL",
        "browser_mode": "browser_live",
        "verdict": "PASS",
        "fail_reasons": [],
        "visible_summary_before": {},
        "selected_action_title": "Design is efficient - target band achieved",
        "one_click_button_enabled_before": False,
        "family_utils": {"bending": 0.07, "shear": 0.91},
        "materially_overprovided_families": ["bending"],
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "safe_local_cleanup_count": 0,
        "candidate_inventory_count": 1,
        "local_cleanup_candidate_inventory_count": 1,
        "terminal_state_reason": "governing_in_target_no_safe_local_cleanup",
        "local_cleanup_blocked_reasons": ["no_local_cleanup_candidate_for_materially_overprovided_family"],
    }
    cleanup = {
        "case_id": "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP",
        "browser_mode": "browser_live",
        "verdict": "PASS",
        "fail_reasons": [],
        "visible_summary_before": {},
        "selected_action_title": "Design is safe - optional bending cleanup available",
        "selected_action_family": "bending",
        "one_click_button_enabled_before": True,
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "bending",
            "updates": {"bot1_count": 3},
            "preview_pass": True,
            "blocking_reason": None,
        },
        "family_utils": {"bending": 0.25, "shear": 0.91},
        "materially_overprovided_families": ["bending"],
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "safe_local_cleanup_count": 1,
        "candidate_inventory_count": 1,
        "local_cleanup_candidate_inventory_count": 1,
        "local_cleanup_candidate_inventory": [{"candidate_id": "cleanup_1", "proposed_updates": {"bot1_count": 3}}],
        "terminal_state_blocked_by_local_cleanup": True,
    }
    shear_cleanup = copy.deepcopy(cleanup)
    shear_cleanup.update(
        {
            "case_id": "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP",
            "selected_action_title": "Design is safe - optional shear cleanup available",
            "selected_action_family": "shear",
            "family_utils": {"bending": 0.91, "shear": 0.10, "crack": 0.20},
            "materially_overprovided_families": ["shear", "crack"],
        }
    )
    shear_cleanup["button_contract"] = {**dict(shear_cleanup["button_contract"]), "family": "shear", "updates": {"s_lig": 300}}
    service_cleanup = copy.deepcopy(cleanup)
    service_cleanup.update(
        {
            "case_id": "SERVICEABILITY_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP",
            "selected_action_family": "geometry",
            "family_utils": {"bending": 0.91, "shear": 0.20, "crack": 0.20, "deflection": 0.30},
            "materially_overprovided_families": ["shear", "crack", "deflection"],
        }
    )
    geometry_cleanup = copy.deepcopy(cleanup)
    geometry_cleanup.update(
        {
            "case_id": "GEOMETRY_LOW_REO_OR_SHEAR_IN_TARGET_LOCAL_CLEANUP",
            "selected_action_family": "geometry",
            "family_utils": {"bending": 0.50, "shear": 0.20, "crack": 0.20, "deflection": 0.30},
            "materially_overprovided_families": ["bending", "shear", "crack", "deflection"],
        }
    )
    return {"cases": [terminal, cleanup, shear_cleanup, service_cleanup, geometry_cleanup]}


def main() -> int:
    mutations = []

    offline = _base_payload()
    offline["cases"][1]["browser_mode"] = "offline_fallback"
    mutations.append(("offline_browser_mode_fails", offline))

    missing_count = _base_payload()
    missing_count["cases"][1].pop("safe_local_cleanup_count", None)
    mutations.append(("missing_safe_local_cleanup_count_fails", missing_count))

    terminal_with_cleanup = _base_payload()
    terminal_with_cleanup["cases"][1]["selected_action_title"] = "Design is efficient - target band achieved"
    terminal_with_cleanup["cases"][1]["one_click_button_enabled_before"] = False
    mutations.append(("safe_cleanup_terminal_no_action_fails", terminal_with_cleanup))

    preview_fail = _base_payload()
    preview_fail["cases"][1]["button_contract"]["preview_pass"] = False
    mutations.append(("enabled_cta_preview_fail_fails", preview_fail))

    missing_material = _base_payload()
    missing_material["cases"][1].pop("materially_overprovided_families", None)
    mutations.append(("missing_materially_overprovided_families_fails", missing_material))

    exhaustive_placeholder = _base_payload()
    exhaustive_placeholder["cases"][1]["candidate_inventory_count"] = 0
    exhaustive_placeholder["cases"][1]["local_cleanup_candidate_inventory_count"] = 0
    exhaustive_placeholder["cases"][1]["local_cleanup_candidate_inventory"] = []
    mutations.append(("exhaustive_without_real_candidates_fails", exhaustive_placeholder))

    results = []
    failed = []
    for name, payload in mutations:
        parsed = parse_real_user_terminal_case(copy.deepcopy(payload))
        ok = parsed.get("status") == "FAIL"
        results.append({"mutation": name, "expected": "FAIL", "actual": parsed.get("status"), "ok": ok, "fail_reasons": parsed.get("fail_reasons")})
        if not ok:
            failed.append(name)

    print(json.dumps({"total": len(mutations), "failed_mutation_checks": failed, "results": results}, indent=2, default=str))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
