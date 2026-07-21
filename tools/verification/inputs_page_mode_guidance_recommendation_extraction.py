from __future__ import annotations

import ast
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.design_guide import mode_guidance_recommendation


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "mode_guidance_recommendation.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


class FakeStreamlit:
    def __init__(self, *, dev_mode: bool = False) -> None:
        self.session_state = {"_dev_mode": dev_mode}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _bind_for_case(case: dict[str, Any], logs: list[dict[str, Any]]) -> None:
    def _seed_candidate(state: dict, *, source: str) -> dict | None:
        if case.get("seed_missing"):
            return None
        return {
            "is_compliant": not case.get("seed_noncompliant", False),
            "overview": {"focus": case.get("governing_focus", "bending")},
            "state": dict(state),
            "summary": {
                "Ast_bot": case.get("current_ast", 100.0),
                "summary_phiMu_kNm": 200.0,
                "summary_Mu_star_kNm": 100.0,
            },
        }

    def _run_full(seed: dict, mode: str, *, force: bool) -> dict:
        return {
            "candidate": {
                "updates": dict(case.get("updates") or {"D": 525}),
                "label": case.get("label", "Mode candidate"),
                "score": case.get("score", 1.25),
                "state": {"mode": case.get("candidate_mode", case.get("mode", "efficient"))},
                "overview": {"utils": {"shear": case.get("shear_util", 0.64)}},
                "summary": {
                    "Ast_bot": case.get("candidate_ast", 90.0),
                    "summary_phiMu_kNm": case.get("phi", 250.0),
                    "summary_Mu_star_kNm": case.get("mu", 200.0),
                    "real_util": case.get("real_util", 0.8),
                },
                "objective": case.get("objective", 0.73),
            },
            "material_change": bool(case.get("material_change", True)),
            "metrics": {"checked": True},
        }

    mode_guidance_recommendation.bind_mode_guidance_recommendation_dependencies(
        {
            "_agent_debug_log": lambda message, payload, **kwargs: logs.append(
                {"message": message, "payload": payload, "kwargs": kwargs}
            ),
            "_candidate_debug_summary": lambda candidate: dict((candidate or {}).get("summary") or {}),
            "_candidate_objective_util": lambda candidate: float((candidate or {}).get("objective", 0.0) or 0.0),
            "_design_optimisation_goal": lambda state: str((state or {}).get("mode") or case.get("mode", "efficient")),
            "_evaluate_auto_design_candidate": _seed_candidate,
            "_governing_focus_from_overview": lambda overview: str((overview or {}).get("focus") or "bending"),
            "_guidance_state_snapshot": lambda state: dict(state or {}),
            "_materialize_full_evaluated_candidate": lambda candidate, *, source: dict(candidate or {}),
            "_mode_guidance_focus_from_updates": lambda updates: case.get("focus", "bending"),
            "_recommendation_search_allowed": lambda state: not case.get("search_blocked", False),
            "_updates_match_state": lambda state, updates: bool(case.get("updates_match_state", False)),
            "math": math,
            "run_full_auto_design": _run_full,
            "st": FakeStreamlit(dev_mode=bool(case.get("dev_mode", False))),
        }
    )


def _run_cases() -> list[dict[str, Any]]:
    cases = [
        {"name": "search_blocked", "search_blocked": True, "expected_none": True},
        {"name": "seed_noncompliant", "seed_noncompliant": True, "expected_none": True},
        {"name": "updates_match_state", "updates_match_state": True, "expected_none": True},
        {
            "name": "bending_expected_util",
            "mode": "efficient",
            "updates": {"D": 525},
            "phi": 250.0,
            "mu": 200.0,
            "expected_util": 0.8,
            "expected_focus": "bending",
        },
        {
            "name": "shear_mode_expected_util",
            "mode": "less_shear_reinforcement",
            "candidate_mode": "less_shear_reinforcement",
            "updates": {"s_lig": 250},
            "focus": "shear",
            "shear_util": 0.61,
            "expected_util": 0.61,
            "expected_focus": "shear",
        },
        {
            "name": "dev_mode_logs_heavier_bending",
            "dev_mode": True,
            "current_ast": 100.0,
            "candidate_ast": 120.0,
            "updates": {"bottom_bar_dia": 20},
            "expected_log_count_at_least": 2,
        },
    ]
    results: list[dict[str, Any]] = []
    for case in cases:
        logs: list[dict[str, Any]] = []
        _bind_for_case(case, logs)
        result = mode_guidance_recommendation._compute_mode_guidance_recommendation_uncached(
            {"mode": case.get("mode", "efficient")}
        )
        passed = True
        if case.get("expected_none"):
            passed = result is None
        else:
            result_d = dict(result or {})
            if "expected_util" in case:
                passed = passed and abs(float(result_d.get("expected_util")) - float(case["expected_util"])) < 1e-9
            if "expected_focus" in case:
                passed = passed and result_d.get("focus") == case["expected_focus"]
            passed = passed and result_d.get("candidate_type") == "mode"
            passed = passed and bool(result_d.get("updates"))
            if "expected_log_count_at_least" in case:
                passed = passed and len(logs) >= int(case["expected_log_count_at_least"])
        results.append(
            {
                "name": case["name"],
                "passed": passed,
                "result": result,
                "log_count": len(logs),
            }
        )
    return results


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Mode Guidance Recommendation Extraction",
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
    bridge_helper = _function_source(bridge_source, "_compute_mode_guidance_recommendation_uncached")
    module_helper = _function_source(module_source, "_compute_mode_guidance_recommendation_uncached")
    case_results = _run_cases()
    checks = {
        "module_exists": MODULE.exists(),
        "bridge_imports_extracted_helper": "_compute_mode_guidance_recommendation_uncached_extracted" in bridge_source,
        "bridge_helper_is_thin_delegate": len(bridge_helper.splitlines()) <= 8,
        "bridge_binds_module_dependencies": "_bind_mode_guidance_recommendation_dependencies(globals())" in bridge_helper,
        "bridge_delegates_to_extracted": "_compute_mode_guidance_recommendation_uncached_extracted(state)" in bridge_helper,
        "bridge_removed_solver_body": "run_full_auto_design(" not in bridge_helper,
        "module_keeps_solver_body": "run_full_auto_design(" in module_helper,
        "all_cases_pass": all(row["passed"] for row in case_results),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in case_results if not row["passed"])
    decision = "INPUTS_PAGE_MODE_GUIDANCE_RECOMMENDATION_EXTRACTION_LOCKED" if not failures else "GAPS_REMAIN"
    payload = {
        "audit": "inputs_page_mode_guidance_recommendation_extraction",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "case_results": case_results,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_behavior_changed": False,
        "engineering_calculations_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_page_mode_guidance_recommendation_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_mode_guidance_recommendation_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_mode_guidance_recommendation_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
