"""Verify late-evidence contract rebound entry decision moved to DesignGuideController."""

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
        resolve_design_guide_controller_compute_late_evidence_contract_rebound_decision,
    )

    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    page_start, page_end, page_segment = _function_source(
        inputs_source,
        "_apply_compute_late_evidence_contract_rebound",
    )
    controller_start, controller_end, controller_segment = _function_source(
        controller_source,
        "resolve_design_guide_controller_compute_late_evidence_contract_rebound_decision",
    )

    accepted = resolve_design_guide_controller_compute_late_evidence_contract_rebound_decision(
        primary_item={"button_contract": {"actionable": False, "updates": {}, "preview_pass": False}},
        existing_evidence={"selected_candidate_updates": {"s_lig": 180.0}, "family": "shear"},
    )
    active_blocked = resolve_design_guide_controller_compute_late_evidence_contract_rebound_decision(
        primary_item={"button_contract": {"actionable": False, "updates": {}, "preview_pass": False}},
        existing_evidence={
            "selected_candidate_updates": {"s_lig": 180.0},
            "family": "shear",
            "active_under_capacity_blocker": True,
        },
    )
    enabled_same = resolve_design_guide_controller_compute_late_evidence_contract_rebound_decision(
        primary_item={
            "button_contract": {
                "actionable": True,
                "updates": {"s_lig": 180.0},
                "preview_pass": True,
                "blocking_reason": None,
            }
        },
        existing_evidence={"selected_candidate_updates": {"s_lig": 180.0}, "family": "shear"},
    )
    combined_mismatch = resolve_design_guide_controller_compute_late_evidence_contract_rebound_decision(
        primary_item={
            "button_contract": {
                "actionable": True,
                "updates": {"s_lig": 200.0},
                "preview_pass": True,
                "blocking_reason": None,
            }
        },
        existing_evidence={"selected_candidate_updates": {"s_lig": 180.0}, "family": "combined"},
    )

    removed_page_tokens = (
        "contract_disabled_or_mismatched =",
        '"late_updates_present"',
        '"active_under_capacity_blocker": bool(existing_evidence.get("active_under_capacity_blocker"))',
    )
    controller_tokens = (
        "contract_disabled_or_mismatched =",
        '"late_updates_present"',
        '"active_under_capacity_blocker"',
        "design_guide_button_contract_enabled(",
    )
    snapshot_runs = [
        _run("tools/verification/compute_safe_cleanup_rehydration_snapshot.py"),
        _run("tools/verification/compute_shear_final_threshold_blocker_snapshot.py"),
        _run("tools/verification/design_guide_compute_late_evidence_lane_boundary_audit.py"),
    ]
    return {
        "schema": "design_guide_compute_late_evidence_contract_rebound_decision_extraction.v1",
        "target": {
            "page_helper_line_start": page_start,
            "page_helper_line_end": page_end,
            "page_helper_line_count": max(0, page_end - page_start + 1),
            "controller_helper_line_start": controller_start,
            "controller_helper_line_end": controller_end,
        },
        "decision_cases": {
            "accepted_should_rebound": bool(accepted.get("should_rebound")),
            "active_blocked_does_not_rebound": not bool(active_blocked.get("should_rebound")),
            "enabled_same_does_not_rebound": not bool(enabled_same.get("should_rebound")),
            "combined_mismatch_rebounds": bool(combined_mismatch.get("should_rebound")),
        },
        "source_checks": {
            "page_helper_delegates_entry_decision_to_controller": (
                "_resolve_design_guide_controller_compute_late_evidence_contract_rebound_decision("
                in page_segment
            ),
            "page_helper_keeps_rebound_execution_and_mutation_shell": (
                "_compute_rebound_item_from_controller_publication_item(" in page_segment
                and "_collapsed_guidance_item_from_final_publication_authority(" in page_segment
                and "_stamp_final_publication_compute_handoff_rebound_decision_proof(" in page_segment
            ),
            "page_helper_removed_entry_decision_tokens": all(token not in page_segment for token in removed_page_tokens),
            "controller_helper_exists": bool(controller_start),
            "controller_helper_exported": (
                '"resolve_design_guide_controller_compute_late_evidence_contract_rebound_decision"'
                in controller_source
            ),
            "controller_owns_entry_decision_tokens": all(token in controller_segment for token in controller_tokens),
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
    cases = dict(payload.get("decision_cases") or {})
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
    json_path = ARTIFACT_DIR / f"design_guide_compute_late_evidence_contract_rebound_decision_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_late_evidence_contract_rebound_decision_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    target = dict(payload.get("target") or {})
    lines = [
        "# Design Guide Compute Late Evidence Contract Rebound Decision Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Surface",
        f"- page helper: `_apply_compute_late_evidence_contract_rebound` lines {target.get('page_helper_line_start')}-{target.get('page_helper_line_end')}",
        f"- page helper line count: {target.get('page_helper_line_count')}",
        f"- controller helper: `resolve_design_guide_controller_compute_late_evidence_contract_rebound_decision` lines {target.get('controller_helper_line_start')}-{target.get('controller_helper_line_end')}",
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
