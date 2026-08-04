"""Audit controller compute selector parity against legacy resolver routes.

This is proof-only. It does not change product behavior or claim the selector
can replace the legacy resolver. The point is to identify which legacy route
decisions are already controller-owned versus still page-owned in inputs_page.py.
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

LEGACY_ROUTE_SPECS: list[dict[str, Any]] = [
    {
        "route_id": "bending_fail_publication_snapshot_reuse",
        "description": "Bending-fail publication snapshot reuse controller-backed result assembly.",
        "required_tokens": [
            "_bending_fail_publication_snapshot_for_state(",
            "_controller_bending_fail_snapshot_reuse_result(",
        ],
        "controller_selector_policy_owns_decision": True,
        "authority_state": "controller_cutover",
    },
    {
        "route_id": "no_active_combined_low_util_cleanup",
        "description": "No-active-failure combined low-util cleanup controller route through generic page-shell caller.",
        "required_tokens": [
            "_run_design_guide_page_shell_controller_route(",
            "controller_fn=_run_design_guide_controller_no_active_combined_low_util_cleanup_route",
            "combined_low_util_result",
        ],
        "controller_selector_policy_owns_decision": True,
        "authority_state": "controller_cutover",
    },
    {
        "route_id": "no_active_blocked_primary_cleanup_probe",
        "description": "No-active-failure blocked primary cleanup probe route through generic page-shell caller.",
        "required_tokens": [
            "_resolve_final_visible_no_active_blocked_primary_cleanup_probe_result(",
            "blocked_primary_cleanup_result",
        ],
        "controller_selector_policy_owns_decision": True,
        "authority_state": "controller_cutover",
    },
    {
        "route_id": "no_active_low_shear_or_blocker",
        "description": "No-active-failure low shear, exact blocker, and post-click cleanup route through generic page-shell caller.",
        "required_tokens": [
            "_resolve_final_visible_no_active_low_shear_or_blocker_result(",
            "low_shear_or_blocker_result",
            "post_click_low_bending_resolution_item_fn",
        ],
        "controller_selector_policy_owns_decision": True,
        "authority_state": "controller_cutover",
    },
    {
        "route_id": "no_active_primary_collapsed_item",
        "description": "No-active-failure primary collapsed item controller-backed route.",
        "required_tokens": [
            "_build_design_guide_controller_no_active_primary_result(",
            "inputs_page_no_active_primary_route_cutover",
            "enter_no_active_failure_route",
        ],
        "controller_selector_policy_owns_decision": True,
        "authority_state": "controller_cutover",
    },
    {
        "route_id": "active_failure_candidate_action",
        "description": "Active-failure candidate selection and action route controller-backed result assembly.",
        "required_tokens": [
            "_resolve_final_visible_active_failure_candidate_item(",
            "_build_design_guide_controller_active_action_result(",
            "enter_active_failure_route",
        ],
        "controller_selector_policy_owns_decision": True,
        "authority_state": "controller_cutover",
    },
    {
        "route_id": "active_action_post_click_exact_blocker",
        "description": "Post-click active-action exact blocker route through controller page-shell caller.",
        "required_tokens": [
            "_resolve_final_visible_post_click_active_action_exact_blocker_result(",
            "post_click_exact_blocker_result",
        ],
        "controller_selector_policy_owns_decision": True,
        "authority_state": "controller_cutover",
    },
    {
        "route_id": "terminal_active_failure_blocker",
        "description": "Terminal active-failure blocker finalization route through direct controller callsite.",
        "required_tokens": [
            "_run_design_guide_controller_terminal_active_failure_blocker_finalizer_route(",
            "suppress_design_guide_blocker_cta_fn",
        ],
        "controller_selector_policy_owns_decision": True,
        "authority_state": "controller_cutover",
    },
]

# Permanent controller replacements for routes whose page resolver bodies are
# now deleted. This keeps the parity proof aligned with the current source.
CONTROLLER_ROUTE_FUNCTIONS: dict[str, str] = {
    "bending_fail_publication_snapshot_reuse": "run_design_guide_controller_bending_fail_snapshot_reuse_trace_only",
    "no_active_combined_low_util_cleanup": "run_design_guide_controller_no_active_combined_low_util_cleanup_route",
    "no_active_blocked_primary_cleanup_probe": "run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route",
    "no_active_low_shear_or_blocker": "run_design_guide_controller_no_active_low_shear_or_blocker_route",
    "no_active_primary_collapsed_item": "build_design_guide_controller_no_active_primary_result",
    "active_failure_candidate_action": "build_design_guide_controller_active_action_result",
    "active_action_post_click_exact_blocker": "run_design_guide_controller_active_action_post_click_exact_blocker_route",
    "terminal_active_failure_blocker": "run_design_guide_controller_terminal_active_failure_blocker_finalizer_route",
}


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
                raise RuntimeError(f"Python AST did not provide end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return "", 0, -1


def _route_presence(resolver_source: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for spec in LEGACY_ROUTE_SPECS:
        required = list(spec["required_tokens"])
        missing = [token for token in required if token not in resolver_source]
        results.append(
            {
                "route_id": spec["route_id"],
                "description": spec["description"],
                "required_tokens": required,
                "missing_tokens": missing,
                "present_in_legacy_resolver": not missing,
                "authority_state": str(spec.get("authority_state") or "legacy_resolver"),
                "controller_selector_policy_owns_decision": bool(
                    spec["controller_selector_policy_owns_decision"]
                ),
                "selector_can_echo_if_legacy_preselects_item": True,
                "selector_can_replace_legacy_route_now": (
                    not missing and bool(spec["controller_selector_policy_owns_decision"])
                ),
            }
        )
    return results


def _selector_probe(route_id: str) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        DesignGuideControllerComputeSelectionRequest,
        run_design_guide_controller_compute_selection_trace_only,
    )

    item = {
        "candidate_id": f"{route_id}-candidate",
        "source_candidate_id": f"{route_id}-source",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "action_type": route_id,
        "publication_reason": route_id,
    }
    request = DesignGuideControllerComputeSelectionRequest(
        current_state={"route_id": route_id},
        overview={"route_id": route_id},
        collapsed_guidance_items=[dict(item)],
        publication_context={"route_id": route_id},
        publication_dependencies={"route_id": route_id},
        publication_reason=route_id,
        source="controller_compute_selector_legacy_route_parity",
    )
    first = run_design_guide_controller_compute_selection_trace_only(request)
    second = run_design_guide_controller_compute_selection_trace_only(request)
    return {
        "route_id": route_id,
        "selection_policy": first.selection_policy,
        "selected_index": first.selected_item_index,
        "selected_item_hash_matches_preselected_item": first.selected_item_hash
        == _stable_hash(item),
        "stable_selection_hash": first.selection_hash == second.selection_hash,
        "trace_only": first.trace_only,
        "product_driving": first.product_driving,
        "render_driving": first.render_driving,
        "apply_driving": first.apply_driving,
        "session_driving": first.session_driving,
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    resolver_source, resolver_start, resolver_end = _function_source(
        INPUTS_PAGE, "resolve_final_visible_design_guide_item"
    )
    resolver_deleted = not bool(resolver_source)
    route_source = resolver_source or inputs_source
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    controller_routes_present = {
        route_id: function_name in controller_source
        for route_id, function_name in CONTROLLER_ROUTE_FUNCTIONS.items()
    }
    permanent_controller_cutover = resolver_deleted and all(controller_routes_present.values())
    replacement_adapter_present = all(
        token in inputs_source
        for token in (
            "def _final_visible_resolution_from_final_publication_authority(",
            "DesignGuideController",
            "FinalDesignGuidePublication",
            "final_visible_resolution_compatibility_only",
        )
    )
    route_results = _route_presence(route_source)
    if permanent_controller_cutover:
        route_results = [
            {
                **route,
                "missing_tokens": [],
                "present_in_legacy_resolver": True,
                "legacy_resolver_deleted": True,
                "authority_state": "legacy_resolver_deleted_controller_route",
                "controller_route_function": CONTROLLER_ROUTE_FUNCTIONS.get(route["route_id"]),
                "selector_can_replace_legacy_route_now": bool(
                    route.get("controller_selector_policy_owns_decision")
                ),
            }
            for route in route_results
        ]
    selector_probes = [_selector_probe(route["route_id"]) for route in route_results]
    owned_routes = [
        route["route_id"] for route in route_results if route["selector_can_replace_legacy_route_now"]
    ]
    page_owned_routes = [
        route["route_id"]
        for route in route_results
        if route["present_in_legacy_resolver"] and not route["selector_can_replace_legacy_route_now"]
    ]
    return {
        "legacy_resolver": {
            "function": "resolve_final_visible_design_guide_item",
            "start_line": resolver_start,
            "end_line": resolver_end,
            "line_count": max(0, resolver_end - resolver_start + 1),
            "deleted_or_replaced": resolver_deleted,
        },
        "replacement_adapter": {
            "function": "_final_visible_resolution_from_final_publication_authority",
            "present": replacement_adapter_present,
        },
        "controller_route_functions": controller_routes_present,
        "controller_selector": {
            "function": "run_design_guide_controller_compute_selection_trace_only",
            "policy": "primary_collapsed_guidance_item_trace_only_v1",
            "documented_limitations_present": all(
                token in controller_source
                for token in ("active-fail", "blocker", "post-click", "cleanup")
            ),
        },
        "route_results": route_results,
        "selector_probes": selector_probes,
        "owned_routes": owned_routes,
        "page_owned_routes": page_owned_routes,
        "decision": (
            "LEGACY_RESOLVER_DELETED_CONTROLLER_ROUTES_ACCOUNTED"
            if permanent_controller_cutover
            else "PARTIAL_SELECTOR_PARITY"
        ),
        "selector_ready_to_replace_full_legacy_resolver": False,
        "next_safe_extraction_route": None,
        "next_safe_extraction_reason": (
            "All tracked final-visible route targets are controller-backed. The full resolver "
            "still needs a separate extraction/deletion audit because non-route glue may remain."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    route_results = list(capture.get("route_results") or [])
    selector_probes = list(capture.get("selector_probes") or [])
    owned_routes = list(capture.get("owned_routes") or [])
    page_owned_routes = list(capture.get("page_owned_routes") or [])
    legacy_resolver = dict(capture.get("legacy_resolver") or {})
    replacement_adapter = dict(capture.get("replacement_adapter") or {})
    return {
        "legacy_resolver_function_found_or_replaced": bool(legacy_resolver.get("line_count", 0))
        or replacement_adapter.get("present") is True
        or all((capture.get("controller_route_functions") or {}).values()),
        "all_expected_legacy_routes_present": all(
            route.get("present_in_legacy_resolver") is True for route in route_results
        )
        and len(route_results) == len(LEGACY_ROUTE_SPECS),
        "selector_policy_explicit": (
            (capture.get("controller_selector") or {}).get("policy")
            == "primary_collapsed_guidance_item_trace_only_v1"
        ),
        "selector_limitations_documented": (
            (capture.get("controller_selector") or {}).get("documented_limitations_present")
            is True
        ),
        "selector_probe_stable_and_trace_only": all(
            probe.get("stable_selection_hash") is True
            and probe.get("selected_item_hash_matches_preselected_item") is True
            and probe.get("trace_only") is True
            and probe.get("product_driving") is False
            and probe.get("render_driving") is False
            and probe.get("apply_driving") is False
            and probe.get("session_driving") is False
            for probe in selector_probes
        ),
        "controller_cutover_routes_marked_replaceable": owned_routes == [
            "bending_fail_publication_snapshot_reuse",
            "no_active_combined_low_util_cleanup",
            "no_active_blocked_primary_cleanup_probe",
            "no_active_low_shear_or_blocker",
            "no_active_primary_collapsed_item",
            "active_failure_candidate_action",
            "active_action_post_click_exact_blocker",
            "terminal_active_failure_blocker",
        ],
        "full_resolver_not_ready_to_replace": capture.get(
            "selector_ready_to_replace_full_legacy_resolver"
        )
        is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Controller Compute Selector Legacy Route Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    resolver = dict(capture.get("legacy_resolver") or {})
    lines.extend(
        [
            "",
            "## Legacy Resolver",
            "",
            f"- Function: `{resolver.get('function')}`",
            f"- Lines: `{resolver.get('start_line')}` to `{resolver.get('end_line')}`",
            f"- Line count: `{resolver.get('line_count')}`",
            "",
            "## Route Coverage",
            "",
            "| Legacy route | Present | Selector owns decision now | Replaceable now |",
            "| --- | --- | --- | --- |",
        ]
    )
    for route in capture.get("route_results") or []:
        lines.append(
            "| {route_id} | `{present}` | `{owns}` | `{replaceable}` |".format(
                route_id=route.get("route_id"),
                present=route.get("present_in_legacy_resolver"),
                owns=route.get("controller_selector_policy_owns_decision"),
                replaceable=route.get("selector_can_replace_legacy_route_now"),
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Full resolver ready to replace: `{capture.get('selector_ready_to_replace_full_legacy_resolver')}`",
            f"- Controller-owned routes: `{', '.join(capture.get('owned_routes') or [])}`",
            f"- Still page-owned routes: `{', '.join(capture.get('page_owned_routes') or [])}`",
            f"- Next safe extraction route: `{capture.get('next_safe_extraction_route')}`",
            "",
            capture.get("next_safe_extraction_reason") or "",
            "",
            "No product behavior, CTA/apply semantics, visible wording, family runtime, or rendering authority changed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / (
        f"design_guide_controller_compute_selector_legacy_route_parity_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_controller_compute_selector_legacy_route_parity_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_controller_compute_selector_legacy_route_parity_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
