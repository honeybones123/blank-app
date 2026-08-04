"""Verify governing-domain tightening candidate extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "governing_domain_tightening_candidates.py"
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

    bridge_node = _function_node(bridge_source, "_generate_tightening_candidates_for_governing_domain")
    module_node = _function_node(module_source, "_generate_tightening_candidates_for_governing_domain")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 18,
        "bridge_binds_dependencies": "_bind_governing_domain_tightening_candidates_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_generate_tightening_candidates_for_governing_domain_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 160,
        "module_has_dependency_binder": "def bind_governing_domain_tightening_candidates_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_tightening_contract_surface": (
            "Governing-action-first tightening candidate orchestration" in module_source
            and "tightening_domain_candidate" in module_source
            and "candidate_families_considered" in module_source
            and "candidate_families_pruned" in module_source
            and "candidate_family_depth_reached" in module_source
            and "multi_domain_refinement" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import governing_domain_tightening_candidates as extracted

    original = bridge._generate_tightening_candidates_for_governing_domain_extracted
    call_record: dict = {}

    def _fake_extracted(
        working_state: dict,
        cur_eval: dict,
        mode_config: dict,
        *,
        tightening_step_count: int = 0,
    ) -> tuple[list[dict], dict]:
        call_record.update(
            {
                "working_state": dict(working_state),
                "cur_eval": dict(cur_eval),
                "mode_config": dict(mode_config),
                "tightening_step_count": tightening_step_count,
                "bound_focus": getattr(extracted, "_governing_focus_from_overview", None) is bridge._governing_focus_from_overview,
                "bound_diff": getattr(extracted, "_one_click_diff_accumulated_updates", None) is bridge._one_click_diff_accumulated_updates,
                "bound_shear_candidates": (
                    getattr(extracted, "_generate_shear_governing_candidates", None)
                    is bridge._generate_shear_governing_candidates
                ),
            }
        )
        return ([{"title": "Tightening: fake"}], {"governing_domain": "bending"})

    try:
        bridge._generate_tightening_candidates_for_governing_domain_extracted = _fake_extracted
        returned = bridge._generate_tightening_candidates_for_governing_domain(
            {"D": 600},
            {"overview": {"statuses": {"bending": "PASS"}}},
            {"target_util_min": 0.85},
            tightening_step_count=2,
        )
    finally:
        bridge._generate_tightening_candidates_for_governing_domain_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_governing_focus_from_overview", None) is bridge._governing_focus_from_overview
        and getattr(extracted, "_candidate_objective_util", None) is bridge._candidate_objective_util
        and getattr(extracted, "_one_click_diff_accumulated_updates", None)
        is bridge._one_click_diff_accumulated_updates
        and getattr(extracted, "generate_less_bottom_reo_variants", None)
        is bridge.generate_less_bottom_reo_variants
        and getattr(extracted, "_generate_shear_governing_candidates", None)
        is bridge._generate_shear_governing_candidates
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == ([{"title": "Tightening: fake"}], {"governing_domain": "bending"})
        and call_record.get("working_state") == {"D": 600}
        and call_record.get("cur_eval") == {"overview": {"statuses": {"bending": "PASS"}}}
        and call_record.get("mode_config") == {"target_util_min": 0.85}
        and call_record.get("tightening_step_count") == 2
        and call_record.get("bound_focus") is True
        and call_record.get("bound_diff") is True
        and call_record.get("bound_shear_candidates") is True
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
    json_path = ARTIFACTS / f"inputs_page_governing_domain_tightening_candidates_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_governing_domain_tightening_candidates_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Governing Domain Tightening Candidates Extraction",
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
