"""Verify app-bridge design-action widget sync delegates to the widget module."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "widgets" / "design_action_sync.py"
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

    bridge_node = _function_node(bridge_source, "_sync_design_action_widget_to_shared")
    module_node = _function_node(module_source, "sync_design_action_widget_to_shared")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 32,
        "bridge_delegates_to_widget_module": "_sync_design_action_widget_to_shared_module(" in bridge_body,
        "bridge_does_not_keep_old_trace_body": "design_action_widget_sync_entry" not in bridge_body
        and "design_action_widget_sync_exit" not in bridge_body,
        "module_contains_sync_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 120,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_keeps_sync_contract_surface": all(
            token in module_source
            for token in (
                "design_action_widget_sync_entry",
                "design_action_widget_sync_exit",
                "cached_results",
                "_cached_compute_results",
                "_last_compute_fp",
                "pending_recommendation",
                "pending_recommendation_applied_id",
                "_solver_result",
                "_one_click_run_feedback",
                "auto_design_status",
                "auto_design_steps",
                "inputs_dirty",
                "_inputs_dirty",
                "run_design_clicked",
                "N_star",
                "Mu_star_manual",
                "load_Mstar_proxy",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge

    original = bridge._sync_design_action_widget_to_shared_module
    call_record: dict = {}

    def _fake_module(widget_key, shared_key, proxy_key=None, **kwargs):
        call_record.update(
            {
                "widget_key": widget_key,
                "shared_key": shared_key,
                "proxy_key": proxy_key,
                "trigger_rerun": kwargs.get("trigger_rerun"),
                "st_module": kwargs.get("st_module") is bridge.st,
                "debug": kwargs.get("debug_design_guidance_probe")
                is bridge.DEBUG_DESIGN_GUIDANCE_PROBE,
                "trace": kwargs.get("append_design_guide_trace_fn")
                is bridge._append_design_guide_trace,
                "get_param": kwargs.get("get_param_fn") is bridge.get_param,
                "mark_user_edit": kwargs.get("mark_user_edit_fn") is bridge.mark_user_edit,
                "set_shared": kwargs.get("set_shared_fn") is bridge.set_shared,
                "invalidate_summary": kwargs.get("invalidate_inputs_summary_packs_fn")
                is bridge._invalidate_inputs_summary_packs,
                "queue_refresh": kwargs.get("queue_inputs_refresh_fn") is bridge._queue_inputs_refresh,
                "invalidate_design_guide": kwargs.get("invalidate_design_guide_caches_fn")
                is bridge._invalidate_design_guide_caches,
                "mark_dirty": kwargs.get("mark_design_guide_dirty_fn") is bridge._mark_design_guide_dirty,
                "persist_beam": kwargs.get("persist_active_beam_from_shared_fn")
                is bridge.persist_active_beam_from_shared,
                "persist_snapshot": kwargs.get("persist_state_snapshot_fn")
                is bridge.persist_state_snapshot,
                "debug_actions": kwargs.get("debug_resolved_guidance_actions_fn")
                is bridge._debug_resolved_guidance_actions,
                "snapshot": kwargs.get("shared_state_snapshot_fn") is bridge._shared_state_snapshot,
                "auto_design_invalidation": kwargs.get("sync_auto_design_invalidation_fn")
                is bridge._sync_auto_design_invalidation,
                "debug_consistency": kwargs.get("debug_check_design_action_consistency_fn")
                is bridge._debug_check_design_action_consistency,
                "time_ms_callable": callable(kwargs.get("time_ms_fn")),
            }
        )

    try:
        bridge._sync_design_action_widget_to_shared_module = _fake_module
        returned = bridge._sync_design_action_widget_to_shared(
            "inputs_load_Vstar_proxy",
            "uls_Vstar",
            "load_Vstar_proxy",
            trigger_rerun=True,
        )
    finally:
        bridge._sync_design_action_widget_to_shared_module = original

    checks["bridge_runtime_delegates_with_dependencies"] = (
        returned is None
        and call_record.get("widget_key") == "inputs_load_Vstar_proxy"
        and call_record.get("shared_key") == "uls_Vstar"
        and call_record.get("proxy_key") == "load_Vstar_proxy"
        and call_record.get("trigger_rerun") is True
        and all(
            call_record.get(key) is True
            for key in (
                "st_module",
                "debug",
                "trace",
                "get_param",
                "mark_user_edit",
                "set_shared",
                "invalidate_summary",
                "queue_refresh",
                "invalidate_design_guide",
                "mark_dirty",
                "persist_beam",
                "persist_snapshot",
                "debug_actions",
                "snapshot",
                "auto_design_invalidation",
                "debug_consistency",
                "time_ms_callable",
            )
        )
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
    json_path = ARTIFACTS / f"inputs_page_app_bridge_design_action_widget_sync_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_app_bridge_design_action_widget_sync_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Design Action Widget Sync Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Widget module function lines: {result['module_function_lines']}",
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
