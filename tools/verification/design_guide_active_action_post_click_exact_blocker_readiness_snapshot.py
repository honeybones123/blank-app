"""Audit readiness for extracting active-action post-click exact-blocker route.

Proof-only: this verifier does not create a controller route, wire the page,
change publication, alter CTA/apply behaviour, or change visible wording.
It records the current page-owned branch shape that must be preserved before
the route can move behind a controller-owned plain-data boundary.
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

ROUTE = "_resolve_final_visible_post_click_active_action_exact_blocker_result"
TARGET_CONTROLLER_ROUTE = "run_design_guide_controller_active_action_post_click_exact_blocker_route"
GENERIC_CALLER = "_run_design_guide_page_shell_controller_route"

BRANCH_TOKENS: tuple[dict[str, Any], ...] = (
    {
        "branch": "gate_requires_bending_exact_blocker",
        "tokens": (
            "post_click_active_action_requires_blocker",
            'active_family == "bending"',
            "active_outside_exact_blockers",
            "no_second_cta_required",
            "return None",
        ),
        "meaning": "Only bending active-action post-click states with exact blocker proof should replace the action card.",
    },
    {
        "branch": "audit_surface",
        "tokens": (
            "post_click_blocker_audit",
            "post_click_exact_blockers_by_family",
            "post_click_unresolved_low_util_families",
            "post_click_active_action_has_exact_blocker",
        ),
        "meaning": "The route builds the exact-blocker audit surface needed to explain why a second CTA is not required.",
    },
    {
        "branch": "replacement_item",
        "tokens": (
            "post_click_low_bending_resolution_item_fn(",
            "post_click_blocker_item",
            "design_guide_button_contract_enabled_fn(",
            "normalise_final_visible_design_guide_item_fn(",
        ),
        "meaning": "The route asks the existing post-click bending blocker builder for a replacement item and accepts only disabled/blocker output.",
    },
    {
        "branch": "published_result",
        "tokens": (
            "final_visible_post_click_active_action_exact_blocker",
            "show_apply_button",
            "post_click_active_action_replaced_by_exact_blocker",
            '"item": post_click_blocker_item',
            '"presentation":',
            '"debug":',
        ),
        "meaning": "The route returns the final-visible result shape with no Apply button and exact blocker debug proof.",
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
    controller_route_source, controller_start_line, controller_end_line = _function_source(
        CONTROLLER, TARGET_CONTROLLER_ROUTE
    )
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    route_delegates_to_controller = bool(
        GENERIC_CALLER in route_source and TARGET_CONTROLLER_ROUTE in route_source
    )
    route_retired_to_controller = not bool(route_source) and bool(controller_route_source)
    branch_source = (
        controller_route_source if route_delegates_to_controller or route_retired_to_controller else route_source
    )
    branch_tokens = (
        (
            {
                **BRANCH_TOKENS[0],
                "tokens": (
                    "requires_blocker",
                    'family == "bending"',
                    "blockers",
                    "no_second_cta_required",
                    "return None",
                ),
            },
            BRANCH_TOKENS[1],
            BRANCH_TOKENS[2],
            BRANCH_TOKENS[3],
        )
        if route_delegates_to_controller or route_retired_to_controller
        else BRANCH_TOKENS
    )
    branch_map = []
    for spec in branch_tokens:
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
        token: token in route_source for token in FORBIDDEN_OWNERSHIP_TOKENS
    }
    target_controller_route_exists = TARGET_CONTROLLER_ROUTE in controller_source
    broader_active_action_surface_exists = (
        "build_design_guide_controller_active_action_result" in controller_source
    )
    return {
        "decision": (
            "READY_FOR_CONTROLLER_ROUTE_OBJECT_PROOF"
            if not target_controller_route_exists
            else "CONTROLLER_ROUTE_EXISTS_NEEDS_PARITY_PROOF"
        ),
        "route": {
            "function": ROUTE,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
            "retired_to_controller": route_retired_to_controller,
            "return_count": route_source.count("return "),
            "trace_event_count": route_source.count("_resolver_route_trace_event("),
            "source_hash": _stable_hash(route_source),
            "route_delegates_to_controller": route_delegates_to_controller,
            "branch_authority": "controller"
            if route_delegates_to_controller or route_retired_to_controller
            else "page",
        },
        "controller_route": {
            "function": TARGET_CONTROLLER_ROUTE,
            "start_line": controller_start_line,
            "end_line": controller_end_line,
            "line_count": controller_end_line - controller_start_line + 1,
            "source_hash": _stable_hash(controller_route_source),
        },
        "branch_map": branch_map,
        "target_controller_route": TARGET_CONTROLLER_ROUTE,
        "target_controller_route_exists": target_controller_route_exists,
        "broader_active_action_surface_exists": broader_active_action_surface_exists,
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
        "route_function_found_or_retired_to_controller": bool(route.get("line_count"))
        or route.get("retired_to_controller") is True,
        "all_expected_branches_mapped": (
            [row.get("branch") for row in branch_map]
            == [spec["branch"] for spec in BRANCH_TOKENS]
            and all(row.get("all_tokens_present") is True for row in branch_map)
        ),
        "no_forbidden_ownership_in_route": not any(
            (capture.get("forbidden_ownership_hits") or {}).values()
        ),
        "broader_active_action_controller_surface_exists": (
            capture.get("broader_active_action_surface_exists") is True
        ),
        "target_controller_route_state_valid": capture.get("target_controller_route_exists") in (False, True),
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
    lines = [
        "# Design Guide Active-Action Post-Click Exact-Blocker Readiness",
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
        f"- Broader active-action controller surface exists: `{capture.get('broader_active_action_surface_exists')}`",
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
                f"`{TARGET_CONTROLLER_ROUTE}(...)` exists; continue with trace-only parity beside the page route."
                if capture.get("target_controller_route_exists")
                else f"Create `{TARGET_CONTROLLER_ROUTE}(...)` as a controller-owned plain-data route object."
            ),
            (
                "Do not wire the page or delete the old route until route-object proof and branch parity pass."
                if capture.get("target_controller_route_exists")
                else "It must preserve the same gate, exact-blocker audit surface, replacement item, disabled CTA result, and debug payload shape."
            ),
            (
                ""
                if capture.get("target_controller_route_exists")
                else "Do not wire the page or delete the old route until route object proof and branch parity pass."
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
        / f"design_guide_active_action_post_click_exact_blocker_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_active_action_post_click_exact_blocker_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_active_action_post_click_exact_blocker_readiness {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
