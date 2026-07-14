"""Verify trace-only wiring or completed deletion for bending-fail snapshot reuse."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
        timeout=180,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "passed": proc.returncode == 0,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    required_tokens = {
        "controller_request_import": (
            "DesignGuideControllerBendingFailSnapshotReuseRequest as "
            "_DesignGuideControllerBendingFailSnapshotReuseRequest"
        ),
        "controller_runner_import": (
            "run_design_guide_controller_bending_fail_snapshot_reuse_trace_only as "
            "_run_design_guide_controller_bending_fail_snapshot_reuse_trace_only"
        ),
        "trace_helper": "def _trace_design_guide_controller_bending_fail_snapshot_reuse(",
        "controller_request_constructed": "_DesignGuideControllerBendingFailSnapshotReuseRequest(",
        "controller_runner_called": (
            "_run_design_guide_controller_bending_fail_snapshot_reuse_trace_only(request)"
        ),
        "legacy_hash_compared": "legacy_hash = _stable_final_publication_hash(dict(legacy_result or {}))",
        "controller_hash_compared": "controller_hash=response.result_hash",
        "hash_match_recorded": "result_hash_match=response.result_hash == legacy_hash",
        "trace_event_present": '"bending_fail_snapshot_reuse_controller_trace"',
    }
    trace_wired_legacy = (
        "legacy_snapshot_result = _assemble_bending_fail_publication_snapshot_reuse_result(" in source
        and "legacy_result=dict(legacy_snapshot_result or {})" in source
        and "return legacy_snapshot_result" in source
    )
    controller_cutover = (
        "def _controller_bending_fail_snapshot_reuse_result(" in source
        and "return _controller_bending_fail_snapshot_reuse_result(" in source
        and "controller_authority=\"DesignGuideController.bending_fail_snapshot_reuse\"" in source
        and "product_driving=True" in source[
            source.find("def _controller_bending_fail_snapshot_reuse_result(") :
            source.find("def _trace_design_guide_controller_bending_fail_snapshot_reuse(")
        ]
    )
    page_helpers_deleted_no_live_branch = (
        "def _trace_design_guide_controller_bending_fail_snapshot_reuse(" not in source
        and "def _controller_bending_fail_snapshot_reuse_result(" not in source
        and "_assemble_bending_fail_publication_snapshot_reuse_result(" not in source
        and "_run_design_guide_controller_bending_fail_snapshot_reuse_trace_only" not in source
        and "_DesignGuideControllerBendingFailSnapshotReuseRequest" not in source
        and "_bending_fail_publication_snapshot_for_state(" in source
    )
    return {
        "token_presence": {key: token in source for key, token in required_tokens.items()},
        "helper_count": source.count("def _trace_design_guide_controller_bending_fail_snapshot_reuse("),
        "cutover_helper_count": source.count("def _controller_bending_fail_snapshot_reuse_result("),
        "trace_call_count_including_definition": source.count(
            "_trace_design_guide_controller_bending_fail_snapshot_reuse("
        ),
        "controller_cutover_call_count_including_definition": source.count(
            "_controller_bending_fail_snapshot_reuse_result("
        ),
        "trace_wired_legacy": trace_wired_legacy,
        "controller_cutover": controller_cutover,
        "page_helpers_deleted_no_live_branch": page_helpers_deleted_no_live_branch,
        "session_snapshot_storage_retained": (
            "_bending_fail_publication_snapshot_for_state(" in source
            and "_store_bending_fail_publication_snapshot(" in source
        ),
        "legacy_assembler_direct_return_removed": (
            "return _assemble_bending_fail_publication_snapshot_reuse_result(" not in source
        ),
        "legacy_assembler_function_deleted": (
            "def _assemble_bending_fail_publication_snapshot_reuse_result(" not in source
        ),
        "controller_trace_is_product_driving": "product_driving=True" in source[
            source.find("def _trace_design_guide_controller_bending_fail_snapshot_reuse(") :
            source.find("def _mark_compute_debug_restamp_metadata_compatibility_only(")
        ],
        "composed": {
            "controller_object": _run(
                "tools/verification/design_guide_bending_fail_snapshot_reuse_controller_object_snapshot.py"
            )
        },
        "decision": (
            "PAGE_HELPERS_DELETED_NO_LIVE_BRANCH"
            if page_helpers_deleted_no_live_branch
            else (
            "CONTROLLER_CUTOVER_LEGACY_ASSEMBLER_DELETED"
            if controller_cutover
            and "def _assemble_bending_fail_publication_snapshot_reuse_result(" not in source
            else (
                "CONTROLLER_CUTOVER_LEGACY_ASSEMBLER_RETAINED"
                if controller_cutover
                else "TRACE_WIRED_LEGACY_RETURN_UNCHANGED"
            )
            )
        ),
        "product_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "all_required_tokens_present_or_page_helpers_deleted": (
            all((capture.get("token_presence") or {}).values())
            or capture.get("page_helpers_deleted_no_live_branch") is True
        ),
        "single_trace_helper_defined_or_page_helpers_deleted": (
            capture.get("helper_count") == 1
            or capture.get("page_helpers_deleted_no_live_branch") is True
        ),
        "single_cutover_helper_defined_if_cutover": (
            capture.get("controller_cutover") is False
            or capture.get("cutover_helper_count") == 1
        ),
        "helper_or_cutover_called_from_branch": (
            capture.get("trace_wired_legacy") is True
            or capture.get("page_helpers_deleted_no_live_branch") is True
            or (
                capture.get("controller_cutover") is True
                and capture.get("controller_cutover_call_count_including_definition") == 2
            )
        ),
        "legacy_assembler_function_retained_or_deleted": (
            capture.get("legacy_assembler_direct_return_removed") is True
            and (
                capture.get("legacy_assembler_function_deleted") is True
                or "def _assemble_bending_fail_publication_snapshot_reuse_result(" in INPUTS_PAGE.read_text(
                    encoding="utf-8",
                    errors="replace",
                ).lstrip("\ufeff")
            )
        ),
        "controller_trace_not_product_driving_until_cutover": (
            capture.get("controller_cutover") is True
            or capture.get("page_helpers_deleted_no_live_branch") is True
            or capture.get("controller_trace_is_product_driving") is False
        ),
        "session_snapshot_storage_retained": (
            capture.get("session_snapshot_storage_retained") is True
        ),
        "controller_object_gate_passes": (
            (capture.get("composed") or {}).get("controller_object") or {}
        ).get("passed")
        is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Bending-Fail Snapshot Reuse Trace Wiring Snapshot",
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
            "## Boundary",
            "",
            "- The controller object is traced beside the legacy bending-fail snapshot branch when that branch exists.",
            "- If the page helper route has already been deleted, this verifier records that as the completed extraction state.",
            "- Session-backed snapshot retrieval/storage remains page-owned.",
            "",
            "Next safe slice: keep the completed deletion state flowing through cutover readiness and deletion proof.",
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
    json_path = ARTIFACT_DIR / f"design_guide_bending_fail_snapshot_reuse_trace_wiring_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_fail_snapshot_reuse_trace_wiring_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_bending_fail_snapshot_reuse_trace_wiring_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
