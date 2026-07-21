"""Verify shear recommendation rank-key extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "shear_candidate_generation.py"
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

    bridge_node = _function_node(bridge_source, "_shear_recommendation_rank_key")
    module_node = _function_node(module_source, "_shear_recommendation_rank_key")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 14,
        "bridge_binds_dependencies": "_bind_shear_candidate_generation_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_shear_recommendation_rank_key_extracted(" in bridge_body,
        "module_contains_rank_policy": all(
            token in ast.get_source_segment(module_source, module_node) or ""
            for token in (
                "_distance_to_target_band(",
                "EFFICIENCY_TARGET_UTIL_MIN",
                "EFFICIENCY_TARGET_UTIL_MAX",
                "TARGET_BAND_EPS",
                "_shear_candidate_type(",
                "_severe_shear_failure(",
                "update_complexity",
            )
        ),
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "rank_key_removed_from_dependency_contract": '"_shear_recommendation_rank_key"' not in module_source,
        "rank_dependencies_in_dependency_contract": all(
            token in module_source
            for token in (
                '"_distance_to_target_band"',
                '"EFFICIENCY_TARGET_UTIL_MIN"',
                '"EFFICIENCY_TARGET_UTIL_MAX"',
                '"TARGET_BAND_EPS"',
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import shear_candidate_generation as extracted

    original_delegate = bridge._shear_recommendation_rank_key_extracted
    call_record: dict = {}

    def _fake_delegate(candidate: dict, *, base_state: dict, severity_band: str, seed_shear_util: float | None) -> tuple:
        call_record.update(
            {
                "candidate": dict(candidate),
                "base_state": dict(base_state),
                "severity_band": severity_band,
                "seed_shear_util": seed_shear_util,
                "bound_distance": getattr(extracted, "_distance_to_target_band", None)
                is bridge._distance_to_target_band,
                "bound_target_min": getattr(extracted, "EFFICIENCY_TARGET_UTIL_MIN", None)
                == bridge.EFFICIENCY_TARGET_UTIL_MIN,
                "bound_target_max": getattr(extracted, "EFFICIENCY_TARGET_UTIL_MAX", None)
                == bridge.EFFICIENCY_TARGET_UTIL_MAX,
                "bound_target_eps": getattr(extracted, "TARGET_BAND_EPS", None)
                == bridge.TARGET_BAND_EPS,
                "bound_shear_type": getattr(extracted, "_shear_candidate_type", None)
                is bridge._shear_candidate_type,
                "bound_severe": getattr(extracted, "_severe_shear_failure", None)
                is bridge._severe_shear_failure,
            }
        )
        return ("delegated",)

    try:
        bridge._shear_recommendation_rank_key_extracted = _fake_delegate
        delegated = bridge._shear_recommendation_rank_key(
            {"label": "candidate", "overview": {"utils": {"shear": 0.92}}},
            base_state={"s_lig": 250.0},
            severity_band="severe",
            seed_shear_util=1.35,
        )
    finally:
        bridge._shear_recommendation_rank_key_extracted = original_delegate

    checks["bridge_runtime_delegates_with_arguments"] = (
        delegated == ("delegated",)
        and call_record.get("candidate", {}).get("label") == "candidate"
        and call_record.get("base_state") == {"s_lig": 250.0}
        and call_record.get("severity_band") == "severe"
        and call_record.get("seed_shear_util") == 1.35
    )
    checks["bridge_runtime_binds_rank_dependencies"] = all(
        call_record.get(name) is True
        for name in (
            "bound_distance",
            "bound_target_min",
            "bound_target_max",
            "bound_target_eps",
            "bound_shear_type",
            "bound_severe",
        )
    )

    extracted.bind_shear_candidate_generation_dependencies(bridge.__dict__)
    sample_rank = extracted._shear_recommendation_rank_key(
        {
            "label": "Spacing",
            "is_compliant": True,
            "reaches_target_band": True,
            "shear_candidate_type": "spacing",
            "overview": {"utils": {"shear": 0.9}},
            "updates": {"s_lig": 200.0},
            "score": 4.0,
        },
        base_state={"s_lig": 250.0},
        severity_band="severe",
        seed_shear_util=1.25,
    )
    checks["module_runtime_rank_tuple_contract"] = (
        isinstance(sample_rank, tuple)
        and len(sample_rank) == 9
        and sample_rank[:5] == (0, 0, 0, 0, 1)
        and sample_rank[6] == -4.0
        and sample_rank[7] == 1
        and sample_rank[8] == "Spacing"
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
    json_path = ARTIFACTS / f"inputs_page_shear_recommendation_rank_key_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_shear_recommendation_rank_key_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Shear Recommendation Rank Key Extraction",
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
