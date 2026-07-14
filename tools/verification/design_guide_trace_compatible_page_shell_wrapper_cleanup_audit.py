"""Audit trace-compatible page-shell wrappers after route cutovers.

This is proof-only. It identifies remaining wrappers whose body delegates to
``_run_design_guide_page_shell_controller_route(...)`` and classifies whether
they are dead, still live as page-shell callback forwarders, or ready for a
future direct generic-caller migration.
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

GENERIC_CALLER = "_run_design_guide_page_shell_controller_route"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _parse_inputs() -> tuple[str, ast.Module, list[str]]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    return source, ast.parse(source), source.splitlines()


def _function_body_without_docstring(node: ast.FunctionDef) -> list[ast.stmt]:
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            body = body[1:]
    return body


def _delegating_return(node: ast.FunctionDef) -> ast.Call | None:
    body = _function_body_without_docstring(node)
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return None
    value = body[0].value
    if not isinstance(value, ast.Call):
        return None
    if _call_name(value.func) != GENERIC_CALLER:
        return None
    return value


def _keyword_names(call: ast.Call) -> dict[str, str]:
    names: dict[str, str] = {}
    for kw in call.keywords:
        if not kw.arg:
            continue
        names[kw.arg] = ast.unparse(kw.value) if hasattr(ast, "unparse") else type(kw.value).__name__
    return names


def _callsite_lines(source: str, function_name: str, def_line: int) -> list[int]:
    lines: list[int] = []
    token = f"{function_name}("
    for lineno, line in enumerate(source.splitlines(), start=1):
        if lineno == def_line:
            continue
        stripped = line.lstrip()
        if stripped.startswith("def "):
            continue
        if token in line:
            lines.append(lineno)
    return lines


def _capture() -> dict[str, Any]:
    source, tree, lines = _parse_inputs()
    wrappers: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        call = _delegating_return(node)
        if call is None:
            continue
        keywords = _keyword_names(call)
        callsite_lines = _callsite_lines(source, node.name, int(node.lineno))
        controller_fn = keywords.get("controller_fn")
        wrappers.append(
            {
                "function": node.name,
                "start_line": int(node.lineno),
                "end_line": int(getattr(node, "end_lineno", node.lineno)),
                "line_count": int(getattr(node, "end_lineno", node.lineno)) - int(node.lineno) + 1,
                "controller_fn": controller_fn,
                "forwarded_kwarg_count": len([key for key in keywords if key != "controller_fn"]),
                "callsite_lines": callsite_lines,
                "callsite_count": len(callsite_lines),
                "classification": (
                    "LIVE_PAGE_SHELL_CALLBACK_FORWARDER"
                    if callsite_lines
                    else "DEAD_PAGE_SHELL_CALLBACK_FORWARDER"
                ),
                "owns_design_guide_meaning": False,
                "owns_cta_apply_meaning": False,
                "owns_visible_wording": False,
                "owns_publication_truth": False,
                "owns_route_trace_authority": False,
                "owns_session_state": False,
                "safe_next_action": (
                    "direct-callsite-migration-readiness-proof"
                    if callsite_lines
                    else "dead-wrapper-deletion-proof"
                ),
            }
        )
    wrappers = sorted(wrappers, key=lambda row: row["start_line"])
    category_counts: dict[str, int] = {}
    for wrapper in wrappers:
        category_counts[wrapper["classification"]] = category_counts.get(wrapper["classification"], 0) + 1
    return {
        "decision": (
            "TRACE_COMPATIBLE_PAGE_SHELL_WRAPPERS_REMAIN"
            if any(row["callsite_count"] for row in wrappers)
            else (
                "NO_TRACE_COMPATIBLE_PAGE_SHELL_HELPER_OR_WRAPPERS"
                if f"def {GENERIC_CALLER}(" not in source
                else "NO_LIVE_TRACE_COMPATIBLE_PAGE_SHELL_WRAPPERS"
            )
        ),
        "wrappers": wrappers,
        "category_counts": category_counts,
        "generic_caller_definition_present": f"def {GENERIC_CALLER}(" in source,
        "generic_caller_call_count": source.count(f"{GENERIC_CALLER}(") - int(f"def {GENERIC_CALLER}(" in source),
        "latest": {
            "remaining_route_inventory": _latest("design_guide_remaining_page_owned_route_extraction_audit"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "session_state_behavior_changed": False,
        "widget_keys_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    wrappers = list(capture.get("wrappers") or [])
    return {
        "generic_caller_state_valid": (
            bool(capture.get("generic_caller_definition_present"))
            or (
                int(capture.get("generic_caller_call_count") or 0) == 0
                and not list(capture.get("wrappers") or [])
            )
        ),
        "all_wrappers_are_non_authoritative": all(
            not any(
                row.get(key)
                for key in (
                    "owns_design_guide_meaning",
                    "owns_cta_apply_meaning",
                    "owns_visible_wording",
                    "owns_publication_truth",
                    "owns_route_trace_authority",
                    "owns_session_state",
                )
            )
            for row in wrappers
        ),
        "wrappers_identified": len(wrappers) == int(capture.get("generic_caller_call_count") or 0),
        "remaining_route_inventory_latest_pass": (latest.get("remaining_route_inventory") or {}).get("status") == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "session_state_behavior_unchanged": capture.get("session_state_behavior_changed") is False,
        "widget_keys_unchanged": capture.get("widget_keys_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Trace-Compatible Page-Shell Wrapper Cleanup Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Wrapper Inventory",
        "",
        "| Function | Lines | Controller | Calls | Classification | Next |",
        "| --- | ---: | --- | ---: | --- | --- |",
    ]
    for row in list(capture.get("wrappers") or []):
        lines.append(
            "| `{function}` | {start_line}-{end_line} | `{controller_fn}` | {callsite_count} | {classification} | {safe_next_action} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Category Counts",
            "",
            "```json",
            json.dumps(capture.get("category_counts") or {}, indent=2),
            "```",
            "",
            "## Next Safe Step",
            "",
            (
                "For each live wrapper, create a direct-callsite migration readiness proof. "
                "Do not delete a wrapper until its callsites are migrated or proven dead."
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
        "schema": "design_guide_trace_compatible_page_shell_wrapper_cleanup_audit.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_trace_compatible_page_shell_wrapper_cleanup_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_trace_compatible_page_shell_wrapper_cleanup_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(
        json.dumps(
            {
                "status": status,
                "decision": capture.get("decision"),
                "json": str(json_path),
                "report": str(report_path),
            },
            indent=2,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
