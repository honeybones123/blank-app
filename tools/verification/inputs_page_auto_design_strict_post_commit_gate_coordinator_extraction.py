"""Verify auto-design strict post-commit gate coordinator extraction."""

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
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _run_case(module: Any, *, strict_ok: bool) -> dict[str, Any]:
    originals = {
        "_shared_state_snapshot": getattr(module, "_shared_state_snapshot", None),
        "_guidance_state_snapshot": getattr(module, "_guidance_state_snapshot", None),
        "_collect_design_overview": getattr(module, "_collect_design_overview", None),
        "_one_click_strict_target_band_ok": getattr(module, "_one_click_strict_target_band_ok", None),
    }
    try:
        module._shared_state_snapshot = lambda: {"D": 650, "shared": True}
        module._guidance_state_snapshot = lambda state: {"snap": dict(state)}
        module._collect_design_overview = lambda state: {
            "state": dict(state),
            "governing_util": 0.97 if strict_ok else 1.23,
            "worst_util": 1.99,
            "statuses": {"bending": "PASS", "shear": "PASS" if strict_ok else "FAIL"},
        }
        module._one_click_strict_target_band_ok = lambda overview, config: bool(strict_ok)
        result = module._prepare_auto_design_strict_post_commit_gate_coordinator(
            commit_mode_config={"mode": "unit"},
            dbg={"seed": "kept"},
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
    return {"result": result}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_auto_design_strict_post_commit_gate_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    _, _, final_tail_body = _function_segment(
        source,
        "_run_one_click_auto_design_solver_and_final_response_coordinator",
    )
    _, _, post_solver_commit_body = _function_segment(
        source,
        "_run_auto_design_post_solver_commit_orchestration_coordinator",
    )
    _, _, commit_body = _function_segment(
        source,
        "_run_auto_design_commit_orchestration_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    ok_runtime = _run_case(module, strict_ok=True)
    fail_runtime = _run_case(module, strict_ok=False)
    ok_dbg = ok_runtime["result"]["dbg"]
    fail_dbg = fail_runtime["result"]["dbg"]
    runtime_checks = {
        "ok_gate_fields_preserved": ok_runtime["result"]["strict_live_ok"] is True
        and ok_dbg.get("one_click_strict_post_commit_target_band_ok") is True
        and ok_dbg.get("one_click_strict_post_commit_live_worst_util") == 0.97
        and ok_dbg.get("one_click_strict_post_commit_statuses") == {"bending": "PASS", "shear": "PASS"},
        "fail_gate_fields_preserved": fail_runtime["result"]["strict_live_ok"] is False
        and fail_dbg.get("one_click_strict_post_commit_target_band_ok") is False
        and fail_dbg.get("one_click_strict_post_commit_live_worst_util") == 1.23
        and fail_dbg.get("one_click_strict_post_commit_statuses") == {"bending": "PASS", "shear": "FAIL"},
        "state_and_overview_returned": ok_runtime["result"]["strict_live_state"] == {
            "snap": {"D": 650, "shared": True},
        }
        and ok_runtime["result"]["strict_live_overview"].get("state") == {
            "snap": {"D": 650, "shared": True},
        },
        "seed_debug_preserved": ok_dbg.get("seed") == "kept" and fail_dbg.get("seed") == "kept",
    }
    static_checks = {
        "helper_present": "def _prepare_auto_design_strict_post_commit_gate_coordinator(" in source,
        "helper_preserves_live_state_snapshot": "_guidance_state_snapshot(_shared_state_snapshot())" in helper,
        "helper_preserves_overview_collection": "_collect_design_overview(strict_live_state)" in helper,
        "helper_preserves_target_band_gate": "_one_click_strict_target_band_ok(strict_live_overview, commit_mode_config)" in helper,
        "helper_preserves_debug_fields": "one_click_strict_post_commit_target_band_ok" in helper
        and "one_click_strict_post_commit_live_worst_util" in helper
        and "one_click_strict_post_commit_statuses" in helper,
        "commit_orchestration_delegates_strict_gate": "_prepare_auto_design_strict_post_commit_gate_coordinator("
        in commit_body,
        "commit_orchestration_delegates_strict_followup": "_handle_auto_design_strict_followup_commit_coordinator("
        in commit_body,
        "post_solver_commit_delegates_commit_orchestration": "_run_auto_design_commit_orchestration_coordinator("
        in post_solver_commit_body,
        "run_delegates_post_solver_commit_orchestration": (
            "_run_one_click_auto_design_solver_and_final_response_coordinator("
            in run_body
            and "_run_auto_design_post_solver_commit_orchestration_coordinator("
            in final_tail_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_strict_post_commit_gate_coordinator",
        "helper_segment": {
            "function": "_prepare_auto_design_strict_post_commit_gate_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "run_segment": {
            "function": "run_one_click_auto_design",
            "start_line": run_start,
            "end_line": run_end,
            "line_count": run_end - run_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "ok_runtime": ok_runtime,
        "fail_runtime": fail_runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract strict follow-up commit branch from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_strict_post_commit_gate_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_strict_post_commit_gate_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Strict Post-Commit Gate Coordinator Extraction",
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
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            str(payload["next_safe_slice"]),
        ],
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
