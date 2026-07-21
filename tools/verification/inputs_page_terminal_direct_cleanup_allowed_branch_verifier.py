from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_terminal_direct_cleanup_allowed_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_direct_cleanup_allowed_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    item = {"title_main": "Safe cleanup"}
    evidence = {
        "safe_executor_backed_candidates_count": 3,
        "safe_executor_backed_candidates": [{"id": "a"}, {"id": "b"}],
    }
    debug: dict = {}
    result = inputs_page.render_design_guide_terminal_direct_cleanup_allowed_branch(
        direct_cleanup_item=item,
        direct_evidence=evidence,
        guidance_debug=debug,
    )
    cases.append({"name": "explicit_inventory_count", "result": result, "debug": dict(debug)})
    if result != ([item], None, "blocked_by_safe_local_cleanup"):
        failures.append(f"explicit_inventory_result_mismatch:{result}")
    if debug.get("safe_local_cleanup_count") != 3:
        failures.append(f"explicit_inventory_safe_count_mismatch:{debug}")
    if debug.get("local_cleanup_candidate_inventory") != [{"id": "a"}, {"id": "b"}]:
        failures.append(f"explicit_inventory_list_mismatch:{debug}")
    if debug.get("local_cleanup_candidate_inventory_count") != 2:
        failures.append(f"explicit_inventory_count_mismatch:{debug}")
    if debug.get("candidate_inventory_count") != 2:
        failures.append(f"explicit_candidate_count_mismatch:{debug}")
    if debug.get("terminal_state_blocked_by_local_cleanup") is not True:
        failures.append(f"explicit_blocked_flag_mismatch:{debug}")
    if debug.get("design_guide_terminal_state") is not None:
        failures.append(f"explicit_terminal_state_mismatch:{debug}")
    if debug.get("design_guide_terminal_state_source") != "blocked_by_safe_local_cleanup":
        failures.append(f"explicit_terminal_source_mismatch:{debug}")
    if debug.get("design_guide_has_actionable_recommendation") is not True:
        failures.append(f"explicit_actionable_flag_mismatch:{debug}")

    debug = {}
    result = inputs_page.render_design_guide_terminal_direct_cleanup_allowed_branch(
        direct_cleanup_item=item,
        direct_evidence={},
        guidance_debug=debug,
    )
    cases.append({"name": "default_safe_count", "result": result, "debug": dict(debug)})
    if debug.get("safe_local_cleanup_count") != 1:
        failures.append(f"default_safe_count_mismatch:{debug}")
    if debug.get("local_cleanup_candidate_inventory") != []:
        failures.append(f"default_inventory_mismatch:{debug}")
    if debug.get("local_cleanup_candidate_inventory_count") != 0:
        failures.append(f"default_inventory_count_mismatch:{debug}")

    payload = {
        "verifier": "inputs_page_terminal_direct_cleanup_allowed_branch_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal Direct Cleanup Allowed Branch Verifier",
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
