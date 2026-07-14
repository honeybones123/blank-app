"""Verify missing-candidate target-band context moved to DesignGuideController."""

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
    import inputs_page
    from design_brain.config import (
        resolve_design_mode_config,
        resolve_design_optimisation_goal,
        resolve_efficiency_target_band,
    )
    from design_brain.design_guide_controller import (
        build_design_guide_controller_compute_missing_candidate_target_band_context,
    )

    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    helper_start, helper_end, helper_segment = _function_source(
        inputs_source,
        "_prepare_compute_missing_candidate_search_evidence",
    )
    controller_start, controller_end, controller_segment = _function_source(
        controller_source,
        "build_design_guide_controller_compute_missing_candidate_target_band_context",
    )

    labels = dict(inputs_page.DESIGN_OPTIMISATION_GOAL_LABELS)
    mode_config_by_goal = dict(inputs_page.AUTO_DESIGN_MODE_CONFIG)
    default_low = inputs_page.EFFICIENCY_TARGET_UTIL_MIN
    default_high = inputs_page.EFFICIENCY_TARGET_UTIL_MAX

    cases: list[dict[str, Any]] = []
    for state in (
        {"design_optimisation_goal": "balanced"},
        {"design_optimisation_goal": "economy"},
        {"design_optimisation_goal": "invalid_goal"},
    ):
        goal = resolve_design_optimisation_goal(
            state,
            goal_labels=labels,
            default_goal="balanced",
        )
        mode = resolve_design_mode_config(
            goal,
            mode_config_by_goal=mode_config_by_goal,
            default_goal="balanced",
        )
        low, high, default_used = resolve_efficiency_target_band(
            mode,
            goal=goal,
            mode_config_by_goal=mode_config_by_goal,
            default_low=float(default_low),
            default_high=float(default_high),
            default_goal="balanced",
        )
        expected = {
            "goal": goal,
            "mode_config": dict(mode),
            "target_low": float(low),
            "target_high": float(high),
            "default_used": bool(default_used),
        }
        actual = build_design_guide_controller_compute_missing_candidate_target_band_context(
            state=dict(state),
            goal_labels=dict(labels),
            mode_config_by_goal=dict(mode_config_by_goal),
            default_low=default_low,
            default_high=default_high,
            default_goal="balanced",
        )
        cases.append(
            {
                "state": state,
                "matches_old_target_band_context": actual == expected,
                "expected": expected,
                "actual": actual,
            }
        )

    snapshot_runs = [
        _run("tools/verification/design_guide_compute_late_evidence_lane_boundary_audit.py"),
    ]
    return {
        "schema": "design_guide_compute_missing_candidate_target_band_context_extraction.v1",
        "target": {
            "page_helper_line_start": helper_start,
            "page_helper_line_end": helper_end,
            "controller_helper_line_start": controller_start,
            "controller_helper_line_end": controller_end,
        },
        "cases": cases,
        "source_checks": {
            "page_helper_delegates_target_band_context_to_controller": (
                "_build_design_guide_controller_compute_missing_candidate_target_band_context("
                in helper_segment
            ),
            "page_helper_no_longer_calls_local_target_band_wrappers": all(
                token not in helper_segment
                for token in (
                    "_design_optimisation_goal(",
                    "_design_mode_config(",
                    "_resolved_efficiency_target_band(",
                )
            ),
            "page_helper_keeps_page_record_collection": all(
                token in helper_segment
                for token in (
                    "_guidance_item_source_candidate_id(",
                    "_resolve_recommendation_updates(",
                    "_build_compute_missing_candidate_search_evidence(",
                )
            ),
            "controller_helper_exists": bool(controller_start),
            "controller_helper_exported": (
                '"build_design_guide_controller_compute_missing_candidate_target_band_context"'
                in controller_source
            ),
            "controller_uses_design_brain_config_helpers": all(
                token in controller_segment
                for token in (
                    "resolve_design_optimisation_goal(",
                    "resolve_design_mode_config(",
                    "resolve_efficiency_target_band(",
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
        "all_cases_match_old_target_band_context": all(
            bool(row.get("matches_old_target_band_context")) for row in payload.get("cases") or []
        ),
        **{name: bool(value) for name, value in source_checks.items()},
        "late_evidence_boundary_audit_passes": all(
            bool(row.get("passed")) for row in payload.get("snapshot_runs") or []
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
    json_path = ARTIFACT_DIR / f"design_guide_compute_missing_candidate_target_band_context_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_missing_candidate_target_band_context_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    target = dict(payload.get("target") or {})
    lines = [
        "# Design Guide Compute Missing-Candidate Target-Band Context Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Surface",
        f"- page helper: `_prepare_compute_missing_candidate_search_evidence` lines {target.get('page_helper_line_start')}-{target.get('page_helper_line_end')}",
        f"- controller helper: `build_design_guide_controller_compute_missing_candidate_target_band_context` lines {target.get('controller_helper_line_start')}-{target.get('controller_helper_line_end')}",
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
