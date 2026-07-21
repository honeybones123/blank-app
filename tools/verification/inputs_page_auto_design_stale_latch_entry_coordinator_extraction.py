"""Verify auto-design stale-latch entry coordinator extraction."""

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


def _run_case(module: Any, session_state: dict[str, Any], *, entry_source_norm: str) -> dict[str, Any]:
    original_st = getattr(module, "st", None)
    original_clear = getattr(module, "_clear_auto_design_runtime_latches", None)
    original_key = getattr(module, "AUTO_DESIGN_REQUEST_SOURCE_KEY", None)
    fake_st = _FakeStreamlit()
    fake_st.session_state.update(session_state)
    clears: list[str] = []

    def _clear(reason: str) -> dict[str, Any]:
        clears.append(reason)
        fake_st.session_state["_solver_running"] = False
        return {"reason": reason, "cleared": True}

    try:
        module.st = fake_st
        module.AUTO_DESIGN_REQUEST_SOURCE_KEY = "auto_design_request_source_key"
        module._clear_auto_design_runtime_latches = _clear
        result = module._resolve_auto_design_stale_latch_entry_state_coordinator(
            entry_source_norm=entry_source_norm,
        )
    finally:
        if original_st is not None:
            module.st = original_st
        if original_clear is not None:
            module._clear_auto_design_runtime_latches = original_clear
        if original_key is not None:
            module.AUTO_DESIGN_REQUEST_SOURCE_KEY = original_key

    return {
        "result": result,
        "clears": clears,
        "session_state": dict(fake_st.session_state),
    }


def _runtime() -> dict[str, Any]:
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    direct = _run_case(
        module,
        {
            "_solver_running": True,
            "_compute_in_progress": False,
            "auto_design_request_source": "primary_apply_button",
            "auto_design_latch_owner": "",
        },
        entry_source_norm="inputs_handle_auto_design",
    )
    owned = _run_case(
        module,
        {
            "_solver_running": True,
            "_compute_in_progress": False,
            "auto_design_request_source": "primary_apply_button",
            "auto_design_latch_owner": "handle_auto_design",
        },
        entry_source_norm="inputs_handle_auto_design",
    )
    compute_in_progress = _run_case(
        module,
        {
            "_solver_running": True,
            "_compute_in_progress": True,
            "auto_design_request_source": "primary_apply_button",
            "auto_design_latch_owner": "",
        },
        entry_source_norm="inputs_handle_auto_design",
    )
    fallback = _run_case(
        module,
        {
            "_solver_running": False,
            "_compute_in_progress": False,
            "auto_design_request_source_key": "run_one_click_auto_design",
        },
        entry_source_norm="inputs_handle_auto_design",
    )
    expected_reason = "run_one_click_auto_design:stale_solver_running_missing_owner"
    return {
        "direct": direct,
        "owned": owned,
        "compute_in_progress": compute_in_progress,
        "fallback": fallback,
        "checks": {
            "direct_clears_stale_unowned_latch": direct["clears"] == [expected_reason]
            and direct["result"]["auto_design_stale_latch_cleared_at_entry"] is True
            and direct["result"]["auto_design_stale_latch_clear_reason"] == expected_reason
            and direct["session_state"]["auto_design_stale_latch_cleared_at_entry"] is True,
            "owned_latch_not_cleared": owned["clears"] == []
            and owned["result"]["auto_design_stale_latch_cleared_at_entry"] is False
            and owned["session_state"]["auto_design_stale_latch_clear_reason"] == "",
            "compute_in_progress_not_cleared": compute_in_progress["clears"] == []
            and compute_in_progress["result"]["auto_design_stale_latch_cleared_at_entry"] is False,
            "fallback_request_source_used": fallback["result"]["request_source"] == "run_one_click_auto_design",
        },
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_resolve_auto_design_stale_latch_entry_state_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    runtime = _runtime()
    static_checks = {
        "helper_present": "def _resolve_auto_design_stale_latch_entry_state_coordinator(" in source,
        "helper_preserves_request_source_precedence": "auto_design_request_source" in helper
        and "AUTO_DESIGN_REQUEST_SOURCE_KEY" in helper
        and "entry_source_norm" in helper,
        "helper_preserves_direct_request_set": all(
            token in helper
            for token in [
                '"primary_apply_button"',
                '"run_one_click_auto_design"',
                '"inputs_handle_auto_design"',
            ]
        ),
        "helper_preserves_stale_clear_reason": (
            '"run_one_click_auto_design:stale_solver_running_missing_owner"' in helper
        ),
        "helper_writes_session_audit_flags": all(
            token in helper
            for token in [
                'st.session_state["auto_design_stale_latch_cleared_at_entry"]',
                'st.session_state["auto_design_stale_latch_clear_reason"]',
            ]
        ),
        "run_delegates_stale_latch_entry": "_resolve_auto_design_stale_latch_entry_state_coordinator(" in run_body,
        "run_omits_dead_request_source_rehydrate": 'request_source = stale_latch_entry_state["request_source"]'
        not in run_body,
        "run_keeps_latch_clear_adapter": "def _return_with_latch_clear(" in run_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime["checks"].values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_stale_latch_entry_coordinator",
        "helper_segment": {
            "function": "_resolve_auto_design_stale_latch_entry_state_coordinator",
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
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract the run skip-gate checks into a coordinator or remove the latch-clear nested adapter",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_stale_latch_entry_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_stale_latch_entry_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Stale-Latch Entry Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Runtime Checks")
    for key, value in payload["runtime"]["checks"].items():
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
