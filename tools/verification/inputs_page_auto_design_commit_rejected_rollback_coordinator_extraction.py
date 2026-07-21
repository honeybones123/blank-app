"""Verify auto-design commit-rejected rollback coordinator extraction."""

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


def _run_case(module: Any) -> dict[str, Any]:
    originals = {
        "SHARED_DEFAULTS": getattr(module, "SHARED_DEFAULTS", None),
        "_restore_shared_state_snapshot": getattr(module, "_restore_shared_state_snapshot", None),
        "persist_active_beam_from_shared": getattr(module, "persist_active_beam_from_shared", None),
        "_pop_inputs_widget_keys_for_shared_updates": getattr(
            module,
            "_pop_inputs_widget_keys_for_shared_updates",
            None,
        ),
        "_append_design_guide_trace": getattr(module, "_append_design_guide_trace", None),
        "_invalidate_design_guide_caches": getattr(module, "_invalidate_design_guide_caches", None),
        "finalize_auto_design_publish": getattr(module, "finalize_auto_design_publish", None),
        "_agent_debug_log": getattr(module, "_agent_debug_log", None),
    }
    restored: list[dict[str, Any]] = []
    persisted: list[bool] = []
    popped: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    invalidations: list[dict[str, Any]] = []
    publishes: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []
    commit_audit = {
        "audited_commit_updates": {"D": 650},
        "ignored_commit_update_keys": ["ignored"],
        "has_row_model_updates": True,
        "ignored_row_model_legacy_mirror_keys": ["legacy"],
        "post_commit_mismatch_keys": ["D"],
        "post_commit_mismatch_details": {"D": "rolled"},
        "post_commit_live_worst_util": 1.42,
        "post_commit_live_statuses": {"shear": "FAIL"},
    }

    def _publish(**kwargs: Any) -> dict[str, Any]:
        publishes.append(dict(kwargs))
        return {"publication": "rollback", "kwargs": dict(kwargs)}

    try:
        module.SHARED_DEFAULTS = {"D": 0, "B": 0, "lig_d": 0}
        module._restore_shared_state_snapshot = lambda snapshot, **kwargs: restored.append(
            {"snapshot": dict(snapshot), "kwargs": dict(kwargs)},
        )
        module.persist_active_beam_from_shared = lambda: persisted.append(True)
        module._pop_inputs_widget_keys_for_shared_updates = lambda updates: popped.append(dict(updates))
        module._append_design_guide_trace = lambda event, data, **kwargs: traces.append(
            {"event": event, "data": dict(data), "kwargs": dict(kwargs)},
        )
        module._invalidate_design_guide_caches = lambda **kwargs: invalidations.append(dict(kwargs))
        module.finalize_auto_design_publish = _publish
        module._agent_debug_log = lambda message, payload, **kwargs: logs.append(
            {"message": message, "payload": dict(payload), "kwargs": dict(kwargs)},
        )
        result = module._handle_auto_design_commit_rejected_rollback_coordinator(
            commit_audit=commit_audit,
            commit_reject_reason="mismatch",
            dbg={
                "final_updates_raw_keys": ["D", "lig_d"],
                "final_updates_sanitized_keys": ["D"],
                "final_updates_dropped_nonshared_keys": ["local"],
                "final_updates_dropped_private_keys": ["_private"],
                "final_no_links_candidate_committed": True,
            },
            pre_commit_shared_state={"D": 500, "B": 300, "lig_d": 10},
            pre_commit_worst_util=1.05,
            solver_final_updates={"D": 650, "lig_d": 8},
            trace_run_id="run-123",
            trace_src="unit",
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {
        "result": result,
        "restored": restored,
        "persisted": persisted,
        "popped": popped,
        "traces": traces,
        "invalidations": invalidations,
        "publishes": publishes,
        "logs": logs,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_auto_design_commit_rejected_rollback_coordinator",
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

    runtime = _run_case(module)
    result = runtime["result"]
    dbg = result["dbg"]
    trace = runtime["traces"][0]
    runtime_checks = {
        "rollback_source_preserved": runtime["restored"] == [
            {
                "snapshot": {"D": 500, "B": 300, "lig_d": 10},
                "kwargs": {"source": "one_click_auto_design:rollback_failed_commit"},
            },
        ],
        "persist_and_widget_reset_preserved": runtime["persisted"] == [True]
        and runtime["popped"] == [{"D": 500, "B": 300, "lig_d": 10}],
        "rejection_debug_flags_preserved": dbg.get("final_no_links_candidate_committed") is False
        and dbg.get("one_click_commit_rejected") is True
        and dbg.get("one_click_commit_reject_reason") == "mismatch"
        and dbg.get("one_click_commit_rolled_back") is True
        and dbg.get("restored_after_failed_commit") is True,
        "commit_rejected_trace_preserved": trace["event"] == "commit_rejected"
        and trace["data"].get("reject_reason") == "mismatch"
        and trace["data"].get("attempted_final_updates") == {"D": 650, "lig_d": 8}
        and trace["data"].get("final_updates_sanitized_keys") == ["D"]
        and trace["kwargs"] == {"run_id": "run-123", "source": "unit"},
        "cache_invalidation_preserved": runtime["invalidations"] == [
            {
                "reason": "one_click_auto_design:commit_rejected",
                "updated_keys": ["D", "lig_d"],
            },
        ],
        "rollback_publish_preserved": runtime["publishes"] == [
            {
                "updated_keys": ["D", "lig_d"],
                "source": "one_click_auto_design:commit_rollback",
                "focus_section": "shear",
                "set_run_design_clicked": True,
            },
        ]
        and dbg.get("rollback_publish_payload", {}).get("publication") == "rollback",
        "debug_log_preserved": runtime["logs"][0]["message"]
        == "One-click commit rejected after live validation; rolled back"
        and runtime["logs"][0]["kwargs"] == {
            "location": "inputs_page.py:run_one_click_auto_design:commit_rejected",
            "hypothesis_id": "H_ONE_CLICK_COMMIT",
        },
        "runner_state_returned": result["final_updates"] == {}
        and result["commit_rejected"] is True
        and result["commit_reject_reason"] == "mismatch",
    }
    static_checks = {
        "helper_present": "def _handle_auto_design_commit_rejected_rollback_coordinator(" in source,
        "helper_preserves_restore_source": "one_click_auto_design:rollback_failed_commit" in helper,
        "helper_preserves_trace": '"commit_rejected"' in helper,
        "helper_preserves_publish_refresh": "one_click_auto_design:commit_rollback" in helper,
        "helper_preserves_debug_log": "H_ONE_CLICK_COMMIT" in helper,
        "commit_orchestration_delegates_rejected_branch": "_handle_auto_design_commit_rejected_rollback_coordinator("
        in commit_body,
        "commit_orchestration_delegates_success_branch": "_handle_auto_design_commit_success_audit_setup_coordinator("
        in commit_body,
        "post_solver_commit_delegates_commit_orchestration": "_run_auto_design_commit_orchestration_coordinator("
        in post_solver_commit_body,
        "run_delegates_post_solver_commit_orchestration": "_run_auto_design_post_solver_commit_orchestration_coordinator("
        in run_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_commit_rejected_rollback_coordinator",
        "helper_segment": {
            "function": "_handle_auto_design_commit_rejected_rollback_coordinator",
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
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract successful commit audit trace setup from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_commit_rejected_rollback_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_commit_rejected_rollback_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Commit-Rejected Rollback Coordinator Extraction",
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
