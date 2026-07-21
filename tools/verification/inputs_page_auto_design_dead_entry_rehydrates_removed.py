"""Verify dead entry rehydrate assignments were removed from run_one_click_auto_design."""

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


DEAD_REHYDRATES = ("latch_owner", "request_source")


def _function_node(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"Function not found: {name}")


def build_payload() -> dict[str, Any]:
    source = AUTO_DESIGN_COMPUTE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    run = _function_node(tree, "run_one_click_auto_design")
    run_body = "\n".join(source.splitlines()[run.lineno - 1 : run.end_lineno])
    usage: dict[str, dict[str, Any]] = {}
    for name in DEAD_REHYDRATES:
        stores: list[int] = []
        loads: list[int] = []
        for node in ast.walk(run):
            if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Store):
                stores.append(int(node.lineno))
            if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load):
                loads.append(int(node.lineno))
        usage[name] = {"stores": stores, "loads": loads}
    stale_latch_keys: set[str] = set()
    for node in ast.walk(run):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "stale_latch_entry_state"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            stale_latch_keys.add(node.slice.value)
    static_checks = {
        "dead_rehydrate_stores_removed": all(not value["stores"] for value in usage.values()),
        "dead_rehydrate_loads_absent": all(not value["loads"] for value in usage.values()),
        "entry_state_live_fields_preserved": 'trace_run_id = run_entry_state["trace_run_id"]' in run_body
        and 'tracer_path = run_entry_state["tracer_path"]' in run_body
        and 'entry_source_norm = run_entry_state["entry_source_norm"]' in run_body,
        "stale_latch_live_fields_preserved": {
            "auto_design_stale_latch_cleared_at_entry",
            "auto_design_stale_latch_clear_reason",
        }.issubset(stale_latch_keys),
        "authority_helpers_still_called": "_start_one_click_auto_design_run_entry_coordinator(" in run_body
        and "_resolve_auto_design_stale_latch_entry_state_coordinator(" in run_body,
    }
    status = "PASS" if all(static_checks.values()) else "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_dead_entry_rehydrates_removed",
        "run_segment": {
            "function": "run_one_click_auto_design",
            "start_line": int(run.lineno),
            "end_line": int(run.end_lineno),
            "line_count": int(run.end_lineno - run.lineno + 1),
        },
        "usage": usage,
        "static_checks": static_checks,
        "product_behavior_changed": False,
        "next_safe_slice": "audit run_one_click_auto_design for the next mechanical orchestration extraction",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_dead_entry_rehydrates_removed_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_dead_entry_rehydrates_removed_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Dead Entry Rehydrates Removed",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Usage")
    for name, value in payload["usage"].items():
        lines.append(f"- `{name}`: `{value}`")
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
