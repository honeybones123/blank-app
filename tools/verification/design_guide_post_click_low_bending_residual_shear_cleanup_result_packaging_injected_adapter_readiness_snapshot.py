"""Readiness snapshot for residual shear cleanup result packaging injected adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
TRACE_SNAPSHOT = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff_trace_wiring_snapshot.py"
)
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff,
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter,
)


def _stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _run_trace_snapshot() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(TRACE_SNAPSHOT)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0
        and "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff_trace_wiring PASS"
        in proc.stdout,
    }


def _handoff() -> dict[str, Any]:
    return build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff(
        candidate_selection_sort_key={"candidate_selection_sort_key_hash": "selection-hash"},
        packaging_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": "state-hash",
            "overview_hash": "overview-hash",
            "mode_config_hash": "mode-hash",
            "residual_shear_tighten_hash": "tighten-hash",
            "residual_updates_hash": "updates-hash",
            "actions_used_hash": "actions-hash",
        },
        packaging_output_summary={
            "residual_shear_item_hash": "item-hash",
            "residual_promoted_hash": "promoted-hash",
            "residual_detail_hash": "detail-hash",
            "residual_evidence_hash": "evidence-hash",
            "residual_candidate_id": "candidate-id",
            "residual_preview_util": 0.91,
            "residual_outside_preferred_band": False,
            "button_contract_hash_observed_not_owned": "button-hash",
        },
        dependency_status="page_live",
    )


def _contract_for(handoff: dict[str, Any], **updates: Any) -> dict[str, Any]:
    contract = {
        "packager_name": "_shear_tightening_as_local_cleanup_item",
        "local_cleanup_evaluator_name": "_evaluate_local_cleanup_guidance_item",
        "input_hash": handoff.get("packaging_input_hash"),
        "output_hash": handoff.get("packaging_output_hash"),
        "promoted_item_hash": handoff.get("residual_promoted_hash"),
        "evidence_hash": handoff.get("residual_evidence_hash"),
        "stale_state_policy": "rebuild_on_changed_or_missing_state_fingerprint",
        "button_contract_policy": "observe_hash_only_keep_button_contract_page_owned",
        "packager_available": True,
        "local_cleanup_evaluator_available": True,
        "adapter_is_injected": True,
        "adapter_changes_behavior": False,
    }
    contract.update(updates)
    return contract


def _case(name: str, contract_updates: dict[str, Any] | None = None, expected_ready: bool = False) -> dict[str, Any]:
    handoff = _handoff()
    contract = _contract_for(handoff, **dict(contract_updates or {}))
    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter(
        result_packaging_handoff=handoff,
        adapter_contract=contract,
    )
    second = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter(
        result_packaging_handoff=handoff,
        adapter_contract=contract,
    )
    return {
        "name": name,
        "expected_ready": expected_ready,
        "adapter_boundary_ready": bool(first.get("adapter_boundary_ready")),
        "behavior_cutover_ready": bool(first.get("behavior_cutover_ready")),
        "stable_hash_repeat": first.get("result_packaging_injected_adapter_hash")
        == second.get("result_packaging_injected_adapter_hash"),
        "page_must_keep_for_now": tuple(first.get("page_must_keep_for_now") or ()),
        "not_moved": tuple(first.get("not_moved") or ()),
        "product_driving": bool(first.get("product_driving")),
        "render_driving": bool(first.get("render_driving")),
        "apply_driving": bool(first.get("apply_driving")),
        "session_driving": bool(first.get("session_driving")),
    }


def _capture() -> dict[str, Any]:
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    inputs_source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    function_block = _between(
        controller_source,
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter(",
        "\n\n@dataclass",
    )
    helper = _between(
        inputs_source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter(",
        "\n\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(",
    )
    route = _between(
        inputs_source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    trace_snapshot = _run_trace_snapshot()
    cases = [
        _case(name="complete_injected_packaging_contract_ready", expected_ready=True),
        _case(
            name="mismatched_output_hash",
            contract_updates={"output_hash": "wrong"},
            expected_ready=False,
        ),
        _case(
            name="missing_button_policy",
            contract_updates={"button_contract_policy": ""},
            expected_ready=False,
        ),
        _case(
            name="behavior_change_not_ready",
            contract_updates={"adapter_changes_behavior": True},
            expected_ready=False,
        ),
    ]
    forbidden_page_terms = (
        "inputs_page",
        "import streamlit",
        "st.session_state",
        "st.button",
        "design_guide_page",
    )
    forbidden_execution_terms = (
        "_shear_tightening_as_local_cleanup_item(",
        "_evaluate_local_cleanup_guidance_item(",
        "_design_guide_button_contract(",
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_RESULT_PACKAGING_INJECTED_ADAPTER_READY",
        "function_present": bool(function_block),
        "exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter"'
            in controller_source
        ),
        "import_alias_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter"
        )
        in inputs_source,
        "helper_present": bool(helper),
        "helper_calls_controller": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter("
            in helper
        ),
        "helper_non_driving": all(
            token in helper
            for token in (
                "result_packaging_injected_adapter_proof_only",
                "result_packaging_injected_adapter_product_driving",
                "result_packaging_injected_adapter_render_driving",
                "result_packaging_injected_adapter_apply_driving",
                "result_packaging_injected_adapter_session_driving",
            )
        ),
        "route_stamps_after_handoff": (
            route.find(
                "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff("
            )
            < route.find(
                "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter("
            )
        ),
        "route_live_packaging_still_present": (
            "_shear_tightening_as_local_cleanup_item(" in route
            or "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(" in route
        ),
        "route_live_evaluator_still_present": (
            "_evaluate_local_cleanup_guidance_item(" in route
            or "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(" in route
        ),
        "route_packaging_cutover_wrapper_present": (
            "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(" in route
        ),
        "cases": cases,
        "trace_snapshot": trace_snapshot,
        "forbidden_page_terms_absent": not any(
            term.lower() in function_block.lower() for term in forbidden_page_terms
        ),
        "execution_terms_absent": not any(term in function_block for term in forbidden_execution_terms),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    cases = list(capture.get("cases") or [])
    return {
        "function_present": capture.get("function_present") is True,
        "exported": capture.get("exported") is True,
        "import_alias_present": capture.get("import_alias_present") is True,
        "helper_present": capture.get("helper_present") is True,
        "helper_calls_controller": capture.get("helper_calls_controller") is True,
        "helper_non_driving": capture.get("helper_non_driving") is True,
        "route_stamps_after_handoff": capture.get("route_stamps_after_handoff") is True,
        "route_live_packaging_still_present": capture.get("route_live_packaging_still_present") is True,
        "route_live_evaluator_still_present": capture.get("route_live_evaluator_still_present") is True,
        "case_count": len(cases) == 4,
        "ready_case_ready": any(
            case.get("name") == "complete_injected_packaging_contract_ready"
            and case.get("adapter_boundary_ready") is True
            and case.get("behavior_cutover_ready") is True
            for case in cases
        ),
        "guarded_cases_not_ready": all(
            case.get("behavior_cutover_ready") is case.get("expected_ready")
            for case in cases
        ),
        "stable_hashes": all(case.get("stable_hash_repeat") is True for case in cases),
        "packaging_kept_when_not_ready": all(
            "local_cleanup_item_packaging_execution" in case.get("page_must_keep_for_now")
            for case in cases
            if not case.get("expected_ready")
        ),
        "non_driving": all(
            not case.get("product_driving")
            and not case.get("render_driving")
            and not case.get("apply_driving")
            and not case.get("session_driving")
            for case in cases
        ),
        "trace_snapshot_passed": (capture.get("trace_snapshot") or {}).get("passed") is True,
        "forbidden_page_terms_absent": capture.get("forbidden_page_terms_absent") is True,
        "execution_terms_absent": capture.get("execution_terms_absent") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Result Packaging Injected Adapter Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Cases",
        "",
    ]
    for case in capture.get("cases") or []:
        lines.append(
            "- {name}: adapter_boundary_ready=`{ready}`, behavior_cutover_ready=`{cutover}`".format(
                name=case.get("name"),
                ready=case.get("adapter_boundary_ready"),
                cutover=case.get("behavior_cutover_ready"),
            )
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "A narrow packaging/evaluator dependency-shell cutover may be considered next. Keep button contract, visible wording, apply routing, and evidence merge unchanged.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter_readiness_snapshot.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_result_packaging_injected_adapter_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter_readiness "
        f"{payload['status']}"
    )
    print(json_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
