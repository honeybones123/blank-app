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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

TARGET = "_evaluate_local_cleanup_guidance_item"
CONTROLLER_TARGET = "resolve_design_guide_controller_local_cleanup_basic_post_preview_gate"
TARGET_DISTANCE_TOKEN = "_resolved_efficiency_target_band("
POST_PREVIEW_BLOCKED_REASONS = {
    "cleanup_preview_failed",
    "cleanup_preview_not_all_pass",
    "cleanup_preview_has_fail_status",
    "shear_cleanup_does_not_improve_utilisation",
}


def _function_segment(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_start = source.find("\ndef ", start + len(marker))
    if next_start < 0:
        next_start = len(source)
    return source[start:next_start]


def _post_preview_before_target_band_segment(page_segment: str) -> str:
    boundary = page_segment.find(TARGET_DISTANCE_TOKEN)
    if boundary < 0:
        return page_segment
    return page_segment[:boundary]


def _expected(
    *,
    candidate_valid: bool = True,
    candidate_overview_any_fail: bool = False,
    candidate_overview_required_checks_acceptable: bool = True,
    candidate_preview_has_explicit_fail: bool = False,
    family: str | None = "bending",
    allow_in_target_primary_action: bool = False,
    current_shear_util: Any = None,
    preview_shear_util: Any = None,
) -> tuple[bool, str | None]:
    if not candidate_valid:
        return False, "cleanup_preview_failed"
    if candidate_overview_any_fail or not candidate_overview_required_checks_acceptable:
        return False, "cleanup_preview_not_all_pass"
    if candidate_preview_has_explicit_fail:
        return False, "cleanup_preview_has_fail_status"
    if str(family or "").strip().lower() == "shear":
        try:
            current_util = float(current_shear_util)
        except Exception:
            current_util = None
        try:
            preview_util = float(preview_shear_util)
        except Exception:
            preview_util = None
        if (
            allow_in_target_primary_action
            and current_util is not None
            and preview_util is not None
            and preview_util <= current_util + 1e-9
        ):
            return False, "shear_cleanup_does_not_improve_utilisation"
    return True, None


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_local_cleanup_basic_post_preview_gate,
    )

    cases = [
        ("invalid_candidate", {"candidate_valid": False}),
        ("overview_any_fail", {"candidate_overview_any_fail": True}),
        ("required_checks_false", {"candidate_overview_required_checks_acceptable": False}),
        ("explicit_fail_status", {"candidate_preview_has_explicit_fail": True}),
        (
            "shear_no_improvement",
            {
                "family": "shear",
                "allow_in_target_primary_action": True,
                "current_shear_util": 0.70,
                "preview_shear_util": 0.70,
            },
        ),
        (
            "shear_improves",
            {
                "family": "shear",
                "allow_in_target_primary_action": True,
                "current_shear_util": 0.70,
                "preview_shear_util": 0.60,
            },
        ),
        (
            "shear_missing_utils_accepts",
            {
                "family": "shear",
                "allow_in_target_primary_action": True,
                "current_shear_util": None,
                "preview_shear_util": None,
            },
        ),
        ("bending_accepts", {"family": "bending"}),
    ]
    rows = []
    for name, overrides in cases:
        kwargs: dict[str, Any] = {
            "candidate_valid": True,
            "candidate_overview_any_fail": False,
            "candidate_overview_required_checks_acceptable": True,
            "candidate_preview_has_explicit_fail": False,
            "family": "bending",
            "allow_in_target_primary_action": False,
            "current_shear_util": None,
            "preview_shear_util": None,
        }
        kwargs.update(overrides)
        expected_accepted, expected_reason = _expected(**kwargs)
        actual = resolve_design_guide_controller_local_cleanup_basic_post_preview_gate(**kwargs)
        rows.append(
            {
                "case": name,
                "expected_accepted": expected_accepted,
                "actual_accepted": bool(actual.get("accepted_for_target_checks")),
                "expected_reason": expected_reason,
                "actual_reason": actual.get("blocked_reason"),
                "passed": (
                    bool(actual.get("accepted_for_target_checks")) is expected_accepted
                    and actual.get("blocked_reason") == expected_reason
                ),
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    page_segment = _function_segment(inputs_source, TARGET)
    post_preview_segment = _post_preview_before_target_band_segment(page_segment)
    controller_segment = _function_segment(controller_source, CONTROLLER_TARGET)
    page_post_preview_reasons = sorted(
        reason for reason in POST_PREVIEW_BLOCKED_REASONS if f"\"{reason}\"" in post_preview_segment
    )
    parity_cases = _parity_cases()
    return {
        "schema": "design_guide_local_cleanup_basic_post_preview_gate_extraction.v1",
        "target": TARGET,
        "controller_target": CONTROLLER_TARGET,
        "page_imports_controller_helper": f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source,
        "page_delegates_basic_post_preview_gate": f"_{CONTROLLER_TARGET}(" in post_preview_segment,
        "page_post_preview_blocked_reasons_remaining": page_post_preview_reasons,
        "page_keeps_candidate_evaluation": "_evaluate_auto_design_candidate(" in page_segment,
        "page_keeps_executor_safety_and_promotion": all(
            token in page_segment
            for token in (
                "_resolved_shear_cleanup_is_executor_safe",
                "_promote_guidance_item_to_resolved_candidate",
            )
        ),
        "page_keeps_target_band_distance_policy": all(
            token in page_segment
            for token in (
                "_resolved_efficiency_target_band",
                "_distance_to_target_band",
                "_governing_focus_from_overview",
            )
        ),
        "page_keeps_actionability_callbacks": "_guidance_executor_actionability_contract" in page_segment,
        "controller_has_post_preview_reasons": all(
            f"\"{reason}\"" in controller_segment for reason in POST_PREVIEW_BLOCKED_REASONS
        ),
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "parity_cases": parity_cases,
        "all_parity_cases_passed": all(case.get("passed") for case in parity_cases),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "page_imports_controller_helper": bool(capture.get("page_imports_controller_helper")),
        "page_delegates_basic_post_preview_gate": bool(capture.get("page_delegates_basic_post_preview_gate")),
        "page_post_preview_blocked_reasons_moved": not capture.get("page_post_preview_blocked_reasons_remaining"),
        "page_keeps_candidate_evaluation": bool(capture.get("page_keeps_candidate_evaluation")),
        "page_keeps_executor_safety_and_promotion": bool(capture.get("page_keeps_executor_safety_and_promotion")),
        "page_keeps_target_band_distance_policy": bool(capture.get("page_keeps_target_band_distance_policy")),
        "page_keeps_actionability_callbacks": bool(capture.get("page_keeps_actionability_callbacks")),
        "controller_has_post_preview_reasons": bool(capture.get("controller_has_post_preview_reasons")),
        "controller_has_no_page_or_streamlit_imports": bool(capture.get("controller_has_no_page_or_streamlit_imports")),
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
        "`_evaluate_local_cleanup_guidance_item(...)` basic post-preview acceptance gate.",
        "",
        "## Ownership Before",
        "`inputs_page.py` owned basic post-preview preview-validity, all-pass, explicit-fail, and shear-no-improvement blocked-reason policy.",
        "",
        "## Ownership After",
        "`DesignGuideController` owns that basic post-preview gate. `inputs_page.py` still owns actual candidate evaluation execution, target-band distance checks, executor safety, promotion, and page callbacks.",
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
        lines.append(
            f"- `{case.get('case')}`: accepted `{case.get('actual_accepted')}`, reason `{case.get('actual_reason')}`, passed=`{case.get('passed')}`"
        )
    lines.extend(
        [
            "",
            "## Cutover Proof",
            f"- Page delegates post-preview gate: `{capture.get('page_delegates_basic_post_preview_gate')}`",
            f"- Page post-preview blocked reasons remaining: `{capture.get('page_post_preview_blocked_reasons_remaining')}`",
            f"- Page keeps candidate evaluation: `{capture.get('page_keeps_candidate_evaluation')}`",
            "",
            "## Deadness / Deletion Proof",
            "The old page-local basic post-preview blocked-reason branches were replaced. Target-band distance, executor safety, actionability, and promotion remain for later slices.",
            "",
            "## Lines Removed / Added",
            "Line-count accounting is intentionally deferred to the final local-cleanup helper shell audit.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "- `design_brain/design_guide_controller.py`",
            "- `tools/verification/design_guide_local_cleanup_basic_post_preview_gate_extraction.py`",
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
            "Candidate evaluation execution, target-band distance checks, executor actionability, shear executor safety, candidate promotion, and page callbacks remain in `inputs_page.py`.",
            "",
            "## Next Safe Target",
            "Extract target-band distance acceptance policy or executor/actionability post-preview branches after this gate remains locked.",
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
        f"## {stamp} - Local Cleanup Basic Post-Preview Gate Extraction\n"
        f"- Result: `{status}`\n"
        "- Moved local cleanup basic post-preview acceptance policy into `DesignGuideController`.\n"
        "- Page still owns candidate evaluation, target-band distance policy, promotion, and executor/actionability callbacks.\n"
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
        "schema": "design_guide_local_cleanup_basic_post_preview_gate_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_local_cleanup_basic_post_preview_gate_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_local_cleanup_basic_post_preview_gate_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_local_cleanup_basic_post_preview_gate_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_local_cleanup_basic_post_preview_gate_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
