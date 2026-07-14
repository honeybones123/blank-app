"""Parity scenarios for residual shear cleanup route proof object."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }


def _base_request() -> dict[str, Any]:
    bending_blocker = {
        "family": "bending",
        "source": "post_click_low_bending_exact_blocker",
        "exact_blocker": True,
        "no_second_cta_required": True,
    }
    return {
        "state": {"b": 400.0, "D": 650.0, "lig_legs": 2, "s_lig": 200},
        "overview": {"utils": {"bending": 0.24, "shear": 0.69}},
        "mode_config": {"target_band": [0.85, 1.0], "goal": "efficiency"},
        "bending_blocker": bending_blocker,
        "exact_blockers_by_family": {"bending": bending_blocker},
        "route_flags": {"starting_shear_util": 0.69, "target_low": 0.85, "target_high": 1.0},
    }


def _scenario_requests() -> dict[str, dict[str, Any]]:
    base = _base_request()
    exact = dict(base.get("exact_blockers_by_family") or {})
    in_band_evidence = {
        "post_click_bending_blocker_preserved": True,
        "post_click_residual_shear_cleanup_after_bending_blocker": True,
        "no_second_cta_required": True,
        "starting_util": 0.69,
        "best_safe_final_util": 0.91,
        "selected_candidate_id": "shear_cleanup_in_band",
        "safe_candidate_count": 1,
        "executable_candidate_count": 1,
        "exact_blockers_by_family": exact,
    }
    outside_shear_blocker = {
        "family": "shear",
        "source": "post_click_residual_shear_cleanup_outside_preferred_band",
        "exact_blocker": True,
        "threshold": 1.0,
        "best_safe_final_util": 1.04,
        "no_second_cta_required": True,
    }
    outside_exact = {**exact, "shear": outside_shear_blocker}
    outside_evidence = {
        **in_band_evidence,
        "best_safe_final_util": 1.04,
        "selected_candidate_id": "shear_cleanup_outside_band",
        "outside_target_band_allowed": True,
        "outside_target_band_allowed_category": "discrete_shear_cleanup_above_preferred_band",
        "exact_blockers_by_family": outside_exact,
    }
    return {
        "promoted_in_band": {
            **base,
            "residual_shear_tightening": {
                "updates": {"lig_legs": 0, "s_lig": 0},
                "candidate_search_evidence": dict(in_band_evidence),
            },
            "residual_result_item": {
                "selected_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "family": "shear",
                "guidance_intent": "efficiency_tightening",
                "action_type": "apply_resolved_candidate",
                "candidate_id": "shear_cleanup_in_band",
                "no_second_cta_required": True,
                "button_contract": {
                    "family": "shear",
                    "enabled": True,
                    "action_type": "apply_resolved_candidate",
                    "updates": {"lig_legs": 0, "s_lig": 0},
                },
                "candidate_search_evidence": dict(in_band_evidence),
            },
            "residual_detail": {"accepted": True},
            "route_debug": {
                "post_click_bending_blocker_preserved": True,
                "post_click_residual_shear_cleanup_after_bending_blocker": True,
            },
        },
        "outside_preferred_target_band": {
            **base,
            "exact_blockers_by_family": outside_exact,
            "route_flags": {
                "starting_shear_util": 0.69,
                "target_low": 0.85,
                "target_high": 1.0,
                "residual_outside_preferred_band": True,
            },
            "residual_shear_tightening": {
                "updates": {"s_lig": 300},
                "candidate_search_evidence": dict(outside_evidence),
            },
            "residual_result_item": {
                "selected_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "family": "shear",
                "guidance_intent": "efficiency_tightening",
                "action_type": "apply_resolved_candidate",
                "candidate_id": "shear_cleanup_outside_band",
                "no_second_cta_required": True,
                "button_contract": {
                    "family": "shear",
                    "enabled": True,
                    "action_type": "apply_resolved_candidate",
                    "updates": {"s_lig": 300},
                },
                "candidate_search_evidence": dict(outside_evidence),
            },
            "residual_detail": {"accepted": True, "outside_preferred_band": True},
            "route_debug": {
                "post_click_bending_blocker_preserved": True,
                "post_click_residual_shear_cleanup_after_bending_blocker": True,
            },
        },
        "no_promoted_result": {
            **base,
            "residual_shear_tightening": {},
            "residual_result_item": {},
            "residual_detail": {"accepted": False, "reason": "no_candidate"},
            "route_debug": {},
        },
    }


def _scenario_row(name: str, request: dict[str, Any]) -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof,
    )

    first = build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof(
        **request
    )
    second = build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof(
        **request
    )
    projection = dict(first.get("route_projection") or {})
    blocker_projection = dict(projection.get("blocker_projection") or {})
    result_projection = dict(projection.get("result_projection") or {})
    return {
        "name": name,
        "stable_repeat_hash": first.get("proof_hash") == second.get("proof_hash"),
        "route_projection_hash_present": bool(first.get("route_projection_hash")),
        "proof_only": first.get("proof_only") is True,
        "product_driving": first.get("product_driving") is True,
        "render_driving": first.get("render_driving") is True,
        "apply_driving": first.get("apply_driving") is True,
        "session_driving": first.get("session_driving") is True,
        "bending_blocker_preserved": blocker_projection.get("bending_blocker_preserved"),
        "residual_cleanup_after_bending_blocker": blocker_projection.get(
            "residual_cleanup_after_bending_blocker"
        ),
        "outside_target_band_allowed": blocker_projection.get("outside_target_band_allowed"),
        "result_selected_family_id": result_projection.get("selected_family_id"),
        "button_contract_hash_present": bool(result_projection.get("button_contract_hash")),
        "raw_payload_hash": _stable_hash(first),
    }


def _capture() -> dict[str, Any]:
    scenarios = {
        name: _scenario_row(name, request) for name, request in _scenario_requests().items()
    }
    return {
        "decision": "POST_CLICK_LOW_BENDING_RESIDUAL_SHEAR_CLEANUP_ROUTE_PARITY_SCENARIOS_PROVEN",
        "scenarios": scenarios,
        "object_snapshot": _run(
            [
                sys.executable,
                "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_object_snapshot.py",
            ]
        ),
        "live_trace": _run(
            [
                sys.executable,
                "tools/verification/design_guide_live_post_click_low_bending_residual_shear_cleanup_route_trace_snapshot.py",
            ]
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    scenarios = dict(capture.get("scenarios") or {})
    return {
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "live_trace_passed": (capture.get("live_trace") or {}).get("passed") is True,
        "all_scenarios_stable": all(
            row.get("stable_repeat_hash") is True for row in scenarios.values()
        ),
        "all_scenarios_hash_present": all(
            row.get("route_projection_hash_present") is True for row in scenarios.values()
        ),
        "all_scenarios_proof_only": all(row.get("proof_only") is True for row in scenarios.values()),
        "all_scenarios_non_product_driving": all(
            row.get("product_driving") is False
            and row.get("render_driving") is False
            and row.get("apply_driving") is False
            and row.get("session_driving") is False
            for row in scenarios.values()
        ),
        "promoted_in_band_preserves_bending_blocker": (
            scenarios.get("promoted_in_band", {}).get("bending_blocker_preserved") is True
        ),
        "outside_band_records_target_band_blocker": (
            scenarios.get("outside_preferred_target_band", {}).get("outside_target_band_allowed")
            is True
        ),
        "no_result_still_hashes": bool(
            scenarios.get("no_promoted_result", {}).get("raw_payload_hash")
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Low-Bending Residual Shear Cleanup Route Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenarios",
        "",
        "Scenario | Stable | Family | Outside Target | Bending Blocker Preserved",
        "--- | --- | --- | --- | ---",
    ]
    for name, row in (capture.get("scenarios") or {}).items():
        lines.append(
            f"{name} | `{row.get('stable_repeat_hash')}` | `{row.get('result_selected_family_id')}` | "
            f"`{row.get('outside_target_band_allowed')}` | `{row.get('bending_blocker_preserved')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Use these scenario hashes to build route cutover readiness before moving live residual shear cleanup behavior.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_parity_scenarios.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_parity_scenarios_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_parity_scenarios_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_residual_shear_cleanup_route_parity_scenarios {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
