"""Verify one-click solver early in-band gate state coordinator extraction."""

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


def _run_cases(module: Any) -> dict[str, Any]:
    originals = {
        "compute_efficiency_tightening_state": getattr(module, "compute_efficiency_tightening_state", None),
        "_updates_match_state": getattr(module, "_updates_match_state", None),
        "_one_click_in_band_shear_cleanup_deferral": getattr(
            module,
            "_one_click_in_band_shear_cleanup_deferral",
            None,
        ),
    }
    calls: list[dict[str, Any]] = []

    try:
        module._updates_match_state = lambda working, updates: bool(updates.get("same"))

        module.compute_efficiency_tightening_state = lambda working: {
            "classification": "inefficient",
            "mode_tightening": {"updates": {"same": True}},
            "bottom_tightening": {"updates": {"D": 700}},
            "shear_tightening": {"updates": {}},
            "geometry_tightening": None,
        }
        module._one_click_in_band_shear_cleanup_deferral = lambda working, init_eval, mode_config: {
            "active": False,
            "reason": "not_needed",
            "recommendation": None,
            "candidate_eval": None,
        }
        actionable = module._prepare_one_click_solver_early_in_band_gate_state_coordinator(
            working={"D": 650},
            init_eval={"overview": {}},
            mode_config={"mode": "probe"},
            init_pass=True,
            init_in_band=True,
        )

        module.compute_efficiency_tightening_state = lambda working: {
            "classification": "balanced",
            "mode_tightening": {"updates": {}},
        }

        def _cleanup(working: dict, init_eval: dict, mode_config: dict) -> dict[str, Any]:
            calls.append({"cleanup": {"working": dict(working), "mode_config": dict(mode_config)}})
            return {
                "active": True,
                "reason": "blocked_non_governing_shear_cleanup_available",
                "recommendation": {"label": "shear cleanup"},
                "candidate_eval": {"overview": {}},
            }

        module._one_click_in_band_shear_cleanup_deferral = _cleanup
        cleanup_blocked = module._prepare_one_click_solver_early_in_band_gate_state_coordinator(
            working={"D": 650},
            init_eval={"overview": {}},
            mode_config={"mode": "probe"},
            init_pass=True,
            init_in_band=True,
        )

        module.compute_efficiency_tightening_state = lambda working: (_ for _ in ()).throw(RuntimeError("probe"))
        module._one_click_in_band_shear_cleanup_deferral = lambda *_args, **_kwargs: {
            "active": False,
            "reason": "not_called_for_seed",
            "recommendation": None,
            "candidate_eval": None,
        }
        seed_not_in_band = module._prepare_one_click_solver_early_in_band_gate_state_coordinator(
            working={"D": 650},
            init_eval={"overview": {}},
            mode_config={"mode": "probe"},
            init_pass=False,
            init_in_band=False,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {
        "actionable": actionable,
        "cleanup_blocked": cleanup_blocked,
        "seed_not_in_band": seed_not_in_band,
        "calls": calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_early_in_band_gate_state_coordinator",
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

    runtime = _run_cases(module)
    actionable = runtime["actionable"]
    cleanup_blocked = runtime["cleanup_blocked"]
    seed_not_in_band = runtime["seed_not_in_band"]
    runtime_checks = {
        "actionable_efficiency_tightening_blocks_exit": actionable[
            "early_in_band_exit_blocked_for_tightening"
        ]
        is True
        and actionable["early_in_band_exit_tightening_classification"] == "inefficient"
        and actionable["early_in_band_exit_available_tightening_paths"] == ["bottom_tightening"]
        and actionable["early_in_band_exit_reason"] == "blocked_actionable_efficiency_tightening_available"
        and actionable["should_return_already_in_band"] is False,
        "shear_cleanup_deferral_blocks_exit": cleanup_blocked[
            "early_in_band_exit_blocked_for_tightening"
        ]
        is True
        and cleanup_blocked["early_in_band_exit_available_tightening_paths"] == ["shear_tightening"]
        and cleanup_blocked["early_in_band_exit_reason"] == "blocked_non_governing_shear_cleanup_available"
        and cleanup_blocked["early_in_band_shear_cleanup_deferral"]["active"] is True
        and cleanup_blocked["should_return_already_in_band"] is False,
        "seed_not_in_band_defaults_preserved": seed_not_in_band[
            "early_in_band_exit_blocked_for_tightening"
        ]
        is False
        and seed_not_in_band["early_in_band_exit_tightening_classification"] == ""
        and seed_not_in_band["early_in_band_exit_available_tightening_paths"] == []
        and seed_not_in_band["early_in_band_exit_reason"] == "seed_not_in_band_or_not_passing"
        and seed_not_in_band["early_in_band_shear_cleanup_deferral"] == {
            "active": False,
            "reason": "not_evaluated",
            "recommendation": None,
            "candidate_eval": None,
        }
        and seed_not_in_band["should_return_already_in_band"] is False,
        "cleanup_call_arguments_preserved": runtime["calls"] == [
            {"cleanup": {"working": {"D": 650}, "mode_config": {"mode": "probe"}}}
        ],
    }
    static_checks = {
        "solver_delegates_runtime_setup_state": (
            "_prepare_one_click_solver_runtime_setup_state_coordinator(" in solve_body
        ),
        "helper_present": "def _prepare_one_click_solver_early_in_band_gate_state_coordinator(" in source,
        "helper_preserves_default_reason": '"seed_not_in_band_or_not_passing"' in helper,
        "helper_preserves_efficiency_probe": "compute_efficiency_tightening_state(working)" in helper
        and "except Exception" in helper,
        "helper_preserves_tightening_paths": all(
            token in helper
            for token in (
                '"mode_tightening"',
                '"bottom_tightening"',
                '"shear_tightening"',
                '"geometry_tightening"',
                "_updates_match_state(working, _updates)",
            )
        ),
        "helper_preserves_actionable_reason": '"blocked_actionable_efficiency_tightening_available"' in helper,
        "helper_preserves_cleanup_deferral": "_one_click_in_band_shear_cleanup_deferral(" in helper
        and '"blocked_non_governing_shear_cleanup_available"' in helper,
        "helper_preserves_already_in_band_gate": '"should_return_already_in_band"' in helper
        and "init_pass and init_in_band and not early_in_band_exit_blocked_for_tightening" in helper,
        "solver_delegates_early_gate": "_prepare_one_click_solver_early_in_band_gate_state_coordinator("
        in after_mode_budget_body,
        "solver_preserves_already_in_band_return": "_build_already_in_band_solver_return_coordinator("
        in after_mode_budget_body,
        "solver_no_longer_inlines_early_gate_probe": "compute_efficiency_tightening_state(working)" not in solve_body
        and "_one_click_in_band_shear_cleanup_deferral(\n            working,\n            init_eval,\n            mode_config,"
        not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_early_in_band_gate_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_early_in_band_gate_state_coordinator",
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
        "next_safe_slice": "extract solver iteration state initialization",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_early_in_band_gate_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_early_in_band_gate_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Early In-Band Gate State Coordinator Extraction",
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
