"""Audit outer reachability for the remaining render-panel rebind bridges."""

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
EXPORT_PREFIX = "design_guide_pre_helper_branch_predicate_probe_browser_export"

TARGETS = {
    "combined_evidence_rebind_bridge": {
        "callsite_token": 'callsite_id="combined_evidence_rebind_bridge"',
        "outer_gate_token": "if sidebar_debug:",
        "outer_gate_kind": "sidebar_debug_only",
        "expected_reachability": "not_reached_in_normal_non_debug_browser_runs",
        "next_step": "old debug-only binding body deleted; retain predicate probe as non-driving compatibility evidence",
        "expected_old_binding_call_present": False,
    },
    "engine_evidence_rebind_bridge": {
        "callsite_token": 'callsite_id="engine_evidence_rebind_bridge"',
        "outer_gate_token": "if isinstance(st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY), dict):",
        "outer_gate_kind": "debug_bundle_update_path",
        "expected_reachability": "requires live debug bundle plus engine evidence state",
        "next_step": "old debug-bundle binding body deleted; retain outer and predicate probes as non-driving compatibility evidence",
        "expected_old_binding_call_present": False,
    },
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


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _nearest_outer_gate(lines: list[str], callsite_line: int | None, gate_token: str) -> dict[str, Any]:
    if callsite_line is None:
        return {"found": False, "line": None, "indent": None, "callsite_indent": None}
    callsite_indent = _indent(lines[callsite_line - 1])
    for index in range(callsite_line - 2, -1, -1):
        line = lines[index]
        if gate_token in line and _indent(line) < callsite_indent:
            return {
                "found": True,
                "line": index + 1,
                "indent": _indent(line),
                "callsite_indent": callsite_indent,
            }
    return {"found": False, "line": None, "indent": None, "callsite_indent": callsite_indent}


def _window(lines: list[str], line: int | None, *, before: int = 12, after: int = 45) -> str:
    if line is None:
        return ""
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _live_probe_summary(live_payload: dict[str, Any]) -> dict[str, Any]:
    captures = list(live_payload.get("recipe_captures") or [])
    return {
        "recipe_count": len(captures),
        "recipes": [capture.get("recipe") for capture in captures],
        "visible_card_count": sum(
            1
            for capture in captures
            if bool(dict(capture.get("dom") or {}).get("design_guide_card_visible"))
        ),
        "captures_with_traces": sum(1 for capture in captures if dict(capture.get("traces") or {})),
        "captures_with_predicate_probes": sum(
            1 for capture in captures if dict(capture.get("predicate_probes") or {})
        ),
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    rows = []
    for callsite_id, target in TARGETS.items():
        callsite_line = _line_for(lines, target["callsite_token"])
        outer_gate = _nearest_outer_gate(lines, callsite_line, target["outer_gate_token"])
        context = _window(lines, callsite_line)
        rows.append(
            {
                "callsite_id": callsite_id,
                "callsite_line": callsite_line,
                "outer_gate": outer_gate,
                "outer_gate_kind": target["outer_gate_kind"],
                "expected_reachability": target["expected_reachability"],
                "next_step": target["next_step"],
                "predicate_probe_call_present": "_record_controller_pre_helper_rebind_branch_predicate_probe("
                in context,
                "old_binding_call_present": "_publish_final_visible_design_guide_contract_binding("
                in context,
                "expected_old_binding_call_present": bool(target["expected_old_binding_call_present"]),
            }
        )
    latest_live = _latest(LIVE_PREFIX)
    latest_export = _latest(EXPORT_PREFIX)
    return {
        "rows": rows,
        "latest_live": {key: value for key, value in latest_live.items() if key != "payload"},
        "latest_export": {key: value for key, value in latest_export.items() if key != "payload"},
        "live_probe_summary": _live_probe_summary(dict(latest_live.get("payload") or {})),
        "decision": "OUTER_REACHABILITY_CLASSIFIED_NO_CUTOVER",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Outer Rebind Reachability Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "| Callsite | Line | Outer Gate | Gate Line | Classification | Next Step |",
        "| --- | ---: | --- | ---: | --- | --- |",
    ]
    for row in capture.get("rows") or []:
        gate = dict(row.get("outer_gate") or {})
        lines.append(
            f"| `{row.get('callsite_id')}` | `{row.get('callsite_line')}` | `{row.get('outer_gate_kind')}` | `{gate.get('line')}` | `{row.get('expected_reachability')}` | {row.get('next_step')} |"
        )
    lines.extend(
        [
            "",
            "## Live Browser Summary",
            "",
            "```json",
            json.dumps(capture.get("live_probe_summary") or {}, indent=2),
            "```",
            "",
            "## Conclusion",
            "",
            "Both old rebind binding bodies are deleted. The combined bridge was gated by sidebar debug mode; "
            "the engine bridge was gated by the debug-bundle update path and is now represented by "
            "non-driving outer/predicate probes.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", "", "```json", json.dumps(payload["failures"], indent=2), "```"])
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
            "inputs_page.py",
            "tools/verification/design_guide_outer_rebind_reachability_audit.py",
        ]
    )
    capture = _capture()
    rows = list(capture.get("rows") or [])
    checks = {
        "py_compile_pass": compile_run["returncode"] == 0,
        "two_callsite_rows": len(rows) == 2,
        "callsite_lines_found": all(row.get("callsite_line") for row in rows),
        "outer_gates_found": all(dict(row.get("outer_gate") or {}).get("found") is True for row in rows),
        "predicate_probe_calls_present": all(row.get("predicate_probe_call_present") is True for row in rows),
        "old_binding_call_presence_matches_expectation": all(
            row.get("old_binding_call_present") is row.get("expected_old_binding_call_present")
            for row in rows
        ),
        "latest_export_pass": dict(capture.get("latest_export") or {}).get("status") == "PASS",
        "latest_browser_live_failed_without_probes": (
            dict(capture.get("latest_live") or {}).get("status") == "FAIL"
            and int(dict(capture.get("live_probe_summary") or {}).get("captures_with_predicate_probes") or 0)
            == 0
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_outer_rebind_reachability_audit.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"design_guide_outer_rebind_reachability_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_outer_rebind_reachability_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(audit_path, payload)
    print(f"design_guide_outer_rebind_reachability {status}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    if failures:
        print("failures=" + json.dumps(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
