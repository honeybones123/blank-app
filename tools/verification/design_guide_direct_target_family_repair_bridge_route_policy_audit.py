from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

TARGET = "_direct_target_band_guidance_item"


TOKENS = {
    "controller_owned_route_policy": [
        "_resolve_design_guide_controller_direct_target_active_failure_route_policy(",
    ],
    "controller_owned_route_projection": [
        "_build_design_guide_controller_direct_target_active_failure_route_request_result_adapter(",
        "_build_design_guide_controller_direct_target_combined_family_bypass_evidence_projection(",
    ],
    "page_owned_family_bridge_execution": [
        "_active_fail_near_current_repair_item(",
    ],
    "page_owned_debug_and_cta_recording": [
        "debug_sink.update(",
        "direct_target_active_failure_route_adapter_trace",
        "_record_bending_fail_valid_repair_cta_published(",
        "generic_target_band_search_skipped",
        "direct_target_band_bypassed_by_family_owner",
    ],
    "hardcoded_family_route_metadata": [
        "BENDING_FAIL_GOVERNS",
        "SHEAR_FAIL_GOVERNS",
        "COMBINED_BENDING_SHEAR_FAIL",
        "family_route_owner=",
        "skipped_reason=",
    ],
    "legacy_page_candidate_evaluator": [
        "_evaluate_auto_design_candidate(",
        "evaluate_candidate_full(",
    ],
    "candidate_evaluation_service_call": [
        "_evaluate_direct_target_band_candidate_with_service(",
    ],
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _token_matches(segment: str, start_line: int) -> dict[str, Any]:
    matches: dict[str, Any] = {}
    for category, tokens in TOKENS.items():
        found = []
        for token in tokens:
            lines = _line_numbers(segment, start_line, token)
            if lines:
                found.append({"token": token, "count": len(lines), "lines": lines[:30]})
        matches[category] = {"present": bool(found), "matches": found}
    return matches


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    matches = _token_matches(segment, start)

    controller_import_clean = all(
        token not in controller_source
        for token in (
            "import inputs_page",
            "from inputs_page",
            "import streamlit",
            "from streamlit",
            "st.session_state",
        )
    )
    controller_exports_policy = "resolve_design_guide_controller_direct_target_active_failure_route_policy" in controller_source
    controller_exports_adapter = (
        "build_design_guide_controller_direct_target_active_failure_route_request_result_adapter" in controller_source
    )
    legacy_evaluator_absent = not matches["legacy_page_candidate_evaluator"]["present"]
    candidate_service_present = matches["candidate_evaluation_service_call"]["present"]

    route_branches = {
        "bending": 'if _active_failure_route_kind == "bending"' in segment,
        "shear": 'if _active_failure_route_kind == "shear"' in segment,
        "combined": 'if _active_failure_route_kind == "combined"' in segment,
    }

    first_slice_ready = all(
        (
            bool(segment),
            controller_import_clean,
            controller_exports_policy,
            controller_exports_adapter,
            matches["controller_owned_route_policy"]["present"],
            matches["controller_owned_route_projection"]["present"],
            matches["page_owned_family_bridge_execution"]["present"],
            matches["page_owned_debug_and_cta_recording"]["present"],
            legacy_evaluator_absent,
            candidate_service_present,
        )
    )

    decision = (
        "READY_FOR_ROUTE_BRIDGE_PROJECTION_ADAPTER_EXTRACTION"
        if first_slice_ready
        else "NOT_READY_WITH_EXACT_REMAINING_SURFACE"
    )

    return {
        "schema": "design_guide_direct_target_family_repair_bridge_route_policy_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "decision": decision,
        "matches": matches,
        "route_branches": route_branches,
        "classification": {
            "controller_owned_route_policy": {
                "owner": "design_brain.design_guide_controller",
                "evidence": matches["controller_owned_route_policy"],
                "status": "already_controller_owned",
            },
            "controller_owned_route_projection": {
                "owner": "design_brain.design_guide_controller",
                "evidence": matches["controller_owned_route_projection"],
                "status": "already_controller_owned_but_page_orchestrated",
            },
            "family_bridge_execution": {
                "owner": "inputs_page.py page shell for now",
                "target_owner": "DesignGuideController adapter only after callback boundary proof",
                "evidence": matches["page_owned_family_bridge_execution"],
                "status": "page_owned_callback_execution_not_deletion_ready",
            },
            "debug_and_cta_recording": {
                "owner": "inputs_page.py page shell",
                "target_owner": "page shell or non-authoritative debug/proof service",
                "evidence": matches["page_owned_debug_and_cta_recording"],
                "status": "page_side_effect_not_publication_authority",
            },
            "family_route_metadata": {
                "owner": "inputs_page.py today",
                "target_owner": "design_brain.design_guide_controller",
                "evidence": matches["hardcoded_family_route_metadata"],
                "status": "extractable_pure_projection_metadata",
            },
        },
        "source_checks": {
            "target_found": bool(segment),
            "controller_import_clean": controller_import_clean,
            "controller_exports_route_policy": controller_exports_policy,
            "controller_exports_route_adapter": controller_exports_adapter,
            "controller_route_policy_called_by_target": matches["controller_owned_route_policy"]["present"],
            "controller_route_projection_called_by_target": matches["controller_owned_route_projection"]["present"],
            "page_family_bridge_execution_present": matches["page_owned_family_bridge_execution"]["present"],
            "page_debug_cta_recording_present": matches["page_owned_debug_and_cta_recording"]["present"],
            "legacy_page_candidate_evaluator_absent": legacy_evaluator_absent,
            "candidate_evaluation_service_call_present": candidate_service_present,
            "route_branches_present": all(route_branches.values()),
        },
        "first_safe_implementation_slice": {
            "name": "direct_target_family_route_projection_metadata_extraction",
            "ready": first_slice_ready,
            "move": (
                "Move the pure route metadata/projection defaults for bending, shear, and combined active-failure "
                "direct-target bridges into a controller helper. Keep `_active_fail_near_current_repair_item(...)`, "
                "`_record_bending_fail_valid_repair_cta_published(...)`, debug_sink mutation, and apply/render/session "
                "plumbing in `inputs_page.py`."
            ),
            "must_not_move": [
                "family repair callback execution",
                "page debug_sink mutation",
                "bending repair CTA recording side effect",
                "Streamlit/session diagnostics",
                "CTA/apply routing",
                "visible wording",
                "family runtime behavior",
            ],
            "required_verifier": "design_guide_direct_target_family_route_projection_metadata_extraction.py",
        },
        "stop_conditions": [
            "route branch selected family changes",
            "family item callback execution changes",
            "debug/CTA recording side effect changes",
            "visible wording changes",
            "CTA/apply semantics change",
            "family runtime behavior changes",
            "any composed lock fails",
        ],
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "target_found": bool(source_checks.get("target_found")),
        "controller_import_clean": bool(source_checks.get("controller_import_clean")),
        "controller_route_policy_available": bool(source_checks.get("controller_exports_route_policy")),
        "controller_route_adapter_available": bool(source_checks.get("controller_exports_route_adapter")),
        "route_policy_called_by_target": bool(source_checks.get("controller_route_policy_called_by_target")),
        "route_projection_called_by_target": bool(source_checks.get("controller_route_projection_called_by_target")),
        "page_family_bridge_execution_classified": bool(source_checks.get("page_family_bridge_execution_present")),
        "page_debug_cta_recording_classified": bool(source_checks.get("page_debug_cta_recording_present")),
        "legacy_page_candidate_evaluator_absent": bool(source_checks.get("legacy_page_candidate_evaluator_absent")),
        "candidate_evaluation_service_call_present": bool(source_checks.get("candidate_evaluation_service_call_present")),
        "route_branches_present": bool(source_checks.get("route_branches_present")),
        "first_safe_slice_identified": bool((capture.get("first_safe_implementation_slice") or {}).get("ready")),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    target = dict(capture.get("target") or {})
    first_slice = dict(capture.get("first_safe_implementation_slice") or {})
    classification = dict(capture.get("classification") or {})
    lines = [
        "# Direct Target Family Repair Bridge Route Policy Audit",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Decision: `{capture.get('decision')}`",
        f"- Target lines: `{target.get('line_start')}`-`{target.get('line_end')}`",
        f"- Target line count: `{target.get('line_count')}`",
        "",
        "## Ownership Classification",
    ]
    for name, row in classification.items():
        lines.append(f"- `{name}`: `{row.get('status')}`; owner `{row.get('owner')}`; target `{row.get('target_owner') or row.get('owner')}`")
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first_slice.get('name')}`",
            f"- Ready: `{first_slice.get('ready')}`",
            f"- Move: {first_slice.get('move')}",
            f"- Required verifier: `{first_slice.get('required_verifier')}`",
            "",
            "## Do Not Move",
        ]
    )
    for item in list(first_slice.get("must_not_move") or []):
        lines.append(f"- {item}")
    lines.extend(["", "## Checks"])
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    lines.extend(["", "## Stop Conditions"])
    for item in list(capture.get("stop_conditions") or []):
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = PROGRESS_PATH.read_text(encoding="utf-8").rstrip() if PROGRESS_PATH.exists() else ""
    lines = [existing, ""] if existing else []
    lines.extend(
        [
            f"## {payload.get('created_at')} - Direct target family repair bridge route policy audit",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Decision: `{(payload.get('capture') or {}).get('decision')}`",
            f"- Report: [{report_path.name}](../audits/{report_path.name})",
            "",
        ]
    )
    PROGRESS_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    created_at = _timestamp()
    capture = _capture()
    checks = _checks(capture)
    passed = all(checks.values())
    payload = {
        "schema": "design_guide_direct_target_family_repair_bridge_route_policy_audit.v1",
        "created_at": created_at,
        "status": "PASS" if passed else "FAIL",
        "capture": capture,
        "checks": checks,
    }
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_family_repair_bridge_route_policy_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_family_repair_bridge_route_policy_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_direct_target_family_repair_bridge_route_policy_audit {payload['status']}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if not passed:
        print("failing_checks=" + json.dumps([name for name, ok in checks.items() if not ok]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
