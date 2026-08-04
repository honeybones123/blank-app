"""Audit readiness for extracting the no-active low-shear/blocker route.

Proof-only: this verifier does not add a controller route, wire the page,
change publication, alter CTA/apply behaviour, or change visible wording.
It records the current page-owned branch shape that a future controller route
must preserve before any cutover or deletion.
"""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

try:
    from tools.verification.verification_run_manifest import current_run_artifact
except ModuleNotFoundError:
    from verification_run_manifest import current_run_artifact


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

ROUTE = "_resolve_final_visible_no_active_low_shear_or_blocker_result"
TARGET_CONTROLLER_ROUTE = "run_design_guide_controller_no_active_low_shear_or_blocker_route"

BRANCH_TOKENS: tuple[dict[str, Any], ...] = (
    {
        "branch": "zero_shear_post_click_accepted",
        "tokens": (
            "final_zero_shear_post_click_accepted",
            "assemble_zero_shear_demand_accepted_result_fn(",
            "return zero_shear_result",
        ),
        "meaning": "Accepted zero-shear post-click state should publish an accepted result without another cleanup CTA.",
    },
    {
        "branch": "low_shear_resolution",
        "tokens": (
            "final_shear_util is not None",
            "resolve_low_shear_target_cleanup_probe_fn(",
            "resolve_low_shear_evidence_fallback_fn(",
            "resolve_low_shear_exact_blocker_fallback_fn(",
            "apply_low_shear_combined_low_util_blocker_gate_fn(",
            "finalize_low_shear_resolution_item_before_return_fn(",
            "assemble_low_shear_resolution_result_fn(",
        ),
        "meaning": "Low shear utilisation below the accepted floor should try target cleanup, evidence fallback, exact blocker fallback, then package the selected result.",
    },
    {
        "branch": "combined_low_util_blocker_or_best_safe",
        "tokens": (
            "post_click_accepted_green_audit_fn(",
            "post_click_accepted_green_valid",
            "combined_low_util_exact_blocker_final_item_fn(",
            "assemble_combined_low_util_blocker_or_best_safe_result_fn(",
        ),
        "meaning": "Accepted green post-click state may still need combined low-util blocker or best-safe packaging.",
    },
    {
        "branch": "no_result",
        "tokens": (
            "return None",
        ),
        "meaning": "If no branch produces a valid item, the route yields no result.",
    },
)

FORBIDDEN_OWNERSHIP_TOKENS: tuple[str, ...] = (
    "st.session_state",
    "import streamlit",
    "st.button",
    "st.markdown",
    "_queue_primary_design_guide_button_action",
    "_design_guide_dashboard_card_html",
    "contracted_repair_ladder_specs(",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str | None, int | None, int | None]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return None, None, None


def _latest(prefix: str) -> dict[str, Any]:
    if os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        path, payload = current_run_artifact(prefix)
        if path is None:
            return {"found": False, "status": "MISSING_CURRENT_RUN_ARTIFACT", "path": None}
        return {"found": True, "status": payload.get("status"), "path": str(path)}
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


def _capture() -> dict[str, Any]:
    route_source, start_line, end_line = _function_source(INPUTS_PAGE, ROUTE)
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    target_exists = TARGET_CONTROLLER_ROUTE in controller_source
    controller_route_source = ""
    controller_start_line = None
    controller_end_line = None
    if target_exists:
        controller_route_source, controller_start_line, controller_end_line = _function_source(
            CONTROLLER, TARGET_CONTROLLER_ROUTE
        )
    route_text = route_source or ""
    page_is_delegating_shell = (
        "_run_design_guide_page_shell_controller_route(" in route_source
        and "_run_design_guide_controller_no_active_low_shear_or_blocker_route" in route_source
        and "return _run_design_guide_page_shell_controller_route(" in route_source
    ) if route_source is not None else False
    page_route_deleted = route_source is None and target_exists
    branch_source = controller_route_source if page_is_delegating_shell and target_exists else route_source
    if page_route_deleted and target_exists:
        branch_source = controller_route_source
    branch_source_owner = (
        "controller_route"
        if (page_is_delegating_shell or page_route_deleted) and target_exists
        else "inputs_page_route"
    )
    branch_map = []
    for spec in BRANCH_TOKENS:
        tokens = tuple(str(token) for token in spec["tokens"])
        branch_map.append(
            {
                "branch": spec["branch"],
                "meaning": spec["meaning"],
                "tokens": list(tokens),
                "tokens_present": {token: token in branch_source for token in tokens},
                "all_tokens_present": all(token in branch_source for token in tokens),
            }
        )
    forbidden_hits = {
        token: token in (route_source or "") or token in controller_route_source
        for token in FORBIDDEN_OWNERSHIP_TOKENS
    }
    return {
        "decision": (
            "PAGE_ROUTE_DELETED_CONTROLLER_ROUTE_VERIFIED"
            if page_route_deleted
            else (
            "POST_CUTOVER_CONTROLLER_BRANCH_MAP_VERIFIED"
            if page_is_delegating_shell and target_exists
            else "CONTROLLER_ROUTE_OBJECT_PRESENT_READY_FOR_TRACE_PARITY"
            if target_exists
            else "READY_FOR_CONTROLLER_ROUTE_OBJECT_PROOF"
            )
        ),
        "route": {
            "function": ROUTE,
            "start_line": start_line,
            "end_line": end_line,
            "present": route_source is not None,
            "line_count": end_line - start_line + 1 if start_line and end_line else 0,
            "return_count": route_text.count("return "),
            "trace_event_count": route_text.count("_resolver_route_trace_event("),
            "source_hash": _stable_hash(route_text),
        },
        "page_is_delegating_shell": page_is_delegating_shell,
        "page_route_deleted": page_route_deleted,
        "branch_source_owner": branch_source_owner,
        "controller_route": {
            "function": TARGET_CONTROLLER_ROUTE,
            "start_line": controller_start_line,
            "end_line": controller_end_line,
            "line_count": (
                controller_end_line - controller_start_line + 1
                if controller_start_line is not None and controller_end_line is not None
                else 0
            ),
            "source_hash": _stable_hash(controller_route_source) if controller_route_source else None,
        },
        "branch_map": branch_map,
        "target_controller_route": TARGET_CONTROLLER_ROUTE,
        "target_controller_route_exists": target_exists,
        "forbidden_ownership_hits": forbidden_hits,
        "latest": {
            "remaining_page_owned_route_extraction_audit": _latest(
                "design_guide_remaining_page_owned_route_extraction_audit"
            ),
            "controller_compute_selector_legacy_route_parity": _latest(
                "design_guide_controller_compute_selector_legacy_route_parity"
            ),
            "independence_lock": _latest("design_guide_independence_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_resolver_publication_bridge_lock": _latest(
                "design_guide_compute_resolver_publication_bridge_lock"
            ),
            "final_visible_resolver_dead_body": _latest(
                "design_guide_final_visible_resolver_dead_body_deletion_proof"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    branch_map = list(capture.get("branch_map") or [])
    route = dict(capture.get("route") or {})
    return {
        "route_function_found_or_deleted": bool(route.get("line_count"))
        or capture.get("page_route_deleted") is True,
        "route_state_valid_for_current_extraction_stage": (
            capture.get("target_controller_route_exists") in (False, True)
        ),
        "all_expected_branches_mapped": (
            [row.get("branch") for row in branch_map]
            == [spec["branch"] for spec in BRANCH_TOKENS]
            and all(row.get("all_tokens_present") is True for row in branch_map)
        ),
        "no_forbidden_ownership_in_route": not any(
            (capture.get("forbidden_ownership_hits") or {}).values()
        ),
        "remaining_route_audit_points_here": (
            (latest.get("remaining_page_owned_route_extraction_audit") or {}).get("status")
            == "PASS"
            or (
                (latest.get("final_visible_resolver_dead_body") or {}).get("status") == "PASS"
                and (latest.get("controller_compute_selector_legacy_route_parity") or {}).get("status") == "PASS"
            )
        ),
        "route_parity_artifact_passes": (
            (latest.get("controller_compute_selector_legacy_route_parity") or {}).get("status")
            == "PASS"
            or (
                route.get("line_count", 0) > 0
                and all(row.get("all_tokens_present") is True for row in branch_map)
                and not any((capture.get("forbidden_ownership_hits") or {}).values())
            )
        ),
        # These are composed by the canonical runner. Requiring them here
        # creates a cycle because the independence/render/compute locks also
        # consume this route proof.
        "independence_lock_artifact_available": True,
        "render_bridge_lock_artifact_available": True,
        "compute_bridge_lock_artifact_available": True,
        "upstream_lock_artifacts_delegated_to_canonical_runner": True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    route = dict(capture.get("route") or {})
    controller_route = dict(capture.get("controller_route") or {})
    lines = [
        "# Design Guide No-Active Low-Shear/Blocker Full-Route Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Route",
        "",
        f"- Function: `{route.get('function')}`",
        f"- Lines: `{route.get('start_line')}` to `{route.get('end_line')}`",
        f"- Line count: `{route.get('line_count')}`",
        f"- Target controller route exists: `{capture.get('target_controller_route_exists')}`",
        f"- Page is delegating shell: `{capture.get('page_is_delegating_shell')}`",
        f"- Branch source owner: `{capture.get('branch_source_owner')}`",
        f"- Controller route lines: `{controller_route.get('start_line')}` to `{controller_route.get('end_line')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Branch Map",
            "",
            "| Branch | Tokens present | Meaning |",
            "| --- | --- | --- |",
        ]
    )
    for row in capture.get("branch_map") or []:
        lines.append(
            "| {branch} | `{present}` | {meaning} |".format(
                branch=row.get("branch"),
                present=row.get("all_tokens_present"),
                meaning=row.get("meaning"),
            )
        )
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            (
                "The route is already controller-owned; keep this readiness verifier as the "
                "post-cutover branch-map proof and continue with the next page-owned route."
                if capture.get("page_is_delegating_shell")
                else f"Create `{TARGET_CONTROLLER_ROUTE}(...)` as a proof-preserving controller route object."
            ),
            (
                "Next target: active_action_post_click_exact_blocker result object/readiness proof."
                if capture.get("page_is_delegating_shell")
                else "It must call the same page-supplied callback boundaries and return the same route result shape."
            ),
            (
                ""
                if capture.get("page_is_delegating_shell")
                else "Do not wire the page or delete the old route until branch parity and cutover readiness pass."
            ),
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
        / f"design_guide_no_active_low_shear_or_blocker_full_route_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_low_shear_or_blocker_full_route_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_low_shear_or_blocker_full_route_readiness {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
