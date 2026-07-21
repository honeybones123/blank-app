from __future__ import annotations

import ast
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.design_guide import recommendation_result_builder


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "recommendation_result_builder.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _bind(pending: dict | None = None) -> None:
    def ensure_guidance_item_resolved_candidate_payload(item: dict, state: dict | None = None) -> None:
        item["resolved_payload_checked"] = True
        item["state_seen"] = dict(state or {})

    def build_pending_recommendation(item: dict, base_state: dict) -> dict | None:
        if pending is None:
            return {
                "title": "Pending title",
                "updates": {"D": 650, "b": 350},
                "action_type": "apply_geometry_recommendation",
                "action_payload": {"updates": {"D": 650, "b": 350}},
            }
        return pending

    recommendation_result_builder.bind_recommendation_result_builder_dependencies(
        {
            "_build_pending_recommendation": build_pending_recommendation,
            "_ensure_guidance_item_resolved_candidate_payload": ensure_guidance_item_resolved_candidate_payload,
        }
    )


def _expected_recommendation_id(title: str, updates: dict) -> str:
    stable = {
        "title": title,
        "updates": sorted((str(k), updates[k]) for k in sorted(updates.keys())),
    }
    return hashlib.sha256(json.dumps(stable, default=str, sort_keys=True).encode("utf-8")).hexdigest()


def _case_results() -> list[dict[str, Any]]:
    _bind()
    source_item = {
        "canonical_winner_label": "Canonical winner",
        "title_main": "Fallback title",
        "primary_action": "Increase geometry",
        "reasoning": "Needs more capacity",
        "util": "0.91",
        "status": "FAIL",
        "bucket": "strength",
        "title_locked_from_final_winner": True,
    }
    result = recommendation_result_builder._build_recommendation_result_from_guidance_item(
        source_item,
        {"D": 600},
        branch=" direct_target ",
        request_kind="",
    )
    expected_id = _expected_recommendation_id("Canonical winner", {"D": 650, "b": 350})
    expected_winner_id = hashlib.sha256(
        f"apply_geometry_recommendation|{expected_id}".encode("utf-8")
    ).hexdigest()

    _bind({"title": "No updates", "updates": {}, "action_type": "noop", "action_payload": {}})
    no_updates = recommendation_result_builder._build_recommendation_result_from_guidance_item(
        {"title_main": "No updates"},
        {},
    )

    _bind(None)
    return [
        {
            "name": "non_dict_item_returns_none",
            "passed": recommendation_result_builder._build_recommendation_result_from_guidance_item(None, {}) is None,
        },
        {
            "name": "empty_updates_returns_none",
            "passed": no_updates is None,
        },
        {
            "name": "canonical_result_contract_is_built",
            "passed": isinstance(result, dict)
            and result["recommendation_id"] == expected_id
            and result["winner_id"] == expected_winner_id
            and result["title"] == "Canonical winner"
            and result["summary"] == "Increase geometry"
            and result["reasoning"] == "Needs more capacity"
            and result["source"] == "recommendation_engine"
            and result["request_kind"] == "design_guide"
            and result["branch"] == "direct_target"
            and result["updates"] == {"D": 650, "b": 350}
            and result["metrics"] == {"util": 0.91, "status": "FAIL", "bucket": "strength"}
            and result["apply"] == {
                "mode": "apply_geometry_recommendation",
                "payload": {"updates": {"D": 650, "b": 350}},
            }
            and result["canonical_winner_label"] == "Canonical winner"
            and result["title_locked_from_final_winner"] is True,
            "result": result,
        },
        {
            "name": "source_item_is_not_mutated_by_payload_resolution",
            "passed": "resolved_payload_checked" not in source_item
            and "state_seen" not in source_item,
            "source_item": source_item,
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Recommendation Result Builder Extraction",
        "",
        f"## Decision: {payload['decision']}",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    bridge_source = _read(BRIDGE)
    module_source = _read(MODULE)
    bridge_helper = _function_source(bridge_source, "_build_recommendation_result_from_guidance_item")
    module_helper = _function_source(module_source, "_build_recommendation_result_from_guidance_item")
    cases = _case_results()
    checks = {
        "module_exists": MODULE.exists(),
        "bridge_imports_extracted_helper": "_build_recommendation_result_from_guidance_item_extracted" in bridge_source,
        "bridge_helper_is_thin_delegate": len(bridge_helper.splitlines()) <= 15,
        "bridge_binds_builder_dependencies": "_bind_recommendation_result_builder_dependencies(globals())" in bridge_helper,
        "bridge_delegates_to_extracted": "_build_recommendation_result_from_guidance_item_extracted(" in bridge_helper,
        "bridge_removed_builder_body": "recommendation_engine" not in bridge_helper
        and "title_locked_from_final_winner" not in bridge_helper,
        "module_keeps_builder_body": "recommendation_engine" in module_helper
        and "title_locked_from_final_winner" in module_helper,
        "module_has_dependency_binder": "def bind_recommendation_result_builder_dependencies" in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "all_cases_pass": all(row["passed"] for row in cases),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in cases if not row["passed"])
    decision = (
        "INPUTS_PAGE_RECOMMENDATION_RESULT_BUILDER_EXTRACTION_LOCKED"
        if not failures
        else "GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_page_recommendation_result_builder_extraction",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "case_results": cases,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_behavior_changed": False,
        "engineering_calculations_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_page_recommendation_result_builder_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_recommendation_result_builder_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_recommendation_result_builder_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
