"""Verify one-click solver initial eval state coordinator extraction."""

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

AUTO_DESIGN_COMPUTE = ROOT / "inputs_page_modules" / "auto_design_compute.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _run_normal_case(module: Any) -> dict[str, Any]:
    originals = {
        "BEAM_STATUS_FAIL": getattr(module, "BEAM_STATUS_FAIL", None),
        "_build_canonical_design_state_pack": getattr(module, "_build_canonical_design_state_pack", None),
        "evaluate_candidate_full": getattr(module, "evaluate_candidate_full", None),
        "_governing_focus_from_overview": getattr(module, "_governing_focus_from_overview", None),
        "_one_click_seed_target_domains_from_eval": getattr(module, "_one_click_seed_target_domains_from_eval", None),
        "_one_click_target_domains_for_eval": getattr(module, "_one_click_target_domains_for_eval", None),
        "_one_click_attach_eval_target_domains": getattr(module, "_one_click_attach_eval_target_domains", None),
        "_candidate_in_target_band": getattr(module, "_candidate_in_target_band", None),
        "_one_click_required_domain_progress": getattr(module, "_one_click_required_domain_progress", None),
        "_trace_initial_solver_eval_coordinator": getattr(module, "_trace_initial_solver_eval_coordinator", None),
    }
    calls: list[dict[str, Any]] = []
    init_eval = {
        "overview": {
            "statuses": {"shear": "FAIL"},
            "worst_util": 0.88,
            "all_key_pass": True,
        }
    }

    try:
        module.BEAM_STATUS_FAIL = "FAIL"
        module._build_canonical_design_state_pack = lambda working: {"pack": dict(working)}

        def _eval(pack: dict, **kwargs: Any) -> dict[str, Any]:
            calls.append({"evaluate": {"pack": pack, "kwargs": dict(kwargs)}})
            return init_eval

        def _attach(eval_obj: dict, domains: list[str], mode_config: dict) -> None:
            calls.append({"attach": {"domains": list(domains), "mode_config": dict(mode_config)}})

        def _trace(**kwargs: Any) -> None:
            calls.append(
                {
                    "trace": {
                        "init_eval_same_object": kwargs.get("init_eval") is init_eval,
                        "init_worst": kwargs.get("init_worst"),
                        "init_in_band": kwargs.get("init_in_band"),
                        "init_pass": kwargs.get("init_pass"),
                        "working": dict(kwargs.get("working") or {}),
                    }
                }
            )

        module.evaluate_candidate_full = _eval
        module._governing_focus_from_overview = lambda overview: "shear"
        module._one_click_seed_target_domains_from_eval = lambda eval_obj, mode_config: []
        module._one_click_target_domains_for_eval = lambda domains, updates: []
        module._one_click_attach_eval_target_domains = _attach
        module._candidate_in_target_band = lambda eval_obj, mode_config: True
        module._one_click_required_domain_progress = lambda eval_obj, mode_config: {"required_fail_count": 0}
        module._trace_initial_solver_eval_coordinator = _trace
        result = module._prepare_one_click_solver_initial_eval_state_coordinator(
            working={"D": 650},
            mode_config={"mode": "probe"},
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {"result": result, "calls": calls}


def _run_none_case(module: Any) -> dict[str, Any]:
    originals = {
        "_build_canonical_design_state_pack": getattr(module, "_build_canonical_design_state_pack", None),
        "evaluate_candidate_full": getattr(module, "evaluate_candidate_full", None),
    }
    try:
        module._build_canonical_design_state_pack = lambda working: {"pack": dict(working)}
        module.evaluate_candidate_full = lambda *_args, **_kwargs: None
        result = module._prepare_one_click_solver_initial_eval_state_coordinator(
            working={"D": 650},
            mode_config={"mode": "probe"},
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
    return result


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_initial_eval_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    runtime_setup_start, runtime_setup_end, runtime_setup_body = _function_segment(
        source, "_prepare_one_click_solver_runtime_setup_state_coordinator"
    )
    _, _, after_mode_budget_body = _function_segment(
        source,
        "_prepare_one_click_solver_runtime_setup_after_mode_budget_state_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    normal = _run_normal_case(module)
    none_case = _run_none_case(module)
    result = normal["result"]
    runtime_checks = {
        "seed_evaluation_call_preserved": normal["calls"][0] == {
            "evaluate": {
                "pack": {"pack": {"D": 650}},
                "kwargs": {
                    "source": "one_click_solve_seed",
                    "label": "Seed",
                    "action_type": "one_click",
                    "updates": {},
                },
            }
        },
        "target_domain_attachment_preserved": normal["calls"][1] == {
            "attach": {"domains": [], "mode_config": {"mode": "probe"}}
        }
        and result["init_eval"]["target_domain_for_band"] == "shear",
        "initial_eval_values_preserved": result["target_band_domain"] == "shear"
        and result["initial_statuses"] == {"shear": "FAIL"}
        and result["target_domains_for_band"] == []
        and result["init_worst"] == 0.88
        and result["init_pass"] is True
        and result["init_in_band"] is True
        and result["init_progress"] == {"required_fail_count": 0},
        "initial_trace_delegation_preserved": normal["calls"][2] == {
            "trace": {
                "init_eval_same_object": True,
                "init_worst": 0.88,
                "init_in_band": True,
                "init_pass": True,
                "working": {"D": 650},
            }
        },
        "none_eval_path_preserved": none_case == {"init_eval": None},
    }
    static_checks = {
        "solver_delegates_runtime_setup_state": (
            "_prepare_one_click_solver_runtime_setup_state_coordinator(" in solve_body
        ),
        "helper_present": "def _prepare_one_click_solver_initial_eval_state_coordinator(" in source,
        "helper_preserves_seed_evaluation": "evaluate_candidate_full(" in helper
        and 'source="one_click_solve_seed"' in helper
        and 'label="Seed"' in helper
        and 'action_type="one_click"' in helper
        and "updates={}" in helper,
        "helper_preserves_none_path": 'return {"init_eval": None}' in helper,
        "helper_preserves_target_domain_setup": "_governing_focus_from_overview" in helper
        and "_one_click_seed_target_domains_from_eval" in helper
        and "_one_click_target_domains_for_eval" in helper
        and "_one_click_attach_eval_target_domains" in helper,
        "helper_preserves_shear_fallback": "target_band_domain == \"shear\"" in helper
        and "BEAM_STATUS_FAIL" in helper
        and 'init_eval["target_domain_for_band"] = "shear"' in helper,
        "helper_preserves_initial_values": "_candidate_in_target_band(init_eval, mode_config)" in helper
        and "_one_click_required_domain_progress(init_eval, mode_config)" in helper,
        "helper_preserves_trace_call": "_trace_initial_solver_eval_coordinator(" in helper,
        "solver_delegates_initial_eval_state": "_prepare_one_click_solver_initial_eval_state_coordinator("
        in after_mode_budget_body,
        "solver_preserves_failed_eval_return": "_build_evaluate_failed_solver_return_coordinator("
        in after_mode_budget_body,
        "solver_rehydrates_initial_eval_state_fields": (
            'init_eval = solver_initial_eval_state["init_eval"]'
            in after_mode_budget_body
            and '"target_band_domain": solver_initial_eval_state["target_band_domain"]'
            in after_mode_budget_body
            and '"init_progress": solver_initial_eval_state["init_progress"]'
            in after_mode_budget_body
        ),
        "solver_no_longer_inlines_seed_evaluation": 'source="one_click_solve_seed"' not in solve_body
        and "_one_click_seed_target_domains_from_eval(init_eval, mode_config)" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_initial_eval_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_initial_eval_state_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "solver_segment": {
            "function": "_solve_one_click_to_target",
            "start_line": solve_start,
            "end_line": solve_end,
            "line_count": solve_end - solve_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "runtime": {"normal": normal, "none_case": none_case},
        "product_behavior_changed": False,
        "next_safe_slice": "extract early in-band tightening/cleanup gate setup",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_initial_eval_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_initial_eval_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Initial Eval State Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Runtime Checks")
    for key, value in payload["runtime_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"])])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
