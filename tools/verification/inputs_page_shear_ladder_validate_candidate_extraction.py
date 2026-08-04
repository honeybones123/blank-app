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

from inputs_page_modules import recommendation_compute


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "recommendation_compute.py"
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


class _Legacy:
    def __getattr__(self, name: str) -> Any:
        mapping = {
            "_float_from_state": self._float_from_state,
            "_int_from_state": self._int_from_state,
            "_shear_detailing_updates_pure": self._shear_detailing_updates_pure,
            "_shear_no_links_candidate_passes_code": lambda state, candidate: bool(
                (candidate or {}).get("no_links_code_ok", True)
            ),
            "_shear_state_eligible_for_no_links": lambda state: bool(
                (state or {}).get("no_links_eligible", True)
            ),
            "_updates_match_state": self._updates_match_state,
            "math": math,
        }
        if name in mapping:
            return mapping[name]
        return lambda *args, **kwargs: None

    @staticmethod
    def _float_from_state(state: dict, key: str, default: float) -> float:
        try:
            return float((state or {}).get(key, default))
        except Exception:
            return float(default)

    @staticmethod
    def _int_from_state(state: dict, key: str, default: int) -> int:
        try:
            return int((state or {}).get(key, default))
        except Exception:
            return int(default)

    @staticmethod
    def _updates_match_state(state: dict, updates: dict) -> bool:
        return all((state or {}).get(key) == value for key, value in dict(updates or {}).items())

    @staticmethod
    def _shear_detailing_updates_pure(updates: dict | None) -> tuple[bool, tuple[str, ...]]:
        allowed = {"lig_d", "lig_legs", "s_lig"}
        bad = tuple(sorted(str(key) for key in dict(updates or {}) if key not in allowed))
        return not bad, bad


def _runtime() -> recommendation_compute.ShearRecommendationRuntime:
    legacy = _Legacy()
    from inputs_application.auto_design_scoring_runtime import (
        build_auto_design_scoring_runtime,
    )

    evaluation = recommendation_compute.RecommendationEvaluationRuntime(
        build_design_actions_context=lambda state: {},
        collect_design_overview=lambda state, context=None: {},
        combined_shear_truth_gate=lambda state, **kwargs: {},
        evaluate_candidate_fast=lambda state, **kwargs: None,
        evaluate_candidate_full=lambda state, **kwargs: None,
    )
    trace = recommendation_compute.RecommendationTraceRuntime(
        agent_debug_log=lambda *args, **kwargs: None,
        active_recommendation_trace=None,
        append_recommendation_trace=lambda entry: None,
        candidate_debug_enabled=False,
        log_candidate_rank=lambda **kwargs: None,
        log_efficiency_growth_rejection=lambda **kwargs: None,
        merge_rank_trace=lambda entry: None,
    )
    return recommendation_compute.ShearRecommendationRuntime(
        **{
            name: (
                evaluation
                if name == "evaluation"
                else trace
                if name == "trace"
                else build_auto_design_scoring_runtime(
                    agent_debug_log=lambda *args, **kwargs: None
                )
                if name == "scoring"
                else getattr(legacy, name)
            )
            for name in recommendation_compute._SHEAR_RECOMMENDATION_NAMES
        }
    )


def _candidate(
    *,
    updates: dict,
    state: dict,
    shear_util: float | None = 0.8,
    compliant: bool = True,
    **extra: Any,
) -> dict:
    out = {
        "updates": dict(updates),
        "state": dict(state),
        "is_compliant": compliant,
        "overview": {"utils": {"shear": shear_util}},
    }
    out.update(extra)
    return out


def _case_results() -> list[dict[str, Any]]:
    runtime = _runtime()
    base_state = {"lig_legs": 2, "lig_d": 12, "s_lig": 200.0, "no_links_eligible": True}
    cases = [
        {
            "name": "none_candidate_rejected",
            "result": recommendation_compute._shear_ladder_validate_candidate(
                base_state,
                None,
                branch="spacing_tighter",
                conservative=False,
                baseline_shear_util=1.0,
                runtime=runtime,
            ),
            "expected": (False, "eval_none"),
        },
        {
            "name": "empty_updates_rejected",
            "result": recommendation_compute._shear_ladder_validate_candidate(
                base_state,
                _candidate(updates={}, state=base_state),
                branch="spacing_tighter",
                conservative=False,
                baseline_shear_util=1.0,
                runtime=runtime,
            ),
            "expected": (False, "empty_updates"),
        },
        {
            "name": "conservative_non_shear_update_rejected",
            "result": recommendation_compute._shear_ladder_validate_candidate(
                base_state,
                _candidate(updates={"D": 650}, state={**base_state, "D": 650}),
                branch="spacing_looser",
                conservative=True,
                baseline_shear_util=None,
                runtime=runtime,
            ),
            "expected": (False, "non_shear_detailing_updates_in_conservative_shear_ladder"),
        },
        {
            "name": "conservative_no_links_accepted_when_code_passes",
            "result": recommendation_compute._shear_ladder_validate_candidate(
                base_state,
                _candidate(
                    updates={"lig_legs": 0},
                    state={**base_state, "lig_legs": 0},
                    no_links_code_ok=True,
                ),
                branch="no_ligs",
                conservative=True,
                baseline_shear_util=None,
                runtime=runtime,
            ),
            "expected": (True, "accepted"),
        },
        {
            "name": "failing_spacing_tighter_requires_improved_shear_util",
            "result": recommendation_compute._shear_ladder_validate_candidate(
                base_state,
                _candidate(
                    updates={"s_lig": 150.0},
                    state={**base_state, "s_lig": 150.0},
                    shear_util=0.85,
                ),
                branch="spacing_tighter",
                conservative=False,
                baseline_shear_util=1.0,
                runtime=runtime,
            ),
            "expected": (True, "accepted"),
        },
        {
            "name": "failing_branch_rejects_unimproved_shear_util",
            "result": recommendation_compute._shear_ladder_validate_candidate(
                base_state,
                _candidate(
                    updates={"s_lig": 150.0},
                    state={**base_state, "s_lig": 150.0},
                    shear_util=1.0,
                ),
                branch="spacing_tighter",
                conservative=False,
                baseline_shear_util=1.0,
                runtime=runtime,
            ),
            "expected": (False, "shear_util_not_improved"),
        },
    ]
    return [
        {
            "name": case["name"],
            "passed": case["result"] == case["expected"],
            "result": case["result"],
            "expected": case["expected"],
        }
        for case in cases
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Shear Ladder Validate Candidate Extraction",
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
    bridge_helper = _function_source(bridge_source, "_shear_ladder_validate_candidate")
    module_helper = _function_source(module_source, "_shear_ladder_validate_candidate")
    cases = _case_results()
    checks = {
        "module_owns_validator_body": "non_shear_detailing_updates_in_conservative_shear_ladder" in module_helper
        and "shear_util_not_improved" in module_helper,
        "bridge_imports_extracted_validator": "_shear_ladder_validate_candidate_extracted" in bridge_source,
        "bridge_helper_is_delegate": len(bridge_helper.splitlines()) <= 19,
        "bridge_supplies_typed_recommendation_runtime": (
            "runtime=_build_shear_recommendation_runtime()" in bridge_helper
            and "_bind_named_recommendation_globals(" not in bridge_helper
        ),
        "bridge_delegates_to_extracted": "_shear_ladder_validate_candidate_extracted(" in bridge_helper,
        "bridge_removed_validator_body": "shear_util_not_improved" not in bridge_helper
        and "non_shear_detailing_updates_in_conservative_shear_ladder" not in bridge_helper,
        "recommendation_module_no_longer_depends_on_bridge_validator": (
            "'_shear_ladder_validate_candidate'" not in module_source.split(
                "def _bind_named_recommendation_globals", 1
            )[0]
        ),
        "recommendation_module_types_lower_level_validator_dependencies": (
            "shear_no_links_candidate_passes_code as _shear_no_links_candidate_passes_code"
            in module_source
        )
        and "shear_state_eligible_for_no_links as _shear_state_eligible_for_no_links"
        in module_source
        and "updates_match_state as _updates_match_state" in module_source
        and "shear_detailing_updates_pure as _shear_detailing_updates_pure"
        in module_source
        and "runtime: ShearRecommendationRuntime" in module_helper,
        "all_cases_pass": all(row["passed"] for row in cases),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in cases if not row["passed"])
    decision = (
        "INPUTS_PAGE_SHEAR_LADDER_VALIDATE_CANDIDATE_EXTRACTION_LOCKED"
        if not failures
        else "GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_page_shear_ladder_validate_candidate_extraction",
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
    json_path = VERIFICATION_DIR / f"inputs_page_shear_ladder_validate_candidate_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_shear_ladder_validate_candidate_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_shear_ladder_validate_candidate_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
