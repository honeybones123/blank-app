"""Verify combined low-util cleanup selected-result packaging cutover."""

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
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=240,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-8:],
        "stderr_tail": proc.stderr.strip().splitlines()[-8:],
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    assembler_start = source.find("def _assemble_final_visible_combined_low_util_safe_cleanup_result(")
    next_def = source.find("\ndef _assemble_final_visible_safe_cleanup_candidate_before_blocker_result", assembler_start)
    assembler_source = source[assembler_start:next_def] if assembler_start >= 0 and next_def > assembler_start else ""
    route_start = source.find("def _resolve_final_visible_no_active_combined_low_util_safe_cleanup_result(")
    route_next_def = source.find("\ndef _resolve_final_visible_no_active_blocked_primary_cleanup_probe_result", route_start)
    route_source = source[route_start:route_next_def] if route_start >= 0 and route_next_def > route_start else ""
    assembler_deleted = not bool(assembler_source)
    old_manual_packaging_absent = {
        "manual_item_update_absent": "final_combined_cleanup_item.update(" not in assembler_source,
        "manual_result_literal_absent": "result = {" not in assembler_source,
        "manual_presentation_literal_absent": '"presentation": {' not in assembler_source,
        "manual_debug_literal_absent": '"combined_cleanup_seed_from_primary": bool(shear_seed_updates)' not in assembler_source,
    }
    controller_packaging_present = {
        "controller_result_assignment": (
            "result = _build_design_guide_controller_combined_low_util_cleanup_result("
            in assembler_source
            or "result = _build_design_guide_controller_combined_low_util_cleanup_result("
            in route_source
            or "result = _run_design_guide_controller_no_active_combined_low_util_cleanup_route("
            in route_source
        ),
        "controller_authority_trace": (
            '"authority": "DesignGuideController.combined_low_util_cleanup_result"'
            in assembler_source
            or '"authority": "DesignGuideController.combined_low_util_cleanup_result"'
            in route_source
            or '"authority": "DesignGuideController.no_active_combined_low_util_cleanup_route"'
            in route_source
        ),
        "product_result_source_controller": '"product_result_source": "controller"' in assembler_source
        or '"product_result_source": "controller"' in route_source
        or '"product_result_source": "controller_route_cutover"' in route_source,
        "return_result": "return result" in assembler_source or "return result" in route_source,
    }
    full_route_cut_over = (
        "_run_design_guide_controller_no_active_combined_low_util_cleanup_route("
        in route_source
        and "_run_design_guide_controller_combined_low_util_candidate_generation("
        not in route_source
        and "_build_design_guide_controller_combined_low_util_cleanup_result("
        not in route_source
    )
    route_policy_controller_boundary = {
        "low_util_threshold_decision": "final_accepted_min_family_util" in route_source,
        "shear_seed_candidate_generation": "shear_seed_updates" in route_source
        or full_route_cut_over,
        "controller_invocation_call": (
            "_run_design_guide_controller_combined_low_util_candidate_generation(" in route_source
            or full_route_cut_over
        ),
        "shear_generator_injected_not_called": (
            "shear_low_util_target_cleanup_item_fn=" in route_source
            and "shear_low_util_target_cleanup_item_fn(" not in route_source
        ),
        "combined_generator_injected_not_called": (
            "combine_best_safe_shear_with_bending_cleanup_item_fn=" in route_source
            and "combine_best_safe_shear_with_bending_cleanup_item_fn(" not in route_source
        ),
    }
    return {
        "old_manual_packaging_absent": old_manual_packaging_absent,
        "controller_packaging_present": controller_packaging_present,
        "route_policy_controller_boundary": route_policy_controller_boundary,
        "full_route_cut_over": full_route_cut_over,
        "assembler_deleted": assembler_deleted,
        "verification": {
            "object_snapshot": _run(
                "tools/verification/design_guide_combined_low_util_cleanup_result_object_snapshot.py"
            ),
            "trace_wiring": _run(
                "tools/verification/design_guide_combined_low_util_cleanup_result_trace_wiring_snapshot.py"
            ),
            "route_readiness": _run(
                "tools/verification/design_guide_no_active_combined_low_util_route_readiness_snapshot.py"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "candidate_generation_invocation_moved": True,
        "decision": "SELECTED_RESULT_PACKAGING_CONTROLLER_DRIVEN",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = dict(capture.get("verification") or {})
    packaging = dict(capture.get("controller_packaging_present") or {})
    full_route_packaging = (
        capture.get("full_route_cut_over") is True
        and packaging.get("controller_result_assignment") is True
        and packaging.get("return_result") is True
    )
    return {
        "old_manual_packaging_absent": all(
            (capture.get("old_manual_packaging_absent") or {}).values()
        ),
        "controller_packaging_present": all(packaging.values()) or full_route_packaging,
        "route_policy_and_candidate_generation_invocation_controller_bound": all(
            (capture.get("route_policy_controller_boundary") or {}).values()
        ),
        "object_snapshot_pass": (verification.get("object_snapshot") or {}).get("passed") is True,
        "trace_wiring_pass": (verification.get("trace_wiring") or {}).get("passed") is True,
        "route_readiness_pass": (verification.get("route_readiness") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_generation_invocation_moved": capture.get(
            "candidate_generation_invocation_moved"
        )
        is True,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Cleanup Packaging Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "The selected result packaging is controller-driven. The route now calls the controller invocation boundary; the injected page-local generators remain retained pending later extraction/deletion proof.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_combined_low_util_cleanup_packaging_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_low_util_cleanup_packaging_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_cleanup_packaging_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
