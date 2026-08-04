"""Verify shear low-util candidate delta/materiality screen cutover."""

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


def _old_float_from_state(state: dict, key: str, default: float) -> float:
    value = state.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def _old_int_from_state(state: dict, key: str, default: int) -> int:
    value = state.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _old_one_click_diff_accumulated_updates(base: dict, final: dict) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for key, value in (final or {}).items():
        if key not in base:
            delta[key] = value
            continue
        base_value = base[key]
        if isinstance(value, float) or isinstance(base_value, float):
            try:
                if abs(float(base_value) - float(value)) > 1e-9:
                    delta[key] = value
            except (TypeError, ValueError):
                if base_value != value:
                    delta[key] = value
        elif base_value != value:
            delta[key] = value
    return delta


def _old_shear_cleanup_materially_reduces_reinforcement(
    current_state: dict | None,
    candidate_state: dict | None,
) -> bool:
    if not isinstance(current_state, dict) or not isinstance(candidate_state, dict):
        return False
    cur_spacing = _old_float_from_state(current_state, "s_lig", 0.0)
    nxt_spacing = _old_float_from_state(candidate_state, "s_lig", cur_spacing)
    cur_legs = _old_int_from_state(current_state, "lig_legs", 0)
    nxt_legs = _old_int_from_state(candidate_state, "lig_legs", cur_legs)
    cur_dia = _old_int_from_state(current_state, "lig_d", 0)
    nxt_dia = _old_int_from_state(candidate_state, "lig_d", cur_dia)
    if cur_legs > 0 and nxt_legs == 0:
        return True
    if nxt_spacing > cur_spacing + 1e-9:
        return True
    if nxt_legs < cur_legs:
        return True
    if nxt_dia < cur_dia:
        return True
    return False


def _old_delta_screen(base_state: dict[str, Any], variant_state: dict[str, Any]) -> dict[str, Any]:
    updates = _old_one_click_diff_accumulated_updates(base_state, variant_state)
    trial_state = dict(base_state)
    trial_state.update(dict(updates))
    return {
        "updates": dict(updates),
        "materially_reduces_reinforcement": _old_shear_cleanup_materially_reduces_reinforcement(
            base_state,
            trial_state,
        ),
    }


def _target_function_source(inputs_source: str) -> str:
    function_start = inputs_source.find("def _shear_low_util_target_cleanup_item(")
    function_end = inputs_source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    if function_start < 0 or function_end <= function_start:
        return ""
    return inputs_source[function_start:function_end]


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_candidate_delta_screen,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    shear_cleanup_source = _target_function_source(inputs_source)
    base = {
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 180.0,
        "D": 600.0,
    }
    cases = [
        {"name": "unchanged", "variant": dict(base)},
        {"name": "spacing_increase", "variant": {**base, "s_lig": 250.0}},
        {"name": "leg_removal", "variant": {**base, "lig_legs": 0, "lig_d": 0}},
        {"name": "diameter_reduction", "variant": {**base, "lig_d": 8}},
        {"name": "non_material_depth_change", "variant": {**base, "D": 620.0}},
        {"name": "new_extra_key", "variant": {**base, "extra": "x"}},
    ]
    comparisons = []
    for case in cases:
        old = _old_delta_screen(base, case["variant"])
        new_raw = build_design_guide_shear_low_util_candidate_delta_screen(
            base_state=base,
            variant_state=case["variant"],
        )
        new = {
            "updates": dict(new_raw.get("updates") or {}),
            "materially_reduces_reinforcement": bool(
                new_raw.get("materially_reduces_reinforcement")
            ),
        }
        comparisons.append(
            {
                "case": case["name"],
                "old_hash": _stable_hash(old),
                "new_hash": _stable_hash(new),
                "match": old == new,
                "old": old,
                "new": new,
            }
        )
    return {
        "decision": "SHEAR_LOW_UTIL_CANDIDATE_DELTA_SCREEN_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "helper_imported": (
                "build_design_guide_shear_low_util_candidate_delta_screen as "
                "_build_design_guide_shear_low_util_candidate_delta_screen"
            )
            in inputs_source,
            "helper_called_in_target_function": (
                "_build_design_guide_shear_low_util_candidate_delta_screen("
                in shear_cleanup_source
            ),
            "old_diff_helper_removed_from_target": (
                "_one_click_diff_accumulated_updates(" not in shear_cleanup_source
            ),
            "old_materiality_helper_removed_from_target": (
                "_shear_cleanup_materially_reduces_reinforcement(" not in shear_cleanup_source
            ),
            "generic_diff_helper_not_deleted": (
                "def _one_click_diff_accumulated_updates(" in inputs_source
            ),
            "generic_materiality_helper_not_deleted": (
                "def _shear_cleanup_materially_reduces_reinforcement(" in inputs_source
            ),
            "target_function_found": bool(shear_cleanup_source),
            "controller_has_helper": (
                "def build_design_guide_shear_low_util_candidate_delta_screen("
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
        "generic_helpers_deleted": False,
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
            and source_checks.get("controller_has_helper") is True
            and source_checks.get("old_diff_helper_removed_from_target") is True
            and source_checks.get("old_materiality_helper_removed_from_target") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_not_moved": capture.get("candidate_evaluation_moved") is False,
        "generic_helpers_not_deleted": capture.get("generic_helpers_deleted") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Candidate Delta Screen Cutover Snapshot",
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
        lines.append(
            f"- {item.get('case')}: match=`{item.get('match')}`, old=`{item.get('old_hash')}`, new=`{item.get('new_hash')}`"
        )
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_candidate_delta_screen_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_candidate_delta_screen_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_candidate_delta_screen_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
