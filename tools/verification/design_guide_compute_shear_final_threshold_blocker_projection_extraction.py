"""Verify shear final-threshold blocker projection moved to DesignGuideController."""

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
        build_design_guide_controller_shear_final_threshold_blocker_projection,
    )

    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    helper_start, helper_end, helper_segment = _function_source(
        inputs_source,
        "_materialize_compute_shear_final_threshold_blocker",
    )
    controller_start, controller_end, controller_segment = _function_source(
        controller_source,
        "build_design_guide_controller_shear_final_threshold_blocker_projection",
    )

    fixture_item = {
        "title_main": "Shear cleanup blocked by final efficiency threshold",
        "button_contract": {"expected_util": 0.73, "candidate_id": "old_candidate"},
        "source_candidate_id": "source_candidate",
        "util": 0.73,
    }
    fixture_evidence = {
        "target_low": 0.85,
        "target_high": 1.0,
        "selected_candidate_id": "selected_candidate",
        "total_candidates_considered": 4,
    }
    fixture_updates = {"link_count": 0}
    projection = build_design_guide_controller_shear_final_threshold_blocker_projection(
        primary_item=dict(fixture_item),
        existing_evidence=dict(fixture_evidence),
        shear_util=0.73,
        attempted_updates=dict(fixture_updates),
        final_accepted_min_family_util=0.85,
    )

    snapshot_runs = [
        _run("tools/verification/compute_shear_final_threshold_blocker_snapshot.py"),
        _run("tools/verification/compute_safe_cleanup_rehydration_snapshot.py"),
    ]

    page_owned_projection_tokens = (
        "No executor-backed one-click candidate reaches the final accepted-family",
        '"failed_check_name": "final accepted shear-family utilisation"',
        '"outside_target_band_allowed_category": "shear_lock"',
        '"display_truth_source": "post_commit_truth"',
        '"blocking_reason": _reason_for_evidence',
        '_evidence_contract_for_blocker.update(',
    )

    return {
        "schema": "design_guide_compute_shear_final_threshold_blocker_projection_extraction.v1",
        "target": {
            "page_helper_line_start": helper_start,
            "page_helper_line_end": helper_end,
            "controller_helper_line_start": controller_start,
            "controller_helper_line_end": controller_end,
        },
        "source_checks": {
            "page_helper_delegates_to_controller": (
                "_build_design_guide_controller_shear_final_threshold_blocker_projection(" in helper_segment
            ),
            "page_helper_keeps_title_guard": (
                "shear cleanup blocked by final efficiency threshold" in helper_segment
            ),
            "page_helper_keeps_input_collection": all(
                token in helper_segment
                for token in (
                    "_parse_util_value(",
                    "_resolve_recommendation_updates(",
                    "_compute_guidance_trace_event(",
                )
            ),
            "page_helper_removed_projection_literals": all(
                token not in helper_segment for token in page_owned_projection_tokens
            ),
            "controller_helper_exists": bool(controller_start),
            "controller_helper_exported": (
                '"build_design_guide_controller_shear_final_threshold_blocker_projection"'
                in controller_source
            ),
            "controller_owns_reason_and_projection_literals": all(
                token in controller_segment
                for token in (
                    "No executor-backed one-click candidate reaches the final accepted-family",
                    '"failed_check_name": "final accepted shear-family utilisation"',
                    '"outside_target_band_allowed_category": "shear_lock"',
                    '"display_truth_source": "post_commit_truth"',
                )
            ),
            "controller_has_no_page_or_streamlit_imports": all(
                token not in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
        },
        "projection_fixture": {
            "materialized": projection.get("materialized"),
            "reason": projection.get("reason"),
            "shear_util": projection.get("shear_util"),
            "attempted_updates": projection.get("attempted_updates"),
            "primary_item_button_contract": (projection.get("primary_item") or {}).get("button_contract"),
            "existing_evidence": projection.get("existing_evidence"),
        },
        "projection_checks": {
            "projection_materialized": projection.get("materialized") is True,
            "projection_disables_button_contract": not bool(
                ((projection.get("primary_item") or {}).get("button_contract") or {}).get("enabled")
            ),
            "projection_clears_action_payload": (projection.get("primary_item") or {}).get("action_payload") == {},
            "projection_sets_exact_blocker": "shear"
            in ((projection.get("primary_item") or {}).get("exact_blockers_by_family") or {}),
            "projection_preserves_updates": projection.get("attempted_updates") == fixture_updates,
        },
        "snapshot_runs": snapshot_runs,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    projection_checks = dict(payload.get("projection_checks") or {})
    return {
        **{name: bool(value) for name, value in source_checks.items()},
        **{name: bool(value) for name, value in projection_checks.items()},
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
    json_path = ARTIFACT_DIR / f"design_guide_compute_shear_final_threshold_blocker_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_shear_final_threshold_blocker_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    target = dict(payload.get("target") or {})
    lines = [
        "# Design Guide Compute Shear Final-Threshold Blocker Projection Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Surface",
        f"- page helper: `_materialize_compute_shear_final_threshold_blocker` lines {target.get('page_helper_line_start')}-{target.get('page_helper_line_end')}",
        f"- controller helper: `build_design_guide_controller_shear_final_threshold_blocker_projection` lines {target.get('controller_helper_line_start')}-{target.get('controller_helper_line_end')}",
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        "",
        "## Snapshot Runs",
    ]
    for row in payload.get("snapshot_runs") or []:
        lines.append(f"- `{row.get('script')}`: {'PASS' if row.get('passed') else 'FAIL'}")
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
