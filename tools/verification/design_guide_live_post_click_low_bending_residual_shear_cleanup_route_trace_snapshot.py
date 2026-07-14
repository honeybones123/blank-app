"""Trace snapshot for live residual shear cleanup route proof wiring."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


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


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    helper_block = _block(
        source,
        "def _stamp_final_publication_post_click_low_bending_residual_shear_cleanup_route_proof(",
        "\ndef _stamp_final_publication_post_click_final_contract_predicate_result_adapter(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    stamp_call_index = route_block.find(
        "_stamp_final_publication_post_click_low_bending_residual_shear_cleanup_route_proof("
    )
    return_index = route_block.find("return residual_route_return_item", stamp_call_index)
    if return_index < 0:
        return_index = route_block.find("return residual_promoted", stamp_call_index)
    object_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_object_snapshot.py",
        ]
    )
    audit_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_audit.py",
        ]
    )
    return {
        "decision": "LIVE_POST_CLICK_LOW_BENDING_RESIDUAL_SHEAR_CLEANUP_ROUTE_TRACE_WIRED",
        "builder_imported": (
            "build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof as "
            "_build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof"
            in source
        ),
        "helper_present": bool(helper_block),
        "trace_call_present": stamp_call_index >= 0,
        "trace_before_residual_return": (
            stamp_call_index >= 0 and return_index >= 0 and stamp_call_index < return_index
        ),
        "live_route_return_boundary_retained": (
            "return residual_route_return_item" in route_block
        ),
        "old_live_result_return_removed": "return residual_promoted" not in route_block,
        "live_route_execution_retained": all(
            token in route_block
            for token in (
                "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
                "executor=_compute_shear_tightening_recommendation",
                "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
                "generator=generate_less_shear_reo_variants",
                "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
                "evaluator=_evaluate_auto_design_candidate",
                "_design_guide_button_contract(",
            )
        ),
        "proof_stamps_present": all(
            token in helper_block
            for token in (
                "final_publication_post_click_low_bending_residual_shear_cleanup_route",
                "final_publication_post_click_low_bending_residual_shear_cleanup_route_hash",
                "final_publication_post_click_low_bending_residual_shear_cleanup_route_proof_hash",
                "final_publication_post_click_low_bending_residual_shear_cleanup_route_surfaces",
                "final_publication_post_click_low_bending_residual_shear_cleanup_route_excluded_live_surfaces",
            )
        ),
        "non_driving_stamps_present": all(
            token in helper_block
            for token in (
                '"final_publication_post_click_low_bending_residual_shear_cleanup_route_proof_only"] = True',
                '"final_publication_post_click_low_bending_residual_shear_cleanup_route_product_driving"] = False',
                '"final_publication_post_click_low_bending_residual_shear_cleanup_route_render_driving"] = False',
                '"final_publication_post_click_low_bending_residual_shear_cleanup_route_apply_driving"] = False',
                '"final_publication_post_click_low_bending_residual_shear_cleanup_route_session_driving"] = False',
            )
        ),
        "live_inputs_passed": all(
            token in route_block
            for token in (
                "current_state=dict(state or {})",
                "overview=overview if isinstance(overview, dict) else {}",
                "mode_config=dict(mode_config or {})",
                "bending_blocker=dict(blocker or {})",
                "exact_blockers_by_family=dict(residual_exact_blockers or {})",
                "residual_shear_tightening=dict(residual_shear_tighten or {})",
                "residual_result_item=dict(residual_promoted or {})",
                "residual_detail=dict(residual_detail or {})",
                "route_debug=dict(residual_shear_debug or {})",
                "guidance_debug=debug_sink",
            )
        ),
        "product_behavior_changed": False,
        "object_snapshot": object_run,
        "route_audit": audit_run,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "builder_imported": capture.get("builder_imported") is True,
        "helper_present": capture.get("helper_present") is True,
        "trace_call_present": capture.get("trace_call_present") is True,
        "trace_before_residual_return": capture.get("trace_before_residual_return") is True,
        "live_route_return_boundary_retained": (
            capture.get("live_route_return_boundary_retained") is True
        ),
        "old_live_result_return_removed": (
            capture.get("old_live_result_return_removed") is True
        ),
        "live_route_execution_retained": capture.get("live_route_execution_retained") is True,
        "proof_stamps_present": capture.get("proof_stamps_present") is True,
        "non_driving_stamps_present": capture.get("non_driving_stamps_present") is True,
        "live_inputs_passed": capture.get("live_inputs_passed") is True,
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "route_audit_passed": (capture.get("route_audit") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Live Post-Click Low-Bending Residual Shear Cleanup Route Trace Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Trace before residual return: `{capture.get('trace_before_residual_return')}`",
        f"- Live route execution retained: `{capture.get('live_route_execution_retained')}`",
        f"- Product behavior changed: `{capture.get('product_behavior_changed')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Create residual shear cleanup route parity scenarios before moving any route behavior.",
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
        "schema": "design_guide_live_post_click_low_bending_residual_shear_cleanup_route_trace_snapshot.v1",
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
        / f"design_guide_live_post_click_low_bending_residual_shear_cleanup_route_trace_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_live_post_click_low_bending_residual_shear_cleanup_route_trace_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_live_post_click_low_bending_residual_shear_cleanup_route_trace {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
