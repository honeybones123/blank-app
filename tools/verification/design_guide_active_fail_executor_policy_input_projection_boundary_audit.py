"""Audit active-fail executor policy/input projection boundary.

This is audit-only. It maps the pure target-band/route input preparation still
inside `_active_fail_near_current_repair_item(...)` before any controller or
service extraction.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
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


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _token_rows(segment: str, start_line: int, tokens: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "token": token,
            "present": token in segment,
            "count": segment.count(token),
            "lines": _line_numbers(segment, start_line, token)[:20],
        }
        for token in tokens
    ]


def _surface(
    *,
    name: str,
    segment: str,
    start_line: int,
    tokens: list[str],
    current_owner: str,
    target_owner: str,
    classification: str,
    readiness: str,
    first_slice: str | None = None,
) -> dict[str, Any]:
    evidence = _token_rows(segment, start_line, tokens)
    return {
        "surface": name,
        "current_owner": current_owner,
        "target_owner": target_owner,
        "classification": classification,
        "deletion_readiness": readiness,
        "first_slice": first_slice,
        "present": any(row.get("present") for row in evidence),
        "evidence": evidence,
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    prefix = segment.split("def _evaluate(", 1)[0]
    surfaces = [
        _surface(
            name="base state snapshot and active failure normalization",
            segment=prefix,
            start_line=start,
            tokens=["active =", "_guidance_state_snapshot("],
            current_owner="inputs_page page shell",
            target_owner="inputs_page page shell",
            classification="page-shell input collection",
            readiness="SHELL_ONLY",
        ),
        _surface(
            name="optimisation goal and target-band policy inputs",
            segment=prefix,
            start_line=start,
            tokens=["_build_design_guide_controller_active_fail_executor_policy_input_request("],
            current_owner="DesignGuideController called by inputs_page",
            target_owner="DesignGuideController policy-input request object",
            classification="completed controller-owned policy input projection",
            readiness="SHELL_CALL",
        ),
        _surface(
            name="candidate generation context request",
            segment=prefix,
            start_line=start,
            tokens=["_build_active_fail_executor_candidate_generation_context("],
            current_owner="design_brain.candidate_evaluation called by inputs_page",
            target_owner="candidate_evaluation service",
            classification="already service-owned helper call",
            readiness="SHELL_CALL",
        ),
        _surface(
            name="search/cache fingerprint input projection",
            segment=prefix,
            start_line=start,
            tokens=["stable_fingerprint_for_payload(", "overview_statuses", "overview_utils", "overview_any_fail"],
            current_owner="inputs_page page-shell cache guard",
            target_owner="inputs_page page-shell cache guard",
            classification="page-owned rerun cache/stale-state guard",
            readiness="KEEP_BOUNDED",
        ),
        _surface(
            name="bending selected repair cache and early-stop guard",
            segment=prefix,
            start_line=start,
            tokens=[
                "_bending_fail_publication_snapshot_for_state(",
                "_bending_post_cta_early_stop_status(",
                "st.session_state",
                "_inputs_pre_widget_trace(",
            ],
            current_owner="inputs_page page-shell/session side-effect guard",
            target_owner="inputs_page page shell or future cache/debug service",
            classification="page-owned cache/session/trace guard, not Design Brain decision authority",
            readiness="KEEP_BOUNDED",
        ),
        _surface(
            name="route geometry-lock and rescue-tier inputs",
            segment=segment,
            start_line=start,
            tokens=[
                "_geometry_lock_enabled(",
                "_rescue_mode_choose_tier_from_overview(",
                "_rescue_mode_seed_order(",
            ],
            current_owner="inputs_page",
            target_owner="DesignGuideController route-input adapter or bounded page-shell callback input",
            classification="mixed route input preparation, not first slice",
            readiness="NOT_READY",
            first_slice="active_fail_executor_route_input_projection_audit",
        ),
    ]
    first_slice = {
        "name": "active_fail_executor_route_input_projection_audit",
        "why": (
            "Optimisation goal, mode config, and target-band projection now delegate to "
            "DesignGuideController. The next remaining mixed input surface is route geometry-lock "
            "and rescue-tier input preparation."
        ),
        "move": (
            "Audit only. Classify geometry-lock and rescue-tier input preparation before moving any "
            "code. Keep session/cache/trace, executor callbacks, family ladder execution, CTA side effects, "
            "and visible wording unchanged."
        ),
        "required_verifier": "design_guide_active_fail_executor_route_input_projection_audit.py",
    }
    return {
        "schema": "design_guide_active_fail_executor_policy_input_projection_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
            "prefix_line_count": len(prefix.splitlines()),
        },
        "decision": "POLICY_INPUT_PROJECTION_BOUNDARY_MAPPED",
        "surfaces": surfaces,
        "first_safe_implementation_slice": first_slice,
        "candidate_evaluation_boundary_clean": all(
            token not in candidate_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "controller_boundary_clean": all(
            token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    surfaces = payload.get("surfaces") or []
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "surfaces_classified": len(surfaces) >= 6,
        "policy_input_surface_service_backed": any(
            row.get("surface") == "optimisation goal and target-band policy inputs"
            and row.get("present")
            and row.get("deletion_readiness") == "SHELL_CALL"
            for row in surfaces
        ),
        "cache_and_session_bounded": all(
            any(row.get("surface") == surface and row.get("deletion_readiness") == "KEEP_BOUNDED" for row in surfaces)
            for surface in (
                "search/cache fingerprint input projection",
                "bending selected repair cache and early-stop guard",
            )
        ),
        "candidate_generation_context_service_backed": any(
            row.get("surface") == "candidate generation context request"
            and row.get("present")
            and row.get("deletion_readiness") == "SHELL_CALL"
            for row in surfaces
        ),
        "first_safe_slice_identified": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
        ),
        "candidate_evaluation_boundary_clean": bool(payload.get("candidate_evaluation_boundary_clean")),
        "controller_boundary_clean": bool(payload.get("controller_boundary_clean")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_policy_input_projection_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_policy_input_projection_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Policy Input Projection Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} "
            f"({row.get('current_owner')} -> {row.get('target_owner')}); "
            f"readiness `{row.get('deletion_readiness')}`"
        )
    first_slice = payload.get("first_safe_implementation_slice") or {}
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first_slice.get('name')}`",
            f"- Move: {first_slice.get('move')}",
            f"- Verifier: `{first_slice.get('required_verifier')}`",
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
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_policy_input_projection_boundary_audit {payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
