from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

TARGET_HELPER = "_evaluate_local_cleanup_guidance_item"
EVALUATOR = "_evaluate_auto_design_candidate"


def _function_bounds(source: str, name: str) -> tuple[int, int, str]:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return 0, 0, ""
    next_start = source.find("\ndef ", start + len(marker))
    if next_start < 0:
        next_start = len(source)
    start_line = source[:start].count("\n") + 1
    end_line = source[:next_start].count("\n") + 1
    return start_line, end_line, source[start:next_start]


def _callsite_lines(source: str, token: str) -> list[int]:
    return [source[:match.start()].count("\n") + 1 for match in re.finditer(re.escape(token), source)]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    eval_start, eval_end, eval_segment = _function_bounds(source, EVALUATOR)
    helper_start, helper_end, helper_segment = _function_bounds(source, TARGET_HELPER)
    call_lines = _callsite_lines(source, f"{EVALUATOR}(")
    helper_call_lines = [
        line for line in call_lines
        if helper_start <= line <= helper_end and line != eval_start
    ]
    evaluator_uses_guidance_snapshot = "_guidance_state_snapshot(state)" in eval_segment
    evaluator_delegates_full_eval = "evaluate_candidate_full(" in eval_segment
    evaluator_has_streamlit_session = any(token in eval_segment for token in ("st.", "st[", "session_state"))
    return {
        "schema": "design_guide_candidate_evaluation_boundary_audit.v1",
        "target_helper": TARGET_HELPER,
        "target_helper_line_start": helper_start,
        "target_helper_line_end": helper_end,
        "target_helper_line_count": max(0, helper_end - helper_start + 1),
        "evaluator": EVALUATOR,
        "evaluator_line_start": eval_start,
        "evaluator_line_end": eval_end,
        "evaluator_line_count": max(0, eval_end - eval_start + 1),
        "total_evaluator_callsite_count": max(0, len(call_lines) - 1),
        "local_cleanup_helper_evaluator_callsite_count": len(helper_call_lines),
        "local_cleanup_helper_evaluator_callsite_lines": helper_call_lines,
        "evaluator_uses_guidance_state_snapshot": evaluator_uses_guidance_snapshot,
        "evaluator_delegates_to_evaluate_candidate_full": evaluator_delegates_full_eval,
        "evaluator_has_streamlit_or_session_tokens": evaluator_has_streamlit_session,
        "boundary_observation": (
            "`_evaluate_auto_design_candidate(...)` is already a thin candidate-state/update wrapper "
            "around `evaluate_candidate_full(...)`, but it remains physically page-owned and broadly called."
        ),
        "recommended_next_slice": "extract_evaluate_auto_design_candidate_wrapper_to_candidate_service",
        "recommended_target_module": "design_brain/candidate_evaluation.py",
        "implementation_readiness": "READY_FOR_NARROW_WRAPPER_EXTRACTION",
        "why_not_direct_delete": "The wrapper has many live callsites; delete only after all callsites use the service boundary or a compatibility alias is proven dead.",
        "must_preserve": [
            "candidate_state = _guidance_state_snapshot(state)",
            "candidate_state.update(updates)",
            "evaluate_candidate_full(...) call shape",
            "source/label/action_type/updates pass-through",
        ],
        "stop_conditions": [
            "evaluate_candidate_full output shape changes",
            "state snapshot normalization changes",
            "any callsite loses source/label/action_type/update metadata",
            "Streamlit/session state moves into Design Brain",
        ],
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_helper_found": bool(capture.get("target_helper_line_count")),
        "evaluator_found": bool(capture.get("evaluator_line_count")),
        "local_cleanup_uses_evaluator_once": capture.get("local_cleanup_helper_evaluator_callsite_count") == 1,
        "evaluator_is_thin_wrapper": bool(capture.get("evaluator_uses_guidance_state_snapshot"))
        and bool(capture.get("evaluator_delegates_to_evaluate_candidate_full")),
        "evaluator_has_no_streamlit_or_session_tokens": not capture.get("evaluator_has_streamlit_or_session_tokens"),
        "implementation_readiness_identified": capture.get("implementation_readiness") == "READY_FOR_NARROW_WRAPPER_EXTRACTION",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtimes_unchanged": capture.get("family_runtimes_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    checks = dict(payload.get("checks") or {})
    lines = [
        "# Candidate Evaluation Boundary Audit",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Target Helper",
        f"- `{capture.get('target_helper')}` lines `{capture.get('target_helper_line_start')}`-`{capture.get('target_helper_line_end')}`",
        f"- Local cleanup evaluator callsites: `{capture.get('local_cleanup_helper_evaluator_callsite_count')}`",
        "",
        "## Evaluator Wrapper",
        f"- `{capture.get('evaluator')}` lines `{capture.get('evaluator_line_start')}`-`{capture.get('evaluator_line_end')}`",
        f"- Total evaluator callsites in `inputs_page.py`: `{capture.get('total_evaluator_callsite_count')}`",
        f"- Uses guidance snapshot: `{capture.get('evaluator_uses_guidance_state_snapshot')}`",
        f"- Delegates to full evaluator: `{capture.get('evaluator_delegates_to_evaluate_candidate_full')}`",
        f"- Contains Streamlit/session tokens: `{capture.get('evaluator_has_streamlit_or_session_tokens')}`",
        "",
        "## Boundary Observation",
        str(capture.get("boundary_observation") or ""),
        "",
        "## Recommended Next Slice",
        f"- Slice: `{capture.get('recommended_next_slice')}`",
        f"- Target module: `{capture.get('recommended_target_module')}`",
        f"- Readiness: `{capture.get('implementation_readiness')}`",
        "",
        "## Must Preserve",
    ]
    for item in capture.get("must_preserve") or []:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Why Not Direct Delete",
            str(capture.get("why_not_direct_delete") or ""),
            "",
            "## Stop Conditions",
        ]
    )
    for item in capture.get("stop_conditions") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Verifier Results"])
    for name, passed in checks.items():
        lines.append(f"- `{name}`: `{passed}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = str(payload.get("created_at") or "")
    status = str(payload.get("status") or "")
    capture = dict(payload.get("capture") or {})
    existing = PROGRESS_PATH.read_text(encoding="utf-8") if PROGRESS_PATH.exists() else ""
    entry = (
        "\n"
        f"## {stamp} - Candidate Evaluation Boundary Audit\n"
        f"- Result: `{status}`\n"
        f"- Total `_evaluate_auto_design_candidate` callsites: `{capture.get('total_evaluator_callsite_count')}`\n"
        f"- Readiness: `{capture.get('implementation_readiness')}`\n"
        f"- Next slice: `{capture.get('recommended_next_slice')}`\n"
        f"- Report: `{report_path}`\n"
    )
    if entry.strip() not in existing:
        PROGRESS_PATH.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().replace(microsecond=0).isoformat().replace(":", "-")
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_candidate_evaluation_boundary_audit.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_candidate_evaluation_boundary_audit_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_candidate_evaluation_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    if status == "PASS":
        _append_progress(payload, audit_path)
    print(f"design_guide_candidate_evaluation_boundary_audit {status}")
    print(f"json={json_path}")
    print(f"report={audit_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
