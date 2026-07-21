"""Verify auto-design commit write/audit setup coordinator extraction."""

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


def _run_case(module: Any, *, best_effort: bool) -> dict[str, Any]:
    originals = {
        "st": getattr(module, "st", None),
        "BEAM_STATUS_FAIL": getattr(module, "BEAM_STATUS_FAIL", None),
        "_set_shared_updates": getattr(module, "_set_shared_updates", None),
        "_publish_current_normalized_shear_truth_coordinator": getattr(
            module,
            "_publish_current_normalized_shear_truth_coordinator",
            None,
        ),
        "_shared_state_snapshot": getattr(module, "_shared_state_snapshot", None),
        "_int_from_state": getattr(module, "_int_from_state", None),
        "_record_one_click_shear_publish_audit": getattr(
            module,
            "_record_one_click_shear_publish_audit",
            None,
        ),
        "_pop_inputs_widget_keys_for_shared_updates": getattr(
            module,
            "_pop_inputs_widget_keys_for_shared_updates",
            None,
        ),
        "_one_click_post_commit_audit": getattr(module, "_one_click_post_commit_audit", None),
    }
    fake_st = _FakeStreamlit()
    writes: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    popped: list[dict[str, Any]] = []

    commit_audit = {
        "post_commit_matches_intended_updates": True,
        "audited_commit_updates": {"D": 650},
        "ignored_commit_update_keys": ["ignored"],
        "has_row_model_updates": True,
        "ignored_row_model_legacy_mirror_keys": ["legacy"],
        "post_commit_mismatch_keys": ["mismatch"],
        "post_commit_mismatch_details": {"mismatch": "detail"},
        "post_commit_live_worst_util": 0.91,
        "post_commit_live_statuses": {"shear": "PASS"},
    }

    try:
        module.st = fake_st
        module.BEAM_STATUS_FAIL = "FAIL"
        module._set_shared_updates = lambda updates, **kwargs: writes.append(
            {"updates": dict(updates), "kwargs": dict(kwargs)},
        )
        module._publish_current_normalized_shear_truth_coordinator = lambda stage, dbg: normalized.append(
            {"stage": stage, "dbg": dict(dbg)},
        )
        module._shared_state_snapshot = lambda: {"lig_legs": 0, "lig_d": 0}
        module._int_from_state = lambda state, key, default=0: int(state.get(key, default) or 0)
        module._record_one_click_shear_publish_audit = lambda **kwargs: audits.append(dict(kwargs))
        module._pop_inputs_widget_keys_for_shared_updates = lambda updates: popped.append(dict(updates))
        module._one_click_post_commit_audit = lambda updates: dict(commit_audit)
        result = module._apply_auto_design_commit_write_audit_setup_coordinator(
            final_updates={"D": 650, "lig_d": 0},
            dbg={"seed": "kept"},
            stop_reason="best_available_out_of_band_candidate" if best_effort else "target_reached",
            current_overview={"statuses": {"shear": "FAIL" if best_effort else "PASS"}},
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
        "audits": audits,
        "popped": popped,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_apply_auto_design_commit_write_audit_setup_coordinator",
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

    best_runtime = _run_case(module, best_effort=True)
    normal_runtime = _run_case(module, best_effort=False)
    best_dbg = best_runtime["result"]["dbg"]
    session_payload = best_runtime["session_state"].get("_one_click_post_commit_audit_latest") or {}
    runtime_checks = {
        "shared_write_preserved": best_runtime["writes"] == [
            {"updates": {"D": 650, "lig_d": 0}, "kwargs": {"source": "auto_design_commit"}},
        ],
        "normalized_shear_truth_publish_preserved": best_runtime["normalized"][0]["stage"]
        == "run_one_click_auto_design:post_current_eval:post_commit_write",
        "no_links_commit_probe_preserved": best_dbg.get("final_no_links_candidate_committed") is True,
        "final_commit_publish_audit_preserved": best_runtime["audits"] == [
            {
                "stage": "final_commit_publish",
                "source": "auto_design_commit",
                "candidate_updates": {"D": 650, "lig_d": 0},
                "publish_attempted": True,
                "publish_blocked": False,
            },
        ],
        "widget_key_pop_preserved": best_runtime["popped"] == [{"D": 650, "lig_d": 0}],
        "commit_audit_debug_fields_preserved": best_dbg.get("one_click_commit_audit", {}).get(
            "post_commit_matches_intended_updates",
        )
        is True
        and best_dbg.get("audited_commit_updates") == {"D": 650}
        and best_dbg.get("ignored_commit_update_keys") == ["ignored"]
        and best_dbg.get("has_row_model_updates") is True
        and best_dbg.get("ignored_row_model_legacy_mirror_keys") == ["legacy"]
        and best_dbg.get("post_commit_mismatch_keys") == ["mismatch"]
        and best_dbg.get("post_commit_mismatch_details") == {"mismatch": "detail"}
        and best_dbg.get("post_commit_live_worst_util") == 0.91
        and best_dbg.get("post_commit_live_statuses") == {"shear": "PASS"},
        "best_effort_flag_preserved": best_dbg.get("one_click_best_effort_cleanup_commit") is True
        and normal_runtime["result"]["dbg"].get("one_click_best_effort_cleanup_commit") is False,
        "session_payload_preserved": session_payload == {
            "post_commit_matches_intended_updates": True,
            "post_commit_mismatch_keys": ["mismatch"],
            "ignored_commit_update_keys": ["ignored"],
            "has_row_model_updates": True,
            "ignored_row_model_legacy_mirror_keys": ["legacy"],
            "post_commit_live_worst_util": 0.91,
            "post_commit_live_statuses": {"shear": "PASS"},
        },
        "returns_runner_audit": best_runtime["result"]["commit_audit"].get("audited_commit_updates") == {"D": 650},
    }
    static_checks = {
        "helper_present": "def _apply_auto_design_commit_write_audit_setup_coordinator(" in source,
        "helper_preserves_shared_write": "_set_shared_updates(final_updates, source=\"auto_design_commit\")" in helper,
        "helper_preserves_normalized_publish": "post_commit_write" in helper,
        "helper_preserves_no_links_probe": "final_no_links_candidate_committed" in helper,
        "helper_preserves_post_commit_audit_session_payload": "_one_click_post_commit_audit_latest" in helper,
        "helper_returns_commit_audit": '"commit_audit": commit_audit' in helper,
        "commit_orchestration_delegates_commit_write_setup": "_apply_auto_design_commit_write_audit_setup_coordinator("
        in commit_body,
        "commit_orchestration_owns_audit_pass_gate": "_one_click_commit_audit_passes("
        in commit_body,
        "commit_orchestration_owns_rejection_branch": "if not passes:" in commit_body
        and "_handle_auto_design_commit_rejected_rollback_coordinator(" in commit_body,
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
        "surface": "run_one_click_auto_design_commit_write_audit_setup_coordinator",
        "helper_segment": {
            "function": "_apply_auto_design_commit_write_audit_setup_coordinator",
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
        "best_effort_runtime": best_runtime,
        "normal_runtime": normal_runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract commit rejected rollback branch from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_commit_write_audit_setup_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_commit_write_audit_setup_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Commit Write/Audit Setup Coordinator Extraction",
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
