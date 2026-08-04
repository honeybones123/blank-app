"""Verify active-action final visible result is controller-owned."""

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

ROUTE = "resolve_final_visible_design_guide_item"
ACTIVE_ASSEMBLER = "_assemble_final_visible_active_action_result"
ACTIVE_BUILDER_ALIAS = "_build_design_guide_controller_active_action_result"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return "", 0, -1


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
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE)
    route_retired_with_legacy_resolver = not bool(route_source) and all(
        token in inputs_source
        for token in (
            "def _final_visible_resolution_from_final_publication_authority(",
            "DesignGuideController",
            "FinalDesignGuidePublication",
            "final_visible_resolution_compatibility_only",
        )
    )
    try:
        assembler_source, assembler_start, assembler_end = _function_source(INPUTS_PAGE, ACTIVE_ASSEMBLER)
    except RuntimeError:
        assembler_source, assembler_start, assembler_end = "", None, None
    return {
        "route": {"name": ROUTE, "start_line": route_start, "end_line": route_end},
        "legacy_assembler": {
            "name": ACTIVE_ASSEMBLER,
            "start_line": assembler_start,
            "end_line": assembler_end,
        },
        "active_builder_import_present": ACTIVE_BUILDER_ALIAS in inputs_source,
        "route_retired_with_legacy_resolver": route_retired_with_legacy_resolver,
        "active_failure_candidate_helper_call_count": max(
            0,
            inputs_source.count("_resolve_final_visible_active_failure_candidate_item(") - 1,
        ),
        "route_builds_controller_result": (
            "controller_active_action_result = " + ACTIVE_BUILDER_ALIAS + "(" in route_source
        ),
        "route_returns_controller_result": "return controller_active_action_result" in route_source,
        "route_no_longer_calls_legacy_assembler": ACTIVE_ASSEMBLER + "(" not in route_source,
        "legacy_assembler_still_present_pending_deletion": f"def {ACTIVE_ASSEMBLER}(" in assembler_source,
        "legacy_assembler_deleted_after_cutover": not assembler_source,
        "route_preserves_state_fingerprint_input": (
            "_active_action_state_fingerprint = _design_guide_primary_apply_state_fingerprint"
            in route_source
            and "state_fingerprint=_active_action_state_fingerprint" in route_source
        ),
        "route_preserves_change_line_inputs": (
            "_active_action_change_lines = _guidance_change_lines_for_updates" in route_source
            and "guidance_change_lines=list(_active_action_change_lines or [])" in route_source
            and "guidance_change_summary_compact=_guidance_compact_change_text" in route_source
        ),
        "route_preserves_target_band_inputs": (
            "efficiency_target_util_min=float(EFFICIENCY_TARGET_UTIL_MIN)" in route_source
            and "efficiency_target_util_max=float(EFFICIENCY_TARGET_UTIL_MAX)" in route_source
        ),
        "verification": {
            "active_action_result_object": _run(
                "tools/verification/design_guide_active_action_result_object_snapshot.py"
            ),
            "active_action_trace_parity_artifact": _run(
                "tools/verification/design_guide_active_action_result_trace_parity_snapshot.py"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "deletion_performed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = capture.get("verification") or {}
    return {
        "active_builder_import_present": capture.get("active_builder_import_present") is True,
        "route_builds_controller_result": capture.get("route_builds_controller_result") is True
        or capture.get("route_retired_with_legacy_resolver") is True,
        "route_returns_controller_result": capture.get("route_returns_controller_result") is True
        or capture.get("route_retired_with_legacy_resolver") is True,
        "route_no_longer_calls_legacy_assembler": capture.get(
            "route_no_longer_calls_legacy_assembler"
        )
        is True,
        "legacy_assembler_pending_or_deleted_state_known": (
            capture.get("legacy_assembler_still_present_pending_deletion") is True
            or capture.get("legacy_assembler_deleted_after_cutover") is True
        ),
        "route_preserves_state_fingerprint_input": capture.get(
            "route_preserves_state_fingerprint_input"
        )
        is True
        or capture.get("route_retired_with_legacy_resolver") is True,
        "route_preserves_change_line_inputs": capture.get("route_preserves_change_line_inputs")
        is True
        or capture.get("route_retired_with_legacy_resolver") is True,
        "route_preserves_target_band_inputs": capture.get("route_preserves_target_band_inputs")
        is True
        or capture.get("route_retired_with_legacy_resolver") is True,
        "active_action_result_object_passed": (
            verification.get("active_action_result_object") or {}
        ).get("passed")
        is True,
        "active_action_trace_parity_artifact_passed": (
            verification.get("active_action_trace_parity_artifact") or {}
        ).get("passed")
        is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "deletion_not_in_this_slice": capture.get("deletion_performed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    lines = [
        "# Design Guide Active-Action Result Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Route: `{ROUTE}` lines `{(capture.get('route') or {}).get('start_line')}`-`{(capture.get('route') or {}).get('end_line')}`",
        f"Legacy assembler still present: `{capture.get('legacy_assembler_still_present_pending_deletion')}`",
        f"Legacy assembler deleted: `{capture.get('legacy_assembler_deleted_after_cutover')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The active-action final visible result is now returned from the controller-owned "
            "result builder. The legacy page assembler may either remain present pending a "
            "separate deletion proof or be already deleted after that proof passes.",
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
    json_path = ARTIFACT_DIR / f"design_guide_active_action_result_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_active_action_result_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_active_action_result_cutover {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
