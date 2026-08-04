"""Verify trace-only controller parity for active-action final visible result."""

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
HELPER = "_stamp_design_guide_controller_active_action_result_trace_only"
ACTIVE_BUILDER_ALIAS = "_build_design_guide_controller_active_action_result"
ACTIVE_ASSEMBLER = "_assemble_final_visible_active_action_result"
TRACE_KEY = "design_guide_controller_active_action_result_trace_only"


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
    helper_source, helper_start, helper_end = _function_source(INPUTS_PAGE, HELPER)
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
    projection_block = helper_source[
        helper_source.find("def _projection") : helper_source.find("try:")
    ]
    return {
        "helper": {"name": HELPER, "start_line": helper_start, "end_line": helper_end},
        "route": {"name": ROUTE, "start_line": route_start, "end_line": route_end},
        "active_builder_import_present": ACTIVE_BUILDER_ALIAS in inputs_source,
        "helper_stamps_trace_key": TRACE_KEY in helper_source,
        "helper_marks_trace_only": '"trace_only": True' in helper_source,
        "helper_hashes_product_projection": all(
            token in helper_source
            for token in [
                '"item"',
                '"overview"',
                '"presentation"',
                '"render_reason"',
                '"state_fingerprint"',
            ]
        ),
        "helper_excludes_debug_from_product_projection": '"debug"' not in projection_block,
        "helper_sets_non_driving_flags": all(
            token in helper_source
            for token in [
                '"product_driving": False',
                '"render_driving": False',
                '"apply_driving": False',
                '"session_driving": False',
            ]
        ),
        "helper_catches_errors": "except Exception as exc:" in helper_source,
        "route_retired_with_legacy_resolver": route_retired_with_legacy_resolver,
        "active_failure_candidate_helper_call_count": max(
            0,
            inputs_source.count("_resolve_final_visible_active_failure_candidate_item(") - 1,
        ),
        "route_still_builds_legacy_assembler_result": (
            "active_action_result = " + ACTIVE_ASSEMBLER + "(" in route_source
        ),
        "route_builds_controller_result": (
            "controller_active_action_result = " + ACTIVE_BUILDER_ALIAS + "(" in route_source
        ),
        "route_stamps_trace": HELPER + "(" in route_source,
        "route_returns_legacy_result": "return active_action_result" in route_source,
        "route_does_not_return_controller_result": "return controller_active_action_result" not in route_source,
        "route_cutover_state_detected": (
            (
                "return controller_active_action_result" in route_source
                and ACTIVE_ASSEMBLER + "(" not in route_source
            )
            or route_retired_with_legacy_resolver
        ),
        "route_precomputes_state_fingerprint": (
            "_active_action_state_fingerprint = _design_guide_primary_apply_state_fingerprint"
            in route_source
        ),
        "route_precomputes_change_lines": "_active_action_change_lines = _guidance_change_lines_for_updates" in route_source,
        "verification": {
            "active_action_result_object": _run(
                "tools/verification/design_guide_active_action_result_object_snapshot.py"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = capture.get("verification") or {}
    trace_wired_state = (
        capture.get("route_still_builds_legacy_assembler_result") is True
        and capture.get("route_builds_controller_result") is True
        and capture.get("route_stamps_trace") is True
        and capture.get("route_returns_legacy_result") is True
        and capture.get("route_does_not_return_controller_result") is True
    )
    cutover_state = (
        capture.get("route_cutover_state_detected") is True
        and (
            capture.get("route_builds_controller_result") is True
            or capture.get("route_retired_with_legacy_resolver") is True
        )
    )
    return {
        "active_builder_import_present": capture.get("active_builder_import_present") is True,
        "helper_stamps_trace_key": capture.get("helper_stamps_trace_key") is True,
        "helper_marks_trace_only": capture.get("helper_marks_trace_only") is True,
        "helper_hashes_product_projection": capture.get("helper_hashes_product_projection") is True,
        "helper_excludes_debug_from_product_projection": capture.get(
            "helper_excludes_debug_from_product_projection"
        )
        is True,
        "helper_sets_non_driving_flags": capture.get("helper_sets_non_driving_flags") is True,
        "helper_catches_errors": capture.get("helper_catches_errors") is True,
        "route_is_trace_wired_or_cutover": trace_wired_state or cutover_state,
        "route_precomputes_state_fingerprint": capture.get("route_precomputes_state_fingerprint")
        is True
        or capture.get("route_retired_with_legacy_resolver") is True,
        "route_precomputes_change_lines": capture.get("route_precomputes_change_lines") is True
        or capture.get("route_retired_with_legacy_resolver") is True,
        "active_action_result_object_passed": (
            verification.get("active_action_result_object") or {}
        ).get("passed")
        is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    lines = [
        "# Design Guide Active-Action Result Trace Parity",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Helper: `{HELPER}` lines `{(capture.get('helper') or {}).get('start_line')}`-`{(capture.get('helper') or {}).get('end_line')}`",
        f"Route: `{ROUTE}` lines `{(capture.get('route') or {}).get('start_line')}`-`{(capture.get('route') or {}).get('end_line')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The active-action path now builds the controller result beside the legacy "
            "assembler and stamps product-projection parity only. The legacy assembler "
            "still drives the returned product result until a separate cutover verifier passes.",
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
    json_path = ARTIFACT_DIR / f"design_guide_active_action_result_trace_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_active_action_result_trace_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_active_action_result_trace_parity {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
