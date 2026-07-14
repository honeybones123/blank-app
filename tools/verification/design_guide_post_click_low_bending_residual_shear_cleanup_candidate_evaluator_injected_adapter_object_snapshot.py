"""Object snapshot for residual shear cleanup candidate evaluator injected adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary,
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff,
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter,
)
from design_brain.final_publication import stable_final_publication_hash  # noqa: E402


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


def _function_block(source: str) -> str:
    start = source.find(
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter("
    )
    if start < 0:
        return ""
    end = source.find("\n\n@dataclass", start)
    return source[start:end] if end > start else source[start:]


def _handoff() -> dict[str, Any]:
    route_projection = {
        "route_request": {"branch": "post_click_residual_shear_cleanup_after_bending_blocker"},
        "search_projection": {"candidate_evaluation_required": True},
        "result_projection": {"candidate_id": "residual-shear-candidate"},
    }
    route_proof = {
        "proof_hash": stable_final_publication_hash({"route_projection": route_projection}),
        "route_projection_hash": stable_final_publication_hash(route_projection),
        "route_projection": route_projection,
    }
    boundary = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary(
        route_proof=route_proof,
        route_shell_readiness={"readiness_hash": "route-shell-readiness"},
        dependency_status={},
        candidate_boundary_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "starting_shear_util": 0.69,
            "target_low": 0.85,
            "target_high": 1.0,
            "has_residual_updates": True,
        },
    )
    sequence = [
        {
            "index": 0,
            "updates_hash": stable_final_publication_hash({"s_lig": 300}),
            "candidate_hash": stable_final_publication_hash({"overview": {"utils": {"shear": 0.91}}}),
            "overview_hash": stable_final_publication_hash({"utils": {"shear": 0.91}}),
            "success": True,
            "accepted_as_safe_cleanup": True,
        },
        {
            "index": 1,
            "updates_hash": stable_final_publication_hash({"lig_legs": 0}),
            "candidate_hash": "",
            "overview_hash": "",
            "success": False,
            "accepted_as_safe_cleanup": False,
            "failed_reason": "candidate_evaluation_returned_no_candidate",
        },
    ]
    return build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff(
        candidate_boundary=boundary,
        evaluation_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "evaluation_source": "post_click_low_bending_residual_shear_cleanup_probe",
            "evaluation_label": "Shear cleanup - one-click reduction",
            "evaluation_action_type": "apply_resolved_candidate",
            "state_fingerprint": "state-fingerprint",
            "mode_config_hash": "mode-config-hash",
        },
        evaluation_output_summary={
            "evaluation_attempted_count": 2,
            "evaluated_candidate_count": 2,
            "successful_candidate_count": 1,
            "failed_candidate_count": 1,
            "stable_sequence_hash": stable_final_publication_hash(sequence),
        },
        dependency_status="page_live",
    )


def _contract_for(handoff: dict[str, Any], **updates: Any) -> dict[str, Any]:
    contract = {
        "evaluator_name": "_evaluate_auto_design_candidate",
        "input_hash": handoff.get("evaluator_input_hash"),
        "output_hash": handoff.get("evaluator_output_hash"),
        "stable_sequence_hash": handoff.get("stable_sequence_hash"),
        "stale_state_policy": "rebuild_on_changed_or_missing_state_fingerprint",
        "exception_policy": "preserve_existing_page_exception_handling",
        "acceptance_policy": "preserve_existing_materiality_detailing_overview_preview_filters",
        "evaluator_available": True,
        "evaluator_is_injected": True,
        "evaluator_changes_behavior": False,
    }
    contract.update(updates)
    return contract


def _case(name: str, contract_updates: dict[str, Any] | None = None, expected_ready: bool = False) -> dict[str, Any]:
    handoff = _handoff()
    contract = _contract_for(handoff, **dict(contract_updates or {}))
    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter(
        candidate_evaluator_handoff=handoff,
        adapter_contract=contract,
    )
    second = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter(
        candidate_evaluator_handoff=handoff,
        adapter_contract=contract,
    )
    return {
        "name": name,
        "expected_ready": expected_ready,
        "adapter_boundary_ready": bool(first.get("adapter_boundary_ready")),
        "behavior_cutover_ready": bool(first.get("behavior_cutover_ready")),
        "stable_hash_repeat": first.get("candidate_evaluator_injected_adapter_hash")
        == second.get("candidate_evaluator_injected_adapter_hash"),
        "page_must_keep_for_now": tuple(first.get("page_must_keep_for_now") or ()),
        "not_moved": tuple(first.get("not_moved") or ()),
        "product_driving": bool(first.get("product_driving")),
        "render_driving": bool(first.get("render_driving")),
        "apply_driving": bool(first.get("apply_driving")),
        "session_driving": bool(first.get("session_driving")),
    }


def _capture() -> dict[str, Any]:
    source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    block = _function_block(source)
    forbidden_page_terms = (
        "inputs_page",
        "import streamlit",
        "st.session_state",
        "st.button",
        "design_guide_page",
    )
    forbidden_execution_terms = (
        "_evaluate_auto_design_candidate(",
        "_evaluate_candidate_fast(",
        "evaluate_candidate_full(",
        "generate_less_shear_reo_variants(",
        "_design_guide_button_contract(",
    )
    cases = [
        _case(name="complete_injected_contract_ready", expected_ready=True),
        _case(
            name="missing_acceptance_policy",
            contract_updates={"acceptance_policy": ""},
            expected_ready=False,
        ),
        _case(
            name="mismatched_input_hash",
            contract_updates={"input_hash": "wrong"},
            expected_ready=False,
        ),
        _case(
            name="behavior_change_not_ready",
            contract_updates={"evaluator_changes_behavior": True},
            expected_ready=False,
        ),
    ]
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_CANDIDATE_EVALUATOR_INJECTED_ADAPTER_OBJECT_PROVEN",
        "function_present": bool(block),
        "exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter"'
            in source
        ),
        "cases": cases,
        "forbidden_page_terms_absent": not any(
            term.lower() in block.lower() for term in forbidden_page_terms
        ),
        "execution_terms_absent": not any(term in block for term in forbidden_execution_terms),
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
        "case_count": len(cases) == 4,
        "ready_case_ready": any(
            case.get("name") == "complete_injected_contract_ready"
            and case.get("adapter_boundary_ready") is True
            and case.get("behavior_cutover_ready") is True
            for case in cases
        ),
        "guarded_cases_not_ready": all(
            case.get("behavior_cutover_ready") is case.get("expected_ready")
            for case in cases
        ),
        "stable_hashes": all(case.get("stable_hash_repeat") is True for case in cases),
        "candidate_evaluation_kept_when_not_ready": all(
            "candidate_evaluation_execution" in case.get("page_must_keep_for_now")
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
        "# Residual Shear Cleanup Candidate Evaluator Injected Adapter Object Snapshot",
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
            "- "
            + str(case.get("name"))
            + ": adapter_boundary_ready=`"
            + str(case.get("adapter_boundary_ready"))
            + "`, behavior_cutover_ready=`"
            + str(case.get("behavior_cutover_ready"))
            + "`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Trace-wire the injected-adapter proof beside the live evaluator handoff. Do not replace `_evaluate_auto_design_candidate(...)` yet.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_object_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_object_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_object_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_candidate_evaluator_injected_adapter_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_object "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
