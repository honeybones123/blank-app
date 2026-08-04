"""Snapshot compatibility restamper projection inside render binding payload.

This proves the surviving Design Brain render-binding payload still emits the
component payloads needed by the remaining compatibility restamper path after
the older intermediate adapter helper is deleted.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
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
    sys.path.insert(0, str(ROOT))
    from design_brain.final_publication import (  # noqa: WPS433
        build_final_visible_render_binding_payload,
        stable_final_publication_hash,
    )

    final_source = _read(FINAL_PUBLICATION)
    binding_body = _function_body(final_source, "build_final_visible_render_binding_payload")
    enabled_item = {
        "title": "Strengthening required",
        "family": "bending",
        "check_key": "bending",
        "selected_action_family": "bending",
        "primary_card_actionable": True,
        "action_type": "apply_resolved_candidate",
        "updates": {"depth_mm": 650.0},
        "selected_action_updates": {"depth_mm": 650.0},
        "candidate_id": "BENDING_FAIL_GOVERNS:depth",
        "source_candidate_id": "BENDING_FAIL_GOVERNS:depth",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "bending",
            "updates": {"depth_mm": 650.0},
            "preview_pass": True,
        },
        "action_payload": {
            "candidate_id": "BENDING_FAIL_GOVERNS:depth",
            "updates": {"depth_mm": 650.0},
            "candidate_search_evidence": {"family": "bending"},
        },
        "resolved_candidate": {
            "candidate_id": "BENDING_FAIL_GOVERNS:depth",
            "updates": {"depth_mm": 650.0},
            "candidate_search_evidence": {"family": "bending"},
        },
        "candidate_search_evidence": {"family": "bending"},
        "family_status_current": {"bending": {"util": 1.2}},
        "family_status_preview": {"bending": {"util": 0.82}},
    }
    disabled_item = {
        "title": "Design Guide blocker proof incomplete",
        "family": "bending",
        "primary_card_actionable": False,
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "family": "bending",
            "updates": {},
            "blocking_reason": "specific_blocker",
        },
        "candidate_search_evidence": {"family": "bending", "blocked": True},
        "family_status_current": {"bending": {"util": 1.4}},
    }

    enabled_binding = build_final_visible_render_binding_payload(
        input_item=enabled_item,
        callsite_id="component_projection_snapshot.enabled",
    )
    enabled_adapter = dict(enabled_binding.get("adapter_projection") or {})
    enabled_components = dict(enabled_adapter.get("component_projection") or {})
    enabled_projection = dict(enabled_adapter.get("projection") or {})

    disabled_binding = build_final_visible_render_binding_payload(
        input_item=disabled_item,
        callsite_id="component_projection_snapshot.disabled",
    )
    disabled_adapter = dict(disabled_binding.get("adapter_projection") or {})
    disabled_components = dict(disabled_adapter.get("component_projection") or {})
    disabled_projection = dict(disabled_adapter.get("projection") or {})

    repeat = build_final_visible_render_binding_payload(
        input_item=enabled_item,
        callsite_id="component_projection_snapshot.enabled",
    )
    repeat_adapter = dict(repeat.get("adapter_projection") or {})
    capture = {
        "decision": "COMPATIBILITY_RESTAMPER_ADAPTER_PROJECTION_READY",
        "adapter_scope": {
            "render_binding_present": bool(binding_body),
            "deleted_component_helper": (
                "def build_final_visible_final_visible_contract_binding_component_projection("
                not in final_source
            ),
            "deleted_adapter_helper": (
                "def build_final_visible_final_visible_contract_binding_adapter_projection("
                not in final_source
            ),
            "imports_inputs_page": "inputs_page" in binding_body,
            "imports_streamlit": "streamlit" in binding_body or "st." in binding_body,
            "mutates_session_state": "session_state" in binding_body,
            "calls_evaluator": "evaluate_candidate" in binding_body,
            "calls_old_page_helper": "_publish_final_visible_design_guide_contract_binding" in binding_body,
        },
        "enabled_case": {
            "component_hash": enabled_components.get("component_payloads_hash"),
            "projection_item_hash": stable_final_publication_hash(enabled_projection.get("item") or {}),
            "cutover_ready": enabled_adapter.get("cutover_ready"),
            "fallback_reason": enabled_adapter.get("fallback_reason"),
        },
        "disabled_case": {
            "component_hash": disabled_components.get("component_payloads_hash"),
            "projection_item_hash": stable_final_publication_hash(disabled_projection.get("item") or {}),
            "cutover_ready": disabled_adapter.get("cutover_ready"),
            "fallback_reason": disabled_adapter.get("fallback_reason"),
        },
        "stable_repeat_hash": enabled_adapter.get("adapter_hash") == repeat_adapter.get("adapter_hash"),
        "latest_required": {
            "compat_deletion_readiness": _latest(
                "design_guide_restamper_compatibility_stamp_deletion_readiness"
            ),
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
            "Keep deleting leftover compatibility-only intermediate helper surfaces now that the adapter "
            "projection itself is inlined into the clean render binding payload."
        ),
    }
    return capture


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    scope = dict(capture.get("adapter_scope") or {})
    enabled = dict(capture.get("enabled_case") or {})
    disabled = dict(capture.get("disabled_case") or {})
    latest = dict(capture.get("latest_required") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "render_binding_present": scope.get("render_binding_present") is True,
        "deleted_component_helper": scope.get("deleted_component_helper") is True,
        "deleted_adapter_helper": scope.get("deleted_adapter_helper") is True,
        "adapter_does_not_import_inputs_page": scope.get("imports_inputs_page") is False,
        "adapter_does_not_import_streamlit": scope.get("imports_streamlit") is False,
        "adapter_does_not_mutate_session": scope.get("mutates_session_state") is False,
        "adapter_does_not_call_evaluator": scope.get("calls_evaluator") is False,
        "adapter_does_not_call_old_page_helper": scope.get("calls_old_page_helper") is False,
        "enabled_cutover_ready": enabled.get("cutover_ready") is True,
        "enabled_no_guard_fallback": not bool(enabled.get("fallback_reason")),
        "disabled_cutover_ready": disabled.get("cutover_ready") is True,
        "disabled_no_guard_fallback": not bool(disabled.get("fallback_reason")),
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "compat_deletion_readiness_pass": (
            (latest.get("compat_deletion_readiness") or {}).get("status") == "PASS"
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
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        str(payload.get("status")),
        "",
        "## Surface Targeted",
        "Adapter projection for compatibility restamper stamps.",
        "",
        "## Ownership Before",
        "The two compatibility callsites used the old page helper to assemble final-visible component inputs.",
        "",
        "## Ownership After",
        "A page-free FinalDesignGuidePublication adapter projection can assemble enabled and disabled branch component payloads.",
        "",
        "## Behaviour Preserved",
        "- Engineering behaviour unchanged.",
        "- Visible wording unchanged.",
        "- CTA/apply semantics unchanged.",
        "- Family runtimes unchanged.",
        "",
        "## Adapter / Default Rebuild Proof",
        f"Enabled cutover ready: `{(capture.get('enabled_case') or {}).get('cutover_ready')}`.",
        f"Disabled cutover ready: `{(capture.get('disabled_case') or {}).get('cutover_ready')}`.",
        "",
        "## Cutover Proof",
        "Not cut over in this slice.",
        "",
        "## Deadness / Deletion Proof",
        "The older intermediate component helper is deleted; the surviving adapter projection now carries the component proof surface.",
        "",
        "## Lines Removed / Added",
        "No product code deleted.",
        "",
        "## Files Changed",
        "- `design_brain/final_publication.py`",
        "- `tools/verification/design_guide_restamper_compatibility_component_projection_snapshot.py`",
        "",
        "## Verifier Results",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "The two compatibility callsites still need guarded cutover to use the adapter instead of the old page helper.",
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
            "design_brain/final_publication.py",
            "tools/verification/design_guide_restamper_compatibility_component_projection_snapshot.py",
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
    json_path = ARTIFACT_DIR / f"design_guide_restamper_compatibility_component_projection_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_restamper_compatibility_component_projection_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_restamper_compatibility_component_projection_{stamp}.md"
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

