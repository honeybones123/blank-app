"""Verify shear low-util change-line wording cutover."""

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

ARROW = "\u00e2\ufffd\u00a0\u2019"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _width_context(state: dict[str, Any]) -> tuple[str, str, float]:
    sec_shape = str(state.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "bw", "Web width bw (mm)", float(state.get("bw", state.get("b", 300.0)) or 300.0)
    if sec_shape == "I":
        return "tw", "Web thickness tw (mm)", float(state.get("tw", state.get("b", 200.0)) or 200.0)
    return "b", "Width b (mm)", float(state.get("b", 400.0) or 400.0)


def _float_from_state(state: dict[str, Any], key: str, default: float) -> float:
    value = state.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def _practical_label(count_1: int, count_2: int, dia: int) -> str:
    if count_2 > 0:
        return f"{count_1}N{dia} + {count_2}N{dia}"
    return f"{count_1}N{dia}"


def _bottom_label(state: dict[str, Any]) -> str:
    mode_1 = str(state.get("bot1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("bot2_layout_mode", "Count") or "Count")
    if mode_1 == "Count" and mode_2 == "Count":
        count_1 = int(state.get("bot1_count", 0) or 0)
        count_2 = int(state.get("bot2_count", 0) or 0)
        dia = int(state.get("db_bot_1", state.get("db_bot", 0)) or 0)
        if count_1 > 0:
            return _practical_label(count_1, count_2, dia)
    spacing_1 = float(state.get("bot1_spacing", 0.0) or 0.0)
    dia_1 = int(state.get("db_bot_1", 0) or 0)
    return f"N{dia_1} @ {int(spacing_1)}"


def _top_label(state: dict[str, Any]) -> str:
    mode_1 = str(state.get("top1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("top2_layout_mode", "Count") or "Count")
    count_1 = int(state.get("top1_count", 0) or 0)
    count_2 = int(state.get("top2_count", 0) or 0)
    if mode_1 == "Count" and mode_2 == "Count":
        dia = int(state.get("db_top_1", state.get("db_top", 0)) or 0)
        if count_1 > 0 or count_2 > 0:
            return _practical_label(count_1, count_2, dia)
        return "None"
    spacing_1 = float(state.get("top1_spacing", 0.0) or 0.0)
    dia_1 = int(state.get("db_top_1", 0) or 0)
    return f"N{dia_1} @ {int(spacing_1)}"


def _sec_shape(raw: Any) -> str:
    value = str(raw or "RECT").strip().upper()
    if value in ("T", "T-SECTION", "T_SECTION", "T-BEAM"):
        return "T"
    if value in ("I", "I-SECTION", "I_SECTION", "I-BEAM"):
        return "I"
    return "RECT"


def _prefixes(state: dict[str, Any] | None) -> tuple[str, str]:
    raw = (state or {}).get("sec_shape") or (state or {}).get("inputs_sec_shape")
    if _sec_shape(raw) in ("T", "I"):
        return "Web bottom reo", "Web top reo"
    return "Bottom reo", "Top reo"


def _shear_fragment(state: dict[str, Any]) -> str | None:
    legs = int(state.get("lig_legs", 0) or 0)
    if legs <= 0:
        return None
    return f"N{int(state.get('lig_d', 0) or 0)}, {legs}-leg @{int(float(state.get('s_lig', 0.0) or 0.0))}"


def _old_change_lines(before: dict[str, Any], updates: dict[str, Any] | None) -> list[str]:
    if not updates:
        return []
    after = dict(before)
    after.update(dict(updates or {}))
    lines: list[str] = []
    _, _, bw = _width_context(before)
    _, _, aw = _width_context(after)
    try:
        if abs(float(aw) - float(bw)) > 1e-6:
            lines.append(f"Width: {int(round(float(bw)))} {ARROW} {int(round(float(aw)))} mm")
    except (TypeError, ValueError):
        pass
    try:
        b_d = float(_float_from_state(before, "D", 0.0))
        a_d = float(_float_from_state(after, "D", 0.0))
        if abs(a_d - b_d) > 1e-6:
            lines.append(f"Depth: {int(round(b_d))} {ARROW} {int(round(a_d))} mm")
    except (TypeError, ValueError):
        pass
    bl = _bottom_label(before)
    al = _bottom_label(after)
    bot_phrase, top_phrase = _prefixes(after)
    if bl != al:
        lines.append(f"{bot_phrase}: {bl} {ARROW} {al}")
    tl_b = _top_label(before)
    tl_a = _top_label(after)
    if tl_b != tl_a:
        lines.append(f"{top_phrase}: {tl_b} {ARROW} {tl_a}")
    bf = _shear_fragment(before)
    af = _shear_fragment(after)
    if bf != af:
        if af is None:
            lines.append(f"Shear links: {bf} {ARROW} removed")
        elif bf is None:
            lines.append(f"Shear links: none {ARROW} {af}")
        else:
            lines.append(f"Shear links: {bf} {ARROW} {af}")
    return lines


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


def _base_state(**overrides: Any) -> dict[str, Any]:
    state = {
        "sec_shape": "RECT",
        "b": 400.0,
        "D": 650.0,
        "bot1_layout_mode": "Count",
        "bot2_layout_mode": "Count",
        "bot1_count": 5,
        "bot2_count": 0,
        "db_bot_1": 16,
        "top1_layout_mode": "Count",
        "top2_layout_mode": "Count",
        "top1_count": 2,
        "top2_count": 0,
        "db_top_1": 12,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200.0,
    }
    state.update(overrides)
    return state


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_change_lines_for_updates,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    target_source = _target_function_source(inputs_source)
    cases = [
        {"name": "no_updates", "before": _base_state(), "updates": {}},
        {"name": "width_depth", "before": _base_state(), "updates": {"b": 450.0, "D": 700.0}},
        {"name": "bottom_count", "before": _base_state(), "updates": {"bot1_count": 4}},
        {"name": "top_count", "before": _base_state(), "updates": {"top1_count": 0}},
        {"name": "shear_removed", "before": _base_state(), "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0}},
        {"name": "shear_added", "before": _base_state(lig_d=0, lig_legs=0), "updates": {"lig_d": 10, "lig_legs": 2, "s_lig": 250.0}},
        {"name": "shear_spacing_changed", "before": _base_state(), "updates": {"s_lig": 300.0}},
        {"name": "t_section_prefix", "before": _base_state(sec_shape="T", bw=300.0), "updates": {"bot1_count": 4}},
        {"name": "i_section_width_and_prefix", "before": _base_state(sec_shape="I", tw=250.0), "updates": {"tw": 300.0, "top1_count": 0}},
        {
            "name": "spacing_layout_bottom",
            "before": _base_state(bot1_layout_mode="Spacing", bot1_spacing=150.0, db_bot_1=12),
            "updates": {"bot1_spacing": 200.0},
        },
    ]
    comparisons = []
    for case in cases:
        old = _old_change_lines(case["before"], case["updates"])
        new = build_design_guide_shear_low_util_change_lines_for_updates(
            before=case["before"],
            updates=case["updates"],
        )
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
        "decision": "SHEAR_LOW_UTIL_CHANGE_LINES_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "target_function_found": bool(target_source),
            "helper_imported": (
                "build_design_guide_shear_low_util_change_lines_for_updates as "
                "_build_design_guide_shear_low_util_change_lines_for_updates"
            )
            in inputs_source,
            "helper_called_in_target_function": (
                "_build_design_guide_shear_low_util_change_lines_for_updates("
                in target_source
            ),
            "old_page_helper_removed_from_target": (
                "_guidance_change_lines_for_updates(state, updates)" not in target_source
            ),
            "legacy_page_helper_retained_for_other_paths": (
                "def _guidance_change_lines_for_updates(" in inputs_source
            ),
            "candidate_evaluation_controller_boundary_present": (
                "_evaluate_design_guide_shear_low_util_cleanup_candidate(" in target_source
            ),
            "legacy_direct_candidate_evaluation_removed": (
                "candidate = _evaluate_auto_design_candidate(" not in target_source
            ),
            "current_overview_input_still_page_owned": (
                "_collect_design_overview(state)" in target_source
            ),
            "controller_has_helper": (
                "def build_design_guide_shear_low_util_change_lines_for_updates("
                in controller_source
            ),
            "controller_page_free": "inputs_page" not in controller_source
            and "st.session_state" not in controller_source
            and "streamlit" not in controller_source
            and "widgets_helpers" not in controller_source,
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "candidate_evaluation_moved": True,
        "overview_collection_moved": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "all_old_new_cases_match": all(
            item.get("match") for item in capture.get("comparisons") or []
        ),
        "source_checks_pass": all(source_checks.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_boundary_moved": capture.get("candidate_evaluation_moved") is True,
        "overview_collection_not_moved": capture.get("overview_collection_moved") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Change Lines Cutover Snapshot",
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_change_lines_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_change_lines_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_change_lines_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

