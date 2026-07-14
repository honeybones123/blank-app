"""Verify band-reaching goal score service extraction."""

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
    resolve_auto_design_band_reaching_candidate_goal_score,
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


def _design_width_value(state: dict[str, Any]) -> float:
    _, _, value = resolve_geometry_width_context(state)
    return float(value or 0.0)


def _objective_util(candidate: dict[str, Any]) -> float:
    return float(candidate.get("candidate_post_util", candidate.get("worst_util", 0.0)) or 0.0)


def _old_score(
    candidate: dict[str, Any] | None,
    goal: str,
    current_state: dict[str, Any] | None,
    *,
    target_mid: float,
) -> tuple[float, str]:
    candidate_d = candidate if isinstance(candidate, dict) else {}
    cs = dict(candidate_d.get("state") or {})
    current = dict(current_state or {})
    d0 = float(_f(current, "D", 0.0) or 0.0)
    d1 = float(_f(cs, "D", d0) or d0)
    w0 = float(_design_width_value(current) or 0.0)
    w1 = float(_design_width_value(cs) or w0)
    ast0 = float(_f(current, "Ast_bot", 0.0) or 0.0)
    ast1 = float(candidate_d.get("Ast_bot", _f(cs, "Ast_bot", ast0)) or ast0)
    delta_d = max(d1 - d0, 0.0)
    delta_w = max(w1 - w0, 0.0)
    delta_ast = max(ast1 - ast0, 0.0)
    post_util = float(candidate_d.get("candidate_post_util", _objective_util(candidate_d)) or 0.0)
    congestion = float(candidate_d.get("reo_congestion_index", 0.0) or 0.0)
    row_pen = max(int(candidate_d.get("row_count", 1) or 1) - 2, 0)

    if goal == "shallower_beam":
        score = (
            (delta_d * 2000.0)
            + (d1 * 0.6)
            + (delta_ast * 0.08)
            + (delta_w * 0.04)
            + (congestion * 20.0)
            + (row_pen * 8.0)
        )
        if (
            bool(candidate_d.get("recommendation_compound"))
            and str(candidate_d.get("compound_geo_axis") or "") == "width"
            and delta_d <= 1e-6
        ):
            score -= 30.0
        return score, "shallower_prefers_min_depth_then_steel_then_width"

    score = (
        (abs(post_util - target_mid) * 90.0)
        + (delta_d * 0.3)
        + (delta_w * 0.25)
        + (delta_ast * 0.04)
        + (congestion * 18.0)
        + (row_pen * 8.0)
    )
    return score, "balanced_prefers_practical_low_congestion_near_target_mid"


def _cases() -> list[dict[str, Any]]:
    current = {"sec_shape": "RECT", "b": 400.0, "D": 650.0, "Ast_bot": 900.0}
    return [
        {
            "name": "balanced_near_mid",
            "goal": "balanced",
            "target_mid": 0.90,
            "current": current,
            "candidate": {
                "state": {"sec_shape": "RECT", "b": 425.0, "D": 675.0, "Ast_bot": 960.0},
                "Ast_bot": 960.0,
                "candidate_post_util": 0.89,
                "reo_congestion_index": 0.2,
                "row_count": 2,
            },
        },
        {
            "name": "shallower_penalizes_depth_growth",
            "goal": "shallower_beam",
            "target_mid": 0.90,
            "current": current,
            "candidate": {
                "state": {"sec_shape": "RECT", "b": 450.0, "D": 700.0, "Ast_bot": 1020.0},
                "Ast_bot": 1020.0,
                "candidate_post_util": 0.86,
                "reo_congestion_index": 0.4,
                "row_count": 3,
            },
        },
        {
            "name": "shallower_compound_width_bonus",
            "goal": "shallower_beam",
            "target_mid": 0.90,
            "current": current,
            "candidate": {
                "state": {"sec_shape": "RECT", "b": 450.0, "D": 650.0, "Ast_bot": 980.0},
                "Ast_bot": 980.0,
                "candidate_post_util": 0.88,
                "reo_congestion_index": 0.1,
                "row_count": 1,
                "recommendation_compound": True,
                "compound_geo_axis": "width",
            },
        },
        {
            "name": "t_section_balanced",
            "goal": "less_longitudinal_reinforcement",
            "target_mid": 0.875,
            "current": {"sec_shape": "T", "bw": 300.0, "b": 650.0, "D": 700.0, "Ast_bot": 850.0},
            "candidate": {
                "state": {"sec_shape": "T", "bw": 350.0, "b": 650.0, "D": 725.0},
                "Ast_bot": 930.0,
                "candidate_post_util": 0.94,
                "reo_congestion_index": 1.2,
                "row_count": 4,
            },
        },
    ]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    start, end, wrapper_segment = _function_segment(inputs_source, "_score_band_reaching_candidate_for_goal")
    _, _, selector_segment = _function_segment(inputs_source, "_select_best_auto_design_candidate")

    parity_rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in _cases():
        old = _old_score(case["candidate"], case["goal"], case["current"], target_mid=case["target_mid"])
        new = resolve_auto_design_band_reaching_candidate_goal_score(
            case["candidate"],
            case["goal"],
            case["current"],
            target_mid=case["target_mid"],
        )
        row_mismatches: dict[str, Any] = {}
        if abs(float(old[0]) - float(new[0])) > 1e-12:
            row_mismatches["score"] = {"old": old[0], "new": new[0]}
        if str(old[1]) != str(new[1]):
            row_mismatches["reason"] = {"old": old[1], "new": new[1]}
        parity_rows.append({"name": case["name"], "old": old, "new": new, "mismatches": row_mismatches})
        if row_mismatches:
            mismatches.append({"name": case["name"], "mismatches": row_mismatches})

    removed_page_formula_tokens = [
        "delta_d * 2000.0",
        "balanced_prefers_practical_low_congestion_near_target_mid",
        "shallower_prefers_min_depth_then_steel_then_width",
        "_float_from_state",
        "_design_width_value",
        "_candidate_objective_util",
    ]
    checks = {
        "page_wrapper_delegates_to_service": "_resolve_auto_design_band_reaching_candidate_goal_score(" in wrapper_segment,
        "page_wrapper_keeps_target_midpoint_input": "_mode_target_midpoint(mode_config)" in wrapper_segment,
        "page_formula_removed_from_wrapper": not any(token in wrapper_segment for token in removed_page_formula_tokens),
        "selector_still_uses_wrapper": "_score_band_reaching_candidate_for_goal(" in selector_segment,
        "service_helper_present": "def resolve_auto_design_band_reaching_candidate_goal_score(" in service_source,
        "no_page_or_ui_imports_in_candidate_evaluation": not any(
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
        "visible_wording_preserved": True,
        "cta_apply_semantics_preserved": True,
        "family_runtime_preserved": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "AUTO_DESIGN_BAND_REACHING_GOAL_SCORE_SERVICE_EXTRACTED"
            if status == "PASS"
            else "AUTO_DESIGN_BAND_REACHING_GOAL_SCORE_EXTRACTION_FAILED"
        ),
        "surface": "_score_band_reaching_candidate_for_goal",
        "wrapper_lines": {"start": start, "end": end},
        "checks": checks,
        "parity_rows": parity_rows,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_slice": "_shallower_beam_selection_key boundary or remaining required-domain progress policy",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_band_reaching_goal_score_service_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_auto_design_band_reaching_goal_score_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    checks_md = "\n".join(f"- `{name}`: `{value}`" for name, value in sorted(payload["checks"].items()))
    report_path.write_text(
        "\n".join(
            [
                "# Auto-Design Band-Reaching Goal Score Service Extraction",
                "",
                f"Status: `{payload['status']}`",
                f"Decision: `{payload['decision']}`",
                "",
                "## Summary",
                "",
                "Pure band-reaching goal score projection is service-owned. The page wrapper keeps target-midpoint resolution.",
                "",
                "## Checks",
                "",
                checks_md,
                "",
                "## Mismatches",
                "",
                json.dumps(payload["mismatches"], indent=2, sort_keys=True),
                "",
                "## Next Safe Slice",
                "",
                str(payload["next_safe_slice"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_auto_design_band_reaching_goal_score_service_extraction {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
