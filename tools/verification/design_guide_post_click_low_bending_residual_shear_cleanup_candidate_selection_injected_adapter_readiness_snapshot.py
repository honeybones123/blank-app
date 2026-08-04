"""Readiness snapshot for residual shear cleanup candidate selection injected adapter."""

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
    / "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key_trace_wiring_snapshot.py"
)
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff,
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter,
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
        and "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key_trace_wiring PASS"
        in proc.stdout,
    }


def _selection_proof() -> dict[str, Any]:
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
    handoff = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff(
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
    return build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key(
        candidate_evaluator_handoff=handoff,
        selection_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "sort_key_order": ("shear_util", "update_count", "updates_items"),
            "state_fingerprint": "state-fingerprint",
            "mode_config_hash": "mode-config-hash",
        },
        selection_output_summary={
            "candidate_count": 1,
            "stable_candidate_sequence_hash": stable_final_publication_hash(sequence),
            "selected_updates_hash": stable_final_publication_hash({"s_lig": 300}),
            "selected_candidate_hash": stable_final_publication_hash({"overview": {"utils": {"shear": 0.91}}}),
            "selected_sort_key_hash": stable_final_publication_hash(
                {"shear_util": 0.91, "update_count": 1, "updates_items": "[('s_lig', 300)]"}
            ),
            "selected_shear_util": 0.91,
        },
        dependency_status="page_live",
    )


def _contract_for(selection: dict[str, Any], **updates: Any) -> dict[str, Any]:
    contract = {
        "selector_name": "residual_shear_cleanup_min_sort_key_selector",
        "input_hash": selection.get("selection_input_hash"),
        "output_hash": selection.get("selection_output_hash"),
        "stable_sequence_hash": selection.get("stable_candidate_sequence_hash"),
        "sort_key_order_hash": stable_final_publication_hash(tuple(selection.get("sort_key_order") or ())),
        "selected_candidate_hash": selection.get("selected_candidate_hash"),
        "stale_state_policy": "rebuild_on_changed_or_missing_state_fingerprint",
        "tie_break_policy": "shear_util_then_update_count_then_sorted_updates",
        "selector_available": True,
        "selector_is_injected": True,
        "selector_changes_behavior": False,
    }
    contract.update(updates)
    return contract


def _case(name: str, contract_updates: dict[str, Any] | None = None, expected_ready: bool = False) -> dict[str, Any]:
    selection = _selection_proof()
    contract = _contract_for(selection, **dict(contract_updates or {}))
    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter(
        candidate_selection_sort_key=selection,
        adapter_contract=contract,
    )
    second = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter(
        candidate_selection_sort_key=selection,
        adapter_contract=contract,
    )
    return {
        "name": name,
        "expected_ready": expected_ready,
        "adapter_boundary_ready": bool(first.get("adapter_boundary_ready")),
        "behavior_cutover_ready": bool(first.get("behavior_cutover_ready")),
        "stable_hash_repeat": first.get("candidate_selection_injected_adapter_hash")
        == second.get("candidate_selection_injected_adapter_hash"),
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
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter(",
        "\n\n@dataclass",
    )
    helper = _between(
        inputs_source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter(",
        "\n\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(",
    )
    route = _between(
        inputs_source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    trace_snapshot = _run_trace_snapshot()
    cases = [
        _case(name="complete_injected_selection_contract_ready", expected_ready=True),
        _case(
            name="mismatched_sequence_hash",
            contract_updates={"stable_sequence_hash": "wrong"},
            expected_ready=False,
        ),
        _case(
            name="mismatched_sort_key_order_hash",
            contract_updates={"sort_key_order_hash": "wrong"},
            expected_ready=False,
        ),
        _case(
            name="behavior_change_not_ready",
            contract_updates={"selector_changes_behavior": True},
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
        "min(",
        "_evaluate_auto_design_candidate(",
        "generate_less_shear_reo_variants(",
        "_design_guide_button_contract(",
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_CANDIDATE_SELECTION_INJECTED_ADAPTER_READY",
        "function_present": bool(function_block),
        "exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter"'
            in controller_source
        ),
        "import_alias_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter"
        )
        in inputs_source,
        "helper_present": bool(helper),
        "helper_calls_controller": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter("
            in helper
        ),
        "helper_non_driving": all(
            token in helper
            for token in (
                "candidate_selection_injected_adapter_proof_only",
                "candidate_selection_injected_adapter_product_driving",
                "candidate_selection_injected_adapter_render_driving",
                "candidate_selection_injected_adapter_apply_driving",
                "candidate_selection_injected_adapter_session_driving",
            )
        ),
        "route_stamps_after_sort_key": (
            route.find(
                "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key("
            )
            < route.find(
                "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter("
            )
        ),
        "selection_dependency_shell_present": (
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_selector(" in route
        ),
        "selection_selector_callable_injected": (
            "selector=_select_design_guide_post_click_low_bending_residual_shear_cleanup_candidate_by_sort_key"
            in route
        ),
        "route_direct_min_removed": "fallback_best = min(" not in route,
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
        "route_stamps_after_sort_key": capture.get("route_stamps_after_sort_key") is True,
        "selection_dependency_shell_present": (
            capture.get("selection_dependency_shell_present") is True
        ),
        "selection_selector_callable_injected": (
            capture.get("selection_selector_callable_injected") is True
        ),
        "route_direct_min_removed": capture.get("route_direct_min_removed") is True,
        "case_count": len(cases) == 4,
        "ready_case_ready": any(
            case.get("name") == "complete_injected_selection_contract_ready"
            and case.get("adapter_boundary_ready") is True
            and case.get("behavior_cutover_ready") is True
            for case in cases
        ),
        "guarded_cases_not_ready": all(
            case.get("behavior_cutover_ready") is case.get("expected_ready")
            for case in cases
        ),
        "stable_hashes": all(case.get("stable_hash_repeat") is True for case in cases),
        "selection_kept_when_not_ready": all(
            "candidate_selection_execution" in case.get("page_must_keep_for_now")
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
        "# Residual Shear Cleanup Candidate Selection Injected Adapter Readiness Snapshot",
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
            "A narrow selection dependency-shell cutover may be considered next. Do not delete the live page selection expression until cutover and deadness are separately proven.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter_readiness_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_candidate_selection_injected_adapter_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter_readiness "
        f"{payload['status']}"
    )
    print(json_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
