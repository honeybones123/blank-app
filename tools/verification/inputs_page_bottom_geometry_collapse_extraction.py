from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.design_guide import bottom_recommendation_selector


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "bottom_recommendation_selector.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _bind(trace: list[dict[str, Any]]) -> None:
    def axis(candidate: dict, state: dict) -> str:
        return str(candidate.get("axis") or "")

    def score(candidate: dict, mode_config: dict, seed_candidate: dict) -> float:
        return float(candidate.get("score_seed", candidate.get("score", 0.0)) or 0.0)

    def select_best(candidates: list[dict], mode_config: dict, seed_candidate: dict) -> dict | None:
        pool = [c for c in candidates if c]
        if not pool:
            return None
        return min(pool, key=lambda c: float(c.get("score", c.get("score_seed", 0.0)) or 0.0))

    bottom_recommendation_selector.bind_bottom_recommendation_selector_dependencies(
        {
            "GUIDANCE_SHALLOW_GEOMETRY_SCORE_TIE_EPS": 5.0,
            "_geometry_trial_axis_for_bottom_rec": axis,
            "_merge_design_guide_rank_trace": lambda payload: trace.append(dict(payload)),
            "_score_auto_design_candidate": score,
            "_select_best_auto_design_candidate": select_best,
        }
    )


def _base_candidates() -> list[dict[str, Any]]:
    return [
        {"id": "compound", "recommendation_compound": True},
        {"id": "reo", "score": 9.0},
        {
            "id": "depth",
            "axis": "depth",
            "recommendation_geometry_trial": True,
            "score": 10.0,
        },
        {
            "id": "width",
            "axis": "width",
            "recommendation_geometry_trial": True,
            "score": 11.0,
        },
        {
            "id": "other",
            "axis": "other",
            "recommendation_geometry_trial": True,
            "score": 20.0,
        },
    ]


def _case_results() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    trace: list[dict[str, Any]] = []
    _bind(trace)
    original = _base_candidates()
    out = bottom_recommendation_selector._collapse_bottom_geometry_width_depth_trials(
        original,
        state={},
        seed_candidate={},
        mode_config={"search_strategy": "balanced"},
        efficiency_reduction_only=True,
    )
    results.append(
        {
            "name": "efficiency_reduction_only_returns_original",
            "passed": out is original
            and trace
            and trace[-1]["bottom_geo_collapse"]["chosen_axis_reason"]
            == "efficiency_reduction_only_skip_growth_axis_compare",
            "ids": [c.get("id") for c in out],
            "trace": trace,
        }
    )

    trace = []
    _bind(trace)
    out = bottom_recommendation_selector._collapse_bottom_geometry_width_depth_trials(
        _base_candidates(),
        state={},
        seed_candidate={},
        mode_config={"search_strategy": "shallow"},
    )
    results.append(
        {
            "name": "shallow_prefers_width_within_tie_eps",
            "passed": [c.get("id") for c in out] == ["compound", "reo", "width", "other"]
            and trace[-1]["bottom_geo_collapse"]["chosen_axis"] == "width"
            and trace[-1]["bottom_geo_collapse"]["depth_beat_width_reason"]
            == "depth_score_not_better_by_5",
            "ids": [c.get("id") for c in out],
            "trace": trace,
        }
    )

    trace = []
    _bind(trace)
    candidates = _base_candidates()
    for c in candidates:
        if c.get("id") == "width":
            c["score"] = 30.0
    out = bottom_recommendation_selector._collapse_bottom_geometry_width_depth_trials(
        candidates,
        state={},
        seed_candidate={},
        mode_config={"search_strategy": "shallow"},
    )
    results.append(
        {
            "name": "shallow_keeps_materially_better_depth",
            "passed": [c.get("id") for c in out] == ["compound", "reo", "depth", "other"]
            and trace[-1]["bottom_geo_collapse"]["chosen_axis"] == "depth",
            "ids": [c.get("id") for c in out],
            "trace": trace,
        }
    )

    trace = []
    _bind(trace)
    out = bottom_recommendation_selector._collapse_bottom_geometry_width_depth_trials(
        _base_candidates(),
        state={},
        seed_candidate={},
        mode_config={"search_strategy": "balanced"},
    )
    results.append(
        {
            "name": "balanced_selects_best_of_axes",
            "passed": [c.get("id") for c in out] == ["compound", "reo", "depth", "other"]
            and trace[-1]["bottom_geo_collapse"]["chosen_axis_reason"] == "balanced_mode_best_of_width_depth",
            "ids": [c.get("id") for c in out],
            "trace": trace,
        }
    )

    trace = []
    _bind(trace)
    no_width = [c for c in _base_candidates() if c.get("id") != "width"]
    out = bottom_recommendation_selector._collapse_bottom_geometry_width_depth_trials(
        no_width,
        state={},
        seed_candidate={},
        mode_config={"search_strategy": "balanced"},
    )
    results.append(
        {
            "name": "missing_axis_returns_original",
            "passed": out is no_width and trace == [],
            "ids": [c.get("id") for c in out],
            "trace": trace,
        }
    )
    return results


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Bottom Geometry Collapse Extraction",
        "",
        f"## Decision: {payload['decision']}",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    bridge_source = _read(BRIDGE)
    module_source = _read(MODULE)
    bridge_helper = _function_source(bridge_source, "_collapse_bottom_geometry_width_depth_trials")
    module_helper = _function_source(module_source, "_collapse_bottom_geometry_width_depth_trials")
    cases = _case_results()
    checks = {
        "module_exports_helper": "_collapse_bottom_geometry_width_depth_trials" in module_source,
        "bridge_imports_extracted_helper": "_collapse_bottom_geometry_width_depth_trials_extracted" in bridge_source,
        "bridge_helper_is_thin_delegate": len(bridge_helper.splitlines()) <= 18,
        "bridge_binds_bottom_selector_dependencies": "_bind_bottom_recommendation_selector_dependencies(globals())" in bridge_helper,
        "bridge_delegates_to_extracted": "_collapse_bottom_geometry_width_depth_trials_extracted(" in bridge_helper,
        "bridge_removed_collapse_body": "efficiency_reduction_only_skip_growth_axis_compare" not in bridge_helper,
        "module_keeps_collapse_body": "efficiency_reduction_only_skip_growth_axis_compare" in module_helper,
        "all_cases_pass": all(row["passed"] for row in cases),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in cases if not row["passed"])
    decision = "INPUTS_PAGE_BOTTOM_GEOMETRY_COLLAPSE_EXTRACTION_LOCKED" if not failures else "GAPS_REMAIN"
    payload = {
        "audit": "inputs_page_bottom_geometry_collapse_extraction",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "case_results": cases,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_behavior_changed": False,
        "engineering_calculations_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_page_bottom_geometry_collapse_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_bottom_geometry_collapse_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_bottom_geometry_collapse_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
