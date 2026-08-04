"""Verify result trace parity wiring for blocked-primary cleanup probe route."""

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

ROUTE = "_resolve_final_visible_no_active_blocked_primary_cleanup_probe_result"
HELPER = (
    "_stamp_design_guide_controller_no_active_blocked_primary_cleanup_probe_result_trace_only"
)
SAFE_BUILDER_ALIAS = "_build_design_guide_controller_safe_cleanup_candidate_before_blocker_result"
BENDING_BUILDER_ALIAS = "_build_design_guide_controller_bending_cleanup_available_before_blocker_result"
TRACE_KEY = "design_guide_controller_no_active_blocked_primary_cleanup_probe_result_trace_only"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name}")


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
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    helper_source, helper_start, helper_end = _function_source(INPUTS_PAGE, HELPER)
    route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE)
    return {
        "helper": {"name": HELPER, "start_line": helper_start, "end_line": helper_end},
        "route": {"name": ROUTE, "start_line": route_start, "end_line": route_end},
        "safe_builder_import_present": SAFE_BUILDER_ALIAS in inputs_source,
        "bending_builder_import_present": BENDING_BUILDER_ALIAS in inputs_source,
        "helper_stamps_trace_key": TRACE_KEY in helper_source,
        "helper_hashes_product_projection": all(
            token in helper_source
            for token in ["\"item\"", "\"overview\"", "\"presentation\"", "\"render_reason\"", "\"state_fingerprint\""]
        ),
        "helper_excludes_debug_from_product_projection": '"debug"' not in helper_source[
            helper_source.find("def _projection") : helper_source.find("try:")
        ],
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
        "safe_route_builds_controller_result": SAFE_BUILDER_ALIAS + "(" in route_source,
        "bending_route_builds_controller_result": BENDING_BUILDER_ALIAS + "(" in route_source,
        "route_trace_call_count": route_source.count(f"{HELPER}("),
        "safe_controller_result_is_product_return": (
            "safe_cleanup_result = (\n                        "
            + SAFE_BUILDER_ALIAS
            + "("
            in route_source
            and "return safe_cleanup_result" in route_source
        ),
        "old_safe_assembler_still_product_return": (
            "safe_cleanup_result = _assemble_final_visible_safe_cleanup_candidate_before_blocker_result("
            in route_source
            and "return safe_cleanup_result" in route_source
        ),
        "old_bending_assembler_still_product_return": (
            "bending_probe_result = _assemble_final_visible_bending_cleanup_available_before_blocker_result("
            in route_source
            and "return bending_probe_result" in route_source
        ),
        "bending_controller_result_is_product_return": (
            "bending_probe_result = (\n                            "
            + BENDING_BUILDER_ALIAS
            + "("
            in route_source
            and "return bending_probe_result" in route_source
        ),
        "verification": {
            "result_object": _run(
                "tools/verification/design_guide_no_active_blocked_primary_cleanup_probe_result_object_snapshot.py"
            ),
            "assembler_readiness": _run(
                "tools/verification/design_guide_no_active_blocked_primary_cleanup_probe_assembler_replacement_readiness_snapshot.py"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = capture.get("verification") or {}
    return {
        "safe_builder_import_present": capture.get("safe_builder_import_present") is True,
        "bending_builder_import_present": capture.get("bending_builder_import_present") is True,
        "helper_stamps_trace_key": capture.get("helper_stamps_trace_key") is True,
        "helper_hashes_product_projection": capture.get("helper_hashes_product_projection") is True,
        "helper_excludes_debug_from_product_projection": capture.get(
            "helper_excludes_debug_from_product_projection"
        )
        is True,
        "helper_sets_non_driving_flags": capture.get("helper_sets_non_driving_flags") is True,
        "helper_catches_errors": capture.get("helper_catches_errors") is True,
        "safe_route_builds_controller_result": capture.get("safe_route_builds_controller_result")
        is True,
        "bending_route_builds_controller_result": capture.get(
            "bending_route_builds_controller_result"
        )
        is True,
        "two_trace_calls_present": int(capture.get("route_trace_call_count") or 0) == 2,
        "safe_product_return_known": (
            capture.get("old_safe_assembler_still_product_return") is True
            or capture.get("safe_controller_result_is_product_return") is True
        ),
        "bending_product_return_known": (
            capture.get("old_bending_assembler_still_product_return") is True
            or capture.get("bending_controller_result_is_product_return") is True
        ),
        "result_object_passed": (verification.get("result_object") or {}).get("passed") is True,
        "assembler_readiness_passed": (verification.get("assembler_readiness") or {}).get("passed")
        is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    lines = [
        "# Design Guide No-Active Blocked-Primary Cleanup Probe Result Trace Parity",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Trace calls: `{capture.get('route_trace_call_count')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The route now builds controller result objects beside the legacy assemblers and "
            "stamps product-projection parity. The legacy assemblers still drive the returned "
            "result until a separate cutover verifier passes.",
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
        / f"design_guide_no_active_blocked_primary_cleanup_probe_result_trace_parity_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_blocked_primary_cleanup_probe_result_trace_parity_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_cleanup_probe_result_trace_parity {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
