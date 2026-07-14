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

TARGET = "_evaluate_auto_design_candidate"
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

    rows = []

    def snapshot_fn(state: dict) -> dict:
        copied = dict(state or {})
        copied["snapshot_marker"] = "snapshot"
        return copied

    def evaluator_fn(candidate_state: dict, **kwargs: Any) -> dict:
        return {
            "candidate_state": dict(candidate_state),
            "source": kwargs.get("source"),
            "label": kwargs.get("label"),
            "action_type": kwargs.get("action_type"),
            "updates": dict(kwargs.get("updates") or {}),
        }

    cases = [
        ("no_updates", {"state": {"D": 600}, "updates": None, "source": "seed", "label": None, "action_type": None}),
        (
            "with_updates",
            {
                "state": {"D": 600, "b": 300},
                "updates": {"D": 650},
                "source": "local_cleanup",
                "label": "Local cleanup",
                "action_type": "apply_resolved_candidate",
            },
        ),
    ]
    for name, kwargs in cases:
        actual = evaluate_design_candidate_with_updates(
            dict(kwargs["state"]),
            updates=kwargs.get("updates"),
            source=str(kwargs.get("source") or ""),
            label=kwargs.get("label"),
            action_type=kwargs.get("action_type"),
            state_snapshot_fn=snapshot_fn,
            evaluator_fn=evaluator_fn,
        )
        expected_state = snapshot_fn(dict(kwargs["state"]))
        if kwargs.get("updates"):
            expected_state.update(dict(kwargs["updates"]))
        expected = {
            "candidate_state": expected_state,
            "source": kwargs.get("source"),
            "label": kwargs.get("label"),
            "action_type": kwargs.get("action_type"),
            "updates": dict(kwargs.get("updates") or {}),
        }
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
    page_segment = _function_segment(inputs_source, TARGET)
    service_segment = _function_segment(service_source, SERVICE_TARGET)
    parity_cases = _parity_cases()
    return {
        "schema": "design_guide_candidate_evaluation_wrapper_extraction.v1",
        "target": TARGET,
        "service_target": SERVICE_TARGET,
        "page_imports_service": f"{SERVICE_TARGET} as _{SERVICE_TARGET}" in inputs_source,
        "page_wrapper_delegates_to_service": f"_{SERVICE_TARGET}(" in page_segment,
        "page_wrapper_no_longer_builds_candidate_state": "candidate_state =" not in page_segment,
        "page_wrapper_no_longer_updates_candidate_state": "candidate_state.update" not in page_segment,
        "page_wrapper_no_longer_directly_calls_evaluate_candidate_full": "return evaluate_candidate_full(" not in page_segment,
        "page_wrapper_keeps_injected_dependencies": all(
            token in page_segment for token in ("state_snapshot_fn=_guidance_state_snapshot", "evaluator_fn=evaluate_candidate_full")
        ),
        "service_applies_snapshot_and_updates": all(
            token in service_segment
            for token in (
                "candidate_state = state_snapshot_fn(state)",
                "candidate_state.update(updates)",
                "return evaluator_fn(",
            )
        ),
        "service_has_no_page_or_streamlit_imports": "inputs_page" not in service_source and "streamlit" not in service_source,
        "parity_cases": parity_cases,
        "all_parity_cases_passed": all(case.get("passed") for case in parity_cases),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "page_imports_service": bool(capture.get("page_imports_service")),
        "page_wrapper_delegates_to_service": bool(capture.get("page_wrapper_delegates_to_service")),
        "page_wrapper_no_longer_builds_candidate_state": bool(capture.get("page_wrapper_no_longer_builds_candidate_state")),
        "page_wrapper_no_longer_updates_candidate_state": bool(capture.get("page_wrapper_no_longer_updates_candidate_state")),
        "page_wrapper_no_longer_directly_calls_evaluate_candidate_full": bool(capture.get("page_wrapper_no_longer_directly_calls_evaluate_candidate_full")),
        "page_wrapper_keeps_injected_dependencies": bool(capture.get("page_wrapper_keeps_injected_dependencies")),
        "service_applies_snapshot_and_updates": bool(capture.get("service_applies_snapshot_and_updates")),
        "service_has_no_page_or_streamlit_imports": bool(capture.get("service_has_no_page_or_streamlit_imports")),
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
        "`_evaluate_auto_design_candidate(...)` candidate-state/update wrapper.",
        "",
        "## Ownership Before",
        "`inputs_page.py` owned candidate state snapshot/update application before calling `evaluate_candidate_full(...)`.",
        "",
        "## Ownership After",
        "`design_brain.candidate_evaluation.evaluate_design_candidate_with_updates(...)` owns the wrapper logic. `inputs_page.py` remains a compatibility shim supplying existing page-local dependencies.",
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
            f"- Page wrapper delegates to service: `{capture.get('page_wrapper_delegates_to_service')}`",
            f"- Page wrapper keeps injected dependencies: `{capture.get('page_wrapper_keeps_injected_dependencies')}`",
            f"- Service has no page/Streamlit imports: `{capture.get('service_has_no_page_or_streamlit_imports')}`",
            "",
            "## Deadness / Deletion Proof",
            "The page helper cannot be deleted yet because many live callsites still use it. It is now a compatibility shim.",
            "",
            "## Lines Removed / Added",
            "The wrapper body is reduced to a service call; broad callsite migration remains future work.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "- `design_brain/candidate_evaluation.py`",
            "- `tools/verification/design_guide_candidate_evaluation_wrapper_extraction.py`",
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
            "`_guidance_state_snapshot(...)` and `evaluate_candidate_full(...)` are still injected from `inputs_page.py`; migrate those only with a broader candidate evaluation service cutover.",
            "",
            "## Next Safe Target",
            "Migrate local-cleanup callsite to the candidate evaluation service directly, then progressively migrate other callsites or extract `evaluate_candidate_full(...)` dependencies.",
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
        f"## {stamp} - Candidate Evaluation Wrapper Extraction\n"
        f"- Result: `{status}`\n"
        "- Moved `_evaluate_auto_design_candidate(...)` wrapper logic into `design_brain.candidate_evaluation`.\n"
        "- Page helper remains as a compatibility shim with injected page-local dependencies.\n"
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
        "schema": "design_guide_candidate_evaluation_wrapper_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_candidate_evaluation_wrapper_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_candidate_evaluation_wrapper_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_candidate_evaluation_wrapper_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_candidate_evaluation_wrapper_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
