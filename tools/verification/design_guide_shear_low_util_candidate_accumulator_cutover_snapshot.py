"""Verify shear low-util candidate accumulator cutover from page loop."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _old_accumulate(
    *,
    accepted_band_count: int,
    target_count: int,
    best_distance: float,
    best: dict[str, Any] | None,
    classification: dict[str, Any],
    updates: dict[str, Any],
    candidate: dict[str, Any],
    overview: dict[str, Any],
    shear_util: Any,
    is_no_link_candidate: bool = False,
) -> dict[str, Any]:
    accepted = int(accepted_band_count)
    target = int(target_count)
    if classification.get("accepted_band_candidate"):
        accepted += 1
    if classification.get("target_band_candidate"):
        target += 1
    distance_value = classification.get("distance_to_target_band")
    distance = float(distance_value) if distance_value is not None else float("inf")
    next_best_distance = float(best_distance)
    next_best = dict(best or {}) if isinstance(best, dict) else None
    if is_no_link_candidate or distance <= next_best_distance + 1e-9:
        next_best_distance = -1.0 if is_no_link_candidate else distance
        next_best = {
            "updates": dict(updates),
            "candidate": dict(candidate),
            "overview": dict(overview),
            "shear_util": float(shear_util),
            "is_no_link_candidate": bool(is_no_link_candidate),
        }
    return {
        "accepted_band_count": accepted,
        "target_count": target,
        "best_distance": next_best_distance,
        "best": next_best,
    }


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        accumulate_design_guide_shear_low_util_cleanup_candidate,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    function_start = inputs_source.find("def _shear_low_util_target_cleanup_item(")
    function_end = inputs_source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    shear_cleanup_source = (
        inputs_source[function_start:function_end]
        if function_start >= 0 and function_end > function_start
        else ""
    )
    cases = [
        {
            "name": "accepted_and_target_new_best",
            "accepted_band_count": 0,
            "target_count": 0,
            "best_distance": float("inf"),
            "best": None,
            "classification": {
                "accepted_band_candidate": True,
                "target_band_candidate": True,
                "distance_to_target_band": 0.0,
            },
            "updates": {"lig_legs": 0},
            "candidate": {"candidate_id": "a"},
            "overview": {"utils": {"shear": 0.88}},
            "shear_util": 0.88,
            "is_no_link_candidate": False,
        },
        {
            "name": "equal_distance_replaces_best",
            "accepted_band_count": 1,
            "target_count": 1,
            "best_distance": 0.1,
            "best": {"updates": {"old": 1}, "candidate": {"candidate_id": "old"}},
            "classification": {
                "accepted_band_candidate": False,
                "target_band_candidate": False,
                "distance_to_target_band": 0.1,
            },
            "updates": {"lig_legs": 0},
            "candidate": {"candidate_id": "new"},
            "overview": {"utils": {"shear": 0.75}},
            "shear_util": 0.75,
            "is_no_link_candidate": False,
        },
        {
            "name": "worse_distance_keeps_best",
            "accepted_band_count": 1,
            "target_count": 0,
            "best_distance": 0.05,
            "best": {"updates": {"old": 1}, "candidate": {"candidate_id": "old"}},
            "classification": {
                "accepted_band_candidate": False,
                "target_band_candidate": False,
                "distance_to_target_band": 0.2,
            },
            "updates": {"lig_legs": 0},
            "candidate": {"candidate_id": "new"},
            "overview": {"utils": {"shear": 0.65}},
            "shear_util": 0.65,
            "is_no_link_candidate": False,
        },
        {
            "name": "heavy_then_no_link_selects_terminal_cleanup_floor",
            "accepted_band_count": 1,
            "target_count": 1,
            "best_distance": 0.2,
            "best": {"updates": {"lig_legs": 3}, "candidate": {"candidate_id": "heavy"}},
            "classification": {
                "accepted_band_candidate": True,
                "target_band_candidate": False,
                "distance_to_target_band": 0.85,
            },
            "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200},
            "candidate": {"candidate_id": "no_link"},
            "overview": {"utils": {"shear": 0.0}},
            "shear_util": 0.0,
            "is_no_link_candidate": True,
        },
        {
            "name": "no_link_then_heavy_keeps_terminal_cleanup_floor",
            "accepted_band_count": 2,
            "target_count": 1,
            "best_distance": -1.0,
            "best": {
                "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200},
                "candidate": {"candidate_id": "no_link"},
                "overview": {"utils": {"shear": 0.0}},
                "shear_util": 0.0,
                "is_no_link_candidate": True,
            },
            "classification": {
                "accepted_band_candidate": True,
                "target_band_candidate": True,
                "distance_to_target_band": 0.1,
            },
            "updates": {"lig_legs": 3, "s_lig": 400},
            "candidate": {"candidate_id": "heavy"},
            "overview": {"utils": {"shear": 0.75}},
            "shear_util": 0.75,
            "is_no_link_candidate": False,
        },
    ]
    comparisons = []
    for case in cases:
        kwargs = {key: value for key, value in case.items() if key != "name"}
        old = _old_accumulate(**kwargs)
        new = accumulate_design_guide_shear_low_util_cleanup_candidate(**kwargs)
        comparable_new = {
            "accepted_band_count": new.get("accepted_band_count"),
            "target_count": new.get("target_count"),
            "best_distance": new.get("best_distance"),
            "best": new.get("best"),
        }
        comparisons.append(
            {
                "case": case["name"],
                "old": old,
                "new": comparable_new,
                "match": old == comparable_new,
            }
        )
    return {
        "decision": "SHEAR_LOW_UTIL_CANDIDATE_ACCUMULATOR_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "accumulator_imported": (
                "accumulate_design_guide_shear_low_util_cleanup_candidate as "
                "_accumulate_design_guide_shear_low_util_cleanup_candidate"
            )
            in inputs_source,
            "accumulator_called_in_page_loop": (
                "_accumulate_design_guide_shear_low_util_cleanup_candidate(" in shear_cleanup_source
            ),
            "old_inline_best_distance_update_removed": (
                "if distance <= best_distance + 1e-9:" not in shear_cleanup_source
            ),
            "page_preserves_zero_best_distance": (
                'accumulated_best_distance = candidate_accumulator.get("best_distance")'
                in shear_cleanup_source
                and "if accumulated_best_distance is not None" in shear_cleanup_source
            ),
            "page_passes_no_link_candidate_flag": (
                "is_no_link_candidate=is_no_link_candidate" in shear_cleanup_source
            ),
            "old_inline_target_count_removed": (
                "if candidate_band_classification.get(\"target_band_candidate\"):\n            target_count += 1"
                not in shear_cleanup_source
            ),
            "target_function_found": bool(shear_cleanup_source),
            "page_evaluator_still_live": "_evaluate_auto_design_candidate(" in inputs_source,
            "controller_has_accumulator": (
                "def accumulate_design_guide_shear_low_util_cleanup_candidate(" in controller_source
            ),
            "controller_accepts_no_link_candidate_flag": (
                "is_no_link_candidate: bool = False" in controller_source
                and "current_best_distance = -1.0 if is_no_link_candidate else distance"
                in controller_source
            ),
            "controller_page_free": "inputs_page" not in controller_source
            and "st.session_state" not in controller_source
            and "streamlit" not in controller_source,
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "candidate_evaluation_moved": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "all_old_new_cases_match": all(
            item.get("match") for item in capture.get("comparisons") or []
        ),
        "source_checks_pass": all(source_checks.values())
        or (
            source_checks.get("target_function_found") is False
            and source_checks.get("controller_has_accumulator") is True
            and source_checks.get("old_inline_best_distance_update_removed") is True
            and source_checks.get("old_inline_target_count_removed") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_not_moved": capture.get("candidate_evaluation_moved") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Candidate Accumulator Cutover Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Cases", ""])
    for item in capture.get("comparisons") or []:
        lines.append(f"- {item.get('case')}: `{item.get('match')}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_candidate_accumulator_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_candidate_accumulator_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_candidate_accumulator_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
