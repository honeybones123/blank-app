"""Verify candidate-search evidence extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "candidate_search_evidence.py"
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

    bridge_node = _function_node(bridge_source, "_build_candidate_search_evidence")
    bridge_align_node = _function_node(bridge_source, "_align_guidance_items_to_candidate_search_evidence")
    bridge_row_node = _function_node(bridge_source, "_candidate_search_summary_row")
    bridge_distance_node = _function_node(bridge_source, "_candidate_search_distance_to_band")
    module_node = _function_node(module_source, "_build_candidate_search_evidence")
    module_align_node = _function_node(module_source, "_align_guidance_items_to_candidate_search_evidence")
    module_row_node = _function_node(module_source, "_candidate_search_summary_row")
    module_distance_node = _function_node(module_source, "_candidate_search_distance_to_band")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    bridge_align_body = ast.get_source_segment(bridge_source, bridge_align_node) or ""
    bridge_row_body = ast.get_source_segment(bridge_source, bridge_row_node) or ""
    bridge_distance_body = ast.get_source_segment(bridge_source, bridge_distance_node) or ""
    dependency_section = module_source.partition("def bind_candidate_search_evidence_dependencies")[0]

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 20,
        "bridge_binds_dependencies": "_bind_candidate_search_evidence_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_build_candidate_search_evidence_extracted" in bridge_body,
        "bridge_align_wrapper_is_small": (bridge_align_node.end_lineno or bridge_align_node.lineno)
        - bridge_align_node.lineno
        + 1
        <= 5,
        "bridge_align_binds_dependencies": "_bind_candidate_search_evidence_dependencies(globals())" in bridge_align_body,
        "bridge_align_delegates_to_extracted_module": "_align_guidance_items_to_candidate_search_evidence_extracted" in bridge_align_body,
        "bridge_row_wrapper_is_small": (bridge_row_node.end_lineno or bridge_row_node.lineno)
        - bridge_row_node.lineno
        + 1
        <= 15,
        "bridge_row_delegates_to_extracted_module": "_candidate_search_summary_row_extracted(" in bridge_row_body,
        "bridge_distance_wrapper_is_small": (bridge_distance_node.end_lineno or bridge_distance_node.lineno)
        - bridge_distance_node.lineno
        + 1
        <= 3,
        "bridge_distance_delegates_to_extracted_module": "_candidate_search_distance_to_band_extracted(" in bridge_distance_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 128,
        "module_contains_align_body": (module_align_node.end_lineno or module_align_node.lineno)
        - module_align_node.lineno
        + 1
        >= 65,
        "module_contains_local_summary_row": (module_row_node.end_lineno or module_row_node.lineno)
        - module_row_node.lineno
        + 1
        >= 90,
        "module_contains_local_distance_helper": (module_distance_node.end_lineno or module_distance_node.lineno)
        - module_distance_node.lineno
        + 1
        >= 10,
        "module_dependency_tuple_binds_target_band_constants": all(
            token in dependency_section
            for token in ('"EFFICIENCY_TARGET_UTIL_MIN"', '"EFFICIENCY_TARGET_UTIL_MAX"')
        )
        or (
            "from inputs_application.policy_constants import (" in module_source
            and "EFFICIENCY_TARGET_UTIL_MIN," in module_source
            and "EFFICIENCY_TARGET_UTIL_MAX," in module_source
        ),
        "module_has_dependency_binder": "def bind_candidate_search_evidence_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_evidence_contract_surface": all(
            token in module_source
            for token in (
                "candidate_search_exhaustive",
                "search_scope",
                "target_low",
                "target_high",
                "safe_executor_backed_candidates_count",
                "target_band_candidate_count",
                "selected_candidate_id",
                "closest_safe_candidate_id",
                "best_target_band_candidate_id",
                "target_band_candidates",
                "safe_executor_backed_candidates",
                "rejected_target_band_candidates",
                "outside_target_band_allowed_reason",
                "discrete_increment_limit",
                "_candidate_search_summary_row",
                "_candidate_search_distance_to_band",
                "_align_guidance_items_to_candidate_search_evidence",
                "resolved_candidate_reaches_target_band",
                "apply_resolved_candidate",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import candidate_search_evidence as extracted

    original = bridge._build_candidate_search_evidence_extracted
    call_record: dict = {}

    def _fake_extracted(
        *,
        selected_candidate: dict | None,
        all_candidates: list[dict],
        target_low: float,
        target_high: float,
        exhaustive: bool,
        search_scope: str,
        selected_title: str | None = None,
    ) -> dict:
        call_record.update(
            {
                "selected_candidate": dict(selected_candidate or {}),
                "all_candidates": list(all_candidates),
                "target_low": target_low,
                "target_high": target_high,
                "exhaustive": exhaustive,
                "search_scope": search_scope,
                "selected_title": selected_title,
                "summary_row_is_local": getattr(extracted, "_candidate_search_summary_row", None)
                is not bridge._candidate_search_summary_row,
                "distance_helper_is_local": getattr(extracted, "_candidate_search_distance_to_band", None)
                is not bridge._candidate_search_distance_to_band,
                "align_is_local": getattr(extracted, "_align_guidance_items_to_candidate_search_evidence", None)
                is not bridge._align_guidance_items_to_candidate_search_evidence,
                "target_min_bound": getattr(extracted, "EFFICIENCY_TARGET_UTIL_MIN", None)
                == bridge.EFFICIENCY_TARGET_UTIL_MIN,
                "target_max_bound": getattr(extracted, "EFFICIENCY_TARGET_UTIL_MAX", None)
                == bridge.EFFICIENCY_TARGET_UTIL_MAX,
            }
        )
        return {"candidate_search_exhaustive": bool(exhaustive)}

    selected = {"candidate_id": "sel"}
    try:
        bridge._build_candidate_search_evidence_extracted = _fake_extracted
        returned = bridge._build_candidate_search_evidence(
            selected_candidate=selected,
            all_candidates=[selected],
            target_low=0.85,
            target_high=0.95,
            exhaustive=True,
            search_scope="focused",
            selected_title="Selected",
        )
    finally:
        bridge._build_candidate_search_evidence_extracted = original

    checks["bridge_runtime_keeps_row_and_distance_local_to_module"] = (
        getattr(extracted, "_candidate_search_summary_row", None) is not bridge._candidate_search_summary_row
        and getattr(extracted, "_candidate_search_distance_to_band", None) is not bridge._candidate_search_distance_to_band
        and getattr(extracted, "_align_guidance_items_to_candidate_search_evidence", None)
        is not bridge._align_guidance_items_to_candidate_search_evidence
        and getattr(extracted, "EFFICIENCY_TARGET_UTIL_MIN", None) == bridge.EFFICIENCY_TARGET_UTIL_MIN
        and getattr(extracted, "EFFICIENCY_TARGET_UTIL_MAX", None) == bridge.EFFICIENCY_TARGET_UTIL_MAX
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"candidate_search_exhaustive": True}
        and call_record.get("selected_candidate") == {"candidate_id": "sel"}
        and call_record.get("all_candidates") == [{"candidate_id": "sel"}]
        and call_record.get("target_low") == 0.85
        and call_record.get("target_high") == 0.95
        and call_record.get("exhaustive") is True
        and call_record.get("search_scope") == "focused"
        and call_record.get("selected_title") == "Selected"
        and call_record.get("summary_row_is_local") is True
        and call_record.get("distance_helper_is_local") is True
        and call_record.get("align_is_local") is True
        and call_record.get("target_min_bound") is True
        and call_record.get("target_max_bound") is True
    )

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_candidate_search_evidence_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_candidate_search_evidence_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Candidate Search Evidence Extraction",
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
