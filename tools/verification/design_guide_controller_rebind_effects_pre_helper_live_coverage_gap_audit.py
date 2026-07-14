"""Audit live coverage gap for pre-helper rebind parity traces.

This is audit-only. It records whether the latest browser/live parity snapshot
failed because of actual controller mismatch or because no sampled live recipe
entered the two old render-panel rebind branches.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

LIVE_PREFIX = "design_guide_controller_rebind_effects_pre_helper_browser_live_parity"
STATIC_PREFIX = "design_guide_controller_rebind_effects_pre_helper_cutover_parity_trace"
REQUIRED_CALLSITES = (
    "combined_evidence_rebind_bridge",
    "engine_evidence_rebind_bridge",
)
BRANCH_TOKENS = {
    "combined_evidence_rebind_bridge": (
        "_combined_rebind_predicates = {",
        '"engine_evidence_family_is_combined"',
        '"engine_evidence_updates_present"',
        '"displayed_contract_updates_differ"',
        '"updates_not_already_applied"',
        '"cleanup_search_evidence_present"',
        '"displayed_primary_item_is_dict"',
    ),
    "engine_evidence_rebind_bridge": (
        "_engine_rebind_predicates = {",
        '"engine_evidence_family_is_combined"',
        '"engine_evidence_updates_present"',
        '"engine_contract_updates_differ"',
        '"updates_not_already_applied"',
        '"cleanup_search_evidence_present"',
        "_engine_rebind_source_item",
    ),
}
BRANCH_START_TOKENS = {
    "combined_evidence_rebind_bridge": "_combined_rebound_item = _publish_final_visible_design_guide_contract_binding(",
    "engine_evidence_rebind_bridge": "_engine_rebound_item = _publish_final_visible_design_guide_contract_binding(",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": "MISSING", "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "found": True,
        "path": str(path),
        "status": str(payload.get("status") or payload.get("result") or ""),
        "payload": payload,
    }


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _line_for(lines: list[str], token: str) -> int | None:
    for index, line in enumerate(lines, start=1):
        if token in line:
            return index
    return None


def _window(lines: list[str], line: int | None, *, before: int = 75, after: int = 95) -> str:
    if line is None:
        return ""
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _source_branch_rows() -> list[dict[str, Any]]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    rows: list[dict[str, Any]] = []
    for callsite_id in REQUIRED_CALLSITES:
        line = _line_for(lines, BRANCH_START_TOKENS[callsite_id])
        context = _window(lines, line)
        compact_context = " ".join(context.split())
        rows.append(
            {
                "callsite_id": callsite_id,
                "line": line,
                "branch_tokens_present": {
                    token: token in context or token in compact_context
                    for token in BRANCH_TOKENS[callsite_id]
                },
                "trace_call_present": (
                    "_stamp_controller_final_visible_rebind_effects_pre_helper_cutover_parity_trace("
                    in context
                ),
                "old_helper_call_present": (
                    "_publish_final_visible_design_guide_contract_binding(" in context
                ),
                "old_helper_still_drives_output": (
                    "displayed_primary_item = dict(_combined_rebound_item)" in context
                    or "displayed_primary_item = dict(_engine_rebound_item)" in context
                ),
            }
        )
    return rows


def _coverage_rows(live_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for capture in live_payload.get("recipe_captures") or []:
        traces = dict(capture.get("traces") or {})
        rows.append(
            {
                "recipe": capture.get("recipe"),
                "visible_card": bool(dict(capture.get("dom") or {}).get("design_guide_card_visible")),
                "loading_shell_visible": bool(dict(capture.get("dom") or {}).get("loading_shell_visible")),
                "trace_callsites": sorted(str(key) for key in traces.keys()),
                "trace_hash_present": bool(capture.get("trace_hash")),
            }
        )
    return rows


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Design Guide Pre-Helper Rebind Live Coverage Gap Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "## Latest Browser Live Snapshot",
        "",
        f"- Path: `{payload['latest_live'].get('path')}`",
        f"- Status: `{payload['latest_live'].get('status')}`",
        f"- Failure mode: `{payload['failure_mode']}`",
        "",
        "## Recipe Coverage",
        "",
        "| Recipe | Visible Card | Loading Shell | Trace Callsites |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("coverage_rows") or []:
        lines.append(
            f"| `{row.get('recipe')}` | `{row.get('visible_card')}` | `{row.get('loading_shell_visible')}` | `{row.get('trace_callsites')}` |"
        )
    lines.extend(["", "## Branch Predicate Inventory", "", "| Callsite | Line | Trace | Old Helper | Old Helper Drives Output |", "| --- | ---: | --- | --- | --- |"])
    for row in payload.get("source_branch_rows") or []:
        lines.append(
            f"| `{row.get('callsite_id')}` | `{row.get('line')}` | `{row.get('trace_call_present')}` | `{row.get('old_helper_call_present')}` | `{row.get('old_helper_still_drives_output')}` |"
        )
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            (
                "Do not cut over or delete the old rebind helper calls yet. Either add a "
                "targeted browser recipe that satisfies the recorded branch predicates, "
                "or create a broader deadness proof showing the predicates are unreachable "
                "under supported Design Guide states."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "tools/verification/design_guide_controller_rebind_effects_pre_helper_live_coverage_gap_audit.py",
        ]
    )
    latest_live = _latest(LIVE_PREFIX)
    latest_static = _latest(STATIC_PREFIX)
    live_payload = dict(latest_live.get("payload") or {})
    callsite_summaries = list(live_payload.get("callsite_summaries") or [])
    captured_any = any(row.get("captured") for row in callsite_summaries)
    all_not_captured = bool(callsite_summaries) and not captured_any
    source_branch_rows = _source_branch_rows()
    coverage_rows = _coverage_rows(live_payload)
    source_checks_pass = all(
        row.get("trace_call_present")
        and row.get("old_helper_call_present")
        and row.get("old_helper_still_drives_output")
        and all((row.get("branch_tokens_present") or {}).values())
        for row in source_branch_rows
    )
    failure_mode = (
        "coverage_gap_no_sampled_recipe_entered_rebind_branches"
        if all_not_captured
        else "parity_or_browser_failure_needs_investigation"
    )
    decision = (
        "LIVE_COVERAGE_GAP_NO_CUTOVER"
        if all_not_captured and source_checks_pass
        else "UNSAFE_TO_CUTOVER_INVESTIGATE"
    )
    checks = {
        "py_compile_pass": compile_run["returncode"] == 0,
        "latest_live_found": latest_live.get("found") is True,
        "latest_static_found": latest_static.get("found") is True,
        "latest_static_pass": latest_static.get("status") == "PASS",
        "live_failure_is_not_captured_coverage_gap": all_not_captured,
        "source_branch_predicates_mapped": source_checks_pass,
        "no_product_behavior_changed": live_payload.get("product_behaviour_changed") is False,
    }
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_controller_rebind_effects_pre_helper_live_coverage_gap_audit.v1",
        "status": status,
        "created_at": stamp,
        "decision": decision,
        "failure_mode": failure_mode,
        "checks": checks,
        "failures": failures,
        "compile_run": compile_run,
        "latest_live": {key: value for key, value in latest_live.items() if key != "payload"},
        "latest_static": {key: value for key, value in latest_static.items() if key != "payload"},
        "coverage_rows": coverage_rows,
        "source_branch_rows": source_branch_rows,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_controller_rebind_effects_pre_helper_live_coverage_gap_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_controller_rebind_effects_pre_helper_live_coverage_gap_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(audit_path, payload)
    print(f"design_guide_controller_rebind_effects_pre_helper_live_coverage_gap {status}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    if failures:
        print("failures=" + json.dumps(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
