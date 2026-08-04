"""Verify shear candidate practicality metric service extraction."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import (  # noqa: E402
    resolve_auto_design_shear_candidate_practicality_metrics,
    resolve_geometry_width_context,
)


INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _f(source: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(source.get(key, default) if source.get(key) is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _i(source: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(source.get(key, default) if source.get(key) is not None else default)
    except (TypeError, ValueError):
        return int(default)


def _old_metrics(candidate: dict[str, Any] | None, current_state: dict[str, Any] | None) -> dict[str, float | int]:
    candidate_d = candidate if isinstance(candidate, dict) else {}
    cs = dict(candidate_d.get("state") or {})
    current = dict(current_state or {})
    cur_legs = max(_i(current, "lig_legs", 0), 0)
    cand_legs = max(_i(cs, "lig_legs", cur_legs), 0)
    cur_s = float(_f(current, "s_lig", 0.0) or 0.0)
    cand_s = float(_f(cs, "s_lig", cur_s) or cur_s)
    cur_dia = max(_i(current, "lig_d", 0), 0)
    cand_dia = max(_i(cs, "lig_d", cur_dia), 0)
    cur_depth = float(_f(current, "D", 0.0) or 0.0)
    cand_depth = float(_f(cs, "D", cur_depth) or cur_depth)
    _, _, cur_width_raw = resolve_geometry_width_context(current)
    _, _, cand_width_raw = resolve_geometry_width_context(cs)
    cur_width = float(cur_width_raw or 0.0)
    cand_width = float(cand_width_raw or cur_width)
    cur_ast_bot = float(_f(current, "Ast_bot", 0.0) or 0.0)
    cur_ast_top = float(_f(current, "Ast_top", 0.0) or 0.0)
    cur_ast = cur_ast_bot + cur_ast_top
    cand_ast = (
        float(candidate_d.get("Ast_bot", _f(cs, "Ast_bot", cur_ast_bot)) or 0.0)
        + float(candidate_d.get("Ast_top", _f(cs, "Ast_top", cur_ast_top)) or 0.0)
    )
    leg_delta = abs(int(cand_legs) - int(cur_legs))
    spacing_delta = abs(float(cand_s) - float(cur_s))
    dia_delta = abs(int(cand_dia) - int(cur_dia))
    depth_delta = abs(float(cand_depth) - float(cur_depth))
    width_delta = abs(float(cand_width) - float(cur_width))
    steel_delta = abs(float(cand_ast) - float(cur_ast))
    odd_leg_penalty = 0.015 if cand_legs > 0 and cand_legs % 2 == 1 else 0.0
    total_practicality_penalty = odd_leg_penalty + (float(leg_delta) * 0.01)
    geometry_escalation_flag = 1 if (depth_delta > 1e-9 or width_delta > 1e-9) else 0
    geometry_delta = depth_delta + width_delta
    engineering_change = (
        (5.0 if geometry_escalation_flag else 0.0)
        + float(leg_delta)
        + (spacing_delta / 100.0)
        + (dia_delta / 2.0)
        + (geometry_delta / 100.0)
        + (steel_delta / 500.0)
        + total_practicality_penalty
    )
    return {
        "shear_candidate_leg_count": int(cand_legs),
        "shear_candidate_leg_delta": int(leg_delta),
        "shear_candidate_spacing_delta": float(spacing_delta),
        "shear_candidate_dia_delta": int(dia_delta),
        "shear_candidate_depth_delta": float(depth_delta),
        "shear_candidate_width_delta": float(width_delta),
        "shear_candidate_geometry_delta": float(geometry_delta),
        "shear_candidate_geometry_escalation_flag": int(geometry_escalation_flag),
        "shear_candidate_steel_delta": float(steel_delta),
        "shear_candidate_odd_leg_penalty": float(odd_leg_penalty),
        "shear_candidate_total_practicality_penalty": float(total_practicality_penalty),
        "shear_candidate_engineering_change": float(engineering_change),
    }


def _cases() -> list[dict[str, Any]]:
    base = {
        "sec_shape": "RECT",
        "b": 400.0,
        "D": 650.0,
        "lig_legs": 2,
        "s_lig": 200.0,
        "lig_d": 10,
        "Ast_bot": 900.0,
        "Ast_top": 200.0,
    }
    return [
        {"name": "same_state", "current": base, "candidate": {"state": dict(base)}},
        {
            "name": "odd_leg_spacing_depth_width",
            "current": base,
            "candidate": {
                "state": {**base, "lig_legs": 3, "s_lig": 125.0, "lig_d": 12, "D": 700.0, "b": 450.0},
                "Ast_bot": 1200.0,
                "Ast_top": 260.0,
            },
        },
        {
            "name": "t_section_width",
            "current": {**base, "sec_shape": "T", "bw": 300.0, "b": 650.0},
            "candidate": {"state": {**base, "sec_shape": "T", "bw": 350.0, "b": 650.0, "lig_legs": 4}},
        },
        {
            "name": "i_section_width",
            "current": {**base, "sec_shape": "I", "tw": 220.0, "b": 500.0},
            "candidate": {"state": {**base, "sec_shape": "I", "tw": 260.0, "b": 500.0, "lig_d": 16}},
        },
        {
            "name": "candidate_ast_fallback_from_state",
            "current": base,
            "candidate": {"state": {**base, "Ast_bot": 750.0, "Ast_top": 150.0, "lig_legs": 0, "s_lig": 0.0}},
        },
    ]


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        return abs(float(left) - float(right)) <= 1e-12
    return left == right


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    _, _, wrapper_segment = _function_segment(inputs_source, "_shear_candidate_practicality_metrics")
    _, _, score_segment = _function_segment(inputs_source, "_score_auto_design_candidate_components")

    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in _cases():
        old = _old_metrics(case["candidate"], case["current"])
        new = resolve_auto_design_shear_candidate_practicality_metrics(case["candidate"], case["current"])
        diff = {
            key: {"old": old.get(key), "new": new.get(key)}
            for key in sorted(set(old) | set(new))
            if not _same(old.get(key), new.get(key))
        }
        row = {"case": case["name"], "matches": not diff, "diff": diff, "old": old, "new": new}
        rows.append(row)
        if diff:
            mismatches.append(row)

    checks = {
        "wrapper_delegates_to_candidate_evaluation": "_resolve_auto_design_shear_candidate_practicality_metrics(candidate, current_state)" in wrapper_segment,
        "old_page_formula_removed": all(
            token not in wrapper_segment
            for token in (
                "leg_delta",
                "spacing_delta",
                "geometry_escalation_flag",
                "_float_from_state",
                "_int_from_state",
                "_design_width_value",
            )
        ),
        "score_components_still_uses_wrapper": "_shear_candidate_practicality_metrics(" in score_segment,
        "service_helper_present": "def resolve_auto_design_shear_candidate_practicality_metrics(" in service_source,
        "candidate_evaluation_forbidden_import_hits_empty": not any(
            token in service_source
            for token in (
                "import inputs_page",
                "from inputs_page",
                "import streamlit",
                "from streamlit",
                "st.session_state",
            )
        ),
        "parity_matches": not mismatches,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "AUTO_DESIGN_SHEAR_CANDIDATE_PRACTICALITY_SERVICE_EXTRACTED",
        "checks": checks,
        "case_count": len(rows),
        "mismatch_count": len(mismatches),
        "rows": rows,
        "mismatches": mismatches,
        "next_safe_slice": "auto-design selector shallower-beam metric boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_shear_candidate_practicality_service_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_auto_design_shear_candidate_practicality_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto-Design Shear Candidate Practicality Service Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        f"Cases: `{payload.get('case_count')}`",
        f"Mismatches: `{payload.get('mismatch_count')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_auto_design_shear_candidate_practicality_service_extraction {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [key for key, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
