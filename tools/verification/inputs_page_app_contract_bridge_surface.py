from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

APP = ROOT / "app.py"
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

LOCAL_BRIDGE_HELPERS = {
    "DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY",
    "DESIGN_GUIDE_PUBLICATION_FP_KEY",
    "EFFICIENCY_TARGET_UTIL_MAX",
    "_accepted_green_exact_blocker_is_valid",
    "_clear_design_guide_transient_ui_state",
    "_collect_design_overview",
    "_complete_exact_blocker_map_from_attempts",
    "_compute_design_guidance_items",
    "_design_mode_config",
    "_design_guide_blocker_attempts_table",
    "_exact_cleanup_blocker_for_outside_target_action",
    "_get_design_guide_fp",
    "_inputs_hydration_trace_log",
    "_local_cleanup_post_apply_acceptance_matches",
    "_parse_util_value",
    "_post_click_low_bending_resolution_item",
    "_publishable_safe_cleanup_updates_from_evidence",
    "_pop_inputs_widget_keys_for_shared_updates",
    "_resolve_design_actions_from_state",
    "_resolved_inputs_summary_state",
    "_shear_demands_negligible",
    "_shear_low_util_active_links_exact_blocker",
    "_shear_reinforcement_is_active",
    "identify_materially_overprovided_non_governing_families",
    "run_inputs_layer4_pre_hydrate_shear_normalisation",
}

EXPECTED_REMAINING_FALLBACK_HELPERS = set()


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_names(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _top_level_assignment_names(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _app_bridge_attrs(source: str) -> set[str]:
    tree = ast.parse(source)
    direct_attrs = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "inputs_page_bridge"
    }
    string_getattr_attrs = {
        node.args[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "inputs_page_bridge"
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    }
    return direct_attrs | string_getattr_attrs


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    app_source = _source(APP)
    bridge_source = _source(BRIDGE)
    bridge_symbols = _function_names(bridge_source) | _top_level_assignment_names(bridge_source)
    app_attrs = _app_bridge_attrs(app_source)
    remaining_fallback_attrs = app_attrs - LOCAL_BRIDGE_HELPERS
    checks = {
        "local_bridge_helpers_defined": LOCAL_BRIDGE_HELPERS.issubset(bridge_symbols),
        "local_bridge_helpers_used_by_app": LOCAL_BRIDGE_HELPERS.issubset(app_attrs),
        "remaining_fallback_surface_matches_expected": remaining_fallback_attrs
        == EXPECTED_REMAINING_FALLBACK_HELPERS,
        "remaining_fallback_surface_count_0": len(remaining_fallback_attrs) == 0,
        "bridge_has_no_module_getattr_fallback": "def __getattr__" not in bridge_source,
        "bridge_does_not_explicitly_record_old_page_dependency": "import inputs_page as _legacy_inputs_page"
        not in bridge_source,
    }
    failures = [name for name, value in checks.items() if not value]
    payload = {
        "audit": "inputs_page_app_contract_bridge_surface",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "local_bridge_helpers": sorted(LOCAL_BRIDGE_HELPERS),
        "remaining_fallback_helpers": sorted(remaining_fallback_attrs),
        "remaining_fallback_count": len(remaining_fallback_attrs),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_contract_bridge_surface_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_contract_bridge_surface_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Contract Bridge Surface",
                "",
                f"Status: `{payload['status']}`",
                f"Remaining fallback count: `{payload['remaining_fallback_count']}`",
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
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
