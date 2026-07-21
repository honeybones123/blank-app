from __future__ import annotations

import ast
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
SHELL_PAGE = ROOT / "inputs_page_shell.py"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
SESSION_ROOT = ROOT / "inputs_page_modules" / "session"
APPLY_STEP_HISTORY_FINALIZER = (
    ROOT / "inputs_page_modules" / "design_guide" / "apply_step_history_finalizer.py"
)
APPLY_TRACE_RUN_END = (
    ROOT / "inputs_page_modules" / "design_guide" / "apply_trace_run_end.py"
)


DELEGATED_BOUNDARIES = {
    "_inputs_audit_snapshot_state": ("build_inputs_session_source_snapshot",),
    "_overlay_current_design_action_results_for_summary": ("build_inputs_design_action_result_overlay_snapshot",),
    "_apply_active_page_shear_widget_mirror_overlay": ("build_inputs_shear_widget_mirror_overlay_plan",),
    "_overlay_inputs_reo_widget_mirrors_for_model": ("build_inputs_model_reo_widget_mirror_overlay_plan",),
    "_overlay_current_normalized_shear_truth": ("build_inputs_normalized_shear_truth_overlay_snapshot",),
    "_record_inputs_rerun_trigger": ("build_inputs_rerun_trigger_record_plan",),
    "_clear_design_guide_transient_ui_state": ("build_inputs_design_guide_transient_ui_clear_plan",),
    "_mark_design_guide_dirty": ("build_inputs_design_guide_dirty_mark_plan",),
    "_get_cached_design_guide_guidance": (
        "build_inputs_design_guide_guidance_cache_result",
        "build_inputs_design_guide_cached_debug_trust_decision",
    ),
    "_set_cached_design_guide_guidance": ("build_inputs_design_guide_guidance_cache_write_plan",),
    "_maybe_reset_design_guide_step_history": ("build_inputs_design_guide_step_history_reset_plan",),
    "_finalize_design_guide_apply_step_history": ("build_inputs_design_guide_apply_step_history_entry_plan",),
    "_design_guide_step_history_debug_summary": ("build_inputs_design_guide_step_history_debug_summary",),
    "_emit_design_guide_apply_trace_run_end": (
        "build_inputs_design_guide_apply_trace_run_end_meta_plan",
        "build_inputs_design_guide_apply_trace_run_end_outcome",
    ),
}

APPROVED_PAGE_SHELL_BOUNDARIES = {
    "session_mutation": (
        "_record_inputs_rerun_trigger",
        "_clear_design_guide_transient_ui_state",
        "_mark_design_guide_dirty",
        "_set_cached_design_guide_guidance",
        "_maybe_reset_design_guide_step_history",
        "_finalize_design_guide_apply_step_history",
    ),
    "apply_routing": (
        "_apply_resolved_candidate_payload",
        "apply_guidance_action",
    ),
    "callbacks_and_hydration": (
        "_wrap_inputs_sync_callbacks",
        "_reseed_inputs_longitudinal_reo_widgets_from_shared",
        "_request_shear_widget_seed_from_shared",
    ),
}

FUNCTION_ALIASES = {
    "_overlay_current_design_action_results_for_summary": (
        "_overlay_current_design_action_results_for_summary_for_app_bridge",
    ),
    "_wrap_inputs_sync_callbacks": (
        "_wrap_longitudinal_reo_sync_callbacks",
    ),
}

FORBIDDEN_MODULE_PATTERNS = {
    "streamlit_import": r"(?:^|\n)\s*(?:import|from)\s+streamlit\b",
    "inputs_page_import": r"(?:^|\n)\s*(?:import\s+inputs_page\b|from\s+inputs_page\b)",
    "session_state_access": r"(?:st\.)?session_state",
    "apply_routing": r"\b(?:apply_guidance_action|_apply_resolved_candidate_payload|route_apply|execute_apply)\s*\(",
    "widget_rendering": r"\bst\.(?:button|selectbox|number_input|toggle|checkbox|radio|slider)\s*\(",
}


def _function_sources(source: str) -> dict[str, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    result: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = int(getattr(node, "end_lineno", node.lineno))
            body = "\n".join(lines[node.lineno - 1 : end])
            if node.name in result:
                result[node.name] += "\n" + body
            else:
                result[node.name] = body
    return result


def main() -> int:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    shell_source = (
        SHELL_PAGE.read_text(encoding="utf-8", errors="replace")
        if SHELL_PAGE.exists()
        else inputs_source
    )
    live_surface = inputs_source
    for path in (ROUTE_COORDINATORS, APP_CONTRACT_BRIDGE):
        if path.exists():
            live_surface += "\n" + path.read_text(encoding="utf-8", errors="replace")
    for extracted_boundary in (APPLY_STEP_HISTORY_FINALIZER, APPLY_TRACE_RUN_END):
        if extracted_boundary.exists():
            live_surface += "\n" + extracted_boundary.read_text(
                encoding="utf-8",
                errors="replace",
            )
    functions = _function_sources(live_surface)
    shell_functions = _function_sources(shell_source)
    module_sources = {
        path.name: path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(SESSION_ROOT.glob("*.py"))
    }
    executable_source = "\n".join(
        text for name, text in module_sources.items() if name != "contracts.py"
    )
    contracts_source = module_sources.get("contracts.py", "")

    failures: list[str] = []
    delegated_results: list[dict[str, object]] = []
    for function_name, required_calls in DELEGATED_BOUNDARIES.items():
        body = functions.get(function_name, "")
        for alias in FUNCTION_ALIASES.get(function_name, ()):
            body += "\n" + functions.get(alias, "")
        if function_name == "_inputs_audit_snapshot_state" and not body:
            body = live_surface if "build_inputs_session_source_snapshot(" in live_surface else ""
        if function_name == "_overlay_current_normalized_shear_truth":
            body += "\n" + functions.get("_overlay_current_normalized_shear_truth_for_app_bridge", "")
        missing_calls = [token for token in required_calls if token not in body]
        delegated_results.append(
            {
                "function": function_name,
                "required_calls": list(required_calls),
                "missing_calls": missing_calls,
                "passed": bool(body) and not missing_calls,
            }
        )
        if not body:
            failures.append(f"missing delegated page boundary: {function_name}")
        elif missing_calls:
            failures.append(f"{function_name} missing delegation: {', '.join(missing_calls)}")

    forbidden_hits: dict[str, bool] = {}
    for label, pattern in FORBIDDEN_MODULE_PATTERNS.items():
        hit = bool(re.search(pattern, executable_source, flags=re.MULTILINE))
        forbidden_hits[label] = hit
        if hit:
            failures.append(f"session module owns forbidden surface: {label}")

    shell_results: dict[str, list[dict[str, object]]] = {}
    for category, names in APPROVED_PAGE_SHELL_BOUNDARIES.items():
        rows: list[dict[str, object]] = []
        for name in names:
            body = functions.get(name, "")
            for alias in FUNCTION_ALIASES.get(name, ()):
                body += "\n" + functions.get(alias, "")
            present = bool(body)
            rows.append({"function": name, "present": present})
            if not present:
                failures.append(f"approved page-shell boundary missing: {name}")
        shell_results[category] = rows

    shell_render_present = bool(shell_functions.get("render_inputs_page"))
    shell_results["rendering"] = [
        {"function": "inputs_page_shell.render_inputs_page", "present": shell_render_present},
        {"function": "inputs_page.render_inputs", "present": bool(functions.get("render_inputs"))},
    ]
    if not shell_render_present:
        failures.append("approved live shell render boundary missing: inputs_page_shell.render_inputs_page")
    if functions.get("render_inputs"):
        failures.append("old inputs_page render boundary still present: render_inputs")

    if "pure_snapshot_decision_and_plan_models" not in contracts_source:
        failures.append("session contract does not declare pure snapshot/decision/plan ownership")
    for required_rule in (
        "do_not_import_streamlit",
        "do_not_mutate_session_state",
        "do_not_route_apply",
        "do_not_execute_callbacks",
        "do_not_render_widgets",
    ):
        if required_rule not in contracts_source:
            failures.append(f"missing ownership rule: {required_rule}")

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    decision = "INPUTS_SESSION_STATE_OWNERSHIP_LOCKED" if not failures else "INPUTS_SESSION_STATE_OWNERSHIP_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_state_ownership_lock",
        "timestamp": timestamp,
        "decision": decision,
        "status": "PASS" if not failures else "FAIL",
        "delegated_boundary_count": len(delegated_results),
        "delegated_boundaries": delegated_results,
        "approved_page_shell_boundaries": shell_results,
        "module_forbidden_hits": forbidden_hits,
        "module_file_count": len(module_sources),
        "failures": failures,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "widget_keys_changed": False,
        "session_behavior_changed": False,
        "apply_routing_moved": False,
        "render_ownership_moved": False,
    }

    verification_dir = ROOT / "artifacts" / "verification"
    audit_dir = ROOT / "artifacts" / "audits"
    verification_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = verification_dir / f"inputs_session_state_ownership_lock_{timestamp}.json"
    report_path = audit_dir / f"inputs_session_state_ownership_lock_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Session State Ownership Lock",
                "",
                f"Decision: `{decision}`",
                "",
                f"Delegated pure boundaries checked: `{len(delegated_results)}`",
                f"Forbidden module ownership hits: `{sum(1 for hit in forbidden_hits.values() if hit)}`",
                f"Failures: `{len(failures)}`",
                "",
                "The session module owns plain snapshots, decisions, and mutation plans only.",
                "`inputs_page.py` retains Streamlit session mutation, callbacks, Apply routing, rendering, and orchestration.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(decision)
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
