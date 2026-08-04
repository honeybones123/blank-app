"""Verify one-click solver candidate target-domain attachment coordinator extraction."""

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
        "_one_click_target_domains_for_eval": getattr(module, "_one_click_target_domains_for_eval", None),
        "_one_click_attach_eval_target_domains": getattr(module, "_one_click_attach_eval_target_domains", None),
    }
    attach_calls: list[dict[str, Any]] = []

    def _target_domains(target_domains_for_band: list[str], norm_u: dict) -> list[str]:
        if norm_u.get("kind") == "has_domains":
            return ["bending", "shear"]
        return []

    def _attach(peval: dict[str, Any], domains: list[str], mode_config: Any) -> None:
        attach_calls.append({"domains": list(domains), "mode_config": mode_config})
        peval["attached_domains"] = list(domains)

    try:
        module._one_click_target_domains_for_eval = _target_domains
        module._one_click_attach_eval_target_domains = _attach
        with_domains_peval = {"target_domain_for_band": "old"}
        with_domains = module._prepare_one_click_solver_candidate_target_domain_attachment_state_coordinator(
            peval=with_domains_peval,
            norm_u={"kind": "has_domains"},
            target_domains_for_band=["bending"],
            mode_config={"mode": "balanced"},
            target_band_domain="shear",
            cur_shear_failing=True,
        )
        shear_fallback_peval = {"existing": True}
        shear_fallback = module._prepare_one_click_solver_candidate_target_domain_attachment_state_coordinator(
            peval=shear_fallback_peval,
            norm_u={},
            target_domains_for_band=["shear"],
            mode_config={"mode": "balanced"},
            target_band_domain="shear",
            cur_shear_failing=True,
        )
        removed_peval = {"target_domain_for_band": "old", "existing": True}
        removed = module._prepare_one_click_solver_candidate_target_domain_attachment_state_coordinator(
            peval=removed_peval,
            norm_u={},
            target_domains_for_band=["bending"],
            mode_config={"mode": "balanced"},
            target_band_domain="bending",
            cur_shear_failing=True,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "with_domains": with_domains,
        "shear_fallback": shear_fallback,
        "removed": removed,
        "attach_calls": attach_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_target_domain_attachment_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    scoring_loop_start, scoring_loop_end, scoring_loop_body = _function_segment(
        source, "_run_one_click_solver_candidate_scoring_loop_coordinator"
    )
    _, _, single_candidate_body = _function_segment(
        source, "_run_one_click_solver_single_candidate_scoring_flow_coordinator"
    )
    _, _, pre_metric_body = _function_segment(
        source, "_run_one_click_solver_single_candidate_pre_metric_gate_flow_coordinator"
    )
    _, _, pre_selection_body = _function_segment(
        source, "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator"
    )
    _, _, pre_selection_pipeline_body = _function_segment(
        source,
        "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "with_domains_preserved": runtime["with_domains"] == {
            "peval": {
                "target_domain_for_band": "old",
                "attached_domains": ["bending", "shear"],
            },
            "candidate_target_domains": ["bending", "shear"],
        },
        "shear_fallback_preserved": runtime["shear_fallback"] == {
            "peval": {
                "existing": True,
                "attached_domains": [],
                "target_domain_for_band": "shear",
            },
            "candidate_target_domains": [],
        },
        "target_domain_removed_preserved": runtime["removed"] == {
            "peval": {"existing": True, "attached_domains": []},
            "candidate_target_domains": [],
        },
        "attach_calls_preserved": runtime["attach_calls"] == [
            {"domains": ["bending", "shear"], "mode_config": {"mode": "balanced"}},
            {"domains": [], "mode_config": {"mode": "balanced"}},
            {"domains": [], "mode_config": {"mode": "balanced"}},
        ],
    }
    static_checks = {
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "pre_selection_delegates_candidate_scoring_loop": (
            "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator(" in pre_selection_body
            and "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator("
            in pre_selection_pipeline_body
        ),
        "scoring_loop_delegates_single_candidate_flow": (
            "_run_one_click_solver_single_candidate_scoring_flow_coordinator(" in scoring_loop_body
        ),
        "single_candidate_flow_delegates_pre_metric_gate_flow": (
            "_run_one_click_solver_single_candidate_pre_metric_gate_flow_coordinator(" in single_candidate_body
        ),
        "helper_present": "def _prepare_one_click_solver_candidate_target_domain_attachment_state_coordinator("
        in source,
        "helper_preserves_target_domain_resolution": (
            "_one_click_target_domains_for_eval(target_domains_for_band, norm_u)" in helper
        ),
        "helper_preserves_attachment": "_one_click_attach_eval_target_domains(peval, candidate_target_domains, mode_config)"
        in helper,
        "helper_preserves_shear_fallback": 'peval["target_domain_for_band"] = "shear"' in helper,
        "helper_preserves_removal": 'peval.pop("target_domain_for_band", None)' in helper,
        "pre_metric_flow_delegates_target_domain_attachment": (
            "_prepare_one_click_solver_candidate_target_domain_attachment_state_coordinator(" in pre_metric_body
        ),
        "pre_metric_flow_rehydrates_target_domain_peval": (
            'peval = target_domain_state["peval"]' in pre_metric_body
        ),
        "scoring_loop_no_longer_delegates_target_domain_attachment_directly": (
            "_prepare_one_click_solver_candidate_target_domain_attachment_state_coordinator(" not in scoring_loop_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_target_domain_attachment_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_candidate_target_domain_attachment_state_coordinator",
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
        "next_safe_slice": "extract duplicate-signature candidate rejection branch",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_target_domain_attachment_state_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_target_domain_attachment_state_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Target-Domain Attachment State Coordinator Extraction",
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
