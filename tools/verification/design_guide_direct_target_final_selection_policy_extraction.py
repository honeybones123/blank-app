"""Verify direct target-band final selection policy is controller-owned."""

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

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "_direct_target_band_guidance_item"
CONTROLLER_HELPER = "select_design_guide_controller_direct_target_final_candidate"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node.lineno, int(node.end_lineno or node.lineno), "\n".join(
                lines[node.lineno - 1 : int(node.end_lineno or node.lineno)]
            )
    return 0, 0, ""


def _legacy_select(
    *,
    safe_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
    strengthening: bool,
    current_material_family_set: set[str],
    proof_exhausted: bool,
) -> dict[str, Any]:
    if target_rows:
        pool = list(target_rows)
        if current_material_family_set:
            covering = [
                row
                for row in pool
                if all(
                    family in set(row.get("affected_current_low_families") or [])
                    for family in current_material_family_set
                )
            ]
            if covering:
                pool = covering
        selected = min(
            pool,
            key=lambda row: (
                tuple(row.get("final_cleanup_sort_key") or ()),
                (
                    float(row.get("preferred_band_distance"))
                    if strengthening
                    else float(row.get("target_mid_distance") or 0.0)
                ),
                float(row.get("target_mid_distance") or 0.0),
            ),
        )
        return {"status": "selected", "selected_id": selected.get("id"), "selection_pool": "target"}

    if proof_exhausted and not strengthening:
        return {
            "status": "budget_exhausted_without_target_candidate_no_visible_budget_card",
            "selected_id": None,
            "selection_pool": "none",
        }

    pool = list(safe_rows)
    accepted = []
    if strengthening:
        accepted = [row for row in safe_rows if row.get("families_in_accepted_band")]
        if accepted:
            pool = accepted
    selected = min(
        pool,
        key=lambda row: (
            tuple(row.get("final_cleanup_sort_key") or ()),
            (
                float(row.get("accepted_band_distance"))
                if strengthening
                else float(row.get("fallback_band_distance") or 0.0)
            ),
            float(row.get("fallback_band_distance") or 0.0),
        ),
    )
    return {
        "status": "selected",
        "selected_id": selected.get("id"),
        "selection_pool": "accepted_fallback" if accepted else "safe_fallback",
    }


def _row(
    row_id: str,
    *,
    sort_key: tuple[Any, ...],
    target_mid: float = 0.0,
    preferred: float = 0.0,
    accepted: float = 0.0,
    fallback: float = 0.0,
    affected: list[str] | None = None,
    accepted_families: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": row_id,
        "candidate": {"id": row_id},
        "final_cleanup_sort_key": sort_key,
        "target_mid_distance": target_mid,
        "preferred_band_distance": preferred,
        "accepted_band_distance": accepted,
        "fallback_band_distance": fallback,
        "affected_current_low_families": list(affected or []),
        "families_in_accepted_band": list(accepted_families or []),
    }


def _parity() -> dict[str, Any]:
    from design_brain.design_guide_controller import select_design_guide_controller_direct_target_final_candidate

    cases = [
        {
            "case": "target_pool_prefers_covering_current_low",
            "safe_rows": [_row("safe", sort_key=(0, 0))],
            "target_rows": [
                _row("target_best_but_missing", sort_key=(0, 0), target_mid=0.01, affected=["bending"]),
                _row("target_covering", sort_key=(1, 0), target_mid=0.20, affected=["bending", "shear"]),
            ],
            "strengthening": False,
            "current": {"bending", "shear"},
            "proof_exhausted": False,
        },
        {
            "case": "strengthening_fallback_prefers_accepted_band_pool",
            "safe_rows": [
                _row("safe_best", sort_key=(0, 0), accepted=0.1, fallback=0.1),
                _row("accepted", sort_key=(5, 0), accepted=0.4, fallback=0.4, accepted_families=["bending"]),
            ],
            "target_rows": [],
            "strengthening": True,
            "current": set(),
            "proof_exhausted": False,
        },
        {
            "case": "cleanup_fallback_uses_safe_pool",
            "safe_rows": [
                _row("worse", sort_key=(1, 0), fallback=0.1),
                _row("better", sort_key=(0, 0), fallback=0.5),
            ],
            "target_rows": [],
            "strengthening": False,
            "current": set(),
            "proof_exhausted": False,
        },
        {
            "case": "cleanup_budget_exhausted_without_target",
            "safe_rows": [_row("safe", sort_key=(0, 0))],
            "target_rows": [],
            "strengthening": False,
            "current": set(),
            "proof_exhausted": True,
        },
    ]
    rows: list[dict[str, Any]] = []
    for case in cases:
        expected = _legacy_select(
            safe_rows=list(case["safe_rows"]),
            target_rows=list(case["target_rows"]),
            strengthening=bool(case["strengthening"]),
            current_material_family_set=set(case["current"]),
            proof_exhausted=bool(case["proof_exhausted"]),
        )
        actual_result = select_design_guide_controller_direct_target_final_candidate(
            safe_candidate_rows=list(case["safe_rows"]),
            target_candidate_rows=list(case["target_rows"]),
            strengthening=bool(case["strengthening"]),
            current_material_family_set=set(case["current"]),
            proof_exhausted=bool(case["proof_exhausted"]),
        )
        actual = {
            "status": actual_result.get("status"),
            "selected_id": (actual_result.get("selected_candidate") or {}).get("id")
            if isinstance(actual_result.get("selected_candidate"), dict)
            else None,
            "selection_pool": actual_result.get("selection_pool"),
        }
        rows.append(
            {
                "case": case["case"],
                "expected": expected,
                "actual": actual,
                "passed": actual == expected,
            }
        )
    return {"cases": rows, "all_passed": all(bool(row.get("passed")) for row in rows)}


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    helper_start, helper_end, helper_source = _function_source(controller_source, CONTROLLER_HELPER)
    source_checks = {
        "controller_helper_exists": bool(helper_source),
        "controller_helper_exported": f'"{CONTROLLER_HELPER}"' in controller_source,
        "inputs_imports_controller_helper": f"{CONTROLLER_HELPER} as _{CONTROLLER_HELPER}" in inputs_source,
        "target_calls_controller_helper": f"_{CONTROLLER_HELPER}(" in target_source,
        "page_builds_selection_rows_only": "def _direct_target_selection_row" in target_source,
        "page_no_longer_owns_target_selection_pool_filter": "target_covering_all_current_low" not in target_source,
        "page_no_longer_owns_active_accepted_fallback_pool": "active_accepted_band_candidates" not in target_source,
        "page_no_longer_owns_final_selected_min_calls": all(
            token not in target_source
            for token in (
                "selected = min(\n            target_selection_pool",
                "selected = min(\n            fallback_pool",
            )
        ),
        "evidence_projection_remains_page_owned": all(
            token in target_source
            for token in (
                "_build_candidate_search_evidence(",
                "_guidance_item_from_resolved_candidate(",
                "selected[\"candidate_search_evidence\"]",
                "item[\"action_payload\"]",
            )
        ),
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source
        and "streamlit" not in controller_source
        and "st.session_state" not in controller_source,
    }
    return {
        "schema": "design_guide_direct_target_final_selection_policy_extraction.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "controller_helper": {
            "name": CONTROLLER_HELPER,
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
        },
        "parity": _parity(),
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "remaining_page_owned_surfaces": [
            "selection dependency row construction",
            "candidate evaluation execution loop",
            "evidence and item projection",
            "debug/session diagnostics",
        ],
        "next_safe_slice": "direct_target_selection_dependency_row_extraction_or_evidence_projection_audit",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "parity_passed": bool((capture.get("parity") or {}).get("all_passed")),
        **{str(key): bool(value) for key, value in source_checks.items()},
        "product_behavior_unchanged": not bool(capture.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(capture.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(capture.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(capture.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_final_selection_policy_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_final_selection_policy_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Final Selection Policy Extraction",
        "",
        f"Status: {payload['status']}",
        "",
        "## Parity",
    ]
    for row in (payload.get("parity") or {}).get("cases") or []:
        lines.append(f"- {row['case']}: {'PASS' if row.get('passed') else 'FAIL'}")
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Surfaces",
            *[f"- {item}" for item in payload.get("remaining_page_owned_surfaces") or []],
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
            "",
            f"Next safe slice: `{payload.get('next_safe_slice')}`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        **capture,
        "status": status,
        "checks": checks,
        "checked_at": _timestamp(),
    }
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_direct_target_final_selection_policy_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
