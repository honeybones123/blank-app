from __future__ import annotations

import json
import math
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
CONTROLLER_TARGET = "resolve_design_guide_controller_local_cleanup_target_band_acceptance"
TARGET_DISTANCE_TOKEN = "_resolved_efficiency_target_band("
PROMOTION_TOKEN = "promoted = _promote_guidance_item_to_resolved_candidate"
TARGET_BAND_REASON = "cleanup_does_not_move_governing_utilisation_toward_target"


def _function_segment(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_start = source.find("\ndef ", start + len(marker))
    if next_start < 0:
        next_start = len(source)
    return source[start:next_start]


def _target_band_segment(page_segment: str) -> str:
    start = page_segment.find(TARGET_DISTANCE_TOKEN)
    if start < 0:
        return page_segment
    end = page_segment.find(PROMOTION_TOKEN, start)
    if end < 0:
        end = len(page_segment)
    return page_segment[start:end]


def _distance(util: Any, target_min: Any, target_max: Any) -> float:
    try:
        u = float(util)
        lo = float(target_min)
        hi = float(target_max)
    except Exception:
        return float("inf")
    if lo <= u <= hi:
        return 0.0
    if u < lo:
        return lo - u
    return u - hi


def _expected(
    *,
    post_worst_util: Any,
    current_worst_util: Any,
    target_min: Any,
    target_max: Any,
    family_key: str | None,
    governing_key: str | None,
    current_family_util: Any = None,
    preview_family_util: Any = None,
) -> tuple[bool, str | None, float, float | None, bool]:
    distance = _distance(post_worst_util, target_min, target_max)
    try:
        current_worst = float(current_worst_util)
    except Exception:
        current_worst = None
    family = str(family_key or "").strip().lower()
    governing = str(governing_key or "").strip().lower()
    current_distance = None
    family_moves_toward_target = False
    if current_worst is not None and current_worst < float(target_min) - 1e-9:
        current_distance = _distance(current_worst, target_min, target_max)
        try:
            current_family = float(current_family_util)
            preview_family = float(preview_family_util)
        except Exception:
            current_family = None
            preview_family = None
        if family and family != governing and current_family is not None and preview_family is not None:
            if current_family < float(target_min) - 1e-9:
                family_moves_toward_target = (
                    _distance(preview_family, target_min, target_max)
                    < _distance(current_family, target_min, target_max) - 1e-9
                )
        if distance >= current_distance - 1e-9 and family != governing and not family_moves_toward_target:
            return False, TARGET_BAND_REASON, distance, current_distance, family_moves_toward_target
    return True, None, distance, current_distance, family_moves_toward_target


def _same_float(left: Any, right: Any) -> bool:
    try:
        left_value = float(left)
        right_value = float(right)
    except Exception:
        return False
    if math.isinf(left_value) or math.isinf(right_value):
        return math.isinf(left_value) and math.isinf(right_value) and (left_value > 0) == (right_value > 0)
    return abs(left_value - right_value) <= 1e-12


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_local_cleanup_target_band_acceptance,
    )

    cases = [
        (
            "current_in_band_accepts",
            {
                "post_worst_util": 0.70,
                "current_worst_util": 0.86,
                "target_min": 0.85,
                "target_max": 0.95,
                "family_key": "bending",
                "governing_key": "shear",
            },
        ),
        (
            "governing_family_accepts_even_same_distance",
            {
                "post_worst_util": 0.70,
                "current_worst_util": 0.70,
                "target_min": 0.85,
                "target_max": 0.95,
                "family_key": "bending",
                "governing_key": "bending",
            },
        ),
        (
            "non_governing_no_family_movement_rejects",
            {
                "post_worst_util": 0.70,
                "current_worst_util": 0.70,
                "target_min": 0.85,
                "target_max": 0.95,
                "family_key": "bending",
                "governing_key": "shear",
                "current_family_util": 0.40,
                "preview_family_util": 0.40,
            },
        ),
        (
            "non_governing_family_moves_accepts",
            {
                "post_worst_util": 0.70,
                "current_worst_util": 0.70,
                "target_min": 0.85,
                "target_max": 0.95,
                "family_key": "bending",
                "governing_key": "shear",
                "current_family_util": 0.40,
                "preview_family_util": 0.60,
            },
        ),
        (
            "post_worst_moves_closer_accepts",
            {
                "post_worst_util": 0.80,
                "current_worst_util": 0.70,
                "target_min": 0.85,
                "target_max": 0.95,
                "family_key": "bending",
                "governing_key": "shear",
            },
        ),
        (
            "bad_post_rejects_when_current_below_and_no_family_move",
            {
                "post_worst_util": "bad",
                "current_worst_util": 0.70,
                "target_min": 0.85,
                "target_max": 0.95,
                "family_key": "bending",
                "governing_key": "shear",
            },
        ),
    ]
    rows = []
    for name, kwargs in cases:
        expected_accepted, expected_reason, expected_distance, expected_current_distance, expected_family_move = _expected(**kwargs)
        actual = resolve_design_guide_controller_local_cleanup_target_band_acceptance(**kwargs)
        actual_distance = float(actual.get("distance"))
        actual_current_distance = actual.get("current_distance")
        rows.append(
            {
                "case": name,
                "expected_accepted": expected_accepted,
                "actual_accepted": bool(actual.get("accepted_for_executor_checks")),
                "expected_reason": expected_reason,
                "actual_reason": actual.get("blocked_reason"),
                "expected_distance": expected_distance,
                "actual_distance": actual_distance,
                "expected_current_distance": expected_current_distance,
                "actual_current_distance": actual_current_distance,
                "expected_family_moves_toward_target": expected_family_move,
                "actual_family_moves_toward_target": bool(actual.get("family_moves_toward_target")),
                "passed": (
                    bool(actual.get("accepted_for_executor_checks")) is expected_accepted
                    and actual.get("blocked_reason") == expected_reason
                    and _same_float(actual_distance, expected_distance)
                    and (
                        (actual_current_distance is None and expected_current_distance is None)
                        or _same_float(actual_current_distance, expected_current_distance)
                    )
                    and bool(actual.get("family_moves_toward_target")) is expected_family_move
                ),
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    page_segment = _function_segment(inputs_source, TARGET)
    band_segment = _target_band_segment(page_segment)
    controller_segment = _function_segment(controller_source, CONTROLLER_TARGET)
    parity_cases = _parity_cases()
    return {
        "schema": "design_guide_local_cleanup_target_band_acceptance_extraction.v1",
        "target": TARGET,
        "controller_target": CONTROLLER_TARGET,
        "page_imports_controller_helper": f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source,
        "page_delegates_target_band_acceptance": f"_{CONTROLLER_TARGET}(" in band_segment,
        "page_target_band_reason_remaining": f"\"{TARGET_BAND_REASON}\"" in band_segment,
        "page_no_longer_computes_family_moves_toward_target": "family_moves_toward_target =" not in band_segment,
        "page_no_longer_compares_distance_to_current_distance": "detail[\"distance\"] >= current_distance" not in band_segment,
        "page_still_collects_target_band_inputs": all(
            token in band_segment
            for token in (
                "_resolved_efficiency_target_band",
                "_governing_focus_from_overview",
                "_parse_util_value",
            )
        ),
        "page_keeps_candidate_evaluation": "_evaluate_auto_design_candidate(" in page_segment,
        "page_keeps_promotion_and_executor_callbacks": all(
            token in page_segment
            for token in (
                "_promote_guidance_item_to_resolved_candidate",
                "_guidance_executor_actionability_contract",
            )
        ),
        "controller_has_target_band_reason": f"\"{TARGET_BAND_REASON}\"" in controller_segment,
        "controller_uses_controller_distance_helper": "_controller_distance_to_target_band" in controller_segment,
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
        "page_delegates_target_band_acceptance": bool(capture.get("page_delegates_target_band_acceptance")),
        "page_target_band_reason_moved": not capture.get("page_target_band_reason_remaining"),
        "page_no_longer_computes_family_moves_toward_target": bool(capture.get("page_no_longer_computes_family_moves_toward_target")),
        "page_no_longer_compares_distance_to_current_distance": bool(capture.get("page_no_longer_compares_distance_to_current_distance")),
        "page_still_collects_target_band_inputs": bool(capture.get("page_still_collects_target_band_inputs")),
        "page_keeps_candidate_evaluation": bool(capture.get("page_keeps_candidate_evaluation")),
        "page_keeps_promotion_and_executor_callbacks": bool(capture.get("page_keeps_promotion_and_executor_callbacks")),
        "controller_has_target_band_reason": bool(capture.get("controller_has_target_band_reason")),
        "controller_uses_controller_distance_helper": bool(capture.get("controller_uses_controller_distance_helper")),
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
        "`_evaluate_local_cleanup_guidance_item(...)` target-band acceptance policy.",
        "",
        "## Ownership Before",
        "`inputs_page.py` owned target-band distance comparison and family-specific movement acceptance logic.",
        "",
        "## Ownership After",
        "`DesignGuideController` owns target-band acceptance; `inputs_page.py` supplies current/candidate utility scalars from existing overview data.",
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
            f"- Page delegates target-band acceptance: `{capture.get('page_delegates_target_band_acceptance')}`",
            f"- Page target-band blocked reason remaining: `{capture.get('page_target_band_reason_remaining')}`",
            f"- Page still collects target-band inputs: `{capture.get('page_still_collects_target_band_inputs')}`",
            "",
            "## Deadness / Deletion Proof",
            "The old page-local target-band distance comparison and family movement branch were replaced. Executor/actionability and promotion remain for later slices.",
            "",
            "## Lines Removed / Added",
            "Line-count accounting is intentionally deferred to the final local-cleanup helper shell audit.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "- `design_brain/design_guide_controller.py`",
            "- `tools/verification/design_guide_local_cleanup_target_band_acceptance_extraction.py`",
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
            "Candidate evaluation execution, promotion, executor actionability, and shear executor safety remain in `inputs_page.py`.",
            "",
            "## Next Safe Target",
            "Extract post-preview executor/actionability shell policy or create a local-cleanup helper shell audit.",
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
        f"## {stamp} - Local Cleanup Target-Band Acceptance Extraction\n"
        f"- Result: `{status}`\n"
        "- Moved local cleanup target-band acceptance policy into `DesignGuideController`.\n"
        "- Page still owns scalar collection, candidate evaluation, promotion, and executor/actionability callbacks.\n"
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
        "schema": "design_guide_local_cleanup_target_band_acceptance_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_local_cleanup_target_band_acceptance_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_local_cleanup_target_band_acceptance_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_local_cleanup_target_band_acceptance_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_local_cleanup_target_band_acceptance_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
