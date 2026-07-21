"""Verify one-click no-action visibility coordinator extraction."""

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


def _run_case(module: Any) -> dict[str, Any]:
    original = getattr(module, "_one_click_build_user_visible_no_action_fields", None)
    calls: list[dict[str, Any]] = []

    def _fake_visibility(stop_reason: str | None, dbg: dict) -> dict[str, str | None]:
        calls.append({"stop_reason": stop_reason, "dbg_seen": dict(dbg)})
        return {
            "user_visible_no_action_reason": f"reason:{stop_reason}",
            "user_visible_rejection_summary": "summary",
        }

    dbg = {"existing": True}
    try:
        module._one_click_build_user_visible_no_action_fields = _fake_visibility
        returned = module._attach_no_action_visibility_coordinator(
            stop_reason="no_actionable_candidates",
            dbg=dbg,
        )
    finally:
        if original is not None:
            module._one_click_build_user_visible_no_action_fields = original

    return {
        "returned": returned,
        "dbg": dbg,
        "calls": calls,
        "matches": (
            returned
            == {
                "user_visible_no_action_reason": "reason:no_actionable_candidates",
                "user_visible_rejection_summary": "summary",
            }
            and dbg.get("user_visible_no_action_reason") == "reason:no_actionable_candidates"
            and dbg.get("user_visible_rejection_summary") == "summary"
            and calls
            and calls[0]["stop_reason"] == "no_actionable_candidates"
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_attach_no_action_visibility_coordinator")
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _attach_no_action_visibility_coordinator(" in source,
        "helper_uses_existing_builder": "_one_click_build_user_visible_no_action_fields(stop_reason, dbg)" in helper,
        "helper_projects_debug_fields": all(
            token in helper
            for token in (
                'dbg["user_visible_no_action_reason"]',
                'dbg["user_visible_rejection_summary"]',
            )
        ),
        "nested_adapter_delegates": "_attach_no_action_visibility_coordinator(" in run_body,
        "nested_adapter_no_longer_projects_fields": 'dbg["user_visible_no_action_reason"] = uv' not in run_body,
        "return_call_sites_preserved": run_body.count("_attach_no_action_visibility()") >= 3,
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_no_action_visibility_coordinator",
        "helper_segment": {
            "function": "_attach_no_action_visibility_coordinator",
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
        "next_safe_slice": "extract another return-payload assembly block from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_no_action_visibility_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_no_action_visibility_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# One-Click No-Action Visibility Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Runtime", f"- Projection matches: `{payload['runtime']['matches']}`"])
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
