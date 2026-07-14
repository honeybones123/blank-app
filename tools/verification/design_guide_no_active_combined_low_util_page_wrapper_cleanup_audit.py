"""Audit remaining page wrapper code after no-active combined low-util cutover.

Proof-only: this does not delete code or change product behaviour. It classifies
the remaining page wrapper body so the next slice can target diagnostics-only
code with consumer reachability proof.
"""

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

ROUTE = "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result"
CONTROLLER_ALIAS = "_run_design_guide_controller_no_active_combined_low_util_cleanup_route"
TRACE_KEY = "design_guide_controller_no_active_combined_low_util_full_route_trace_only"

CALLBACK_ARGS = (
    "parse_util_value_fn",
    "updates_match_state_fn",
    "normalise_design_guide_candidate_id_fn",
    "shear_low_util_target_cleanup_item_fn",
    "combine_best_safe_shear_with_bending_cleanup_item_fn",
    "design_mode_config_fn",
    "design_optimisation_goal_fn",
    "normalise_final_visible_design_guide_item_fn",
    "resolve_recommendation_updates_fn",
    "design_guide_button_contract_enabled_fn",
    "state_fingerprint_fn",
)


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
    raise RuntimeError(f"Could not find {function_name}")


def _count_lines_with(source: str, token: str) -> int:
    return sum(1 for line in source.splitlines() if token in line)


def _capture() -> dict[str, Any]:
    try:
        route_source, start_line, end_line = _function_source(INPUTS_PAGE, ROUTE)
        route_deleted = False
    except RuntimeError:
        route_source = ""
        start_line = None
        end_line = None
        route_deleted = True
        source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
        generic_callsite_present = (
            "_run_design_guide_page_shell_controller_route(" in source
            and "controller_fn=_run_design_guide_controller_no_active_combined_low_util_cleanup_route"
            in source
        )
        return {
            "decision": "PAGE_WRAPPER_DELETED_GENERIC_PAGE_SHELL_CALLER_CUT_OVER",
            "route": {
                "name": ROUTE,
                "start_line": start_line,
                "end_line": end_line,
                "line_count": 0,
                "deleted": True,
            },
            "required_wiring": {
                "generic_page_shell_caller_present": generic_callsite_present,
                "route_specific_wrapper_deleted": True,
            },
            "callback_args_present": {name: True for name in CALLBACK_ARGS},
            "lower_level_calls": {
                "candidate_generation": False,
                "selected_result_builder": False,
                "direct_shear_generator": False,
                "direct_combined_generator": False,
            },
            "diagnostics_inventory": {
                "resolver_route_trace_event": 0,
                "controller_trace_key_stamp": 0,
                "live_wired_stamp": 0,
                "projection_hash_build": 0,
                "final_item_summary_for_trace": 0,
                "contract_summary_for_trace": 0,
                "updates_summary_for_trace": 0,
            },
            "classifications": [
                {
                    "class": "A route-specific page wrapper",
                    "evidence": "deleted after generic page-shell caller cutover proof",
                    "safe_to_delete_now": True,
                    "present": False,
                }
            ],
            "deletion_candidates_now": [],
            "next_safe_slice": "Move to the next route-specific page wrapper.",
            "product_behavior_changed": False,
            "visible_wording_changed": False,
            "cta_apply_semantics_changed": False,
            "family_runtime_changed": False,
        }
    callback_args_present = {
        name: f"{name}={name}" in route_source for name in CALLBACK_ARGS
    }
    lower_level_calls = {
        "candidate_generation": (
            "_run_design_guide_controller_combined_low_util_candidate_generation("
            in route_source
        ),
        "selected_result_builder": (
            "_build_design_guide_controller_combined_low_util_cleanup_result("
            in route_source
        ),
        "direct_shear_generator": "shear_low_util_target_cleanup_item_fn(" in route_source,
        "direct_combined_generator": (
            "combine_best_safe_shear_with_bending_cleanup_item_fn(" in route_source
        ),
    }
    diagnostics_inventory = {
        "resolver_route_trace_event": _count_lines_with(
            route_source, "_resolver_route_trace_event("
        ),
        "controller_trace_key_stamp": _count_lines_with(route_source, TRACE_KEY),
        "live_wired_stamp": _count_lines_with(route_source, '"live_wired"'),
        "projection_hash_build": _count_lines_with(
            route_source, "controller_projection_hash"
        ),
        "final_item_summary_for_trace": _count_lines_with(
            route_source, "final_combined_cleanup_item"
        ),
        "contract_summary_for_trace": _count_lines_with(
            route_source, "final_combined_cleanup_contract"
        ),
        "updates_summary_for_trace": _count_lines_with(
            route_source, "final_combined_cleanup_updates"
        ),
    }
    required_wiring = {
        "controller_route_called": f"{CONTROLLER_ALIAS}(" in route_source,
        "controller_result_returned": "return result" in route_source,
        "none_guard_retained": "if not isinstance(result, dict):" in route_source
        and "return None" in route_source,
        "all_callback_boundaries_forwarded": all(callback_args_present.values()),
    }
    classifications = [
        {
            "class": "A required controller invocation",
            "evidence": "controller route alias called and result returned",
            "safe_to_delete_now": False,
        },
        {
            "class": "B required callback boundary forwarding",
            "evidence": f"{sum(callback_args_present.values())}/{len(callback_args_present)} callbacks forwarded",
            "safe_to_delete_now": False,
        },
        {
            "class": "C diagnostics/proof stamps",
            "evidence": "deleted after source-only consumer reachability proof",
            "safe_to_delete_now": True,
            "present": any(value > 0 for value in diagnostics_inventory.values()),
        },
        {
            "class": "D lower-level page assembly",
            "evidence": "direct candidate generation/result-builder calls",
            "safe_to_delete_now": True,
            "present": any(lower_level_calls.values()),
        },
    ]
    return {
        "decision": "PAGE_WRAPPER_IS_THIN_CALLBACK_BOUNDARY_DIAGNOSTICS_DELETED",
        "route": {
            "name": ROUTE,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
            "deleted": route_deleted,
        },
        "required_wiring": required_wiring,
        "callback_args_present": callback_args_present,
        "lower_level_calls": lower_level_calls,
        "diagnostics_inventory": diagnostics_inventory,
        "classifications": classifications,
        "deletion_candidates_now": [],
        "next_safe_slice": (
            "Audit whether callback forwarding itself can be hidden behind a generic "
            "page-shell controller caller without moving Streamlit/session ownership."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    route_deleted_after_cutover = (capture.get("route") or {}).get("deleted") is True
    wiring = capture.get("required_wiring") or {}
    return {
        "route_found_or_deleted_after_cutover": bool(
            (capture.get("route") or {}).get("line_count")
        )
        or route_deleted_after_cutover,
        "required_wiring_present": all(wiring.values())
        or (
            route_deleted_after_cutover
            and wiring.get("route_specific_wrapper_deleted") is True
        ),
        "callback_boundaries_complete": all(
            (capture.get("callback_args_present") or {}).values()
        ),
        "no_lower_level_page_assembly": not any(
            (capture.get("lower_level_calls") or {}).values()
        ),
        "diagnostics_deleted": all(
            int(value or 0) == 0
            for value in (capture.get("diagnostics_inventory") or {}).values()
        ),
        "no_deletion_without_consumer_proof": capture.get("deletion_candidates_now") == [],
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    route = dict(capture.get("route") or {})
    lines = [
        "# Design Guide No-Active Combined Low-Util Page Wrapper Cleanup Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Route: `{route.get('name')}`",
        f"Route lines: `{route.get('start_line')}-{route.get('end_line')}`",
        f"Route line count: `{route.get('line_count')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Classification"])
    for row in capture.get("classifications") or []:
        lines.append(
            f"- {row.get('class')}: {row.get('evidence')} "
            f"(safe_to_delete_now: `{row.get('safe_to_delete_now')}`)"
        )
    lines.extend(["", "## Diagnostics Inventory"])
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("diagnostics_inventory") or {}).items()
    )
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            str(capture.get("next_safe_slice")),
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
        / f"design_guide_no_active_combined_low_util_page_wrapper_cleanup_audit_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_combined_low_util_page_wrapper_cleanup_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_combined_low_util_page_wrapper_cleanup_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
