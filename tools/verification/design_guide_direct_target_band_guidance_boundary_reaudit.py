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
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

TARGET = "_direct_target_band_guidance_item"


CLASSIFICATION_TOKENS = {
    "page_shell_input_collection": [
        "_guidance_state_snapshot(",
        "_resolved_efficiency_target_band(",
        "_resolve_geometry_width_context(",
        "_float_from_state(",
        "_design_optimisation_goal(",
    ],
    "family_owned_or_controller_owned_early_dispatch": [
        "_active_fail_near_current_repair_item(",
        "BENDING_FAIL_GOVERNS",
        "SHEAR_FAIL_GOVERNS",
        "COMBINED_BENDING_SHEAR_FAIL",
        "family_route_owner",
    ],
    "page_session_diag_cache": [
        "st.session_state",
        "_direct_target_band_diag_trace(",
        "get_rerun_pure_cache(",
        "set_rerun_pure_cache(",
        "_direct_target_band_diag_active",
        "_direct_target_band_proof_active",
    ],
    "candidate_generation_search": [
        "width_values",
        "depth_values",
        "_evaluate_updates(",
        "seen_updates",
        "candidates.append(",
        "max_evals",
    ],
    "legacy_page_evaluation_shim_dependency": [
        "_evaluate_auto_design_candidate(",
        "evaluate_candidate_full(",
    ],
    "candidate_evaluation_service_call": [
        "_evaluate_direct_target_band_candidate_with_service(",
        "_evaluate_design_candidate_with_updates(",
    ],
    "ranking_selection_policy": [
        "_direct_candidate_final_cleanup_key(",
        "_select_direct_target_item(",
        "selected = min(",
        "target_selection_pool",
        "fallback_pool",
    ],
    "blocker_fallback_policy": [
        "_bounded_proof_blocker_item(",
        "_active_failure_no_target_blocker_item(",
        "active_failure_no_safe_candidates_blocker",
        "budget_exhausted",
    ],
    "publication_item_projection": [
        "_guidance_item_from_resolved_candidate(",
        "item[\"action_payload\"]",
        "item[\"resolved_candidate\"]",
        "candidate_search_evidence",
        "primary_action",
    ],
    "cta_apply_plumbing": [
        "action_type",
        "apply_resolved_candidate",
        "_design_guide_button_contract(",
        "_resolve_recommendation_updates(",
    ],
    "debug_proof_construction": [
        "debug_sink",
        "candidate_search_evidence",
        "direct_target_band_search_used",
        "direct_target_band_search_candidate_count",
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
            return node.lineno, int(node.end_lineno or node.lineno), "\n".join(lines[node.lineno - 1 : int(node.end_lineno or node.lineno)])
    return 0, 0, ""


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _classifications(segment: str, start_line: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, tokens in CLASSIFICATION_TOKENS.items():
        matches = []
        for token in tokens:
            count = segment.count(token)
            if count:
                matches.append(
                    {
                        "token": token,
                        "count": count,
                        "lines": _line_numbers(segment, start_line, token)[:20],
                    }
                )
        result[name] = {"present": bool(matches), "matches": matches}
    return result


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, segment = _function_source(inputs_source, TARGET)
    classifications = _classifications(segment, start)
    source_checks = {
        "target_found": bool(segment),
        "candidate_evaluation_module_import_clean": all(
            token not in candidate_source
            for token in (
                "inputs_page",
                "streamlit",
                "st.session_state",
                "rendered_html",
                "apply_routing",
                "ui_state",
            )
        ),
        "legacy_page_evaluator_calls_in_target": segment.count("_evaluate_auto_design_candidate("),
        "legacy_full_evaluator_calls_in_target": segment.count("evaluate_candidate_full("),
        "candidate_evaluation_service_calls_in_target": segment.count(
            "_evaluate_direct_target_band_candidate_with_service("
        ),
        "legacy_candidate_evaluation_seam_extracted": (
            segment.count("_evaluate_auto_design_candidate(") == 0
            and segment.count("evaluate_candidate_full(") == 0
            and segment.count("_evaluate_direct_target_band_candidate_with_service(") >= 3
        ),
        "target_still_has_page_session_diag_cache": classifications["page_session_diag_cache"]["present"],
        "target_still_has_large_route_orchestration": all(
            classifications[name]["present"]
            for name in (
                "candidate_generation_search",
                "ranking_selection_policy",
                "blocker_fallback_policy",
                "publication_item_projection",
            )
        ),
    }
    legacy_page_eval_lines = []
    for token in ("_evaluate_auto_design_candidate(", "evaluate_candidate_full("):
        legacy_page_eval_lines.extend(_line_numbers(segment, start, token))
    legacy_page_eval_lines = sorted(set(legacy_page_eval_lines))
    service_eval_lines = _line_numbers(segment, start, "_evaluate_direct_target_band_candidate_with_service(")
    first_safe_slice = {
        "name": "direct_target_family_repair_bridge_route_policy_audit",
        "target_helper": TARGET,
        "target_nested_surface": "active-failure family repair bridge route policy and page adapter boundary",
        "ready": bool(source_checks["legacy_candidate_evaluation_seam_extracted"]),
        "why": (
            "The previous narrow candidate-evaluation seam has already moved behind "
            "`design_brain.candidate_evaluation`: no `_evaluate_auto_design_candidate(...)` or "
            "`evaluate_candidate_full(...)` calls remain in `_direct_target_band_guidance_item(...)`, and the "
            "target now calls `_evaluate_direct_target_band_candidate_with_service(...)`. The next remaining "
            "boundary is the active-failure family repair bridge route: controller-owned route policy exists, but "
            "the page still invokes family-item bridge helpers, records CTA/debug side effects, and manages "
            "session diagnostics around the route."
        ),
        "move": (
            "Audit the direct-target active-failure family repair bridge and classify what is controller-owned "
            "route policy, what is page-shell callback/recording, and what can move behind a controller adapter."
        ),
        "do_not_move": [
            "direct route orchestration",
            "family early-dispatch branches",
            "Streamlit/session diagnostics and proof-active guard",
            "bounded proof cache",
            "candidate generation loops",
            "ranking/selection",
            "fallback/blocker construction",
            "item/action payload projection",
            "CTA/apply routing",
        ],
    }
    return {
        "schema": "design_guide_direct_target_band_guidance_boundary_reaudit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "classifications": classifications,
        "summary": {
            "legacy_page_evaluation_shim_lines": legacy_page_eval_lines,
            "legacy_page_evaluation_shim_count": len(legacy_page_eval_lines),
            "candidate_evaluation_service_lines": service_eval_lines,
            "candidate_evaluation_service_count": len(service_eval_lines),
            "candidate_evaluation_service_already_present": classifications["candidate_evaluation_service_call"]["present"],
            "page_session_diag_cache_present": classifications["page_session_diag_cache"]["present"],
            "route_orchestration_present": classifications["candidate_generation_search"]["present"],
            "ranking_selection_policy_present": classifications["ranking_selection_policy"]["present"],
            "blocker_fallback_policy_present": classifications["blocker_fallback_policy"]["present"],
            "publication_item_projection_present": classifications["publication_item_projection"]["present"],
        },
        "decision": "CANDIDATE_EVALUATION_SEAM_EXTRACTED_NEXT_ROUTE_POLICY_AUDIT"
        if first_safe_slice["ready"]
        else "NOT_READY_WITH_EXACT_REMAINING_SURFACE",
        "first_safe_implementation_slice": first_safe_slice,
        "required_verifier": {
            "name": "design_guide_direct_target_family_repair_bridge_route_policy_audit.py",
            "must_prove": [
                "active-failure route policy is controller-owned",
                "page-owned family bridge calls are classified as shell callback/adapter execution or remaining Design Brain logic",
                "CTA/debug recording side effects remain page-owned and do not decide publication truth",
                "no candidate evaluation shim calls return to `_direct_target_band_guidance_item(...)`",
                "next extraction or deletion slice is exact and bounded",
            ],
        },
        "stop_conditions": [
            "candidate output differs",
            "candidate metadata changes",
            "action payload or CTA semantics change",
            "visible wording changes",
            "session/proof-active behavior changes",
            "ranking or route orchestration moves",
            "any composed lock fails",
        ],
        "source_checks": source_checks,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((capture.get("target") or {}).get("line_count")),
        "candidate_evaluation_module_import_clean": bool((capture.get("source_checks") or {}).get("candidate_evaluation_module_import_clean")),
        "legacy_candidate_evaluation_seam_extracted": bool((capture.get("source_checks") or {}).get("legacy_candidate_evaluation_seam_extracted")),
        "large_route_not_broadly_movable": bool((capture.get("source_checks") or {}).get("target_still_has_large_route_orchestration")),
        "page_session_diag_cache_explicitly_classified": bool((capture.get("source_checks") or {}).get("target_still_has_page_session_diag_cache")),
        "first_safe_slice_ready": bool((capture.get("first_safe_implementation_slice") or {}).get("ready")),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    summary = dict(capture.get("summary") or {})
    first_slice = dict(capture.get("first_safe_implementation_slice") or {})
    lines = [
        "# Direct Target-Band Guidance Boundary Re-Audit",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Decision: `{capture.get('decision')}`",
        f"- Target lines: `{(capture.get('target') or {}).get('line_start')}`-`{(capture.get('target') or {}).get('line_end')}`",
        f"- Target line count: `{(capture.get('target') or {}).get('line_count')}`",
        f"- Legacy page evaluation shim lines: `{summary.get('legacy_page_evaluation_shim_lines')}`",
        f"- Candidate-evaluation service lines: `{summary.get('candidate_evaluation_service_lines')}`",
        "",
        "## Current Ownership",
        "- This helper is not shell-only.",
        "- The old page-local candidate evaluation seam has already been extracted.",
        "- It still owns route orchestration, diagnostics/cache, ranking, blocker/fallback construction, and item projection.",
        "- The next narrow surface is the active-failure family repair bridge route policy boundary.",
        "",
        "## First Safe Slice",
        f"- Name: `{first_slice.get('name')}`",
        f"- Nested surface: `{first_slice.get('target_nested_surface')}`",
        f"- Ready: `{first_slice.get('ready')}`",
        f"- Move: {first_slice.get('move')}",
        "",
        "## Do Not Move Yet",
    ]
    for item in list(first_slice.get("do_not_move") or []):
        lines.append(f"- {item}")
    lines.extend(["", "## Checks"])
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    lines.extend(["", "## Required Verifier"])
    required = dict(capture.get("required_verifier") or {})
    lines.append(f"- `{required.get('name')}`")
    for item in list(required.get("must_prove") or []):
        lines.append(f"- {item}")
    lines.extend(["", "## Stop Conditions"])
    for item in list(capture.get("stop_conditions") or []):
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = PROGRESS_PATH.read_text(encoding="utf-8").rstrip() if PROGRESS_PATH.exists() else ""
    lines = [existing, ""] if existing else []
    lines.extend(
        [
            f"## {payload.get('created_at')} - Direct target-band guidance boundary re-audit",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Decision: `{(payload.get('capture') or {}).get('decision')}`",
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
        "schema": "design_guide_direct_target_band_guidance_boundary_reaudit.v1",
        "created_at": created_at,
        "status": "PASS" if passed else "FAIL",
        "capture": capture,
        "checks": checks,
    }
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_band_guidance_boundary_reaudit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_band_guidance_boundary_reaudit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_direct_target_band_guidance_boundary_reaudit {payload['status']}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if not passed:
        print("failing_checks=" + json.dumps([name for name, ok in checks.items() if not ok]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
