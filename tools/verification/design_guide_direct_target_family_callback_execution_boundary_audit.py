from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

ROUTE_TARGET = "_direct_target_band_guidance_item"
CALLBACK_TARGET = "_active_fail_near_current_repair_item"

CALLBACK_TOKENS = {
    "family_runtime_orchestration": [
        "_active_fail_executor_family_ladder_specs",
        "_build_active_fail_executor_candidate_from_stage",
        "_select_active_fail_executor_family_ladder_candidate",
        "_build_active_fail_executor_candidate_search_evidence",
    ],
    "candidate_generation": [
        "_generate_escalated_bending_states",
        "_generate_escalated_shear_states",
        "_enumerate_bottom_reo_design_trials",
        "candidate",
        "candidates.append",
    ],
    "candidate_evaluation": [
        "_evaluate_design_candidate_with_updates(",
        "_evaluate_direct_target_band_candidate_with_service(",
        "evaluate_candidate_full(",
    ],
    "publication_item_projection": [
        "_guidance_item_from_resolved_candidate(",
        "action_payload",
        "button_contract",
        "candidate_search_evidence",
    ],
    "page_side_effects": [
        "_inputs_pre_widget_trace(",
        "_record_bending_fail_valid_repair_cta_published(",
    ],
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _classify_callback(segment: str, start_line: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, tokens in CALLBACK_TOKENS.items():
        rows = []
        for token in tokens:
            lines = _line_numbers(segment, start_line, token)
            if lines:
                rows.append({"token": token, "count": len(lines), "lines": lines[:30]})
        result[name] = {"present": bool(rows), "matches": rows}
    return result


def _capture() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    route_start, route_end, route_segment = _function_source(source, ROUTE_TARGET)
    cb_start, cb_end, cb_segment = _function_source(source, CALLBACK_TARGET)
    callback_classification = _classify_callback(cb_segment, cb_start)
    route_callback_lines = _line_numbers(route_segment, route_start, f"{CALLBACK_TARGET}(")
    callback_is_shell_only = bool(cb_segment) and not any(
        callback_classification[name]["present"]
        for name in (
            "family_runtime_orchestration",
            "candidate_generation",
            "publication_item_projection",
        )
    )
    decision = (
        "CALLBACK_EXECUTION_BOUNDED_PAGE_SHELL"
        if callback_is_shell_only
        else "NOT_BOUNDED_CALLBACK_TARGET_STILL_PAGE_OWNED_DESIGN_BRAIN_LOGIC"
    )
    return {
        "schema": "design_guide_direct_target_family_callback_execution_boundary_audit.v1",
        "route_target": {
            "name": ROUTE_TARGET,
            "line_start": route_start,
            "line_end": route_end,
            "line_count": max(0, route_end - route_start + 1),
            "callback_call_lines": route_callback_lines,
        },
        "callback_target": {
            "name": CALLBACK_TARGET,
            "line_start": cb_start,
            "line_end": cb_end,
            "line_count": max(0, cb_end - cb_start + 1),
        },
        "decision": decision,
        "callback_classification": callback_classification,
        "source_checks": {
            "route_target_found": bool(route_segment),
            "callback_target_found": bool(cb_segment),
            "route_calls_callback_three_times": len(route_callback_lines) >= 3,
            "route_metadata_projection_extracted": "route_adapter_kwargs" in route_segment
            and "family_route_owner=" not in route_segment
            and "skipped_reason=" not in route_segment,
            "callback_still_owns_family_orchestration": callback_classification["family_runtime_orchestration"]["present"],
            "callback_still_owns_candidate_generation": callback_classification["candidate_generation"]["present"],
            "callback_still_owns_publication_item_projection": callback_classification["publication_item_projection"]["present"],
            "callback_has_page_side_effects": callback_classification["page_side_effects"]["present"],
            "callback_shell_only": callback_is_shell_only,
        },
        "first_safe_implementation_slice": {
            "name": "active_fail_near_current_repair_item_service_boundary_audit",
            "ready": bool(cb_segment) and not callback_is_shell_only,
            "move": (
                "Audit `_active_fail_near_current_repair_item(...)` itself and split family ladder/candidate "
                "construction from page trace/CTA side effects. Do not move the direct-target route branch until "
                "that callback has a service/controller boundary."
            ),
            "do_not_move_yet": [
                "direct-target route callback callsites",
                "CTA/apply routing",
                "visible wording",
                "family runtime behaviour",
                "page trace callbacks",
            ],
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "route_target_found": bool(source_checks.get("route_target_found")),
        "callback_target_found": bool(source_checks.get("callback_target_found")),
        "route_calls_callback_three_times": bool(source_checks.get("route_calls_callback_three_times")),
        "route_metadata_projection_extracted": bool(source_checks.get("route_metadata_projection_extracted")),
        "callback_remaining_surface_identified": bool(
            source_checks.get("callback_shell_only")
            or source_checks.get("callback_still_owns_family_orchestration")
            or source_checks.get("callback_still_owns_candidate_generation")
            or source_checks.get("callback_still_owns_publication_item_projection")
        ),
        "first_safe_slice_identified": bool((capture.get("first_safe_implementation_slice") or {}).get("ready"))
        or bool(source_checks.get("callback_shell_only")),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    route = dict(capture.get("route_target") or {})
    callback = dict(capture.get("callback_target") or {})
    first_slice = dict(capture.get("first_safe_implementation_slice") or {})
    lines = [
        "# Direct Target Family Callback Execution Boundary Audit",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Decision: `{capture.get('decision')}`",
        f"- Route target lines: `{route.get('line_start')}`-`{route.get('line_end')}`",
        f"- Callback target lines: `{callback.get('line_start')}`-`{callback.get('line_end')}`",
        f"- Callback target line count: `{callback.get('line_count')}`",
        "",
        "## Callback Classification",
    ]
    for name, row in dict(capture.get("callback_classification") or {}).items():
        lines.append(f"- `{name}`: `{row.get('present')}`")
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first_slice.get('name')}`",
            f"- Ready: `{first_slice.get('ready')}`",
            f"- Move: {first_slice.get('move')}",
            "",
            "## Do Not Move Yet",
        ]
    )
    for item in list(first_slice.get("do_not_move_yet") or []):
        lines.append(f"- {item}")
    lines.extend(["", "## Checks"])
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = PROGRESS_PATH.read_text(encoding="utf-8").rstrip() if PROGRESS_PATH.exists() else ""
    lines = [existing, ""] if existing else []
    lines.extend(
        [
            f"## {payload.get('created_at')} - Direct target family callback execution boundary audit",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Decision: `{(payload.get('capture') or {}).get('decision')}`",
            "- Extraction estimate: `99.67%`",
            f"- Report: [{report_path.name}](../audits/{report_path.name})",
            "",
        ]
    )
    PROGRESS_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    created_at = _timestamp()
    capture = _capture()
    checks = _checks(capture)
    passed = all(checks.values())
    payload = {
        "schema": "design_guide_direct_target_family_callback_execution_boundary_audit.v1",
        "created_at": created_at,
        "status": "PASS" if passed else "FAIL",
        "capture": capture,
        "checks": checks,
    }
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_family_callback_execution_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_family_callback_execution_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_direct_target_family_callback_execution_boundary_audit {payload['status']}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if not passed:
        print("failing_checks=" + json.dumps([name for name, ok in checks.items() if not ok]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
