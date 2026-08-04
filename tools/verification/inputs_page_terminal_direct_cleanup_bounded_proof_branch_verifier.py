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
    json_path = ARTIFACT_DIR / f"inputs_page_terminal_direct_cleanup_bounded_proof_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_direct_cleanup_bounded_proof_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_st = inputs_page.st
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _run_case(name: str, **kwargs):
        fake_session = {"_design_guide_engine_decision": {"old": True}}
        inputs_page.st = SimpleNamespace(session_state=fake_session)
        try:
            result = inputs_page.render_design_guide_terminal_direct_cleanup_bounded_proof_branch(**kwargs)
        finally:
            inputs_page.st = original_st
        cases.append(
            {
                "name": name,
                "result": result,
                "debug": dict(kwargs["guidance_debug"]),
                "session_state": dict(fake_session),
            }
        )
        return result, fake_session

    original_values = {
        "guidance_items": [{"title_main": "Existing"}],
        "recommendation_result": {"status": "old"},
        "terminal_state": "optimal",
        "terminal_state_source": "pre_existing_terminal",
        "dg_engine_decision": {"decision": "keep"},
        "dg_presentation": {"headline": "ok"},
        "render_plan": {"reason": "old"},
    }
    debug: dict[str, Any] = {}
    result, session_state = _run_case(
        "no_unresolved_item",
        direct_cleanup_item={"title_main": "Resolved"},
        has_terminal_cleanup_evidence=False,
        guidance_debug=debug,
        **original_values,
    )
    if result[-1] is not False:
        failures.append(f"no_unresolved_handled_mismatch:{result}")
    if result[:-1] != (
        original_values["guidance_items"],
        original_values["recommendation_result"],
        original_values["terminal_state"],
        original_values["terminal_state_source"],
        original_values["dg_engine_decision"],
        original_values["dg_presentation"],
        original_values["render_plan"],
    ):
        failures.append(f"no_unresolved_state_changed:{result}")
    if session_state.get("_design_guide_engine_decision") != {"old": True}:
        failures.append(f"no_unresolved_session_changed:{session_state}")

    debug = {}
    result, session_state = _run_case(
        "ignored_with_terminal_cleanup_evidence",
        direct_cleanup_item={
            "direct_target_band_proof_unresolved": True,
            "direct_target_band_blocker_reason": "bounded",
        },
        has_terminal_cleanup_evidence=True,
        guidance_debug=debug,
        **original_values,
    )
    if result[-1] is not True:
        failures.append(f"ignored_handled_mismatch:{result}")
    if result[0] != original_values["guidance_items"] or result[2] != "optimal":
        failures.append(f"ignored_state_changed:{result}")
    if debug.get("direct_target_band_search_bounded_proof_unresolved_ignored") is not True:
        failures.append(f"ignored_debug_missing:{debug}")
    if debug.get("direct_target_band_search_bounded_proof_unresolved_ignored_reason") != "terminal_cleanup_evidence_already_exhaustive":
        failures.append(f"ignored_reason_mismatch:{debug}")
    if debug.get("design_guide_terminal_positive") is not True:
        failures.append(f"ignored_terminal_positive_missing:{debug}")
    if session_state.get("_design_guide_engine_decision") != {"old": True}:
        failures.append(f"ignored_session_changed:{session_state}")

    direct_item = {
        "direct_target_band_proof_unresolved": True,
        "direct_target_band_blocker_reason": "bounded proof",
        "button_contract": {"enabled": True},
        "title_main": "Target band proof blocked",
    }
    debug = {}
    result, session_state = _run_case(
        "published_bounded_proof_blocker",
        direct_cleanup_item=direct_item,
        has_terminal_cleanup_evidence=False,
        guidance_debug=debug,
        **original_values,
    )
    if result[-1] is not True:
        failures.append(f"published_handled_mismatch:{result}")
    if result[0] != [direct_item]:
        failures.append(f"published_guidance_items_mismatch:{result[0]}")
    if result[1] is not None or result[2] is not None:
        failures.append(f"published_terminal_state_mismatch:{result}")
    if result[3] != "direct_target_band_bounded_proof_unresolved":
        failures.append(f"published_terminal_source_mismatch:{result}")
    if result[4] != {} or result[5] != {}:
        failures.append(f"published_decision_presentation_mismatch:{result}")
    expected_plan = {
        "render_primary_only": True,
        "visible_guidance_items": [direct_item],
        "reason": "direct_target_band_bounded_proof_unresolved",
        "input_count": 1,
        "visible_count": 1,
    }
    if result[6] != expected_plan:
        failures.append(f"published_render_plan_mismatch:{result[6]}")
    if session_state.get("_design_guide_engine_decision") != {}:
        failures.append(f"published_session_not_reset:{session_state}")
    if debug.get("primary_button_contract") != {"enabled": True}:
        failures.append(f"published_button_contract_mismatch:{debug}")
    if debug.get("button_contract_enabled") is not False:
        failures.append(f"published_button_contract_enabled_mismatch:{debug}")
    if debug.get("primary_card_intent") != "blocked" or debug.get("primary_guidance_intent") != "blocked":
        failures.append(f"published_intent_mismatch:{debug}")

    payload = {
        "verifier": "inputs_page_terminal_direct_cleanup_bounded_proof_branch_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal Direct Cleanup Bounded Proof Branch Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}` handled={case['result'][-1]}" for case in cases),
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
