"""Verify recommendation compound candidate extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "recommendation_compound_candidates.py"
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

    bridge_node = _function_node(bridge_source, "_append_geometry_bottom_compound_candidates")
    module_node = _function_node(module_source, "_append_geometry_bottom_compound_candidates")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    dependency_block = module_source.split("def _append_geometry_bottom_compound_candidates", 1)[0]

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 55,
        "bridge_binds_dependencies": "runtime=RecommendationCompoundRuntime(" in bridge_body,
        "bridge_delegates_to_extracted_module": "_append_geometry_bottom_compound_candidates_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 190,
        "module_has_dependency_binder": (
            "class RecommendationCompoundRuntime" in module_source
            and "globals().update" not in module_source
        ),
        "module_does_not_bind_nested_false_positives": all(
            name not in dependency_block
            for name in (
                '"_consume_axis"',
                '"_trace_sample"',
                '"axis"',
                '"reason"',
                '"result"',
                '"score"',
                '"seed_limit"',
                '"selected_key"',
                '"trials_key"',
            )
        ),
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
    }

    import inputs_page_app_contract_bridge as bridge
    import inputs_page_modules.recommendation_compound_candidates as extracted

    original = bridge._append_geometry_bottom_compound_candidates_extracted
    call_record: dict = {}

    def _fake_extracted(
        *,
        state: dict,
        seed_candidate: dict,
        candidates: list[dict],
        mode_config: dict,
        context: dict,
        eval_cache: dict,
        metrics: dict,
        compound_stats: dict,
        compound_trace_log: list,
        runtime,
    ) -> None:
        call_record.update(
            {
                "candidates": list(candidates),
                "state": dict(state),
                "bottom_rec": dict(seed_candidate),
                "mode_config": dict(mode_config),
                "context": dict(context or {}),
                "compound_trace_log": list(compound_trace_log or []),
                "bound_helper": runtime.evaluate_candidate_fast
                is bridge._evaluate_candidate_fast,
            }
        )
        candidates.append({"added": True})

    candidates = [{"existing": True}]
    try:
        bridge._append_geometry_bottom_compound_candidates_extracted = _fake_extracted
        returned = bridge._append_geometry_bottom_compound_candidates(
            candidates,
            {"D": 600},
            {"updates": {"bot1_count": 4}},
            {"goal": "balanced"},
            context={"trace": True},
            compound_trace_log=[{"before": True}],
        )
    finally:
        bridge._append_geometry_bottom_compound_candidates_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        call_record.get("bound_helper") is True
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned is None
        and candidates == [{"existing": True}, {"added": True}]
        and call_record.get("state") == {"D": 600}
        and call_record.get("bottom_rec") == {"updates": {"bot1_count": 4}}
        and call_record.get("mode_config") == {"goal": "balanced"}
        and call_record.get("context") == {"trace": True}
        and call_record.get("compound_trace_log") == [{"before": True}]
        and call_record.get("bound_helper") is True
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
    json_path = ARTIFACTS / f"inputs_page_recommendation_compound_candidates_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_recommendation_compound_candidates_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Recommendation Compound Candidates Extraction",
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
