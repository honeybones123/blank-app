"""Verify one-click solver current target-domain state coordinator extraction."""

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


def _run_required_domain_case(module: Any) -> dict[str, Any]:
    originals = {
        "_one_click_diff_accumulated_updates": getattr(module, "_one_click_diff_accumulated_updates", None),
        "_one_click_target_domains_for_eval": getattr(module, "_one_click_target_domains_for_eval", None),
        "_one_click_attach_eval_target_domains": getattr(module, "_one_click_attach_eval_target_domains", None),
        "_candidate_in_target_band": getattr(module, "_candidate_in_target_band", None),
        "_one_click_domain_needs_cleanup": getattr(module, "_one_click_domain_needs_cleanup", None),
    }
    calls: list[dict[str, Any]] = []
    cur_eval = {"target_domain_for_band": "bending"}

    try:
        module._one_click_diff_accumulated_updates = lambda initial_snapshot, working: {
            "D": working.get("D") - initial_snapshot.get("D")
        }
        module._one_click_target_domains_for_eval = lambda domains, updates: ["bending"]

        def _attach(eval_obj: dict, domains: list[str], mode_config: dict) -> None:
            calls.append({"attach": {"domains": list(domains), "mode_config": dict(mode_config)}})

        module._one_click_attach_eval_target_domains = _attach
        module._candidate_in_target_band = lambda eval_obj, mode_config: False
        module._one_click_domain_needs_cleanup = lambda eval_obj, target_work_domain, mode_config: True
        result = module._prepare_one_click_solver_current_target_domain_state_coordinator(
            initial_snapshot={"D": 600},
            working={"D": 650},
            cur_eval=cur_eval,
            mode_config={"mode": "probe"},
            target_domains_for_band=("bending",),
            target_band_domain="bending",
            cur_shear_failing=False,
            cur_pass=False,
            governing_domain="crack",
            tightening_mode_active=False,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {"result": result, "calls": calls, "cur_eval": cur_eval}


def _run_shear_fallback_case(module: Any) -> dict[str, Any]:
    originals = {
        "_one_click_diff_accumulated_updates": getattr(module, "_one_click_diff_accumulated_updates", None),
        "_one_click_target_domains_for_eval": getattr(module, "_one_click_target_domains_for_eval", None),
        "_one_click_attach_eval_target_domains": getattr(module, "_one_click_attach_eval_target_domains", None),
        "_candidate_in_target_band": getattr(module, "_candidate_in_target_band", None),
        "_one_click_domain_needs_cleanup": getattr(module, "_one_click_domain_needs_cleanup", None),
    }
    cur_eval: dict[str, Any] = {}

    try:
        module._one_click_diff_accumulated_updates = lambda initial_snapshot, working: {}
        module._one_click_target_domains_for_eval = lambda domains, updates: []
        module._one_click_attach_eval_target_domains = lambda *_args, **_kwargs: None
        module._candidate_in_target_band = lambda eval_obj, mode_config: False
        module._one_click_domain_needs_cleanup = lambda *_args, **_kwargs: False
        result = module._prepare_one_click_solver_current_target_domain_state_coordinator(
            initial_snapshot={"D": 600},
            working={"D": 650},
            cur_eval=cur_eval,
            mode_config={"mode": "probe"},
            target_domains_for_band=(),
            target_band_domain="shear",
            cur_shear_failing=True,
            cur_pass=True,
            governing_domain="bending",
            tightening_mode_active=False,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {"result": result, "cur_eval": cur_eval}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_current_target_domain_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    iteration_gate_start, iteration_gate_end, iteration_gate_body = _function_segment(
        source, "_prepare_one_click_solver_iteration_gate_state_coordinator"
    )
    _, _, iteration_gate_after_current_eval_body = _function_segment(
        source,
        "_prepare_one_click_solver_iteration_gate_after_current_eval_state_coordinator",
    )
    _, _, current_target_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_current_target_domain_state_from_iteration_gate_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    required = _run_required_domain_case(module)
    shear = _run_shear_fallback_case(module)
    runtime_checks = {
        "required_domain_gate_preserved": required["result"]["step_accum"] == {"D": 50}
        and required["result"]["cur_target_domains"] == ["bending"]
        and required["calls"] == [{"attach": {"domains": ["bending"], "mode_config": {"mode": "probe"}}}]
        and required["result"]["cur_ib"] is False
        and required["result"]["target_work_domain"] == "bending"
        and required["result"]["required_domain_work_active"] is True
        and required["result"]["governing_domain"] == "bending"
        and required["result"]["tightening_mode_active"] is True,
        "shear_fallback_preserved": shear["cur_eval"].get("target_domain_for_band") == "shear"
        and shear["result"]["target_band_domain"] == "shear"
        and shear["result"]["cur_ib"] is False
        and shear["result"]["required_domain_work_active"] is False
        and shear["result"]["governing_domain"] == "shear"
        and shear["result"]["tightening_mode_active"] is True,
    }
    static_checks = {
        "solver_delegates_iteration_gate_state": (
            "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator("
            in solve_body
            and "_prepare_one_click_solver_iteration_gate_state_coordinator(" in source
        ),
        "helper_present": "def _prepare_one_click_solver_current_target_domain_state_coordinator(" in source,
        "helper_preserves_accumulated_diff": "_one_click_diff_accumulated_updates(initial_snapshot, working)"
        in helper,
        "helper_preserves_target_domain_eval_and_attach": "_one_click_target_domains_for_eval(" in helper
        and "_one_click_attach_eval_target_domains(cur_eval, cur_target_domains, mode_config)" in helper,
        "helper_preserves_shear_fallback": 'cur_eval["target_domain_for_band"] = "shear"' in helper
        and "target_band_domain == \"shear\" and cur_shear_failing" in helper,
        "helper_preserves_target_band_reset": "target_band_domain == \"shear\" and not cur_shear_failing and not cur_pass"
        in helper
        and "target_band_domain = governing_domain" in helper,
        "helper_preserves_current_in_band_check": "_candidate_in_target_band(cur_eval, mode_config)" in helper,
        "helper_preserves_required_domain_gate": "target_work_domain in (\"bending\", \"shear\")" in helper
        and "_one_click_domain_needs_cleanup(cur_eval, target_work_domain, mode_config)" in helper,
        "helper_preserves_shear_governing_override": "target_band_domain == \"shear\" and cur_shear_failing and not cur_ib"
        in helper
        and "governing_domain = \"shear\"" in helper
        and "tightening_mode_active = bool(cur_pass)" in helper,
        "solver_delegates_current_target_domain_state": (
            "_dispatch_one_click_solver_current_target_domain_state_from_iteration_gate_coordinator("
            in iteration_gate_after_current_eval_body
            and "_prepare_one_click_solver_current_target_domain_state_coordinator("
            in current_target_dispatch
            and "iteration_gate_scope[" in current_target_dispatch
        ),
        "solver_rehydrates_current_target_domain_fields": 'cur_ib = current_target_domain_state["cur_ib"]'
        in iteration_gate_after_current_eval_body
        and 'required_domain_work_active = current_target_domain_state["required_domain_work_active"]'
        in iteration_gate_after_current_eval_body
        and 'tightening_mode_active = current_target_domain_state["tightening_mode_active"]'
        in iteration_gate_after_current_eval_body,
        "solver_no_longer_inlines_current_target_domain_state": "_step_accum = _one_click_diff_accumulated_updates"
        not in solve_body
        and "_cur_td = _one_click_target_domains_for_eval(target_domains_for_band, _step_accum)" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_current_target_domain_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_current_target_domain_state_coordinator",
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
        "runtime": {"required": required, "shear": shear},
        "product_behavior_changed": False,
        "next_safe_slice": "extract in-band shear cleanup deferral state",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_current_target_domain_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_current_target_domain_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Current Target-Domain State Coordinator Extraction",
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
