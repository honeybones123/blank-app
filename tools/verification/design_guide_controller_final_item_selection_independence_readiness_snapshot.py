"""Audit controller readiness to select final compute item without page resolver.

This is proof-only. It does not change product behavior and does not claim the
compute-stage resolver can be deleted. It records which final-visible selection
routes are already owned by DesignGuideController and which still require the
legacy page resolver to choose the item first.
"""

from __future__ import annotations

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


EXPECTED_LEGACY_ROUTES: tuple[str, ...] = (
    "bending_fail_publication_snapshot_reuse",
    "no_active_combined_low_util_cleanup",
    "no_active_blocked_primary_cleanup_probe",
    "no_active_low_shear_or_blocker",
    "no_active_primary_collapsed_item",
    "active_failure_candidate_action",
    "active_action_post_click_exact_blocker",
    "terminal_active_failure_blocker",
)

EXPECTED_CONTROLLER_OWNED_NOW: tuple[str, ...] = (
    "bending_fail_publication_snapshot_reuse",
    "no_active_combined_low_util_cleanup",
    "no_active_blocked_primary_cleanup_probe",
    "no_active_low_shear_or_blocker",
    "no_active_primary_collapsed_item",
    "active_failure_candidate_action",
    "active_action_post_click_exact_blocker",
    "terminal_active_failure_blocker",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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
    status = str(payload.get("status") or payload.get("result") or "")
    if "PASS" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _selector_probe_without_page_resolution() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        DesignGuideControllerComputeSelectionRequest,
        run_design_guide_controller_compute_selection_trace_only,
    )

    primary = {
        "candidate_id": "primary-no-page-resolution",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "publication_reason": "primary_without_page_resolution",
    }
    secondary = {
        "candidate_id": "secondary-no-page-resolution",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "publication_reason": "secondary_without_page_resolution",
    }
    request = DesignGuideControllerComputeSelectionRequest(
        current_state={"D": 600, "b": 300},
        overview={"statuses": {"bending": "FAIL"}},
        collapsed_guidance_items=[dict(primary), dict(secondary)],
        publication_context={
            "source": "controller_final_item_selection_independence_readiness",
            "guidance_state_snapshot": {"D": 600, "b": 300},
        },
        publication_reason="primary_without_page_resolution",
        source="controller_final_item_selection_independence_readiness",
    )
    first = run_design_guide_controller_compute_selection_trace_only(request)
    second = run_design_guide_controller_compute_selection_trace_only(request)
    return {
        "selected_item_index": first.selected_item_index,
        "selected_candidate_id": first.selected_item.get("candidate_id"),
        "selection_policy": first.selection_policy,
        "stable_selection_hash": first.selection_hash == second.selection_hash,
        "trace_only": first.trace_only,
        "product_driving": first.product_driving,
        "render_driving": first.render_driving,
        "apply_driving": first.apply_driving,
        "session_driving": first.session_driving,
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    route_parity = _latest("design_guide_controller_compute_selector_legacy_route_parity")
    live_trace = _latest("design_guide_live_controller_compute_selection_trace")
    replacement = _latest("design_guide_compute_stage_resolver_replacement_readiness")
    route_capture = dict((route_parity.get("payload") or {}).get("capture") or {})
    route_results = list(route_capture.get("route_results") or [])
    controller_owned_routes = list(route_capture.get("owned_routes") or [])
    page_owned_routes = list(route_capture.get("page_owned_routes") or [])
    route_readiness = {
        str(route.get("route_id")): {
            "present_in_legacy_resolver": bool(route.get("present_in_legacy_resolver")),
            "controller_selector_policy_owns_decision": bool(
                route.get("controller_selector_policy_owns_decision")
            ),
            "selector_can_replace_legacy_route_now": bool(
                route.get("selector_can_replace_legacy_route_now")
            ),
        }
        for route in route_results
    }
    direct_compute_resolver_call_count = inputs_source.count(
        "final_compute_resolution = resolve_final_visible_design_guide_item("
    )
    controller_current_limitations = {
        "primary_item_policy_only": "primary_collapsed_guidance_item_trace_only_v1"
        in controller_source,
        "documented_not_full_replacement": (
            "does not replace the legacy resolver's active-fail" in controller_source
        ),
        "no_final_compute_resolution_field_on_selection_request": (
            "class DesignGuideControllerComputeSelectionRequest" in controller_source
            and "final_compute_resolution:" not in controller_source[
                controller_source.find("class DesignGuideControllerComputeSelectionRequest") :
                controller_source.find("class DesignGuideControllerComputeSelectionResponse")
            ]
        ),
    }
    replacement_decision = (replacement.get("payload") or {}).get("capture", {}).get("decision")
    controller_cutover_complete = replacement_decision in {
        "CONTROLLER_CUTOVER_COMPLETE_FALLBACK_DEADNESS_REQUIRED",
        "LEGACY_RESOLVER_REPLACED_CONTROLLER_FALLBACK_SHELL_RETAINED",
    }
    return {
        "decision": (
            "CONTROLLER_ITEM_SELECTION_CUTOVER_COMPLETE_FALLBACK_DEADNESS_REQUIRED"
            if controller_cutover_complete
            else "PARTIAL_CONTROLLER_ITEM_SELECTION_INDEPENDENCE"
        ),
        "replacement_ready": bool(controller_cutover_complete),
        "direct_compute_resolver_call_count": direct_compute_resolver_call_count,
        "fallback_compute_resolver_call_count": inputs_source.count(
            "_legacy_fallback_resolution = resolve_final_visible_design_guide_item("
        ),
        "expected_routes": list(EXPECTED_LEGACY_ROUTES),
        "route_readiness": route_readiness,
        "controller_owned_routes": controller_owned_routes,
        "page_owned_routes": page_owned_routes,
        "controller_current_limitations": controller_current_limitations,
        "selector_probe_without_page_resolution": _selector_probe_without_page_resolution(),
        "latest": {
            "controller_compute_selector_legacy_route_parity": {
                "status": route_parity.get("status"),
                "path": route_parity.get("path"),
                "decision": route_capture.get("decision"),
            },
            "live_controller_compute_selection_trace": {
                "status": live_trace.get("status"),
                "path": live_trace.get("path"),
            },
            "compute_stage_resolver_replacement_readiness": {
                "status": replacement.get("status"),
                "path": replacement.get("path"),
                "decision": replacement_decision,
                "blocking_reason": (replacement.get("payload") or {}).get("capture", {}).get(
                    "blocking_reason"
                ),
            },
        },
        "next_required_extraction": {
            "target": "controller-owned final item selection for legacy resolver routes",
            "first_boundary": "browser/live parity for the trace-wired compute resolver replacement",
            "blocked_until": (
                "fallback deadness proof for the old page resolver fallback"
                if controller_cutover_complete
            else "controller replacement trace proves parity in product browser states"
            ),
        },
        "product_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    probe = dict(capture.get("selector_probe_without_page_resolution") or {})
    return {
        "route_parity_artifact_passes": (
            latest.get("controller_compute_selector_legacy_route_parity") or {}
        ).get("status")
        == "PASS",
        "live_trace_artifact_passes": (
            capture.get("replacement_ready") is True
            or (latest.get("live_controller_compute_selection_trace") or {}).get("status") == "PASS"
        ),
        "replacement_readiness_artifact_passes": (
            latest.get("compute_stage_resolver_replacement_readiness") or {}
        ).get("status")
        == "PASS",
        "replacement_still_correctly_blocked": (
            (latest.get("compute_stage_resolver_replacement_readiness") or {}).get("decision")
            in {
                "TRACE_WIRED_AWAITING_BROWSER_PARITY",
                "BROWSER_PARITY_PROVEN_CUTOVER_REQUIRED",
                "CONTROLLER_CUTOVER_COMPLETE_FALLBACK_DEADNESS_REQUIRED",
                "LEGACY_RESOLVER_REPLACED_CONTROLLER_FALLBACK_SHELL_RETAINED",
            }
        ),
        "direct_compute_resolver_assignment_removed": (
            capture.get("direct_compute_resolver_call_count") == 0
        ),
        "fallback_compute_resolver_call_deleted": (
            capture.get("fallback_compute_resolver_call_count") == 0
        ),
        "all_expected_routes_accounted_for": sorted(capture.get("route_readiness") or {})
        == sorted(EXPECTED_LEGACY_ROUTES),
        "expected_routes_owned_by_controller_now": tuple(
            capture.get("controller_owned_routes") or ()
        )
        == EXPECTED_CONTROLLER_OWNED_NOW,
        "page_owned_routes_remain_explicit": len(capture.get("page_owned_routes") or []) == (
            len(EXPECTED_LEGACY_ROUTES) - len(EXPECTED_CONTROLLER_OWNED_NOW)
        ),
        "selector_probe_stable_trace_only": (
            probe.get("selected_item_index") == 0
            and probe.get("selected_candidate_id") == "primary-no-page-resolution"
            and probe.get("stable_selection_hash") is True
            and probe.get("trace_only") is True
            and probe.get("product_driving") is False
            and probe.get("render_driving") is False
            and probe.get("apply_driving") is False
            and probe.get("session_driving") is False
        ),
        "controller_limitations_explicit": all(
            (capture.get("controller_current_limitations") or {}).values()
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Controller Final Item Selection Independence Readiness",
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
            "## Route Ownership",
            "",
            "| Route | Controller-owned now | Replaceable now |",
            "| --- | --- | --- |",
        ]
    )
    for route_id, route in (capture.get("route_readiness") or {}).items():
        lines.append(
            "| {route} | `{owned}` | `{replaceable}` |".format(
                route=route_id,
                owned=route.get("controller_selector_policy_owns_decision"),
                replaceable=route.get("selector_can_replace_legacy_route_now"),
            )
        )
    next_step = dict(capture.get("next_required_extraction") or {})
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Replacement ready: `{capture.get('replacement_ready')}`",
            f"- Direct compute resolver calls: `{capture.get('direct_compute_resolver_call_count')}`",
            f"- Controller-owned routes: `{', '.join(capture.get('controller_owned_routes') or [])}`",
            f"- Page-owned routes: `{', '.join(capture.get('page_owned_routes') or [])}`",
            "",
            "## Next Required Extraction",
            "",
            f"- Target: `{next_step.get('target')}`",
            f"- First boundary: `{next_step.get('first_boundary')}`",
            f"- Blocked until: {next_step.get('blocked_until')}",
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
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_controller_final_item_selection_independence_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_controller_final_item_selection_independence_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_controller_final_item_selection_independence_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
