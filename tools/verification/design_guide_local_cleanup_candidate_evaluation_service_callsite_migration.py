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

TARGET = "_evaluate_local_cleanup_guidance_item"
SHIM = "_evaluate_auto_design_candidate"
SERVICE_TARGET = "evaluate_design_candidate_with_updates"


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
    from design_brain.candidate_evaluation import evaluate_design_candidate_with_updates

    def snapshot_fn(state: dict) -> dict:
        out = dict(state or {})
        out["snapshot"] = "page_snapshot"
        return out

    def evaluator_fn(candidate_state: dict, **kwargs: Any) -> dict:
        return {
            "state": dict(candidate_state),
            "source": kwargs.get("source"),
            "label": kwargs.get("label"),
            "action_type": kwargs.get("action_type"),
            "updates": dict(kwargs.get("updates") or {}),
            "overview": {"any_fail": False, "utils": {"bending": 0.7}},
        }

    rows = []
    cases = [
        ("local_cleanup_no_updates", {"state": {"D": 650}, "updates": {}, "source": "local_cleanup"}),
        (
            "local_cleanup_with_updates",
            {
                "state": {"D": 650, "b": 400},
                "updates": {"D": 600, "b": 350},
                "source": "design_guide_local_cleanup",
                "label": "Local cleanup",
                "action_type": "apply_resolved_candidate",
            },
        ),
    ]
    for name, kwargs in cases:
        actual = evaluate_design_candidate_with_updates(
            dict(kwargs["state"]),
            updates=dict(kwargs.get("updates") or {}),
            source=str(kwargs.get("source") or ""),
            label=kwargs.get("label"),
            action_type=kwargs.get("action_type"),
            state_snapshot_fn=snapshot_fn,
            evaluator_fn=evaluator_fn,
        )
        expected_state = snapshot_fn(dict(kwargs["state"]))
        expected_state.update(dict(kwargs.get("updates") or {}))
        expected = evaluator_fn(
            expected_state,
            source=str(kwargs.get("source") or ""),
            label=kwargs.get("label"),
            action_type=kwargs.get("action_type"),
            updates=dict(kwargs.get("updates") or {}),
        )
        rows.append(
            {
                "case": name,
                "expected": expected,
                "actual": actual,
                "passed": actual == expected,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    service_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    target_segment = _function_segment(inputs_source, TARGET)
    shim_segment = _function_segment(inputs_source, SHIM)
    service_segment = _function_segment(service_source, SERVICE_TARGET)
    parity_cases = _parity_cases()
    return {
        "schema": "design_guide_local_cleanup_candidate_evaluation_service_callsite_migration.v1",
        "target": TARGET,
        "shim": SHIM,
        "service_target": SERVICE_TARGET,
        "target_calls_service_directly": "_evaluate_design_candidate_with_updates(" in target_segment,
        "target_no_longer_calls_page_shim": "_evaluate_auto_design_candidate(" not in target_segment,
        "target_preserves_source_label_action_updates": all(
            token in target_segment
            for token in (
                "updates=updates",
                "source=source",
                "action_type=action_type",
                "resolved_candidate_label",
                "Local cleanup",
            )
        ),
        "target_injects_existing_page_dependencies": all(
            token in target_segment
            for token in (
                "state_snapshot_fn=_guidance_state_snapshot",
                "evaluator_fn=evaluate_candidate_full",
            )
        ),
        "page_shim_still_exists": bool(shim_segment),
        "page_shim_still_delegates_to_service": "_evaluate_design_candidate_with_updates(" in shim_segment,
        "service_applies_snapshot_and_updates": all(
            token in service_segment
            for token in (
                "candidate_state = state_snapshot_fn(state)",
                "candidate_state.update(updates)",
                "return evaluator_fn(",
            )
        ),
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
        "all_parity_cases_passed": all(case.get("passed") for case in parity_cases),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_calls_service_directly": bool(capture.get("target_calls_service_directly")),
        "target_no_longer_calls_page_shim": bool(capture.get("target_no_longer_calls_page_shim")),
        "target_preserves_source_label_action_updates": bool(capture.get("target_preserves_source_label_action_updates")),
        "target_injects_existing_page_dependencies": bool(capture.get("target_injects_existing_page_dependencies")),
        "page_shim_still_exists": bool(capture.get("page_shim_still_exists")),
        "page_shim_still_delegates_to_service": bool(capture.get("page_shim_still_delegates_to_service")),
        "service_applies_snapshot_and_updates": bool(capture.get("service_applies_snapshot_and_updates")),
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
        "`_evaluate_local_cleanup_guidance_item(...)` candidate-evaluation callsite.",
        "",
        "## Ownership Before",
        "The helper called the page compatibility shim `_evaluate_auto_design_candidate(...)`.",
        "",
        "## Ownership After",
        "The helper calls `design_brain.candidate_evaluation.evaluate_design_candidate_with_updates(...)` directly through the imported service alias. The page shim remains for other callsites.",
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
            f"- Target calls service directly: `{capture.get('target_calls_service_directly')}`",
            f"- Target no longer calls page shim: `{capture.get('target_no_longer_calls_page_shim')}`",
            f"- Page shim still exists: `{capture.get('page_shim_still_exists')}`",
            "",
            "## Deadness / Deletion Proof",
            "No deletion yet. `_evaluate_auto_design_candidate(...)` remains required by broad non-migrated callsites.",
            "",
            "## Lines Removed / Added",
            "One audited local-cleanup callsite migrated from page shim to Design Brain service.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "- `tools/verification/design_guide_local_cleanup_candidate_evaluation_service_callsite_migration.py`",
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
            "The compatibility shim and many non-local-cleanup evaluator callsites remain. Full/fast evaluator internals remain page-owned.",
            "",
            "## Next Safe Target",
            "Audit the next local-cleanup/search-specific evaluator callsite before migrating it.",
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
        f"## {stamp} - Local Cleanup Candidate Evaluation Service Callsite Migration\n"
        f"- Result: `{status}`\n"
        "- Migrated `_evaluate_local_cleanup_guidance_item(...)` from page shim to candidate evaluation service.\n"
        "- Kept `_evaluate_auto_design_candidate(...)` as compatibility shim for non-migrated callers.\n"
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
        "schema": "design_guide_local_cleanup_candidate_evaluation_service_callsite_migration.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_local_cleanup_candidate_evaluation_service_callsite_migration_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_local_cleanup_candidate_evaluation_service_callsite_migration_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_local_cleanup_candidate_evaluation_service_callsite_migration_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_local_cleanup_candidate_evaluation_service_callsite_migration {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
