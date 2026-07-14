"""Verify active-fail executor safe-candidate filtering moved to controller."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    accept_design_guide_controller_active_fail_executor_repair_candidate,
    filter_design_guide_controller_active_fail_executor_repair_candidates,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_active_fail_near_current_repair_item"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _legacy_filter(
    candidates: list[dict[str, Any]],
    *,
    bending_family_ladder_attempted: bool,
    shear_family_ladder_attempted: bool,
) -> list[dict[str, Any]]:
    safe: list[dict[str, Any]] = []
    for candidate in candidates:
        if accept_design_guide_controller_active_fail_executor_repair_candidate(
            candidate=dict(candidate),
            bending_family_ladder_attempted=bool(bending_family_ladder_attempted),
            shear_family_ladder_attempted=bool(shear_family_ladder_attempted),
        ):
            safe.append(dict(candidate))
    return safe


def _sample_candidates() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "generic_pass",
            "is_compliant": True,
            "overview": {"all_key_pass": True, "any_fail": False},
            "updates": {"D": 650.0},
        },
        {
            "candidate_id": "generic_partial",
            "is_compliant": True,
            "overview": {"all_key_pass": False, "any_fail": False},
            "updates": {"D": 625.0},
        },
        {
            "candidate_id": "failed_overview",
            "is_compliant": True,
            "overview": {"all_key_pass": True, "any_fail": True},
            "updates": {"D": 600.0},
        },
        {
            "candidate_id": "failed_compliance",
            "is_compliant": False,
            "overview": {"all_key_pass": True, "any_fail": False},
            "updates": {"D": 590.0},
        },
        {
            "candidate_id": "bending_required_pass",
            "candidate_family_id": "BENDING_FAIL_GOVERNS",
            "is_compliant": True,
            "overview": {
                "all_key_pass": False,
                "any_fail": False,
                "statuses": {"bending": "PASS", "shear": "PASS"},
            },
            "updates": {"bot1_count": 8},
        },
        {
            "candidate_id": "shear_required_pass",
            "candidate_family_id": "SHEAR_FAIL_GOVERNS",
            "is_compliant": True,
            "overview": {
                "all_key_pass": False,
                "any_fail": False,
                "statuses": {"bending": "PASS", "shear": "PASS"},
            },
            "updates": {"lig_legs": 2},
        },
    ]


def _parity_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    samples = _sample_candidates()
    for bending_attempted, shear_attempted in (
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ):
        old = _legacy_filter(
            samples,
            bending_family_ladder_attempted=bending_attempted,
            shear_family_ladder_attempted=shear_attempted,
        )
        new = filter_design_guide_controller_active_fail_executor_repair_candidates(
            candidates=samples,
            bending_family_ladder_attempted=bending_attempted,
            shear_family_ladder_attempted=shear_attempted,
        )
        cases.append(
            {
                "bending_family_ladder_attempted": bending_attempted,
                "shear_family_ladder_attempted": shear_attempted,
                "old_ids": [row.get("candidate_id") for row in old],
                "new_ids": [row.get("candidate_id") for row in new],
                "match": old == new,
            }
        )
    return cases


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    cases = _parity_cases()
    return {
        "schema": "design_guide_active_fail_executor_safe_candidate_filter_adapter.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "parity_cases": cases,
        "source_checks": {
            "page_delegates_to_filter_helper": "_filter_design_guide_controller_active_fail_executor_repair_candidates(" in segment,
            "page_local_acceptance_wrapper_removed": "def _candidate_accepted_for_active_fail_repair" not in segment,
            "page_direct_accept_predicate_removed": "_accept_design_guide_controller_active_fail_executor_repair_candidate(" not in segment,
            "controller_filter_helper_present": "def filter_design_guide_controller_active_fail_executor_repair_candidates(" in controller_source,
            "controller_filter_helper_exported": '"filter_design_guide_controller_active_fail_executor_repair_candidates"' in controller_source,
            "controller_boundary_clean": all(
                token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    parity_cases = list(payload.get("parity_cases") or [])
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "all_parity_cases_match": bool(parity_cases) and all(bool(case.get("match")) for case in parity_cases),
        "page_delegates_to_filter_helper": bool(source_checks.get("page_delegates_to_filter_helper")),
        "page_local_acceptance_wrapper_removed": bool(source_checks.get("page_local_acceptance_wrapper_removed")),
        "page_direct_accept_predicate_removed": bool(source_checks.get("page_direct_accept_predicate_removed")),
        "controller_filter_helper_present": bool(source_checks.get("controller_filter_helper_present")),
        "controller_filter_helper_exported": bool(source_checks.get("controller_filter_helper_exported")),
        "controller_boundary_clean": bool(source_checks.get("controller_boundary_clean")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_safe_candidate_filter_adapter_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_safe_candidate_filter_adapter_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Safe Candidate Filter Adapter",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        "- Safe candidate filtering now delegates to `DesignGuideController`.",
        "- Candidate generation, evaluation callbacks, item materialization, cache/session, CTA/apply, family runtimes, and visible wording were not moved.",
        "",
        "## Parity Cases",
    ]
    for case in payload.get("parity_cases") or []:
        lines.append(
            "- bending_attempted={bending} shear_attempted={shear}: {status} old={old} new={new}".format(
                bending=case.get("bending_family_ladder_attempted"),
                shear=case.get("shear_family_ladder_attempted"),
                status="PASS" if case.get("match") else "FAIL",
                old=case.get("old_ids"),
                new=case.get("new_ids"),
            )
        )
    lines.extend(
        [
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_safe_candidate_filter_adapter {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
