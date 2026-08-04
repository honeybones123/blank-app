"""Verify final-tightening pass extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "auto_design_solver.py"
ARTIFACTS = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def _run_module_scenario(name: str) -> dict[str, Any]:
    from inputs_page_modules.app_bridge import auto_design_solver as extracted

    initial = {"id": "initial", "state": {"D": 600}, "score": 10.0}
    seed = {"id": "seed", "state": {"D": 600}, "score": 10.0}
    metrics: dict[str, Any] = {"_reference_overview": {"ref": True}}
    calls: dict[str, Any] = {"generated": [], "evaluated": []}

    if name == "cap_hit":
        metrics["cap_hit"] = True

    max_iters = 2 if name == "iteration_cap" else 4
    sequence: dict[str, list[dict[str, Any]]] = {
        "no_neighbours": [],
        "worsens_filtered": [{"id": "worse", "state": {"D": 610}, "worse": True, "score": 9.0}],
        "next_none": [{"id": "candidate", "state": {"D": 610}, "score": 8.0}],
        "not_meaningfully_better": [{"id": "candidate", "state": {"D": 610}, "score": 8.0}],
        "reached_target_zone": [{"id": "candidate", "state": {"D": 610}, "score": 8.0, "good": True}],
    }

    def _build_context(state: dict, mode_config: dict, *, reference_overview: dict | None = None) -> dict:
        return {"state": dict(state), "mode": dict(mode_config), "reference_overview": reference_overview}

    def _ensure_score(candidate: dict, mode_config: dict, seed_candidate: dict) -> None:
        candidate.setdefault("score", 0.0)

    def _generate(current: dict, mode_config: dict, context: dict, *, search_band: int, is_first_hop: bool) -> list[dict]:
        calls["generated"].append(
            {
                "current": current.get("id"),
                "search_band": search_band,
                "is_first_hop": is_first_hop,
            }
        )
        if name == "cap_hit":
            return [{"id": "unused", "state": {}, "score": 100.0}]
        if name == "iteration_cap":
            idx = len(calls["generated"])
            return [{"id": f"candidate_{idx}", "state": {"D": 600 + idx}, "score": 10.0 - idx}]
        return [dict(item) for item in sequence.get(name, [])]

    def _evaluate(candidate_state: dict, **kwargs: Any) -> dict | None:
        calls["evaluated"].append(dict(candidate_state))
        return dict(candidate_state)

    def _worsens(candidate: dict, current: dict, mode_config: dict, *, phase: str) -> bool:
        return bool(candidate.get("worse"))

    def _keep_top(candidates: list[dict], mode_config: dict, *, limit: int) -> list[dict]:
        return list(candidates)[:limit]

    def _select_next(current: dict, candidates: list[dict], mode_config: dict, *, phase: str) -> dict | None:
        if name == "next_none":
            return None
        return candidates[0] if candidates else None

    def _select_final(results: list[dict], mode_config: dict, baseline_candidate: dict | None = None) -> dict | None:
        candidates = [candidate for candidate in results if isinstance(candidate, dict)]
        return min(candidates, key=lambda candidate: float(candidate.get("score", 0.0) or 0.0)) if candidates else None

    def _meaningfully_better(new_result: dict, old_result: dict, mode_config: dict) -> bool:
        return name != "not_meaningfully_better"

    def _good_enough(candidate: dict, mode_config: dict, reference_candidate: dict | None = None) -> bool:
        return bool(candidate.get("good"))

    extracted.bind_auto_design_solver_dependencies(
        {
            "AUTO_DESIGN_MAX_KEPT_RESULTS": 5,
            "AUTO_DESIGN_MAX_TIGHTENING_ITERS": max_iters,
            "_build_auto_design_context": _build_context,
            "_ensure_candidate_score": _ensure_score,
            "_evaluate_candidate_fast": _evaluate,
            "_keep_top_candidates": _keep_top,
            "candidate_materially_worsens": _worsens,
            "candidate_is_good_enough": _good_enough,
            "generate_local_improvement_candidates": _generate,
            "is_meaningfully_better": _meaningfully_better,
            "select_best_next_hop_candidate": _select_next,
            "select_final_candidate": _select_final,
        }
    )

    returned = extracted.run_final_tightening_pass(
        initial,
        {"mode": "balanced"},
        seed_candidate=seed,
        eval_cache={},
        metrics=metrics,
        is_first_hop=True,
    )
    return {
        "returned_id": returned.get("id"),
        "stop_reason": metrics.get("tightening_stop_reason"),
        "iterations": metrics.get("tightening_iterations"),
        "generated": calls["generated"],
        "evaluated": calls["evaluated"],
    }


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    bridge_node = _function_node(bridge_source, "run_final_tightening_pass")
    module_node = _function_node(module_source, "run_final_tightening_pass")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    dependency_section = module_source.partition("def bind_auto_design_solver_dependencies")[0]

    scenarios = {name: _run_module_scenario(name) for name in (
        "cap_hit",
        "no_neighbours",
        "worsens_filtered",
        "next_none",
        "not_meaningfully_better",
        "reached_target_zone",
        "iteration_cap",
    )}

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import auto_design_solver as extracted

    original = bridge._run_final_tightening_pass_extracted
    delegate_call: dict[str, Any] = {}

    def _fake_extracted(
        initial_candidate: dict,
        mode_config: dict,
        *,
        seed_candidate: dict,
        eval_cache: dict,
        metrics: dict,
        is_first_hop: bool = False,
    ) -> dict:
        delegate_call.update(
            {
                "initial": dict(initial_candidate),
                "mode": dict(mode_config),
                "seed": dict(seed_candidate),
                "eval_cache": eval_cache,
                "metrics": metrics,
                "is_first_hop": bool(is_first_hop),
                "module_owner": extracted.run_final_tightening_pass is original,
            }
        )
        return {"id": "delegated"}

    try:
        bridge._run_final_tightening_pass_extracted = _fake_extracted
        returned = bridge.run_final_tightening_pass(
            {"id": "initial", "state": {"D": 600}},
            {"mode": "balanced"},
            seed_candidate={"id": "seed", "state": {"D": 600}},
            eval_cache={},
            metrics={},
            is_first_hop=True,
        )
    finally:
        bridge._run_final_tightening_pass_extracted = original

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 18,
        "bridge_binds_dependencies": "_bind_auto_design_solver_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_run_final_tightening_pass_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 60,
        "module_dependency_list_no_longer_binds_tightening": '"run_final_tightening_pass"' not in dependency_section,
        "module_has_needed_low_level_dependencies": all(
            token in dependency_section
            for token in (
                '"AUTO_DESIGN_MAX_KEPT_RESULTS"',
                '"generate_local_improvement_candidates"',
                '"select_best_next_hop_candidate"',
                '"is_meaningfully_better"',
            )
        ),
        "cap_hit_stop_reason": scenarios["cap_hit"]["stop_reason"] == "evaluation_cap_hit",
        "no_neighbours_stop_reason": scenarios["no_neighbours"]["stop_reason"] == "no_more_candidates",
        "worsens_filtered_stop_reason": scenarios["worsens_filtered"]["stop_reason"] == "no_more_candidates",
        "next_none_stop_reason": scenarios["next_none"]["stop_reason"] == "no_meaningful_candidate",
        "not_meaningfully_better_stop_reason": scenarios["not_meaningfully_better"]["stop_reason"] == "no_meaningful_improvement",
        "reached_target_zone_stop_reason": scenarios["reached_target_zone"]["stop_reason"] == "reached_target_zone",
        "iteration_cap_stop_reason": scenarios["iteration_cap"]["stop_reason"] == "iteration_cap_hit",
        "first_hop_search_band_preserved": scenarios["reached_target_zone"]["generated"][0] == {
            "current": "initial",
            "search_band": 1,
            "is_first_hop": True,
        },
        "bridge_runtime_delegates": returned == {"id": "delegated"} and delegate_call.get("is_first_hop") is True,
        "bridge_runtime_preserves_module_owner": delegate_call.get("module_owner") is True,
    }

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "scenarios": scenarios,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_final_tightening_pass_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_final_tightening_pass_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Final Tightening Pass Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                "",
                "## Checks",
                "",
                *[f"- {check}: {'PASS' if passed else 'FAIL'}" for check, passed in checks.items()],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(result["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
