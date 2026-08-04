"""Verify dead local response bridge functions were removed from run_one_click_auto_design."""

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


DEAD_LOCAL_BRIDGES = (
    "_trace_run_end",
    "_attach_no_action_visibility",
    "_result_recommendation_envelope",
)


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
    bridge_usage: dict[str, dict[str, Any]] = {}
    for name in DEAD_LOCAL_BRIDGES:
        defs: list[int] = []
        calls: list[int] = []
        loads: list[int] = []
        for node in ast.walk(run):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                defs.append(int(node.lineno))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name:
                calls.append(int(node.lineno))
            if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load):
                loads.append(int(node.lineno))
        bridge_usage[name] = {"defs": defs, "calls": calls, "loads": loads}
    static_checks = {
        "dead_local_bridge_defs_removed": all(not data["defs"] for data in bridge_usage.values()),
        "dead_local_bridge_calls_absent": all(not data["calls"] for data in bridge_usage.values()),
        "dead_local_bridge_loads_absent": all(not data["loads"] for data in bridge_usage.values()),
        "response_coordinator_calls_remain": "_return_auto_design_default_no_action_response_coordinator(" in run_body
        and "_return_auto_design_ready_response_coordinator(" in run_body
        and "_return_auto_design_commit_rejected_response_coordinator(" in run_body,
    }
    status = "PASS" if all(static_checks.values()) else "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_dead_local_response_bridges_removed",
        "run_segment": {
            "function": "run_one_click_auto_design",
            "start_line": int(run.lineno),
            "end_line": int(run.end_lineno),
            "line_count": int(run.end_lineno - run.lineno + 1),
        },
        "bridge_usage": bridge_usage,
        "static_checks": static_checks,
        "product_behavior_changed": False,
        "next_safe_slice": "audit run_one_click_auto_design orchestration setup for next mechanical extraction",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_dead_local_response_bridges_removed_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_dead_local_response_bridges_removed_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Dead Local Response Bridges Removed",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Bridge Usage")
    for name, value in payload["bridge_usage"].items():
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
