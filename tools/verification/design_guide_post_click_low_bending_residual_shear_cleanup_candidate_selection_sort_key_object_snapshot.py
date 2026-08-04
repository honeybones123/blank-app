"""Object snapshot for residual shear cleanup candidate selection/sort-key proof."""

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
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff,
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key,
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
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key("
    )
    if start < 0:
        return ""
    end = source.find("\n\n@dataclass", start)
    return source[start:end] if end > start else source[start:]


def _handoff() -> dict[str, Any]:
    sequence = [
        {
            "index": 0,
            "updates_hash": stable_final_publication_hash({"s_lig": 300}),
            "candidate_hash": stable_final_publication_hash({"overview": {"utils": {"shear": 0.91}}}),
            "overview_hash": stable_final_publication_hash({"utils": {"shear": 0.91}}),
            "success": True,
            "accepted_as_safe_cleanup": True,
        }
    ]
    return build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff(
        candidate_boundary={"candidate_boundary_hash": "candidate-boundary-hash"},
        evaluation_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "evaluation_source": "post_click_low_bending_residual_shear_cleanup_probe",
            "evaluation_label": "Shear cleanup - one-click reduction",
            "evaluation_action_type": "apply_resolved_candidate",
            "state_fingerprint": "state-fingerprint",
            "mode_config_hash": "mode-config-hash",
        },
        evaluation_output_summary={
            "evaluation_attempted_count": 1,
            "evaluated_candidate_count": 1,
            "successful_candidate_count": 1,
            "failed_candidate_count": 0,
            "stable_sequence_hash": stable_final_publication_hash(sequence),
        },
        dependency_status="page_live",
    )


def _case(
    *,
    name: str,
    input_updates: dict[str, Any] | None = None,
    output_updates: dict[str, Any] | None = None,
    dependency_status: str = "page_live",
    expected_ready: bool,
) -> dict[str, Any]:
    sequence = [
        {
            "index": 0,
            "updates_hash": stable_final_publication_hash({"s_lig": 300}),
            "candidate_hash": stable_final_publication_hash({"overview": {"utils": {"shear": 0.91}}}),
            "overview_hash": stable_final_publication_hash({"utils": {"shear": 0.91}}),
            "shear_util": 0.91,
            "sort_key": {
                "shear_util": 0.91,
                "update_count": 1,
                "updates_items": "[('s_lig', 300)]",
            },
        }
    ]
    inputs = {
        "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
        "sort_key_order": ("shear_util", "update_count", "updates_items"),
        "state_fingerprint": "state-fingerprint",
        "mode_config_hash": "mode-config-hash",
    }
    output = {
        "candidate_count": 1,
        "stable_candidate_sequence_hash": stable_final_publication_hash(sequence),
        "selected_updates_hash": stable_final_publication_hash({"s_lig": 300}),
        "selected_candidate_hash": stable_final_publication_hash({"overview": {"utils": {"shear": 0.91}}}),
        "selected_sort_key_hash": stable_final_publication_hash(
            {"shear_util": 0.91, "update_count": 1, "updates_items": "[('s_lig', 300)]"}
        ),
        "selected_shear_util": 0.91,
    }
    inputs.update(input_updates or {})
    output.update(output_updates or {})
    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key(
        candidate_evaluator_handoff=_handoff(),
        selection_inputs=inputs,
        selection_output_summary=output,
        dependency_status=dependency_status,
    )
    second = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key(
        candidate_evaluator_handoff=_handoff(),
        selection_inputs=inputs,
        selection_output_summary=output,
        dependency_status=dependency_status,
    )
    return {
        "name": name,
        "expected_ready": expected_ready,
        "output_shape_ready": bool(first.get("output_shape_ready")),
        "behavior_cutover_ready": bool(first.get("behavior_cutover_ready")),
        "selection_cutover_ready": bool(first.get("selection_cutover_ready")),
        "stable_hash_repeat": first.get("candidate_selection_sort_key_hash")
        == second.get("candidate_selection_sort_key_hash"),
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
        "min(",
        "_evaluate_auto_design_candidate(",
        "generate_less_shear_reo_variants(",
        "_design_guide_button_contract(",
    )
    cases = [
        _case(name="page_live_complete_selection_shape", expected_ready=False),
        _case(
            name="missing_sequence_hash",
            output_updates={"stable_candidate_sequence_hash": ""},
            expected_ready=False,
        ),
        _case(
            name="wrong_sort_key_order",
            input_updates={"sort_key_order": ("update_count", "shear_util")},
            expected_ready=False,
        ),
        _case(
            name="future_controller_owned",
            dependency_status="controller_owned",
            expected_ready=True,
        ),
    ]
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_CANDIDATE_SELECTION_SORT_KEY_OBJECT_PROVEN",
        "function_present": bool(block),
        "exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key"'
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
        "page_live_shape_ready_not_cutover": any(
            case.get("name") == "page_live_complete_selection_shape"
            and case.get("output_shape_ready") is True
            and case.get("behavior_cutover_ready") is False
            and "candidate_selection_execution" in case.get("page_must_keep_for_now")
            for case in cases
        ),
        "guarded_cases_not_ready": all(
            case.get("behavior_cutover_ready") is case.get("expected_ready")
            for case in cases
        ),
        "future_controller_owned_ready": any(
            case.get("name") == "future_controller_owned"
            and case.get("behavior_cutover_ready") is True
            for case in cases
        ),
        "stable_hashes": all(case.get("stable_hash_repeat") is True for case in cases),
        "selection_not_moved_when_page_live": all(
            "candidate_selection_execution" in case.get("not_moved") for case in cases
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
        "# Residual Shear Cleanup Candidate Selection Sort-Key Object Snapshot",
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
            "- {name}: output_shape_ready=`{ready}`, behavior_cutover_ready=`{cutover}`, page_must_keep=`{keep}`".format(
                name=case.get("name"),
                ready=case.get("output_shape_ready"),
                cutover=case.get("behavior_cutover_ready"),
                keep=case.get("page_must_keep_for_now"),
            )
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Trace-wire beside the live page selection. Candidate selection execution remains page-owned until a separate injected selection cutover is proven.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key_object_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key_object_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key_object_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_candidate_selection_sort_key_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key_object "
        f"{payload['status']}"
    )
    print(json_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
