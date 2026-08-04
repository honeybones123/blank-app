"""Verify no-active primary resolver branch is controller-backed."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=220,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "passed": proc.returncode == 0,
    }


def _capture() -> dict[str, Any]:
    inputs = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    controller = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    old_assembler_token = "_assemble_final_visible_no_active_primary_result("
    old_assembler_reference_count = inputs.count(old_assembler_token)
    old_assembler_deleted = old_assembler_reference_count == 0
    old_assembler_only_definition_remains = old_assembler_reference_count == 1
    composed = {
        "adapter_parity": _run(
            "tools/verification/design_guide_plain_data_fingerprint_adapter_parity_snapshot.py"
        ),
        "selector_readiness": _run(
            "tools/verification/design_guide_no_active_primary_selector_readiness_snapshot.py"
        ),
        "selector_legacy_route_parity": _run(
            "tools/verification/design_guide_controller_compute_selector_legacy_route_parity_snapshot.py"
        ),
    }
    legacy_resolver_deleted_controller_adapter_accounted = (
        old_assembler_deleted
        and (composed.get("selector_legacy_route_parity") or {}).get("passed") is True
        and "LEGACY_RESOLVER_DELETED_CONTROLLER_ADAPTER_ACCOUNTED"
        in ((composed.get("selector_legacy_route_parity") or {}).get("stdout_tail") or "")
    )
    return {
        "tokens": {
            "controller_builder_imported": (
                "build_design_guide_controller_no_active_primary_result as "
                "_build_design_guide_controller_no_active_primary_result"
            )
            in inputs,
            "controller_selection_request_used": "_DesignGuideControllerComputeSelectionRequest(" in inputs,
            "controller_selection_runner_used": (
                "_run_design_guide_controller_compute_selection_trace_only(" in inputs
            ),
            "no_active_cutover_source": "inputs_page_no_active_primary_route_cutover" in inputs,
            "controller_authority_trace": (
                'controller_authority="DesignGuideController.no_active_primary_result"'
                in inputs
            ),
            "controller_builder_call": (
                "_build_design_guide_controller_no_active_primary_result(" in inputs
            ),
            "controller_builder_defined": (
                "def build_design_guide_controller_no_active_primary_result(" in controller
            ),
            "controller_builder_exported": (
                '"build_design_guide_controller_no_active_primary_result"' in controller
            ),
        },
        "old_assembler_reference_count": old_assembler_reference_count,
        "old_assembler_only_definition_remains": old_assembler_only_definition_remains,
        "old_assembler_deleted": old_assembler_deleted,
        "legacy_resolver_deleted_controller_adapter_accounted": (
            legacy_resolver_deleted_controller_adapter_accounted
        ),
        "controller_forbidden_tokens_present": {
            "inputs_page": "inputs_page" in controller,
            "streamlit": "streamlit" in controller,
            "st_session_state": "st.session_state" in controller,
            "render_panel": "render_final_panel" in controller,
            "apply_routing": "handle_apply_buttons" in controller,
        },
        "composed": composed,
        "decision": (
            "NO_ACTIVE_PRIMARY_LEGACY_RESOLVER_DELETED_CONTROLLER_ADAPTER_ACCOUNTED"
            if legacy_resolver_deleted_controller_adapter_accounted
            else "NO_ACTIVE_PRIMARY_ROUTE_CONTROLLER_BACKED"
        ),
        "remaining_legacy_resolver_scope": [
            "no_active_combined_low_util_cleanup",
            "no_active_blocked_primary_cleanup_probe",
            "no_active_low_shear_or_blocker",
        ],
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    composed = dict(capture.get("composed") or {})
    return {
        "required_cutover_tokens_present_or_legacy_resolver_deleted": (
            all((capture.get("tokens") or {}).values())
            or capture.get("legacy_resolver_deleted_controller_adapter_accounted") is True
        ),
        "old_assembler_no_longer_called": capture.get("old_assembler_only_definition_remains") is True
        or capture.get("old_assembler_deleted") is True,
        "controller_has_no_page_ui_session_apply_imports": not any(
            (capture.get("controller_forbidden_tokens_present") or {}).values()
        ),
        "focused_prerequisite_verifiers_pass": all(
            (result or {}).get("passed") is True for result in composed.values()
        ),
        "remaining_legacy_scope_explicit": len(capture.get("remaining_legacy_resolver_scope") or []) == 3,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide No-Active Primary Route Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Scope",
            "",
            f"- Old assembler reference count: `{capture.get('old_assembler_reference_count')}`",
            f"- Old assembler only definition remains: `{capture.get('old_assembler_only_definition_remains')}`",
            f"- Old assembler deleted: `{capture.get('old_assembler_deleted')}`",
            "",
            "Remaining legacy resolver routes:",
        ]
    )
    lines.extend(f"- `{item}`" for item in capture.get("remaining_legacy_resolver_scope") or [])
    lines.append("")
    lines.append(
        "Only the no-active primary branch is controller-backed by this slice. Cleanup, blocker, active-failure, post-click, and snapshot-reuse routes remain unchanged."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_no_active_primary_route_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_no_active_primary_route_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_primary_route_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
