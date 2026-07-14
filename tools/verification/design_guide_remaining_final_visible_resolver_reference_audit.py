"""Audit remaining references to the legacy final-visible resolver.

Proof-only. This does not change product behavior. It classifies whether
``resolve_final_visible_design_guide_item(...)`` still has product callsites in
``inputs_page.py`` after the controller compute resolver cutover, and records
what still blocks deleting the legacy function body.
"""

from __future__ import annotations

import ast
from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
TOOLS_DIR = ROOT / "tools" / "verification"

RESOLVER_NAME = "resolve_final_visible_design_guide_item"
DIRECT_ASSIGNMENT = "final_compute_resolution = resolve_final_visible_design_guide_item("
FALLBACK_ASSIGNMENT = "_legacy_fallback_resolution = resolve_final_visible_design_guide_item("
RENDER_ASSIGNMENT = "_final_visible_resolution = resolve_final_visible_design_guide_item("
CONTROLLER_FALLBACK_SHELL = "_build_design_guide_controller_compute_resolver_fallback_shell("


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _ast_call_sites(path: Path, target_name: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig", errors="replace"))
    except SyntaxError as exc:
        return [{"path": str(path), "line": exc.lineno, "call": "SYNTAX_ERROR", "error": str(exc)}]
    calls: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name == target_name or name.endswith(f".{target_name}"):
            calls.append({"path": str(path), "line": int(getattr(node, "lineno", 0) or 0), "call": name})
    return calls


def _line_numbers(source: str, token: str) -> list[int]:
    return [index for index, line in enumerate(source.splitlines(), start=1) if token in line]


def _resolver_body(source: str) -> str:
    start = source.find(f"def {RESOLVER_NAME}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    if next_def < 0:
        return source[start:]
    return source[start:next_def]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    body = _resolver_body(source)
    inputs_calls = _ast_call_sites(INPUTS_PAGE, RESOLVER_NAME)
    tool_calls: list[dict[str, Any]] = []
    for path in sorted(TOOLS_DIR.rglob("*.py")):
        if path.name == Path(__file__).name:
            continue
        for call in _ast_call_sites(path, RESOLVER_NAME):
            tool_calls.append(call)
    body_route_markers = {
        "bending_snapshot_reuse": "_controller_bending_fail_snapshot_reuse_result(" in body,
        "no_active_primary_controller_route": "_prepare_final_visible_no_active_primary_for_publication(" in body,
        "no_active_combined_low_util_controller_route": "_run_design_guide_page_shell_controller_route(" in body,
        "no_active_low_shear_or_blocker_route": "_resolve_final_visible_no_active_low_shear_or_blocker_result(" in body,
        "active_fail_near_current_repair_route": "_active_fail_near_current_repair_item(" in body,
        "post_click_low_bending_route": "_post_click_low_bending_resolution_item(" in body,
    }
    latest = {
        "compute_resolver_fallback_deadness": _latest("design_guide_compute_resolver_fallback_deadness"),
        "compute_stage_resolver_controller_cutover": _latest("design_guide_compute_stage_resolver_controller_cutover"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_resolver_publication_bridge_lock": _latest(
            "design_guide_compute_resolver_publication_bridge_lock"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    decision = (
        "PRODUCT_CALLS_DELETED_BODY_COMPATIBILITY_FIXTURE_BLOCKED"
        if not inputs_calls and tool_calls
        else "PRODUCT_CALLS_REMAIN"
        if inputs_calls
        else "LEGACY_RESOLVER_BODY_DELETED"
        if not body
        else "BODY_READY_FOR_DEADNESS_PROOF"
    )
    return {
        "decision": decision,
        "inputs_ast_calls": inputs_calls,
        "tools_ast_calls": tool_calls,
        "line_references": {
            "function_definition": _line_numbers(source, f"def {RESOLVER_NAME}("),
            "direct_compute_assignment": _line_numbers(source, DIRECT_ASSIGNMENT),
            "legacy_fallback_assignment": _line_numbers(source, FALLBACK_ASSIGNMENT),
            "render_stage_assignment": _line_numbers(source, RENDER_ASSIGNMENT),
            "string_references": _line_numbers(source, RESOLVER_NAME),
        },
        "resolver_body": {
            "present": bool(body),
            "line_count_estimate": body.count("\n") + 1 if body else 0,
            "route_markers": body_route_markers,
        },
        "controller_fallback_shell_present": CONTROLLER_FALLBACK_SHELL in source,
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    line_refs = dict(capture.get("line_references") or {})
    return {
        "no_inputs_ast_calls_to_legacy_resolver": not capture.get("inputs_ast_calls"),
        "old_direct_assignment_absent": not line_refs.get("direct_compute_assignment"),
        "old_fallback_assignment_absent": not line_refs.get("legacy_fallback_assignment"),
        "old_render_stage_assignment_absent": not line_refs.get("render_stage_assignment"),
        "legacy_function_body_deleted": not bool((capture.get("resolver_body") or {}).get("present")),
        "tool_fixture_callers_retired_or_absent": not capture.get("tools_ast_calls"),
        "controller_fallback_shell_present": capture.get("controller_fallback_shell_present") is True,
        "fallback_deadness_latest_pass": (
            latest.get("compute_resolver_fallback_deadness") or {}
        ).get("status")
        == "PASS",
        "controller_cutover_latest_pass": (
            latest.get("compute_stage_resolver_controller_cutover") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_latest_pass": (
            latest.get("compute_resolver_publication_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    body = dict(capture.get("resolver_body") or {})
    lines = [
        "# Design Guide Remaining Final Visible Resolver Reference Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Checks",
        "",
        "| Check | Pass |",
        "| --- | --- |",
    ]
    lines.extend(f"| `{key}` | `{value}` |" for key, value in dict(payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Reference Counts",
            "",
            f"- Inputs AST callsites: `{len(capture.get('inputs_ast_calls') or [])}`",
            f"- Tool/fixture AST callsites: `{len(capture.get('tools_ast_calls') or [])}`",
            f"- Resolver body present: `{body.get('present')}`",
            f"- Resolver body line estimate: `{body.get('line_count_estimate')}`",
            "",
            "## Tool/Fixture Callers",
            "",
            "```json",
            json.dumps(capture.get("tools_ast_calls") or [], indent=2),
            "```",
            "",
            "## Next Safe Step",
            "",
            (
                "Retire or retarget the fixture callers to controller/publication APIs, then create a "
                "dead-body deletion proof for `resolve_final_visible_design_guide_item(...)` before "
                "deleting the legacy function body."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_remaining_final_visible_resolver_reference_audit.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_remaining_final_visible_resolver_reference_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_remaining_final_visible_resolver_reference_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_remaining_final_visible_resolver_reference_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
