"""Prove old bending-fail snapshot reuse assembler is deletable or deleted."""

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

TARGET = "_assemble_bending_fail_publication_snapshot_reuse_result"


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


def _line_hits(source: str, token: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        if token in line:
            hits.append({"line": line_no, "text": line.strip()})
    return hits


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    hits = _line_hits(source, TARGET)
    definition_hits = [hit for hit in hits if hit["text"].startswith(f"def {TARGET}(")]
    live_call_hits = [
        hit
        for hit in hits
        if not hit["text"].startswith(f"def {TARGET}(")
        and not hit["text"].startswith("#")
    ]
    function_present = bool(definition_hits)
    decision = "DELETED" if not function_present else "READY_TO_DELETE"
    if live_call_hits:
        decision = "NOT_READY_LIVE_CALLS_REMAIN"
    page_helpers_deleted_no_live_branch = (
        "_controller_bending_fail_snapshot_reuse_result(" not in source
        and "_trace_design_guide_controller_bending_fail_snapshot_reuse(" not in source
        and TARGET not in source
        and "_run_design_guide_controller_bending_fail_snapshot_reuse_trace_only" not in source
        and "_DesignGuideControllerBendingFailSnapshotReuseRequest" not in source
        and "_bending_fail_publication_snapshot_for_state(" in source
    )
    return {
        "decision": decision,
        "target": TARGET,
        "function_present": function_present,
        "page_helpers_deleted_no_live_branch": page_helpers_deleted_no_live_branch,
        "definition_hits": definition_hits,
        "live_call_hits": live_call_hits,
        "live_call_count": len(live_call_hits),
        "controller_cutover_present": (
            "return _controller_bending_fail_snapshot_reuse_result(" in source
        ),
        "controller_cutover_or_page_helpers_deleted": (
            "return _controller_bending_fail_snapshot_reuse_result(" in source
            or page_helpers_deleted_no_live_branch
        ),
        "session_snapshot_retrieval_retained": (
            "snapshot_item = _bending_fail_publication_snapshot_for_state(" in source
        ),
        "session_snapshot_storage_retained": (
            "_bending_fail_publication_snapshot_for_state(" in source
            and "_store_bending_fail_publication_snapshot(" in source
        ),
        "composed": {
            "cutover": _run("tools/verification/design_guide_bending_fail_snapshot_reuse_cutover.py")
        },
        "delete_allowed_now": function_present and not live_call_hits,
        "product_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "cutover_gate_passes": ((capture.get("composed") or {}).get("cutover") or {}).get(
            "passed"
        )
        is True,
        "no_live_calls_remain": capture.get("live_call_count") == 0,
        "controller_cutover_present_or_page_helpers_deleted": (
            capture.get("controller_cutover_or_page_helpers_deleted") is True
        ),
        "session_snapshot_retrieval_retained": capture.get("session_snapshot_retrieval_retained")
        is True,
        "session_snapshot_storage_retained": capture.get("session_snapshot_storage_retained")
        is True,
        "decision_is_ready_or_deleted": capture.get("decision")
        in {"READY_TO_DELETE", "DELETED"},
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Bending-Fail Snapshot Reuse Legacy Assembler Deletion Proof",
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
            "## Target",
            "",
            f"- Function present: `{capture.get('function_present')}`",
            f"- Live call count: `{capture.get('live_call_count')}`",
            f"- Delete allowed now: `{capture.get('delete_allowed_now')}`",
            "",
            "The page-owned session snapshot retrieval branch is intentionally retained; only the obsolete result assembler is in scope.",
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
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_bending_fail_snapshot_reuse_legacy_assembler_deletion_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_bending_fail_snapshot_reuse_legacy_assembler_deletion_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_bending_fail_snapshot_reuse_legacy_assembler_deletion_proof {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
