"""Verify one-click solver candidate collection state coordinator extraction."""

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


def _base_kwargs() -> dict[str, Any]:
    return {
        "working": {"D": 650},
        "debug_enabled": True,
        "trace_run_id": "run-1",
        "step_idx": 2,
        "tightening_mode_active": False,
        "governing_domain_failing": False,
        "required_domain_work_active": False,
        "target_band_domain": "bending",
        "cur_shear_failing": False,
        "governing_domain": "bending",
        "cur_ib": True,
        "cur_eval": {"overview": {}},
        "mode_config": {"mode": "probe"},
        "tightening_step_count": 3,
        "tightening_meta": {"candidate_families_considered": ["existing"]},
        "candidate_family_depth_reached": "none",
        "shear_governing_mode_active": False,
        "shear_severity_band": "mild",
        "shear_candidate_family_order": ["old"],
        "spacing_candidates_considered": 1,
        "leg_candidates_considered": 2,
        "dia_candidates_considered": 3,
        "geometry_candidates_considered_for_shear": 4,
        "combined_candidates_considered_for_shear": 5,
    }


def _run_cases(module: Any) -> dict[str, Any]:
    originals = {
        "_one_click_collect_actionable_guidance_candidates": getattr(
            module,
            "_one_click_collect_actionable_guidance_candidates",
            None,
        ),
        "_generate_tightening_candidates_for_governing_domain": getattr(
            module,
            "_generate_tightening_candidates_for_governing_domain",
            None,
        ),
    }
    calls: list[dict[str, Any]] = []

    try:
        def _collect(working: dict, *, debug_enabled: bool, trace_run_id: str | None, trace_step: int):
            calls.append(
                {
                    "collect": {
                        "working": dict(working),
                        "debug_enabled": debug_enabled,
                        "trace_run_id": trace_run_id,
                        "trace_step": trace_step,
                    }
                }
            )
            return [{"label": "base"}], 1

        def _generate(working: dict, cur_eval: dict, mode_config: dict, *, tightening_step_count: int):
            calls.append(
                {
                    "generate": {
                        "working": dict(working),
                        "mode_config": dict(mode_config),
                        "tightening_step_count": tightening_step_count,
                    }
                }
            )
            return [{"label": "tight"}], {
                "candidate_family_depth_reached": "combined",
                "shear_governing_mode_active": True,
                "shear_severity_band": "severe",
                "shear_candidate_family_order": ["spacing", "legs"],
                "spacing_candidates_considered": 10,
                "leg_candidates_considered": 11,
                "dia_candidates_considered": 12,
                "geometry_candidates_considered_for_shear": 13,
                "combined_candidates_considered_for_shear": 14,
                "candidate_families_considered": ["spacing"],
                "candidate_families_pruned": ["bottom"],
            }

        module._one_click_collect_actionable_guidance_candidates = _collect
        module._generate_tightening_candidates_for_governing_domain = _generate

        gov_kwargs = _base_kwargs()
        gov_kwargs["required_domain_work_active"] = True
        governing = module._prepare_one_click_solver_candidate_collection_state_coordinator(**gov_kwargs)

        plain_kwargs = _base_kwargs()
        plain = module._prepare_one_click_solver_candidate_collection_state_coordinator(**plain_kwargs)
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {"governing": governing, "plain": plain, "calls": calls}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_collection_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    candidate_pipeline_start, candidate_pipeline_end, candidate_pipeline_body = _function_segment(
        source, "_prepare_one_click_solver_candidate_pipeline_state_coordinator"
    )
    _, _, after_collection_body = _function_segment(
        source,
        "_run_one_click_solver_candidate_pipeline_after_collection_coordinator",
    )
    _, _, candidate_pipeline_collection_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_collection_state_from_candidate_pipeline_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    governing = runtime["governing"]
    plain = runtime["plain"]
    runtime_checks = {
        "governing_candidate_injection_preserved": governing["use_governing_domain_candidates"] is True
        and governing["raw_candidates"] == [{"label": "tight"}, {"label": "base"}]
        and governing["raw_n"] == 2
        and governing["candidate_family_depth_reached"] == "combined"
        and governing["shear_governing_mode_active"] is True
        and governing["shear_severity_band"] == "severe"
        and governing["shear_candidate_family_order"] == ["spacing", "legs"]
        and governing["spacing_candidates_considered"] == 10
        and governing["leg_candidates_considered"] == 11
        and governing["dia_candidates_considered"] == 12
        and governing["geometry_candidates_considered_for_shear"] == 13
        and governing["combined_candidates_considered_for_shear"] == 14,
        "plain_candidate_collection_preserved": plain["use_governing_domain_candidates"] is False
        and plain["raw_candidates"] == [{"label": "base"}]
        and plain["raw_n"] == 1
        and plain["tightening_meta"] == {"candidate_families_considered": ["existing"]}
        and plain["candidate_family_depth_reached"] == "none"
        and plain["shear_governing_mode_active"] is False
        and plain["shear_severity_band"] == "mild"
        and plain["shear_candidate_family_order"] == ["old"]
        and plain["spacing_candidates_considered"] == 1
        and plain["combined_candidates_considered_for_shear"] == 5,
        "call_order_preserved": runtime["calls"] == [
            {
                "collect": {
                    "working": {"D": 650},
                    "debug_enabled": True,
                    "trace_run_id": "run-1",
                    "trace_step": 2,
                }
            },
            {
                "generate": {
                    "working": {"D": 650},
                    "mode_config": {"mode": "probe"},
                    "tightening_step_count": 3,
                }
            },
            {
                "collect": {
                    "working": {"D": 650},
                    "debug_enabled": True,
                    "trace_run_id": "run-1",
                    "trace_step": 2,
                }
            },
        ],
    }
    static_checks = {
        "pipeline_delegates_candidate_collection_state": (
            "_dispatch_one_click_solver_candidate_collection_state_from_candidate_pipeline_coordinator("
            in candidate_pipeline_body
            and "_prepare_one_click_solver_candidate_collection_state_coordinator("
            in candidate_pipeline_collection_dispatch
            and "candidate_pipeline_scope[" in candidate_pipeline_collection_dispatch
        ),
        "helper_present": "def _prepare_one_click_solver_candidate_collection_state_coordinator(" in source,
        "helper_preserves_raw_collection": "_one_click_collect_actionable_guidance_candidates(" in helper
        and "debug_enabled=debug_enabled" in helper
        and "trace_run_id=trace_run_id" in helper
        and "trace_step=step_idx" in helper,
        "helper_preserves_governing_gate": "use_governing_domain_candidates = bool(" in helper
        and "tightening_mode_active" in helper
        and "governing_domain_failing" in helper
        and "required_domain_work_active" in helper,
        "helper_preserves_shear_gate": 'target_band_domain == "shear"' in helper
        and "cur_shear_failing" in helper
        and "not cur_ib" in helper,
        "helper_preserves_tightening_generation": "_generate_tightening_candidates_for_governing_domain(" in helper
        and "tightening_step_count=tightening_step_count" in helper,
        "helper_preserves_raw_count_update": "raw_candidates = tightening_domain_candidates + list(raw_candidates or [])"
        in helper
        and "raw_n = int(raw_n) + len(tightening_domain_candidates)" in helper,
        "helper_preserves_shear_metadata": "candidate_family_depth_reached" in helper
        and "shear_candidate_family_order" in helper
        and "combined_candidates_considered_for_shear" in helper,
        "solver_rehydrates_candidate_collection_fields": (
            "candidate_pipeline_after_collection_scope.update(" in after_collection_body
            and '"raw_candidates"' in after_collection_body
            and '"use_governing_domain_candidates"' in after_collection_body
            and '"combined_candidates_considered_for_shear"' in after_collection_body
        ),
        "solver_no_longer_inlines_candidate_collection_state": "_one_click_collect_actionable_guidance_candidates(\n            working,"
        not in solve_body
        and "_generate_tightening_candidates_for_governing_domain(\n                working," not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_collection_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_candidate_collection_state_coordinator",
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
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract prepared-candidate state rehydration and initial rejection counters",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_candidate_collection_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_candidate_collection_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Collection State Coordinator Extraction",
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
