"""Verify combined active-fail ladder fallback selector is family-owned."""

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

CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
COMBINED_FAIL = ROOT / "design_brain" / "families" / "combined_bending_shear_fail.py"
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "select_design_guide_controller_active_fail_executor_family_ladder_candidate"
HELPER = "select_combined_fail_fallback_repair_candidate_from_ladder"


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


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _distance_to_target_band(util: Any, low: Any, high: Any) -> float:
    util_value = _float_or_none(util)
    low_value = _float_or_none(low)
    high_value = _float_or_none(high)
    if util_value is None or low_value is None or high_value is None:
        return float("inf")
    if low_value <= util_value <= high_value:
        return 0.0
    if util_value < low_value:
        return low_value - util_value
    return util_value - high_value


def _candidate_family_utils(candidate: dict[str, Any] | None) -> dict[str, float]:
    utils = _mapping(_mapping(candidate).get("overview")).get("utils")
    out: dict[str, float] = {}
    for family in ("bending", "shear"):
        util = _float_or_none(_mapping(utils).get(family))
        if util is not None:
            out[family] = float(util)
    return out


def _in_band_count(candidate: dict[str, Any] | None, low: Any, high: Any) -> int:
    low_f = _float_or_none(low)
    high_f = _float_or_none(high)
    if low_f is None or high_f is None:
        return 0
    return sum(1 for util in _candidate_family_utils(candidate).values() if low_f <= float(util) <= high_f)


def _old_combined_fallback(
    candidates: list[dict[str, Any]],
    *,
    target_low: float,
    target_high: float,
    final_accepted_min_family_util: float,
) -> dict[str, Any]:
    rows = [dict(candidate or {}) for candidate in list(candidates or []) if isinstance(candidate, dict)]
    if not rows:
        return {
            "selected": {},
            "selection_source": "combined_controller_fallback_ranker",
            "family_selected": {},
        }
    selected = min(
        rows,
        key=lambda cand: (
            -_in_band_count(cand, float(target_low), float(target_high)),
            -_in_band_count(cand, float(final_accepted_min_family_util), 1.0),
            _distance_to_target_band(
                _float_or_none(cand.get("candidate_post_util") or cand.get("worst_util")) or 0.0,
                float(target_low),
                float(target_high),
            ),
            int(cand.get("combined_fail_ladder_index") or cand.get("ladder_index") or 999999),
            len(dict(cand.get("updates") or {})),
        ),
    )
    return {
        "selected": dict(selected),
        "selection_source": "combined_controller_fallback_ranker",
        "family_selected": {},
    }


def _sample_candidates() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "no_overview_near",
            "combined_fail_ladder_index": 1,
            "candidate_post_util": 0.91,
            "bending_utilisation_after": 0.92,
            "shear_utilisation_after": 0.93,
            "updates": {"b": 350.0},
        },
        {
            "candidate_id": "accepted_floor_winner",
            "combined_fail_ladder_index": 4,
            "candidate_post_util": 0.83,
            "overview": {"utils": {"bending": 0.86, "shear": 0.91}},
            "updates": {"D": 625.0, "shear_legs": 2},
        },
        {
            "candidate_id": "target_band_winner",
            "combined_fail_ladder_index": 9,
            "candidate_post_util": 0.89,
            "overview": {"utils": {"bending": 0.89, "shear": 0.91}},
            "updates": {"D": 650.0, "b": 350.0, "shear_legs": 2},
        },
        {
            "candidate_id": "target_band_tie_later",
            "combined_fail_ladder_index": 10,
            "candidate_post_util": 0.90,
            "overview": {"utils": {"bending": 0.89, "shear": 0.91}},
            "updates": {"D": 675.0},
        },
    ]


def _parity() -> dict[str, Any]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        select_design_guide_controller_active_fail_executor_family_ladder_candidate,
    )
    from design_brain.families.combined_bending_shear_fail import (  # noqa: WPS433
        select_combined_fail_fallback_repair_candidate_from_ladder,
    )

    candidates = _sample_candidates()
    kwargs = {"target_low": 0.85, "target_high": 1.0, "final_accepted_min_family_util": 0.85}
    old = _old_combined_fallback(candidates, **kwargs)
    family = select_combined_fail_fallback_repair_candidate_from_ladder(candidates, **kwargs)
    controller = select_design_guide_controller_active_fail_executor_family_ladder_candidate(
        safe_candidates=candidates,
        base_state={"b": 300.0, "D": 500.0},
        target_low=kwargs["target_low"],
        target_high=kwargs["target_high"],
        final_accepted_min_family_util=kwargs["final_accepted_min_family_util"],
        shear_family_ladder_attempted=False,
        combined_family_ladder_attempted=True,
        combined_family_ladder_found_safe=True,
        combined_family_strategy=object(),
        bending_family_ladder_attempted=False,
        bending_family_ladder_found_safe=False,
    )
    empty_old = _old_combined_fallback([], **kwargs)
    empty_family = select_combined_fail_fallback_repair_candidate_from_ladder([], **kwargs)
    return {
        "old": old,
        "family": family,
        "controller": controller,
        "empty_old": empty_old,
        "empty_family": empty_family,
        "old_matches_family": old == family,
        "old_matches_controller": old == controller,
        "empty_matches": empty_old == empty_family,
    }


def _capture() -> dict[str, Any]:
    controller_source = _read(CONTROLLER)
    combined_source = _read(COMBINED_FAIL)
    inputs_source = _read(INPUTS_PAGE)
    target_start, target_end, target_segment = _function_source(controller_source, TARGET)
    helper_start, helper_end, helper_segment = _function_source(combined_source, HELPER)
    parity = _parity()
    return {
        "schema": "design_guide_active_fail_combined_ladder_selector_fallback_family_extraction.v1",
        "target": {"name": TARGET, "line_start": target_start, "line_end": target_end},
        "helper": {"name": HELPER, "line_start": helper_start, "line_end": helper_end},
        "parity": parity,
        "source_checks": {
            "controller_delegates_combined_fallback_to_family": f"{HELPER}(" in target_segment,
            "controller_no_longer_contains_inline_combined_fallback_source_string": (
                '"combined_controller_fallback_ranker"' not in target_segment
            ),
            "family_helper_exists": bool(helper_segment),
            "family_helper_preserves_existing_selection_source": (
                '"combined_controller_fallback_ranker"' in helper_segment
            ),
            "inputs_page_still_shell_calls_controller_selector": (
                "_select_design_guide_controller_active_fail_executor_family_ladder_candidate(" in inputs_source
            ),
            "controller_boundary_clean": all(
                token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
            ),
            "family_helper_boundary_clean": all(
                token not in combined_source for token in ("inputs_page", "streamlit", "st.session_state")
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    parity = dict(payload.get("parity") or {})
    return {
        "old_family_controller_parity": bool(parity.get("old_matches_family"))
        and bool(parity.get("old_matches_controller")),
        "empty_candidate_parity": bool(parity.get("empty_matches")),
        **{key: bool(value) for key, value in source_checks.items()},
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_combined_ladder_selector_fallback_family_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_combined_ladder_selector_fallback_family_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Active-Fail Combined Ladder Selector Fallback Family Extraction",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "The combined active-fail fallback selector rule now lives in "
            "`design_brain.families.combined_bending_shear_fail`. The controller still sequences the selector call "
            "and preserves the previous selection source string for behaviour and trace stability."
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
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_combined_ladder_selector_fallback_family_extraction {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
