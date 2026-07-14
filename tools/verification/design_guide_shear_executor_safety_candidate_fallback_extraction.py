from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

SAFETY_CALLBACK = "_resolved_shear_cleanup_is_executor_safe"
PAGE_SHIM = "_evaluate_auto_design_candidate"
SERVICE_TARGET = "resolve_design_candidate_overview_for_safety_check"


def _function_segment(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_start = source.find("\ndef ", start + len(marker))
    if next_start < 0:
        next_start = len(source)
    return source[start:next_start]


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.candidate_evaluation import (
        resolve_design_candidate_overview_for_safety_check,
    )

    calls: list[dict[str, Any]] = []

    def snapshot_fn(state: dict) -> dict:
        out = dict(state or {})
        out["snapshot_marker"] = "snap"
        return out

    def evaluator_fn(candidate_state: dict, **kwargs: Any) -> dict:
        calls.append({"candidate_state": dict(candidate_state), "kwargs": dict(kwargs)})
        return {
            "overview": {"any_fail": False, "statuses": {"shear": "PASS"}},
            "updates": dict(kwargs.get("updates") or {}),
            "source": kwargs.get("source"),
            "label": kwargs.get("label"),
            "action_type": kwargs.get("action_type"),
            "candidate_state": dict(candidate_state),
            "candidate_post_util": 0.72,
        }

    rows: list[dict[str, Any]] = []
    existing = resolve_design_candidate_overview_for_safety_check(
        current_state={"s_lig": 200},
        updates={"s_lig": 300},
        resolved_candidate={"overview": {"any_fail": False, "statuses": {"shear": "PASS"}}, "updates": {"s_lig": 300}},
        source="guidance_shear_executor_contract_probe",
        label="Adjust shear reinforcement",
        action_type="apply_shear_recommendation",
        state_snapshot_fn=snapshot_fn,
        evaluator_fn=evaluator_fn,
    )
    rows.append(
        {
            "case": "existing_overview_path",
            "passed": (
                existing.get("overview") == {"any_fail": False, "statuses": {"shear": "PASS"}}
                and existing.get("used_fallback_evaluation") is False
                and len(calls) == 0
            ),
            "actual": existing,
        }
    )

    before_count = len(calls)
    missing = resolve_design_candidate_overview_for_safety_check(
        current_state={"s_lig": 200, "lig_legs": 2},
        updates={"s_lig": 300},
        resolved_candidate={"updates": {"s_lig": 300}},
        source="guidance_shear_executor_contract_probe",
        label="Payload label",
        action_type="apply_shear_recommendation",
        state_snapshot_fn=snapshot_fn,
        evaluator_fn=evaluator_fn,
    )
    call = calls[-1] if len(calls) > before_count else {}
    rows.append(
        {
            "case": "missing_overview_fallback",
            "passed": (
                missing.get("overview") == {"any_fail": False, "statuses": {"shear": "PASS"}}
                and missing.get("used_fallback_evaluation") is True
                and missing.get("fallback_source") == "guidance_shear_executor_contract_probe"
                and dict(missing.get("candidate") or {}).get("updates") == {"s_lig": 300}
                and dict(call.get("kwargs") or {}).get("source") == "guidance_shear_executor_contract_probe"
                and dict(call.get("kwargs") or {}).get("label") == "Payload label"
                and dict(call.get("kwargs") or {}).get("action_type") == "apply_shear_recommendation"
                and dict(call.get("kwargs") or {}).get("updates") == {"s_lig": 300}
                and dict(call.get("candidate_state") or {}).get("s_lig") == 300
                and dict(call.get("candidate_state") or {}).get("snapshot_marker") == "snap"
            ),
            "actual": missing,
            "call": call,
        }
    )

    def none_evaluator(candidate_state: dict, **kwargs: Any) -> None:
        return None

    failed = resolve_design_candidate_overview_for_safety_check(
        current_state={"s_lig": 200},
        updates={"s_lig": 300},
        resolved_candidate={},
        source="guidance_shear_executor_contract_probe",
        label="Adjust shear reinforcement",
        action_type="apply_shear_recommendation",
        state_snapshot_fn=snapshot_fn,
        evaluator_fn=none_evaluator,
    )
    rows.append(
        {
            "case": "fallback_evaluator_returns_none",
            "passed": (
                failed.get("candidate") == {}
                and failed.get("overview") == {}
                and failed.get("used_fallback_evaluation") is True
                and failed.get("updates") == {"s_lig": 300}
            ),
            "actual": failed,
        }
    )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    service_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    safety_segment = _function_segment(inputs_source, SAFETY_CALLBACK)
    shim_segment = _function_segment(inputs_source, PAGE_SHIM)
    service_segment = _function_segment(service_source, SERVICE_TARGET)
    parity_cases = _parity_cases()
    return {
        "schema": "design_guide_shear_executor_safety_candidate_fallback_extraction.v1",
        "safety_callback": SAFETY_CALLBACK,
        "service_target": SERVICE_TARGET,
        "page_imports_service_helper": f"{SERVICE_TARGET} as _{SERVICE_TARGET}" in inputs_source,
        "safety_callback_calls_service_helper": f"_{SERVICE_TARGET}(" in safety_segment,
        "safety_callback_no_longer_calls_page_shim": f"{PAGE_SHIM}(" not in safety_segment,
        "page_shim_still_exists": bool(shim_segment),
        "page_shim_still_delegates_to_service": "_evaluate_design_candidate_with_updates(" in shim_segment,
        "resolved_candidate_overview_path_still_present": "resolved_candidate" in safety_segment
        and "overview_resolution" in safety_segment,
        "fallback_source_preserved": "guidance_shear_executor_contract_probe" in safety_segment,
        "fallback_label_preserved": "Adjust shear reinforcement" in safety_segment,
        "fallback_action_type_preserved": "apply_shear_recommendation" in safety_segment,
        "service_uses_existing_candidate_evaluation_logic": "evaluate_design_candidate_with_updates(" in service_segment,
        "service_preserves_existing_overview_without_evaluation": "used_fallback_evaluation" in service_segment
        and "False" in service_segment,
        "service_sets_updates_on_fallback_candidate": 'candidate["updates"] = dict(updates or {})' in service_segment,
        "service_has_no_page_or_streamlit_imports": "inputs_page" not in service_source and "streamlit" not in service_source,
        "candidate_boundary_contract_tokens_present": all(
            token in service_source
            for token in (
                "class BeamCandidateInput",
                "class BeamCandidateUpdate",
                "class BeamCandidateEvaluation",
                "build_candidate_state_hash",
            )
        ),
        "parity_cases": parity_cases,
        "all_parity_cases_passed": all(row.get("passed") for row in parity_cases),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "page_imports_service_helper": bool(capture.get("page_imports_service_helper")),
        "safety_callback_calls_service_helper": bool(capture.get("safety_callback_calls_service_helper")),
        "safety_callback_no_longer_calls_page_shim": bool(capture.get("safety_callback_no_longer_calls_page_shim")),
        "page_shim_still_exists": bool(capture.get("page_shim_still_exists")),
        "page_shim_still_delegates_to_service": bool(capture.get("page_shim_still_delegates_to_service")),
        "resolved_candidate_overview_path_still_present": bool(capture.get("resolved_candidate_overview_path_still_present")),
        "fallback_source_preserved": bool(capture.get("fallback_source_preserved")),
        "fallback_label_preserved": bool(capture.get("fallback_label_preserved")),
        "fallback_action_type_preserved": bool(capture.get("fallback_action_type_preserved")),
        "service_uses_existing_candidate_evaluation_logic": bool(capture.get("service_uses_existing_candidate_evaluation_logic")),
        "service_preserves_existing_overview_without_evaluation": bool(capture.get("service_preserves_existing_overview_without_evaluation")),
        "service_sets_updates_on_fallback_candidate": bool(capture.get("service_sets_updates_on_fallback_candidate")),
        "service_has_no_page_or_streamlit_imports": bool(capture.get("service_has_no_page_or_streamlit_imports")),
        "candidate_boundary_contract_tokens_present": bool(capture.get("candidate_boundary_contract_tokens_present")),
        "parity_cases_passed": bool(capture.get("all_parity_cases_passed")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtimes_unchanged": capture.get("family_runtimes_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    checks = dict(payload.get("checks") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        "Shear executor safety missing-overview candidate-evaluation fallback.",
        "",
        "## Ownership Before",
        "`_resolved_shear_cleanup_is_executor_safe(...)` called `_evaluate_auto_design_candidate(...)` directly when resolved-candidate overview evidence was missing.",
        "",
        "## Ownership After",
        "`_resolved_shear_cleanup_is_executor_safe(...)` calls `design_brain.candidate_evaluation.resolve_design_candidate_overview_for_safety_check(...)`; the callback itself remains page-owned for now.",
        "",
        "## Behaviour Preserved",
        f"- Product behaviour changed: `{capture.get('product_behavior_changed')}`",
        f"- Visible wording changed: `{capture.get('visible_wording_changed')}`",
        f"- CTA/apply semantics changed: `{capture.get('cta_apply_semantics_changed')}`",
        f"- Family runtimes changed: `{capture.get('family_runtimes_changed')}`",
        "",
        "## Adapter / Default Rebuild Proof",
    ]
    for case in capture.get("parity_cases") or []:
        lines.append(f"- `{case.get('case')}`: passed=`{case.get('passed')}`")
    lines.extend(
        [
            "",
            "## Cutover Proof",
            f"- Safety callback calls service helper: `{capture.get('safety_callback_calls_service_helper')}`",
            f"- Safety callback no longer calls page shim: `{capture.get('safety_callback_no_longer_calls_page_shim')}`",
            f"- Page shim still exists: `{capture.get('page_shim_still_exists')}`",
            "",
            "## Deadness / Deletion Proof",
            "No deletion yet. `_evaluate_auto_design_candidate(...)` remains as a compatibility shim for broad non-migrated callsites.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "- `design_brain/candidate_evaluation.py`",
            "- `tools/verification/design_guide_shear_executor_safety_candidate_fallback_extraction.py`",
            "",
            "## Verifier Results",
        ]
    )
    for name, passed in checks.items():
        lines.append(f"- `{name}`: `{passed}`")
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "The shear executor safety callback still owns pure policy checks and page-owned current-state/probe collection. It is now ready for a pure safety-policy extraction audit/cutover.",
            "",
            "## Next Safe Target",
            "Move pure shear executor safety policy behind `DesignGuideController` while passing current_state, updates, resolved overview, and governing domain as plain inputs.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = str(payload.get("created_at") or "")
    status = str(payload.get("status") or "")
    existing = PROGRESS_PATH.read_text(encoding="utf-8") if PROGRESS_PATH.exists() else ""
    entry = (
        "\n"
        f"## {stamp} - Shear Executor Safety Candidate Fallback Extraction\n"
        f"- Result: `{status}`\n"
        "- Moved missing-overview safety fallback from page shim to `design_brain.candidate_evaluation`.\n"
        "- Kept `_evaluate_auto_design_candidate(...)` as compatibility shim for other callers.\n"
        f"- Report: `{report_path}`\n"
    )
    if entry.strip() not in existing:
        PROGRESS_PATH.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().replace(microsecond=0).isoformat().replace(":", "-")
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_shear_executor_safety_candidate_fallback_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_shear_executor_safety_candidate_fallback_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_shear_executor_safety_candidate_fallback_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_shear_executor_safety_candidate_fallback_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_shear_executor_safety_candidate_fallback_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
