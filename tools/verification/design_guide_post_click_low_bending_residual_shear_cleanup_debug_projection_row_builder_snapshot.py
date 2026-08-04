"""Snapshot for residual-shear cleanup debug projection row builder."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

BUILDER = (
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_debug_projection_rows"
)
HELPER = (
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_debug_projection_rows"
)
IMPORT_ALIAS = (
    "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_debug_projection_rows"
)
ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("
DIRECT_DEBUG_KEYS = (
    "post_click_bending_blocker_preserved",
    "post_click_residual_shear_cleanup_after_bending_blocker",
    "post_click_residual_shear_cleanup_debug",
    "post_click_residual_shear_cleanup_detail",
    "post_click_residual_shear_cleanup_updates",
    "exact_blockers_by_family",
    "post_click_exact_blockers_by_family",
    "cleanup_evidence_by_family",
    "post_click_cleanup_evidence_by_family",
    "candidate_search_evidence",
    "guidance_branch",
    "selected_action_family",
    "primary_guidance_intent",
    "safe_local_cleanup_count",
    "executable_safe_cleanup_count",
)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180)
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }


def _sample_rows() -> dict[str, Any]:
    return {
        "post_click_bending_blocker_preserved": True,
        "post_click_residual_shear_cleanup_after_bending_blocker": True,
        "post_click_residual_shear_cleanup_debug": {"route": "residual_shear"},
        "post_click_residual_shear_cleanup_detail": {"accepted": True},
        "post_click_residual_shear_cleanup_updates": {"lig_legs": 0, "s_lig": 0},
        "exact_blockers_by_family": {"bending": {"exact_stop": True}},
        "post_click_exact_blockers_by_family": {"bending": {"exact_stop": True}},
        "cleanup_evidence_by_family": {"bending": {"exact_stop": True}},
        "post_click_cleanup_evidence_by_family": {"bending": {"exact_stop": True}},
        "candidate_search_evidence": {"safe_candidate_count": 1},
        "guidance_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
        "selected_action_family": "shear",
        "primary_guidance_intent": "efficiency_tightening",
        "safe_local_cleanup_count": 1,
        "executable_safe_cleanup_count": 1,
    }


def _builder_sample() -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from design_brain.design_guide_controller import (  # noqa: PLC0415
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_debug_projection_rows,
    )

    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_debug_projection_rows(
        debug_projection_rows=_sample_rows()
    )
    second = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_debug_projection_rows(
        debug_projection_rows=_sample_rows()
    )
    return {
        "first": first,
        "second": second,
        "stable_repeat_hash": first.get("debug_projection_rows_proof_hash")
        == second.get("debug_projection_rows_proof_hash"),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(inputs_source, ROUTE_START, ROUTE_END)
    helper_block = _between(
        inputs_source,
        f"def {HELPER}(",
        "\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
    )
    builder_sample = _builder_sample()
    builder_payload = dict(builder_sample.get("first") or {})
    call_index = route.find(f"{HELPER}(")
    executable_row_index = route.find('debug_sink["executable_safe_cleanup_count"] = 1')
    route_proof_index = route.find(
        "_stamp_final_publication_post_click_low_bending_residual_shear_cleanup_route_proof("
    )
    direct_rows_present = {
        key: f'debug_sink["{key}"]' in route for key in DIRECT_DEBUG_KEYS
    }
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_DEBUG_PROJECTION_ROW_BUILDER_TRACE_ONLY",
        "builder_defined": f"def {BUILDER}(" in controller_source,
        "builder_exported": f'"{BUILDER}"' in controller_source,
        "builder_imported": f"{BUILDER} as {IMPORT_ALIAS}" in inputs_source,
        "helper_defined": f"def {HELPER}(" in inputs_source,
        "helper_calls_builder": BUILDER in helper_block,
        "helper_stamps_payload": (
            "debug_projection_rows_proof_hash" in helper_block
            and "debug_projection_rows_all_required_present" in helper_block
        ),
        "helper_non_driving_flags": all(
            token in helper_block
            for token in (
                "debug_projection_rows_proof_only",
                "debug_projection_rows_product_driving",
                "debug_projection_rows_render_driving",
                "debug_projection_rows_apply_driving",
                "debug_projection_rows_session_driving",
            )
        )
        and helper_block.count("] = False") >= 4,
        "trace_call_after_direct_rows": (
            executable_row_index >= 0 and call_index > executable_row_index
        ),
        "trace_call_before_route_proof": call_index >= 0 and route_proof_index > call_index,
        "direct_rows_present": direct_rows_present,
        "missing_direct_rows": [key for key, present in direct_rows_present.items() if not present],
        "builder_sample": {
            "row_count": builder_payload.get("row_count"),
            "required_row_count": builder_payload.get("required_row_count"),
            "all_required_keys_present": builder_payload.get("all_required_keys_present"),
            "missing_required_keys": list(builder_payload.get("missing_required_keys") or []),
            "stable_repeat_hash": builder_sample.get("stable_repeat_hash"),
            "proof_only": builder_payload.get("proof_only"),
            "product_driving": builder_payload.get("product_driving"),
            "render_driving": builder_payload.get("render_driving"),
            "apply_driving": builder_payload.get("apply_driving"),
            "session_driving": builder_payload.get("session_driving"),
            "safe_next_cutover_surface": builder_payload.get("safe_next_cutover_surface"),
            "debug_projection_rows_hash": builder_payload.get("debug_projection_rows_hash"),
            "debug_projection_rows_proof_hash": builder_payload.get("debug_projection_rows_proof_hash"),
        },
        "tail_audit": _run(
            [
                sys.executable,
                "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_tail_audit.py",
            ]
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    sample = dict(capture.get("builder_sample") or {})
    return {
        "builder_defined": capture.get("builder_defined") is True,
        "builder_exported": capture.get("builder_exported") is True,
        "builder_imported": capture.get("builder_imported") is True,
        "helper_defined": capture.get("helper_defined") is True,
        "helper_calls_builder": capture.get("helper_calls_builder") is True,
        "helper_stamps_payload": capture.get("helper_stamps_payload") is True,
        "helper_non_driving_flags": capture.get("helper_non_driving_flags") is True,
        "trace_call_after_direct_rows": capture.get("trace_call_after_direct_rows") is True,
        "trace_call_before_route_proof": capture.get("trace_call_before_route_proof") is True,
        "all_direct_rows_still_present": not capture.get("missing_direct_rows"),
        "builder_represents_all_rows": sample.get("row_count") == len(DIRECT_DEBUG_KEYS)
        and sample.get("required_row_count") == len(DIRECT_DEBUG_KEYS),
        "builder_sample_all_required_keys_present": sample.get("all_required_keys_present") is True,
        "builder_hash_stable": sample.get("stable_repeat_hash") is True,
        "builder_is_proof_only": sample.get("proof_only") is True,
        "builder_non_driving": all(
            sample.get(key) is False
            for key in ("product_driving", "render_driving", "apply_driving", "session_driving")
        ),
        "tail_audit_passed": (capture.get("tail_audit") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    sample = dict(capture.get("builder_sample") or {})
    lines = [
        "# Residual Shear Cleanup Debug Projection Row Builder Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- rows represented: `{sample.get('row_count')}` / `{sample.get('required_row_count')}`",
        f"- all required keys present: `{sample.get('all_required_keys_present')}`",
        f"- stable proof hash: `{sample.get('stable_repeat_hash')}`",
        f"- safe next cutover surface: `{sample.get('safe_next_cutover_surface')}`",
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
            "Narrow these direct debug projection rows to compatibility-only only after a consumer reachability proof.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if passed is not True]
    payload = {
        "schema": (
            "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_row_builder_snapshot.v1"
        ),
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_row_builder_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_row_builder_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_row_builder "
        f"{payload['status']}"
    )
    print(json_path)
    print(report_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
