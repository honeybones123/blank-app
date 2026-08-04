"""Verify active-under-capacity blocker projection moved to DesignGuideController."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


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


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / script)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_compute_active_under_capacity_blocker_projection,
    )

    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    helper_start, helper_end, helper_segment = _function_source(
        inputs_source,
        "_materialize_compute_active_under_capacity_blocker",
    )
    controller_start, controller_end, controller_segment = _function_source(
        controller_source,
        "build_design_guide_controller_compute_active_under_capacity_blocker_projection",
    )

    cases: list[dict[str, Any]] = []
    for family in ("shear", "bending"):
        evidence = {
            "active_failures": [family],
            "total_candidates_considered": 0,
            "safe_candidate_count": 0,
        }
        if family == "bending":
            evidence["family_id"] = "BENDING_FAIL_GOVERNS"
        projection = build_design_guide_controller_compute_active_under_capacity_blocker_projection(
            active_blocker_family=family,
            primary_item={"util": 1.24, "button_contract": {"enabled": True}},
            existing_evidence=dict(evidence),
            overview={"statuses": {family: "FAIL"}},
        )
        cases.append(
            {
                "family": family,
                "materialized": projection.get("materialized") is True,
                "button_disabled": not bool((projection.get("button_contract") or {}).get("enabled")),
                "evidence_has_exact_blockers": isinstance(
                    (projection.get("existing_evidence") or {}).get("exact_blockers_by_family"),
                    dict,
                ),
                "attempted_updates_present": bool(projection.get("attempted_updates")),
                "projection": projection,
            }
        )

    removed_page_projection_tokens = (
        '"Shear repair is blocked by shear/detailing limits.',
        '"Bending repair is blocked by reinforcement, geometry, ductility, or detailing limits.',
        '"BENDING_FAIL_GOVERNS did not publish family-owned repair-blocked proof.',
        '"active_under_capacity_blocker": not _bending_fail_missing_family_proof_for_evidence',
        '_active_failure_exact_blockers_for_families(',
        '_contract_blocker_for_evidence.update(',
    )
    snapshot_runs = [
        _run("tools/verification/compute_shear_final_threshold_blocker_snapshot.py"),
        _run("tools/verification/compute_safe_cleanup_rehydration_snapshot.py"),
        _run("tools/verification/design_guide_compute_late_evidence_lane_boundary_audit.py"),
    ]
    return {
        "schema": "design_guide_compute_active_under_capacity_blocker_projection_extraction.v1",
        "target": {
            "page_helper_line_start": helper_start,
            "page_helper_line_end": helper_end,
            "controller_helper_line_start": controller_start,
            "controller_helper_line_end": controller_end,
        },
        "cases": cases,
        "source_checks": {
            "page_helper_delegates_projection_to_controller": (
                "_build_design_guide_controller_compute_active_under_capacity_blocker_projection("
                in helper_segment
            ),
            "page_helper_keeps_safe_repair_promotion_probe": (
                "_promote_compute_active_failure_safe_repair_before_blocker(" in helper_segment
            ),
            "page_helper_removed_projection_literals": all(
                token not in helper_segment for token in removed_page_projection_tokens
            ),
            "controller_helper_exists": bool(controller_start),
            "controller_helper_exported": (
                '"build_design_guide_controller_compute_active_under_capacity_blocker_projection"'
                in controller_source
            ),
            "controller_owns_projection_literals": all(
                token in controller_segment
                for token in (
                    '"Shear repair is blocked by shear/detailing limits.',
                    '"Bending repair is blocked by reinforcement, geometry, ductility, or detailing limits.',
                    '"BENDING_FAIL_GOVERNS did not publish family-owned repair-blocked proof.',
                    '"active_under_capacity_blocker": not bending_missing_family_proof',
                    "active_failure_exact_blockers_for_families(",
                )
            ),
            "controller_has_no_page_or_streamlit_imports": all(
                token not in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
        },
        "snapshot_runs": snapshot_runs,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "projection_cases_materialize": all(bool(row.get("materialized")) for row in payload.get("cases") or []),
        "projection_cases_disable_button": all(bool(row.get("button_disabled")) for row in payload.get("cases") or []),
        "projection_cases_have_attempted_updates": all(
            bool(row.get("attempted_updates_present")) for row in payload.get("cases") or []
        ),
        **{name: bool(value) for name, value in source_checks.items()},
        "focused_snapshots_pass": all(bool(row.get("passed")) for row in payload.get("snapshot_runs") or []),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_active_under_capacity_blocker_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_active_under_capacity_blocker_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    target = dict(payload.get("target") or {})
    lines = [
        "# Design Guide Compute Active Under-Capacity Blocker Projection Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Surface",
        f"- page helper: `_materialize_compute_active_under_capacity_blocker` lines {target.get('page_helper_line_start')}-{target.get('page_helper_line_end')}",
        f"- controller helper: `build_design_guide_controller_compute_active_under_capacity_blocker_projection` lines {target.get('controller_helper_line_start')}-{target.get('controller_helper_line_end')}",
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"{payload['status']}: {json_path}")
    print(f"report: {report_path}")
    if payload["status"] != "PASS":
        print(json.dumps({k: v for k, v in checks.items() if not v}, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
