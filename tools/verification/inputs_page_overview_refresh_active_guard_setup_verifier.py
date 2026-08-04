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
    json_path = ARTIFACT_DIR / f"inputs_page_overview_refresh_active_guard_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_overview_refresh_active_guard_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_collect_design_overview": inputs_page._collect_design_overview,
        "_build_design_actions_context": inputs_page._build_design_actions_context,
        "stable_fingerprint_for_payload": inputs_page.stable_fingerprint_for_payload,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_overview_active_failure_keys": inputs_page._overview_active_failure_keys,
        "_resolve_recommendation_updates": inputs_page._resolve_recommendation_updates,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "classify_governing_state": inputs_page.classify_governing_state,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _install_common(*, overview: dict, active_keys: set[str], classifier: dict | Exception) -> None:
        inputs_page._collect_design_overview = lambda state, *, context=None: dict(overview)
        inputs_page._build_design_actions_context = lambda state: {"context": True}
        inputs_page.stable_fingerprint_for_payload = lambda payload: json.dumps(payload, sort_keys=True)
        inputs_page._design_mode_config = lambda goal: {"goal": goal}
        inputs_page._design_optimisation_goal = lambda state: "balanced"
        inputs_page._overview_active_failure_keys = lambda ov: set(active_keys) if dict(ov or {}).get("statuses") else set()
        inputs_page._resolve_recommendation_updates = lambda item, *, state=None: dict(item.get("fallback_updates") or {})
        inputs_page._design_guide_button_contract_enabled = lambda contract: bool(contract.get("enabled"))

        def _classifier(summary, debug):
            if isinstance(classifier, Exception):
                raise classifier
            return dict(classifier)

        inputs_page.classify_governing_state = _classifier

    def _run_case(
        name: str,
        *,
        overview: dict,
        active_keys: set[str],
        classifier: dict | Exception,
        guidance_debug: dict,
        guidance_items: list[dict],
        debug_trace: dict,
    ) -> dict[str, Any]:
        try:
            _install_common(overview=overview, active_keys=active_keys, classifier=classifier)
            result = inputs_page.render_design_guide_overview_refresh_and_active_guard_setup(
                guidance_debug=guidance_debug,
                guidance_disp_state={"D": 500},
                guidance_items=guidance_items,
                debug_trace=debug_trace,
            )
        finally:
            _restore()
        case = {"name": name, "result": result}
        cases.append(case)
        return case

    fresh = _run_case(
        "fresh_overview_active_blocker",
        overview={"statuses": {"bending": "FAIL"}, "fresh": True},
        active_keys={"bending"},
        classifier={"governing_state": "BENDING_FAIL_GOVERNS"},
        guidance_debug={"overview": {"statuses": {"bending": "PASS"}, "fresh": False}},
        guidance_items=[
            {
                "family": "bending",
                "title": "Repair blocked by detailing",
                "active_under_capacity_blocker": True,
            }
        ],
        debug_trace={},
    )
    (
        fresh_debug,
        fresh_overview,
        fresh_mode,
        fresh_active_keys,
        fresh_primary,
        fresh_key,
        fresh_contract,
        fresh_action_type,
        fresh_updates,
        fresh_is_executable,
        fresh_title_text,
        fresh_evidence,
        fresh_locked,
        fresh_active_blocker,
        fresh_classifier,
    ) = fresh["result"]
    if fresh_overview.get("fresh") is not True:
        failures.append(f"fresh_overview_not_used:{fresh_overview}")
    if fresh_debug.get("design_guide_overview_refreshed_from_current_state") is not True:
        failures.append(f"fresh_refresh_flag_mismatch:{fresh_debug}")
    if fresh_active_keys != {"bending"}:
        failures.append(f"fresh_active_keys_mismatch:{fresh_active_keys}")
    if fresh_active_blocker is not True:
        failures.append(f"fresh_active_blocker_mismatch:{fresh_active_blocker}")
    if fresh_classifier.get("governing_state") != "BENDING_FAIL_GOVERNS":
        failures.append(f"fresh_classifier_mismatch:{fresh_classifier}")

    executable = _run_case(
        "executable_repair_suppresses_active_blocker",
        overview={"statuses": {"bending": "FAIL"}},
        active_keys={"bending"},
        classifier={},
        guidance_debug={},
        guidance_items=[
            {
                "family": "bending",
                "title": "Repair blocked",
                "action_type": "apply_resolved_candidate",
                "button_contract": {"enabled": True, "updates": {"D": 550}},
            }
        ],
        debug_trace={},
    )
    if executable["result"][9] is not True:
        failures.append(f"executable_repair_flag_mismatch:{executable['result']}")
    if executable["result"][13] is not False:
        failures.append(f"executable_active_blocker_not_suppressed:{executable['result']}")

    fallback = _run_case(
        "debug_overview_fallback_and_locked_no_repair",
        overview={},
        active_keys=set(),
        classifier=RuntimeError("classifier boom"),
        guidance_debug={"overview": {"statuses": {"shear": "FAIL"}}},
        guidance_items=[
            {
                "check_key": "locked_no_repair",
                "candidate_search_evidence": {"locked_no_repair": True},
            }
        ],
        debug_trace={"overview": {"statuses": {"bending": "FAIL"}}},
    )
    if fallback["result"][1].get("statuses") != {"shear": "FAIL"}:
        failures.append(f"fallback_overview_mismatch:{fallback['result'][1]}")
    if fallback["result"][0].get("design_guide_overview_refreshed_from_current_state") is not False:
        failures.append(f"fallback_refresh_flag_mismatch:{fallback['result'][0]}")
    if fallback["result"][11].get("locked_no_repair") is not True:
        failures.append(f"fallback_evidence_mismatch:{fallback['result'][11]}")
    if fallback["result"][12] is not True:
        failures.append(f"fallback_locked_no_repair_mismatch:{fallback['result'][12]}")
    if fallback["result"][14] != {}:
        failures.append(f"classifier_exception_not_suppressed:{fallback['result'][14]}")

    payload = {
        "verifier": "inputs_page_overview_refresh_active_guard_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Overview Refresh Active Guard Setup Verifier",
                "",
                f"Status: `{payload['status']}`",
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
