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

from inputs_page_modules.design_guide import geometry_tightening


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "geometry_tightening.py"
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


def _bind(case: dict[str, Any], trace: list[dict[str, Any]]) -> None:
    trials = list(case.get("trials") or [])
    candidate_by_depth = dict(case.get("candidate_by_depth") or {})

    def evaluate_candidate_full(state: dict, **kwargs: Any) -> dict | None:
        trace.append({"kind": "seed", "kwargs": dict(kwargs)})
        if case.get("no_seed"):
            return None
        return {
            "state": dict(state),
            "is_compliant": not bool(case.get("seed_noncompliant")),
            "overview": {"utils": {"bending": 0.8}},
            "score": float(case.get("current_score", 10.0)),
        }

    def evaluate_candidate_fast(candidate_state: dict, **kwargs: Any) -> dict | None:
        depth = candidate_state.get("D")
        row = candidate_by_depth.get(depth)
        trace.append({"kind": "candidate", "state": dict(candidate_state), "kwargs": dict(kwargs)})
        if row is None:
            return None
        out = dict(row)
        out.setdefault("state", dict(candidate_state))
        out.setdefault("updates", {"D": depth, "b": candidate_state.get("b")})
        out.setdefault("depth", depth)
        out.setdefault("width", candidate_state.get("b"))
        out.setdefault("label", kwargs.get("label"))
        out.setdefault("worst_util", row.get("util", 0.0))
        return out

    geometry_tightening.bind_geometry_tightening_dependencies(
        {
            "_build_auto_design_context": lambda state, mode_config, **kwargs: {
                "state": dict(state),
                "mode_config": dict(mode_config),
            },
            "_candidate_debug_summary": lambda candidate: {
                "label": candidate.get("label"),
                "score": candidate.get("score"),
            },
            "_candidate_in_target_band": lambda candidate, mode_config: bool(candidate.get("in_band")),
            "_design_mode_config": lambda goal: {"goal": goal},
            "_design_optimisation_goal": lambda state: str(state.get("goal") or "balanced"),
            "_evaluate_candidate_fast": evaluate_candidate_fast,
            "_geometry_lock_enabled": lambda state: bool(case.get("geometry_locked")),
            "_geometry_tightening_trial_updates": lambda state: list(trials),
            "_guidance_state_snapshot": lambda state: dict(state or {}),
            "_resolve_geometry_width_context": lambda state: ("b", "width", float(state.get("b", 0.0) or 0.0)),
            "_score_auto_design_candidate": lambda candidate, mode_config, seed_candidate: float(
                candidate.get("score", case.get("current_score", 10.0))
            ),
            "evaluate_candidate_full": evaluate_candidate_full,
        }
    )


def _case_results() -> list[dict[str, Any]]:
    cases = [
        {
            "name": "geometry_lock_returns_none",
            "state": {"D": 600, "b": 300},
            "geometry_locked": True,
            "expected_none": True,
        },
        {
            "name": "missing_seed_returns_none",
            "state": {"D": 600, "b": 300},
            "no_seed": True,
            "expected_none": True,
        },
        {
            "name": "noncompliant_seed_returns_none",
            "state": {"D": 600, "b": 300},
            "seed_noncompliant": True,
            "expected_none": True,
        },
        {
            "name": "best_improved_candidate_is_packaged",
            "state": {"D": 600, "b": 300},
            "current_score": 10.0,
            "trials": [{"D": 570, "b": 280}, {"D": 560, "b": 270}, {"D": 550, "b": 260}],
            "candidate_by_depth": {
                570: {"is_compliant": False, "score": 1.0},
                560: {"is_compliant": True, "score": 9.0, "in_band": False, "util": 0.91},
                550: {"is_compliant": True, "score": 8.0, "in_band": True, "util": 0.88},
            },
            "expected_updates": {"D": 550, "b": 260},
            "expected_label": "260 x 550 mm",
            "expected_score": 8.0,
        },
        {
            "name": "candidate_not_better_than_current_returns_none",
            "state": {"D": 600, "b": 300},
            "current_score": 8.0,
            "trials": [{"D": 560, "b": 270}],
            "candidate_by_depth": {
                560: {"is_compliant": True, "score": 8.0, "in_band": True, "util": 0.88},
            },
            "expected_none": True,
        },
    ]
    rows: list[dict[str, Any]] = []
    for case in cases:
        trace: list[dict[str, Any]] = []
        _bind(case, trace)
        result = geometry_tightening._compute_geometry_tightening_recommendation(
            dict(case.get("state") or {})
        )
        if case.get("expected_none"):
            passed = result is None
        else:
            passed = isinstance(result, dict)
            passed = passed and result.get("updates") == case.get("expected_updates")
            passed = passed and result.get("label") == case.get("expected_label")
            passed = passed and result.get("candidate_type") == "geometry"
            passed = passed and abs(float(result.get("score", 0.0)) - float(case.get("expected_score"))) < 1e-9
            passed = passed and result.get("candidate_summary") == {
                "label": case.get("expected_label"),
                "score": case.get("expected_score"),
            }
        rows.append({"name": case["name"], "passed": passed, "result": result, "trace": trace})
    return rows


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Geometry Tightening Extraction",
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
    bridge_helper = _function_source(bridge_source, "_compute_geometry_tightening_recommendation")
    module_helper = _function_source(module_source, "_compute_geometry_tightening_recommendation")
    cases = _case_results()
    checks = {
        "module_exists": MODULE.exists(),
        "bridge_imports_extracted_helper": "_compute_geometry_tightening_recommendation_extracted" in bridge_source,
        "bridge_helper_is_thin_delegate": len(bridge_helper.splitlines()) <= 3,
        "bridge_binds_geometry_tightening_dependencies": "_bind_geometry_tightening_dependencies(globals())" in bridge_helper,
        "bridge_delegates_to_extracted": "_compute_geometry_tightening_recommendation_extracted(state)" in bridge_helper,
        "bridge_removed_tightening_body": "source=\"geometry_tighten\"" not in bridge_helper
        and "action_type=\"tighten_geometry\"" not in bridge_helper
        and "_geometry_tightening_trial_updates(" not in bridge_helper,
        "module_keeps_tightening_body": "geometry_tighten" in module_helper
        and "tighten_geometry" in module_helper,
        "module_has_dependency_binder": "def bind_geometry_tightening_dependencies" in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "all_cases_pass": all(row["passed"] for row in cases),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in cases if not row["passed"])
    decision = "INPUTS_PAGE_GEOMETRY_TIGHTENING_EXTRACTION_LOCKED" if not failures else "GAPS_REMAIN"
    payload = {
        "audit": "inputs_page_geometry_tightening_extraction",
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
    json_path = VERIFICATION_DIR / f"inputs_page_geometry_tightening_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_geometry_tightening_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_geometry_tightening_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
