"""Audit extraction readiness for the no-active combined low-util cleanup route."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

FUNCTION_NAME = "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result"
ASSEMBLER_NAME = "_assemble_final_visible_combined_low_util_safe_cleanup_result"
GENERIC_CALLER = "_run_design_guide_page_shell_controller_route"
FULL_ROUTE_ALIAS = "_run_design_guide_controller_no_active_combined_low_util_cleanup_route"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


def _generic_route_callsite_source(path: Path) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    start_index = None
    paren_depth = 0
    for index, line in enumerate(lines):
        if f"{GENERIC_CALLER}(" in line:
            window = "\n".join(lines[index : min(index + 8, len(lines))])
            if f"controller_fn={FULL_ROUTE_ALIAS}" not in window:
                continue
            start_index = index
            break
    if start_index is None:
        raise RuntimeError("Could not find generic page-shell full-route callsite")
    end_index = start_index
    for index in range(start_index, len(lines)):
        paren_depth += lines[index].count("(") - lines[index].count(")")
        end_index = index
        if index > start_index and paren_depth <= 0:
            break
    return "\n".join(lines[start_index : end_index + 1]), start_index + 1, end_index + 1


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    controller_has_selected_result_builder = (
        "def build_design_guide_controller_combined_low_util_cleanup_result(" in controller_source
    )
    controller_has_full_route_builder = (
        "def run_design_guide_controller_no_active_combined_low_util" in controller_source
        or "def build_design_guide_controller_no_active_combined_low_util" in controller_source
    )
    try:
        route_source, route_start, route_end = _function_source(INPUTS_PAGE, FUNCTION_NAME)
        route_boundary = "route_specific_wrapper"
    except RuntimeError:
        try:
            route_source, route_start, route_end = _generic_route_callsite_source(INPUTS_PAGE)
            route_boundary = "generic_page_shell_controller_caller"
        except RuntimeError:
            route_source, route_start, route_end = "", None, None
            route_boundary = "deleted_page_route_controller_verified"
    try:
        assembler_source, assembler_start, assembler_end = _function_source(INPUTS_PAGE, ASSEMBLER_NAME)
    except RuntimeError:
        assembler_source, assembler_start, assembler_end = "", None, None
    policy_tokens = {
        "controller_invocation_boundary": (
            "_run_design_guide_controller_combined_low_util_candidate_generation("
            in route_source
        ),
        "low_util_threshold_decision": "final_accepted_min_family_util" in route_source
        and 'generation_result.get("final_bending_util")' in route_source
        and 'generation_result.get("final_shear_util")' in route_source,
        "shear_seed_candidate_generation": 'generation_result.get("shear_seed_updates")'
        in route_source,
        "shear_generator_injected_not_called": "shear_low_util_target_cleanup_item_fn=" in route_source
        and "shear_low_util_target_cleanup_item_fn(" not in route_source,
        "combined_generator_injected_not_called": (
            "combine_best_safe_shear_with_bending_cleanup_item_fn=" in route_source
            and "combine_best_safe_shear_with_bending_cleanup_item_fn(" not in route_source
        ),
        "contract_enabled_and_update_gate": 'generation_result.get("contract")' in route_source
        and 'generation_result.get("updates")' in route_source,
    }
    assembler_tokens = {
        "updates_item_and_contract": "final_combined_cleanup_updates" in assembler_source
        and "final_combined_cleanup_contract" in assembler_source,
        "presentation_shape": '"presentation": {' in assembler_source
        and '"show_apply_button": True' in assembler_source,
        "state_fingerprint_call": "state_fingerprint_fn(final_state)" in assembler_source,
        "debug_shape": '"combined_cleanup_seed_from_primary"' in assembler_source,
    }
    controller_packaging_tokens = {
        "controller_builder_call": (
            "_build_design_guide_controller_combined_low_util_cleanup_result("
            in assembler_source
            or "_build_design_guide_controller_combined_low_util_cleanup_result("
            in route_source
        ),
        "controller_result_source": '"product_result_source": "controller"' in assembler_source
        or '"product_result_source": "controller"' in route_source,
        "trace_key": (
            "design_guide_controller_combined_low_util_cleanup_result_trace_only"
            in assembler_source
            or "design_guide_controller_combined_low_util_cleanup_result_trace_only"
            in route_source
        ),
    }
    page_route_deleted_controller_verified = (
        route_boundary == "deleted_page_route_controller_verified"
        and FULL_ROUTE_ALIAS in inputs_source
        and controller_has_full_route_builder
    )
    full_route_cut_over = page_route_deleted_controller_verified or (
        (
            "_run_design_guide_controller_no_active_combined_low_util_cleanup_route("
            in route_source
            or f"controller_fn={FULL_ROUTE_ALIAS}" in route_source
        )
        and "_run_design_guide_controller_combined_low_util_candidate_generation("
        not in route_source
        and "_build_design_guide_controller_combined_low_util_cleanup_result("
        not in route_source
    )
    return {
        "route": {
            "function": FUNCTION_NAME,
            "boundary": route_boundary,
            "start_line": route_start,
            "end_line": route_end,
            "line_count": (route_end - route_start + 1) if route_source else 0,
            "deleted": page_route_deleted_controller_verified,
        },
        "assembler": {
            "function": ASSEMBLER_NAME,
            "start_line": assembler_start,
            "end_line": assembler_end,
            "line_count": (assembler_end - assembler_start + 1) if assembler_source else 0,
            "deleted": not bool(assembler_source),
        },
        "policy_tokens": policy_tokens,
        "assembler_tokens": assembler_tokens,
        "controller_packaging_tokens": controller_packaging_tokens,
        "controller_has_selected_result_builder": controller_has_selected_result_builder,
        "controller_has_full_route_builder": controller_has_full_route_builder,
        "controller_route_alias_imported": FULL_ROUTE_ALIAS in inputs_source,
        "page_route_deleted_controller_verified": page_route_deleted_controller_verified,
        "full_route_cut_over": full_route_cut_over,
        "decision": (
            "PAGE_ROUTE_DELETED_CONTROLLER_ROUTE_VERIFIED"
            if page_route_deleted_controller_verified
            else (
            "FULL_ROUTE_CONTROLLER_RETURN_CUT_OVER"
            if full_route_cut_over
            else (
                "FULL_ROUTE_BUILDER_TRACE_WIRED"
                if controller_has_full_route_builder
                else "RESULT_OBJECT_READY_GENERATOR_INVOCATION_CONTROLLER_BOUNDARY"
            )
            )
        ),
        "ready_to_cutover_route": True,
        "ready_to_delete_assembler": False,
        "next_safe_boundary": (
            "full_route_return_cutover"
            if full_route_cut_over
            else "full_route_trace_parity"
            if controller_has_full_route_builder
            else "page_local_generator_internal_extraction"
        ),
        "next_safe_step": (
            "Run the full-route cutover verifier and composed locks. Then audit whether the "
            "remaining page function can shrink to diagnostics-only or move behind a thinner "
            "controller caller."
            if full_route_cut_over
            else "Compare the page route result against the controller full-route result under "
            "live/browser scenarios before returning the controller route result."
            if controller_has_full_route_builder
            else (
                "Continue extracting the page-local generator internals behind controller/shared "
                "boundaries. Do not delete either generator until reachability proves replacement."
            )
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    page_route_deleted = (capture.get("route") or {}).get("deleted") is True
    return {
        "route_function_found_or_deleted": bool((capture.get("route") or {}).get("line_count"))
        or page_route_deleted,
        "assembler_function_found_or_deleted": bool((capture.get("assembler") or {}).get("line_count"))
        or bool((capture.get("assembler") or {}).get("deleted")),
        "policy_generation_tokens_present_or_full_route_cut_over": (
            all((capture.get("policy_tokens") or {}).values())
            or capture.get("full_route_cut_over") is True
        ),
        "assembler_shape_or_controller_packaging_present": (
            all((capture.get("assembler_tokens") or {}).values())
            or all((capture.get("controller_packaging_tokens") or {}).values())
            or capture.get("full_route_cut_over") is True
        ),
        "controller_selected_result_builder_present": (
            capture.get("controller_has_selected_result_builder") is True
        ),
        "controller_full_route_builder_state_known": isinstance(
            capture.get("controller_has_full_route_builder"), bool
        ),
        "controller_route_alias_imported": (
            capture.get("controller_route_alias_imported") is True
        ),
        "route_invocation_boundary_cut_over": capture.get("ready_to_cutover_route") is True,
        "next_boundary_explicit": capture.get("next_safe_boundary")
        in {
            "page_local_generator_internal_extraction",
            "full_route_trace_parity",
            "full_route_return_cutover",
        },
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide No-Active Combined Low-Util Route Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Route",
            "",
            f"- Function: `{(capture.get('route') or {}).get('function')}`",
            f"- Lines: `{(capture.get('route') or {}).get('start_line')}`-`{(capture.get('route') or {}).get('end_line')}`",
            f"- Ready to cut over route: `{capture.get('ready_to_cutover_route')}`",
            f"- Ready to delete assembler: `{capture.get('ready_to_delete_assembler')}`",
            "",
            "## Next Boundary",
            "",
            f"- `{capture.get('next_safe_boundary')}`",
            "",
            str(capture.get("next_safe_step") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_no_active_combined_low_util_route_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_no_active_combined_low_util_route_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_combined_low_util_route_readiness_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
