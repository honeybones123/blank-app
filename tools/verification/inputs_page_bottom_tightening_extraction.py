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

from inputs_page_modules.design_guide import bottom_tightening


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "bottom_tightening.py"
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


def _bind(case: dict[str, Any]) -> None:
    arrangements = list(case.get("arrangements") or [])
    candidate_by_id = dict(case.get("candidate_by_id") or {})

    def arrangement_to_updates(arrangement: dict) -> dict:
        return {
            "bot1_count": arrangement.get("bot1_count"),
            "bot2_count": arrangement.get("bot2_count"),
            "db_bot_1": arrangement.get("db_bot_1"),
        }

    def evaluate_fast(candidate_state: dict, **kwargs: Any) -> dict | None:
        key = candidate_state.get("bot1_count")
        row = candidate_by_id.get(key)
        if row is None:
            return None
        out = dict(row)
        out.setdefault("state", dict(candidate_state))
        out.setdefault("label", kwargs.get("label"))
        out.setdefault("overview", {"utils": {"bending": row.get("bending", 0.0)}})
        return out

    bottom_tightening.bind_bottom_tightening_dependencies(
        {
            "_bottom_arrangement_to_shared_updates": arrangement_to_updates,
            "_build_auto_design_context": lambda state, mode_config, **kwargs: {
                "state": dict(state),
                "mode_config": dict(mode_config),
            },
            "_candidate_debug_summary": lambda candidate: {
                "Ast_bot": candidate.get("Ast_bot"),
                "label": candidate.get("label"),
            },
            "_design_mode_config": lambda goal: {"goal": goal},
            "_design_optimisation_goal": lambda state: str((state or {}).get("goal") or "efficient"),
            "_effective_bottom_design_state": lambda state: {
                "Ast_bot": case.get("current_ast", state.get("Ast_bot", 0.0))
            },
            "_evaluate_candidate_fast": evaluate_fast,
            "_generate_local_bottom_arrangements": lambda state, mode_config, **kwargs: list(arrangements),
            "_guidance_state_snapshot": lambda state: dict(state or {}),
            "_practical_bottom_reo_label": lambda n1, n2, dia: f"{n1}+{n2} N{dia}",
            "_resolved_efficiency_target_band": lambda mode_config, **kwargs: (
                case.get("target_lo", 0.82),
                case.get("target_hi", 0.92),
                False,
            ),
            "evaluate_candidate_full": lambda state, **kwargs: None
            if case.get("no_seed")
            else {"state": dict(state), "overview": {"utils": {"bending": 0.95}}},
        }
    )


def _case_results() -> list[dict[str, Any]]:
    cases = [
        {
            "name": "no_current_ast_returns_none",
            "state": {"Ast_bot": 0.0},
            "current_ast": 0.0,
            "expected_none": True,
        },
        {
            "name": "no_seed_returns_none",
            "state": {"Ast_bot": 1000.0},
            "current_ast": 1000.0,
            "no_seed": True,
            "expected_none": True,
        },
        {
            "name": "filters_noncompliant_and_nonreducing_candidates",
            "state": {"Ast_bot": 1000.0},
            "current_ast": 1000.0,
            "arrangements": [
                {"bot1_count": 1, "bot2_count": 0, "db_bot_1": 16},
                {"bot1_count": 2, "bot2_count": 0, "db_bot_1": 16},
                {"bot1_count": 3, "bot2_count": 0, "db_bot_1": 16},
            ],
            "candidate_by_id": {
                1: {"is_compliant": False, "Ast_bot": 700.0, "bending": 0.86, "score": 1.0},
                2: {"is_compliant": True, "Ast_bot": 1000.0, "bending": 0.86, "score": 2.0},
                3: {"is_compliant": True, "Ast_bot": 850.0, "bending": 0.90, "score": 3.0},
            },
            "expected_updates": {"bot1_count": 3, "bot2_count": 0, "db_bot_1": 16},
            "expected_util": 0.90,
        },
        {
            "name": "prefers_in_band_closest_to_target_mid_then_rows_bars_ast",
            "state": {"Ast_bot": 1200.0},
            "current_ast": 1200.0,
            "target_lo": 0.80,
            "target_hi": 0.90,
            "arrangements": [
                {"bot1_count": 4, "bot2_count": 0, "db_bot_1": 16},
                {"bot1_count": 5, "bot2_count": 0, "db_bot_1": 16},
                {"bot1_count": 6, "bot2_count": 0, "db_bot_1": 16},
            ],
            "candidate_by_id": {
                4: {
                    "is_compliant": True,
                    "Ast_bot": 900.0,
                    "bending": 0.78,
                    "score": 4.0,
                    "row_count": 1,
                    "bar_count": 4,
                },
                5: {
                    "is_compliant": True,
                    "Ast_bot": 950.0,
                    "bending": 0.84,
                    "score": 5.0,
                    "row_count": 2,
                    "bar_count": 5,
                },
                6: {
                    "is_compliant": True,
                    "Ast_bot": 1000.0,
                    "bending": 0.88,
                    "score": 6.0,
                    "row_count": 1,
                    "bar_count": 6,
                },
            },
            "expected_updates": {"bot1_count": 5, "bot2_count": 0, "db_bot_1": 16},
            "expected_util": 0.84,
        },
    ]
    results: list[dict[str, Any]] = []
    for case in cases:
        _bind(case)
        result = bottom_tightening._compute_bottom_reo_tightening_recommendation(dict(case.get("state") or {}))
        if case.get("expected_none"):
            passed = result is None
        else:
            passed = isinstance(result, dict)
            passed = passed and result.get("updates") == case.get("expected_updates")
            passed = passed and abs(float(result.get("util", 0.0)) - float(case.get("expected_util"))) < 1e-9
            passed = passed and result.get("candidate_type") == "bottom"
        results.append(
            {
                "name": case["name"],
                "passed": passed,
                "result": result,
            }
        )
    return results


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Bottom Tightening Extraction",
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
    bridge_helper = _function_source(bridge_source, "_compute_bottom_reo_tightening_recommendation")
    module_helper = _function_source(module_source, "_compute_bottom_reo_tightening_recommendation")
    cases = _case_results()
    checks = {
        "module_exists": MODULE.exists(),
        "bridge_imports_extracted_helper": "_compute_bottom_reo_tightening_recommendation_extracted" in bridge_source,
        "bridge_helper_is_thin_delegate": len(bridge_helper.splitlines()) <= 5,
        "bridge_binds_bottom_tightening_dependencies": "_bind_bottom_tightening_dependencies(globals())" in bridge_helper,
        "bridge_delegates_to_extracted": "_compute_bottom_reo_tightening_recommendation_extracted(state)" in bridge_helper,
        "bridge_removed_tightening_body": "guidance_bottom_tighten" not in bridge_helper,
        "module_keeps_tightening_body": "guidance_bottom_tighten" in module_helper,
        "all_cases_pass": all(row["passed"] for row in cases),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in cases if not row["passed"])
    decision = "INPUTS_PAGE_BOTTOM_TIGHTENING_EXTRACTION_LOCKED" if not failures else "GAPS_REMAIN"
    payload = {
        "audit": "inputs_page_bottom_tightening_extraction",
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
    json_path = VERIFICATION_DIR / f"inputs_page_bottom_tightening_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_bottom_tightening_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_bottom_tightening_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
