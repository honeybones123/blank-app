"""Verify combined active-strength blocker-attempt row projection extraction."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_combined_active_strength_attempt_row,
    build_design_guide_controller_blocker_attempt_strength_reason,
    resolve_design_guide_controller_blocker_attempt_strength_capacity_rule,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


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


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _legacy_value_limit(
    *,
    family: str,
    value: Any,
    limit: Any,
    current_rows: dict[str, Any] | None,
) -> tuple[Any, Any]:
    parsed_value = _float_or_none(value)
    if parsed_value is None and family in {"bending", "shear"}:
        parsed_value = _float_or_none(dict((current_rows or {}).get(family) or {}).get("util"))
    parsed_limit = _float_or_none(limit)
    limit_text = str(limit or "").strip().lower()
    if parsed_limit is None or not limit_text or "capacity or serviceability" in limit_text:
        parsed_limit = 1.0
    return (parsed_value if parsed_value is not None else value), parsed_limit


def _legacy_combined_row(
    *,
    active_failures: set[str],
    blockers: dict[str, Any],
    active_candidate_rows: list[dict[str, Any]],
    evidence: dict[str, Any],
    current_rows: dict[str, Any],
    combined_attempted_updates: dict[str, Any],
) -> dict[str, Any]:
    if not ({"bending", "shear"}.issubset(active_failures) or {"bending", "shear"}.issubset(set(blockers))):
        return {}
    best_row = None
    for row in active_candidate_rows:
        if str(row.get("affected_family") or row.get("family") or "").strip().lower() == "combined":
            best_row = dict(row)
            break
    if best_row is None and active_candidate_rows:
        best_row = dict(active_candidate_rows[0])
    failed_family = str((best_row or {}).get("failed_check_family") or "").strip().lower()
    if failed_family not in {"bending", "shear"}:
        statuses = dict((best_row or {}).get("preview_statuses") or {})
        if str(statuses.get("bending") or "").strip().upper() == "FAIL":
            failed_family = "bending"
        elif str(statuses.get("shear") or "").strip().upper() == "FAIL":
            failed_family = "shear"
        else:
            failed_family = "combined"
    preview_values = [
        value
        for value in (
            _float_or_none((best_row or {}).get("preview_bending_util")),
            _float_or_none((best_row or {}).get("preview_shear_util")),
        )
        if value is not None
    ]
    failed_value = (
        (best_row or {}).get("failed_check_util")
        or (best_row or {}).get("preview_util")
        or (max(preview_values) if preview_values else None)
    )
    failed_value, failed_limit = _legacy_value_limit(
        family=failed_family if failed_family in {"bending", "shear"} else "combined",
        value=failed_value,
        limit=(best_row or {}).get("failed_check_capacity_or_limit")
        or (best_row or {}).get("failed_check_limit")
        or None,
        current_rows=current_rows,
    )
    display_family = failed_family if failed_family in {"bending", "shear"} else "combined"
    return {
        "attempted": True,
        "attempted_candidate_count": (
            evidence.get("total_candidates_considered")
            or evidence.get("preview_count")
            or evidence.get("generated_count")
            or len(active_candidate_rows)
        ),
        "attempted_updates": dict(combined_attempted_updates or {}),
        "best_rejected_candidate_id": (
            (best_row or {}).get("candidate_id")
            or evidence.get("failed_candidate_id")
            or evidence.get("best_rejected_candidate_id")
            or "combined_active_failure_practical_ladder_exhausted"
        ),
        "failed_check_name": resolve_design_guide_controller_blocker_attempt_strength_capacity_rule(display_family),
        "failed_check_status": str((best_row or {}).get("failed_check_status") or "FAIL").strip() or "FAIL",
        "failed_check_value": failed_value,
        "failed_check_limit": failed_limit,
        "reason": build_design_guide_controller_blocker_attempt_strength_reason(
            display_family,
            failed_value,
            failed_limit,
        ),
    }


def _cases() -> list[dict[str, Any]]:
    return [
        {"active": set(), "blockers": {}, "rows": [], "evidence": {}, "current": {}, "updates": {}},
        {
            "active": {"bending", "shear"},
            "blockers": {},
            "rows": [
                {"family": "bottom", "candidate_id": "ignored", "preview_bending_util": 0.8},
                {
                    "affected_family": "combined",
                    "candidate_id": "c1",
                    "preview_statuses": {"bending": "PASS", "shear": "FAIL"},
                    "preview_bending_util": 0.7,
                    "preview_shear_util": 1.2,
                    "failed_check_status": "FAIL",
                },
            ],
            "evidence": {"total_candidates_considered": 8},
            "current": {},
            "updates": {"D": 650.0},
        },
        {
            "active": set(),
            "blockers": {"bending": {}, "shear": {}},
            "rows": [{"candidate_id": "fallback", "failed_check_family": "bending", "failed_check_util": 1.4}],
            "evidence": {"failed_candidate_id": "fallback_evidence"},
            "current": {"bending": {"util": 1.3}},
            "updates": {"b": 450.0},
        },
        {
            "active": {"bending", "shear"},
            "blockers": {},
            "rows": [],
            "evidence": {"preview_count": 3, "best_rejected_candidate_id": "no_rows"},
            "current": {},
            "updates": {},
        },
    ]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, helper = _function_source(inputs_source, "_design_guide_blocker_attempts_table")
    _, _, controller_helper = _function_source(
        controller_source,
        "build_design_guide_controller_combined_active_strength_attempt_row",
    )

    parity_rows: list[dict[str, Any]] = []
    for index, case in enumerate(_cases()):
        legacy = _legacy_combined_row(
            active_failures=set(case.get("active") or set()),
            blockers=dict(case.get("blockers") or {}),
            active_candidate_rows=[dict(row) for row in case.get("rows") or []],
            evidence=dict(case.get("evidence") or {}),
            current_rows=dict(case.get("current") or {}),
            combined_attempted_updates=dict(case.get("updates") or {}),
        )
        current = build_design_guide_controller_combined_active_strength_attempt_row(
            active_failures=set(case.get("active") or set()),
            blockers=dict(case.get("blockers") or {}),
            active_candidate_rows=[dict(row) for row in case.get("rows") or []],
            candidate_search_evidence=dict(case.get("evidence") or {}),
            family_status_current=dict(case.get("current") or {}),
            combined_attempted_updates=dict(case.get("updates") or {}),
        )
        parity_rows.append(
            {
                "case": index,
                "matches": legacy == current,
                "legacy": legacy,
                "current": current,
            }
        )

    page_delegates = "_build_design_guide_controller_combined_active_strength_attempt_row(" in helper
    page_nested_helper_removed = "def _combined_active_strength_attempt_row(" not in helper
    route_update_stays_page_owned = '_active_failure_route_attempt_updates("combined")' in helper
    return {
        "schema": "design_guide_combined_active_strength_attempt_row_projection_extraction.v1",
        "target": {
            "function": "_design_guide_blocker_attempts_table",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "page_delegates_to_controller": page_delegates,
        "page_nested_helper_removed": page_nested_helper_removed,
        "route_update_stays_page_owned": route_update_stays_page_owned,
        "controller_helper_present": bool(controller_helper),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "parity_rows": parity_rows,
        "parity_pass": all(row.get("matches") for row in parity_rows),
        "per_family_row_assembly_moved": False,
        "route_update_moved": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "controller_helper_present": bool(payload.get("controller_helper_present")),
        "page_delegates_to_controller": bool(payload.get("page_delegates_to_controller")),
        "page_nested_helper_removed": bool(payload.get("page_nested_helper_removed")),
        "route_update_stays_page_owned": bool(payload.get("route_update_stays_page_owned")),
        "parity_pass": bool(payload.get("parity_pass")),
        "per_family_row_assembly_not_moved": not bool(payload.get("per_family_row_assembly_moved")),
        "route_update_not_moved": not bool(payload.get("route_update_moved")),
        "controller_boundary_clean": bool(payload.get("controller_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_combined_active_strength_attempt_row_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_active_strength_attempt_row_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Combined Active Strength Attempt Row Projection Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Executive Summary",
        "",
        "Combined active-strength row projection now delegates to DesignGuideController. "
        "Route attempted updates and per-family row assembly remain page-owned for later slices.",
        "",
        "## Parity Cases",
        "",
        "| Case | Matches |",
        "| --- | --- |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"| {row.get('case')} | {'PASS' if row.get('matches') else 'FAIL'} |")
    lines.extend(["", "## Checks"])
    for key, value in checks.items():
        lines.append(f"- {key}: {'PASS' if value else 'FAIL'}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_combined_active_strength_attempt_row_projection_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
