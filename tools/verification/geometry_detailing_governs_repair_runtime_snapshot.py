"""Verify GEOMETRY_DETAILING_GOVERNS has a real repair runtime.

The family owns the D/b repair decision. inputs_page remains responsible for
binding/rendering/apply routing through the existing Design Guide surfaces.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.families.geometry_detailing import (  # noqa: E402
    FAMILY_ID,
    evaluate_geometry_detailing_governs,
    run_geometry_detailing_governs_runtime,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
ROUTE_COORDINATOR = ROOT / "inputs_page_route_coordinators.py"
APPLY_ROUTING = ROOT / "inputs_page_modules" / "apply_routing.py"
APPLY_GUIDANCE_ACTION = ROOT / "inputs_page_modules" / "apply_guidance_action.py"
GOVERNING_STATE = ROOT / "design_brain" / "governing_state.py"
PUBLICATION = ROOT / "design_brain" / "publication.py"
FAMILY_REGISTRY = ROOT / "design_brain" / "families" / "registry.py"
GEOMETRY_MODULE = ROOT / "design_brain" / "families" / "geometry_detailing.py"


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _runtime_cases() -> list[dict[str, Any]]:
    cases = []
    invalid = run_geometry_detailing_governs_runtime({"sec_shape": "RECT", "b": 300.0, "D": 850.0})
    invalid_selected = dict(invalid.selected_recommendation or {})
    invalid_updates = dict(invalid_selected.get("updates") or {})
    invalid_failures = []
    if invalid.status != "ACTION":
        invalid_failures.append(f"invalid_expected_ACTION_got_{invalid.status}")
    if invalid_updates.get("b") != 430.0:
        invalid_failures.append(f"invalid_expected_b_430_got_{invalid_updates.get('b')}")
    if float(invalid_selected.get("depth_width_ratio_after") or 999.0) > 2.0 + 1e-9:
        invalid_failures.append("invalid_update_still_exceeds_ratio")
    cases.append(
        {
            "case_id": "invalid_rect_300x850_width_rescue",
            "status": invalid.status,
            "updates": invalid_updates,
            "selected_strategy_lane": invalid.selected_strategy_lane,
            "runtime_hash": invalid.runtime_hash,
            "failures": invalid_failures,
        }
    )

    valid = run_geometry_detailing_governs_runtime({"sec_shape": "RECT", "b": 300.0, "D": 600.0})
    valid_failures = []
    if valid.status != "NOT_APPLICABLE":
        valid_failures.append(f"valid_expected_NOT_APPLICABLE_got_{valid.status}")
    cases.append(
        {
            "case_id": "valid_rect_300x600_no_action",
            "status": valid.status,
            "updates": dict((valid.selected_recommendation or {}).get("updates") or {}),
            "runtime_hash": valid.runtime_hash,
            "failures": valid_failures,
        }
    )

    locked = run_geometry_detailing_governs_runtime(
        {"sec_shape": "RECT", "b": 300.0, "D": 850.0},
        constraints={"width_locked": True},
    )
    locked_failures = []
    if locked.status != "BLOCKED":
        locked_failures.append(f"locked_expected_BLOCKED_got_{locked.status}")
    if locked.selected_recommendation:
        locked_failures.append("locked_unexpected_selected_recommendation")
    cases.append(
        {
            "case_id": "invalid_rect_300x850_width_locked",
            "status": locked.status,
            "blocked_reason": locked.blocked_reason,
            "runtime_hash": locked.runtime_hash,
            "failures": locked_failures,
        }
    )

    family_result = evaluate_geometry_detailing_governs(
        {"base_state": {"sec_shape": "RECT", "b": 300.0, "D": 850.0}}
    )
    family_failures = []
    if family_result.family_id != FAMILY_ID:
        family_failures.append("family_result_wrong_family")
    if family_result.status != "ACTION":
        family_failures.append(f"family_result_expected_ACTION_got_{family_result.status}")
    if family_result.updates.get("b") != 430.0:
        family_failures.append(f"family_result_expected_b_430_got_{family_result.updates.get('b')}")
    cases.append(
        {
            "case_id": "family_result_adapter",
            "status": family_result.status,
            "updates": dict(family_result.updates),
            "lock_proof": dict(family_result.lock_proof),
            "failures": family_failures,
        }
    )
    return cases


def _static_checks() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    route_source = ROUTE_COORDINATOR.read_text(encoding="utf-8")
    apply_routing_source = APPLY_ROUTING.read_text(encoding="utf-8")
    apply_guidance_source = APPLY_GUIDANCE_ACTION.read_text(encoding="utf-8")
    governing_source = GOVERNING_STATE.read_text(encoding="utf-8")
    publication_source = PUBLICATION.read_text(encoding="utf-8")
    registry_source = FAMILY_REGISTRY.read_text(encoding="utf-8")
    geometry_source = GEOMETRY_MODULE.read_text(encoding="utf-8")
    checks = {
        "family_runtime_exists": "def run_geometry_detailing_governs_runtime" in geometry_source,
        "family_public_api_exists": "def evaluate_geometry_detailing_governs" in geometry_source,
        "family_uses_contract_ratio_helper": "bending_depth_width_ratio_limit" in geometry_source,
        "family_does_not_import_inputs_page": "inputs_page" not in geometry_source,
        "family_does_not_import_streamlit": "streamlit" not in geometry_source and "import st" not in geometry_source,
        "inputs_imports_family_api": "GeometryDetailingFamily" in registry_source
        and '"GEOMETRY_DETAILING_GOVERNS"' in registry_source,
        "inputs_has_guidance_adapter": "geometry_detailing_action" in publication_source
        and '"GEOMETRY_DETAILING_GOVERNS"' in publication_source,
        "inputs_early_dispatch_geometry": 'governing_state = "GEOMETRY_DETAILING_GOVERNS"' in governing_source,
        "inputs_uses_existing_apply_binding": "handle_inputs_apply_buttons" in route_source
        and "def handle_inputs_apply_buttons" in apply_routing_source
        and "def apply_guidance_action" in apply_guidance_source
        and "apply_resolved_candidate" in apply_guidance_source,
        "inputs_does_not_move_render_apply_ownership": "apply_resolved_candidate" not in inputs_source
        and "handle_inputs_apply_buttons" not in inputs_source
        and "render_inputs_page" in inputs_source,
    }
    return {
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "hash": _stable_hash(checks),
    }


def _report(payload: dict[str, Any]) -> str:
    case_rows = [
        f"| `{case['case_id']}` | `{case.get('status')}` | `{case.get('updates')}` | {'PASS' if not case['failures'] else 'FAIL'} |"
        for case in payload["cases"]
    ]
    check_rows = [
        f"- `{name}`: {'PASS' if ok else 'FAIL'}"
        for name, ok in payload["static_checks"]["checks"].items()
    ]
    failures = [f"- `{failure}`" for failure in payload["failures"]] or ["- None"]
    return "\n".join(
        [
            "# GEOMETRY_DETAILING_GOVERNS Repair Runtime Snapshot",
            "",
            f"Result: `{payload['status']}`",
            "",
            "## Runtime Cases",
            "",
            "| Case | Status | Updates | Result |",
            "| --- | --- | --- | --- |",
            *case_rows,
            "",
            "## Static Checks",
            "",
            *check_rows,
            "",
            "## Ownership",
            "",
            "- Family owns D/b repair decision and selected update.",
            "- inputs_page owns guidance item adaptation plus existing CTA/apply/render binding.",
            "- No family import of inputs_page, Streamlit, session, rendering, or apply routing.",
            "",
            "## Failures",
            "",
            *failures,
        ]
    )


def main() -> int:
    generated_at = time.strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    cases = _runtime_cases()
    static_checks = _static_checks()
    failures: list[str] = []
    for case in cases:
        failures.extend(f"{case['case_id']}:{failure}" for failure in case["failures"])
    failures.extend(f"static:{failure}" for failure in static_checks["failures"])
    payload = {
        "schema": "geometry_detailing_governs_repair_runtime_snapshot.v1",
        "generated_at": generated_at,
        "status": "PASS" if not failures else "FAIL",
        "family_id": FAMILY_ID,
        "cases": cases,
        "static_checks": static_checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"cases": cases, "static_checks": static_checks}),
    }
    json_path = ARTIFACT_DIR / f"geometry_detailing_governs_repair_runtime_{generated_at}.json"
    report_path = AUDIT_DIR / f"geometry_detailing_governs_repair_runtime_{generated_at}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(_report(payload), encoding="utf-8")
    print(f"geometry_detailing_governs_repair_runtime_snapshot {payload['status']}")
    print(f"json: {json_path}")
    print(f"report: {report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
