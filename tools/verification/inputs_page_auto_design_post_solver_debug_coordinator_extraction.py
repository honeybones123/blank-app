"""Verify auto-design post-solver debug coordinator extraction."""

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
        self.session_state: dict[str, Any] = {
            "auto_design_latch_owner": "owner-a",
            "auto_design_invoke_consumed": True,
        }


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


def _run_case(module: Any, *, overview_raises: bool = False) -> dict[str, Any]:
    originals = {
        "st": getattr(module, "st", None),
        "BEAM_STATUS_FAIL": getattr(module, "BEAM_STATUS_FAIL", None),
        "_coherence_debug_fields": getattr(module, "_coherence_debug_fields", None),
        "_auto_design_invoke_debug_snapshot": getattr(module, "_auto_design_invoke_debug_snapshot", None),
        "_collect_design_overview": getattr(module, "_collect_design_overview", None),
        "_current_design_guide_fail_fingerprint": getattr(module, "_current_design_guide_fail_fingerprint", None),
    }

    raw_coherence = {
        "coherence_ok": True,
        "issues": ["raw-issue"],
        "coherence_blocking_issues": ["raw-block"],
        "coherence_nonblocking_issues": ["raw-note"],
        "coherence_should_block": False,
        "state_coherence_warning": True,
        "state_coherence_warning_issues": ["raw-warning"],
    }
    canonical_coherence = {"coherence_ok": True}
    current_state = {
        "canonical_pack_built": True,
        "canonical_pack_source": "unit-pack",
    }

    def _overview(state: dict[str, Any]) -> dict[str, Any]:
        if overview_raises:
            raise RuntimeError("overview unavailable")
        return {"statuses": {"bending": "FAIL", "shear": "PASS"}}

    try:
        module.st = _FakeStreamlit()
        module.BEAM_STATUS_FAIL = "FAIL"
        module._coherence_debug_fields = lambda coherence: {
            "state_coherence_ok": bool(coherence.get("coherence_ok")),
        }
        module._auto_design_invoke_debug_snapshot = lambda: {"invoke_debug": "yes"}
        module._collect_design_overview = _overview
        module._current_design_guide_fail_fingerprint = lambda overview: {"bending": "FAIL"}
        dbg = module._build_auto_design_post_solver_debug_coordinator(
            solve={"one_click_solver_debug": {"seed": "kept"}},
            trace_run_id="trace-123",
            tracer_path="trace.jsonl",
            raw_coherence=raw_coherence,
            current_state=current_state,
            canonical_coherence=canonical_coherence,
            canonical_pack_valid=True,
            canonical_pack_error=None,
            canonical_pack_error_stage=None,
            entry_source_norm="inputs_handle_auto_design",
            solver_running_bypassed=True,
            one_click_run_feedback_cleared_at_entry=True,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {"debug": dbg}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_build_auto_design_post_solver_debug_coordinator",
    )
    _, _, post_solver_commit_body = _function_segment(
        source,
        "_run_auto_design_post_solver_commit_orchestration_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    fallback_runtime = _run_case(module, overview_raises=True)
    dbg = runtime["debug"]
    fallback_dbg = fallback_runtime["debug"]
    runtime_checks = {
        "keeps_existing_solver_debug": dbg.get("seed") == "kept",
        "trace_fields": dbg.get("trace_run_id") == "trace-123"
        and dbg.get("design_guide_tracer_path") == "trace.jsonl"
        and dbg.get("tracer_entry_reached") is True,
        "coherence_fields": dbg.get("state_coherence_ok_before_rebuild") is True
        and dbg.get("state_coherence_issues_before_rebuild") == ["raw-issue"]
        and dbg.get("coherence_blocking_issues_before_rebuild") == ["raw-block"],
        "canonical_fields": dbg.get("canonical_pack_built") is True
        and dbg.get("canonical_pack_valid") is True
        and dbg.get("canonical_pack_source") == "unit-pack",
        "session_fields": dbg.get("auto_design_latch_owner") == "owner-a"
        and dbg.get("auto_design_invoke_consumed") is True
        and dbg.get("run_one_click_solver_running_bypassed") is True,
        "default_commit_fields": dbg.get("one_click_commit_blocked_reason") is None
        and dbg.get("one_click_final_candidate_valid_reason") == "missing_candidate"
        and dbg.get("final_no_links_candidate_committed") is False,
        "fail_keys_collected": dbg.get("current_fail_keys") == ["bending"]
        and dbg.get("current_fail_fingerprint") == {"bending": "FAIL"},
        "fail_key_fallback": fallback_dbg.get("current_fail_keys_source") == "canonical_overview"
        and fallback_dbg.get("current_fail_fingerprint") == {}
        and fallback_dbg.get("current_fail_keys") == [],
    }
    static_checks = {
        "helper_present": "def _build_auto_design_post_solver_debug_coordinator(" in source,
        "helper_starts_from_solver_debug": 'dict(solve.get("one_click_solver_debug") or {})' in helper,
        "helper_preserves_coherence_fields": "state_coherence_ok_before_rebuild" in helper
        and "coherence_blocking_issues_before_rebuild" in helper,
        "helper_preserves_commit_defaults": "one_click_final_candidate_valid_reason" in helper
        and "final_no_links_candidate_committed" in helper,
        "helper_collects_fail_keys": "_collect_design_overview(current_state)" in helper,
        "run_delegates_post_solver_debug": "_build_auto_design_post_solver_debug_coordinator(" in run_body,
        "run_delegates_post_solver_commit_orchestration": (
            "_run_auto_design_post_solver_commit_orchestration_coordinator(" in run_body
        ),
        "post_solver_commit_delegates_commit_seed_variables": (
            "_prepare_auto_design_post_solver_response_seed_coordinator(" in post_solver_commit_body
            and 'commit_audit: dict | None = post_solver_response_seed["commit_audit"]'
            in post_solver_commit_body
            and 'solver_final_updates = post_solver_response_seed["solver_final_updates"]'
            in post_solver_commit_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_post_solver_debug_coordinator",
        "helper_segment": {
            "function": "_build_auto_design_post_solver_debug_coordinator",
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
        "fallback_runtime": fallback_runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract final-updates current-fail-context enrichment from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_post_solver_debug_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_post_solver_debug_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Post-Solver Debug Coordinator Extraction",
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
