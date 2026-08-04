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
    json_path = ARTIFACT_DIR / f"inputs_page_pre_presentation_combined_terminal_fold_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_presentation_combined_terminal_fold_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_COMPOUND_SHEAR_UPDATE_KEYS": inputs_page._COMPOUND_SHEAR_UPDATE_KEYS,
        "_publishable_same_click_shear_cleanup_merge": inputs_page._publishable_same_click_shear_cleanup_merge,
        "_updates_match_state": inputs_page._updates_match_state,
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

    def _call(
        *,
        family: str = "combined",
        updates: dict | None = None,
        util: float | None = 0.7,
        evidence: dict | None = None,
        candidate_id: str = "old-id",
        debug: dict | None = None,
    ):
        return inputs_page.render_design_guide_pre_presentation_combined_terminal_fold(
            bending_action_family=family,
            pre_presentation_updates=dict(updates or {"bottom_bars": 4, "shear_links": "reduce"}),
            pre_presentation_util=util,
            pre_presentation_evidence=dict(
                evidence or {"target_band_candidate_count": 0, "accepted_band_candidate_count": 0}
            ),
            bending_action_candidate_id=candidate_id,
            guidance_disp_state={"depth": 500, "shear_links": "existing"},
            guidance_debug=debug if debug is not None else {},
        )

    debug: dict[str, Any] = {}
    try:
        inputs_page._COMPOUND_SHEAR_UPDATE_KEYS = {"shear_links", "shear_diameter"}
        result = _call(family="bending", debug=debug)
    finally:
        _restore()
    cases.append({"name": "guard_family_noop", "result": result, "debug": dict(debug)})
    if result != (
        {"bottom_bars": 4, "shear_links": "reduce"},
        0.7,
        {"target_band_candidate_count": 0, "accepted_band_candidate_count": 0},
        "old-id",
    ):
        failures.append(f"guard_family_noop_mismatch:{result}")
    if debug:
        failures.append(f"guard_family_debug_changed:{debug}")

    debug = {}
    try:
        inputs_page._COMPOUND_SHEAR_UPDATE_KEYS = {"shear_links", "shear_diameter"}
        result = _call(updates={"bottom_bars": 4}, debug=debug)
    finally:
        _restore()
    cases.append({"name": "guard_no_shear_update_noop", "result": result, "debug": dict(debug)})
    if result != (
        {"bottom_bars": 4},
        0.7,
        {"target_band_candidate_count": 0, "accepted_band_candidate_count": 0},
        "old-id",
    ):
        failures.append(f"guard_no_shear_update_mismatch:{result}")
    if debug:
        failures.append(f"guard_no_shear_debug_changed:{debug}")

    merge_calls: list[dict[str, Any]] = []
    debug = {}

    def _accepted_merge(state, updates):
        merge_calls.append({"state": dict(state), "updates": dict(updates)})
        return {
            "updates": {"bottom_bars": 5, "shear_links": "min"},
            "expected_util": 0.9,
            "overview": {
                "any_fail": False,
                "utils": {"bending": 0.88, "shear": 0.9},
                "statuses": {"bending": "pass", "shear": "pass"},
            },
            "evidence": {
                "target_band_candidate_count": 3,
                "accepted_band_candidate_count": 2,
                "folded_candidate_ids": ["a", "b"],
            },
        }

    try:
        inputs_page._COMPOUND_SHEAR_UPDATE_KEYS = {"shear_links", "shear_diameter"}
        inputs_page._publishable_same_click_shear_cleanup_merge = _accepted_merge
        inputs_page._updates_match_state = lambda state, updates: False
        inputs_page._overview_required_checks_acceptable = lambda overview: True
        inputs_page._candidate_preview_statuses_have_explicit_fail = lambda statuses: False
        inputs_page._guidance_cleanup_candidate_id = lambda family, updates: "combined-fold-id"
        inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85
        inputs_page.TARGET_BAND_EPS = 0.0001
        result = _call(debug=debug)
    finally:
        _restore()
    cases.append({"name": "accepted_terminal_fold", "result": result, "debug": dict(debug), "merge_calls": merge_calls})
    if result[0] != {"bottom_bars": 5, "shear_links": "min"}:
        failures.append(f"accepted_updates_mismatch:{result[0]}")
    if result[1] != 0.9:
        failures.append(f"accepted_util_mismatch:{result[1]}")
    if result[3] != "combined-fold-id":
        failures.append(f"accepted_candidate_id_mismatch:{result[3]}")
    accepted_evidence = dict(result[2])
    for key in (
        "terminal_candidate_status",
        "same_click_terminalisation_fold",
        "same_click_combined_full_payload_terminal_fold",
        "no_second_cta_required",
        "cleanup_search_ran",
        "local_cleanup_search_ran",
    ):
        if key not in accepted_evidence:
            failures.append(f"accepted_evidence_key_missing:{key}:{accepted_evidence}")
    if accepted_evidence.get("target_band_candidate_count") != 3:
        failures.append(f"accepted_target_count_mismatch:{accepted_evidence}")
    if accepted_evidence.get("accepted_band_candidate_count") != 2:
        failures.append(f"accepted_band_count_mismatch:{accepted_evidence}")
    if accepted_evidence.get("folded_candidate_ids") != ["a", "b"]:
        failures.append(f"accepted_folded_ids_mismatch:{accepted_evidence}")
    if accepted_evidence.get("terminal_fold_proof", {}).get("target_band_candidate_count") != 3:
        failures.append(f"accepted_terminal_proof_mismatch:{accepted_evidence}")
    if debug.get("same_click_combined_full_payload_terminal_fold") is not True:
        failures.append(f"accepted_debug_flag_missing:{debug}")
    if debug.get("same_click_combined_full_payload_terminal_updates") != {"bottom_bars": 5, "shear_links": "min"}:
        failures.append(f"accepted_debug_updates_mismatch:{debug}")
    if not merge_calls:
        failures.append("accepted_merge_not_called")

    for case_name, merge_result, updates_match, checks_ok, explicit_fail in (
        ("merge_exception_noop", "raise", False, True, False),
        (
            "rejected_matching_updates",
            {
                "updates": {"bottom_bars": 5, "shear_links": "min"},
                "expected_util": 0.9,
                "overview": {"any_fail": False, "utils": {"shear": 0.9}, "statuses": {}},
                "evidence": {},
            },
            True,
            True,
            False,
        ),
        (
            "rejected_any_fail",
            {
                "updates": {"bottom_bars": 5, "shear_links": "min"},
                "expected_util": 0.9,
                "overview": {"any_fail": True, "utils": {"shear": 0.9}, "statuses": {}},
                "evidence": {},
            },
            False,
            True,
            False,
        ),
        (
            "rejected_out_of_band",
            {
                "updates": {"bottom_bars": 5, "shear_links": "min"},
                "expected_util": 1.2,
                "overview": {"any_fail": False, "utils": {"shear": 1.2}, "statuses": {}},
                "evidence": {},
            },
            False,
            True,
            False,
        ),
        (
            "rejected_required_checks",
            {
                "updates": {"bottom_bars": 5, "shear_links": "min"},
                "expected_util": 0.9,
                "overview": {"any_fail": False, "utils": {"shear": 0.9}, "statuses": {}},
                "evidence": {},
            },
            False,
            False,
            False,
        ),
        (
            "rejected_explicit_fail",
            {
                "updates": {"bottom_bars": 5, "shear_links": "min"},
                "expected_util": 0.9,
                "overview": {"any_fail": False, "utils": {"shear": 0.9}, "statuses": {"shear": "fail"}},
                "evidence": {},
            },
            False,
            True,
            True,
        ),
    ):
        debug = {}
        try:
            inputs_page._COMPOUND_SHEAR_UPDATE_KEYS = {"shear_links", "shear_diameter"}
            if merge_result == "raise":
                inputs_page._publishable_same_click_shear_cleanup_merge = (
                    lambda state, updates: (_ for _ in ()).throw(RuntimeError("boom"))
                )
            else:
                inputs_page._publishable_same_click_shear_cleanup_merge = (
                    lambda state, updates, _merge_result=merge_result: dict(_merge_result)
                )
            inputs_page._updates_match_state = lambda state, updates, _updates_match=updates_match: bool(_updates_match)
            inputs_page._overview_required_checks_acceptable = lambda overview, _checks_ok=checks_ok: bool(_checks_ok)
            inputs_page._candidate_preview_statuses_have_explicit_fail = (
                lambda statuses, _explicit_fail=explicit_fail: bool(_explicit_fail)
            )
            inputs_page._guidance_cleanup_candidate_id = lambda family, updates: "should-not-be-used"
            inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85
            inputs_page.TARGET_BAND_EPS = 0.0001
            result = _call(debug=debug)
        finally:
            _restore()
        cases.append({"name": case_name, "result": result, "debug": dict(debug)})
        if result != (
            {"bottom_bars": 4, "shear_links": "reduce"},
            0.7,
            {"target_band_candidate_count": 0, "accepted_band_candidate_count": 0},
            "old-id",
        ):
            failures.append(f"{case_name}_result_mismatch:{result}")
        if debug:
            failures.append(f"{case_name}_debug_changed:{debug}")

    payload = {
        "verifier": "inputs_page_pre_presentation_combined_terminal_fold_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre Presentation Combined Terminal Fold Verifier",
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
