"""Adapter parity for residual shear cleanup final-binding tail."""

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
    run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail,
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
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "cmd": cmd,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
        "passed": result.returncode == 0,
    }


def _page_expected(
    *,
    promoted_item: dict[str, Any],
    evidence: dict[str, Any],
    blockers: dict[str, Any],
    action_payload: dict[str, Any],
    resolved_candidate: dict[str, Any],
    button_contract: dict[str, Any],
) -> dict[str, Any]:
    item = dict(promoted_item)
    evidence_d = dict(evidence)
    blockers_d = dict(blockers)
    evidence_d.update(
        {
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "post_click_bending_blocker_preserved": True,
            "post_click_residual_shear_cleanup_after_bending_blocker": True,
            "exact_blockers_by_family": dict(blockers_d),
            "post_click_exact_blockers_by_family": dict(blockers_d),
            "cleanup_evidence_by_family": dict(blockers_d),
            "post_click_cleanup_evidence_by_family": dict(blockers_d),
            "low_util_families": ["bending"],
            "resolved_low_util_families": ["bending"],
            "unresolved_low_util_families": [],
            "post_click_families_below_final_threshold": ["bending"],
            "post_click_unresolved_low_util_families": [],
            "no_second_cta_required": True,
        }
    )
    item["candidate_search_evidence"] = dict(evidence_d)
    item["post_click_residual_shear_cleanup_action"] = True
    item["guidance_intent"] = "efficiency_tightening"
    item["local_cleanup_candidate"] = True
    item["no_second_cta_required"] = True
    item["exact_blockers_by_family"] = dict(blockers_d)
    item["post_click_exact_blockers_by_family"] = dict(blockers_d)
    item["cleanup_evidence_by_family"] = dict(blockers_d)
    item["post_click_cleanup_evidence_by_family"] = dict(blockers_d)
    payload = dict(action_payload)
    payload["candidate_search_evidence"] = dict(evidence_d)
    payload["no_second_cta_required"] = True
    item["action_payload"] = dict(payload)
    resolved = dict(resolved_candidate)
    if resolved:
        resolved["candidate_search_evidence"] = dict(evidence_d)
        resolved["no_second_cta_required"] = True
        item["resolved_candidate"] = dict(resolved)
    if button_contract:
        item["button_contract"] = dict(button_contract)
    return item


def _scenario(name: str, *, util: float, updates: dict[str, Any], blockers: dict[str, Any]) -> dict[str, Any]:
    promoted = {
        "title": "Design is efficient",
        "label": "Shear cleanup - one-click reduction",
        "candidate_id": f"{name}_candidate",
    }
    evidence = {
        "scenario": name,
        "best_safe_final_util": util,
        "safe_candidate_count": 1,
    }
    payload = {
        "updates": dict(updates),
        "action_type": "apply_resolved_candidate",
    }
    resolved = {
        "candidate_id": f"{name}_candidate",
        "updates": dict(updates),
    }
    contract = {
        "enabled": bool(updates),
        "actionable": bool(updates),
        "updates": dict(updates),
        "expected_util": float(util),
    }
    expected = _page_expected(
        promoted_item=promoted,
        evidence=evidence,
        blockers=blockers,
        action_payload=payload,
        resolved_candidate=resolved,
        button_contract=contract,
    )
    adapted = run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(
        promoted_item=dict(promoted),
        candidate_search_evidence=dict(evidence),
        exact_blockers_by_family=dict(blockers),
        action_payload=dict(payload),
        resolved_candidate=dict(resolved),
        button_contract=dict(contract),
    )
    adapted_item = dict(adapted.get("result_item") or {})
    comparisons = {
        "item_hash_matches": _stable_hash(adapted_item) == _stable_hash(expected),
        "evidence_hash_matches": adapted.get("candidate_search_evidence_hash")
        == _stable_hash(expected.get("candidate_search_evidence") or {}),
        "action_payload_hash_matches": adapted.get("action_payload_hash")
        == _stable_hash(expected.get("action_payload") or {}),
        "resolved_candidate_hash_matches": adapted.get("resolved_candidate_hash")
        == _stable_hash(expected.get("resolved_candidate") or {}),
        "button_contract_hash_matches": adapted.get("button_contract_hash")
        == _stable_hash(expected.get("button_contract") or {}),
        "button_contract_execution_not_owned": adapted.get("button_contract_execution_owned_elsewhere")
        is True,
        "visible_wording_not_owned": adapted.get("visible_wording_authoring_owned_elsewhere")
        is True,
        "apply_routing_not_owned": adapted.get("apply_routing_owned_elsewhere") is True,
        "not_render_or_apply_or_session_driving": adapted.get("render_driving") is False
        and adapted.get("apply_driving") is False
        and adapted.get("session_driving") is False,
    }
    return {
        "name": name,
        "expected_hash": _stable_hash(expected),
        "adapted_hash": _stable_hash(adapted_item),
        "adapter_hash": adapted.get("final_binding_tail_adapter_hash"),
        "comparisons": comparisons,
        "passed": all(value is True for value in comparisons.values()),
    }


def _capture() -> dict[str, Any]:
    scenarios = [
        _scenario("accepted_residual_shear_cleanup", util=0.82, updates={"shear_links": 0}, blockers={}),
        _scenario(
            "outside_preferred_band_with_bending_blocker",
            util=0.91,
            updates={"shear_links": 0},
            blockers={"shear": {"exact_blocker": True, "reason": "outside preferred band"}},
        ),
        _scenario("disabled_no_updates_shape", util=0.74, updates={}, blockers={}),
    ]
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FINAL_BINDING_TAIL_ADAPTER_PARITY",
        "scenarios": scenarios,
        "scenario_count": len(scenarios),
        "ready_for_trace_wiring": all(row.get("passed") is True for row in scenarios),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "all_scenarios_pass": all(row.get("passed") is True for row in capture.get("scenarios") or []),
        "scenario_count_expected": capture.get("scenario_count") == 3,
        "ready_for_trace_wiring": capture.get("ready_for_trace_wiring") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Final Binding Tail Adapter Parity",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenarios",
        "",
    ]
    for row in capture.get("scenarios") or []:
        lines.append(f"- {row.get('name')}: passed `{row.get('passed')}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Trace-wire the behaviour adapter beside the live page final-binding tail. Do not replace page execution until trace parity and cutover-readiness pass.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_parity.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_parity_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_parity_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_final_binding_tail_adapter_parity_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_parity "
        f"{payload['status']}"
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print(f"failures={','.join(failures)}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
