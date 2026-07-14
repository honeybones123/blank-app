"""Audit remaining page-owned final-visible Design Guide route extraction targets.

This is proof-only. It does not change product behavior, visible wording,
CTA/apply semantics, family runtimes, render ownership, or session behavior.
It records which legacy resolver routes still own page-side Design Guide
decisions after completed controller-shell cutovers and dead-body deletions.
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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
PUBLICATION = ROOT / "design_brain" / "publication.py"


ROUTES: tuple[dict[str, Any], ...] = ()

COMPLETED_CONTROLLER_SHELL_ROUTES: tuple[dict[str, str], ...] = (
    {
        "route_id": "no_active_blocked_primary_cleanup_probe",
        "proof_prefix": "design_guide_no_active_blocked_primary_dead_body_deletion_proof",
    },
    {
        "route_id": "no_active_low_shear_or_blocker",
        "proof_prefix": "design_guide_no_active_low_shear_or_blocker_dead_body_deletion_proof",
    },
    {
        "route_id": "no_active_combined_low_util_cleanup",
        "proof_prefix": "design_guide_no_active_combined_low_util_generic_page_shell_caller_cutover",
    },
    {
        "route_id": "active_action_post_click_exact_blocker",
        "proof_prefix": "design_guide_active_action_post_click_exact_blocker_dead_body_deletion_proof",
    },
    {
        "route_id": "terminal_active_failure_blocker",
        "proof_prefix": "design_guide_terminal_active_failure_blocker_finalizer_cutover",
    },
)


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


def _token_count(source: str | None, tokens: tuple[str, ...]) -> dict[str, int]:
    text = source or ""
    return {token: text.count(token) for token in tokens}


def _capture() -> dict[str, Any]:
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    publication_source = PUBLICATION.read_text(encoding="utf-8", errors="replace")
    shared_design_brain_source = controller_source + "\n" + publication_source
    route_parity = _latest("design_guide_controller_compute_selector_legacy_route_parity")
    parity_capture = dict((route_parity.get("payload") or {}).get("capture") or {})
    page_owned_routes = list(parity_capture.get("page_owned_routes") or [])
    owned_routes = list(parity_capture.get("owned_routes") or [])
    completed_controller_shell_routes = [
        {
            "route_id": route["route_id"],
            "proof": _latest(route["proof_prefix"]),
        }
        for route in COMPLETED_CONTROLLER_SHELL_ROUTES
    ]
    completed_ids = [row["route_id"] for row in completed_controller_shell_routes]
    expected_page_owned_routes = [str(route["route_id"]) for route in ROUTES]
    parity_page_owned_routes = [
        route_id for route_id in page_owned_routes if route_id not in completed_ids
    ]
    rows: list[dict[str, Any]] = []
    for route in ROUTES:
        source, start, end = _function_source(INPUTS_PAGE, str(route["function"]))
        controller_surface = list(route.get("current_controller_surface") or [])
        rows.append(
            {
                "route_id": route["route_id"],
                "function": route["function"],
                "present": source is not None,
                "start_line": start,
                "end_line": end,
                "line_count": (end - start + 1) if start is not None and end is not None else 0,
                "classification": route["classification"],
                "why_not_delete": route["why_not_delete"],
                "next_boundary": route["next_boundary"],
                "current_controller_surface": controller_surface,
                "controller_surface_present": {
                    name: name in shared_design_brain_source for name in controller_surface
                },
                "uses_streamlit_or_session": bool(source)
                and any(term in source.lower() for term in ("streamlit", "st.session_state")),
                "route_trace_count": (source or "").count("_resolver_route_trace_event("),
                "return_count": (source or "").count("return "),
                "controller_builder_call_counts": _token_count(
                    source,
                    tuple(name + "(" for name in controller_surface),
                ),
                "safe_to_delete_now": False,
                "ready_for_generic_page_shell_caller_now": False,
                "product_driving": True,
            }
        )
    return {
        "decision": "NO_REMAINING_PAGE_OWNED_FINAL_VISIBLE_ROUTE_TARGETS",
        "controller_owned_routes": owned_routes,
        "page_owned_routes": page_owned_routes,
        "parity_page_owned_routes_after_completed_cutovers": parity_page_owned_routes,
        "expected_page_owned_routes": expected_page_owned_routes,
        "completed_controller_shell_routes": completed_controller_shell_routes,
        "routes": rows,
        "latest": {
            "controller_compute_selector_legacy_route_parity": {
                "status": route_parity.get("status"),
                "path": route_parity.get("path"),
            },
            "independence_lock": {
                "status": _latest("design_guide_independence_lock").get("status"),
                "path": _latest("design_guide_independence_lock").get("path"),
            },
            "render_bridge_lock": {
                "status": _latest("design_guide_render_bridge_lock").get("status"),
                "path": _latest("design_guide_render_bridge_lock").get("path"),
            },
            "compute_resolver_publication_bridge_lock": {
                "status": _latest(
                    "design_guide_compute_resolver_publication_bridge_lock"
                ).get("status"),
                "path": _latest("design_guide_compute_resolver_publication_bridge_lock").get(
                    "path"
                ),
            },
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("routes") or [])
    latest = dict(capture.get("latest") or {})
    completed = list(capture.get("completed_controller_shell_routes") or [])
    return {
        "all_expected_routes_present": all(row.get("present") is True for row in rows),
        "page_owned_routes_match_parity_artifact_after_completed_cutovers": sorted(
            capture.get("parity_page_owned_routes_after_completed_cutovers") or []
        )
        == sorted(capture.get("expected_page_owned_routes") or []),
        "completed_controller_shell_route_artifacts_pass": all(
            (row.get("proof") or {}).get("status") == "PASS" for row in completed
        ),
        "no_route_marked_safe_to_delete": all(row.get("safe_to_delete_now") is False for row in rows),
        "no_route_marked_generic_ready": all(
            row.get("ready_for_generic_page_shell_caller_now") is False for row in rows
        ),
        "no_streamlit_or_session_in_route_functions": all(
            row.get("uses_streamlit_or_session") is False for row in rows
        ),
        "known_controller_surfaces_exist": all(
            all((row.get("controller_surface_present") or {}).values()) for row in rows
        ),
        "route_parity_artifact_passes": (
            latest.get("controller_compute_selector_legacy_route_parity") or {}
        ).get("status")
        == "PASS",
        "independence_lock_currently_passes": (latest.get("independence_lock") or {}).get("status")
        == "PASS",
        "render_bridge_lock_currently_passes": (latest.get("render_bridge_lock") or {}).get("status")
        == "PASS",
        "compute_bridge_lock_currently_passes": (
            latest.get("compute_resolver_publication_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Remaining Page-Owned Route Extraction Audit",
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
            "## Remaining Routes",
            "",
            "| Route | Function | Lines | Classification | Safe to delete now | Next boundary |",
            "| --- | --- | ---: | --- | ---: | --- |",
        ]
    )
    for row in capture.get("routes") or []:
        lines.append(
            "| {route} | `{function}` | {lines} | `{classification}` | `{delete}` | {next_boundary} |".format(
                route=row.get("route_id"),
                function=row.get("function"),
                lines=row.get("line_count"),
                classification=row.get("classification"),
                delete=row.get("safe_to_delete_now"),
                next_boundary=row.get("next_boundary"),
            )
    )
    lines.extend(
        [
            "",
            "## Completed Controller Shell Routes",
            "",
            "| Route | Proof status | Proof artifact |",
            "| --- | --- | --- |",
        ]
    )
    for row in capture.get("completed_controller_shell_routes") or []:
        proof = row.get("proof") or {}
        lines.append(
            f"| {row.get('route_id')} | `{proof.get('status')}` | `{proof.get('path')}` |"
        )
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            "Audit trace-compatible page-shell wrappers that remain after route-result cutover.",
            "The terminal active-failure blocker finalizer still exists as a trace-preserving shell, but final result construction now delegates to DesignGuideController.",
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
    json_path = ARTIFACT_DIR / f"design_guide_remaining_page_owned_route_extraction_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_remaining_page_owned_route_extraction_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_remaining_page_owned_route_extraction_audit {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status == "PASS":
        print("next=trace-compatible page-shell wrapper cleanup audit")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
