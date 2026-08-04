from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_terminal_direct_cleanup_advisory_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_direct_cleanup_advisory_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_guidance_item_as_advisory": inputs_page._guidance_item_as_advisory,
        "FINAL_ACCEPTED_MIN_FAMILY_UTIL": inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL,
        "st": inputs_page.st,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(name: str, *, advisory: Any, blocked_reason: object, evidence: dict, item: dict):
        debug: dict[str, Any] = {}
        fake_session = {"_design_guide_engine_decision": {"old": True}}

        def _as_advisory(candidate, *, blocked_reason, state):
            if callable(advisory):
                return advisory(candidate, blocked_reason=blocked_reason, state=state)
            return advisory

        try:
            inputs_page._guidance_item_as_advisory = _as_advisory
            inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85
            inputs_page.st = SimpleNamespace(session_state=fake_session)
            result = inputs_page.render_design_guide_terminal_direct_cleanup_advisory_branch(
                direct_cleanup_item=dict(item),
                direct_blocked_reason=blocked_reason,
                direct_evidence=dict(evidence),
                guidance_items=[{"title_main": "Existing"}],
                guidance_disp_state={"depth": 500},
                material_families=["shear", "bending"],
                guidance_debug=debug,
            )
        finally:
            _restore()
        cases.append({"name": name, "result": result, "debug": debug, "session_state": fake_session})
        return result, debug, fake_session

    advisory = {"title_main": "Blocked advisory", "status": "BLOCKED"}
    result, debug, session_state = _run_case(
        "generic_blocked_advisory",
        advisory=advisory,
        blocked_reason="candidate_not_executor_backed",
        evidence={},
        item={"candidate_id": "base"},
    )
    if result != ([advisory], None, None, "direct_cleanup_not_executor_backed_blocker", {
        "render_primary_only": True,
        "visible_guidance_items": [advisory],
        "reason": "direct_cleanup_not_executor_backed_blocker",
        "input_count": 1,
        "visible_count": 1,
    }):
        failures.append(f"generic_result_mismatch:{result}")
    if session_state.get("_design_guide_engine_decision") != {}:
        failures.append(f"generic_session_not_reset:{session_state}")
    if debug.get("terminal_state_blocked_by_local_cleanup") is not True:
        failures.append(f"generic_blocked_flag_mismatch:{debug}")
    if debug.get("local_cleanup_blocked_reasons_by_family") != {
        "shear": ["candidate_not_executor_backed"],
        "bending": ["candidate_not_executor_backed"],
    }:
        failures.append(f"generic_family_reasons_mismatch:{debug}")

    exact_advisory = {
        "title_main": "Exact stop",
        "status": "PASS",
        "terminal_cleanup_state": "exact_stop",
        "candidate_search_evidence": {
            "post_click_accepted_green_valid": True,
            "exact_blockers_by_family": {"shear": {"reason": "stop"}},
        },
        "cleanup_evidence_by_family": {"shear": {"cleanup": True}},
    }
    result, debug, session_state = _run_case(
        "exact_stop_terminal_advisory",
        advisory=exact_advisory,
        blocked_reason="candidate_not_executor_backed",
        evidence={},
        item={"candidate_id": "exact"},
    )
    if result[2] != "optimal" or result[3] != "direct_cleanup_exact_stop_terminal":
        failures.append(f"exact_terminal_state_mismatch:{result}")
    if result[4].get("reason") != "direct_cleanup_exact_stop_terminal":
        failures.append(f"exact_render_plan_mismatch:{result[4]}")
    if debug.get("terminal_state_blocked_by_local_cleanup") is not False:
        failures.append(f"exact_blocked_flag_mismatch:{debug}")
    if debug.get("post_click_accepted_green_valid") is not True:
        failures.append(f"exact_post_click_flag_mismatch:{debug}")
    if debug.get("local_cleanup_blocked_reason") is not None:
        failures.append(f"exact_blocked_reason_not_cleared:{debug}")
    if debug.get("post_click_exact_blockers_by_family") != {"shear": {"reason": "stop"}}:
        failures.append(f"exact_blockers_mismatch:{debug}")
    if debug.get("post_click_cleanup_evidence_by_family") != {"shear": {"cleanup": True}}:
        failures.append(f"exact_cleanup_evidence_mismatch:{debug}")

    result, debug, session_state = _run_case(
        "shear_final_threshold_blocker",
        advisory={"title_main": "Shear blocked", "status": "BLOCKED"},
        blocked_reason="blocked_shear_cleanup_does_not_reach_final_family_threshold",
        evidence={
            "total_candidates_considered": 5,
            "selected_candidate_id": "shear-c1",
            "selected_candidate_util": 0.72,
        },
        item={"updates": {"shear_links": "reduce"}, "util": 0.72},
    )
    blocker = (debug.get("exact_blockers_by_family") or {}).get("shear") or {}
    if blocker.get("threshold") != 0.85:
        failures.append(f"shear_threshold_mismatch:{debug}")
    if blocker.get("attempted_candidate_count") != 5:
        failures.append(f"shear_attempt_count_mismatch:{debug}")
    if blocker.get("best_rejected_candidate_id") != "shear-c1":
        failures.append(f"shear_candidate_id_mismatch:{debug}")
    if debug.get("cleanup_evidence_by_family") != {"shear": blocker}:
        failures.append(f"shear_cleanup_evidence_mismatch:{debug}")
    if "No executor-backed one-click shear cleanup" not in str(debug.get("local_cleanup_blocked_reason")):
        failures.append(f"shear_reason_mismatch:{debug}")

    payload = {
        "verifier": "inputs_page_terminal_direct_cleanup_advisory_branch_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal Direct Cleanup Advisory Branch Verifier",
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
