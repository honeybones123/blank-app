"""Verify resolved-candidate guidance item extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "resolved_candidate_guidance_item.py"
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


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")

    bridge_node = _function_node(bridge_source, "_guidance_item_from_resolved_candidate")
    bridge_ensure_node = _function_node(bridge_source, "_ensure_guidance_item_resolved_candidate_payload")
    module_node = _function_node(module_source, "_guidance_item_from_resolved_candidate")
    module_ensure_node = _function_node(module_source, "_ensure_guidance_item_resolved_candidate_payload")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    bridge_ensure_body = ast.get_source_segment(bridge_source, bridge_ensure_node) or ""
    module_ensure_body = ast.get_source_segment(module_source, module_ensure_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 20,
        "bridge_binds_dependencies": "_bind_resolved_candidate_guidance_item_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_guidance_item_from_resolved_candidate_extracted" in bridge_body,
        "bridge_ensure_wrapper_is_tiny": (
            bridge_ensure_node.end_lineno or bridge_ensure_node.lineno
        ) - bridge_ensure_node.lineno + 1 <= 3,
        "bridge_ensure_binds_dependencies": "_bind_resolved_candidate_guidance_item_dependencies(globals())" in bridge_ensure_body,
        "bridge_ensure_delegates_to_extracted_module": "_ensure_guidance_item_resolved_candidate_payload_extracted" in bridge_ensure_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 170,
        "module_contains_ensure_body": (
            module_ensure_node.end_lineno or module_ensure_node.lineno
        ) - module_ensure_node.lineno + 1 >= 65,
        "module_has_dependency_binder": "def bind_resolved_candidate_guidance_item_dependencies" in module_source,
        "module_binds_resolve_recommendation_updates": '"_resolve_recommendation_updates"' in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_payload_contract_surface": (
            "resolved_candidate_updates" in module_source
            and "force_direct_apply" in module_source
            and "guidance_before_after" in module_source
            and "failure_coverage" in module_source
            and "has_resolved_candidate_payload" in module_source
            and "title_locked_from_final_winner" in module_source
        ),
        "module_keeps_ensure_payload_contract_surface": all(
            token in module_ensure_body
            for token in (
                "resolved_candidate_updates",
                "resolved_candidate_label",
                "resolved_candidate_action_type",
                "candidate_reaches_target_band",
                "title_locked_from_final_winner",
                "has_resolved_candidate_payload",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import resolved_candidate_guidance_item as extracted

    original = bridge._guidance_item_from_resolved_candidate_extracted
    original_ensure = bridge._ensure_guidance_item_resolved_candidate_payload_extracted
    call_record: dict = {}
    ensure_call_record: dict = {}

    def _fake_extracted(
        candidate: dict,
        *,
        state: dict,
        overview: dict,
        title: str | None = None,
        reasoning: str | None = None,
        status: str = "FAIL",
        primary_action: str = "Apply recommendation",
    ) -> dict:
        call_record.update(
            {
                "candidate": dict(candidate),
                "state": dict(state),
                "overview": dict(overview),
                "title": title,
                "reasoning": reasoning,
                "status": status,
                "primary_action": primary_action,
                "bound_guidance_item": (
                    getattr(extracted, "_guidance_item", None)
                    is bridge._guidance_item
                ),
                "bound_failure_coverage": (
                    getattr(extracted, "_candidate_failure_coverage_summary", None)
                    is bridge._candidate_failure_coverage_summary
                ),
                "bound_title_resolver": (
                    getattr(extracted, "_resolve_canonical_guidance_title_from_candidate", None)
                    is bridge._resolve_canonical_guidance_title_from_candidate
                ),
            }
        )
        return {"title_main": "fake resolved"}

    def _fake_ensure(item: dict, state: dict | None = None) -> None:
        ensure_call_record.update(
            {
                "item_before": dict(item),
                "state": dict(state or {}),
                "bound_resolve_updates": (
                    getattr(extracted, "_resolve_recommendation_updates", None)
                    is bridge._resolve_recommendation_updates
                ),
            }
        )
        item["ensured_by_fake_delegate"] = True

    try:
        bridge._guidance_item_from_resolved_candidate_extracted = _fake_extracted
        bridge._ensure_guidance_item_resolved_candidate_payload_extracted = _fake_ensure
        returned = bridge._guidance_item_from_resolved_candidate(
            {"updates": {"D": 650}, "label": "Resolved"},
            state={"D": 600},
            overview={"worst_util": 1.04},
            title="Resolved title",
            reasoning="Because target band.",
            status="WARN",
            primary_action="Apply recommendation",
        )
        ensure_item = {"action_type": "apply", "title_main": "Ensure"}
        bridge._ensure_guidance_item_resolved_candidate_payload(ensure_item, state={"D": 600})
    finally:
        bridge._guidance_item_from_resolved_candidate_extracted = original
        bridge._ensure_guidance_item_resolved_candidate_payload_extracted = original_ensure

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_guidance_item", None) is bridge._guidance_item
        and getattr(extracted, "_candidate_failure_coverage_summary", None)
        is bridge._candidate_failure_coverage_summary
        and getattr(extracted, "_guidance_before_after_text", None)
        is bridge._guidance_before_after_text
        and getattr(extracted, "_guidance_compact_change_text", None)
        is bridge._guidance_compact_change_text
        and getattr(extracted, "_resolve_recommendation_updates", None)
        is bridge._resolve_recommendation_updates
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"title_main": "fake resolved"}
        and call_record.get("candidate") == {"updates": {"D": 650}, "label": "Resolved"}
        and call_record.get("state") == {"D": 600}
        and call_record.get("overview") == {"worst_util": 1.04}
        and call_record.get("title") == "Resolved title"
        and call_record.get("reasoning") == "Because target band."
        and call_record.get("status") == "WARN"
        and call_record.get("primary_action") == "Apply recommendation"
        and call_record.get("bound_guidance_item") is True
        and call_record.get("bound_failure_coverage") is True
        and call_record.get("bound_title_resolver") is True
    )
    checks["bridge_ensure_runtime_delegates_with_arguments"] = (
        ensure_item.get("ensured_by_fake_delegate") is True
        and ensure_call_record.get("item_before") == {"action_type": "apply", "title_main": "Ensure"}
        and ensure_call_record.get("state") == {"D": 600}
        and ensure_call_record.get("bound_resolve_updates") is True
    )

    def _fake_resolve_updates(item: dict, state: dict | None = None) -> dict:
        return dict(item.get("resolver_updates") or {})

    extracted.bind_resolved_candidate_guidance_item_dependencies(
        {"_resolve_recommendation_updates": _fake_resolve_updates}
    )
    candidate_item = {
        "action_type": "apply",
        "title_main": "Candidate item",
        "resolved_candidate": {"updates": {"D": 650}, "action_type": "candidate_action"},
    }
    extracted._ensure_guidance_item_resolved_candidate_payload(candidate_item, state={})
    payload_item = {
        "action_type": "apply",
        "action_payload": {
            "resolved_candidate_updates": {"b": 350},
            "resolved_candidate_label": "Payload label",
            "resolved_candidate_action_type": "payload_action",
            "resolved_candidate_post_util": 0.91,
            "resolved_candidate_reaches_target_band": True,
        },
    }
    extracted._ensure_guidance_item_resolved_candidate_payload(payload_item, state={})
    resolver_item = {
        "action_type": "apply",
        "title_main": "Resolver item",
        "resolver_updates": {"s_lig": 175},
    }
    extracted._ensure_guidance_item_resolved_candidate_payload(resolver_item, state={})
    no_update_item = {"action_type": "apply", "title_main": "No update"}
    extracted._ensure_guidance_item_resolved_candidate_payload(no_update_item, state={})
    locked_item = {
        "action_type": "apply",
        "canonical_winner_label": "Canonical winner",
        "title_locked_from_final_winner": True,
        "resolved_candidate": {"updates": {"D": 625}},
    }
    extracted._ensure_guidance_item_resolved_candidate_payload(locked_item, state={})
    checks["module_ensure_runtime_cases"] = (
        candidate_item.get("has_resolved_candidate_payload") is True
        and candidate_item["action_payload"]["resolved_candidate_updates"] == {"D": 650}
        and candidate_item["resolved_candidate"]["action_type"] == "candidate_action"
        and payload_item["resolved_candidate"]["candidate_post_util"] == 0.91
        and payload_item["resolved_candidate"]["candidate_reaches_target_band"] is True
        and payload_item["action_payload"]["resolved_candidate_label"] == "Payload label"
        and resolver_item["action_payload"]["resolved_candidate_updates"] == {"s_lig": 175}
        and no_update_item.get("has_resolved_candidate_payload") is False
        and locked_item["resolved_candidate"]["label"] == "Canonical winner"
        and locked_item["resolved_candidate"]["title_locked_from_final_winner"] is True
    )

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "bridge_ensure_wrapper_lines": (
            bridge_ensure_node.end_lineno or bridge_ensure_node.lineno
        ) - bridge_ensure_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
        "module_ensure_function_lines": (
            module_ensure_node.end_lineno or module_ensure_node.lineno
        ) - module_ensure_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_resolved_candidate_guidance_item_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_resolved_candidate_guidance_item_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Resolved Candidate Guidance Item Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Bridge ensure wrapper lines: {result['bridge_ensure_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                f"- Extracted module ensure function lines: {result['module_ensure_function_lines']}",
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
