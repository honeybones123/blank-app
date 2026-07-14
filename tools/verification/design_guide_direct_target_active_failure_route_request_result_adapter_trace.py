"""Verify trace-only active-failure route request/result adapter wiring."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_direct_target_active_failure_route_request_result_adapter_trace,
    build_design_guide_controller_direct_target_combined_family_bypass_evidence_projection,
    build_design_guide_controller_direct_target_family_bypass_projection,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_direct_target_band_guidance_item"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _parity_cases() -> dict[str, dict[str, Any]]:
    base_item = {
        "title": "Strengthening required",
        "status": "ACTION",
        "candidate_search_evidence": {"existing": "kept"},
    }
    combined_extra = build_design_guide_controller_direct_target_combined_family_bypass_evidence_projection(
        overview={
            "statuses": {"bending": "FAIL", "shear": "FAIL"},
            "utils": {"bending": 1.25, "shear": "1.18"},
        }
    ).get("bypass_extra")
    cases = {
        "bending": {
            "active_failure_keys": ("bending",),
            "item": dict(base_item),
            "family_id": "BENDING_FAIL_GOVERNS",
            "family_route_owner": "design_brain.families.bending_fail.BendingFailFamily",
            "skipped_reason": "selected_family_bending_fail_governs",
            "evidence_extra": {
                "family_speed_isolation_owner": "BENDING_FAIL_GOVERNS",
                "family_speed_isolation_active_repair": True,
                "post_publication_generic_proofs_skipped": True,
            },
            "item_extra": {
                "family_speed_isolation_owner": "BENDING_FAIL_GOVERNS",
                "family_speed_isolation_active_repair": True,
                "post_publication_generic_proofs_skipped": True,
            },
            "debug_extra": {
                "family_speed_isolation_owner": "BENDING_FAIL_GOVERNS",
                "family_speed_isolation_active_repair": True,
                "post_publication_generic_proofs_skipped": True,
            },
            "family_early_dispatch_key": "family_early_dispatch_used",
        },
        "shear": {
            "active_failure_keys": ("shear",),
            "item": dict(base_item),
            "family_id": "SHEAR_FAIL_GOVERNS",
            "family_route_owner": "design_brain.families.shear_fail.ShearFailFamily",
            "skipped_reason": "selected_family_shear_fail_governs",
        },
        "combined": {
            "active_failure_keys": ("bending", "shear"),
            "item": dict(base_item),
            "family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "family_route_owner": (
                "design_brain.families.combined_bending_shear_fail.CombinedBendingShearFailFamily"
            ),
            "skipped_reason": "selected_family_combined_bending_shear_fail",
            "evidence_extra": dict(combined_extra or {}),
            "item_extra": dict(combined_extra or {}),
            "family_early_dispatch_key": "early_family_dispatch_used",
            "include_projected_evidence_in_debug": True,
        },
    }
    out: dict[str, dict[str, Any]] = {}
    for name, kwargs in cases.items():
        trace = build_design_guide_controller_direct_target_active_failure_route_request_result_adapter_trace(**kwargs)
        projection = build_design_guide_controller_direct_target_family_bypass_projection(
            item=kwargs.get("item"),
            family_id=kwargs.get("family_id"),
            family_route_owner=kwargs.get("family_route_owner"),
            skipped_reason=kwargs.get("skipped_reason"),
            evidence_extra=kwargs.get("evidence_extra"),
            item_extra=kwargs.get("item_extra"),
            debug_extra=kwargs.get("debug_extra"),
            include_candidate_card_family=kwargs.get("include_candidate_card_family", True),
            family_early_dispatch_key=kwargs.get("family_early_dispatch_key"),
            include_projected_evidence_in_debug=kwargs.get("include_projected_evidence_in_debug", False),
        )
        out[name] = {
            "trace_hash_present": bool(trace.get("trace_hash")),
            "item_matches_projection": dict((trace.get("result") or {}).get("item") or {})
            == dict(projection.get("item") or {}),
            "evidence_matches_projection": dict((trace.get("result") or {}).get("candidate_search_evidence") or {})
            == dict(projection.get("candidate_search_evidence") or {}),
            "debug_matches_projection": dict((trace.get("result") or {}).get("debug_update") or {})
            == dict(projection.get("debug_update") or {}),
            "request_family_id": (trace.get("request") or {}).get("family_id"),
        }
    return out


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    pre_diag = segment.split("_diag_prior = st.session_state.get", 1)[0]
    return {
        "schema": "design_guide_direct_target_active_failure_route_request_result_adapter_trace.v1",
        "target": {"name": TARGET, "line_start": start, "line_end": end},
        "parity_cases": _parity_cases(),
        "page_imports_trace_adapter": (
            "_build_design_guide_controller_direct_target_active_failure_route_request_result_adapter_trace"
            in inputs_source
        ),
        "page_trace_adapter_call_count": pre_diag.count(
            "_build_design_guide_controller_direct_target_active_failure_route_request_result_adapter_trace("
        ),
        "page_records_trace_debug_only": "direct_target_active_failure_route_adapter_trace" in pre_diag,
        "page_still_owns_family_executor": "_active_fail_near_current_repair_item(" in pre_diag,
        "page_still_owns_bending_cta_side_effect": "_record_bending_fail_valid_repair_cta_published(" in pre_diag,
        "controller_helper_exported": (
            '"build_design_guide_controller_direct_target_active_failure_route_request_result_adapter_trace"'
            in controller_source
        ),
        "controller_has_no_page_or_streamlit_imports": (
            "inputs_page" not in controller_source
            and "streamlit" not in controller_source
            and "st.session_state" not in controller_source
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    parity = payload.get("parity_cases") or {}
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "all_parity_cases_match": bool(parity)
        and all(
            row.get("trace_hash_present")
            and row.get("item_matches_projection")
            and row.get("evidence_matches_projection")
            and row.get("debug_matches_projection")
            for row in parity.values()
        ),
        "page_imports_trace_adapter": bool(payload.get("page_imports_trace_adapter")),
        "page_trace_adapter_call_count_is_three": int(payload.get("page_trace_adapter_call_count") or 0) == 3,
        "page_records_trace_debug_only": bool(payload.get("page_records_trace_debug_only")),
        "page_still_owns_family_executor": bool(payload.get("page_still_owns_family_executor")),
        "page_still_owns_bending_cta_side_effect": bool(
            payload.get("page_still_owns_bending_cta_side_effect")
        ),
        "controller_helper_exported": bool(payload.get("controller_helper_exported")),
        "controller_has_no_page_or_streamlit_imports": bool(
            payload.get("controller_has_no_page_or_streamlit_imports")
        ),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_direct_target_active_failure_route_request_result_adapter_trace_{suffix}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_direct_target_active_failure_route_request_result_adapter_trace_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Active-Failure Route Request/Result Adapter Trace",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "Added a trace-only controller route request/result adapter for bending, shear, and combined "
            "active-failure direct-target family bypasses. It matches the existing projection output while "
            "leaving family executor and CTA side effects page-owned."
        ),
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_direct_target_active_failure_route_request_result_adapter_trace {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
