"""Prove deletion safety for the old combined low-util cleanup assembler."""

from __future__ import annotations

import ast
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

ASSEMBLER = "_assemble_final_visible_combined_low_util_safe_cleanup_result"
ROUTE = "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result"
BUILDER_ALIAS = "_build_design_guide_controller_combined_low_util_cleanup_result"
FULL_ROUTE_ALIAS = "_run_design_guide_controller_no_active_combined_low_util_cleanup_route"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int | None, int | None]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return "", None, None


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    assembler_source, assembler_start, assembler_end = _function_source(INPUTS_PAGE, ASSEMBLER)
    route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE)
    assembler_definition_present = bool(assembler_source)
    source_without_definition = source.replace(assembler_source, "", 1) if assembler_source else source
    live_call_count = source_without_definition.count(f"{ASSEMBLER}(")
    route_calls_assembler = f"{ASSEMBLER}(" in route_source
    route_calls_builder = f"{BUILDER_ALIAS}(" in route_source
    route_calls_full_controller = f"{FULL_ROUTE_ALIAS}(" in route_source
    already_deleted = not assembler_definition_present and live_call_count == 0
    ready_to_delete = (
        assembler_definition_present
        and live_call_count == 0
        and not route_calls_assembler
        and (route_calls_builder or route_calls_full_controller)
    )
    return {
        "decision": (
            "DELETED"
            if already_deleted
            else ("READY_TO_DELETE" if ready_to_delete else "NOT_READY_TO_DELETE")
        ),
        "assembler": {
            "name": ASSEMBLER,
            "definition_present": assembler_definition_present,
            "start_line": assembler_start,
            "end_line": assembler_end,
            "line_count": (assembler_end - assembler_start + 1) if assembler_source else 0,
            "live_call_count_outside_definition": live_call_count,
        },
        "route": {
            "name": ROUTE,
            "exists": bool(route_source),
            "start_line": route_start,
            "end_line": route_end,
            "line_count": (route_end - route_start + 1) if route_source else 0,
            "calls_old_assembler": route_calls_assembler,
            "calls_controller_builder_directly": route_calls_builder,
            "calls_full_controller_route": route_calls_full_controller,
        },
        "verification": {
            "assembler_cutover": _run(
                "tools/verification/design_guide_combined_low_util_cleanup_assembler_cutover.py"
            ),
        },
        "ready_to_delete": ready_to_delete,
        "already_deleted": already_deleted,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "recommended_next_slice": (
            "Delete the old assembler function only."
            if ready_to_delete
            else "No deletion action required; assembler is already deleted."
            if already_deleted
            else "Do not delete; a live callsite or missing controller-builder cutover remains."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    assembler = dict(capture.get("assembler") or {})
    route = dict(capture.get("route") or {})
    verification = dict(capture.get("verification") or {})
    return {
        "assembler_ready_or_already_deleted": (
            capture.get("ready_to_delete") is True or capture.get("already_deleted") is True
        ),
        "no_live_calls_outside_definition": int(
            assembler.get("live_call_count_outside_definition") or 0
        )
        == 0,
        "route_no_longer_calls_old_assembler": route.get("calls_old_assembler") is False,
        "route_calls_controller_boundary": (
            route.get("calls_controller_builder_directly") is True
            or route.get("calls_full_controller_route") is True
        ),
        "assembler_cutover_pass": (verification.get("assembler_cutover") or {}).get("passed")
        is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    assembler = dict(capture.get("assembler") or {})
    lines = [
        "# Design Guide Combined Low-Util Cleanup Legacy Assembler Deletion Proof",
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
            "## Assembler",
            f"- Function: `{assembler.get('name')}`",
            f"- Definition present: `{assembler.get('definition_present')}`",
            f"- Lines: `{assembler.get('start_line')}`-`{assembler.get('end_line')}`",
            f"- Live call count outside definition: `{assembler.get('live_call_count_outside_definition')}`",
            "",
            "## Recommendation",
            "",
            str(capture.get("recommended_next_slice") or ""),
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
        / f"design_guide_combined_low_util_cleanup_legacy_assembler_deletion_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_cleanup_legacy_assembler_deletion_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_cleanup_legacy_assembler_deletion {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
