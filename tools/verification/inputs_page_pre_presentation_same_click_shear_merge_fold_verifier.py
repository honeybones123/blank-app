from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_pre_presentation_same_click_shear_merge_fold_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_presentation_same_click_shear_merge_fold_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_updates_match_state": inputs_page._updates_match_state,
        "_publishable_same_click_shear_cleanup_merge": inputs_page._publishable_same_click_shear_cleanup_merge,
        "_overview_required_checks_acceptable": inputs_page._overview_required_checks_acceptable,
        "_candidate_preview_statuses_have_explicit_fail": inputs_page._candidate_preview_statuses_have_explicit_fail,
        "_guidance_cleanup_candidate_id": inputs_page._guidance_cleanup_candidate_id,
        "FINAL_ACCEPTED_MIN_FAMILY_UTIL": inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL,
        "TARGET_BAND_EPS": inputs_page.TARGET_BAND_EPS,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _call(*, same_click_shear_updates: dict, evidence: dict | None = None, debug: dict | None = None):
        return inputs_page.render_design_guide_pre_presentation_same_click_shear_merge_fold(
            same_click_shear_updates=dict(same_click_shear_updates),
            guidance_disp_state={"depth": 500, "shear_links": "existing"},
            pre_presentation_updates={"bottom_bars": 4},
            pre_presentation_util=0.72,
            pre_presentation_evidence=dict(evidence or {"existing": True}),
            bending_action_family="bending",
            bending_action_subfamilies=["bottom_reinforcement"],
            bending_action_title="Bending cleanup",
            bending_action_candidate_id="old-id",
            guidance_debug=debug if debug is not None else {},
        )

    merge_calls: list[dict[str, Any]] = []
    try:
        inputs_page._updates_match_state = lambda state, updates: bool(updates.get("matches"))
        result = _call(same_click_shear_updates={"matches": True})
    finally:
        _restore()
    cases.append({"name": "matching_updates_noop", "result": result, "merge_calls": list(merge_calls)})
    if result != (
        {"bottom_bars": 4},
        0.72,
        {"existing": True},
        "bending",
        ["bottom_reinforcement"],
        "Bending cleanup",
        "old-id",
    ):
        failures.append(f"matching_updates_noop_result_mismatch:{result}")
    if merge_calls:
        failures.append(f"matching_updates_merge_called:{merge_calls}")

    debug: dict[str, Any] = {}
    merge_calls = []

    def _accepted_merge(state, updates):
        merge_calls.append({"state": dict(state), "updates": dict(updates)})
        return {
            "updates": {"bottom_bars": 5, "shear_links": "reduced"},
            "expected_util": 0.88,
            "overview": {
                "any_fail": False,
                "worst_util": 0.87,
                "governing_util": 0.86,
                "utils": {"shear": 0.86},
                "statuses": {"shear": "pass"},
            },
            "evidence": {"merge": "accepted"},
        }

    try:
        inputs_page._updates_match_state = lambda state, updates: False
        inputs_page._publishable_same_click_shear_cleanup_merge = _accepted_merge
        inputs_page._overview_required_checks_acceptable = lambda overview: True
        inputs_page._candidate_preview_statuses_have_explicit_fail = lambda statuses: False
        inputs_page._guidance_cleanup_candidate_id = lambda family, updates: f"{family}:{sorted(updates.items())}"
        inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85
        inputs_page.TARGET_BAND_EPS = 0.0001
        result = _call(same_click_shear_updates={"shear_links": "candidate"}, debug=debug)
    finally:
        _restore()
    cases.append({"name": "accepted_merge", "result": result, "debug": dict(debug), "merge_calls": list(merge_calls)})
    if result[0] != {"bottom_bars": 5, "shear_links": "reduced"}:
        failures.append(f"accepted_updates_mismatch:{result[0]}")
    if result[1] != 0.88:
        failures.append(f"accepted_util_mismatch:{result[1]}")
    if result[3] != "combined":
        failures.append(f"accepted_family_mismatch:{result[3]}")
    if result[4] != ["shear", "bottom_reinforcement"]:
        failures.append(f"accepted_subfamilies_mismatch:{result[4]}")
    if result[5] != "Shear and bending cleanup - one-click optimisation":
        failures.append(f"accepted_title_mismatch:{result[5]}")
    if not str(result[6]).startswith("combined:"):
        failures.append(f"accepted_candidate_id_mismatch:{result[6]}")
    evidence = dict(result[2])
    for key in (
        "cleanup_search_ran",
        "local_cleanup_search_ran",
        "no_second_cta_required",
    ):
        if evidence.get(key) is not True:
            failures.append(f"accepted_evidence_flag_missing:{key}:{evidence}")
    if evidence.get("family") != "combined":
        failures.append(f"accepted_evidence_family_mismatch:{evidence}")
    if debug.get("same_click_bending_cleanup_folded_residual_shear") is not True:
        failures.append(f"accepted_debug_flag_missing:{debug}")
    if debug.get("same_click_bending_cleanup_folded_updates") != {"bottom_bars": 5, "shear_links": "reduced"}:
        failures.append(f"accepted_debug_updates_mismatch:{debug}")
    if not merge_calls:
        failures.append("accepted_merge_not_called")

    debug = {}

    def _exact_blocker_merge(state, updates):
        return {
            "updates": {"bottom_bars": 6, "shear_links": "min"},
            "expected_util": 0.8,
            "overview": {
                "any_fail": False,
                "utils": {"shear": 0.2},
                "statuses": {"shear": "blocked"},
            },
            "evidence": {"exact_blockers_by_family": {"shear": {"reason": "limit"}}},
        }

    try:
        inputs_page._updates_match_state = lambda state, updates: False
        inputs_page._publishable_same_click_shear_cleanup_merge = _exact_blocker_merge
        inputs_page._overview_required_checks_acceptable = lambda overview: True
        inputs_page._candidate_preview_statuses_have_explicit_fail = lambda statuses: False
        inputs_page._guidance_cleanup_candidate_id = lambda family, updates: "exact-blocker-id"
        inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85
        inputs_page.TARGET_BAND_EPS = 0.0001
        result = _call(same_click_shear_updates={"shear_links": "candidate"}, debug=debug)
    finally:
        _restore()
    cases.append({"name": "accepted_by_exact_blocker", "result": result, "debug": dict(debug)})
    exact_evidence = dict(result[2])
    if result[3] != "combined" or result[6] != "exact-blocker-id":
        failures.append(f"exact_blocker_identity_mismatch:{result}")
    if exact_evidence.get("outside_target_band_allowed") is not True:
        failures.append(f"exact_blocker_outside_allowed_missing:{exact_evidence}")
    if exact_evidence.get("outside_target_band_allowed_category") != "combined_cleanup_exact_blocker_after_same_click_merge":
        failures.append(f"exact_blocker_category_mismatch:{exact_evidence}")
    if exact_evidence.get("post_click_exact_blockers_by_family") != {"shear": {"reason": "limit"}}:
        failures.append(f"exact_blocker_payload_mismatch:{exact_evidence}")

    for case_name, merge_result, checks_ok, explicit_fail in (
        (
            "rejected_any_fail",
            {
                "updates": {"bottom_bars": 6, "shear_links": "min"},
                "expected_util": 0.9,
                "overview": {"any_fail": True, "utils": {"shear": 0.9}, "statuses": {}},
                "evidence": {},
            },
            True,
            False,
        ),
        (
            "rejected_required_checks",
            {
                "updates": {"bottom_bars": 6, "shear_links": "min"},
                "expected_util": 0.9,
                "overview": {"any_fail": False, "utils": {"shear": 0.9}, "statuses": {}},
                "evidence": {},
            },
            False,
            False,
        ),
        (
            "rejected_explicit_fail",
            {
                "updates": {"bottom_bars": 6, "shear_links": "min"},
                "expected_util": 0.9,
                "overview": {"any_fail": False, "utils": {"shear": 0.9}, "statuses": {"shear": "fail"}},
                "evidence": {},
            },
            True,
            True,
        ),
        (
            "rejected_missing_util",
            {
                "updates": {"bottom_bars": 6, "shear_links": "min"},
                "overview": {"any_fail": False, "utils": {"shear": 0.9}, "statuses": {}},
                "evidence": {},
            },
            True,
            False,
        ),
    ):
        debug = {}
        try:
            inputs_page._updates_match_state = lambda state, updates: False
            inputs_page._publishable_same_click_shear_cleanup_merge = lambda state, updates, _merge_result=merge_result: dict(_merge_result)
            inputs_page._overview_required_checks_acceptable = lambda overview, _checks_ok=checks_ok: bool(_checks_ok)
            inputs_page._candidate_preview_statuses_have_explicit_fail = (
                lambda statuses, _explicit_fail=explicit_fail: bool(_explicit_fail)
            )
            inputs_page._guidance_cleanup_candidate_id = lambda family, updates: "should-not-be-used"
            inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85
            inputs_page.TARGET_BAND_EPS = 0.0001
            result = _call(same_click_shear_updates={"shear_links": "candidate"}, debug=debug)
        finally:
            _restore()
        cases.append({"name": case_name, "result": result, "debug": dict(debug)})
        if result != (
            {"bottom_bars": 4},
            0.72,
            {"existing": True},
            "bending",
            ["bottom_reinforcement"],
            "Bending cleanup",
            "old-id",
        ):
            failures.append(f"{case_name}_result_mismatch:{result}")
        if debug:
            failures.append(f"{case_name}_debug_changed:{debug}")

    payload = {
        "verifier": "inputs_page_pre_presentation_same_click_shear_merge_fold_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre Presentation Same Click Shear Merge Fold Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
