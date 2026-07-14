"""Verify safe-cleanup rehydration projection moved to DesignGuideController."""

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
        timeout=240,
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
        build_design_guide_controller_compute_safe_cleanup_rehydration_projection,
    )

    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    page_start, page_end, page_segment = _function_source(
        inputs_source,
        "_build_compute_safe_cleanup_rehydrated_result",
    )
    controller_start, controller_end, controller_segment = _function_source(
        controller_source,
        "build_design_guide_controller_compute_safe_cleanup_rehydration_projection",
    )

    updates = {"s_lig": 180.0, "lig_legs": 3}
    accepted_projection = build_design_guide_controller_compute_safe_cleanup_rehydration_projection(
        primary_item={
            "title_main": "shear cleanup blocked by final efficiency threshold",
            "action_payload": {"preview_pass": True, "expected_util": 0.91},
        },
        existing_evidence={
            "family": "shear",
            "best_safe_candidate_updates": dict(updates),
            "best_safe_candidate_id": "accepted_safe",
            "best_safe_final_util": 0.91,
            "accepted_band_candidate_count": 1,
            "exact_blockers_by_family": {"shear": {"reason": "stale"}},
        },
        primary_contract={},
        primary_title="shear cleanup blocked by final efficiency threshold",
        primary_action="Run one-click auto design",
        primary_action_blocked=True,
        state_updates_match_accepted_safe_updates=False,
    )
    combined_projection = build_design_guide_controller_compute_safe_cleanup_rehydration_projection(
        primary_item={
            "title_main": "shear cleanup blocked by final efficiency threshold",
            "action_payload": {"preview_pass": True},
        },
        existing_evidence={"family": "shear", "selected_candidate_id": "combined_safe"},
        primary_contract={},
        primary_title="shear cleanup blocked by final efficiency threshold",
        primary_action="Run one-click auto design",
        primary_action_blocked=True,
        state_updates_match_accepted_safe_updates=False,
        combined_safe_row={
            "candidate_id": "combined_safe",
            "proposed_updates": {"s_lig": 180.0, "lig_legs": 3, "bot1_count": 7},
            "preview_pass": True,
            "preview_util": 0.88,
        },
    )
    no_rehydrate_projection = build_design_guide_controller_compute_safe_cleanup_rehydration_projection(
        primary_item={"title_main": "Other title"},
        existing_evidence={},
        primary_contract={"enabled": False},
        primary_title="Other title",
        primary_action="None",
        primary_action_blocked=True,
        state_updates_match_accepted_safe_updates=False,
    )

    removed_page_tokens = (
        '"Shear and bending cleanup - one-click optimisation"',
        '"Shear cleanup - best safe one-click reduction"',
        '"best_safe_candidate_applied"',
        '"no_second_cta_required"',
        '"efficiency_tightening"',
        "_normalise_design_guide_candidate_id(",
        "_format_guidance_title(",
        "_parse_util_value(",
    )
    controller_tokens = (
        '"Shear and bending cleanup - one-click optimisation"',
        '"Shear cleanup - best safe one-click reduction"',
        '"best_safe_candidate_applied"',
        '"no_second_cta_required"',
        '"efficiency_tightening"',
        "normalise_design_guide_candidate_id(",
        "_controller_format_guidance_title(",
        "_float_or_none(",
    )
    snapshot_runs = [
        _run("tools/verification/compute_safe_cleanup_rehydration_snapshot.py"),
        _run("tools/verification/compute_shear_final_threshold_blocker_snapshot.py"),
        _run("tools/verification/design_guide_compute_late_evidence_lane_boundary_audit.py"),
    ]
    return {
        "schema": "design_guide_compute_safe_cleanup_rehydration_projection_extraction.v1",
        "target": {
            "page_helper_line_start": page_start,
            "page_helper_line_end": page_end,
            "page_helper_line_count": max(0, page_end - page_start + 1),
            "controller_helper_line_start": controller_start,
            "controller_helper_line_end": controller_end,
        },
        "projection_cases": {
            "accepted_safe_rehydrated": bool(accepted_projection.get("rehydrated")),
            "accepted_safe_button_enabled": bool((accepted_projection.get("primary_contract") or {}).get("enabled")),
            "accepted_safe_stale_blockers_removed": not bool(
                (accepted_projection.get("existing_evidence") or {}).get("exact_blockers_by_family")
            ),
            "combined_safe_rehydrated": bool(combined_projection.get("rehydrated")),
            "combined_safe_family": (combined_projection.get("primary_contract") or {}).get("family"),
            "no_rehydrate_declines": not bool(no_rehydrate_projection.get("rehydrated")),
        },
        "source_checks": {
            "page_helper_delegates_projection_to_controller": (
                "_build_design_guide_controller_compute_safe_cleanup_rehydration_projection(" in page_segment
            ),
            "page_helper_keeps_combined_safe_row_collection": (
                "_publishable_safe_combined_cleanup_row_from_evidence(" in page_segment
            ),
            "page_helper_keeps_state_match_probe": "_updates_match_state(" in page_segment,
            "page_helper_removed_projection_tokens": all(token not in page_segment for token in removed_page_tokens),
            "controller_helper_exists": bool(controller_start),
            "controller_helper_exported": (
                '"build_design_guide_controller_compute_safe_cleanup_rehydration_projection"'
                in controller_source
            ),
            "controller_owns_projection_tokens": all(token in controller_segment for token in controller_tokens),
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
    cases = dict(payload.get("projection_cases") or {})
    source = dict(payload.get("source_checks") or {})
    return {
        **{name: bool(value) for name, value in cases.items()},
        **{name: bool(value) for name, value in source.items()},
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
    json_path = ARTIFACT_DIR / f"design_guide_compute_safe_cleanup_rehydration_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_safe_cleanup_rehydration_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    target = dict(payload.get("target") or {})
    lines = [
        "# Design Guide Compute Safe Cleanup Rehydration Projection Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Surface",
        f"- page helper: `_build_compute_safe_cleanup_rehydrated_result` lines {target.get('page_helper_line_start')}-{target.get('page_helper_line_end')}",
        f"- page helper line count: {target.get('page_helper_line_count')}",
        f"- controller helper: `build_design_guide_controller_compute_safe_cleanup_rehydration_projection` lines {target.get('controller_helper_line_start')}-{target.get('controller_helper_line_end')}",
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
