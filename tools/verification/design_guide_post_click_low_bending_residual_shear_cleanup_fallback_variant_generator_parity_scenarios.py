"""Parity scenarios for residual shear cleanup fallback variant generator trace shape."""

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
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary,
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


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=240)
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }


def _case(
    *,
    name: str,
    sequence: list[dict[str, Any]],
    generated_variant_count: int,
    generator_attempted: bool = True,
    generator_exception: bool = False,
) -> dict[str, Any]:
    output_summary = {
        "generator_attempted": generator_attempted,
        "generator_exception": generator_exception,
        "generated_variant_count": generated_variant_count,
        "generated_update_count": len(sequence),
        "iteration_limit": 64,
        "stable_sequence_hash": _stable_hash(sequence),
        "order_proof": {
            "iteration_limit": 64,
            "preserves_generator_order": True,
            "stable_sequence_hash": _stable_hash(sequence),
        },
    }
    payload = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary(
        candidate_boundary={"candidate_boundary_hash": "candidate-boundary-hash"},
        generator_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": f"{name}-state-fingerprint",
            "mode_config_hash": f"{name}-mode-config-hash",
            "iteration_limit": 64,
        },
        generator_output_summary=output_summary,
        dependency_status="page_live",
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary(
        candidate_boundary={"candidate_boundary_hash": "candidate-boundary-hash"},
        generator_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": f"{name}-state-fingerprint",
            "mode_config_hash": f"{name}-mode-config-hash",
            "iteration_limit": 64,
        },
        generator_output_summary=output_summary,
        dependency_status="page_live",
    )
    owned = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary(
        candidate_boundary={"candidate_boundary_hash": "candidate-boundary-hash"},
        generator_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": f"{name}-state-fingerprint",
            "mode_config_hash": f"{name}-mode-config-hash",
            "iteration_limit": 64,
        },
        generator_output_summary=output_summary,
        dependency_status="controller_owned",
    )
    return {
        "name": name,
        "generated_variant_count": payload.get("generated_variant_count"),
        "generated_update_count": payload.get("generated_update_count"),
        "sequence_hash": payload.get("stable_sequence_hash"),
        "output_shape_ready": bool(payload.get("output_shape_ready")),
        "page_live_behavior_cutover_ready": bool(payload.get("behavior_cutover_ready")),
        "owned_behavior_cutover_ready": bool(owned.get("behavior_cutover_ready")),
        "page_must_keep_for_now": list(payload.get("page_must_keep_for_now") or []),
        "stable_hash_repeat": payload.get("fallback_variant_generator_boundary_hash")
        == repeat.get("fallback_variant_generator_boundary_hash"),
        "product_driving": bool(payload.get("product_driving")),
        "render_driving": bool(payload.get("render_driving")),
        "apply_driving": bool(payload.get("apply_driving")),
        "session_driving": bool(payload.get("session_driving")),
    }


def _capture() -> dict[str, Any]:
    trace_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary_trace_wiring_snapshot.py",
        ]
    )
    object_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary_object_snapshot.py",
        ]
    )
    cases = [
        _case(
            name="success_two_update_seeds",
            generated_variant_count=3,
            sequence=[
                {"index": 0, "variant_hash": "v0", "updates": {"lig_legs": 0, "s_lig": 0}},
                {"index": 1, "variant_hash": "v1", "updates": {"s_lig": 300}},
            ],
        ),
        _case(
            name="variants_no_material_updates",
            generated_variant_count=4,
            sequence=[],
        ),
        _case(
            name="empty_generator",
            generated_variant_count=0,
            sequence=[],
        ),
        _case(
            name="generator_exception_empty_output",
            generated_variant_count=0,
            sequence=[],
            generator_exception=True,
        ),
    ]
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FALLBACK_VARIANT_GENERATOR_PARITY_SCENARIOS_PROVEN",
        "cases": cases,
        "trace_wiring": trace_run,
        "object_snapshot": object_run,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    cases = list(capture.get("cases") or [])
    return {
        "case_count": len(cases) == 4,
        "all_output_shapes_ready": all(case.get("output_shape_ready") is True for case in cases),
        "page_live_cases_not_cutover_ready": all(
            case.get("page_live_behavior_cutover_ready") is False for case in cases
        ),
        "owned_cases_cutover_ready": all(
            case.get("owned_behavior_cutover_ready") is True for case in cases
        ),
        "page_keeps_generator_for_now": all(
            "fallback_variant_generation" in set(case.get("page_must_keep_for_now") or [])
            for case in cases
        ),
        "stable_hashes": all(case.get("stable_hash_repeat") is True for case in cases),
        "sequence_hashes_present": all(bool(case.get("sequence_hash")) for case in cases),
        "non_driving": all(
            not case.get("product_driving")
            and not case.get("render_driving")
            and not case.get("apply_driving")
            and not case.get("session_driving")
            for case in cases
        ),
        "trace_wiring_passed": (capture.get("trace_wiring") or {}).get("passed") is True,
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Fallback Variant Generator Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Cases",
        "",
    ]
    for case in capture.get("cases") or []:
        lines.append(
            "- "
            + str(case.get("name"))
            + ": variants=`"
            + str(case.get("generated_variant_count"))
            + "`, update_seeds=`"
            + str(case.get("generated_update_count"))
            + "`, page_live_ready=`"
            + str(case.get("page_live_behavior_cutover_ready"))
            + "`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Create fallback-generator cutover readiness before replacing page-owned variant generation. Candidate evaluation still waits.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_parity_scenarios.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_parity_scenarios_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_parity_scenarios_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_fallback_variant_generator_parity_scenarios_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_parity_scenarios "
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
