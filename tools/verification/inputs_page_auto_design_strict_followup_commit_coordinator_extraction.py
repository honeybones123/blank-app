"""Verify auto-design strict follow-up commit coordinator extraction."""

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


def _run_case(module: Any, *, case: str) -> dict[str, Any]:
    originals = {
        "SHARED_DEFAULTS": getattr(module, "SHARED_DEFAULTS", None),
        "_build_canonical_design_state_pack": getattr(module, "_build_canonical_design_state_pack", None),
        "_overlay_current_normalized_shear_truth": getattr(module, "_overlay_current_normalized_shear_truth", None),
        "_guidance_state_snapshot": getattr(module, "_guidance_state_snapshot", None),
        "_shared_state_snapshot": getattr(module, "_shared_state_snapshot", None),
        "_solve_one_click_to_target": getattr(module, "_solve_one_click_to_target", None),
        "_sanitize_shared_update_bundle": getattr(module, "_sanitize_shared_update_bundle", None),
        "_set_shared_updates": getattr(module, "_set_shared_updates", None),
        "_publish_current_normalized_shear_truth_coordinator": getattr(
            module,
            "_publish_current_normalized_shear_truth_coordinator",
            None,
        ),
        "_pop_inputs_widget_keys_for_shared_updates": getattr(
            module,
            "_pop_inputs_widget_keys_for_shared_updates",
            None,
        ),
        "_one_click_post_commit_audit": getattr(module, "_one_click_post_commit_audit", None),
        "_collect_design_overview": getattr(module, "_collect_design_overview", None),
        "_one_click_commit_audit_passes": getattr(module, "_one_click_commit_audit_passes", None),
        "_one_click_strict_target_band_ok": getattr(module, "_one_click_strict_target_band_ok", None),
        "persist_active_beam_from_shared": getattr(module, "persist_active_beam_from_shared", None),
        "_invalidate_design_guide_caches": getattr(module, "_invalidate_design_guide_caches", None),
        "finalize_auto_design_publish": getattr(module, "finalize_auto_design_publish", None),
        "_restore_shared_state_snapshot": getattr(module, "_restore_shared_state_snapshot", None),
    }
    writes: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    popped: list[dict[str, Any]] = []
    persisted: list[bool] = []
    invalidations: list[dict[str, Any]] = []
    publishes: list[dict[str, Any]] = []
    restores: list[dict[str, Any]] = []

    initial_updates = {"D": 650}
    initial_audit = {"audited_commit_updates": {"D": 650}}
    strict_audit = {"audited_commit_updates": {"B": 320}, "post_commit_live_worst_util": 0.9}

    def _solve(*_: Any, **kwargs: Any) -> dict[str, Any]:
        if case == "exception":
            raise RuntimeError("strict follow exploded")
        updates = {} if case == "no_updates" else {"B": 320, "lig_d": 8}
        return {"stop_reason": "strict_follow_stop", "final_updates": updates}

    def _sanitize(updates: dict[str, Any], **_: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        if case == "empty_sanitized":
            return {}, {}
        return {"B": updates.get("B"), "lig_d": updates.get("lig_d")}, {}

    def _passes(*_: Any, **__: Any) -> tuple[bool, str | None]:
        return (case == "accepted", None if case == "accepted" else "audit_failed")

    def _strict_ok(*_: Any, **__: Any) -> bool:
        return case == "accepted"

    try:
        module.SHARED_DEFAULTS = {"D": 0, "B": 0, "lig_d": 0}
        module._build_canonical_design_state_pack = lambda state: {"packed": dict(state)}
        module._overlay_current_normalized_shear_truth = lambda state: {"overlay": dict(state)}
        module._guidance_state_snapshot = lambda state: {"snap": dict(state)}
        module._shared_state_snapshot = lambda: {"D": 650, "B": 300, "lig_d": 6}
        module._solve_one_click_to_target = _solve
        module._sanitize_shared_update_bundle = _sanitize
        module._set_shared_updates = lambda updates, **kwargs: writes.append(
            {"updates": dict(updates), "kwargs": dict(kwargs)},
        )
        module._publish_current_normalized_shear_truth_coordinator = lambda stage, dbg: normalized.append(
            {"stage": stage, "dbg": dict(dbg)},
        )
        module._pop_inputs_widget_keys_for_shared_updates = lambda updates: popped.append(dict(updates))
        module._one_click_post_commit_audit = lambda updates: dict(strict_audit)
        module._collect_design_overview = lambda state: {
            "governing_util": 0.89 if case == "accepted" else 1.2,
            "statuses": {"bending": "PASS" if case == "accepted" else "FAIL"},
        }
        module._one_click_commit_audit_passes = _passes
        module._one_click_strict_target_band_ok = _strict_ok
        module.persist_active_beam_from_shared = lambda: persisted.append(True)
        module._invalidate_design_guide_caches = lambda **kwargs: invalidations.append(dict(kwargs))
        module.finalize_auto_design_publish = lambda **kwargs: publishes.append(dict(kwargs))
        module._restore_shared_state_snapshot = lambda snapshot, **kwargs: restores.append(
            {"snapshot": dict(snapshot), "kwargs": dict(kwargs)},
        )
        result = module._handle_auto_design_strict_followup_commit_coordinator(
            trace_run_id="run-123",
            dbg={"seed": "kept"},
            final_updates=dict(initial_updates),
            commit_audit=dict(initial_audit),
            commit_mode_config={"mode": "unit"},
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {
        "result": result,
        "writes": writes,
        "normalized": normalized,
        "popped": popped,
        "persisted": persisted,
        "invalidations": invalidations,
        "publishes": publishes,
        "restores": restores,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_auto_design_strict_followup_commit_coordinator",
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

    accepted = _run_case(module, case="accepted")
    rejected = _run_case(module, case="rejected")
    no_updates = _run_case(module, case="no_updates")
    exception = _run_case(module, case="exception")
    accepted_dbg = accepted["result"]["dbg"]
    rejected_dbg = rejected["result"]["dbg"]
    runtime_checks = {
        "accepted_followup_commits_and_replaces_audit": accepted_dbg.get("one_click_strict_followup_committed") is True
        and accepted_dbg.get("one_click_strict_followup_commit_audit") == {
            "audited_commit_updates": {"B": 320},
            "post_commit_live_worst_util": 0.9,
        }
        and accepted["result"]["final_updates"] == {"D": 650, "B": 320, "lig_d": 8}
        and accepted["result"]["commit_audit"].get("audited_commit_updates") == {"B": 320},
        "accepted_write_publish_and_cache_paths_preserved": accepted["writes"] == [
            {"updates": {"B": 320, "lig_d": 8}, "kwargs": {"source": "auto_design_commit_strict_followup"}},
        ]
        and accepted["normalized"][0]["stage"] == "run_one_click_auto_design:post_strict_followup_write"
        and accepted["popped"] == [{"B": 320, "lig_d": 8}]
        and accepted["persisted"] == [True]
        and accepted["invalidations"] == [
            {"reason": "one_click_auto_design:strict_followup", "updated_keys": ["B", "lig_d"]},
        ]
        and accepted["publishes"] == [
            {
                "updated_keys": ["B", "lig_d"],
                "source": "one_click_auto_design:strict_followup",
                "focus_section": "shear",
                "set_run_design_clicked": True,
            },
        ],
        "accepted_debug_fields_preserved": accepted_dbg.get("one_click_strict_followup_stop_reason")
        == "strict_follow_stop"
        and accepted_dbg.get("one_click_strict_followup_update_keys") == ["B", "lig_d"]
        and accepted_dbg.get("one_click_strict_post_commit_target_band_ok") is True
        and accepted_dbg.get("one_click_strict_post_commit_live_worst_util") == 0.89
        and accepted_dbg.get("one_click_strict_post_commit_statuses") == {"bending": "PASS"},
        "rejected_followup_rolls_back": rejected_dbg.get("one_click_strict_followup_committed") is False
        and rejected_dbg.get("one_click_strict_followup_reject_reason") == "audit_failed"
        and rejected["restores"] == [
            {
                "snapshot": {"D": 650, "B": 300, "lig_d": 6},
                "kwargs": {"source": "one_click_auto_design:rollback_strict_followup_failed_audit"},
            },
        ]
        and rejected["popped"] == [{"B": 320, "lig_d": 8}, {"D": 650, "B": 300, "lig_d": 6}]
        and rejected["result"]["final_updates"] == {"D": 650},
        "no_updates_does_not_write": no_updates["writes"] == []
        and no_updates["result"]["dbg"].get("one_click_strict_followup_update_keys") == [],
        "exception_is_captured": "strict follow exploded" in exception["result"]["dbg"].get(
            "one_click_strict_followup_exception",
            "",
        ),
    }
    static_checks = {
        "helper_present": "def _handle_auto_design_strict_followup_commit_coordinator(" in source,
        "helper_preserves_solver_trace_source": "one_click_followup_after_strict_band_mismatch" in helper,
        "helper_preserves_commit_source": "auto_design_commit_strict_followup" in helper,
        "helper_preserves_rollback_source": "rollback_strict_followup_failed_audit" in helper,
        "helper_returns_runner_state": '"final_updates": final_updates' in helper
        and '"commit_audit": commit_audit' in helper,
        "commit_orchestration_delegates_strict_followup": "_handle_auto_design_strict_followup_commit_coordinator("
        in commit_body,
        "commit_orchestration_delegates_partial_followup": "_handle_auto_design_partial_progress_followup_commit_coordinator("
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
        "surface": "run_one_click_auto_design_strict_followup_commit_coordinator",
        "helper_segment": {
            "function": "_handle_auto_design_strict_followup_commit_coordinator",
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
        "accepted_runtime": accepted,
        "rejected_runtime": rejected,
        "no_updates_runtime": no_updates,
        "exception_runtime": exception,
        "product_behavior_changed": False,
        "next_safe_slice": "extract partial-progress bending follow-up branch from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_strict_followup_commit_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_strict_followup_commit_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Strict Follow-Up Commit Coordinator Extraction",
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
