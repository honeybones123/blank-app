"""Verify auto-design commit-start coordinator extraction."""

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


def _run_case(module: Any, *, shear_target: bool) -> dict[str, Any]:
    originals = {
        "_shared_state_snapshot": getattr(module, "_shared_state_snapshot", None),
        "_sanitize_shared_update_bundle": getattr(module, "_sanitize_shared_update_bundle", None),
        "_design_mode_config": getattr(module, "_design_mode_config", None),
        "_design_optimisation_goal": getattr(module, "_design_optimisation_goal", None),
        "_evaluate_auto_design_candidate": getattr(module, "_evaluate_auto_design_candidate", None),
        "_record_one_click_shear_publish_audit": getattr(
            module,
            "_record_one_click_shear_publish_audit",
            None,
        ),
        "evaluate_candidate_full": getattr(module, "evaluate_candidate_full", None),
        "_guidance_state_snapshot": getattr(module, "_guidance_state_snapshot", None),
        "_append_design_guide_trace": getattr(module, "_append_design_guide_trace", None),
    }
    eval_calls: list[dict[str, Any]] = []
    previews: dict[str, dict[str, Any]] = {}
    audits: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []

    def _sanitize(updates: dict[str, Any], **_: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        return (
            {"D": updates.get("D")},
            {
                "dropped_nonshared_keys": ["local_only"],
                "dropped_private_keys": ["_private"],
            },
        )

    def _candidate(state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        source = str(kwargs.get("source") or "")
        eval_calls.append({"state": dict(state), "kwargs": dict(kwargs)})
        preview = {
            "overview": {
                "worst_util": 1.25 if source.endswith("_raw") else 0.94,
                "statuses": {"shear": "FAIL" if source.endswith("_raw") else "PASS"},
            },
            "source": source,
        }
        previews[source] = preview
        return preview

    def _full(state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        eval_calls.append({"state": dict(state), "kwargs": dict(kwargs)})
        return {"overview": {"worst_util": 1.11}}

    def _trace(event: str, data: dict[str, Any], **kwargs: Any) -> None:
        traces.append({"event": event, "data": dict(data), "kwargs": dict(kwargs)})

    try:
        module._shared_state_snapshot = lambda: {"D": 500, "shared": True}
        module._sanitize_shared_update_bundle = _sanitize
        module._design_optimisation_goal = lambda state: "balanced"
        module._design_mode_config = lambda goal: {"goal": goal, "mode": "unit"}
        module._evaluate_auto_design_candidate = _candidate
        module._record_one_click_shear_publish_audit = lambda **kwargs: audits.append(dict(kwargs))
        module.evaluate_candidate_full = _full
        module._guidance_state_snapshot = lambda state: {"snap": dict(state)}
        module._append_design_guide_trace = _trace
        result = module._prepare_auto_design_commit_start_coordinator(
            current_state={"D": 600, "goal": "balanced"},
            final_updates={"D": 650, "local_only": 1, "_private": 2},
            dbg={"target_band_domain": "shear" if shear_target else "bending"},
            win_l="Winner",
            win_at="adjust",
            trace_run_id="run-123",
            trace_src="unit",
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {
        "result": result,
        "eval_calls": eval_calls,
        "previews": previews,
        "audits": audits,
        "traces": traces,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_auto_design_commit_start_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    _, _, post_solver_commit_body = _function_segment(
        source,
        "_run_auto_design_post_solver_commit_orchestration_coordinator",
    )
    _, _, commit_body = _function_segment(
        source,
        "_run_auto_design_commit_orchestration_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    shear_runtime = _run_case(module, shear_target=True)
    bending_runtime = _run_case(module, shear_target=False)
    shear_result = shear_runtime["result"]
    shear_dbg = shear_result["dbg"]
    trace = shear_runtime["traces"][0]
    runtime_checks = {
        "raw_and_sanitized_keys_recorded": shear_dbg.get("final_updates_raw_keys") == ["D", "_private", "local_only"]
        and shear_dbg.get("final_updates_sanitized_keys") == ["D"]
        and shear_dbg.get("final_updates_dropped_nonshared_keys") == ["local_only"]
        and shear_dbg.get("final_updates_dropped_private_keys") == ["_private"],
        "raw_and_sanitized_previews_recorded": shear_dbg.get("raw_commit_preview_worst_util") == 1.25
        and shear_dbg.get("raw_commit_preview_statuses") == {"shear": "FAIL"}
        and shear_dbg.get("sanitized_commit_preview_worst_util") == 0.94
        and shear_dbg.get("sanitized_commit_preview_statuses") == {"shear": "PASS"},
        "preview_call_contracts_preserved": [
            call["kwargs"].get("source") for call in shear_runtime["eval_calls"][:2]
        ]
        == ["one_click_commit_preview_raw", "one_click_commit_preview_sanitized"]
        and shear_runtime["eval_calls"][0]["kwargs"].get("updates") == {"D": 650, "local_only": 1, "_private": 2}
        and shear_runtime["eval_calls"][1]["kwargs"].get("updates") == {"D": 650},
        "shear_target_domain_override_preserved": shear_runtime["previews"]["one_click_commit_preview_raw"].get(
            "target_domain_for_band",
        )
        == "shear"
        and shear_runtime["previews"]["one_click_commit_preview_sanitized"].get("target_domain_for_band") == "shear"
        and "target_domain_for_band" not in bending_runtime["previews"]["one_click_commit_preview_raw"],
        "shear_publish_audit_preserved": shear_runtime["audits"] == [
            {
                "stage": "iterative_selected_candidate",
                "source": "one_click_auto_design:iterative",
                "candidate_updates": {"D": 650, "local_only": 1, "_private": 2},
                "publish_attempted": False,
                "publish_blocked": True,
            },
        ],
        "pre_commit_audit_preserved": shear_dbg.get("pre_commit_worst_util") == 1.11
        and shear_result["pre_commit_worst_util"] == 1.11
        and shear_runtime["eval_calls"][2]["kwargs"].get("source") == "one_click_pre_commit_audit",
        "commit_start_trace_payload_preserved": trace["event"] == "commit_start"
        and trace["data"].get("final_updates_sanitized_keys") == ["D"]
        and trace["data"].get("pre_commit_worst_util") == 1.11
        and trace["data"].get("raw_commit_preview_worst_util") == 1.25
        and trace["kwargs"] == {"run_id": "run-123", "source": "unit"},
        "runner_required_values_returned": shear_result["pre_commit_shared_state"] == {"D": 500, "shared": True}
        and shear_result["commit_mode_config"] == {"goal": "balanced", "mode": "unit"},
    }
    static_checks = {
        "helper_present": "def _prepare_auto_design_commit_start_coordinator(" in source,
        "helper_preserves_sanitize_call": "_sanitize_shared_update_bundle(" in helper,
        "helper_preserves_preview_sources": "one_click_commit_preview_raw" in helper
        and "one_click_commit_preview_sanitized" in helper,
        "helper_preserves_shear_publish_audit": "_record_one_click_shear_publish_audit(" in helper,
        "helper_preserves_commit_start_trace": '"commit_start"' in helper,
        "helper_returns_runner_context": '"pre_commit_shared_state": pre_commit_shared_state' in helper
        and '"commit_mode_config": commit_mode_config' in helper,
        "commit_orchestration_delegates_commit_start": "_prepare_auto_design_commit_start_coordinator("
        in commit_body,
        "post_solver_commit_delegates_commit_orchestration": "_run_auto_design_commit_orchestration_coordinator("
        in post_solver_commit_body,
        "run_delegates_post_solver_commit_orchestration": "_run_auto_design_post_solver_commit_orchestration_coordinator("
        in run_body,
        "run_no_longer_owns_preview_setup": "one_click_commit_preview_raw" not in run_body
        and "one_click_commit_preview_sanitized" not in run_body
        and "one_click_pre_commit_audit" not in run_body,
        "commit_orchestration_delegates_live_commit_write": "_apply_auto_design_commit_write_audit_setup_coordinator("
        in commit_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_commit_start_coordinator",
        "helper_segment": {
            "function": "_prepare_auto_design_commit_start_coordinator",
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
        "shear_runtime": shear_runtime,
        "bending_runtime": bending_runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract post-commit write and audit setup from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_commit_start_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_commit_start_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Commit-Start Coordinator Extraction",
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
