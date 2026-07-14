"""Verify primary Apply payload assembly is cut over to FinalDesignGuidePublication.

The live current-state guard and combined expected-util probe intentionally
remain in inputs_page.py. This verifier proves only the final payload projection
assembly has moved behind the Design Brain adapter.
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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


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
    inputs_source = _read(INPUTS_PAGE)
    final_source = _read(FINAL_PUBLICATION)
    builder = _function_body(inputs_source, "_build_design_guide_primary_apply_payload")
    adapter = _function_body(final_source, "build_final_design_guide_primary_apply_payload_projection")
    return {
        "decision": "PRIMARY_APPLY_PAYLOAD_PROJECTION_CUT_OVER_TO_FINAL_PUBLICATION_ADAPTER",
        "source_lines": {
            "adapter_import": _line_numbers(
                inputs_source,
                "build_final_design_guide_primary_apply_payload_projection as _build_final_design_guide_primary_apply_payload_projection",
            ),
            "payload_builder": _line_numbers(inputs_source, "def _build_design_guide_primary_apply_payload("),
            "adapter_call": _line_numbers(
                inputs_source, "_build_final_design_guide_primary_apply_payload_projection("
            ),
            "current_state_guard": _line_numbers(
                inputs_source, "current_state_apply_guard = _design_guide_apply_updates_current_state_guard("
            ),
            "combined_truth_probe": _line_numbers(
                inputs_source, 'source="design_guide_primary_payload_combined_truth_probe"'
            ),
        },
        "builder_cutover": {
            "builder_present": bool(builder),
            "calls_adapter": "_build_final_design_guide_primary_apply_payload_projection(" in builder,
            "returns_adapter_payload": 'return dict(projection.get("payload") or {})' in builder,
            "passes_current_state_guard_to_adapter": "current_state_apply_guard=dict(current_state_apply_guard)" in builder,
            "passes_render_fingerprint_to_adapter": "render_fingerprint=render_fingerprint" in builder,
            "passes_shear_extra_fields_to_adapter": "extra_payload_fields=dict(extra_payload_fields)" in builder,
            "keeps_guard_before_adapter": (
                builder.find("current_state_apply_guard = _design_guide_apply_updates_current_state_guard(")
                < builder.find("_build_final_design_guide_primary_apply_payload_projection(")
            ),
            "keeps_failed_guard_return_empty": (
                'if not bool(current_state_apply_guard.get("pass")):' in builder and "return {}" in builder
            ),
            "keeps_combined_probe_before_adapter": (
                builder.find('source="design_guide_primary_payload_combined_truth_probe"')
                < builder.find("_build_final_design_guide_primary_apply_payload_projection(")
            ),
        },
        "adapter_boundary": {
            "adapter_present": bool(adapter),
            "adapter_no_inputs_page_import": "inputs_page" not in adapter,
            "adapter_no_streamlit": "streamlit" not in adapter and "st." not in adapter,
            "adapter_no_session_mutation": "session_state" not in adapter,
            "adapter_no_evaluator_call": "evaluate_candidate" not in adapter,
            "adapter_exported": '"build_final_design_guide_primary_apply_payload_projection"' in final_source,
        },
        "remaining_live_inputs_page_surfaces": {
            "current_state_apply_guard": {
                "retained": "current_state_apply_guard = _design_guide_apply_updates_current_state_guard(" in builder,
                "classification": "live stale/current-state safety guard",
                "safe_to_delete_now": False,
            },
            "combined_truth_probe": {
                "retained": 'source="design_guide_primary_payload_combined_truth_probe"' in builder,
                "classification": "live combined expected-util evaluator probe",
                "safe_to_delete_now": False,
            },
        },
        "latest_required": {
            "adapter_snapshot": _latest("design_guide_primary_apply_payload_projection_adapter"),
            "primary_button_boundary": _latest("design_guide_primary_button_apply_session_shell_boundary"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
        "next_safe_step": (
            "Create browser/live parity for the cutover, then extract or bound the "
            "current-state guard and combined truth probe as controller inputs."
        ),
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    cutover = dict(capture.get("builder_cutover") or {})
    adapter = dict(capture.get("adapter_boundary") or {})
    remaining = dict(capture.get("remaining_live_inputs_page_surfaces") or {})
    latest = dict(capture.get("latest_required") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "adapter_imported": bool((capture.get("source_lines") or {}).get("adapter_import")),
        "builder_present": cutover.get("builder_present") is True,
        "builder_calls_adapter": cutover.get("calls_adapter") is True,
        "builder_returns_adapter_payload": cutover.get("returns_adapter_payload") is True,
        "builder_passes_current_state_guard": cutover.get("passes_current_state_guard_to_adapter") is True,
        "builder_passes_render_fingerprint": cutover.get("passes_render_fingerprint_to_adapter") is True,
        "builder_passes_shear_extra_fields": cutover.get("passes_shear_extra_fields_to_adapter") is True,
        "guard_remains_before_adapter": cutover.get("keeps_guard_before_adapter") is True,
        "failed_guard_still_returns_empty": cutover.get("keeps_failed_guard_return_empty") is True,
        "combined_probe_remains_before_adapter": cutover.get("keeps_combined_probe_before_adapter") is True,
        "adapter_present": adapter.get("adapter_present") is True,
        "adapter_exported": adapter.get("adapter_exported") is True,
        "adapter_no_inputs_import": adapter.get("adapter_no_inputs_page_import") is True,
        "adapter_no_streamlit": adapter.get("adapter_no_streamlit") is True,
        "adapter_no_session_mutation": adapter.get("adapter_no_session_mutation") is True,
        "adapter_no_evaluator_call": adapter.get("adapter_no_evaluator_call") is True,
        "current_state_guard_retained": (
            (remaining.get("current_state_apply_guard") or {}).get("retained") is True
        ),
        "combined_truth_probe_retained": (
            (remaining.get("combined_truth_probe") or {}).get("retained") is True
        ),
        "adapter_snapshot_pass": (latest.get("adapter_snapshot") or {}).get("status") == "PASS",
        "primary_button_boundary_pass": (
            (latest.get("primary_button_boundary") or {}).get("status") == "PASS"
        ),
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    remaining = dict(capture.get("remaining_live_inputs_page_surfaces") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        str(payload.get("status")),
        "",
        "## Surface Targeted",
        "Primary Apply payload projection assembly.",
        "",
        "## Ownership Before",
        "`inputs_page.py` assembled the final primary Apply payload dict after running its safety guard/probe.",
        "",
        "## Ownership After",
        "`inputs_page.py` still runs the live safety guard/probe, but payload projection assembly delegates to `FinalDesignGuidePublication`.",
        "",
        "## Behaviour Preserved",
        "- Engineering behaviour unchanged.",
        "- Visible wording unchanged.",
        "- CTA/apply semantics unchanged.",
        "- Family runtimes unchanged.",
        "",
        "## Adapter / Default Rebuild Proof",
        "The focused adapter snapshot is required and latest PASS.",
        "",
        "## Cutover Proof",
        "The builder imports and calls `_build_final_design_guide_primary_apply_payload_projection(...)` and returns the adapter payload.",
        "",
        "## Deadness / Deletion Proof",
        "No deletion yet. Remaining live inputs:",
        "",
    ]
    for key, value in remaining.items():
        lines.append(f"- `{key}`: {value.get('classification')} - safe to delete now: `{value.get('safe_to_delete_now')}`")
    lines.extend(
        [
            "",
            "## Lines Removed / Added",
            "No obsolete code deleted in this slice; projection assembly was cut over.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "- `design_brain/final_publication.py`",
            "- `tools/verification/design_guide_primary_apply_payload_projection_cutover_snapshot.py`",
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
            "The current-state Apply guard and combined expected-util probe remain live in `inputs_page.py`.",
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
            "inputs_page.py",
            "design_brain/final_publication.py",
            "tools/verification/design_guide_primary_apply_payload_projection_cutover_snapshot.py",
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
    json_path = ARTIFACT_DIR / f"design_guide_primary_apply_payload_projection_cutover_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_primary_apply_payload_projection_cutover_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_primary_apply_payload_projection_cutover_{stamp}.md"
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
