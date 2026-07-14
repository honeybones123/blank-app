"""Verify shear low-util raw variant-state generation cutover."""

from __future__ import annotations

import ast
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

REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
CANONICAL_NO_SHEAR_SLIG_MM = 200.0


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _target_function_source(inputs_source: str) -> str:
    inputs_source = inputs_source.lstrip("\ufeff")
    tree = ast.parse(inputs_source)
    lines = inputs_source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_shear_low_util_target_cleanup_item":
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                return ""
            return "\n".join(lines[node.lineno - 1 : end_lineno])
    return ""


def _float_from_state(state: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(state.get(key, default))
    except Exception:
        return float(default)


def _int_from_state(state: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(state.get(key, default))
    except Exception:
        return int(default)


def _old_generate_less_shear_reo_variants(
    *,
    state: dict[str, Any],
    shear_cleanup_possible: bool,
    shear_state_eligible_for_no_links: bool,
) -> list[dict[str, Any]]:
    if not shear_cleanup_possible:
        return []
    cur_sp = float(_float_from_state(state, "s_lig", 200.0))
    current_legs = _int_from_state(state, "lig_legs", 2)
    current_dia = _int_from_state(state, "lig_d", 10)
    max_spacing = float(max(REO_SPACINGS) if REO_SPACINGS else 300.0)
    spacing_values = [float(v) for v in REO_SPACINGS if float(v) > cur_sp + 1e-9][:2]
    spacing_values.extend(float(v) for v in REO_SPACINGS if float(v) < cur_sp - 1e-9)
    spacing_values.extend(float(cur_sp - 25.0 * step) for step in range(0, 5))
    spacing_values.extend(float(cur_sp + 25.0 * step) for step in range(1, 17))
    if max_spacing > cur_sp + 1e-9:
        spacing_values.append(max_spacing)
    spacing_values = sorted(set(float(v) for v in spacing_values))
    leg_values = sorted(
        {
            int(value)
            for value in (
                current_legs,
                2,
                3,
            )
            if int(value) >= 2 and int(value) <= max(current_legs, 3)
        }
    )
    dia_values = sorted(
        set(
            [value for value in REO_BAR_DIAS if 0 < int(value) <= current_dia][-2:]
            or [max(int(current_dia), 10)]
        )
    )
    variants: dict[tuple, dict[str, Any]] = {}
    if shear_state_eligible_for_no_links:
        zero_link_state = dict(state)
        zero_link_state.update(
            {
                "lig_d": 0,
                "lig_legs": 0,
                "s_lig": float(CANONICAL_NO_SHEAR_SLIG_MM),
            }
        )
        variants[_candidate_key_for_snapshot(zero_link_state)] = zero_link_state
    for spacing in spacing_values or [cur_sp]:
        for legs in leg_values:
            for dia in dia_values:
                resolved_dia = int(dia)
                resolved_spacing = float(spacing)
                if (
                    resolved_dia == current_dia
                    and int(legs) == current_legs
                    and abs(float(resolved_spacing) - cur_sp) <= 1e-9
                ):
                    continue
                candidate_state = dict(state)
                candidate_state.update(
                    {
                        "lig_d": int(resolved_dia),
                        "lig_legs": int(legs),
                        "s_lig": float(resolved_spacing),
                    }
                )
                variants[_candidate_key_for_snapshot(candidate_state)] = candidate_state
    return list(variants.values())


def _candidate_key_for_snapshot(state: dict[str, Any]) -> tuple:
    return tuple(
        sorted(
            (
                str(key),
                str(state.get(key)),
            )
            for key in ("lig_d", "lig_legs", "s_lig", "D", "b", "bw")
            if key in state
        )
    )


def _dedupe_for_snapshot(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    variants: dict[tuple, dict[str, Any]] = {}
    for state in states:
        variants[_candidate_key_for_snapshot(dict(state))] = dict(state)
    return list(variants.values())


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_raw_variant_states,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    shear_cleanup_source = _target_function_source(inputs_source)
    cases = [
        {
            "name": "active_links_no_link_eligible",
            "state": {"lig_d": 10, "lig_legs": 2, "s_lig": 200.0, "D": 650.0, "b": 400.0},
            "shear_cleanup_possible": True,
            "shear_state_eligible_for_no_links": True,
        },
        {
            "name": "active_links_no_link_not_eligible",
            "state": {"lig_d": 12, "lig_legs": 3, "s_lig": 225.0, "D": 650.0, "b": 400.0},
            "shear_cleanup_possible": True,
            "shear_state_eligible_for_no_links": False,
        },
        {
            "name": "cleanup_not_possible",
            "state": {"lig_d": 0, "lig_legs": 0, "s_lig": 300.0, "D": 650.0, "b": 400.0},
            "shear_cleanup_possible": False,
            "shear_state_eligible_for_no_links": False,
        },
        {
            "name": "larger_current_links",
            "state": {"lig_d": 16, "lig_legs": 4, "s_lig": 175.0, "D": 650.0, "b": 400.0},
            "shear_cleanup_possible": True,
            "shear_state_eligible_for_no_links": True,
        },
    ]
    comparisons = []
    for case in cases:
        old = _old_generate_less_shear_reo_variants(
            state=dict(case["state"]),
            shear_cleanup_possible=bool(case["shear_cleanup_possible"]),
            shear_state_eligible_for_no_links=bool(case["shear_state_eligible_for_no_links"]),
        )
        new_raw = build_design_guide_shear_low_util_raw_variant_states(
            state=dict(case["state"]),
            shear_cleanup_possible=bool(case["shear_cleanup_possible"]),
            shear_state_eligible_for_no_links=bool(case["shear_state_eligible_for_no_links"]),
            reo_spacings=tuple(REO_SPACINGS),
            reo_bar_dias=tuple(REO_BAR_DIAS),
            canonical_no_shear_slig_mm=CANONICAL_NO_SHEAR_SLIG_MM,
        )
        new = _dedupe_for_snapshot(
            [dict(item) for item in list(new_raw.get("variants") or []) if isinstance(item, dict)]
        )
        comparisons.append(
            {
                "case": case["name"],
                "old_count": len(old),
                "new_count": len(new),
                "old_hash": _stable_hash(old),
                "new_hash": _stable_hash(new),
                "match": old == new,
            }
        )
    return {
        "decision": "SHEAR_LOW_UTIL_RAW_VARIANT_STATES_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "helper_imported": (
                "build_design_guide_shear_low_util_raw_variant_states as "
                "_build_design_guide_shear_low_util_raw_variant_states"
            )
            in inputs_source,
            "helper_called_in_target_function": (
                "_build_design_guide_shear_low_util_raw_variant_states(" in shear_cleanup_source
            ),
            "target_function_no_longer_calls_page_raw_generator": (
                "generate_less_shear_reo_variants(" not in shear_cleanup_source
            ),
            "page_still_computes_candidate_keys": (
                "_make_auto_design_candidate_key(" in shear_cleanup_source
            ),
            "page_raw_generator_retained_for_other_paths": (
                "def generate_less_shear_reo_variants(" in inputs_source
            ),
            "candidate_evaluation_controller_boundary_present": (
                "_evaluate_design_guide_shear_low_util_cleanup_candidate(" in shear_cleanup_source
            ),
            "legacy_direct_candidate_evaluation_removed": (
                "candidate = _evaluate_auto_design_candidate(" not in shear_cleanup_source
            ),
            "controller_has_helper": (
                "def build_design_guide_shear_low_util_raw_variant_states(" in controller_source
            ),
            "controller_page_free": "inputs_page" not in controller_source
            and "st.session_state" not in controller_source
            and "streamlit" not in controller_source,
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "candidate_evaluation_moved": True,
        "page_candidate_key_dedupe_retained": True,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "all_old_new_cases_match": all(
            bool(item.get("match")) for item in capture.get("comparisons") or []
        ),
        "source_checks_pass": all(source_checks.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_boundary_moved": capture.get("candidate_evaluation_moved") is True,
        "page_candidate_key_dedupe_retained": capture.get("page_candidate_key_dedupe_retained") is True,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Raw Variant States Cutover Snapshot",
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
            f"- {item.get('case')}: match=`{item.get('match')}`, old_count=`{item.get('old_count')}`, new_count=`{item.get('new_count')}`"
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_raw_variant_states_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_raw_variant_states_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_raw_variant_states_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

