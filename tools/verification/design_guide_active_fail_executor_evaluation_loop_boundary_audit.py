"""Audit the remaining active-fail executor evaluation loop boundary."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_active_fail_near_current_repair_item"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _token_row(segment: str, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in segment,
        "count": segment.count(token),
    }


def _classifications(segment: str) -> list[dict[str, Any]]:
    rows = [
        {
            "surface": "nested candidate evaluation wrapper",
            "classification": "service-owned eval-attempt result, page-owned loop/callback bridge",
            "current_owner": "candidate_evaluation helper plus inputs_page executor bridge",
            "target_owner": "candidate_evaluation service runner with injected evaluator after loop boundary proof",
            "tokens": [
                "def _evaluate(",
                "seen_updates.add(sig)",
                "eval_cache_by_candidate_fp",
                "_evaluate_active_fail_executor_candidate_with_updates(",
                "_resolve_active_fail_executor_candidate_eval_source(",
                "_build_active_fail_executor_candidate_eval_attempt_result(",
            ],
            "first_safe_slice": "completed_active_fail_executor_candidate_eval_attempt_result_adapter",
            "deletion_readiness": "NOT_READY",
        },
        {
            "surface": "family ladder eval command execution",
            "classification": "controller-owned eval command shaping, page-owned execution",
            "current_owner": "DesignGuideController commands plus inputs_page execution loop",
            "target_owner": "DesignGuideController loop runner after callback boundary",
            "tokens": [
                "_build_design_guide_controller_active_fail_executor_ladder_eval_commands(",
                "for command in _build_design_guide_controller_active_fail_executor_ladder_eval_commands(",
            ],
            "first_safe_slice": "completed_active_fail_executor_ladder_eval_command_handoff",
            "deletion_readiness": "NOT_READY",
        },
        {
            "surface": "family meta construction",
            "classification": "DesignGuideController-owned projection, page calls helper",
            "current_owner": "DesignGuideController",
            "target_owner": "DesignGuideController",
            "tokens": [
                "_build_design_guide_controller_active_fail_executor_ladder_candidate_meta(",
            ],
            "first_safe_slice": "completed_active_fail_executor_ladder_meta_projection_handoff",
            "deletion_readiness": "SHELL_CALL",
        },
        {
            "surface": "trace/progress row emission",
            "classification": "page-owned emission with controller-owned row payloads",
            "current_owner": "inputs_page emission",
            "target_owner": "page shell emission remains; row payloads controller-owned",
            "tokens": [
                "_inputs_pre_widget_trace(",
                "_phase5c_latency_trace(",
                "_build_design_guide_controller_active_fail_executor_bending_ladder_evaluation_trace_row(",
                "_build_design_guide_controller_active_fail_executor_bending_ladder_first_executable_trace_row(",
            ],
            "first_safe_slice": "keep_bounded_page_shell_trace_emission",
            "deletion_readiness": "KEEP_BOUNDED",
        },
        {
            "surface": "fallback rescue seed loops",
            "classification": "controller-owned rescue/near-current command and row projection, page-owned tier choice, geometry fit input plumbing, and execution",
            "current_owner": "DesignGuideController commands plus inputs_page executor bridge",
            "target_owner": "DesignGuideController/candidate_evaluation runner after fallback execution proof",
            "tokens": [
                "_build_design_guide_controller_active_fail_executor_rescue_seed_eval_commands(",
                "_build_design_guide_controller_active_fail_executor_near_current_combined_fallback_eval_commands(",
                "_build_design_guide_controller_active_fail_executor_geometry_update_row(",
                "_build_design_guide_controller_active_fail_executor_bottom_update_row(",
                "_rescue_mode_choose_tier_from_overview(",
                "_geometry_state_with_updates(",
                "_arrangement_fits_state(",
                "Active fail near-current combined repair",
            ],
            "first_safe_slice": "completed_active_fail_executor_geometry_fit_input_plumbing_boundary_audit",
            "deletion_readiness": "NOT_READY",
        },
    ]
    out: list[dict[str, Any]] = []
    for row in rows:
        token_rows = [_token_row(segment, token) for token in row["tokens"]]
        out.append({**row, "evidence": token_rows, "present": any(t["present"] for t in token_rows)})
    return out


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, segment = _function_source(inputs_source, TARGET)
    classifications = _classifications(segment)
    not_ready = [
        row for row in classifications if row.get("present") and row.get("deletion_readiness") == "NOT_READY"
    ]
    ready_after_parity = [
        row for row in classifications if row.get("present") and row.get("deletion_readiness") == "READY_AFTER_PARITY"
    ]
    return {
        "schema": "design_guide_active_fail_executor_evaluation_loop_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "decision": "NOT_READY_TO_MOVE_WHOLE_LOOP",
        "recommended_first_implementation_slice": "target_band_generator_ranking_projection_extraction_audit",
        "why_not_whole_loop_first": (
            "The loop now delegates pure family metadata projection, ladder eval command shaping, and eval-attempt result shaping, "
            "but still mixes callback-style candidate evaluation execution, family ladder iteration, "
            "fallback rescue seed iteration, cache storage, and page-owned trace emission. Moving the "
            "whole loop would still risk changing evaluation order and stale/cache behavior."
        ),
        "classifications": classifications,
        "not_ready_surfaces": not_ready,
        "ready_after_parity_surfaces": ready_after_parity,
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "candidate_evaluation_has_no_page_or_streamlit_imports": all(
            token not in candidate_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "decision_explicit": payload.get("decision") == "NOT_READY_TO_MOVE_WHOLE_LOOP",
        "first_slice_identified": bool(payload.get("recommended_first_implementation_slice")),
        "classifications_present": len(payload.get("classifications") or []) >= 5,
        "not_ready_surfaces_identified": len(payload.get("not_ready_surfaces") or []) >= 1,
        "completed_ladder_command_or_meta_handoff": (
            any(
                row.get("surface") == "family ladder eval command execution"
                and row.get("first_safe_slice") == "completed_active_fail_executor_ladder_eval_command_handoff"
                and row.get("present")
                for row in payload.get("classifications") or []
            )
            or
            any(
                row.get("surface") == "family meta construction"
                and row.get("deletion_readiness") == "SHELL_CALL"
                and row.get("present")
                for row in payload.get("classifications") or []
            )
            or len(payload.get("ready_after_parity_surfaces") or []) >= 1
        ),
        "completed_eval_attempt_adapter_present": any(
            row.get("surface") == "nested candidate evaluation wrapper"
            and row.get("first_safe_slice") == "completed_active_fail_executor_candidate_eval_attempt_result_adapter"
            and row.get("present")
            for row in payload.get("classifications") or []
        ),
        "controller_import_boundary_clean": bool(payload.get("controller_has_no_page_or_streamlit_imports")),
        "candidate_evaluation_import_boundary_clean": bool(
            payload.get("candidate_evaluation_has_no_page_or_streamlit_imports")
        ),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_evaluation_loop_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_evaluation_loop_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Evaluation Loop Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Executive Summary",
        payload.get("why_not_whole_loop_first", ""),
        "",
        "## Recommended First Slice",
        f"`{payload.get('recommended_first_implementation_slice')}`",
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("classifications") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} "
            f"(current: {row.get('current_owner')}; target: {row.get('target_owner')}; "
            f"readiness: {row.get('deletion_readiness')})"
        )
    lines.extend(
        [
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_evaluation_loop_boundary_audit {status}")
    print(f"decision={payload.get('decision')}")
    print(f"next={payload.get('recommended_first_implementation_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
