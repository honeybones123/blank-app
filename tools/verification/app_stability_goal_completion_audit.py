"""Composed completion audit for the app-wide stability goal.

This verifier is proof-only. It composes the current stability evidence and
checks it against the full "Stabilise the Entire App Before Further
Refactoring" goal instead of redefining success around the newest green gate.

Status means the audit itself ran. The app-wide completion state is reported in
``completion_status``:

- ``LOCKED_PARTIAL``: current critical slices are locked, but the full goal is
  not proven across every required page/workflow.
- ``COMPLETE``: every exit-gate requirement has current direct evidence.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REQUIRED_CRITICAL_WORKFLOWS = {
    "normal_action_input_edit",
    "reinforcement_edit",
    "geometry_width_edit",
    "explicit_design_calculation",
    "page_navigation_cycle",
    "design_guide_expand_collapse",
    "calculation_panel_expand_collapse",
    "design_mode_toggle",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None, {}
    path = paths[-1]
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive verifier path
        return path, {"status": "UNREADABLE", "error": str(exc)}


def _status(payload: dict[str, Any]) -> str | None:
    value = payload.get("status") or payload.get("result") or payload.get("audit_result")
    return str(value) if value is not None else None


def _is_pass(payload: dict[str, Any]) -> bool:
    return _status(payload) in {"PASS", "LIVE_EXECUTION_PASS"}


def _count_pages(baseline: dict[str, Any]) -> int:
    pages = baseline.get("pages")
    return len(pages) if isinstance(pages, list) else 0


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary")
    return dict(value) if isinstance(value, dict) else {}


def _workflow_summary(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("workflows")
    if not isinstance(rows, list):
        return {
            "workflow_count": 0,
            "workflows": [],
            "all_workflows_10x_passed": False,
        }
    names: list[str] = []
    details: dict[str, dict[str, Any]] = {}
    all_passed = True
    for row in rows:
        if not isinstance(row, dict):
            all_passed = False
            continue
        name = str(row.get("workflow") or row.get("name") or row.get("id") or "unknown")
        passed = int(row.get("passed") or 0)
        failed = int(row.get("failed") or 0)
        repetitions = int(row.get("repetitions") or 0)
        names.append(name)
        details[name] = {
            "passed": passed,
            "failed": failed,
            "repetitions": repetitions,
        }
        if passed < 10 or failed != 0 or repetitions < 10:
            all_passed = False
    return {
        "workflow_count": len(names),
        "workflows": names,
        "details": details,
        "all_workflows_10x_passed": all_passed,
        "required_workflows_present": sorted(REQUIRED_CRITICAL_WORKFLOWS.intersection(set(names))),
        "missing_required_workflows": sorted(REQUIRED_CRITICAL_WORKFLOWS.difference(set(names))),
        "required_workflows_10x_passed": all_passed and not REQUIRED_CRITICAL_WORKFLOWS.difference(set(names)),
    }


def _artifact_matrix() -> dict[str, dict[str, Any]]:
    prefixes = {
        "baseline_inventory": "app_stability_baseline_inventory",
        "critical_workflows_lock": "app_stability_critical_workflows_lock",
        "inputs_apply_10x_lock": "app_stability_inputs_apply_10x_workflow_lock",
        "apply_interaction_trace": "app_stability_inputs_apply_interaction_trace",
        "solver_state_handoff": "app_stability_solver_state_handoff_snapshot",
        "post_apply_smoothness_lock": "app_stability_post_apply_smoothness_root_cause_lock",
        "design_guide_smoothness_completion": "design_guide_smoothness_goal_completion_audit",
        "family_10_fuzz": "family_10_fuzz_audit",
        "render_bridge_lock": "design_guide_render_bridge_lock",
        "independence_lock": "design_guide_independence_lock",
        "compute_resolver_publication_lock": "design_guide_compute_resolver_publication_bridge_lock",
        "zero_authority_lock": "design_brain_inputs_page_zero_authority_inventory_lock",
        "shared_component_matrix": "design_brain_shared_component_lock_matrix",
        "rerun_trigger_ownership": "design_guide_same_session_rerun_trigger_ownership",
        "transient_blank_gap_ownership": "design_guide_transient_blank_gap_ownership",
    }
    matrix: dict[str, dict[str, Any]] = {}
    for key, prefix in prefixes.items():
        path, payload = _latest(prefix)
        matrix[key] = {
            "prefix": prefix,
            "path": str(path) if path else None,
            "status": _status(payload),
            "payload": payload,
        }
    return matrix


def _build() -> dict[str, Any]:
    matrix = _artifact_matrix()
    baseline = matrix["baseline_inventory"]["payload"]
    critical_workflows = matrix["critical_workflows_lock"]["payload"]
    family = matrix["family_10_fuzz"]["payload"]
    family_summary = _summary(family)
    apply_summary = _summary(matrix["inputs_apply_10x_lock"]["payload"])
    workflow_summary = _workflow_summary(critical_workflows)

    phase_2_proven = (
        _is_pass(critical_workflows)
        and bool(workflow_summary["required_workflows_10x_passed"])
        and _is_pass(matrix["inputs_apply_10x_lock"]["payload"])
    )

    phase_checks = {
        "phase_1_baseline_inventory": {
            "status": "PROVEN" if _is_pass(baseline) and _count_pages(baseline) >= 8 else "MISSING_OR_WEAK",
            "evidence": matrix["baseline_inventory"]["path"],
            "notes": f"pages inventoried: {_count_pages(baseline)}",
        },
        "phase_2_critical_workflows": {
            "status": (
                "PROVEN"
                if phase_2_proven
                else "PARTIAL"
                if _is_pass(critical_workflows) and _is_pass(matrix["inputs_apply_10x_lock"]["payload"])
                else "MISSING_OR_WEAK"
            ),
            "evidence": [
                matrix["critical_workflows_lock"]["path"],
                matrix["inputs_apply_10x_lock"]["path"],
            ],
            "notes": (
                f"Configured workflows locked: {workflow_summary['workflows']} plus the separate Apply 10x lock. "
                f"Missing required workflows: {workflow_summary['missing_required_workflows']}."
            ),
        },
        "phase_3_complete_interaction_trace": {
            "status": "PROVEN" if _is_pass(matrix["apply_interaction_trace"]["payload"]) else "MISSING_OR_WEAK",
            "evidence": matrix["apply_interaction_trace"]["path"],
            "notes": "Design Guide Apply path trace exists; broader workflows still need equivalent traces if unstable.",
        },
        "phase_4_single_controlled_update_pipeline": {
            "status": "PARTIAL",
            "evidence": [
                matrix["render_bridge_lock"]["path"],
                matrix["independence_lock"]["path"],
                matrix["compute_resolver_publication_lock"]["path"],
            ],
            "notes": "Design Guide publication/render pipeline is locked; all-page action pipeline is not yet directly proven.",
        },
        "phase_5_canonical_state_ownership": {
            "status": "PARTIAL",
            "evidence": [
                matrix["zero_authority_lock"]["path"],
                matrix["rerun_trigger_ownership"]["path"],
            ],
            "notes": "Design Guide/Input ownership has strong evidence; a full app state ownership registry is not proven current.",
        },
        "phase_6_jumping_and_blanking": {
            "status": "PARTIAL",
            "evidence": [
                matrix["post_apply_smoothness_lock"]["path"],
                matrix["design_guide_smoothness_completion"]["path"],
                matrix["transient_blank_gap_ownership"]["path"],
            ],
            "notes": "Design Guide smoothness is locked from current evidence; every page/interaction is not fully proven.",
        },
        "phase_7_duplicate_computation": {
            "status": "PARTIAL",
            "evidence": [
                matrix["design_guide_smoothness_completion"]["path"],
                matrix["critical_workflows_lock"]["path"],
            ],
            "notes": "Design Guide unchanged-state computation is controlled; all major engineering entry points are not fully instrumented here.",
        },
        "phase_8_previous_valid_result": {
            "status": "PARTIAL",
            "evidence": [
                matrix["critical_workflows_lock"]["path"],
                matrix["inputs_apply_10x_lock"]["path"],
            ],
            "notes": "Apply workflows settle without duplicate action/loading residue; all-page settled-result model is not proven complete.",
        },
        "phase_9_interactive_vs_full_verification": {
            "status": "PARTIAL",
            "evidence": [
                matrix["design_guide_smoothness_completion"]["path"],
                matrix["family_10_fuzz"]["path"],
            ],
            "notes": "Interactive and verifier authority remain aligned for locked Design Guide/family paths; broader execution levels need current documentation.",
        },
        "phase_10_shared_component_audit": {
            "status": "PARTIAL" if matrix["shared_component_matrix"]["path"] else "MISSING_OR_WEAK",
            "evidence": matrix["shared_component_matrix"]["path"],
            "notes": "Shared component matrix exists, but it is older than the latest app-wide gates and should be refreshed before deletion/refactor.",
        },
        "phase_11_regression_isolation": {
            "status": "PROVEN"
            if _is_pass(family)
            and int(family_summary.get("scenario_trigger_passes") or 0) >= 90
            and int(apply_summary.get("passed_iterations") or 0) >= 10
            else "PARTIAL",
            "evidence": [
                matrix["family_10_fuzz"]["path"],
                matrix["inputs_apply_10x_lock"]["path"],
            ],
            "notes": "Family and Apply regressions are current and strong; page-by-page reports are still partial.",
        },
        "phase_12_exit_gate": {
            "status": "PARTIAL",
            "evidence": [
                matrix["baseline_inventory"]["path"],
                matrix["critical_workflows_lock"]["path"],
                matrix["family_10_fuzz"]["path"],
                matrix["design_guide_smoothness_completion"]["path"],
            ],
            "notes": "Critical app slices are green. Full exit gate remains unproven for every page/workflow in the goal file.",
        },
    }

    locked_evidence_checks = {
        "latest_family_10_fuzz_live_pass": _is_pass(family)
        and int(family_summary.get("families_live_passed") or 0) >= 9
        and int(family_summary.get("scenario_trigger_passes") or 0) >= 90,
        "critical_workflows_pass": _is_pass(matrix["critical_workflows_lock"]["payload"]),
        "critical_workflows_all_configured_10x": bool(workflow_summary["all_workflows_10x_passed"]),
        "inputs_apply_10x_pass": _is_pass(matrix["inputs_apply_10x_lock"]["payload"])
        and int(apply_summary.get("passed_iterations") or 0) >= 10
        and int(apply_summary.get("duplicate_action_count") or 0) == 0,
        "solver_state_handoff_pass": _is_pass(matrix["solver_state_handoff"]["payload"]),
        "post_apply_smoothness_pass": _is_pass(matrix["post_apply_smoothness_lock"]["payload"]),
        "design_guide_smoothness_completion_pass": _is_pass(matrix["design_guide_smoothness_completion"]["payload"]),
        "render_bridge_lock_pass": _is_pass(matrix["render_bridge_lock"]["payload"]),
        "independence_lock_pass": _is_pass(matrix["independence_lock"]["payload"]),
    }

    missing_or_weak = [key for key, row in phase_checks.items() if row["status"] == "MISSING_OR_WEAK"]
    partial = [key for key, row in phase_checks.items() if row["status"] == "PARTIAL"]
    failed_locks = [key for key, value in locked_evidence_checks.items() if not value]

    completion_status = "COMPLETE" if not missing_or_weak and not partial and not failed_locks else "LOCKED_PARTIAL"
    safe_to_resume_extraction = completion_status == "COMPLETE"
    safe_to_begin_legacy_deletion = completion_status == "COMPLETE"

    return {
        "schema": "app_stability_goal_completion_audit.v1",
        "status": "PASS",
        "completion_status": completion_status,
        "timestamp": _stamp(),
        "product_behaviour_changed": False,
        "locked_evidence_checks": locked_evidence_checks,
        "phase_checks": phase_checks,
        "workflow_summary": workflow_summary,
        "missing_or_weak_phases": missing_or_weak,
        "partial_phases": partial,
        "failed_locks": failed_locks,
        "safe_to_resume_extraction": safe_to_resume_extraction,
        "safe_to_begin_legacy_deletion": safe_to_begin_legacy_deletion,
        "recommended_next_slice": (
            "Refresh shared component/state ownership and add 10-repeat workflow coverage for reinforcement edits, "
            "explicit run-calculation workflows, Design Guide expand/collapse, calculation-panel expand/collapse, "
            "and any non-Inputs page interactions that are still outside the configured critical workflow lock."
            if completion_status != "COMPLETE"
            else "Stability goal is complete from current evidence."
        ),
        "artifacts": {key: {"path": row["path"], "status": row["status"]} for key, row in matrix.items()},
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# App Stability Goal Completion Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Completion status: `{payload['completion_status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"Safe to resume extraction: `{payload['safe_to_resume_extraction']}`",
        f"Safe to begin legacy deletion: `{payload['safe_to_begin_legacy_deletion']}`",
        "",
        "## Locked Evidence Checks",
        "",
    ]
    for key, value in dict(payload["locked_evidence_checks"]).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Phase Checks", ""])
    for key, row in dict(payload["phase_checks"]).items():
        lines.append(f"### `{key}`")
        lines.append(f"- status: `{row.get('status')}`")
        lines.append(f"- evidence: `{row.get('evidence')}`")
        lines.append(f"- notes: {row.get('notes')}")
        lines.append("")
    lines.extend(
        [
            "## Remaining Gaps",
            "",
            f"- missing_or_weak_phases: `{payload['missing_or_weak_phases']}`",
            f"- partial_phases: `{payload['partial_phases']}`",
            f"- failed_locks: `{payload['failed_locks']}`",
            "",
            "## Recommended Next Slice",
            "",
            str(payload["recommended_next_slice"]),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build()
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"app_stability_goal_completion_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"app_stability_goal_completion_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(f"app_stability_goal_completion_audit {payload['status']}")
    print(f"completion_status={payload['completion_status']}")
    print(f"safe_to_resume_extraction={payload['safe_to_resume_extraction']}")
    print(f"safe_to_begin_legacy_deletion={payload['safe_to_begin_legacy_deletion']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
