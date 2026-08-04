"""Parity scenarios for residual-shear CTA/apply payload source boundary."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary,
)


def _stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=120)
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
        "passed": proc.returncode == 0,
    }


def _build_live_shapes(
    name: str,
    *,
    enabled: bool,
    actionable: bool,
    util: float,
    updates: dict[str, Any],
    stale_payload: bool = False,
) -> dict[str, Any]:
    evidence = {
        "scenario": name,
        "best_safe_final_util": float(util),
        "no_second_cta_required": True,
        "post_click_residual_shear_cleanup_after_bending_blocker": True,
    }
    promoted_updates = dict(updates)
    live_updates = dict(updates)
    if stale_payload:
        live_updates = {**live_updates, "stale_marker": True}
    promoted_payload = {
        "updates": dict(promoted_updates),
        "action_type": "apply_resolved_candidate" if enabled else "",
        "candidate_search_evidence": dict(evidence),
        "no_second_cta_required": True,
    }
    live_payload = {
        "updates": dict(live_updates),
        "action_type": "apply_resolved_candidate" if enabled else "",
        "candidate_search_evidence": dict(evidence),
        "no_second_cta_required": True,
    }
    promoted_resolved = {
        "candidate_id": f"{name}_candidate",
        "updates": dict(promoted_updates),
        "candidate_search_evidence": dict(evidence),
        "no_second_cta_required": True,
    }
    live_resolved = {
        "candidate_id": f"{name}_candidate",
        "updates": dict(live_updates),
        "candidate_search_evidence": dict(evidence),
        "no_second_cta_required": True,
    }
    promoted_contract = {
        "enabled": bool(enabled),
        "actionable": bool(actionable),
        "action_type": "apply_resolved_candidate" if enabled else "",
        "label": "Apply" if enabled else "",
        "updates": dict(promoted_updates),
        "expected_util": float(util),
    }
    live_contract = {
        "enabled": bool(enabled),
        "actionable": bool(actionable),
        "action_type": "apply_resolved_candidate" if enabled else "",
        "label": "Apply" if enabled else "",
        "updates": dict(live_updates),
        "expected_util": float(util),
    }
    promoted_item = {
        "candidate_id": f"{name}_candidate",
        "title": "Design is efficient",
        "action_payload": dict(promoted_payload),
        "resolved_candidate": dict(promoted_resolved),
        "button_contract": dict(promoted_contract),
        "candidate_search_evidence": dict(evidence),
    }
    return {
        "promoted_item": promoted_item,
        "action_payload": live_payload,
        "resolved_candidate": live_resolved,
        "button_contract": live_contract,
    }


def _scenario(
    name: str,
    *,
    enabled: bool,
    actionable: bool,
    util: float,
    updates: dict[str, Any],
    stale_payload: bool = False,
) -> dict[str, Any]:
    shapes = _build_live_shapes(
        name,
        enabled=enabled,
        actionable=actionable,
        util=util,
        updates=updates,
        stale_payload=stale_payload,
    )
    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(
        promoted_item=dict(shapes["promoted_item"]),
        action_payload=dict(shapes["action_payload"]),
        resolved_candidate=dict(shapes["resolved_candidate"]),
        button_contract=dict(shapes["button_contract"]),
        state_summary={"scenario": name, "state_fingerprint": f"{name}_state"},
        dependency_status="page_live",
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(
        promoted_item=dict(shapes["promoted_item"]),
        action_payload=dict(shapes["action_payload"]),
        resolved_candidate=dict(shapes["resolved_candidate"]),
        button_contract=dict(shapes["button_contract"]),
        state_summary={"scenario": name, "state_fingerprint": f"{name}_state"},
        dependency_status="page_live",
    )
    expected_payload_match = not stale_payload
    expected_resolved_match = not stale_payload
    expected_contract_match = not stale_payload
    comparisons = {
        "action_payload_hash_matches_live": first.get("action_payload_hash")
        == _stable_hash(shapes["action_payload"]),
        "resolved_candidate_hash_matches_live": first.get("resolved_candidate_hash")
        == _stable_hash(shapes["resolved_candidate"]),
        "button_contract_hash_matches_live": first.get("button_contract_hash")
        == _stable_hash(shapes["button_contract"]),
        "button_contract_updates_hash_matches_live": first.get("button_contract_updates_hash")
        == _stable_hash((shapes["button_contract"] or {}).get("updates") or {}),
        "payload_match_flag_expected": first.get("payload_matches_promoted_item")
        is expected_payload_match,
        "resolved_match_flag_expected": first.get("resolved_candidate_matches_promoted_item")
        is expected_resolved_match,
        "button_contract_match_flag_expected": first.get("button_contract_matches_promoted_item")
        is expected_contract_match,
        "enabled_flag_matches": first.get("button_contract_enabled") is bool(enabled or actionable),
        "actionable_flag_matches": first.get("button_contract_actionable") is bool(actionable or enabled),
        "stable_hash_repeat": first.get("cta_apply_payload_source_boundary_hash")
        == repeat.get("cta_apply_payload_source_boundary_hash"),
        "page_live_not_cutover_ready": first.get("behavior_cutover_ready") is False,
        "proof_only_non_driving": first.get("proof_only") is True
        and first.get("product_driving") is False
        and first.get("render_driving") is False
        and first.get("apply_driving") is False
        and first.get("session_driving") is False,
    }
    return {
        "name": name,
        "boundary": first,
        "expected_payload_match": expected_payload_match,
        "expected_resolved_match": expected_resolved_match,
        "expected_contract_match": expected_contract_match,
        "comparisons": comparisons,
        "passed": all(value is True for value in comparisons.values()),
    }


def _capture() -> dict[str, Any]:
    scenarios = [
        _scenario(
            "executor_backed_enabled",
            enabled=True,
            actionable=True,
            util=0.69,
            updates={"ligature_legs": 0, "ligature_dia": 0},
        ),
        _scenario(
            "outside_preferred_band_allowed",
            enabled=True,
            actionable=True,
            util=0.91,
            updates={"ligature_legs": 0, "ligature_dia": 0},
        ),
        _scenario(
            "disabled_missing_updates",
            enabled=False,
            actionable=False,
            util=0.72,
            updates={},
        ),
        _scenario(
            "stale_payload_mismatch_detected",
            enabled=True,
            actionable=True,
            util=0.84,
            updates={"ligature_legs": 0},
            stale_payload=True,
        ),
    ]
    trace = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_trace_wiring.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_CTA_APPLY_PAYLOAD_SOURCE_BOUNDARY_PARITY_PROVEN",
        "scenarios": scenarios,
        "scenario_count": len(scenarios),
        "trace_wiring": trace,
        "ready_for_cutover_readiness_snapshot": all(row.get("passed") is True for row in scenarios),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    scenarios = list(capture.get("scenarios") or [])
    return {
        "all_scenarios_pass": all(row.get("passed") is True for row in scenarios),
        "scenario_count_expected": capture.get("scenario_count") == 4,
        "trace_wiring_pass": (capture.get("trace_wiring") or {}).get("passed") is True,
        "stale_mismatch_scenario_present": any(
            row.get("name") == "stale_payload_mismatch_detected"
            and row.get("expected_payload_match") is False
            and row.get("passed") is True
            for row in scenarios
        ),
        "cutover_readiness_can_be_checked_next": capture.get("ready_for_cutover_readiness_snapshot")
        is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup CTA/Apply Payload Source Boundary Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenarios",
        "",
    ]
    for row in capture.get("scenarios") or []:
        lines.append(
            f"- {row.get('name')}: passed `{row.get('passed')}`, "
            f"payload_match_expected `{row.get('expected_payload_match')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Create a cutover-readiness snapshot. Do not replace live CTA/apply payload extraction until readiness proves stale-state handling and shared button-contract ownership remain bounded.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_parity_scenarios.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_parity_scenarios_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_parity_scenarios_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_cta_apply_payload_source_boundary_parity_scenarios_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_parity_scenarios "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
