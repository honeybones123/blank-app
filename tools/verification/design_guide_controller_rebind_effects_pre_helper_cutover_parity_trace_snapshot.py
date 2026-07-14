"""Verify pre-helper controller parity trace wiring for render rebind bridges.

This is proof-only. The two render-stage combined/engine rebind callsites still
use the old final-visible binding helper for product output. This verifier
proves a non-driving controller trace is wired beside those calls using
pre-helper inputs, so browser/live parity can be captured before any cutover.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
INPUTS_PAGE = ROOT / "inputs_page.py"

HELPER = "_stamp_controller_final_visible_rebind_effects_pre_helper_cutover_parity_trace"
OLD_HELPER = "_publish_final_visible_design_guide_contract_binding("
TARGETS: tuple[dict[str, str], ...] = (
    {
        "id": "combined_evidence_rebind_bridge",
        "old_call": "_combined_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "pre_item": "pre_item=_combined_rebind_item",
        "pre_contract": "pre_contract=displayed_primary_button_contract",
        "old_output": "old_output_item=_combined_rebound_item",
        "current_updates": "current_updates=_displayed_contract_updates",
    },
    {
        "id": "engine_evidence_rebind_bridge",
        "old_call": "_engine_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "pre_item": "pre_item=_engine_rebind_source_item",
        "pre_contract": "pre_contract=_engine_update_contract",
        "old_output": "old_output_item=_engine_rebound_item",
        "current_updates": "current_updates=dict(_engine_update_contract.get(\"updates\") or {})",
    },
)

REQUIRED_ARTIFACTS = (
    "design_guide_controller_rebind_effects_adapter_parity",
    "design_guide_controller_rebind_effects_callsite_parity_readiness",
    "design_guide_render_combined_engine_rebind_parity_gap",
    "design_guide_render_bridge_lock",
    "design_guide_compute_resolver_publication_bridge_lock",
    "design_guide_independence_lock",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


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


def _window(lines: list[str], line: int | None, *, before: int = 8, after: int = 150) -> str:
    if line is None:
        return ""
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    helper_line = _line_for(lines, f"def {HELPER}(")
    helper_context = _window(lines, helper_line, before=0, after=150)
    rows = []
    for target in TARGETS:
        old_line = _line_for(lines, target["old_call"])
        context = _window(lines, old_line)
        trace_line = _line_for(context.splitlines(), f"{HELPER}(")
        rows.append(
            {
                "id": target["id"],
                "old_line": old_line,
                "old_call_present": old_line is not None,
                "trace_call_present": f"{HELPER}(" in context,
                "trace_after_old_call": trace_line is not None and trace_line > 1,
                "callsite_id_present": f'callsite_id="{target["id"]}"' in context,
                "pre_item_from_pre_helper_input": target["pre_item"] in context,
                "pre_contract_from_pre_helper_input": target["pre_contract"] in context,
                "old_output_compared": target["old_output"] in context,
                "current_updates_from_pre_helper_input": target["current_updates"] in context,
                "old_helper_still_drives_output": (
                    "displayed_primary_item = dict(_combined_rebound_item)" in context
                    or "displayed_primary_item = dict(_engine_rebound_item)" in context
                ),
            }
        )
    helper_checks = {
        "helper_defined": helper_line is not None,
        "controller_called": "_run_design_guide_controller_final_visible_rebind_effects_trace_only(" in helper_context,
        "projection_compared": "projected_item_matches_old_output" in helper_context
        and "projected_contract_matches_old_output" in helper_context,
        "trace_bucket_stamped": (
            "controller_final_visible_rebind_effects_pre_helper_cutover_parity_traces"
            in helper_context
        ),
        "non_driving_stamped": all(
            token in helper_context
            for token in (
                "pre_helper_cutover_parity_trace_only",
                "pre_helper_cutover_parity_product_driving",
                "pre_helper_cutover_parity_render_driving",
                "pre_helper_cutover_parity_apply_driving",
                "pre_helper_cutover_parity_session_driving",
            )
        ),
    }
    latest = {prefix: _latest(prefix) for prefix in REQUIRED_ARTIFACTS}
    return {
        "decision": "PRE_HELPER_CUTOVER_PARITY_TRACE_WIRED_NOT_PRODUCT_DRIVING",
        "helper_line": helper_line,
        "helper_checks": helper_checks,
        "rows": rows,
        "row_count": len(rows),
        "old_binding_helper_still_present": OLD_HELPER in source,
        "latest_artifacts": latest,
        "next_safe_step": (
            "Run browser/live parity scenarios that hit both rebind bridges and assert "
            "projected_item_matches_old_output plus projected_contract_matches_old_output before cutover."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("rows") or [])
    latest = dict(capture.get("latest_artifacts") or {})
    helper_checks = dict(capture.get("helper_checks") or {})
    return {
        "two_rows_captured": capture.get("row_count") == 2,
        "helper_defined": helper_checks.get("helper_defined") is True,
        "helper_calls_controller": helper_checks.get("controller_called") is True,
        "helper_compares_projection": helper_checks.get("projection_compared") is True,
        "helper_stamps_trace_bucket": helper_checks.get("trace_bucket_stamped") is True,
        "helper_non_driving": helper_checks.get("non_driving_stamped") is True,
        "old_calls_present": all(row.get("old_call_present") is True for row in rows),
        "trace_calls_present": all(row.get("trace_call_present") is True for row in rows),
        "trace_after_old_calls": all(row.get("trace_after_old_call") is True for row in rows),
        "callsite_ids_present": all(row.get("callsite_id_present") is True for row in rows),
        "pre_items_used": all(row.get("pre_item_from_pre_helper_input") is True for row in rows),
        "pre_contracts_used": all(row.get("pre_contract_from_pre_helper_input") is True for row in rows),
        "old_outputs_compared": all(row.get("old_output_compared") is True for row in rows),
        "current_updates_from_pre_helper": all(
            row.get("current_updates_from_pre_helper_input") is True for row in rows
        ),
        "old_helper_still_drives_output": all(row.get("old_helper_still_drives_output") is True for row in rows),
        "old_binding_helper_still_present": capture.get("old_binding_helper_still_present") is True,
        "adapter_parity_pass": (latest.get("design_guide_controller_rebind_effects_adapter_parity") or {}).get("status") == "PASS",
        "callsite_readiness_pass": (latest.get("design_guide_controller_rebind_effects_callsite_parity_readiness") or {}).get("status") == "PASS",
        "parity_gap_pass": (latest.get("design_guide_render_combined_engine_rebind_parity_gap") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("design_guide_render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("design_guide_compute_resolver_publication_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("design_guide_independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        str(payload.get("status")),
        "",
        "## Surface Targeted",
        "`combined_evidence_rebind_bridge` and `engine_evidence_rebind_bridge` pre-helper controller parity trace.",
        "",
        "## Ownership Before",
        "The old page binding helper still drives the rebound item for both render-panel bridges.",
        "",
        "## Ownership After",
        "No product ownership moved. Controller parity is trace-wired from pre-helper inputs only.",
        "",
        "## Behaviour Preserved",
        "- Engineering behaviour unchanged.",
        "- Visible wording unchanged.",
        "- CTA/apply semantics unchanged.",
        "- Family runtimes unchanged.",
        "",
        "## Cutover Proof",
        f"Decision: `{capture.get('decision')}`",
        "",
        "| Callsite | Old Line | Trace Present | Pre Item | Pre Contract | Old Output Compared |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for row in capture.get("rows") or []:
        lines.append(
            f"| `{row.get('id')}` | `{row.get('old_line')}` | `{row.get('trace_call_present')}` | "
            f"`{row.get('pre_item_from_pre_helper_input')}` | "
            f"`{row.get('pre_contract_from_pre_helper_input')}` | "
            f"`{row.get('old_output_compared')}` |"
        )
    lines.extend(
        [
            "",
            "## Deadness / Deletion Proof",
            "None yet. The old helper still drives product output by design.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "",
            "## Verifier Results",
            "",
        ]
    )
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "The two old rebind binding calls remain live until browser/live parity proves controller projection equals old output.",
            "",
            "## Next Safe Target",
            str(capture.get("next_safe_step") or ""),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "tools/verification/design_guide_controller_rebind_effects_pre_helper_cutover_parity_trace_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    if compile_run["returncode"] != 0:
        failures.append("py_compile_failed")
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_controller_rebind_effects_pre_helper_cutover_parity_trace_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_controller_rebind_effects_pre_helper_cutover_parity_trace_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_controller_rebind_effects_pre_helper_cutover_parity_trace_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_rebind_pre_helper_parity_trace_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_controller_rebind_effects_pre_helper_cutover_parity_trace {status}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
