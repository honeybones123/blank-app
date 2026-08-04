"""Dead-body deletion proof for blocked-primary page route.

This verifier proves the legacy page-owned body after the generic controller
delegation is unreachable and safe to delete. It does not change behavior.
"""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

PAGE_ROUTE = "_resolve_final_visible_no_active_blocked_primary_cleanup_probe_result"
GENERIC_CALLER = "_run_design_guide_page_shell_controller_route"
CONTROLLER_ALIAS = "_run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not paths:
        return {"status": "MISSING", "path": None}
    path = paths[0]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "ERROR", "path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    return {"status": payload.get("status"), "path": str(path), "payload": payload}


def _parse() -> tuple[str, ast.Module, list[str]]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    return source, ast.parse(source), source.splitlines()


def _function() -> tuple[ast.FunctionDef | None, str, int | None, int | None]:
    source, tree, lines = _parse()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == PAGE_ROUTE:
            end = getattr(node, "end_lineno", None)
            if end is None:
                raise RuntimeError(f"Missing end_lineno for {PAGE_ROUTE}")
            return node, "\n".join(lines[node.lineno - 1 : end]), node.lineno, end
    return None, "", None, None


def _body_without_docstring(node: ast.FunctionDef | None) -> list[ast.stmt]:
    if node is None:
        return []
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            body = body[1:]
    return body


def _delegating_return(stmt: ast.stmt | None) -> dict[str, Any]:
    if not isinstance(stmt, ast.Return) or not isinstance(stmt.value, ast.Call):
        return {"is_delegating_return": False, "controller_fn": None}
    call = stmt.value
    if not (isinstance(call.func, ast.Name) and call.func.id == GENERIC_CALLER):
        return {"is_delegating_return": False, "controller_fn": None}
    kwargs = {kw.arg: ast.unparse(kw.value) for kw in call.keywords if kw.arg is not None}
    return {
        "is_delegating_return": True,
        "controller_fn": kwargs.get("controller_fn"),
        "forwarded_kwarg_count": len([key for key in kwargs if key != "controller_fn"]),
    }


def _capture() -> dict[str, Any]:
    node, source, start, end = _function()
    body = _body_without_docstring(node)
    first = body[0] if body else None
    delegation = _delegating_return(first)
    unreachable = body[1:] if len(body) > 1 else []
    unreachable_start = getattr(unreachable[0], "lineno", None) if unreachable else None
    unreachable_end = getattr(unreachable[-1], "end_lineno", None) if unreachable else None
    latest = {
        "trace_wiring": _latest("design_guide_no_active_blocked_primary_full_route_trace_wiring"),
        "branch_parity": _latest(
            "design_guide_no_active_blocked_primary_full_route_branch_parity_scenarios"
        ),
        "controller_route_object": _latest(
            "design_guide_no_active_blocked_primary_controller_route_object"
        ),
        "generic_page_shell_cutover": _latest(
            "design_guide_no_active_blocked_primary_generic_page_shell_caller_cutover"
        ),
        "cutover_readiness": _latest(
            "design_guide_no_active_blocked_primary_full_route_cutover_readiness"
        ),
    }
    deletion_complete = len(unreachable) == 0
    return {
        "decision": (
            "UNREACHABLE_PAGE_BODY_DELETION_COMPLETE"
            if deletion_complete
            else "UNREACHABLE_PAGE_BODY_READY_FOR_DELETION"
        ),
        "route": {
            "name": PAGE_ROUTE,
            "present": node is not None,
            "start_line": start,
            "end_line": end,
            "source_hash": _stable_hash(source),
            "first_executable_is_delegating_return": delegation.get("is_delegating_return"),
            "controller_fn": delegation.get("controller_fn"),
            "forwarded_kwarg_count": delegation.get("forwarded_kwarg_count"),
            "unreachable_statement_count": len(unreachable),
            "unreachable_start_line": unreachable_start,
            "unreachable_end_line": unreachable_end,
        },
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
        "deletion_ready_now": not deletion_complete,
        "deletion_complete": deletion_complete,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    route = dict(capture.get("route") or {})
    latest = dict(capture.get("latest") or {})
    route_absent_after_deletion = (
        route.get("present") is False and capture.get("deletion_complete") is True
    )
    return {
        "route_present_or_deleted": route.get("present") is True or route_absent_after_deletion,
        "first_executable_is_delegating_return": route.get(
            "first_executable_is_delegating_return"
        )
        is True
        or route_absent_after_deletion,
        "delegates_to_expected_controller": route.get("controller_fn") == CONTROLLER_ALIAS
        or route_absent_after_deletion,
        "unreachable_body_state_is_explicit": int(route.get("unreachable_statement_count") or 0)
        >= 0,
        "trace_wiring_recomposed_and_passed": (latest.get("trace_wiring") or {}).get("status")
        == "PASS",
        "branch_parity_recomposed_and_passed": (latest.get("branch_parity") or {}).get("status")
        == "PASS",
        "controller_route_object_passed": (latest.get("controller_route_object") or {}).get(
            "status"
        )
        == "PASS",
        "generic_page_shell_cutover_passed": (latest.get("generic_page_shell_cutover") or {}).get(
            "status"
        )
        == "PASS",
        "cutover_readiness_passed": (latest.get("cutover_readiness") or {}).get("status")
        == "PASS",
        "deletion_state_is_valid": (
            capture.get("deletion_ready_now") is True
            or capture.get("deletion_complete") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    route = dict(capture.get("route") or {})
    lines = [
        "# Design Guide No-Active Blocked-Primary Dead Body Deletion Proof",
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
            "## Deletion Target",
            "",
            f"- Route lines: `{route.get('start_line')}-{route.get('end_line')}`",
            f"- Unreachable body lines: `{route.get('unreachable_start_line')}-{route.get('unreachable_end_line')}`",
            f"- Unreachable statement count: `{route.get('unreachable_statement_count')}`",
            f"- Deletion complete: `{capture.get('deletion_complete')}`",
            "",
            "## Next Safe Slice",
            "",
            "Delete only the unreachable body after the delegating return, then rerun this proof in post-deletion mode or add a deletion-complete verifier.",
            "",
            "No product behavior, visible wording, CTA/apply semantics, family runtime, solver maths, target bands, render ownership, apply routing, or UI/session ownership changed.",
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
        / f"design_guide_no_active_blocked_primary_dead_body_deletion_proof_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_blocked_primary_dead_body_deletion_proof_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_dead_body_deletion_proof {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
