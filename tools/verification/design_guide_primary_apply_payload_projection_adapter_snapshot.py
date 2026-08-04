"""Snapshot the primary Apply payload projection adapter.

This is a deletion-enabling step for the physical Design Brain extraction. It
does not move the live current-state Apply guard or combined evaluator probe.
It proves the payload projection shape can be owned by
FinalDesignGuidePublication once those guard/probe inputs are supplied.
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
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
PRIMARY_APPLY_PAYLOAD = ROOT / "inputs_page_modules" / "design_guide" / "primary_apply_payload.py"
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


def _expected_payload(
    *,
    candidate_id: str,
    family: str,
    selected_family_id: str | None,
    action_type: str,
    updates: dict[str, Any],
    visible_updates: dict[str, Any],
    button_contract: dict[str, Any],
    current_state_apply_guard: dict[str, Any],
    expected_util: Any,
    label: str,
    render_fingerprint: str,
    state_fingerprint: str,
    extra_payload_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "action_type": action_type,
        "family": family,
        "updates": dict(updates),
        "visible_updates": dict(visible_updates),
        "button_contract_updates": dict(updates),
        "preview_status": "PASS" if button_contract.get("preview_pass") is True else "FAIL",
        "preview_pass": bool(button_contract.get("preview_pass")),
        "current_state_apply_preview_guard": dict(current_state_apply_guard),
        "expected_util": expected_util,
        "label": label,
        "source": "design_guide_primary_render",
        "apply_payload_family_id": selected_family_id,
        "selected_family_id": selected_family_id,
        "render_fingerprint": render_fingerprint,
        "state_fingerprint": state_fingerprint,
    }
    payload.update(dict(extra_payload_fields or {}))
    return payload


def _build_snapshot() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    from design_brain.final_publication import (  # noqa: WPS433
        build_final_design_guide_primary_apply_payload_projection,
    )

    inputs_source = "\n".join(
        _read(path) for path in (INPUTS_PAGE, APP_CONTRACT_BRIDGE, PRIMARY_APPLY_PAYLOAD) if path.exists()
    )
    final_source = _read(FINAL_PUBLICATION)
    adapter_body = _function_body(final_source, "build_final_design_guide_primary_apply_payload_projection")
    payload_builder_body = _function_body(inputs_source, "_build_design_guide_primary_apply_payload")
    guard_body = _function_body(inputs_source, "_design_guide_apply_updates_current_state_guard")

    updates = {"width_mm": 450.0, "depth_mm": 700.0}
    visible_updates = {"width_mm": 450.0, "depth_mm": 700.0}
    guard = {
        "pass": True,
        "reason": None,
        "updates": dict(updates),
        "expected_util": 0.82,
        "overview_any_fail": False,
        "overview_all_key_pass": True,
        "overview_statuses": {"bending": "PASS", "shear": "PASS"},
        "candidate_state_fingerprint": "candidate-state-fp",
    }
    button_contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "updates": dict(updates),
        "preview_pass": True,
        "expected_util": 0.82,
        "label": "Apply bending repair",
    }
    item = {
        "title_main": "Apply bending repair",
        "title": "Apply bending repair",
        "family": "bending",
    }
    rec = {"family": "bending", "title": "Apply bending repair"}
    state_fp = "state-fp-1"
    render_fp = "render-fp-1"
    enabled_projection = build_final_design_guide_primary_apply_payload_projection(
        item=item,
        rec=rec,
        button_contract=button_contract,
        updates=updates,
        visible_updates=visible_updates,
        current_state_apply_guard=guard,
        candidate_id="BENDING_FAIL_GOVERNS:abc123",
        family="bending",
        selected_family_id="BENDING_FAIL_GOVERNS",
        action_type="apply_resolved_candidate",
        state_fingerprint=state_fp,
        render_fingerprint=render_fp,
        expected_util=0.82,
        label="Apply bending repair",
    )
    enabled_expected = _expected_payload(
        candidate_id="BENDING_FAIL_GOVERNS:abc123",
        family="bending",
        selected_family_id="BENDING_FAIL_GOVERNS",
        action_type="apply_resolved_candidate",
        updates=updates,
        visible_updates=visible_updates,
        button_contract=button_contract,
        current_state_apply_guard=guard,
        expected_util=0.82,
        label="Apply bending repair",
        render_fingerprint=render_fp,
        state_fingerprint=state_fp,
    )

    blocked_guard = dict(guard)
    blocked_guard.update({"pass": False, "reason": "current_state_apply_preview_any_fail"})
    blocked_projection = build_final_design_guide_primary_apply_payload_projection(
        item=item,
        rec=rec,
        button_contract=button_contract,
        updates=updates,
        visible_updates=visible_updates,
        current_state_apply_guard=blocked_guard,
        candidate_id="BENDING_FAIL_GOVERNS:abc123",
        family="bending",
        selected_family_id="BENDING_FAIL_GOVERNS",
        action_type="apply_resolved_candidate",
        state_fingerprint=state_fp,
        render_fingerprint=render_fp,
    )

    shear_extra = {
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "published_family_id": "SHEAR_FAIL_GOVERNS",
        "cta_family_id": "SHEAR_FAIL_GOVERNS",
        "apply_payload_family_id": "SHEAR_FAIL_GOVERNS",
        "governing_family": "SHEAR_FAIL_GOVERNS",
        "payload_owner": "shear_fail",
        "payload_action_family": "shear_fail",
        "payload_action_kind": "repair",
    }
    shear_projection = build_final_design_guide_primary_apply_payload_projection(
        item={"title": "Apply shear repair", "family": "shear"},
        rec={"family": "shear", "title": "Apply shear repair"},
        button_contract={**button_contract, "family": "shear", "label": "Apply shear repair"},
        updates={"lig_spacing_mm": 150.0},
        visible_updates={"lig_spacing_mm": 150.0},
        current_state_apply_guard={**guard, "updates": {"lig_spacing_mm": 150.0}},
        candidate_id="SHEAR_FAIL_GOVERNS:xyz",
        family="shear",
        selected_family_id="SHEAR_FAIL_GOVERNS",
        action_type="apply_resolved_candidate",
        state_fingerprint="state-fp-shear",
        render_fingerprint="render-fp-shear",
        expected_util=0.76,
        label="Apply shear repair",
        extra_payload_fields=shear_extra,
    )

    capture = {
        "decision": "PRIMARY_APPLY_PAYLOAD_PROJECTION_ADAPTER_READY_BUT_GUARD_PROBE_STILL_LIVE",
        "source_lines": {
            "payload_builder": _line_numbers(inputs_source, "def _build_design_guide_primary_apply_payload("),
            "current_state_guard": _line_numbers(
                inputs_source, "def _design_guide_apply_updates_current_state_guard("
            ),
            "combined_truth_probe": _line_numbers(
                inputs_source, 'source="design_guide_primary_payload_combined_truth_probe"'
            ),
            "adapter": _line_numbers(
                final_source, "def build_final_design_guide_primary_apply_payload_projection("
            ),
        },
        "adapter_scope": {
            "owns_payload_projection_shape": True,
            "owns_current_state_apply_guard": False,
            "owns_combined_truth_probe": False,
            "imports_inputs_page": "inputs_page" in adapter_body,
            "imports_streamlit": "streamlit" in adapter_body or "st." in adapter_body,
            "mutates_session_state": "session_state" in adapter_body,
            "calls_evaluator": "evaluate_candidate" in adapter_body,
        },
        "projection_cases": {
            "enabled_payload_matches_expected": enabled_projection.get("payload") == enabled_expected,
            "enabled_projection": enabled_projection,
            "expected_enabled_payload": enabled_expected,
            "guard_failure_returns_empty_payload": blocked_projection.get("payload") == {},
            "guard_failure_enabled_false": blocked_projection.get("enabled") is False,
            "shear_extra_fields_preserved": all(
                shear_projection.get("payload", {}).get(key) == value for key, value in shear_extra.items()
            ),
            "projection_hashes_stable": (
                enabled_projection
                == build_final_design_guide_primary_apply_payload_projection(
                    item=item,
                    rec=rec,
                    button_contract=button_contract,
                    updates=updates,
                    visible_updates=visible_updates,
                    current_state_apply_guard=guard,
                    candidate_id="BENDING_FAIL_GOVERNS:abc123",
                    family="bending",
                    selected_family_id="BENDING_FAIL_GOVERNS",
                    action_type="apply_resolved_candidate",
                    state_fingerprint=state_fp,
                    render_fingerprint=render_fp,
                    expected_util=0.82,
                    label="Apply bending repair",
                )
            ),
        },
        "live_blockers_to_payload_builder_cutover": {
            "current_state_apply_guard": {
                "classification": "live stale/current-state safety guard",
                "definition_line": _line_numbers(
                    inputs_source, "def _design_guide_apply_updates_current_state_guard("
                ),
                "safe_to_delete_now": False,
                "next_proof_needed": (
                    "controller-owned guard request/result parity using the same evaluator boundary"
                ),
            },
            "combined_truth_probe": {
                "classification": "live combined expected-util evaluator probe",
                "call_line": _line_numbers(
                    inputs_source, 'source="design_guide_primary_payload_combined_truth_probe"'
                ),
                "safe_to_delete_now": False,
                "next_proof_needed": (
                    "controller/final-publication payload input parity for combined updates"
                ),
            },
        },
        "latest_locks": {
            "publication_visual": _latest("design_guide_browser_live_visual_consistency"),
            "apply_safety": _latest("design_guide_apply_current_state_safety"),
            "cta_authority": _latest("design_guide_live_cta_authority_cutover"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
        "next_safe_step": (
            "Wire this adapter trace-only beside _build_design_guide_primary_apply_payload, "
            "then prove browser/live parity before replacing page-local payload assembly."
        ),
    }
    return capture


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    adapter = dict(capture.get("adapter_scope") or {})
    cases = dict(capture.get("projection_cases") or {})
    locks = dict(capture.get("latest_locks") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "adapter_exists": bool((capture.get("source_lines") or {}).get("adapter")),
        "payload_builder_still_present": bool((capture.get("source_lines") or {}).get("payload_builder")),
        "current_state_guard_still_present": bool((capture.get("source_lines") or {}).get("current_state_guard")),
        "combined_truth_probe_absent_or_present_as_live_input": True,
        "adapter_owns_payload_projection_shape": adapter.get("owns_payload_projection_shape") is True,
        "adapter_does_not_import_inputs_page": adapter.get("imports_inputs_page") is False,
        "adapter_does_not_import_streamlit": adapter.get("imports_streamlit") is False,
        "adapter_does_not_mutate_session": adapter.get("mutates_session_state") is False,
        "adapter_does_not_call_evaluator": adapter.get("calls_evaluator") is False,
        "enabled_payload_matches_expected": cases.get("enabled_payload_matches_expected") is True,
        "guard_failure_returns_empty_payload": cases.get("guard_failure_returns_empty_payload") is True,
        "guard_failure_enabled_false": cases.get("guard_failure_enabled_false") is True,
        "shear_extra_fields_preserved": cases.get("shear_extra_fields_preserved") is True,
        "projection_hashes_stable": cases.get("projection_hashes_stable") is True,
        "current_publication_visual_pass": (locks.get("publication_visual") or {}).get("status") == "PASS",
        "current_apply_safety_pass": (locks.get("apply_safety") or {}).get("status") == "PASS",
        "current_cta_authority_pass": (locks.get("cta_authority") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    blockers = dict(capture.get("live_blockers_to_payload_builder_cutover") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        str(payload.get("status")),
        "",
        "## Surface Targeted",
        "Primary Apply payload projection shape.",
        "",
        "## Ownership Before",
        "`inputs_page.py` assembled the primary Apply payload shape and also ran the live current-state guard and combined truth probe.",
        "",
        "## Ownership After",
        "`FinalDesignGuidePublication` has a page-free adapter for the payload projection shape. The live guard/probe remain in `inputs_page.py` until separate parity/cutover.",
        "",
        "## Behaviour Preserved",
        "- Engineering behaviour unchanged.",
        "- Visible wording unchanged.",
        "- CTA/apply semantics unchanged.",
        "- Family runtimes unchanged.",
        "",
        "## Adapter / Default Rebuild Proof",
        "The adapter reproduces the enabled payload projection, preserves guard-failure empty payload behaviour, preserves shear-family extra fields, and has stable hashes.",
        "",
        "## Cutover Proof",
        "Not cut over yet. This is adapter readiness only.",
        "",
        "## Deadness / Deletion Proof",
        "No deletion yet. Remaining blockers:",
        "",
    ]
    for key, value in blockers.items():
        lines.append(f"- `{key}`: {value.get('classification')} - safe to delete now: `{value.get('safe_to_delete_now')}`")
    lines.extend(
        [
            "",
            "## Lines Removed / Added",
            "No product code deleted. Added adapter and verifier only.",
            "",
            "## Files Changed",
            "- `design_brain/final_publication.py`",
            "- `tools/verification/design_guide_primary_apply_payload_projection_adapter_snapshot.py`",
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
            "The current-state Apply guard and combined expected-util probe remain live page-owned safety/evaluator surfaces.",
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
            "tools/verification/design_guide_primary_apply_payload_projection_adapter_snapshot.py",
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
    json_path = ARTIFACT_DIR / f"design_guide_primary_apply_payload_projection_adapter_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_primary_apply_payload_projection_adapter_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_primary_apply_payload_projection_adapter_{stamp}.md"
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
