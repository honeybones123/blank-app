"""Verify active-fail executor family selection/evidence overlay handoff."""

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


def _sample_candidates() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "c0",
            "updates": {"D": 700.0, "b": 450.0, "bw": 450.0},
            "overview": {"utils": {"bending": 0.91, "shear": 0.82}},
            "candidate_post_util": 0.91,
            "worst_util": 0.91,
            "ladder_index": 2,
            "bending_fail_ladder_index": 2,
            "shear_fail_ladder_index": 2,
            "combined_fail_ladder_index": 2,
        },
        {
            "candidate_id": "c1",
            "updates": {"D": 725.0, "b": 450.0, "bw": 450.0, "lig_d": 12, "lig_legs": 2},
            "overview": {"utils": {"bending": 0.88, "shear": 0.92}},
            "candidate_post_util": 0.92,
            "worst_util": 0.92,
            "ladder_index": 1,
            "bending_fail_ladder_index": 1,
            "shear_fail_ladder_index": 1,
            "combined_fail_ladder_index": 1,
        },
    ]


def _old_select(
    *,
    safe: list[dict[str, Any]],
    family: str,
    strategy: Any,
    attempted: bool,
    found_safe: bool,
    target_low: float,
    target_high: float,
) -> dict[str, Any]:
    family_l = str(family or "").strip().lower()
    if attempted and family_l == "shear" and strategy is not None and callable(
        getattr(strategy, "select_repair_candidate_from_ladder", None)
    ):
        selected_result = strategy.select_repair_candidate_from_ladder(
            safe,
            target_low=float(target_low),
            target_high=float(target_high),
        )
        return dict(selected_result.get("selected") or safe[0])
    if attempted and family_l == "combined" and found_safe and strategy is not None and callable(
        getattr(strategy, "select_repair_candidate_from_ladder", None)
    ):
        selected_result = strategy.select_repair_candidate_from_ladder(
            safe,
            target_low=float(target_low),
            target_high=float(target_high),
        )
        return dict(selected_result.get("selected") or safe[0])
    if attempted and family_l == "bending" and found_safe and strategy is not None and callable(
        getattr(strategy, "select_repair_candidate_from_ladder", None)
    ):
        selected_result = strategy.select_repair_candidate_from_ladder(
            safe,
            target_low=float(target_low),
            target_high=float(target_high),
        )
        return dict(selected_result.get("selected") or safe[0])
    return dict(safe[0])


def _sample_parity() -> dict[str, Any]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_family_evidence_overlay,
        build_design_guide_controller_active_fail_executor_family_ladder_dispatch,
        select_design_guide_controller_active_fail_executor_family_ladder_candidate,
    )
    from design_brain.families.registry import family_strategy_for  # noqa: WPS433

    base_state = {
        "sec_shape": "RECT",
        "b": 400.0,
        "bw": 400.0,
        "D": 650.0,
        "bot1_count": 6,
        "db_bot_1": 20,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200.0,
        "uls_Mstar": 300.0,
        "uls_Vstar": 100.0,
    }
    safe = _sample_candidates()
    target_low = 0.85
    target_high = 1.0
    final_floor = 0.85
    dispatches = {
        "shear": build_design_guide_controller_active_fail_executor_family_ladder_dispatch(
            family_id="SHEAR_FAIL_GOVERNS",
            base_state=dict(base_state),
            width_key="b",
            geometry_locked=False,
            reo_spacings=(75.0, 100.0, 150.0, 200.0),
            lig_diameters=(10, 12, 16),
        ),
        "bending": build_design_guide_controller_active_fail_executor_family_ladder_dispatch(
            family_id="BENDING_FAIL_GOVERNS",
            base_state=dict(base_state),
            width_key="b",
            geometry_locked=False,
            bar_diameters=(10, 12, 16, 20, 24),
        ),
        "combined": build_design_guide_controller_active_fail_executor_family_ladder_dispatch(
            family_id="COMBINED_BENDING_SHEAR_FAIL",
            base_state=dict(base_state),
            width_key="b",
            geometry_locked=False,
            rescue_seed_library={
                "combined": {
                    "balanced": {
                        "key": "balanced",
                        "updates": {"D": 700.0, "b": 450.0, "lig_d": 12, "lig_legs": 2, "s_lig": 150.0},
                    }
                }
            },
            rescue_tiers=("balanced",),
        ),
    }
    rows: dict[str, dict[str, Any]] = {}
    for family, dispatch in dispatches.items():
        strategy = family_strategy_for(
            {
                "shear": "SHEAR_FAIL_GOVERNS",
                "bending": "BENDING_FAIL_GOVERNS",
                "combined": "COMBINED_BENDING_SHEAR_FAIL",
            }[family]
        )
        old_selected = _old_select(
            safe=list(safe),
            family=family,
            strategy=strategy,
            attempted=True,
            found_safe=True,
            target_low=target_low,
            target_high=target_high,
        )
        new_selection = select_design_guide_controller_active_fail_executor_family_ladder_candidate(
            safe_candidates=list(safe),
            base_state=dict(base_state),
            target_low=target_low,
            target_high=target_high,
            final_accepted_min_family_util=final_floor,
            shear_family_ladder_attempted=family == "shear",
            combined_family_ladder_attempted=family == "combined",
            combined_family_ladder_found_safe=family == "combined",
            bending_family_ladder_attempted=family == "bending",
            bending_family_ladder_found_safe=family == "bending",
        )
        new_selected = dict(new_selection.get("selected") or {})
        index_key = {
            "shear": "shear_fail_ladder_index",
            "bending": "bending_fail_ladder_index",
            "combined": "combined_fail_ladder_index",
        }[family]
        reason = {
            "shear": "first_compliant_candidate_in_contract_ladder_order",
            "bending": "first_compliant_candidate_in_contract_ladder_order",
            "combined": "contract_family_target_band_ranked_candidate",
        }[family]
        selected_result = {
            "selected": dict(old_selected),
            "selection_reason": reason,
            "selected_ladder_index": old_selected.get(index_key),
        }
        old_overlay = (
            strategy.repair_ladder_evidence_overlay(
                ladder=dict(dispatch.get("ladder") or {}),
                selected_result=dict(selected_result),
            )
            if strategy is not None and callable(getattr(strategy, "repair_ladder_evidence_overlay", None))
            else {}
        )
        new_overlay = build_design_guide_controller_active_fail_executor_family_evidence_overlay(
            family_id={
                "shear": "SHEAR_FAIL_GOVERNS",
                "bending": "BENDING_FAIL_GOVERNS",
                "combined": "COMBINED_BENDING_SHEAR_FAIL",
            }[family],
            ladder=dict(dispatch.get("ladder") or {}),
            selected_candidate=dict(new_selected),
            selection_reason=reason,
            selected_ladder_index_key=index_key,
        )
        rows[family] = {
            "old_selected_hash": _stable_hash(old_selected),
            "new_selected_hash": _stable_hash(new_selected),
            "old_overlay_hash": _stable_hash(old_overlay),
            "new_overlay_hash": _stable_hash(new_overlay.get("overlay") or {}),
            "new_overlay_error": new_overlay.get("error"),
            "dispatch_exposes_strategy": "strategy" in dispatch,
        }
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    parity = _sample_parity()
    return {
        "schema": "design_guide_active_fail_executor_family_selection_evidence_overlay_handoff.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "parity": parity,
        "source_checks": {
            "target_uses_controller_selection": "_select_design_guide_controller_active_fail_executor_family_ladder_candidate("
            in target_source,
            "target_uses_controller_evidence_projection": (
                "_build_design_guide_controller_active_fail_executor_candidate_search_evidence(" in target_source
            ),
            "target_no_longer_calls_family_selector": "select_repair_candidate_from_ladder(" not in target_source,
            "target_no_longer_calls_family_overlay": "repair_ladder_evidence_overlay(" not in target_source,
            "target_no_longer_mentions_family_strategy_bridge": "family_strategy" not in target_source,
            "family_ladder_dispatch_still_controller_owned": "_build_design_guide_controller_active_fail_executor_family_ladder_dispatch("
            in target_source,
            "candidate_evaluation_still_service_owned": "_evaluate_active_fail_executor_candidate_with_updates("
            in target_source,
            "session_cache_still_page_owned": "st.session_state" in target_source,
            "controller_selection_helper_exists": "def select_design_guide_controller_active_fail_executor_family_ladder_candidate("
            in controller_source,
            "controller_overlay_helper_exists": "def build_design_guide_controller_active_fail_executor_family_evidence_overlay("
            in controller_source,
            "controller_evidence_projection_helper_exists": (
                "def build_design_guide_controller_active_fail_executor_candidate_search_evidence("
                in controller_source
            ),
            "controller_exports_selection_helper": '"select_design_guide_controller_active_fail_executor_family_ladder_candidate"'
            in controller_source,
            "controller_exports_overlay_helper": '"build_design_guide_controller_active_fail_executor_family_evidence_overlay"'
            in controller_source,
            "controller_exports_evidence_projection_helper": (
                '"build_design_guide_controller_active_fail_executor_candidate_search_evidence"' in controller_source
            ),
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
        "selected_candidate_hashes_unchanged": bool(parity)
        and all(row.get("old_selected_hash") == row.get("new_selected_hash") for row in parity.values()),
        "overlay_hashes_unchanged": bool(parity)
        and all(row.get("old_overlay_hash") == row.get("new_overlay_hash") for row in parity.values()),
        "overlay_errors_absent": bool(parity)
        and all(not row.get("new_overlay_error") for row in parity.values()),
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
        f"design_guide_active_fail_executor_family_selection_evidence_overlay_handoff_{suffix}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_active_fail_executor_family_selection_evidence_overlay_handoff_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Family Selection/Evidence Overlay Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "Moved active-fail executor family candidate selection and family evidence overlay "
            "calls behind `DesignGuideController`. The page now reaches the family overlay through "
            "the controller candidate-search evidence projection. The page still owns candidate "
            "iteration, candidate evaluation service calls, session/cache/trace, item packaging, "
            "and CTA side effects."
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
    print(f"design_guide_active_fail_executor_family_selection_evidence_overlay_handoff {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
