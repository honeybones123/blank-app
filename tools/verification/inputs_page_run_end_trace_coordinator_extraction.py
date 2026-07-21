"""Verify run-one-click run-end trace coordinator extraction."""

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


def _run_case(module: Any, *, use_commit_audit: bool) -> dict[str, Any]:
    traces: list[dict[str, Any]] = []
    original_trace = getattr(module, "_append_design_guide_trace", None)
    original_compare = getattr(module, "_design_guide_trace_compare_meta", None)
    original_collect = getattr(module, "_collect_design_overview", None)
    original_snapshot = getattr(module, "_guidance_state_snapshot", None)
    original_shared = getattr(module, "_shared_state_snapshot", None)

    def _append_trace(event: str, data: dict, *, run_id: str | None = None, source: str | None = None) -> None:
        traces.append({"event": event, "data": dict(data or {}), "run_id": run_id, "source": source})

    def _compare(**kwargs: Any) -> dict[str, Any]:
        return {"compare_kwargs": dict(kwargs)}

    def _collect(_state: dict) -> dict[str, Any]:
        return {"governing_util": 0.92, "statuses": {"bending": "PASS", "shear": "PASS"}}

    try:
        module._append_design_guide_trace = _append_trace
        module._design_guide_trace_compare_meta = _compare
        module._collect_design_overview = _collect
        module._guidance_state_snapshot = lambda state: dict(state or {})
        module._shared_state_snapshot = lambda: {"D": 600}
        commit_audit = (
            {
                "post_commit_matches_intended_updates": True,
                "post_commit_live_worst_util": 0.88,
                "post_commit_live_statuses": {"bending": "PASS"},
            }
            if use_commit_audit
            else None
        )
        module._trace_run_end_coordinator(
            "ready",
            commit_audit=commit_audit,
            init_u="1.1",
            fin_u="0.9",
            commit_rejected=False,
            commit_reject_reason=None,
            dbg={"pre_commit_worst_util": 1.05},
            trace_run_id="trace-002",
            action_sig="action-abc",
            goal="balanced",
            stop_reason="reached_target_band",
            win_l="Winner",
            final_updates={"D": 650},
            trace_src="run_one_click_auto_design",
        )
    finally:
        if original_trace is not None:
            module._append_design_guide_trace = original_trace
        if original_compare is not None:
            module._design_guide_trace_compare_meta = original_compare
        if original_collect is not None:
            module._collect_design_overview = original_collect
        if original_snapshot is not None:
            module._guidance_state_snapshot = original_snapshot
        if original_shared is not None:
            module._shared_state_snapshot = original_shared

    data = dict(traces[0]["data"] or {}) if traces else {}
    return {
        "use_commit_audit": use_commit_audit,
        "trace_event": traces[0]["event"] if traces else None,
        "run_id": traces[0]["run_id"] if traces else None,
        "source": traces[0]["source"] if traces else None,
        "final_live_worst_util": data.get("final_live_worst_util"),
        "post_commit_live_statuses": data.get("post_commit_live_statuses"),
        "commit_matched_intended_updates": data.get("commit_matched_intended_updates"),
        "compare": data.get("compare"),
        "matches": (
            bool(traces)
            and traces[0]["event"] == "run_end"
            and traces[0]["run_id"] == "trace-002"
            and traces[0]["source"] == "run_one_click_auto_design"
            and data.get("overall_result_status") == "ready"
            and data.get("stop_reason") == "reached_target_band"
            and data.get("pre_commit_worst_util") == 1.05
            and (
                (use_commit_audit and data.get("final_live_worst_util") == 0.88)
                or ((not use_commit_audit) and data.get("final_live_worst_util") == 0.92)
            )
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_trace_run_end_coordinator")
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    rows = [_run_case(module, use_commit_audit=True), _run_case(module, use_commit_audit=False)]
    static_checks = {
        "helper_present": "def _trace_run_end_coordinator(" in source,
        "helper_contains_trace_payload": all(
            token in helper
            for token in (
                "run_end",
                "final_live_worst_util",
                "commit_matched_intended_updates",
                "_design_guide_trace_compare_meta(",
            )
        ),
        "nested_trace_body_removed": "match_ok = None" not in run_body
        and "_collect_design_overview(_guidance_state_snapshot(_shared_state_snapshot()))" not in run_body,
        "run_nested_adapter_delegates": "_trace_run_end_coordinator(" in run_body,
        "run_call_sites_preserved": run_body.count("_trace_run_end(") >= 7,
    }
    status = "PASS"
    if not all(static_checks.values()) or any(not row["matches"] for row in rows):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_run_end_trace_coordinator",
        "helper_segment": {
            "function": "_trace_run_end_coordinator",
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
        "runtime_rows": rows,
        "product_behavior_changed": False,
        "next_safe_slice": "extract the recommendation-envelope or no-action visibility helper from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_run_end_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_run_end_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Run One-Click Run-End Trace Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Runtime Rows"])
    for row in payload["runtime_rows"]:
        lines.append(f"- `use_commit_audit={row['use_commit_audit']}`: `{row['matches']}`")
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
