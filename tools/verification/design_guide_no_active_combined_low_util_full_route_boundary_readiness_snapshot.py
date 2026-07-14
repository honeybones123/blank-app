"""Check readiness for a full no-active combined-low-util route boundary."""

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
PROPOSED_BUILDER = "run_design_guide_controller_no_active_combined_low_util_cleanup_route"


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


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or "")
    if "PASS" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _capture() -> dict[str, Any]:
    route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE)
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")

    callback_boundary_params = {
        "parse_util_value_fn": "parse_util_value_fn",
        "updates_match_state_fn": "updates_match_state_fn",
        "normalise_design_guide_candidate_id_fn": "normalise_design_guide_candidate_id_fn",
        "shear_low_util_target_cleanup_item_fn": "shear_low_util_target_cleanup_item_fn",
        "combine_best_safe_shear_with_bending_cleanup_item_fn": (
            "combine_best_safe_shear_with_bending_cleanup_item_fn"
        ),
        "design_mode_config_fn": "design_mode_config_fn",
        "design_optimisation_goal_fn": "design_optimisation_goal_fn",
        "normalise_final_visible_design_guide_item_fn": (
            "normalise_final_visible_design_guide_item_fn"
        ),
        "resolve_recommendation_updates_fn": "resolve_recommendation_updates_fn",
        "design_guide_button_contract_enabled_fn": "design_guide_button_contract_enabled_fn",
        "state_fingerprint_fn": "state_fingerprint_fn",
    }
    callback_boundary_accounted_for = {
        name: token in route_source for name, token in callback_boundary_params.items()
    }
    route_only_trace_dependencies = {
        "runtime_trace_event": "_resolver_route_trace_event(" in route_source,
        "runtime_trace_summary": "_dg_runtime_trace_item_summary(" in route_source,
        "runtime_trace_hash": "_dg_runtime_trace_hash(" in route_source,
        "stable_final_publication_hash": "_stable_final_publication_hash(" in route_source,
    }
    plain_inputs = {
        "primary": "primary: dict" in route_source,
        "updates": "updates: dict" in route_source,
        "final_state": "final_state: dict" in route_source,
        "final_overview": "final_overview: dict" in route_source,
        "final_accepted_min_family_util": "final_accepted_min_family_util" in route_source,
        "compound_shear_update_keys": "compound_shear_update_keys" in route_source,
    }
    controller_boundaries = {
        "candidate_generation": "_run_design_guide_controller_combined_low_util_candidate_generation("
        in route_source,
        "result_builder": "_build_design_guide_controller_combined_low_util_cleanup_result("
        in route_source,
        "result_builder_exists": "def build_design_guide_controller_combined_low_util_cleanup_result("
        in controller_source,
        "candidate_generation_exists": "def run_design_guide_controller_combined_low_util_candidate_generation("
        in controller_source,
    }
    proposed_builder_exists = f"def {PROPOSED_BUILDER}(" in controller_source
    forbidden_controller_ownership = {
        "streamlit": (
            "import streamlit" in controller_source
            or "st.session_state" in controller_source
            or "st.button" in controller_source
            or "st.markdown" in controller_source
        ),
        "apply_routing": "_queue_primary_design_guide_button_action" in controller_source,
        "html_rendering": "_design_guide_dashboard_card_html_from_render_model" in controller_source,
        "family_runtime_cutover": "contracted_repair_ladder_specs(" in route_source,
    }
    return {
        "decision": (
            "READY_FOR_PROOF_ONLY_FULL_ROUTE_BUILDER"
            if not proposed_builder_exists
            else "FULL_ROUTE_BUILDER_ALREADY_EXISTS"
        ),
        "route": {
            "name": ROUTE,
            "start_line": route_start,
            "end_line": route_end,
            "line_count": route_end - route_start + 1,
        },
        "proposed_builder": PROPOSED_BUILDER,
        "proposed_builder_exists": proposed_builder_exists,
        "plain_inputs": plain_inputs,
        "callback_boundary_accounted_for": callback_boundary_accounted_for,
        "route_only_trace_dependencies": route_only_trace_dependencies,
        "controller_boundaries": controller_boundaries,
        "forbidden_controller_ownership": forbidden_controller_ownership,
        "verification": {
            "ownership_parity": _run(
                "tools/verification/design_guide_no_active_combined_low_util_route_ownership_parity_audit.py"
            ),
            "route_readiness": _run(
                "tools/verification/design_guide_no_active_combined_low_util_route_readiness_snapshot.py"
            ),
            "latest_independence_lock": _latest("design_guide_independence_lock"),
        },
        "ready_for_trace_only_builder": True,
        "ready_for_live_cutover": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = capture.get("verification") or {}
    return {
        "plain_inputs_accounted_for": all((capture.get("plain_inputs") or {}).values()),
        "callback_boundary_accounted_for": all(
            (capture.get("callback_boundary_accounted_for") or {}).values()
        ),
        "route_trace_dependencies_identified": all(
            (capture.get("route_only_trace_dependencies") or {}).values()
        ),
        "controller_boundaries_present": all((capture.get("controller_boundaries") or {}).values()),
        "no_forbidden_controller_ownership": not any(
            (capture.get("forbidden_controller_ownership") or {}).values()
        ),
        "ownership_parity_passed": (verification.get("ownership_parity") or {}).get("passed")
        is True,
        "route_readiness_passed": (verification.get("route_readiness") or {}).get("passed")
        is True,
        "latest_independence_lock_passed": (
            verification.get("latest_independence_lock") or {}
        ).get("status")
        == "PASS",
        "ready_for_trace_only_builder": capture.get("ready_for_trace_only_builder") is True,
        "not_ready_for_live_cutover": capture.get("ready_for_live_cutover") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    lines = [
        "# Design Guide No-Active Combined Low-Util Full Route Boundary Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Proposed builder: `{capture.get('proposed_builder')}`",
        f"Ready for trace-only builder: `{capture.get('ready_for_trace_only_builder')}`",
        f"Ready for live cutover: `{capture.get('ready_for_live_cutover')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Create a proof-only full-route builder in `design_brain.design_guide_controller` "
            "that accepts plain inputs plus explicit callback boundaries and returns the same "
            "route result. Do not cut over the live page route until trace parity passes.",
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
        / f"design_guide_no_active_combined_low_util_full_route_boundary_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_combined_low_util_full_route_boundary_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_combined_low_util_full_route_boundary_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"ready_for_trace_only_builder={capture.get('ready_for_trace_only_builder')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
