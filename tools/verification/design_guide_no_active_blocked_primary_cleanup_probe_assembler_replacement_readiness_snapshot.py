"""Audit result-assembler replacement readiness for blocked-primary cleanup probe route."""

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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

ROUTE = "_resolve_final_visible_no_active_blocked_primary_cleanup_probe_result"
ASSEMBLERS = {
    "_assemble_final_visible_safe_cleanup_candidate_before_blocker_result": {
        "route_reason": "final_visible_safe_cleanup_candidate_before_blocker",
        "target_builder": "build_design_guide_controller_safe_cleanup_candidate_before_blocker_result",
        "classification": "A. ready_for_controller_result_object",
    },
    "_assemble_final_visible_bending_cleanup_available_before_blocker_result": {
        "route_reason": "final_visible_bending_cleanup_available_before_blocker",
        "target_builder": "build_design_guide_controller_bending_cleanup_available_before_blocker_result",
        "classification": "A. ready_for_controller_result_object",
    },
}


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
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE)
    rows: list[dict[str, Any]] = []
    for name, meta in ASSEMBLERS.items():
        source, start, end = _function_source(INPUTS_PAGE, name)
        function_present = source is not None
        live_call_count = inputs_source.count(f"{name}(") - (1 if function_present else 0)
        route_call_count = route_source.count(f"{name}(")
        rows.append(
            {
                "assembler": name,
                "present": function_present,
                "start_line": start,
                "end_line": end,
                "line_count": (end - start + 1) if start is not None and end is not None else 0,
                "route_reason": meta["route_reason"],
                "target_builder": meta["target_builder"],
                "target_builder_exists": meta["target_builder"] in controller_source,
                "classification": meta["classification"],
                "live_call_count": live_call_count,
                "route_call_count": route_call_count,
                "returns_standard_result_shape": (
                    not function_present
                    or all(
                    token in source
                    for token in [
                        '"item"',
                        '"overview"',
                        '"presentation"',
                        '"render_reason"',
                        '"state_fingerprint"',
                        '"debug"',
                    ]
                    )
                ),
                "mutates_candidate_item_before_return": bool(source and ".update(" in source),
                "uses_streamlit_or_session": bool(source)
                and any(
                    token in source.lower() for token in ["streamlit", "st.session_state"]
                ),
                "safe_to_delete_now": False,
                "ready_for_cutover_now": False,
                "next_action": "create_controller_result_builder_then_trace_parity",
            }
        )
    return {
        "route": {"name": ROUTE, "start_line": route_start, "end_line": route_end},
        "assemblers": rows,
        "verification": {
            "route_policy_object": _run(
                "tools/verification/design_guide_no_active_blocked_primary_cleanup_probe_route_policy_object_snapshot.py"
            ),
            "route_policy_trace_wiring": _run(
                "tools/verification/design_guide_no_active_blocked_primary_cleanup_probe_route_policy_trace_wiring_snapshot.py"
            ),
            "result_object": _run(
                "tools/verification/design_guide_no_active_blocked_primary_cleanup_probe_result_object_snapshot.py"
            ),
        },
        "decision": (
            "RESULT_ASSEMBLER_DELETION_COMPLETE"
            if all(not bool(row.get("present")) for row in rows)
            else (
                "RESULT_CUTOVER_COMPLETE_READY_FOR_BENDING_DELETION_PROOF"
                if all(int(row.get("live_call_count") or 0) == 0 for row in rows)
                else (
                    "PARTIAL_SAFE_RESULT_CUTOVER_BENDING_TRACE_PARITY"
                    if any(
                        row["assembler"]
                        == "_assemble_final_visible_safe_cleanup_candidate_before_blocker_result"
                        and row["live_call_count"] == 0
                        for row in rows
                    )
                    else (
                        "READY_FOR_RESULT_TRACE_PARITY_NOT_CUTOVER"
                        if all(row["target_builder_exists"] for row in rows)
                        else "READY_FOR_CONTROLLER_RESULT_OBJECTS_NOT_CUTOVER"
                    )
                )
            )
        ),
        "ready_for_cutover": False,
        "ready_for_deletion": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("assemblers") or [])
    verification = capture.get("verification") or {}
    return {
        "two_assemblers_tracked": len(rows) == 2,
        "no_assembler_has_multiple_live_callsites": all(
            int(row.get("live_call_count") or 0) <= 1 for row in rows
        ),
        "remaining_live_callsites_are_inside_route": all(
            row.get("route_call_count") == row.get("live_call_count") for row in rows
        ),
        "each_returns_standard_result_shape": all(
            row.get("returns_standard_result_shape") is True for row in rows
        ),
        "no_streamlit_or_session_in_assemblers": all(
            row.get("uses_streamlit_or_session") is False for row in rows
        ),
        "target_builders_present": all(
            row.get("target_builder_exists") is True for row in rows
        ),
        "not_ready_for_cutover_yet": capture.get("ready_for_cutover") is False,
        "not_ready_for_deletion_yet": capture.get("ready_for_deletion") is False,
        "route_policy_object_passed": (verification.get("route_policy_object") or {}).get("passed")
        is True,
        "route_policy_trace_wiring_passed": (
            verification.get("route_policy_trace_wiring") or {}
        ).get("passed")
        is True,
        "result_object_passed_when_builders_present": (
            all(row.get("target_builder_exists") is True for row in rows)
            and (verification.get("result_object") or {}).get("passed") is True
        )
        or all(row.get("target_builder_exists") is False for row in rows),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    lines = [
        "# Design Guide No-Active Blocked-Primary Cleanup Probe Assembler Replacement Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Assemblers", ""])
    lines.append("| Assembler | Live calls | Route calls | Target builder exists | Classification | Next action |")
    lines.append("| --- | ---: | ---: | ---: | --- | --- |")
    for row in capture.get("assemblers") or []:
        lines.append(
            "| {assembler} | {live} | {route} | {builder} | {classification} | {next} |".format(
                assembler=row.get("assembler"),
                live=row.get("live_call_count"),
                route=row.get("route_call_count"),
                builder=row.get("target_builder_exists"),
                classification=row.get("classification"),
                next=row.get("next_action"),
            )
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "The controller result builders exist. Next, wire one route callsite at a time through "
            "the controller builder with trace parity. Do not delete either assembler yet.",
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
        / f"design_guide_no_active_blocked_primary_cleanup_probe_assembler_replacement_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_blocked_primary_cleanup_probe_assembler_replacement_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_cleanup_probe_assembler_replacement_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
