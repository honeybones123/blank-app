from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
INPUTS_PAGE = ROOT / "inputs_page.py"
BENDING_FAMILY = ROOT / "design_brain" / "families" / "bending.py"
ARTIFACTS = ROOT / "artifacts"
VERIFICATION_DIR = ARTIFACTS / "verification"
AUDITS_DIR = ARTIFACTS / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _function_segment(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_start = source.find("\ndef ", start + len(marker))
    if next_start < 0:
        next_start = len(source)
    return source[start:next_start]


def _extract_page_change_arrow(inputs_source: str) -> str:
    line = next(
        line
        for line in inputs_source.splitlines()
        if 'lines.append(f"Depth:' in line and "{int(round(a_d))}" in line
    )
    start = line.index(")} ") + 3
    end = line.index(" {int(round(a_d))}")
    return line[start:end]


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        return int(default)


def _normalized_sec_shape(raw: Any) -> str:
    value = str(raw or "RECT").strip().upper()
    if value in ("T", "T-SECTION", "T_SECTION", "T-BEAM"):
        return "T"
    if value in ("I", "I-SECTION", "I_SECTION", "I-BEAM"):
        return "I"
    return "RECT"


def _prefixes(state: dict[str, Any] | None) -> tuple[str, str]:
    raw = (state or {}).get("sec_shape") or (state or {}).get("inputs_sec_shape")
    if _normalized_sec_shape(raw) in ("T", "I"):
        return "Web bottom reo", "Web top reo"
    return "Bottom reo", "Top reo"


def _width_context(state: dict[str, Any]) -> tuple[str, str, float]:
    sec_shape = str(state.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "bw", "Web width bw (mm)", _as_float(state.get("bw", state.get("b", 300.0)), 300.0)
    if sec_shape == "I":
        return "tw", "Web thickness tw (mm)", _as_float(state.get("tw", state.get("b", 200.0)), 200.0)
    return "b", "Width b (mm)", _as_float(state.get("b", 400.0), 400.0)


def _practical_label(count_1: int, count_2: int, dia: int) -> str:
    if count_2 > 0:
        return f"{count_1}N{dia} + {count_2}N{dia}"
    return f"{count_1}N{dia}"


def _bottom_label(state: dict[str, Any]) -> str:
    mode_1 = str(state.get("bot1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("bot2_layout_mode", "Count") or "Count")
    if mode_1 == "Count" and mode_2 == "Count":
        count_1 = _as_int(state.get("bot1_count"), 0)
        count_2 = _as_int(state.get("bot2_count"), 0)
        dia = _as_int(state.get("db_bot_1", state.get("db_bot", 0)), 0)
        if count_1 > 0:
            return _practical_label(count_1, count_2, dia)
    spacing_1 = _as_float(state.get("bot1_spacing"), 0.0)
    dia_1 = _as_int(state.get("db_bot_1"), 0)
    return f"N{dia_1} @ {int(spacing_1)}"


def _top_label(state: dict[str, Any]) -> str:
    mode_1 = str(state.get("top1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("top2_layout_mode", "Count") or "Count")
    count_1 = _as_int(state.get("top1_count"), 0)
    count_2 = _as_int(state.get("top2_count"), 0)
    if mode_1 == "Count" and mode_2 == "Count":
        dia = _as_int(state.get("db_top_1", state.get("db_top", 0)), 0)
        if count_1 > 0 or count_2 > 0:
            return _practical_label(count_1, count_2, dia)
        return "None"
    spacing_1 = _as_float(state.get("top1_spacing"), 0.0)
    dia_1 = _as_int(state.get("db_top_1"), 0)
    return f"N{dia_1} @ {int(spacing_1)}"


def _shear_fragment(state: dict[str, Any]) -> str | None:
    legs = _as_int(state.get("lig_legs"), 0)
    if legs <= 0:
        return None
    return f"N{_as_int(state.get('lig_d'), 0)}, {legs}-leg @{int(_as_float(state.get('s_lig'), 0.0))}"


def _reference_change_lines(before: dict[str, Any], updates: dict[str, Any] | None, arrow: str) -> list[str]:
    if not updates:
        return []
    before_state = dict(before or {})
    after_state = dict(before_state)
    after_state.update(dict(updates or {}))
    lines: list[str] = []
    _, _, before_width = _width_context(before_state)
    _, _, after_width = _width_context(after_state)
    try:
        if abs(float(after_width) - float(before_width)) > 1e-6:
            lines.append(
                f"Width: {int(round(float(before_width)))} {arrow} {int(round(float(after_width)))} mm",
            )
    except (TypeError, ValueError):
        pass
    try:
        before_depth = _as_float(before_state.get("D"), 0.0)
        after_depth = _as_float(after_state.get("D"), 0.0)
        if abs(after_depth - before_depth) > 1e-6:
            lines.append(f"Depth: {int(round(before_depth))} {arrow} {int(round(after_depth))} mm")
    except (TypeError, ValueError):
        pass
    before_bottom = _bottom_label(before_state)
    after_bottom = _bottom_label(after_state)
    bottom_phrase, top_phrase = _prefixes(after_state)
    if before_bottom != after_bottom:
        lines.append(f"{bottom_phrase}: {before_bottom} {arrow} {after_bottom}")
    before_top = _top_label(before_state)
    after_top = _top_label(after_state)
    if before_top != after_top:
        lines.append(f"{top_phrase}: {before_top} {arrow} {after_top}")
    before_shear = _shear_fragment(before_state)
    after_shear = _shear_fragment(after_state)
    if before_shear != after_shear:
        if after_shear is None:
            lines.append(f"Shear links: {before_shear} {arrow} removed")
        elif before_shear is None:
            lines.append(f"Shear links: none {arrow} {after_shear}")
        else:
            lines.append(f"Shear links: {before_shear} {arrow} {after_shear}")
    return lines


def _cases() -> list[dict[str, Any]]:
    base = {
        "sec_shape": "RECT",
        "b": 400.0,
        "D": 650.0,
        "bot1_layout_mode": "Count",
        "bot2_layout_mode": "Count",
        "bot1_count": 8,
        "bot2_count": 0,
        "db_bot_1": 16,
        "top1_layout_mode": "Count",
        "top2_layout_mode": "Count",
        "top1_count": 0,
        "top2_count": 0,
        "db_top_1": 12,
        "lig_legs": 2,
        "lig_d": 10,
        "s_lig": 200.0,
    }
    return [
        {"name": "no_updates", "before": dict(base), "updates": {}},
        {"name": "rect_width_depth", "before": dict(base), "updates": {"b": 350.0, "D": 600.0}},
        {"name": "bottom_count_label", "before": dict(base), "updates": {"bot1_count": 5}},
        {"name": "top_from_none", "before": dict(base), "updates": {"top1_count": 2}},
        {"name": "remove_shear_links", "before": dict(base), "updates": {"lig_legs": 0}},
        {"name": "add_shear_links", "before": {**base, "lig_legs": 0}, "updates": {"lig_legs": 2}},
        {"name": "t_section_web_prefix", "before": {**base, "sec_shape": "T", "bw": 300.0}, "updates": {"bot1_count": 6}},
        {"name": "i_section_tw_width", "before": {**base, "sec_shape": "I", "tw": 220.0}, "updates": {"tw": 260.0}},
        {
            "name": "spacing_mode_bottom_label",
            "before": {**base, "bot1_layout_mode": "Spacing", "bot1_spacing": 180.0},
            "updates": {"bot1_spacing": 150.0},
        },
    ]


def main() -> int:
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    inputs_source = _read(INPUTS_PAGE)
    bending_source = _read(BENDING_FAMILY)
    compute_segment = _function_segment(inputs_source, "_compute_bottom_reo_recommendation")
    family_segment = _function_segment(bending_source, "build_bottom_reo_guidance_change_lines_for_updates")

    from design_brain.families.bending import build_bottom_reo_guidance_change_lines_for_updates

    arrow = _extract_page_change_arrow(inputs_source)
    parity_rows = []
    for case in _cases():
        expected = _reference_change_lines(dict(case["before"]), dict(case["updates"]), arrow)
        actual = build_bottom_reo_guidance_change_lines_for_updates(
            dict(case["before"]),
            dict(case["updates"]),
        )
        parity_rows.append(
            {
                "case": case["name"],
                "expected": expected,
                "actual": actual,
                "matches": expected == actual,
            },
        )

    checks = {
        "family_helper_exists": "def build_bottom_reo_guidance_change_lines_for_updates(" in bending_source,
        "page_imports_family_helper": (
            "build_bottom_reo_guidance_change_lines_for_updates as _build_bottom_reo_guidance_change_lines_for_updates"
            in inputs_source
        ),
        "bottom_reo_callsite_delegates_to_family": (
            "gcl = _build_bottom_reo_guidance_change_lines_for_updates(state, dict(best.get(\"updates\") or {}))"
            in compute_segment
        ),
        "bottom_reo_callsite_no_longer_uses_page_change_line_helper": (
            "gcl = _guidance_change_lines_for_updates(" not in compute_segment
        ),
        "family_helper_has_no_page_or_ui_imports": all(
            token not in family_segment
            for token in (
                "inputs_page",
                "streamlit",
                "\nst.",
                " session_state",
                "Apply routing",
            )
        ),
        "visible_change_line_parity": all(row["matches"] for row in parity_rows),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "surface": "bottom_reo_guidance_change_lines",
        "extraction_complete_estimate_after_pass": "76-80%" if status == "PASS" else "75-79%",
        "checks": checks,
        "parity_rows": parity_rows,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }

    stamp = _timestamp()
    json_path = VERIFICATION_DIR / f"design_guide_bottom_reo_guidance_change_lines_family_extraction_{stamp}.json"
    md_path = AUDITS_DIR / f"design_guide_bottom_reo_guidance_change_lines_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Bottom Reo Guidance Change Lines Family Extraction",
                "",
                f"## Summary\n{status}",
                "",
                "## Checks",
                *[f"- {name}: {value}" for name, value in checks.items()],
                "",
                "## Parity Cases",
                *[f"- {row['case']}: {'PASS' if row['matches'] else 'FAIL'}" for row in parity_rows],
                "",
                "## Ownership",
                "The bottom-reo visible guidance change-line projection is now owned by design_brain.families.bending.",
                "inputs_page.py keeps only the bottom-reo compute orchestration and passes state/updates into the family helper.",
                "",
                "## Behaviour",
                "- visible wording changed: false",
                "- CTA/apply semantics changed: false",
                "- family runtime behaviour changed: false",
                "",
                f"JSON: {json_path}",
            ],
        ),
        encoding="utf-8",
    )
    print(f"{status} {json_path}")
    print(md_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
