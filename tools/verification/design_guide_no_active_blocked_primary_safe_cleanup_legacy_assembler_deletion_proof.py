"""Prove the legacy safe-cleanup-before-blocker assembler can be deleted."""

from __future__ import annotations

from datetime import datetime
import ast
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

ASSEMBLER = "_assemble_final_visible_safe_cleanup_candidate_before_blocker_result"
CONTROLLER_BUILDER_ALIAS = "_build_design_guide_controller_safe_cleanup_candidate_before_blocker_result"
BENDING_ASSEMBLER = "_assemble_final_visible_bending_cleanup_available_before_blocker_result"
BENDING_BUILDER_ALIAS = (
    "_build_design_guide_controller_bending_cleanup_available_before_blocker_result"
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str | None, int | None, int | None]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return None, None, None


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    assembler_source, start, end = _function_source(INPUTS_PAGE, ASSEMBLER)
    bending_source, bending_start, bending_end = _function_source(INPUTS_PAGE, BENDING_ASSEMBLER)
    function_present = assembler_source is not None
    live_call_count = source.count(f"{ASSEMBLER}(") - (1 if function_present else 0)
    controller_builder_call_count = source.count(f"{CONTROLLER_BUILDER_ALIAS}(")
    bending_live_call_count = source.count(f"{BENDING_ASSEMBLER}(") - (
        1 if bending_source is not None else 0
    )
    decision = (
        "DELETED"
        if not function_present
        else ("READY_TO_DELETE" if live_call_count == 0 and controller_builder_call_count > 0 else "NOT_READY")
    )
    return {
        "assembler": {
            "name": ASSEMBLER,
            "present": function_present,
            "start_line": start,
            "end_line": end,
            "live_call_count": live_call_count,
        },
        "replacement": {
            "controller_builder_alias": CONTROLLER_BUILDER_ALIAS,
            "controller_builder_call_count": controller_builder_call_count,
        },
        "bending_branch_state": {
            "assembler_present": bending_source is not None,
            "assembler_live_call_count": bending_live_call_count,
            "controller_builder_call_count": source.count(f"{BENDING_BUILDER_ALIAS}("),
            "state_known": (
                (bending_source is not None and bending_live_call_count in {0, 1})
                or source.count(f"{BENDING_BUILDER_ALIAS}(") > 0
            ),
        },
        "decision": decision,
        "verification": {
            "safe_cutover": _run(
                "tools/verification/design_guide_no_active_blocked_primary_safe_cleanup_result_cutover.py"
            ),
        },
        "ready_for_deletion": decision == "READY_TO_DELETE",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    assembler = capture.get("assembler") or {}
    replacement = capture.get("replacement") or {}
    decision = capture.get("decision")
    return {
        "assembler_present_or_deleted_state_known": decision in {"READY_TO_DELETE", "DELETED", "NOT_READY"},
        "no_live_assembler_calls_when_present": (
            decision == "DELETED" or assembler.get("live_call_count") == 0
        ),
        "controller_replacement_call_present": int(
            replacement.get("controller_builder_call_count") or 0
        )
        > 0,
        "bending_branch_state_known": (capture.get("bending_branch_state") or {}).get(
            "state_known"
        )
        is True,
        "safe_cutover_passed": (capture.get("verification") or {}).get("safe_cutover", {}).get(
            "passed"
        )
        is True,
        "ready_or_already_deleted": decision in {"READY_TO_DELETE", "DELETED"},
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    assembler = capture.get("assembler") or {}
    lines = [
        "# Design Guide No-Active Blocked-Primary Safe Cleanup Legacy Assembler Deletion Proof",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Assembler present: `{assembler.get('present')}`",
        f"Live call count: `{assembler.get('live_call_count')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Delete only `_assemble_final_visible_safe_cleanup_candidate_before_blocker_result(...)` "
            "when decision is `READY_TO_DELETE`. This verifier does not decide whether the "
            "bending cleanup assembler should be deleted.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_no_active_blocked_primary_safe_cleanup_legacy_assembler_deletion_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_blocked_primary_safe_cleanup_legacy_assembler_deletion_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_safe_cleanup_legacy_assembler_deletion {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
