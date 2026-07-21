"""Verify auto-design partial-progress follow-up commit coordinator extraction."""

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


def _run_case(module: Any, *, case: str) -> dict[str, Any]:
    originals = {
        "st": getattr(module, "st", None),
        "SHARED_DEFAULTS": getattr(module, "SHARED_DEFAULTS", None),
        "_build_canonical_design_state_pack": getattr(module, "_build_canonical_design_state_pack", None),
        "_overlay_current_normalized_shear_truth": getattr(module, "_overlay_current_normalized_shear_truth", None),
        "_guidance_state_snapshot": getattr(module, "_guidance_state_snapshot", None),
        "_shared_state_snapshot": getattr(module, "_shared_state_snapshot", None),
        "_solve_one_click_to_target": getattr(module, "_solve_one_click_to_target", None),
        "evaluate_candidate_full": getattr(module, "evaluate_candidate_full", None),
        "_sanitize_shared_update_bundle": getattr(module, "_sanitize_shared_update_bundle", None),
        "_collect_design_overview": getattr(module, "_collect_design_overview", None),
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
        "_one_click_commit_audit_passes": getattr(module, "_one_click_commit_audit_passes", None),
        "persist_active_beam_from_shared": getattr(module, "persist_active_beam_from_shared", None),
        "_invalidate_design_guide_caches": getattr(module, "_invalidate_design_guide_caches", None),
        "finalize_auto_design_publish": getattr(module, "finalize_auto_design_publish", None),
        "_restore_shared_state_snapshot": getattr(module, "_restore_shared_state_snapshot", None),
    }
    fake_st = _FakeStreamlit()
    writes: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    popped: list[dict[str, Any]] = []
    persisted: list[bool] = []
    invalidations: list[dict[str, Any]] = []
    publishes: list[dict[str, Any]] = []
    restores: list[dict[str, Any]] = []
    eval_sources: list[str] = []
    initial_updates = {"D": 650}
    initial_audit = {"audited_commit_updates": {"D": 650}}
    follow_audit = {
        "post_commit_matches_intended_updates": True,
        "audited_commit_updates": {"B": 320},
        "ignored_commit_update_keys": ["ignored"],
        "has_row_model_updates": True,
        "ignored_row_model_legacy_mirror_keys": ["legacy"],
        "post_commit_mismatch_keys": ["B"],
        "post_commit_mismatch_details": {"B": "updated"},
        "post_commit_live_worst_util": 0.86,
        "post_commit_live_statuses": {"bending": "PASS", "shear": "PASS"},
    }

    def _solve(*_: Any, **kwargs: Any) -> dict[str, Any]:
        if case == "exception":
            raise RuntimeError("followup exploded")
        return {
            "stop_reason": "reached_target_band" if case == "accepted" else "still_iterating",
            "final_updates": {} if case == "no_updates" else {"B": 320, "lig_d": 8},
        }

    def _evaluate(state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        source = str(kwargs.get("source") or "")
        eval_sources.append(source)
        if source == "one_click_followup_bending_gate":
            return {"overview": {"statuses": {"bending": "FAIL" if case == "bending_fail" else "PASS"}}}
        if source == "one_click_followup_pre_commit_worst":
            return {"overview": {"worst_util": 1.08}}
        return {"overview": {"worst_util": 1.0}}

    def _passes(*_: Any, **__: Any) -> tuple[bool, str | None]:
        return (case == "accepted", None if case == "accepted" else "follow_audit_failed")

    try:
        module.st = fake_st
        module.SHARED_DEFAULTS = {"D": 0, "B": 0, "lig_d": 0}
        module._build_canonical_design_state_pack = lambda state: {"packed": dict(state)}
        module._overlay_current_normalized_shear_truth = lambda state: {"overlay": dict(state)}
        module._guidance_state_snapshot = lambda state: {"snap": dict(state)}
        module._shared_state_snapshot = lambda: {"D": 650, "B": 300, "lig_d": 6}
        module._solve_one_click_to_target = _solve
        module.evaluate_candidate_full = _evaluate
        module._sanitize_shared_update_bundle = lambda updates, **kwargs: (
            {"B": updates.get("B"), "lig_d": updates.get("lig_d")},
            {},
        )
        module._collect_design_overview = lambda state: {"worst_util": 1.17}
        module._set_shared_updates = lambda updates, **kwargs: writes.append(
            {"updates": dict(updates), "kwargs": dict(kwargs)},
        )
        module._publish_current_normalized_shear_truth_coordinator = lambda stage, dbg: normalized.append(
            {"stage": stage, "dbg": dict(dbg)},
        )
        module._pop_inputs_widget_keys_for_shared_updates = lambda updates: popped.append(dict(updates))
        module._one_click_post_commit_audit = lambda updates: dict(follow_audit)
        module._one_click_commit_audit_passes = _passes
        module.persist_active_beam_from_shared = lambda: persisted.append(True)
        module._invalidate_design_guide_caches = lambda **kwargs: invalidations.append(dict(kwargs))
        module.finalize_auto_design_publish = lambda **kwargs: publishes.append(dict(kwargs))
        module._restore_shared_state_snapshot = lambda snapshot, **kwargs: restores.append(
            {"snapshot": dict(snapshot), "kwargs": dict(kwargs)},
        )
        dbg = {"seed": "kept"}
        if case != "no_gate":
            dbg["one_click_partial_progress_commit"] = True
            dbg["candidate_remaining_fail_keys"] = ["bending"]
        result = module._handle_auto_design_partial_progress_followup_commit_coordinator(
            trace_run_id="run-123",
            dbg=dbg,
            final_updates=dict(initial_updates),
            commit_audit=dict(initial_audit),
            stop_reason="initial_stop",
            fin_u=1.2,
            reached=False,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {
        "result": result,
        "session_state": dict(fake_st.session_state),
        "writes": writes,
        "normalized": normalized,
        "popped": popped,
        "persisted": persisted,
        "invalidations": invalidations,
        "publishes": publishes,
        "restores": restores,
        "eval_sources": eval_sources,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_auto_design_partial_progress_followup_commit_coordinator",
    )
    success_start, success_end, success_helper = _function_segment(
        source,
        "_apply_auto_design_partial_followup_commit_success_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    _, _, commit_body = _function_segment(
        source,
        "_run_auto_design_commit_orchestration_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    accepted = _run_case(module, case="accepted")
    rejected = _run_case(module, case="rejected")
    bending_fail = _run_case(module, case="bending_fail")
    no_gate = _run_case(module, case="no_gate")
    exception = _run_case(module, case="exception")
    accepted_dbg = accepted["result"]["dbg"]
    rejected_dbg = rejected["result"]["dbg"]
    session_payload = accepted["session_state"].get("_one_click_post_commit_audit_latest") or {}
    runtime_checks = {
        "accepted_followup_commits_and_updates_runner_state": accepted_dbg.get("one_click_followup_committed") is True
        and accepted["result"]["final_updates"] == {"D": 650, "B": 320, "lig_d": 8}
        and accepted["result"]["commit_audit"].get("audited_commit_updates") == {"B": 320}
        and accepted["result"]["stop_reason"] == "reached_target_band"
        and accepted["result"]["fin_u"] == 0.86
        and accepted["result"]["reached"] is True,
        "accepted_write_publish_and_cache_paths_preserved": accepted["writes"] == [
            {"updates": {"B": 320, "lig_d": 8}, "kwargs": {"source": "auto_design_commit_followup"}},
        ]
        and accepted["normalized"][0]["stage"] == "run_one_click_auto_design:post_followup_write"
        and accepted["popped"] == [{"B": 320, "lig_d": 8}]
        and accepted["persisted"] == [True]
        and accepted["invalidations"] == [
            {"reason": "one_click_auto_design:followup", "updated_keys": ["B", "lig_d"]},
        ]
        and accepted["publishes"] == [
            {
                "updated_keys": ["B", "lig_d"],
                "source": "one_click_auto_design:followup",
                "focus_section": "shear",
                "set_run_design_clicked": True,
            },
        ],
        "accepted_debug_and_session_fields_preserved": accepted_dbg.get("one_click_followup_stop_reason")
        == "reached_target_band"
        and accepted_dbg.get("one_click_followup_update_keys") == ["B", "lig_d"]
        and accepted_dbg.get("one_click_followup_post_commit_live_statuses") == {
            "bending": "PASS",
            "shear": "PASS",
        }
        and accepted_dbg.get("post_commit_live_worst_util") == 0.86
        and session_payload == {
            "post_commit_matches_intended_updates": True,
            "post_commit_mismatch_keys": ["B"],
            "ignored_commit_update_keys": ["ignored"],
            "has_row_model_updates": True,
            "ignored_row_model_legacy_mirror_keys": ["legacy"],
            "post_commit_live_worst_util": 0.86,
            "post_commit_live_statuses": {"bending": "PASS", "shear": "PASS"},
        },
        "accepted_gate_sources_preserved": accepted["eval_sources"] == [
            "one_click_followup_bending_gate",
            "one_click_followup_pre_commit_worst",
        ],
        "rejected_followup_rolls_back": rejected_dbg.get("one_click_followup_committed") is False
        and rejected_dbg.get("one_click_followup_reject_reason") == "follow_audit_failed"
        and rejected["restores"] == [
            {
                "snapshot": {"D": 650, "B": 300, "lig_d": 6},
                "kwargs": {"source": "one_click_auto_design:rollback_followup_failed_audit"},
            },
        ]
        and rejected["popped"] == [{"B": 320, "lig_d": 8}, {"D": 650, "B": 300, "lig_d": 6}]
        and rejected["result"]["final_updates"] == {"D": 650},
        "bending_fail_blocks_commit": bending_fail["writes"] == []
        and bending_fail["result"]["dbg"].get("one_click_followup_update_keys") == ["B", "lig_d"],
        "no_gate_is_noop": no_gate["writes"] == []
        and no_gate["result"]["final_updates"] == {"D": 650}
        and no_gate["result"]["stop_reason"] == "initial_stop",
        "exception_is_captured": "followup exploded" in exception["result"]["dbg"].get(
            "one_click_followup_exception",
            "",
        ),
    }
    static_checks = {
        "helper_present": "def _handle_auto_design_partial_progress_followup_commit_coordinator(" in source,
        "helper_preserves_solver_trace_source": "one_click_followup_after_partial_shear" in helper,
        "helper_preserves_bending_gate": "one_click_followup_bending_gate" in helper,
        "helper_preserves_pre_commit_worst": "one_click_followup_pre_commit_worst" in helper,
        "helper_preserves_commit_source": "auto_design_commit_followup" in helper,
        "helper_preserves_rollback_source": "rollback_followup_failed_audit" in helper,
        "helper_delegates_success_path": (
            "_apply_auto_design_partial_followup_commit_success_coordinator(" in helper
        ),
        "success_helper_preserves_publish_source": "one_click_auto_design:followup" in success_helper,
        "success_helper_preserves_session_audit": (
            '_one_click_post_commit_audit_latest' in success_helper
        ),
        "helper_returns_runner_state": '"stop_reason": stop_reason' in helper
        and '"fin_u": fin_u' in helper
        and '"reached": bool(reached)' in helper,
        "commit_orchestration_delegates_partial_followup": "_handle_auto_design_partial_progress_followup_commit_coordinator("
        in commit_body,
        "run_no_longer_owns_partial_followup_solver": "one_click_followup_after_partial_shear" not in run_body,
        "run_delegates_final_tail": (
            "_finish_auto_design_post_current_eval_and_dispatch_coordinator(" in run_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_partial_progress_followup_commit_coordinator",
        "helper_segment": {
            "function": "_handle_auto_design_partial_progress_followup_commit_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "success_helper_segment": {
            "function": "_apply_auto_design_partial_followup_commit_success_coordinator",
            "start_line": success_start,
            "end_line": success_end,
            "line_count": success_end - success_start + 1,
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
        "bending_fail_runtime": bending_fail,
        "no_gate_runtime": no_gate,
        "exception_runtime": exception,
        "product_behavior_changed": False,
        "next_safe_slice": "extract post-current-eval publication and base steps setup from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_partial_progress_followup_commit_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_partial_progress_followup_commit_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Partial-Progress Follow-Up Commit Coordinator Extraction",
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
