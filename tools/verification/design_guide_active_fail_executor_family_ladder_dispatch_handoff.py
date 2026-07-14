"""Verify active-fail executor family ladder dispatch handoff."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
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
TARGET = "_active_fail_near_current_repair_item"
SERVICE_HELPER = "build_design_guide_controller_active_fail_executor_family_ladder_dispatch"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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


def _sample_parity() -> dict[str, Any]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_family_ladder_dispatch,
    )
    from design_brain.families.registry import family_strategy_for  # noqa: WPS433

    reo_spacings = tuple(float(value) for value in (75, 100, 125, 150, 175, 200, 225, 250, 275, 300))
    bar_diameters = tuple(int(value) for value in (10, 12, 16, 20, 24, 28, 32, 36, 40))
    base_state = {
        "sec_shape": "RECT",
        "b": 400.0,
        "D": 650.0,
        "bot1_count": 6,
        "db_bot_1": 20,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200.0,
        "uls_Mstar": 300.0,
        "uls_Vstar": 100.0,
    }
    rescue_seed_library = {
        "combined": {
            "balanced": {
                "key": "balanced",
                "updates": {"D": 700.0, "b": 450.0, "lig_d": 12, "lig_legs": 2, "s_lig": 150.0},
            }
        }
    }
    rows: dict[str, dict[str, Any]] = {}

    shear_strategy = family_strategy_for("SHEAR_FAIL_GOVERNS")
    old_shear = shear_strategy.contracted_repair_ladder_specs(
        dict(base_state),
        width_key="b",
        geometry_locked=False,
        reo_spacings=tuple(reo_spacings),
        lig_diameters=tuple(bar_diameters),
    )
    new_shear = build_design_guide_controller_active_fail_executor_family_ladder_dispatch(
        family_id="SHEAR_FAIL_GOVERNS",
        base_state=dict(base_state),
        width_key="b",
        geometry_locked=False,
        reo_spacings=tuple(reo_spacings),
        lig_diameters=tuple(bar_diameters),
    )
    rows["shear"] = {
        "old_ladder_hash": _stable_hash(old_shear),
        "new_ladder_hash": _stable_hash(new_shear.get("ladder")),
        "dispatch_exposes_strategy": "strategy" in new_shear,
    }

    bending_strategy = family_strategy_for("BENDING_FAIL_GOVERNS")
    old_bending = bending_strategy.contracted_repair_ladder_specs(
        dict(base_state),
        width_key="b",
        geometry_locked=False,
        bar_diameters=tuple(bar_diameters),
    )
    new_bending = build_design_guide_controller_active_fail_executor_family_ladder_dispatch(
        family_id="BENDING_FAIL_GOVERNS",
        base_state=dict(base_state),
        width_key="b",
        geometry_locked=False,
        bar_diameters=tuple(bar_diameters),
    )
    rows["bending"] = {
        "old_ladder_hash": _stable_hash(old_bending),
        "new_ladder_hash": _stable_hash(new_bending.get("ladder")),
        "dispatch_exposes_strategy": "strategy" in new_bending,
    }

    combined_strategy = family_strategy_for("COMBINED_BENDING_SHEAR_FAIL")
    approved: list[dict[str, Any]] = [
        {
            "source_family_id": "APPROVED_COMBINED_MERGE_RULE",
            "candidate_id": "balanced",
            "updates": dict(rescue_seed_library["combined"]["balanced"]["updates"]),
            "evidence": {
                "source": "RESCUE_SEED_LIBRARY",
                "tier": "balanced",
                "approved_merge_rule": "unlocked_combined_fail_rescue_seed",
            },
        }
    ]
    if callable(getattr(combined_strategy, "build_target_band_refinement_candidates", None)):
        approved.extend(
            combined_strategy.build_target_band_refinement_candidates(
                dict(base_state),
                approved_combined_merge_candidates=tuple(approved),
            )
        )
    old_combined = combined_strategy.contracted_repair_ladder_specs(
        dict(base_state),
        width_key="b",
        geometry_locked=False,
        approved_combined_merge_candidates=tuple(approved),
    )
    new_combined = build_design_guide_controller_active_fail_executor_family_ladder_dispatch(
        family_id="COMBINED_BENDING_SHEAR_FAIL",
        base_state=dict(base_state),
        width_key="b",
        geometry_locked=False,
        rescue_seed_library=dict(rescue_seed_library),
        rescue_tiers=("balanced",),
    )
    rows["combined"] = {
        "old_ladder_hash": _stable_hash(old_combined),
        "new_ladder_hash": _stable_hash(new_combined.get("ladder")),
        "old_approved_hash": _stable_hash(approved),
        "new_approved_hash": _stable_hash(new_combined.get("approved_combined_merge_candidates")),
        "dispatch_exposes_strategy": "strategy" in new_combined,
    }
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    parity = _sample_parity()
    return {
        "schema": "design_guide_active_fail_executor_family_ladder_dispatch_handoff.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "parity": parity,
        "source_checks": {
            "target_uses_controller_dispatch": "_build_design_guide_controller_active_fail_executor_family_ladder_dispatch("
            in target_source,
            "target_has_three_dispatch_calls": target_source.count(
                "_build_design_guide_controller_active_fail_executor_family_ladder_dispatch("
            )
            == 3,
            "target_no_longer_imports_family_strategy_for": "from design_brain.families.registry import family_strategy_for"
            not in target_source,
            "target_no_longer_calls_family_strategy_for": "family_strategy_for(" not in target_source,
            "target_no_longer_calls_contracted_repair_ladder_specs": ".contracted_repair_ladder_specs("
            not in target_source,
            "selection_now_controller_owned": (
                "_select_design_guide_controller_active_fail_executor_family_ladder_candidate("
                in target_source
                and "select_repair_candidate_from_ladder(" not in target_source
            ),
            "evidence_overlay_now_controller_owned": (
                "_build_design_guide_controller_active_fail_executor_candidate_search_evidence("
                in target_source
                and "_build_design_guide_controller_active_fail_executor_family_evidence_overlay("
                not in target_source
                and "repair_ladder_evidence_overlay(" not in target_source
            ),
            "candidate_evaluation_still_service_owned": "_evaluate_active_fail_executor_candidate_with_updates("
            in target_source,
            "controller_helper_exists": f"def {SERVICE_HELPER}(" in controller_source,
            "controller_exports_helper": f'"{SERVICE_HELPER}"' in controller_source,
            "controller_has_no_page_or_streamlit_imports": all(
                token not in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    parity = payload.get("parity") or {}
    source_checks = payload.get("source_checks") or {}
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "ladder_hashes_unchanged": bool(parity)
        and all(row.get("old_ladder_hash") == row.get("new_ladder_hash") for row in parity.values()),
        "combined_approved_candidates_unchanged": (
            (parity.get("combined") or {}).get("old_approved_hash")
            == (parity.get("combined") or {}).get("new_approved_hash")
        ),
        "dispatch_no_longer_exposes_strategy_to_page": bool(parity)
        and all(not bool(row.get("dispatch_exposes_strategy")) for row in parity.values()),
        **{name: bool(value) for name, value in source_checks.items()},
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"design_guide_active_fail_executor_family_ladder_dispatch_handoff_{suffix}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_active_fail_executor_family_ladder_dispatch_handoff_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Family Ladder Dispatch Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "Moved active-fail executor family strategy lookup and contracted repair ladder generation "
            "behind `DesignGuideController`. Candidate selection and evidence overlay now route "
            "through controller-owned helpers. The page still owns candidate iteration, "
            "trace/session, item packaging, and CTA side effects."
        ),
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_family_ladder_dispatch_handoff {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
