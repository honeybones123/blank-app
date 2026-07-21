"""Verify Design Guide display-truth extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "display_truth.py"
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


def _module_cases() -> list[dict[str, Any]]:
    from inputs_page_modules.design_guide import display_truth as extracted

    def _parse(value: object) -> float | None:
        try:
            return None if value is None or value == "" else float(value)
        except (TypeError, ValueError):
            return None

    def _status(overview: dict | None) -> str | None:
        ov = overview if isinstance(overview, dict) else {}
        statuses = dict(ov.get("statuses") or {})
        if any(str(v or "").strip().upper() == "FAIL" for v in statuses.values()):
            return "FAIL"
        if statuses:
            return "PASS"
        return str(ov.get("status") or "").strip().upper() or None

    extracted.bind_display_truth_dependencies(
        {
            "_design_guide_status_from_overview": _status,
            "_design_mode_config": lambda goal=None: {"target_util_min": 0.8, "target_util_max": 1.0},
            "_design_optimisation_goal": lambda state=None: "balanced",
            "_guidance_item_expected_util": lambda item: (item or {}).get("expected_util"),
            "_parse_util_value": _parse,
            "_resolved_efficiency_target_band": lambda mode_config, **kwargs: (0.8, 1.0, False),
        }
    )
    overview = {"worst_util": 0.90, "statuses": {"bending": "PASS"}}
    cases = {
        "published_summary": extracted._design_guide_display_truth_for_item(
            {"title": "No action"},
            state={},
            overview=overview,
        ),
        "candidate_preview": extracted._design_guide_display_truth_for_item(
            {
                "action_type": "apply",
                "button_contract": {"expected_util": 0.96, "preview_pass": True},
                "resolved_candidate": {"overview": {"statuses": {"bending": "FAIL"}}},
            },
            state={},
            overview=overview,
        ),
        "post_commit_truth": extracted._design_guide_display_truth_for_item(
            {"source_post_commit_util": 0.82},
            state={},
            overview=overview,
            source_override="post_commit_truth",
            post_commit_status="PASS",
        ),
        "existing_source": extracted._design_guide_display_truth_for_item(
            {
                "display_truth": {"display_truth_source": "published_summary"},
                "action_type": "apply",
                "expected_util": 0.99,
            },
            state={},
            overview=overview,
        ),
        "preview_pass_fallback": extracted._design_guide_display_truth_for_item(
            {
                "action_type": "apply",
                "button_contract": {"expected_util": 0.93, "preview_pass": True},
            },
            state={},
            overview=overview,
        ),
    }
    return [
        {
            "name": "published_summary_uses_summary_util",
            "passed": cases["published_summary"]["display_truth_source"] == "published_summary"
            and cases["published_summary"]["displayed_util"] == 0.90
            and cases["published_summary"]["displayed_status"] == "PASS"
            and cases["published_summary"]["displayed_within_target_band"] is True,
            "result": cases["published_summary"],
        },
        {
            "name": "candidate_preview_uses_candidate_contract",
            "passed": cases["candidate_preview"]["display_truth_source"] == "candidate_preview"
            and cases["candidate_preview"]["displayed_util"] == 0.96
            and cases["candidate_preview"]["displayed_status"] == "FAIL",
            "result": cases["candidate_preview"],
        },
        {
            "name": "post_commit_truth_uses_post_commit_inputs",
            "passed": cases["post_commit_truth"]["display_truth_source"] == "post_commit_truth"
            and cases["post_commit_truth"]["displayed_util"] == 0.82
            and cases["post_commit_truth"]["displayed_status"] == "PASS",
            "result": cases["post_commit_truth"],
        },
        {
            "name": "existing_source_precedence_preserved",
            "passed": cases["existing_source"]["display_truth_source"] == "published_summary"
            and cases["existing_source"]["displayed_util"] == 0.90,
            "result": cases["existing_source"],
        },
        {
            "name": "preview_contract_status_fallback_preserved",
            "passed": cases["preview_pass_fallback"]["displayed_status"] == "PREVIEW_PASS"
            and cases["preview_pass_fallback"]["source_candidate_util"] == 0.93,
            "result": cases["preview_pass_fallback"],
        },
    ]


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    bridge_node = _function_node(bridge_source, "_design_guide_display_truth_for_item")
    module_node = _function_node(module_source, "_design_guide_display_truth_for_item")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    module_body = ast.get_source_segment(module_source, module_node) or ""

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import display_truth as extracted

    original_delegate = bridge._design_guide_display_truth_for_item_extracted
    call_record: dict[str, Any] = {}

    def _fake_delegate(item: dict | None, **kwargs) -> dict:
        call_record.update(
            {
                "item": dict(item or {}),
                "kwargs": dict(kwargs),
                "bound_parse": getattr(extracted, "_parse_util_value", None) is bridge._parse_util_value,
                "bound_expected": getattr(extracted, "_guidance_item_expected_util", None)
                is bridge._guidance_item_expected_util,
                "bound_status": getattr(extracted, "_design_guide_status_from_overview", None)
                is bridge._design_guide_status_from_overview,
                "bound_band": getattr(extracted, "_resolved_efficiency_target_band", None)
                is bridge._resolved_efficiency_target_band,
            }
        )
        return {"delegated": True}

    try:
        bridge._design_guide_display_truth_for_item_extracted = _fake_delegate
        delegated = bridge._design_guide_display_truth_for_item(
            {"action_type": "apply"},
            state={"b": 300.0},
            overview={"worst_util": 0.9},
            source_override="candidate_preview",
            post_commit_util=0.88,
            post_commit_status="PASS",
        )
    finally:
        bridge._design_guide_display_truth_for_item_extracted = original_delegate

    cases = _module_cases()
    checks = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 20,
        "bridge_binds_dependencies": "_bind_display_truth_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_module": "_design_guide_display_truth_for_item_extracted(" in bridge_body,
        "bridge_removed_display_truth_body": "existing_source in DESIGN_GUIDE_DISPLAY_TRUTH_SOURCES" not in bridge_body
        and "source_candidate_util = _design_guide_candidate_util(item)" not in bridge_body,
        "module_keeps_display_truth_body": "existing_source in DESIGN_GUIDE_DISPLAY_TRUTH_SOURCES" in module_body
        and "source_candidate_util = _design_guide_candidate_util(item)" in module_body,
        "module_has_dependency_binder": "def bind_display_truth_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "bridge_runtime_delegates_with_arguments": delegated == {"delegated": True}
        and call_record.get("item") == {"action_type": "apply"}
        and call_record.get("kwargs", {}).get("state") == {"b": 300.0}
        and call_record.get("kwargs", {}).get("overview") == {"worst_util": 0.9}
        and call_record.get("kwargs", {}).get("source_override") == "candidate_preview"
        and call_record.get("kwargs", {}).get("post_commit_util") == 0.88
        and call_record.get("kwargs", {}).get("post_commit_status") == "PASS",
        "bridge_runtime_binds_dependencies": call_record.get("bound_parse") is True
        and call_record.get("bound_expected") is True
        and call_record.get("bound_status") is True
        and call_record.get("bound_band") is True,
        "module_cases_pass": all(row["passed"] for row in cases),
    }
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
    json_path = ARTIFACTS / f"inputs_page_design_guide_display_truth_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_design_guide_display_truth_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Display Truth Extraction",
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
