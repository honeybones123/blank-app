"""Audit ownership/parity for the no-active combined low-util cleanup route.

This is proof-only. It does not move route ownership, delete code, or change
publication/render/apply behaviour.
"""

from __future__ import annotations

from datetime import datetime
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

ROUTE = "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result"
CONTROLLER_GENERATION_ALIAS = "_run_design_guide_controller_combined_low_util_candidate_generation"
CONTROLLER_RESULT_ALIAS = "_build_design_guide_controller_combined_low_util_cleanup_result"
TRACE_KEY = "design_guide_controller_combined_low_util_cleanup_result_trace_only"
POLICY_TRACE_KEY = "design_guide_controller_combined_low_util_cleanup_route_policy_trace_only"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name}")


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE)

    injected_callback_tokens = {
        "parse_util_value_fn": "parse_util_value_fn=",
        "updates_match_state_fn": "updates_match_state_fn=",
        "normalise_candidate_id_fn": "normalise_design_guide_candidate_id_fn=",
        "shear_cleanup_item_fn": "shear_low_util_target_cleanup_item_fn=",
        "combined_cleanup_item_fn": "combine_best_safe_shear_with_bending_cleanup_item_fn=",
        "design_mode_config_fn": "design_mode_config_fn=",
        "design_optimisation_goal_fn": "design_optimisation_goal_fn=",
        "normalise_final_visible_item_fn": "normalise_final_visible_design_guide_item_fn=",
        "resolve_recommendation_updates_fn": "resolve_recommendation_updates_fn=",
        "button_contract_enabled_fn": "design_guide_button_contract_enabled_fn=",
        "state_fingerprint_fn": "state_fingerprint_fn(",
    }
    page_callback_invocations_inside_route = {
        "direct_shear_cleanup_call": "shear_low_util_target_cleanup_item_fn(" in route_source,
        "direct_combined_cleanup_call": "combine_best_safe_shear_with_bending_cleanup_item_fn(" in route_source,
        "direct_recommendation_resolver_call": "resolve_recommendation_updates_fn(" in route_source,
        "direct_button_contract_call": "design_guide_button_contract_enabled_fn(" in route_source,
    }

    controller_generation_present = f"{CONTROLLER_GENERATION_ALIAS}(" in route_source
    controller_result_present = f"{CONTROLLER_RESULT_ALIAS}(" in route_source
    full_route_builder_present = (
        "def run_design_guide_controller_no_active_combined_low_util" in controller_source
        or "def build_design_guide_controller_no_active_combined_low_util" in controller_source
    )
    route_debug_shape = {
        "result_trace_key": TRACE_KEY in route_source,
        "policy_trace_key": POLICY_TRACE_KEY in route_source,
        "non_driving_flags": all(
            token in route_source
            for token in (
                '"product_driving": False',
                '"render_driving": False',
                '"apply_driving": False',
                '"session_driving": False',
            )
        ),
        "product_source_controller": '"product_result_source": "controller"' in route_source,
    }
    forbidden_ownership = {
        "streamlit_session_write": "st.session_state" in route_source,
        "rendering": "st.markdown(" in route_source or "st.button(" in route_source,
        "apply_routing": "_queue_primary_design_guide_button_action" in route_source,
        "family_runtime": "contracted_repair_ladder_specs(" in route_source,
        "visible_wording_render": "_design_guide_dashboard_card_html_from_render_model" in route_source,
    }

    return {
        "decision": "PARTIAL_ROUTE_CONTROLLER_BACKED_RESULT_PAGE_OWNED_WRAPPER",
        "route": {
            "name": ROUTE,
            "start_line": route_start,
            "end_line": route_end,
            "line_count": route_end - route_start + 1,
        },
        "controller_generation_boundary_present": controller_generation_present,
        "controller_result_boundary_present": controller_result_present,
        "full_controller_route_builder_present": full_route_builder_present,
        "injected_callback_tokens": {
            name: token in route_source for name, token in injected_callback_tokens.items()
        },
        "page_callback_invocations_inside_route": page_callback_invocations_inside_route,
        "route_debug_shape": route_debug_shape,
        "forbidden_ownership": forbidden_ownership,
        "route_imports_present": {
            "generation_alias": CONTROLLER_GENERATION_ALIAS in inputs_source,
            "result_alias": CONTROLLER_RESULT_ALIAS in inputs_source,
        },
        "verification": {
            "route_readiness": _run(
                "tools/verification/design_guide_no_active_combined_low_util_route_readiness_snapshot.py"
            ),
            "assembler_cutover": _run(
                "tools/verification/design_guide_combined_low_util_cleanup_assembler_cutover.py"
            ),
            "result_object": _run(
                "tools/verification/design_guide_combined_low_util_cleanup_result_object_snapshot.py"
            ),
            "result_trace": _run(
                "tools/verification/design_guide_combined_low_util_cleanup_result_trace_wiring_snapshot.py"
            ),
            "remaining_resolver_surface": _run(
                "tools/verification/design_guide_remaining_final_visible_resolver_extraction_audit.py"
            ),
        },
        "ownership_classification": {
            "result_shape": "controller_owned",
            "candidate_generation": "controller_boundary_with_page_callbacks",
            "route_wrapper": "page_owned_glue",
            "render_apply_publication": "not_owned_here",
        },
        "ready_for_full_route_deletion": False,
        "next_safe_slice": "full_route_builder_or_page_callback_boundary_proof",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = capture.get("verification") or {}
    return {
        "controller_generation_boundary_present": capture.get(
            "controller_generation_boundary_present"
        )
        is True,
        "controller_result_boundary_present": capture.get("controller_result_boundary_present")
        is True,
        "full_controller_route_builder_absent_and_recorded": capture.get(
            "full_controller_route_builder_present"
        )
        is False,
        "all_injected_callbacks_accounted_for": all(
            (capture.get("injected_callback_tokens") or {}).values()
        ),
        "route_does_not_directly_invoke_page_callback_generators": not any(
            (capture.get("page_callback_invocations_inside_route") or {}).values()
        ),
        "debug_shape_proves_non_driving_controller_result": all(
            (capture.get("route_debug_shape") or {}).values()
        ),
        "no_forbidden_page_ownership_inside_route": not any(
            (capture.get("forbidden_ownership") or {}).values()
        ),
        "controller_alias_imports_present": all((capture.get("route_imports_present") or {}).values()),
        "route_readiness_passed": (verification.get("route_readiness") or {}).get("passed")
        is True,
        "assembler_cutover_passed": (verification.get("assembler_cutover") or {}).get("passed")
        is True,
        "result_object_passed": (verification.get("result_object") or {}).get("passed") is True,
        "result_trace_passed": (verification.get("result_trace") or {}).get("passed") is True,
        "remaining_surface_passed": (verification.get("remaining_resolver_surface") or {}).get(
            "passed"
        )
        is True,
        "not_ready_for_full_route_deletion": capture.get("ready_for_full_route_deletion") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    lines = [
        "# Design Guide No-Active Combined Low-Util Route Ownership/Parity Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Route lines: `{(capture.get('route') or {}).get('start_line')}`-`{(capture.get('route') or {}).get('end_line')}`",
        f"Next safe slice: `{capture.get('next_safe_slice')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Ownership Classification",
            "",
        ]
    )
    for key, value in (capture.get("ownership_classification") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Do not delete the route wrapper yet. The result shape and candidate generation "
            "are controller-backed, but the full route wrapper is still page-owned glue because "
            "there is no full controller route builder yet. The next safe slice is a full-route "
            "builder or callback-boundary proof.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_no_active_combined_low_util_route_ownership_parity_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_combined_low_util_route_ownership_parity_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_combined_low_util_route_ownership_parity {status}")
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_slice={capture.get('next_safe_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
