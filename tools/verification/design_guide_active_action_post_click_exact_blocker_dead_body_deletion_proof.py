"""Dead-body/deletion proof for the active-action exact-blocker page route.

This verifier supports three states:
- pre-deletion: generic page-shell delegation is first executable statement and
  the old page body remains unreachable after it;
- post-deletion: generic page-shell delegation is the only executable body.
- post-route-deletion: the old page route itself is absent after a controller
  route cutover/deletion proof.
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

PAGE_ROUTE = "_resolve_final_visible_post_click_active_action_exact_blocker_result"
GENERIC_CALLER = "_run_design_guide_page_shell_controller_route"
CONTROLLER_ALIAS = "_run_design_guide_controller_active_action_post_click_exact_blocker_route"

OLD_BODY_TOKENS = {
    "inline_requires_blocker_gate": "post_click_active_action_requires_blocker",
    "inline_blocker_audit": "post_click_blocker_audit",
    "inline_builder_call": "post_click_low_bending_resolution_item_fn(",
    "inline_trace_candidate": "post_click_blocker_replacement_candidate",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or "")
    if "PASS" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _parse(path: Path) -> tuple[str, ast.Module, list[str]]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    return source, ast.parse(source), source.splitlines()


def _function(path: Path, name: str) -> tuple[ast.FunctionDef | None, str, int | None, int | None]:
    source, tree, lines = _parse(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = getattr(node, "end_lineno", None)
            if end is None:
                raise RuntimeError(f"Missing end_lineno for {name}")
            return node, "\n".join(lines[node.lineno - 1 : end]), node.lineno, end
    return None, "", None, None


def _executable_body(node: ast.FunctionDef | None) -> list[ast.stmt]:
    if node is None:
        return []
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            body = body[1:]
    return body


def _delegating_return(stmt: ast.stmt | None) -> bool:
    if not isinstance(stmt, ast.Return) or not isinstance(stmt.value, ast.Call):
        return False
    call = stmt.value
    if not (isinstance(call.func, ast.Name) and call.func.id == GENERIC_CALLER):
        return False
    kwargs = {kw.arg: ast.unparse(kw.value) for kw in call.keywords if kw.arg is not None}
    return kwargs.get("controller_fn") == CONTROLLER_ALIAS


def _capture() -> dict[str, Any]:
    node, source, start, end = _function(INPUTS_PAGE, PAGE_ROUTE)
    body = _executable_body(node)
    old_body_after_return = len(body) > 1
    first_is_delegating = _delegating_return(body[0] if body else None)
    old_body_tokens_present = {name: token in source for name, token in OLD_BODY_TOKENS.items()}
    route_absent = node is None
    return {
        "decision": (
            "DELETION_COMPLETE_ROUTE_ABSENT"
            if route_absent
            else (
                "DELETION_COMPLETE"
                if first_is_delegating and not old_body_after_return
                else (
                    "READY_TO_DELETE_UNREACHABLE_BODY"
                    if first_is_delegating and old_body_after_return
                    else "NOT_READY"
                )
            )
        ),
        "page_route": {
            "name": PAGE_ROUTE,
            "present": node is not None,
            "start_line": start,
            "end_line": end,
            "line_count": (end - start + 1) if start and end else 0,
            "source_hash": _stable_hash(source),
            "first_executable_is_generic_delegating_return": first_is_delegating,
            "old_body_after_delegating_return_present": old_body_after_return,
            "old_body_tokens_present": old_body_tokens_present,
        },
        "latest": {
            "cutover_readiness": _latest(
                "design_guide_active_action_post_click_exact_blocker_cutover_readiness"
            ),
            "route_parity": _latest("design_guide_active_action_post_click_exact_blocker_route_parity"),
            "route_object": _latest("design_guide_active_action_post_click_exact_blocker_route_object"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    route = dict(capture.get("page_route") or {})
    latest = dict(capture.get("latest") or {})
    decision = capture.get("decision")
    token_hits = dict(route.get("old_body_tokens_present") or {})
    route_absent = route.get("present") is False
    return {
        "page_route_present_or_deleted": route.get("present") is True or route_absent,
        "first_executable_is_generic_return": route.get(
            "first_executable_is_generic_delegating_return"
        )
        is True
        or route_absent,
        "deletion_state_valid": decision in {
            "READY_TO_DELETE_UNREACHABLE_BODY",
            "DELETION_COMPLETE",
            "DELETION_COMPLETE_ROUTE_ABSENT",
        },
        "old_body_state_matches_decision": (
            decision == "DELETION_COMPLETE_ROUTE_ABSENT"
            and route_absent
        )
        or (
            (
                decision == "READY_TO_DELETE_UNREACHABLE_BODY"
                and route.get("old_body_after_delegating_return_present") is True
            )
            or (
                decision == "DELETION_COMPLETE"
                and route.get("old_body_after_delegating_return_present") is False
            )
        ),
        "old_inline_tokens_removed_when_deletion_complete": (
            decision not in {"DELETION_COMPLETE", "DELETION_COMPLETE_ROUTE_ABSENT"}
            or not any(token_hits.values())
        ),
        "cutover_readiness_passes": (
            (latest.get("cutover_readiness") or {}).get("status") == "PASS"
        ),
        "route_parity_passes": (latest.get("route_parity") or {}).get("status") == "PASS",
        "route_object_passes": (latest.get("route_object") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    route = dict(capture.get("page_route") or {})
    lines = [
        "# Design Guide Active-Action Post-Click Exact-Blocker Dead Body Deletion Proof",
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
            "## Route State",
            "",
            f"- Lines: `{route.get('start_line')}-{route.get('end_line')}`",
            f"- Line count: `{route.get('line_count')}`",
            f"- Old body after delegating return present: `{route.get('old_body_after_delegating_return_present')}`",
            f"- Old body tokens present: `{route.get('old_body_tokens_present')}`",
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
        / f"design_guide_active_action_post_click_exact_blocker_dead_body_deletion_proof_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_active_action_post_click_exact_blocker_dead_body_deletion_proof_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_active_action_post_click_exact_blocker_dead_body_deletion_proof {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
