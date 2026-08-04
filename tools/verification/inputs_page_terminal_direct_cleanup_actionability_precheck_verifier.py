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
    json_path = ARTIFACT_DIR / f"inputs_page_terminal_direct_cleanup_actionability_precheck_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_direct_cleanup_actionability_precheck_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_guidance_executor_actionability_contract": inputs_page._guidance_executor_actionability_contract,
        "_resolve_recommendation_updates": inputs_page._resolve_recommendation_updates,
        "_evaluate_auto_design_candidate": inputs_page._evaluate_auto_design_candidate,
        "_guidance_state_snapshot": inputs_page._guidance_state_snapshot,
        "_parse_util_value": inputs_page._parse_util_value,
        "_guidance_item_best_safe_partial_cleanup": inputs_page._guidance_item_best_safe_partial_cleanup,
        "_guidance_item_safe_incremental_cleanup_below_threshold": (
            inputs_page._guidance_item_safe_incremental_cleanup_below_threshold
        ),
        "_COMPOUND_SHEAR_UPDATE_KEYS": inputs_page._COMPOUND_SHEAR_UPDATE_KEYS,
        "FINAL_ACCEPTED_MIN_FAMILY_UTIL": inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(
        name: str,
        *,
        item: dict[str, Any],
        allowed: bool,
        updates_result: Any,
        preview_shear_util: Any,
        best_safe: bool,
        safe_incremental: bool,
    ):
        eval_inputs: list[dict[str, Any]] = []

        def _contract(candidate, *, state):
            return allowed, "original_blocker"

        def _updates(candidate, *, state):
            if updates_result == "raise":
                raise RuntimeError("boom")
            return dict(updates_result or {})

        def _snapshot(state):
            return {"snapshot": dict(state)}

        def _evaluate(snapshot, **kwargs):
            eval_inputs.append({"snapshot": dict(snapshot), "kwargs": dict(kwargs)})
            return {"overview": {"utils": {"shear": preview_shear_util}}}

        try:
            inputs_page._guidance_executor_actionability_contract = _contract
            inputs_page._resolve_recommendation_updates = _updates
            inputs_page._guidance_state_snapshot = _snapshot
            inputs_page._evaluate_auto_design_candidate = _evaluate
            inputs_page._parse_util_value = lambda value: None if value is None else float(value)
            inputs_page._guidance_item_best_safe_partial_cleanup = lambda candidate: bool(best_safe)
            inputs_page._guidance_item_safe_incremental_cleanup_below_threshold = lambda candidate: bool(safe_incremental)
            inputs_page._COMPOUND_SHEAR_UPDATE_KEYS = {"shear_links", "shear_diameter"}
            inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85
            result = inputs_page.render_design_guide_terminal_direct_cleanup_actionability_precheck(
                direct_cleanup_item=dict(item),
                guidance_disp_state={"depth": 500},
            )
        finally:
            _restore()
        cases.append(
            {
                "name": name,
                "result": result,
                "eval_inputs": eval_inputs,
            }
        )
        return result, eval_inputs

    result, eval_inputs = _run_case(
        "allowed_non_shear_update",
        item={"candidate_search_evidence": {"seed": True}, "title_main": "Cleanup"},
        allowed=True,
        updates_result={"depth": 450},
        preview_shear_util=0.3,
        best_safe=False,
        safe_incremental=False,
    )
    item, allowed, reason, evidence = result
    if allowed is not True or reason != "original_blocker":
        failures.append(f"allowed_non_shear_result_mismatch:{result}")
    if evidence != {"seed": True}:
        failures.append(f"allowed_non_shear_evidence_mismatch:{evidence}")
    if eval_inputs:
        failures.append(f"allowed_non_shear_unexpected_eval:{eval_inputs}")
    if item.get("guidance_intent") != "optional_cleanup" or item.get("local_cleanup_candidate") is not True:
        failures.append(f"allowed_non_shear_metadata_missing:{item}")

    result, eval_inputs = _run_case(
        "below_threshold_safe_incremental_allowed",
        item={"candidate_search_evidence": {"seed": True}, "title_main": "Shear cleanup", "action_type": "apply"},
        allowed=True,
        updates_result={"shear_links": "reduce"},
        preview_shear_util=0.2,
        best_safe=False,
        safe_incremental=True,
    )
    item, allowed, reason, evidence = result
    if allowed is not True:
        failures.append(f"safe_incremental_allowed_mismatch:{result}")
    if evidence.get("safe_incremental_cleanup_below_final_threshold") is not True:
        failures.append(f"safe_incremental_evidence_missing:{evidence}")
    if item.get("safe_incremental_cleanup_below_final_threshold") is not True:
        failures.append(f"safe_incremental_item_missing:{item}")
    if not eval_inputs or eval_inputs[0]["kwargs"].get("source") != "design_guide_final_local_cleanup_shear_threshold_probe":
        failures.append(f"safe_incremental_eval_inputs_mismatch:{eval_inputs}")

    result, eval_inputs = _run_case(
        "below_threshold_not_safe_blocked",
        item={"candidate_search_evidence": {}, "title_main": "Shear cleanup"},
        allowed=True,
        updates_result={"shear_links": "reduce"},
        preview_shear_util=0.2,
        best_safe=False,
        safe_incremental=False,
    )
    item, allowed, reason, evidence = result
    if allowed is not False:
        failures.append(f"blocked_allowed_mismatch:{result}")
    if reason != "blocked_shear_cleanup_does_not_reach_final_family_threshold":
        failures.append(f"blocked_reason_mismatch:{result}")

    result, eval_inputs = _run_case(
        "updates_exception_preserves_allowed",
        item={"candidate_search_evidence": {"seed": True}, "title_main": "Cleanup"},
        allowed=True,
        updates_result="raise",
        preview_shear_util=0.2,
        best_safe=False,
        safe_incremental=False,
    )
    item, allowed, reason, evidence = result
    if allowed is not True or evidence != {"seed": True}:
        failures.append(f"updates_exception_result_mismatch:{result}")
    if eval_inputs:
        failures.append(f"updates_exception_unexpected_eval:{eval_inputs}")

    payload = {
        "verifier": "inputs_page_terminal_direct_cleanup_actionability_precheck_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal Direct Cleanup Actionability Precheck Verifier",
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
