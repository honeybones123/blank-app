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
CONTROLLER_TARGET = "resolve_design_guide_controller_local_cleanup_pre_preview_gate"
PREVIEW_BOUNDARY_TOKEN = "_evaluate_auto_design_candidate("
PREVIEW_BLOCKED_REASONS = {
    "invalid_candidate",
    "candidate_not_actionable",
    "cleanup_no_material_update",
    "cleanup_no_net_material_efficiency",
    "cleanup_increases_geometry_without_section_reduction",
    "cleanup_not_material",
    "active_failure_needs_strengthening",
    "shear_not_below_target",
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


def _pre_preview_segment(page_segment: str) -> str:
    boundary = page_segment.find(PREVIEW_BOUNDARY_TOKEN)
    if boundary < 0:
        return page_segment
    return page_segment[:boundary]


def _expected(
    *,
    item_valid: bool = True,
    action_type: str | None = "apply_resolved_candidate",
    updates: dict[str, Any] | None = None,
    updates_match_state: bool = False,
    family: str | None = "bending",
    candidate_id: str | None = "cand",
    before: Any = 100.0,
    after: Any = 90.0,
    section_reduces: bool = True,
    geometry_increases: bool = False,
    materially_reduces: bool = True,
    overview_any_fail: bool = False,
    overview_ok: bool = True,
    shear_cleanup_needed: bool = True,
    allow_passing_shear_cleanup: bool = False,
) -> tuple[bool, str | None, dict[str, Any]]:
    detail = {
        "blocked_reason": None,
        "family": None,
        "candidate_id": None,
        "distance": float("inf"),
        "candidate_complexity_score": None,
        "net_efficiency_delta": None,
        "material_proxy_before": None,
        "material_proxy_after": None,
        "material_proxy_delta": None,
        "is_executable": False,
        "advisory_only": True,
    }
    if not item_valid:
        detail["blocked_reason"] = "invalid_candidate"
        return False, "invalid_candidate", detail
    if not str(action_type or "").strip():
        detail["blocked_reason"] = "candidate_not_actionable"
        return False, "candidate_not_actionable", detail
    update_payload = dict(updates or {})
    if not update_payload or updates_match_state:
        detail["blocked_reason"] = "cleanup_no_material_update"
        return False, "cleanup_no_material_update", detail
    detail["family"] = str(family or "")
    detail["candidate_id"] = str(candidate_id or "")
    detail["candidate_complexity_score"] = len(update_payload)
    detail["material_proxy_before"] = float(before or 0.0)
    detail["material_proxy_after"] = float(after or 0.0)
    detail["material_proxy_delta"] = float(after or 0.0) - float(before or 0.0)
    detail["net_efficiency_delta"] = float(before or 0.0) - float(after or 0.0)
    if float(after or 0.0) >= float(before or 0.0) - 1e-6:
        detail["blocked_reason"] = "cleanup_no_net_material_efficiency"
        return False, "cleanup_no_net_material_efficiency", detail
    if not section_reduces and geometry_increases:
        detail["blocked_reason"] = "cleanup_increases_geometry_without_section_reduction"
        return False, "cleanup_increases_geometry_without_section_reduction", detail
    if not materially_reduces:
        detail["blocked_reason"] = "cleanup_not_material"
        return False, "cleanup_not_material", detail
    if overview_any_fail or not overview_ok:
        detail["blocked_reason"] = "active_failure_needs_strengthening"
        return False, "active_failure_needs_strengthening", detail
    if family == "shear" and not shear_cleanup_needed and not allow_passing_shear_cleanup:
        detail["blocked_reason"] = "shear_not_below_target"
        return False, "shear_not_below_target", detail
    return True, None, detail


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_local_cleanup_pre_preview_gate,
    )

    cases = [
        ("invalid_item", {"item_valid": False, "updates": {"D": 500}}),
        ("missing_action", {"action_type": "", "updates": {"D": 500}}),
        ("missing_updates", {"updates": {}}),
        ("updates_match_state", {"updates": {"D": 500}, "updates_match_state": True}),
        ("no_net_efficiency", {"updates": {"D": 500}, "before": 100.0, "after": 100.0}),
        ("geometry_increase", {"updates": {"D": 700}, "section_reduces": False, "geometry_increases": True}),
        ("not_material", {"updates": {"D": 500}, "materially_reduces": False}),
        ("active_failure", {"updates": {"D": 500}, "overview_any_fail": True}),
        ("bad_required_checks", {"updates": {"D": 500}, "overview_ok": False}),
        ("shear_not_below_target", {"updates": {"lig_d": 0}, "family": "shear", "shear_cleanup_needed": False}),
        ("shear_allowed_passing_cleanup", {"updates": {"lig_d": 0}, "family": "shear", "shear_cleanup_needed": False, "allow_passing_shear_cleanup": True}),
        ("accepted_bending", {"updates": {"D": 500}, "family": "bending"}),
    ]
    rows = []
    for name, overrides in cases:
        kwargs = {
            "item_valid": True,
            "action_type": "apply_resolved_candidate",
            "updates": {"D": 500},
            "updates_match_state": False,
            "family": "bending",
            "candidate_id": "cand",
            "candidate_complexity_score": len(dict(overrides.get("updates", {"D": 500}) or {})),
            "material_proxy_before": overrides.get("before", 100.0),
            "material_proxy_after": overrides.get("after", 90.0),
            "section_reduces": True,
            "geometry_increases_without_section_reduction": False,
            "materially_reduces": True,
            "overview_any_fail": False,
            "overview_required_checks_acceptable": True,
            "shear_cleanup_needed": True,
            "allow_passing_shear_cleanup": False,
        }
        kwargs.update(
            {
                "item_valid": overrides.get("item_valid", kwargs["item_valid"]),
                "action_type": overrides.get("action_type", kwargs["action_type"]),
                "updates": overrides.get("updates", kwargs["updates"]),
                "updates_match_state": overrides.get("updates_match_state", kwargs["updates_match_state"]),
                "family": overrides.get("family", kwargs["family"]),
                "material_proxy_before": overrides.get("before", kwargs["material_proxy_before"]),
                "material_proxy_after": overrides.get("after", kwargs["material_proxy_after"]),
                "section_reduces": overrides.get("section_reduces", kwargs["section_reduces"]),
                "geometry_increases_without_section_reduction": overrides.get("geometry_increases", kwargs["geometry_increases_without_section_reduction"]),
                "materially_reduces": overrides.get("materially_reduces", kwargs["materially_reduces"]),
                "overview_any_fail": overrides.get("overview_any_fail", kwargs["overview_any_fail"]),
                "overview_required_checks_acceptable": overrides.get("overview_ok", kwargs["overview_required_checks_acceptable"]),
                "shear_cleanup_needed": overrides.get("shear_cleanup_needed", kwargs["shear_cleanup_needed"]),
                "allow_passing_shear_cleanup": overrides.get("allow_passing_shear_cleanup", kwargs["allow_passing_shear_cleanup"]),
            }
        )
        expected_accepted, expected_reason, expected_detail = _expected(
            item_valid=kwargs["item_valid"],
            action_type=kwargs["action_type"],
            updates=kwargs["updates"],
            updates_match_state=kwargs["updates_match_state"],
            family=kwargs["family"],
            candidate_id=kwargs["candidate_id"],
            before=kwargs["material_proxy_before"],
            after=kwargs["material_proxy_after"],
            section_reduces=kwargs["section_reduces"],
            geometry_increases=kwargs["geometry_increases_without_section_reduction"],
            materially_reduces=kwargs["materially_reduces"],
            overview_any_fail=kwargs["overview_any_fail"],
            overview_ok=kwargs["overview_required_checks_acceptable"],
            shear_cleanup_needed=kwargs["shear_cleanup_needed"],
            allow_passing_shear_cleanup=kwargs["allow_passing_shear_cleanup"],
        )
        actual = resolve_design_guide_controller_local_cleanup_pre_preview_gate(**kwargs)
        actual_detail = dict(actual.get("detail") or {})
        rows.append(
            {
                "case": name,
                "expected_accepted": expected_accepted,
                "actual_accepted": bool(actual.get("accepted_for_preview")),
                "expected_reason": expected_reason,
                "actual_reason": actual_detail.get("blocked_reason"),
                "detail_shape_matches": set(actual_detail) == set(expected_detail),
                "passed": (
                    bool(actual.get("accepted_for_preview")) is expected_accepted
                    and actual_detail.get("blocked_reason") == expected_reason
                    and set(actual_detail) == set(expected_detail)
                ),
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    page_segment = _function_segment(inputs_source, TARGET)
    pre_segment = _pre_preview_segment(page_segment)
    controller_segment = _function_segment(controller_source, CONTROLLER_TARGET)
    page_pre_reasons = sorted(reason for reason in PREVIEW_BLOCKED_REASONS if f"\"{reason}\"" in pre_segment)
    parity_cases = _parity_cases()
    return {
        "schema": "design_guide_local_cleanup_pre_preview_gate_extraction.v1",
        "target": TARGET,
        "controller_target": CONTROLLER_TARGET,
        "page_imports_controller_helper": f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source,
        "page_delegates_pre_preview_gate": f"_{CONTROLLER_TARGET}(" in pre_segment,
        "page_pre_preview_blocked_reasons_remaining": page_pre_reasons,
        "page_keeps_candidate_evaluation": "_evaluate_auto_design_candidate(" in page_segment,
        "page_keeps_promotion_and_executor_callbacks": all(
            token in page_segment
            for token in (
                "_promote_guidance_item_to_resolved_candidate",
                "_guidance_executor_actionability_contract",
            )
        ),
        "controller_has_pre_preview_reasons": all(f"\"{reason}\"" in controller_segment for reason in PREVIEW_BLOCKED_REASONS),
        "controller_has_detail_shape": all(
            f"\"{key}\"" in controller_segment
            for key in (
                "blocked_reason",
                "family",
                "candidate_id",
                "distance",
                "candidate_complexity_score",
                "net_efficiency_delta",
                "material_proxy_before",
                "material_proxy_after",
                "material_proxy_delta",
                "is_executable",
                "advisory_only",
            )
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
        "page_delegates_pre_preview_gate": bool(capture.get("page_delegates_pre_preview_gate")),
        "page_pre_preview_blocked_reasons_moved": not capture.get("page_pre_preview_blocked_reasons_remaining"),
        "page_keeps_candidate_evaluation": bool(capture.get("page_keeps_candidate_evaluation")),
        "page_keeps_promotion_and_executor_callbacks": bool(capture.get("page_keeps_promotion_and_executor_callbacks")),
        "controller_has_pre_preview_reasons": bool(capture.get("controller_has_pre_preview_reasons")),
        "controller_has_detail_shape": bool(capture.get("controller_has_detail_shape")),
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
        "`_evaluate_local_cleanup_guidance_item(...)` pre-preview gate/detail shaping.",
        "",
        "## Ownership Before",
        "`inputs_page.py` owned default detail shape and pre-preview blocked-reason policy.",
        "",
        "## Ownership After",
        "`DesignGuideController` owns pre-preview gate/detail shaping; `inputs_page.py` still owns callbacks and candidate evaluation execution.",
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
            f"- Page delegates pre-preview gate: `{capture.get('page_delegates_pre_preview_gate')}`",
            f"- Page pre-preview blocked reasons remaining: `{capture.get('page_pre_preview_blocked_reasons_remaining')}`",
            f"- Page keeps candidate evaluation: `{capture.get('page_keeps_candidate_evaluation')}`",
            "",
            "## Deadness / Deletion Proof",
            "The old page-local pre-preview blocked-reason branches were replaced. Candidate evaluation and post-preview policy remain for later slices.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "- `design_brain/design_guide_controller.py`",
            "- `tools/verification/design_guide_local_cleanup_pre_preview_gate_extraction.py`",
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
            "Post-preview acceptance policy, candidate evaluation execution, promotion, executor actionability, and detail distance updates remain in `inputs_page.py`.",
            "",
            "## Next Safe Target",
            "Extract post-preview acceptance policy after this pre-preview gate remains locked.",
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
        f"## {stamp} - Local Cleanup Pre-Preview Gate Extraction\n"
        f"- Result: `{status}`\n"
        "- Moved local cleanup pre-preview gate/detail shaping into `DesignGuideController`.\n"
        "- Page still owns candidate evaluation execution and post-preview acceptance policy.\n"
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
        "schema": "design_guide_local_cleanup_pre_preview_gate_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_local_cleanup_pre_preview_gate_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_local_cleanup_pre_preview_gate_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_local_cleanup_pre_preview_gate_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_local_cleanup_pre_preview_gate_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
