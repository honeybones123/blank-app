"""Verify one-click solver no-real-change candidate coordinator extraction."""

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
        "_updates_match_state": getattr(module, "_updates_match_state", None),
        "_int_from_state": getattr(module, "_int_from_state", None),
        "_trace_candidate_eval_no_real_change_solver_coordinator": getattr(
            module,
            "_trace_candidate_eval_no_real_change_solver_coordinator",
            None,
        ),
    }
    calls: list[dict[str, Any]] = []

    def _trace(**kwargs: Any) -> None:
        calls.append(
            {
                "trace": {
                    "step_idx": kwargs.get("step_idx"),
                    "norm_u": dict(kwargs.get("norm_u") or {}),
                    "raw_u": dict(kwargs.get("raw_u") or {}),
                    "governing_domain": kwargs.get("governing_domain"),
                    "family_hint": kwargs.get("family_hint"),
                }
            }
        )

    try:
        module._trace_candidate_eval_no_real_change_solver_coordinator = _trace
        module._updates_match_state = lambda working, updates: False
        module._int_from_state = lambda state, key, default=0: int(state.get(key, default) or 0)
        pass_through = module._handle_one_click_solver_no_real_change_candidate_coordinator(
            step_idx=0,
            rc={"raw_updates": {"D": 700}},
            norm_u={"D": 700},
            raw_u={"D": 700},
            direction={"kind": "grow"},
            working={"D": 650},
            tightening_mode_active=False,
            governing_domain="bending",
            family_hint="bottom",
            rejected_as_no_real_change=2,
            shear_remove_links_candidate_seen=False,
            shear_remove_links_candidate_dropped_reason=None,
            trace_callback=lambda *_args, **_kwargs: None,
        )

        module._updates_match_state = lambda working, updates: True
        ordinary = module._handle_one_click_solver_no_real_change_candidate_coordinator(
            step_idx=1,
            rc={"raw_updates": {"D": 650}},
            norm_u={"D": 650},
            raw_u={"D": 650},
            direction={"kind": "same"},
            working={"D": 650},
            tightening_mode_active=True,
            governing_domain="bending",
            family_hint="bottom",
            rejected_as_no_real_change=2,
            shear_remove_links_candidate_seen=False,
            shear_remove_links_candidate_dropped_reason=None,
            trace_callback=lambda *_args, **_kwargs: None,
        )

        shear_remove = module._handle_one_click_solver_no_real_change_candidate_coordinator(
            step_idx=2,
            rc={"raw_updates": {"lig_legs": 0, "lig_d": 0}},
            norm_u={},
            raw_u={"lig_legs": 0, "lig_d": 0},
            direction={"kind": "remove"},
            working={"lig_legs": 2, "lig_d": 12},
            tightening_mode_active=True,
            governing_domain="shear",
            family_hint="shear_cleanup",
            rejected_as_no_real_change=3,
            shear_remove_links_candidate_seen=False,
            shear_remove_links_candidate_dropped_reason=None,
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {
        "pass_through": pass_through,
        "ordinary": ordinary,
        "shear_remove": shear_remove,
        "calls": calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_no_real_change_candidate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "pass_through_preserved": runtime["pass_through"] == {
            "rejected_as_no_real_change": 2,
            "shear_remove_links_candidate_seen": False,
            "shear_remove_links_candidate_dropped_reason": None,
            "should_continue": False,
        },
        "ordinary_no_real_change_preserved": runtime["ordinary"] == {
            "rejected_as_no_real_change": 3,
            "shear_remove_links_candidate_seen": False,
            "shear_remove_links_candidate_dropped_reason": None,
            "should_continue": True,
        },
        "shear_remove_links_no_real_change_preserved": runtime["shear_remove"] == {
            "rejected_as_no_real_change": 4,
            "shear_remove_links_candidate_seen": True,
            "shear_remove_links_candidate_dropped_reason": "no_real_change",
            "should_continue": True,
        },
        "trace_calls_preserved": runtime["calls"] == [
            {
                "trace": {
                    "step_idx": 1,
                    "norm_u": {"D": 650},
                    "raw_u": {"D": 650},
                    "governing_domain": "bending",
                    "family_hint": "bottom",
                }
            },
            {
                "trace": {
                    "step_idx": 2,
                    "norm_u": {},
                    "raw_u": {"lig_legs": 0, "lig_d": 0},
                    "governing_domain": "shear",
                    "family_hint": "shear_cleanup",
                }
            },
        ],
    }
    static_checks = {
        "helper_present": "def _handle_one_click_solver_no_real_change_candidate_coordinator(" in source,
        "helper_preserves_gate": "if norm_u and not _updates_match_state(working, norm_u):" in helper
        and '"should_continue": False' in helper,
        "helper_preserves_counter_increment": "rejected_as_no_real_change += 1" in helper,
        "helper_preserves_remove_links_probe": "remove_links_probe_updates = dict(norm_u) if norm_u else dict(raw_u)"
        in helper
        and "remove_links_probe_state.update(remove_links_probe_updates)" in helper,
        "helper_preserves_shear_remove_links_reason": 'shear_remove_links_candidate_dropped_reason = "no_real_change"'
        in helper
        and "shear_remove_links_candidate_seen = True" in helper,
        "helper_preserves_trace": "_trace_candidate_eval_no_real_change_solver_coordinator(" in helper,
        "solver_delegates_no_real_change_branch": "_handle_one_click_solver_no_real_change_candidate_coordinator("
        in solve_body,
        "solver_preserves_continue": 'if no_real_change_state["should_continue"]:' in solve_body
        and "continue" in solve_body,
        "solver_rehydrates_no_real_change_fields": 'rejected_as_no_real_change = no_real_change_state["rejected_as_no_real_change"]'
        in solve_body
        and 'shear_remove_links_candidate_dropped_reason = no_real_change_state[' in solve_body,
        "solver_no_longer_inlines_no_real_change_branch": "rejected_as_no_real_change += 1" not in solve_body
        and '_trace_candidate_eval_no_real_change_solver_coordinator(' not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_no_real_change_candidate_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_no_real_change_candidate_coordinator",
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
        "next_safe_slice": "extract non-governing domain-prune rejection branch",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_no_real_change_candidate_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_no_real_change_candidate_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver No-Real-Change Candidate Coordinator Extraction",
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
