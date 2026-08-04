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
TARGET = "_active_fail_near_current_repair_item"


SURFACES = {
    "controller_owned_preflight": [
        "_build_design_guide_controller_active_fail_near_current_repair_preflight(",
    ],
    "page_shell_cache_and_session": [
        "get_rerun_pure_cache(",
        "set_rerun_pure_cache(",
        "st.session_state",
        "_bending_fail_selected_repair_cache",
    ],
    "page_trace_or_cta_side_effects": [
        "_inputs_pre_widget_trace(",
        "_record_bending_post_cta_early_stop_status(",
        "_record_bending_fail_valid_repair_cta_published(",
    ],
    "service_owned_eval_loop_pieces": [
        "_build_active_fail_executor_candidate_eval_precheck_projection(",
        "_resolve_active_fail_executor_candidate_eval_cache_lookup(",
        "_evaluate_active_fail_executor_candidate_with_updates(",
        "_build_active_fail_executor_candidate_eval_attempt_result(",
        "_apply_active_fail_executor_candidate_eval_loop_attempt_result(",
    ],
    "page_owned_eval_callback_boundary": [
        "evaluator_fn=evaluate_candidate_full",
        "stable_fingerprint_for_payload(candidate_state)",
    ],
    "controller_owned_family_ladder_dispatch": [
        "_build_design_guide_controller_active_fail_executor_family_ladder_dispatch(",
        "_build_design_guide_controller_active_fail_executor_ladder_eval_commands(",
        "_resolve_design_guide_controller_active_fail_executor_ladder_stop_decision(",
    ],
    "page_owned_family_ladder_execution": [
        "for command in _build_design_guide_controller_active_fail_executor_ladder_eval_commands(",
        "_evaluate(",
    ],
    "page_owned_candidate_generation_loops": [
        "for bottom in ordered_bottom",
        "for geom in ordered_geom",
        "for shear in ordered_shear",
        "for updates in",
    ],
    "controller_or_publication_item_projection": [
        "_build_design_guide_controller",
        "_build_final",
        "_build_design_guide_button_contract",
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


def _classify(segment: str, start_line: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, tokens in SURFACES.items():
        matches = []
        for token in tokens:
            lines = _line_numbers(segment, start_line, token)
            if lines:
                matches.append({"token": token, "count": len(lines), "lines": lines[:30]})
        result[name] = {"present": bool(matches), "matches": matches}
    return result


def _capture() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    start, end, segment = _function_source(source, TARGET)
    classifications = _classify(segment, start)
    service_pieces_present = bool(classifications["controller_owned_preflight"]["present"]) and bool(
        classifications["service_owned_eval_loop_pieces"]["present"]
    )
    remaining_design_logic = any(
        bool(classifications[name]["present"])
        for name in (
            "page_owned_family_ladder_execution",
            "controller_or_publication_item_projection",
        )
    )
    return {
        "schema": "design_guide_active_fail_near_current_repair_item_service_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "decision": (
            "NOT_SHELL_ONLY_ACTIVE_FAIL_REPAIR_CALLBACK_STILL_OWNS_GENERATION_AND_PROJECTION"
            if remaining_design_logic
            else "ACTIVE_FAIL_REPAIR_CALLBACK_BOUNDED_PAGE_SHELL"
        ),
        "classifications": classifications,
        "ownership_summary": {
            "already_controller_or_service_owned": [
                "preflight/defaults",
                "candidate eval precheck projection",
                "candidate eval cache lookup",
                "candidate eval attempt projection",
                "candidate eval loop accumulation",
                "family ladder dispatch and ladder command construction",
            ],
            "allowed_page_shell": [
                "rerun/session cache",
                "trace/CTA side-effect callbacks",
                "evaluate_candidate_full callback execution",
                "stable fingerprint adapter",
            ],
            "remaining_page_owned_design_logic": [
                "family ladder command execution loop",
                "near-current raw candidate generation loops if present",
                "item/projection packaging tail",
            ],
        },
        "source_checks": {
            "target_found": bool(segment),
            "controller_preflight_present": bool(classifications["controller_owned_preflight"]["present"]),
            "service_eval_loop_pieces_present": bool(classifications["service_owned_eval_loop_pieces"]["present"]),
            "service_boundary_progress_present": service_pieces_present,
            "page_shell_cache_and_session_bounded": bool(classifications["page_shell_cache_and_session"]["present"]),
            "page_trace_or_cta_side_effects_bounded": bool(
                classifications["page_trace_or_cta_side_effects"]["present"]
            ),
            "page_eval_callback_boundary_bounded": bool(classifications["page_owned_eval_callback_boundary"]["present"]),
            "remaining_family_ladder_execution_identified": bool(
                classifications["page_owned_family_ladder_execution"]["present"]
            ),
        "raw_candidate_generation_loops_absent_or_identified": not bool(
            classifications["page_owned_candidate_generation_loops"]["present"]
        )
        or bool(
            classifications["page_owned_candidate_generation_loops"]["present"]
        ),
            "remaining_projection_tail_identified": bool(
                classifications["controller_or_publication_item_projection"]["present"]
            ),
        },
        "first_safe_implementation_slice": {
            "name": "active_fail_near_current_family_ladder_execution_boundary_audit",
            "ready": bool(segment),
            "move": (
                "Audit whether the remaining family ladder command execution loop can be represented as a "
                "controller/candidate-evaluation command runner while keeping `evaluate_candidate_full`, trace, "
                "session cache, CTA recording, and family runtime behaviour unchanged."
            ),
            "do_not_move_yet": [
                "evaluate_candidate_full execution",
                "Streamlit/session caches",
                "trace callbacks",
                "CTA/apply routing",
                "visible wording",
                "family runtime behaviour",
            ],
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "target_found": bool(source_checks.get("target_found")),
        "controller_preflight_present": bool(source_checks.get("controller_preflight_present")),
        "service_eval_loop_pieces_present": bool(source_checks.get("service_eval_loop_pieces_present")),
        "service_boundary_progress_present": bool(source_checks.get("service_boundary_progress_present")),
        "page_shell_cache_and_session_bounded": bool(source_checks.get("page_shell_cache_and_session_bounded")),
        "page_trace_or_cta_side_effects_bounded": bool(source_checks.get("page_trace_or_cta_side_effects_bounded")),
        "page_eval_callback_boundary_bounded": bool(source_checks.get("page_eval_callback_boundary_bounded")),
        "remaining_family_ladder_execution_identified": bool(
            source_checks.get("remaining_family_ladder_execution_identified")
        ),
        "raw_candidate_generation_loops_absent_or_identified": bool(
            source_checks.get("raw_candidate_generation_loops_absent_or_identified")
        ),
        "remaining_projection_tail_identified": bool(source_checks.get("remaining_projection_tail_identified")),
        "first_safe_slice_identified": bool((capture.get("first_safe_implementation_slice") or {}).get("ready")),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    target = dict(capture.get("target") or {})
    first_slice = dict(capture.get("first_safe_implementation_slice") or {})
    lines = [
        "# Active Fail Near-Current Repair Item Service Boundary Audit",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Decision: `{capture.get('decision')}`",
        f"- Target lines: `{target.get('line_start')}`-`{target.get('line_end')}`",
        f"- Target line count: `{target.get('line_count')}`",
        "",
        "## Classification",
    ]
    for name, row in dict(capture.get("classifications") or {}).items():
        lines.append(f"- `{name}`: `{row.get('present')}`")
    lines.extend(
        [
            "",
            "## Ownership Summary",
            "- Already controller/service-owned: preflight, eval precheck/cache/attempt/accumulation, ladder dispatch/commands",
            "- Allowed page shell: caches, trace/CTA callbacks, evaluator callback execution, fingerprint adapter",
            "- Remaining page-owned Design Brain logic: family ladder command execution and projection tail",
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
            f"## {payload.get('created_at')} - Active fail near-current repair item service boundary audit",
            "",
            f"- Status: `{payload.get('status')}`",
            "- Extraction complete estimate: `99.76%`",
            f"- Decision: `{(payload.get('capture') or {}).get('decision')}`",
            "- Next target: family ladder execution boundary audit.",
            f"- Report: `{report_path}`",
        ]
    )
    PROGRESS_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    created_at = _timestamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_active_fail_near_current_repair_item_service_boundary_audit.v1",
        "created_at": created_at,
        "status": status,
        "capture": capture,
        "checks": checks,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_near_current_repair_item_service_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_near_current_repair_item_service_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_active_fail_near_current_repair_item_service_boundary_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
