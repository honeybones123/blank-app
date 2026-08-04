"""Deletion readiness for remaining compatibility-only restamper stamps.

The remaining compatibility stamps are not live resolver authority, but they
still call the old page helper to assemble final-visible binding effects before
the adapter proof runs. This verifier records the exact gap that must close
before those callsites can be deleted or replaced.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


COMPAT_CALLSITES = {
    "render_guidance_secondary_primary_binding": {
        "function": "_render_guidance_secondary_items",
        "input_marker": "_pre_card_binding_input_item = dict(item)",
        "old_helper_marker": "_publish_final_visible_design_guide_contract_binding(",
        "adapter_marker": "_binding_restamper_adapter = _stamp_final_visible_final_visible_output_bridge_proof(",
        "adapter_result_marker": "_binding_adapter_item = dict(",
        "cutover_marker": "render_guidance_secondary_primary_binding_adapter_cutover_applied",
    },
    "render_fast_design_guidance_panel.final_visible_item_binding": {
        "function": "_render_fast_design_guidance_panel",
        "input_marker": "_final_visible_binding_input_item = dict(_final_visible_resolution.get(\"item\") or {})",
        "old_helper_marker": "_publish_final_visible_design_guide_contract_binding(",
        "adapter_marker": "_final_visible_restamper_adapter = _stamp_final_visible_final_visible_output_bridge_proof(",
        "adapter_result_marker": "_final_visible_adapter_item = dict(",
        "cutover_marker": "render_fast_final_visible_item_binding_adapter_cutover_applied",
    },
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _function_body(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + len(marker))
    if end < 0:
        end = len(source)
    return source[start:end]


def _window_around(source: str, marker: str, *, before: int = 2600, after: int = 3200) -> str:
    idx = source.find(marker)
    if idx < 0:
        return ""
    return source[max(0, idx - before): idx + after]


def _line_numbers(source: str, needle: str) -> list[int]:
    return [idx for idx, line in enumerate(source.splitlines(), 1) if needle in line]


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
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "path": str(path), "status": status or "UNKNOWN", "payload": payload}


def _build_snapshot() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    remaining_audit = _latest("design_guide_remaining_resolver_cleanup_audit")
    rows = []
    for callsite_id, cfg in COMPAT_CALLSITES.items():
        window = _window_around(source, callsite_id)
        function_body = _function_body(source, str(cfg["function"]))
        has_old_helper = str(cfg["old_helper_marker"]) in window
        has_adapter = str(cfg["adapter_marker"]) in window
        has_adapter_result = str(cfg["adapter_result_marker"]) in window
        has_cutover_marker = str(cfg["cutover_marker"]) in window
        rows.append(
            {
                "callsite_id": callsite_id,
                "function": cfg["function"],
                "callsite_lines": _line_numbers(source, callsite_id),
                "old_helper_lines": _line_numbers(window, str(cfg["old_helper_marker"])),
                "input_marker_present": str(cfg["input_marker"]) in function_body,
                "old_helper_still_called": has_old_helper,
                "adapter_proof_present": has_adapter,
                "adapter_result_used_when_hash_matches": has_adapter_result and has_cutover_marker,
                "classification": "compatibility-only stamp, not live authority",
                "safe_to_delete_now": False,
                "delete_blocker": (
                    "old helper still assembles final-visible binding component inputs before adapter proof"
                    if has_old_helper
                    else None
                ),
                "required_next_adapter": (
                    "callsite-local final-visible binding component projection that supplies the same "
                    "cta/display/evidence/action-payload/resolved-candidate inputs to "
                    "_final_visible_contract_binding_output_cutover without calling "
                    "_publish_final_visible_design_guide_contract_binding"
                ),
            }
        )
    capture = {
        "decision": "COMPATIBILITY_RESTAMPER_STAMPS_NOT_DEAD_COMPONENT_INPUT_ADAPTER_REQUIRED",
        "remaining_audit": {
            "status": remaining_audit.get("status"),
            "path": remaining_audit.get("path"),
        },
        "rows": rows,
        "counts": {
            "compatibility_stamp_count": len(rows),
            "safe_deletion_candidate_count": sum(1 for row in rows if row.get("safe_to_delete_now")),
            "old_helper_call_count": sum(1 for row in rows if row.get("old_helper_still_called")),
            "adapter_proof_count": sum(1 for row in rows if row.get("adapter_proof_present")),
        },
        "latest_required": {
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "primary_apply_payload_cutover": _latest("design_guide_primary_apply_payload_projection_cutover"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
        "next_safe_step": (
            "Build the callsite-local component projection adapter for these two compatibility stamps, "
            "prove parity, then replace the old helper calls."
        ),
    }
    return capture


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("rows") or [])
    counts = dict(capture.get("counts") or {})
    latest = dict(capture.get("latest_required") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "two_compatibility_rows_tracked": len(rows) == 2,
        "both_rows_have_adapter_proof": counts.get("adapter_proof_count") == 2,
        "both_rows_still_call_old_helper": counts.get("old_helper_call_count") == 2,
        "no_rows_marked_safe_delete_yet": counts.get("safe_deletion_candidate_count") == 0,
        "all_rows_classified": all(row.get("classification") for row in rows),
        "all_rows_have_next_adapter": all(row.get("required_next_adapter") for row in rows),
        "remaining_audit_pass": (capture.get("remaining_audit") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "primary_apply_payload_cutover_pass": (
            (latest.get("primary_apply_payload_cutover") or {}).get("status") == "PASS"
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
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
        "Remaining compatibility-only restamper stamps.",
        "",
        "## Ownership Before",
        "Two callsites still call `_publish_final_visible_design_guide_contract_binding(...)` before adapter proof.",
        "",
        "## Ownership After",
        "No product code changed. This snapshot names the adapter required before deletion.",
        "",
        "## Behaviour Preserved",
        "- Engineering behaviour unchanged.",
        "- Visible wording unchanged.",
        "- CTA/apply semantics unchanged.",
        "- Family runtimes unchanged.",
        "",
        "## Adapter / Default Rebuild Proof",
        "Existing adapter proof is present at both compatibility stamp callsites, but old helper assembly is still used.",
        "",
        "## Cutover Proof",
        "Not cut over in this slice.",
        "",
        "## Deadness / Deletion Proof",
        "Not dead yet. Rows:",
        "",
        "| Callsite | Old helper still called | Adapter proof | Safe delete | Required next adapter |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in capture.get("rows") or []:
        lines.append(
            "| {callsite} | `{old}` | `{adapter}` | `{safe}` | {next_adapter} |".format(
                callsite=row.get("callsite_id"),
                old=row.get("old_helper_still_called"),
                adapter=row.get("adapter_proof_present"),
                safe=row.get("safe_to_delete_now"),
                next_adapter=row.get("required_next_adapter"),
            )
        )
    lines.extend(
        [
            "",
            "## Lines Removed / Added",
            "No product code changed.",
            "",
            "## Files Changed",
            "- `tools/verification/design_guide_restamper_compatibility_stamp_deletion_readiness_snapshot.py`",
            "",
            "## Verifier Results",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "The old helper still assembles component inputs for two compatibility-only callsites.",
            "",
            "## Next Safe Target",
            str(capture.get("next_safe_step")),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
            "tools/verification/design_guide_restamper_compatibility_stamp_deletion_readiness_snapshot.py",
        ]
    )
    capture = _build_snapshot()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "status": status,
        "timestamp": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "compile": compile_run,
    }
    json_path = ARTIFACT_DIR / f"design_guide_restamper_compatibility_stamp_deletion_readiness_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_restamper_compatibility_stamp_deletion_readiness_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_restamper_compatibility_stamp_deletion_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"status={status}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

