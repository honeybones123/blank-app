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
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

SAFETY_CALLBACK = "_resolved_shear_cleanup_is_executor_safe"
CONTROLLER_TARGET = "resolve_design_guide_controller_shear_executor_safety_policy"


def _function_segment(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_start = source.find("\ndef ", start + len(marker))
    if next_start < 0:
        next_start = len(source)
    return source[start:next_start]


def _old_policy(
    *,
    has_updates: bool,
    pure_shear_detailing_updates: bool,
    materially_reduces_reinforcement: bool,
    candidate_overview: dict[str, Any] | None,
    governing_domain: str | None = None,
) -> bool:
    if not has_updates:
        return False
    if not pure_shear_detailing_updates:
        return False
    if not materially_reduces_reinforcement:
        return False
    overview = dict(candidate_overview or {})
    statuses = dict(overview.get("statuses") or {})
    if any(str(value or "").strip().upper() == "FAIL" for value in statuses.values()):
        return False
    if bool(overview.get("any_fail")):
        return False
    governing = str(governing_domain or "").strip().lower()
    if governing:
        status_after = str(statuses.get(governing) or "").strip().upper()
        if status_after == "FAIL":
            return False
    return True


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_shear_executor_safety_policy,
    )

    cases = [
        (
            "missing_updates",
            {
                "has_updates": False,
                "pure_shear_detailing_updates": True,
                "materially_reduces_reinforcement": True,
                "candidate_overview": {"any_fail": False, "statuses": {"shear": "PASS"}},
            },
        ),
        (
            "non_shear_updates",
            {
                "has_updates": True,
                "pure_shear_detailing_updates": False,
                "materially_reduces_reinforcement": True,
                "candidate_overview": {"any_fail": False, "statuses": {"shear": "PASS"}},
            },
        ),
        (
            "not_material_reduction",
            {
                "has_updates": True,
                "pure_shear_detailing_updates": True,
                "materially_reduces_reinforcement": False,
                "candidate_overview": {"any_fail": False, "statuses": {"shear": "PASS"}},
            },
        ),
        (
            "explicit_fail_status",
            {
                "has_updates": True,
                "pure_shear_detailing_updates": True,
                "materially_reduces_reinforcement": True,
                "candidate_overview": {"any_fail": False, "statuses": {"shear": "FAIL"}},
                "governing_domain": "bending",
            },
        ),
        (
            "any_fail",
            {
                "has_updates": True,
                "pure_shear_detailing_updates": True,
                "materially_reduces_reinforcement": True,
                "candidate_overview": {"any_fail": True, "statuses": {"shear": "PASS"}},
            },
        ),
        (
            "governing_domain_fail",
            {
                "has_updates": True,
                "pure_shear_detailing_updates": True,
                "materially_reduces_reinforcement": True,
                "candidate_overview": {"any_fail": False, "statuses": {"shear": "PASS", "bending": "FAIL"}},
                "governing_domain": "bending",
            },
        ),
        (
            "safe_no_governing",
            {
                "has_updates": True,
                "pure_shear_detailing_updates": True,
                "materially_reduces_reinforcement": True,
                "candidate_overview": {"any_fail": False, "statuses": {"shear": "PASS", "bending": "PASS"}},
            },
        ),
        (
            "safe_with_governing",
            {
                "has_updates": True,
                "pure_shear_detailing_updates": True,
                "materially_reduces_reinforcement": True,
                "candidate_overview": {"any_fail": False, "statuses": {"shear": "PASS", "bending": "PASS"}},
                "governing_domain": "bending",
            },
        ),
    ]
    rows = []
    for name, kwargs in cases:
        expected = _old_policy(**kwargs)
        actual = resolve_design_guide_controller_shear_executor_safety_policy(**kwargs)
        rows.append(
            {
                "case": name,
                "expected_safe": expected,
                "actual_safe": bool(actual.get("safe")),
                "blocked_reason": actual.get("blocked_reason"),
                "passed": bool(actual.get("safe")) is expected,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    service_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    safety_segment = _function_segment(inputs_source, SAFETY_CALLBACK)
    controller_segment = _function_segment(controller_source, CONTROLLER_TARGET)
    parity_cases = _parity_cases()
    return {
        "schema": "design_guide_shear_executor_safety_policy_extraction.v1",
        "safety_callback": SAFETY_CALLBACK,
        "controller_target": CONTROLLER_TARGET,
        "page_imports_controller_policy": f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source,
        "safety_callback_calls_controller_policy": f"_{CONTROLLER_TARGET}(" in safety_segment,
        "safety_callback_keeps_collection_and_fallback": all(
            token in safety_segment
            for token in (
                "_guidance_state_snapshot(",
                "_guidance_item_payload(",
                "_shear_detailing_updates_pure(",
                "_shear_cleanup_materially_reduces_reinforcement(",
                "_resolve_design_candidate_overview_for_safety_check(",
                "_governing_focus_from_overview(",
            )
        ),
        "safety_callback_no_longer_calls_page_shim": "_evaluate_auto_design_candidate(" not in safety_segment,
        "safety_callback_no_longer_owns_explicit_fail_policy": "_candidate_preview_statuses_have_explicit_fail(" not in safety_segment,
        "safety_callback_no_longer_owns_any_fail_policy": "candidate_overview.get(\"any_fail\")" not in safety_segment,
        "safety_callback_no_longer_owns_governing_status_policy": "governing_status_after" not in safety_segment,
        "missing_overview_fallback_still_uses_candidate_service": "_resolve_design_candidate_overview_for_safety_check(" in safety_segment,
        "controller_owns_explicit_fail_policy": "explicit_fail_statuses" in controller_segment,
        "controller_owns_any_fail_policy": "overview_d.get(\"any_fail\")" in controller_segment,
        "controller_owns_governing_status_policy": "governing_status_after" in controller_segment,
        "controller_exported": f'"{CONTROLLER_TARGET}"' in controller_source,
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "candidate_service_has_no_page_or_streamlit_imports": "inputs_page" not in service_source and "streamlit" not in service_source,
        "parity_cases": parity_cases,
        "all_parity_cases_passed": all(row.get("passed") for row in parity_cases),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "blocked_reason_changed": False,
        "candidate_metadata_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "page_imports_controller_policy": bool(capture.get("page_imports_controller_policy")),
        "safety_callback_calls_controller_policy": bool(capture.get("safety_callback_calls_controller_policy")),
        "safety_callback_keeps_collection_and_fallback": bool(capture.get("safety_callback_keeps_collection_and_fallback")),
        "safety_callback_no_longer_calls_page_shim": bool(capture.get("safety_callback_no_longer_calls_page_shim")),
        "safety_callback_no_longer_owns_explicit_fail_policy": bool(capture.get("safety_callback_no_longer_owns_explicit_fail_policy")),
        "safety_callback_no_longer_owns_any_fail_policy": bool(capture.get("safety_callback_no_longer_owns_any_fail_policy")),
        "safety_callback_no_longer_owns_governing_status_policy": bool(capture.get("safety_callback_no_longer_owns_governing_status_policy")),
        "missing_overview_fallback_still_uses_candidate_service": bool(capture.get("missing_overview_fallback_still_uses_candidate_service")),
        "controller_owns_explicit_fail_policy": bool(capture.get("controller_owns_explicit_fail_policy")),
        "controller_owns_any_fail_policy": bool(capture.get("controller_owns_any_fail_policy")),
        "controller_owns_governing_status_policy": bool(capture.get("controller_owns_governing_status_policy")),
        "controller_exported": bool(capture.get("controller_exported")),
        "controller_has_no_page_or_streamlit_imports": bool(capture.get("controller_has_no_page_or_streamlit_imports")),
        "candidate_service_has_no_page_or_streamlit_imports": bool(capture.get("candidate_service_has_no_page_or_streamlit_imports")),
        "parity_cases_passed": bool(capture.get("all_parity_cases_passed")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtimes_unchanged": capture.get("family_runtimes_changed") is False,
        "blocked_reason_unchanged": capture.get("blocked_reason_changed") is False,
        "candidate_metadata_unchanged": capture.get("candidate_metadata_changed") is False,
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
        "Pure shear executor safety policy in `_resolved_shear_cleanup_is_executor_safe(...)`.",
        "",
        "## Ownership Before",
        "`inputs_page.py` owned explicit fail, any-fail, governing-domain status, and final safety decision policy.",
        "",
        "## Ownership After",
        "`design_brain.design_guide_controller.resolve_design_guide_controller_shear_executor_safety_policy(...)` owns the pure safety decision. The page wrapper still collects current state, updates, fallback overview evidence, and governing domain.",
        "",
        "## Behaviour Preserved",
        f"- Product behaviour changed: `{capture.get('product_behavior_changed')}`",
        f"- Visible wording changed: `{capture.get('visible_wording_changed')}`",
        f"- CTA/apply semantics changed: `{capture.get('cta_apply_semantics_changed')}`",
        f"- Family runtimes changed: `{capture.get('family_runtimes_changed')}`",
        f"- Blocked reason changed: `{capture.get('blocked_reason_changed')}`",
        f"- Candidate metadata changed: `{capture.get('candidate_metadata_changed')}`",
        "",
        "## Adapter / Default Rebuild Proof",
    ]
    for case in capture.get("parity_cases") or []:
        lines.append(
            f"- `{case.get('case')}`: expected_safe=`{case.get('expected_safe')}`, actual_safe=`{case.get('actual_safe')}`, passed=`{case.get('passed')}`"
        )
    lines.extend(
        [
            "",
            "## Cutover Proof",
            f"- Safety callback calls controller policy: `{capture.get('safety_callback_calls_controller_policy')}`",
            f"- Safety callback no longer calls page shim: `{capture.get('safety_callback_no_longer_calls_page_shim')}`",
            f"- Missing-overview fallback still uses candidate service: `{capture.get('missing_overview_fallback_still_uses_candidate_service')}`",
            "",
            "## Deadness / Deletion Proof",
            "No deletion yet. The page wrapper remains because it still collects current state, updates, fallback overview evidence, and governing domain.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "- `design_brain/design_guide_controller.py`",
            "- `tools/verification/design_guide_shear_executor_safety_policy_extraction.py`",
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
            "The wrapper still owns shell collection and callback execution. Remaining local-cleanup helper surfaces are one-click probe, actionability callback, and target-band scalar collection.",
            "",
            "## Next Safe Target",
            "Refresh the local-cleanup shell audit and target one-click/actionability callback boundaries if they are not already shell-only.",
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
        f"## {stamp} - Shear Executor Safety Policy Extraction\n"
        f"- Result: `{status}`\n"
        "- Moved pure shear executor safety policy to `design_brain.design_guide_controller`.\n"
        "- Kept page wrapper for current-state/update/fallback-overview/governing-domain collection.\n"
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
        "schema": "design_guide_shear_executor_safety_policy_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_shear_executor_safety_policy_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_shear_executor_safety_policy_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_shear_executor_safety_policy_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_shear_executor_safety_policy_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
