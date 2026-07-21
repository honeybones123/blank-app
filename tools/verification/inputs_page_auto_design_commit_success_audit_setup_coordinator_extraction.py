"""Verify auto-design commit success audit setup coordinator extraction."""

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


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}


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


def _run_case(module: Any, *, refresh_returns_dict: bool = True) -> dict[str, Any]:
    originals = {
        "st": getattr(module, "st", None),
        "_DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS": getattr(
            module,
            "_DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS",
            None,
        ),
        "persist_active_beam_from_shared": getattr(module, "persist_active_beam_from_shared", None),
        "_append_design_guide_trace": getattr(module, "_append_design_guide_trace", None),
        "_invalidate_design_guide_caches": getattr(module, "_invalidate_design_guide_caches", None),
        "finalize_auto_design_publish": getattr(module, "finalize_auto_design_publish", None),
        "_local_cleanup_acceptance_fingerprint": getattr(module, "_local_cleanup_acceptance_fingerprint", None),
        "_shared_state_snapshot": getattr(module, "_shared_state_snapshot", None),
        "_one_click_post_commit_audit": getattr(module, "_one_click_post_commit_audit", None),
        "_agent_debug_log": getattr(module, "_agent_debug_log", None),
    }
    fake_st = _FakeStreamlit()
    accepted_fps: set[str] = set()
    persisted: list[bool] = []
    traces: list[dict[str, Any]] = []
    invalidations: list[dict[str, Any]] = []
    publishes: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []
    initial_audit = {
        "post_commit_matches_intended_updates": True,
        "audited_commit_updates": {"D": 650},
        "ignored_commit_update_keys": ["ignored-initial"],
        "has_row_model_updates": False,
        "ignored_row_model_legacy_mirror_keys": [],
        "post_commit_mismatch_keys": [],
        "post_commit_mismatch_details": {},
        "post_commit_live_worst_util": 0.99,
        "post_commit_live_statuses": {"shear": "PASS"},
    }
    refreshed_audit = {
        "post_commit_matches_intended_updates": True,
        "audited_commit_updates": {"D": 650, "B": 320},
        "ignored_commit_update_keys": ["ignored-refresh"],
        "has_row_model_updates": True,
        "ignored_row_model_legacy_mirror_keys": ["legacy"],
        "post_commit_mismatch_keys": ["B"],
        "post_commit_mismatch_details": {"B": "updated"},
        "post_commit_live_worst_util": 0.88,
        "post_commit_live_statuses": {"bending": "PASS", "shear": "PASS"},
    }

    def _publish(**kwargs: Any) -> dict[str, Any]:
        publishes.append(dict(kwargs))
        return {"publication": "success", "kwargs": dict(kwargs)}

    try:
        module.st = fake_st
        module._DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS = accepted_fps
        module.persist_active_beam_from_shared = lambda: persisted.append(True)
        module._append_design_guide_trace = lambda event, data, **kwargs: traces.append(
            {"event": event, "data": dict(data), "kwargs": dict(kwargs)},
        )
        module._invalidate_design_guide_caches = lambda **kwargs: invalidations.append(dict(kwargs))
        module.finalize_auto_design_publish = _publish
        module._shared_state_snapshot = lambda: {"D": 650, "B": 320}
        module._local_cleanup_acceptance_fingerprint = lambda state: f"fp-{state.get('D')}-{state.get('B')}"
        module._one_click_post_commit_audit = (
            (lambda updates: dict(refreshed_audit))
            if refresh_returns_dict
            else (lambda updates: None)
        )
        module._agent_debug_log = lambda message, payload, **kwargs: logs.append(
            {"message": message, "payload": dict(payload), "kwargs": dict(kwargs)},
        )
        result = module._handle_auto_design_commit_success_audit_setup_coordinator(
            commit_audit=dict(initial_audit),
            final_updates={"D": 650, "B": 320, "lig_d": 8},
            dbg={
                "final_updates_raw_keys": ["B", "D", "lig_d"],
                "final_updates_sanitized_keys": ["B", "D", "lig_d"],
                "final_updates_dropped_nonshared_keys": [],
                "final_updates_dropped_private_keys": [],
            },
            trace_run_id="run-123",
            trace_src="unit",
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {
        "result": result,
        "session_state": dict(fake_st.session_state),
        "accepted_fps": sorted(accepted_fps),
        "persisted": persisted,
        "traces": traces,
        "invalidations": invalidations,
        "publishes": publishes,
        "logs": logs,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_auto_design_commit_success_audit_setup_coordinator",
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

    runtime = _run_case(module, refresh_returns_dict=True)
    no_refresh_runtime = _run_case(module, refresh_returns_dict=False)
    dbg = runtime["result"]["dbg"]
    trace = runtime["traces"][0]
    session_payload = runtime["session_state"].get("_one_click_post_commit_audit_latest") or {}
    runtime_checks = {
        "persist_and_rejection_defaults_preserved": runtime["persisted"] == [True]
        and dbg.get("one_click_commit_rejected") is False
        and dbg.get("one_click_commit_reject_reason") is None
        and dbg.get("one_click_commit_rolled_back") is False
        and dbg.get("restored_after_failed_commit") is False,
        "commit_audit_trace_preserved": trace["event"] == "commit_audit"
        and trace["data"].get("audited_commit_updates") == {"D": 650}
        and trace["data"].get("ignored_commit_update_keys") == ["ignored-initial"]
        and trace["data"].get("final_updates_raw_keys") == ["B", "D", "lig_d"]
        and trace["kwargs"] == {"run_id": "run-123", "source": "unit"},
        "cache_invalidation_and_publish_preserved": runtime["invalidations"] == [
            {"reason": "one_click_auto_design", "updated_keys": ["D", "B", "lig_d"]},
        ]
        and runtime["publishes"] == [
            {
                "updated_keys": ["B", "D", "lig_d"],
                "source": "one_click_auto_design",
                "focus_section": "shear",
                "set_run_design_clicked": True,
            },
        ]
        and dbg.get("success_publish_payload", {}).get("publication") == "success",
        "local_cleanup_acceptance_preserved": runtime["accepted_fps"] == ["fp-650-320"]
        and runtime["session_state"].get("_design_guide_post_cleanup_acceptance_fp") == "fp-650-320"
        and runtime["session_state"].get("_design_guide_post_cleanup_acceptance_enabled") is True,
        "refreshed_commit_audit_preserved": runtime["result"]["commit_audit"].get("audited_commit_updates")
        == {"D": 650, "B": 320}
        and dbg.get("one_click_commit_audit", {}).get("post_commit_live_worst_util") == 0.88
        and dbg.get("audited_commit_updates") == {"D": 650, "B": 320}
        and dbg.get("ignored_commit_update_keys") == ["ignored-refresh"]
        and dbg.get("has_row_model_updates") is True
        and dbg.get("ignored_row_model_legacy_mirror_keys") == ["legacy"]
        and dbg.get("post_commit_mismatch_keys") == ["B"]
        and dbg.get("post_commit_mismatch_details") == {"B": "updated"}
        and dbg.get("post_commit_live_statuses") == {"bending": "PASS", "shear": "PASS"},
        "session_payload_preserved": session_payload == {
            "post_commit_matches_intended_updates": True,
            "post_commit_mismatch_keys": ["B"],
            "ignored_commit_update_keys": ["ignored-refresh"],
            "has_row_model_updates": True,
            "ignored_row_model_legacy_mirror_keys": ["legacy"],
            "post_commit_live_worst_util": 0.88,
            "post_commit_live_statuses": {"bending": "PASS", "shear": "PASS"},
        },
        "debug_log_preserved": runtime["logs"][0]["message"] == "One-click iterative commit audit"
        and runtime["logs"][0]["payload"].get("audited_commit_updates") == {"D": 650, "B": 320}
        and runtime["logs"][0]["kwargs"] == {
            "location": "inputs_page.py:run_one_click_auto_design:commit_audit",
            "hypothesis_id": "H_ONE_CLICK_COMMIT",
        },
        "non_dict_refresh_keeps_initial_audit": no_refresh_runtime["result"]["commit_audit"].get(
            "ignored_commit_update_keys",
        )
        == ["ignored-initial"],
    }
    static_checks = {
        "helper_present": "def _handle_auto_design_commit_success_audit_setup_coordinator(" in source,
        "helper_preserves_trace": '"commit_audit"' in helper,
        "helper_preserves_success_publish": "source=\"one_click_auto_design\"" in helper,
        "helper_preserves_local_cleanup_acceptance": "_DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.add" in helper,
        "helper_preserves_refreshed_audit": "refreshed_commit_audit = _one_click_post_commit_audit(final_updates)" in helper,
        "helper_preserves_debug_log": "One-click iterative commit audit" in helper,
        "commit_orchestration_delegates_success_audit_setup": "_handle_auto_design_commit_success_audit_setup_coordinator("
        in commit_body,
        "commit_orchestration_delegates_strict_followup": "_handle_auto_design_strict_followup_commit_coordinator("
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
        "surface": "run_one_click_auto_design_commit_success_audit_setup_coordinator",
        "helper_segment": {
            "function": "_handle_auto_design_commit_success_audit_setup_coordinator",
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
        "no_refresh_runtime": no_refresh_runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract strict post-commit target-band gate from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_commit_success_audit_setup_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_commit_success_audit_setup_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Commit Success Audit Setup Coordinator Extraction",
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
