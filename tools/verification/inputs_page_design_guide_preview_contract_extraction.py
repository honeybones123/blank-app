"""Verify Design Guide preview contract extraction."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "preview_contract.py"
ARTIFACTS = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def _bind_module(*, current_overview: dict | None = None, preview: Any = None, preview_raises: bool = False) -> dict[str, Any]:
    from inputs_page_modules.design_guide import preview_contract as extracted

    calls: dict[str, Any] = {"overview": [], "snapshots": [], "candidate": []}

    def _snapshot(state: dict) -> dict:
        calls["snapshots"].append(dict(state or {}))
        return dict(state or {})

    def _context(state: dict) -> dict:
        return {"state_keys": sorted(dict(state or {}).keys())}

    def _overview(state: dict, *, context: dict | None = None) -> dict:
        calls["overview"].append({"state": dict(state or {}), "context": dict(context or {})})
        return dict(current_overview or {})

    def _evaluate_candidate_full(state: dict, *, source: str, updates: dict) -> Any:
        calls["candidate"].append({"state": dict(state or {}), "source": source, "updates": dict(updates or {})})
        if preview_raises:
            raise RuntimeError("preview failed")
        return preview

    def _parse_util_value(value: Any) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    def _overview_required_checks_acceptable(overview: dict) -> bool:
        return bool(overview.get("acceptable", True))

    extracted.bind_preview_contract_dependencies(
        {
            "_build_design_actions_context": _context,
            "_collect_design_overview": _overview,
            "_guidance_state_snapshot": _snapshot,
            "_overview_required_checks_acceptable": _overview_required_checks_acceptable,
            "_parse_util_value": _parse_util_value,
            "evaluate_candidate_full": _evaluate_candidate_full,
        }
    )
    return {"module": extracted, "calls": calls}


def _case_results() -> list[dict[str, Any]]:
    state = {"D": 600}
    missing = _bind_module(
        current_overview={"statuses": {}, "worst_util": 0.95},
        preview={"overview": {"statuses": {}, "worst_util": 0.8, "acceptable": True}},
    )
    missing_result = missing["module"]._design_guide_preview_contract_for_updates(state, {})

    clean_pass = _bind_module(
        current_overview={"statuses": {}, "worst_util": 0.95},
        preview={"overview": {"statuses": {}, "worst_util": 0.8, "acceptable": True}},
    )
    clean_pass_result = clean_pass["module"]._design_guide_preview_contract_for_updates(state, {"D": 650})

    clean_fail = _bind_module(
        current_overview={"statuses": {}, "worst_util": 0.95},
        preview={"overview": {"statuses": {}, "worst_util": 0.8, "acceptable": False}},
    )
    clean_fail_result = clean_fail["module"]._design_guide_preview_contract_for_updates(state, {"D": 650})

    new_fail = _bind_module(
        current_overview={"statuses": {"bending": "PASS"}, "worst_util": 0.95},
        preview={"overview": {"statuses": {"bending": "PASS", "shear": "FAIL"}, "worst_util": 0.8}},
    )
    new_fail_result = new_fail["module"]._design_guide_preview_contract_for_updates(state, {"D": 650})

    active_improves = _bind_module(
        current_overview={"statuses": {"crack": "FAIL"}, "worst_util": 1.4},
        preview={"overview": {"statuses": {"crack": "FAIL"}, "worst_util": 1.1}},
    )
    active_improves_result = active_improves["module"]._design_guide_preview_contract_for_updates(state, {"D": 650})

    active_no_improve = _bind_module(
        current_overview={"statuses": {"crack": "FAIL"}, "worst_util": 1.4},
        preview={"overview": {"statuses": {"crack": "FAIL"}, "worst_util": 1.5}},
    )
    active_no_improve_result = active_no_improve["module"]._design_guide_preview_contract_for_updates(state, {"D": 650})

    exception_case = _bind_module(current_overview={}, preview_raises=True)
    exception_result = exception_case["module"]._design_guide_preview_contract_for_updates(state, {"D": 650})

    unavailable_case = _bind_module(current_overview={}, preview=None)
    unavailable_result = unavailable_case["module"]._design_guide_preview_contract_for_updates(state, {"D": 650})

    return [
        {
            "name": "missing_updates",
            "passed": missing_result == (False, None, "missing_updates"),
        },
        {
            "name": "clean_candidate_passes",
            "passed": clean_pass_result == (True, 0.8, None),
            "calls": clean_pass["calls"],
        },
        {
            "name": "clean_candidate_not_compliant_rejected",
            "passed": clean_fail_result == (False, 0.8, "candidate_preview_not_compliant"),
        },
        {
            "name": "new_fail_status_rejected",
            "passed": new_fail_result == (False, 0.8, "candidate_preview_introduces_fail_status"),
        },
        {
            "name": "active_failure_improvement_passes",
            "passed": active_improves_result == (True, 1.1, None),
        },
        {
            "name": "active_failure_no_improvement_rejected",
            "passed": active_no_improve_result == (False, 1.5, "candidate_preview_does_not_improve_active_failure"),
        },
        {
            "name": "preview_exception_rejected",
            "passed": exception_result == (False, None, "preview_exception"),
        },
        {
            "name": "preview_unavailable_rejected",
            "passed": unavailable_result == (False, None, "preview_unavailable"),
        },
    ]


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    bridge_node = _function_node(bridge_source, "_design_guide_preview_contract_for_updates")
    module_node = _function_node(module_source, "_design_guide_preview_contract_for_updates")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    dependency_section = module_source.partition("def bind_preview_contract_dependencies")[0]
    cases = _case_results()

    checks: dict[str, bool] = {
        "module_exists": MODULE.exists(),
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 6,
        "bridge_binds_dependencies": "_bind_preview_contract_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_design_guide_preview_contract_for_updates_extracted" in bridge_body,
        "bridge_removed_preview_body": "candidate_preview_introduces_fail_status" not in bridge_body
        and "evaluate_candidate_full" not in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 60,
        "module_has_dependency_binder": "def bind_preview_contract_dependencies" in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_has_needed_dependencies": all(
            token in dependency_section
            for token in (
                '"_build_design_actions_context"',
                '"_collect_design_overview"',
                '"_guidance_state_snapshot"',
                '"_overview_required_checks_acceptable"',
                '"_parse_util_value"',
                '"evaluate_candidate_full"',
            )
        ),
        "module_keeps_preview_contract_surface": all(
            token in module_source
            for token in (
                "design_guide_button_contract_preview",
                "candidate_preview_introduces_fail_status",
                "candidate_preview_has_fail_status",
                "candidate_preview_not_compliant",
                "candidate_preview_does_not_improve_active_failure",
            )
        ),
        "all_cases_pass": all(row["passed"] for row in cases),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import preview_contract as extracted

    original = bridge._design_guide_preview_contract_for_updates_extracted
    call_record: dict[str, Any] = {}

    def _fake_extracted(state: dict, updates: dict) -> tuple[bool, float, None]:
        call_record.update(
            {
                "state": dict(state),
                "updates": dict(updates),
                "bound_overview": getattr(extracted, "_collect_design_overview", None)
                is bridge._collect_design_overview,
                "bound_snapshot": getattr(extracted, "_guidance_state_snapshot", None)
                is bridge._guidance_state_snapshot,
                "bound_evaluate": getattr(extracted, "evaluate_candidate_full", None)
                is bridge.evaluate_candidate_full,
            }
        )
        return True, 0.7, None

    try:
        bridge._design_guide_preview_contract_for_updates_extracted = _fake_extracted
        returned = bridge._design_guide_preview_contract_for_updates({"D": 600}, {"D": 650})
    finally:
        bridge._design_guide_preview_contract_for_updates_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_collect_design_overview", None) is bridge._collect_design_overview
        and getattr(extracted, "_guidance_state_snapshot", None) is bridge._guidance_state_snapshot
        and getattr(extracted, "evaluate_candidate_full", None) is bridge.evaluate_candidate_full
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == (True, 0.7, None)
        and call_record.get("state") == {"D": 600}
        and call_record.get("updates") == {"D": 650}
        and call_record.get("bound_overview") is True
        and call_record.get("bound_snapshot") is True
        and call_record.get("bound_evaluate") is True
    )

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "case_results": cases,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
    }
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_design_guide_preview_contract_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_design_guide_preview_contract_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Preview Contract Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                "",
                "## Checks",
                "",
                *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(result["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
