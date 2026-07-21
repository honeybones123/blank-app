"""Verify Design Guide button-contract extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "button_contract.py"
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
    from inputs_page_modules.design_guide import button_contract as extracted

    def _family(item: dict | None) -> str:
        return str((item or {}).get("family") or "unknown")

    def _expected_util(item: dict | None) -> float | None:
        value = (item or {}).get("expected_util") if isinstance(item, dict) else None
        return None if value is None else float(value)

    def _source_candidate_id(item: dict | None) -> str | None:
        return (item or {}).get("source_candidate_id") if isinstance(item, dict) else None

    def _normalise(candidate_id: str | None, *, family: str, updates: dict) -> str:
        seed = str(candidate_id or "generated")
        return f"{family}:{seed}:{len(dict(updates or {}))}"

    def _ensure(item: dict, *, state: dict) -> None:
        if item.get("force_resolved_payload"):
            item.setdefault("action_payload", {})["resolved_candidate_updates"] = dict(item.get("updates") or {})

    def _resolve(item: dict, *, state: dict) -> dict:
        return dict(item.get("updates") or {})

    def _executor(item: dict, *, state: dict) -> tuple[bool, str | None]:
        return bool(item.get("executor_allowed", True)), item.get("executor_reason")

    def _preview(state: dict, updates: dict) -> tuple[bool, float | None, str | None]:
        if updates.get("preview_fail"):
            return False, 0.91, "preview_failed_by_unit"
        return True, 0.77, None

    extracted.bind_button_contract_dependencies(
        {
            "_design_guide_preview_contract_for_updates": _preview,
            "_ensure_guidance_item_resolved_candidate_payload": _ensure,
            "_guidance_executor_actionability_contract": _executor,
            "_guidance_item_expected_util": _expected_util,
            "_guidance_item_family": _family,
            "_guidance_item_source_candidate_id": _source_candidate_id,
            "_normalise_design_guide_candidate_id": _normalise,
            "_resolve_recommendation_updates": _resolve,
        }
    )

    scenarios = {
        "invalid_item": extracted._design_guide_button_contract(None, state={}),
        "missing_action_type": extracted._design_guide_button_contract({"family": "bending"}, state={}),
        "missing_updates": extracted._design_guide_button_contract(
            {"action_type": "apply", "family": "bending"},
            state={},
        ),
        "executor_blocked": extracted._design_guide_button_contract(
            {
                "action_type": "apply",
                "family": "shear",
                "updates": {"s_lig": 150.0},
                "executor_allowed": False,
                "executor_reason": "executor_blocked_by_unit",
            },
            state={},
        ),
        "preview_blocked": extracted._design_guide_button_contract(
            {
                "action_type": "apply",
                "family": "geometry",
                "updates": {"preview_fail": True},
            },
            state={},
        ),
        "actionable_resolved": extracted._design_guide_button_contract(
            {
                "action_type": "apply",
                "family": "bending",
                "updates": {"b": 350.0},
                "source_candidate_id": "cand-1",
                "force_resolved_payload": True,
            },
            state={},
        ),
    }
    return [
        {
            "name": "invalid_item_blocks",
            "passed": scenarios["invalid_item"]["blocking_reason"] == "invalid_guidance_item"
            and scenarios["invalid_item"]["actionable"] is False,
            "result": scenarios["invalid_item"],
        },
        {
            "name": "missing_action_type_blocks",
            "passed": scenarios["missing_action_type"]["blocking_reason"] == "missing_action_type"
            and scenarios["missing_action_type"]["action_type"] is None,
            "result": scenarios["missing_action_type"],
        },
        {
            "name": "missing_updates_blocks",
            "passed": scenarios["missing_updates"]["blocking_reason"] == "missing_updates"
            and scenarios["missing_updates"]["updates"] == {},
            "result": scenarios["missing_updates"],
        },
        {
            "name": "executor_block_reason_preserved",
            "passed": scenarios["executor_blocked"]["blocking_reason"] == "executor_blocked_by_unit"
            and scenarios["executor_blocked"]["preview_pass"] is True,
            "result": scenarios["executor_blocked"],
        },
        {
            "name": "preview_block_reason_preserved",
            "passed": scenarios["preview_blocked"]["blocking_reason"] == "preview_failed_by_unit"
            and scenarios["preview_blocked"]["expected_util"] == 0.91,
            "result": scenarios["preview_blocked"],
        },
        {
            "name": "actionable_resolved_contract_preserved",
            "passed": scenarios["actionable_resolved"]["actionable"] is True
            and scenarios["actionable_resolved"]["action_type"] == "apply_resolved_candidate"
            and scenarios["actionable_resolved"]["updates"] == {"b": 350.0}
            and scenarios["actionable_resolved"]["source_candidate_id"] == "bending:cand-1:1",
            "result": scenarios["actionable_resolved"],
        },
    ]


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    bridge_node = _function_node(bridge_source, "_design_guide_button_contract")
    module_node = _function_node(module_source, "_design_guide_button_contract")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    module_body = ast.get_source_segment(module_source, module_node) or ""

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import button_contract as extracted

    original_delegate = bridge._design_guide_button_contract_extracted
    call_record: dict[str, Any] = {}

    def _fake_delegate(item: dict | None, *, state: dict, blocking_reason_override: str | None = None) -> dict:
        call_record.update(
            {
                "item": dict(item or {}),
                "state": dict(state),
                "blocking_reason_override": blocking_reason_override,
                "bound_resolve": getattr(extracted, "_resolve_recommendation_updates", None)
                is bridge._resolve_recommendation_updates,
                "bound_preview": getattr(extracted, "_design_guide_preview_contract_for_updates", None)
                is bridge._design_guide_preview_contract_for_updates,
                "bound_executor": getattr(extracted, "_guidance_executor_actionability_contract", None)
                is bridge._guidance_executor_actionability_contract,
            }
        )
        return {"delegated": True}

    try:
        bridge._design_guide_button_contract_extracted = _fake_delegate
        delegated = bridge._design_guide_button_contract(
            {"action_type": "apply"},
            state={"b": 300.0},
            blocking_reason_override="unit_override",
        )
    finally:
        bridge._design_guide_button_contract_extracted = original_delegate

    cases = _module_cases()
    checks = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 12,
        "bridge_binds_dependencies": "_bind_button_contract_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_module": "_design_guide_button_contract_extracted(" in bridge_body,
        "bridge_removed_contract_body": "_resolve_recommendation_updates(work" not in bridge_body
        and "_guidance_executor_actionability_contract(" not in bridge_body,
        "module_keeps_contract_body": "_resolve_recommendation_updates(work" in module_body
        and "_guidance_executor_actionability_contract(" in module_body,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "bridge_runtime_delegates_with_arguments": delegated == {"delegated": True}
        and call_record.get("item") == {"action_type": "apply"}
        and call_record.get("state") == {"b": 300.0}
        and call_record.get("blocking_reason_override") == "unit_override",
        "bridge_runtime_binds_dependencies": call_record.get("bound_resolve") is True
        and call_record.get("bound_preview") is True
        and call_record.get("bound_executor") is True,
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
    json_path = ARTIFACTS / f"inputs_page_design_guide_button_contract_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_design_guide_button_contract_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Button Contract Extraction",
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
