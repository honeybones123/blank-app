"""Verify one-click latch-clear return coordinator extraction."""

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


def _run_dict_payload_case(module: Any) -> dict[str, Any]:
    original = getattr(module, "_clear_auto_design_runtime_latches", None)
    calls: list[str] = []

    def _fake_clear(reason: str) -> dict[str, Any]:
        calls.append(reason)
        return {"reason": reason, "cleared": True}

    payload: dict[str, Any] = {"status": "ready"}
    try:
        module._clear_auto_design_runtime_latches = _fake_clear
        returned = module._return_with_latch_clear_coordinator(
            reason="unit-test-ready",
            payload=payload,
            auto_design_stale_latch_cleared_at_entry=True,
            auto_design_stale_latch_clear_reason="stale-owner",
        )
    finally:
        if original is not None:
            module._clear_auto_design_runtime_latches = original

    return {
        "returned": returned,
        "payload": payload,
        "calls": calls,
        "matches": (
            returned is payload
            and calls == ["unit-test-ready"]
            and payload.get("status") == "ready"
            and payload.get("auto_design_latch_clear") == {"reason": "unit-test-ready", "cleared": True}
            and payload.get("auto_design_stale_latch_cleared_at_entry") is True
            and payload.get("auto_design_stale_latch_clear_reason") == "stale-owner"
        ),
    }


def _run_non_dict_payload_case(module: Any) -> dict[str, Any]:
    original = getattr(module, "_clear_auto_design_runtime_latches", None)
    calls: list[str] = []

    def _fake_clear(reason: str) -> dict[str, Any]:
        calls.append(reason)
        return {"reason": reason}

    payload = ["unchanged"]
    try:
        module._clear_auto_design_runtime_latches = _fake_clear
        returned = module._return_with_latch_clear_coordinator(
            reason="unit-test-list",
            payload=payload,
            auto_design_stale_latch_cleared_at_entry=False,
            auto_design_stale_latch_clear_reason="",
        )
    finally:
        if original is not None:
            module._clear_auto_design_runtime_latches = original

    return {
        "returned": returned,
        "payload": payload,
        "calls": calls,
        "matches": returned is payload and payload == ["unchanged"] and calls == ["unit-test-list"],
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_return_with_latch_clear_coordinator")
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = {
        "dict_payload": _run_dict_payload_case(module),
        "non_dict_payload": _run_non_dict_payload_case(module),
    }
    static_checks = {
        "helper_present": "def _return_with_latch_clear_coordinator(" in source,
        "helper_calls_existing_latch_clear": "_clear_auto_design_runtime_latches(reason)" in helper,
        "helper_projects_expected_payload_fields": all(
            token in helper
            for token in (
                "auto_design_latch_clear",
                "auto_design_stale_latch_cleared_at_entry",
                "auto_design_stale_latch_clear_reason",
            )
        ),
        "helper_preserves_non_dict_guard": "if isinstance(payload, dict):" in helper,
        "nested_adapter_delegates": "_return_with_latch_clear_coordinator(" in run_body,
        "nested_adapter_passes_closure_state_explicitly": all(
            token in run_body
            for token in (
                "auto_design_stale_latch_cleared_at_entry=auto_design_stale_latch_cleared_at_entry",
                "auto_design_stale_latch_clear_reason=auto_design_stale_latch_clear_reason",
            )
        ),
        "return_call_sites_preserved": run_body.count("_return_with_latch_clear(") >= 8,
    }
    status = "PASS"
    if not all(static_checks.values()) or any(not row["matches"] for row in runtime.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_latch_clear_return_coordinator",
        "helper_segment": {
            "function": "_return_with_latch_clear_coordinator",
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
        "next_safe_slice": "remove another nested run helper adapter or build the solver phase parity harness",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_latch_clear_return_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_latch_clear_return_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# One-Click Latch-Clear Return Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Runtime"])
    for key, row in payload["runtime"].items():
        lines.append(f"- `{key}`: `{row['matches']}`")
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
