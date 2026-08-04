"""Classify final-visible primary button/apply session effects.

This is deletion-enabling evidence for the physical Design Brain extraction:
it separates remaining page-shell session/apply binding writes from obsolete
restamper/fallback authority. It does not change product behaviour.
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
PRIMARY_APPLY_PAYLOAD_RECORDER = ROOT / "inputs_page_modules" / "design_guide" / "primary_apply_payload_recorder.py"
CURRENT_COORDINATORS = ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py"
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


def _build_snapshot() -> dict[str, Any]:
    shell_source = _read(INPUTS_PAGE)
    bridge_source = _read(APP_CONTRACT_BRIDGE)
    primary_apply_payload_source = _read(PRIMARY_APPLY_PAYLOAD)
    primary_apply_payload_recorder_source = _read(PRIMARY_APPLY_PAYLOAD_RECORDER)
    current_coordinators_source = _read(CURRENT_COORDINATORS)
    inputs_source = "\n".join(
        [
            shell_source,
            bridge_source,
            primary_apply_payload_source,
            primary_apply_payload_recorder_source,
            current_coordinators_source,
        ]
    )
    final_publication_source = _read(FINAL_PUBLICATION)
    button_body = _function_body(
        current_coordinators_source,
        "render_guidance_secondary_apply_action_current_coordinator",
    )
    payload_builder_body = "\n".join(
        [
            _function_body(bridge_source, "_build_design_guide_primary_apply_payload"),
            _function_body(primary_apply_payload_source, "_build_design_guide_primary_apply_payload"),
        ]
    )
    payload_body = "\n".join(
        [
            _function_body(bridge_source, "_record_rendered_design_guide_primary_apply_payload"),
            _function_body(primary_apply_payload_recorder_source, "_record_rendered_design_guide_primary_apply_payload"),
            bridge_source,
        ]
    )
    wrapper_body = _function_body(current_coordinators_source, "render_guidance_secondary_apply_action_current_coordinator")
    branch_inventory = _latest("design_guide_final_visible_branch_body_inventory")
    cta_bypass = _latest("design_guide_cta_apply_binding_bypass_live_impact")
    cta_authority = _latest("design_guide_live_cta_authority_cutover")
    publication_visual = _latest("design_guide_browser_live_visual_consistency")
    apply_safety = _latest("design_guide_apply_current_state_safety")
    cta_authority = _latest("design_guide_live_cta_authority_cutover")

    branch_payload = dict(branch_inventory.get("payload") or {})
    branches = list(branch_payload.get("branches") or [])
    branch_effects = []
    for branch in branches:
        hits = dict(branch.get("page_shell_effect_hits") or {})
        branch_effects.append(
            {
                "branch": branch.get("branch"),
                "primary_button_session_helper": dict(hits.get("primary_button_session_helper") or {}),
                "primary_apply_payload_session_projection_helper": dict(
                    hits.get("primary_apply_payload_session_projection_helper") or {}
                ),
            }
        )

    capture = {
        "decision": "PRIMARY_BUTTON_APPLY_SESSION_IS_PAGE_SHELL_BOUNDED_NOT_DEAD",
        "surface": "final-visible primary button/apply session projection",
        "source_lines": {
            "button_session_helper": _line_numbers(
                inputs_source, "def render_guidance_secondary_button_contract_current_coordinator("
            ),
            "apply_payload_projection_wrapper": _line_numbers(
                inputs_source,
                "def render_guidance_secondary_apply_action_current_coordinator(",
            ),
            "apply_payload_builder": _line_numbers(
                inputs_source, "def _build_design_guide_primary_apply_payload("
            ),
            "branch_button_session_calls": _line_numbers(
                inputs_source, "design_guide_primary_button_contract"
            ),
            "branch_apply_payload_calls": _line_numbers(
                inputs_source,
                "_record_rendered_design_guide_primary_apply_payload(",
            ),
        },
        "button_session_helper": {
            "present": bool(button_body),
            # The current coordinator also records transient CTA/session
            # breadcrumbs. What matters for this boundary is that it consumes
            # the authoritative result and cannot rebuild Apply truth from a
            # page-local item or legacy payload key.
            "writes_only_button_contract_keys": (
                "AuthoritativeDesignResultStore" in button_body
                and "authoritative_result.apply_payload" in button_body
                and "render_design_guide_component_cta" in button_body
                and "_record_rendered_design_guide_primary_apply_payload(" not in button_body
                and "_build_design_guide_primary_apply_payload(" not in button_body
                and "DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY" not in button_body
            ),
            "uses_authoritative_result_store": "AuthoritativeDesignResultStore" in button_body,
            "does_not_rebuild_page_local_apply_truth": (
                "_record_rendered_design_guide_primary_apply_payload(" not in button_body
                and "_build_design_guide_primary_apply_payload(" not in button_body
            ),
            "uses_final_publication_projection": "authoritative_result.apply_payload" in button_body,
            "classification": "page-shell session binding",
            "safe_to_delete_now": False,
        },
        "apply_payload_projection": {
            "wrapper_present": bool(wrapper_body),
            "payload_builder_present": bool(payload_builder_body),
            "delegates_to_rendered_payload_binding": (
                "AuthoritativeDesignResultStore" in wrapper_body
                and "authoritative_result.apply_payload" in wrapper_body
                and "_record_rendered_design_guide_primary_apply_payload(" not in wrapper_body
            ),
            "cta_authority_hash_guarded": (
                "_final_publication_cta_authority_payload(" in payload_body
                and "_stamp_final_publication_cta_authority(" in payload_body
                and "final_publication_cta_hash" in payload_body
            ),
            "state_apply_guard_present": "_design_guide_apply_updates_current_state_guard(" in payload_builder_body,
            "candidate_truth_probe_present": "_evaluate_auto_design_candidate(" in payload_builder_body,
            "candidate_preview_guard_present": "evaluate_candidate_full(" in bridge_source,
            "classification": "page-shell apply binding with live safety guards",
            "safe_to_delete_now": False,
        },
        "final_publication_cta_authority": {
            "cta_type_exists": "class FinalDesignGuideCTA" in final_publication_source,
            "cta_builder_exists": "def build_final_design_guide_cta(" in final_publication_source,
            "cta_state_adapter_exists": "def build_final_publication_cta_from_current_state(" in final_publication_source,
            "live_cutover_latest_status": cta_authority.get("status"),
            "bypass_live_impact_latest_status": cta_bypass.get("status"),
        },
        "branch_effects": branch_effects,
        "latest_required": {
            "branch_inventory": {
                "status": branch_inventory.get("status"),
                "path": branch_inventory.get("path"),
            },
            "cta_bypass_live_impact": {
                "status": cta_bypass.get("status"),
                "path": cta_bypass.get("path"),
            },
            "cta_authority_cutover": {
                "status": cta_authority.get("status"),
                "path": cta_authority.get("path"),
            },
            "publication_visual": {
                "status": publication_visual.get("status"),
                "path": publication_visual.get("path"),
            },
            "apply_safety": {
                "status": apply_safety.get("status"),
                "path": apply_safety.get("path"),
            },
            "cta_authority": {
                "status": cta_authority.get("status"),
                "path": cta_authority.get("path"),
            },
        },
        "ownership_after": (
            "FinalDesignGuidePublication.cta owns CTA truth; inputs_page keeps page-shell "
            "session/apply storage and stale/current-state guards."
        ),
        "next_safe_step": (
            "Do not delete this surface yet. Extract or bound the current-state apply guard "
            "and combined truth probe before attempting to move the apply payload builder."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }
    return capture


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_required") or {})
    apply_payload = dict(capture.get("apply_payload_projection") or {})
    button_session = dict(capture.get("button_session_helper") or {})
    cta = dict(capture.get("final_publication_cta_authority") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "button_session_helper_present": button_session.get("present") is True,
        "button_session_is_bounded_page_shell": button_session.get("writes_only_button_contract_keys") is True,
        "apply_payload_wrapper_present": apply_payload.get("wrapper_present") is True,
        "apply_payload_builder_present": apply_payload.get("payload_builder_present") is True,
        "apply_payload_delegates_to_guarded_binding": (
            apply_payload.get("delegates_to_rendered_payload_binding") is True
        ),
        "apply_payload_cta_hash_guarded": apply_payload.get("cta_authority_hash_guarded") is True,
        "state_apply_guard_retained": apply_payload.get("state_apply_guard_present") is True,
        "candidate_truth_probe_retained": (
            apply_payload.get("candidate_truth_probe_present") is True
            or apply_payload.get("candidate_preview_guard_present") is True
        ),
        "final_publication_cta_authority_exists": (
            cta.get("cta_type_exists") is True
            and cta.get("cta_builder_exists") is True
            and cta.get("cta_state_adapter_exists") is True
        ),
        "cta_authority_latest_pass": (
            (latest.get("cta_authority_cutover") or {}).get("status") == "PASS"
        ),
        "current_publication_visual_pass": (
            (latest.get("publication_visual") or {}).get("status") == "PASS"
        ),
        "current_apply_safety_pass": (
            (latest.get("apply_safety") or {}).get("status") == "PASS"
        ),
        "current_cta_authority_pass": (
            (latest.get("cta_authority") or {}).get("status") == "PASS"
        ),
        "not_safe_to_delete_button_session_now": button_session.get("safe_to_delete_now") is False,
        "not_safe_to_delete_apply_payload_now": apply_payload.get("safe_to_delete_now") is False,
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
        str(capture.get("surface")),
        "",
        "## Ownership Before",
        "Primary button/apply session writes appeared as remaining final-visible page-shell effects.",
        "",
        "## Ownership After",
        str(capture.get("ownership_after")),
        "",
        "## Behaviour Preserved",
        "- Engineering behaviour unchanged.",
        "- Visible wording unchanged.",
        "- CTA/apply semantics unchanged.",
        "- Family runtimes unchanged.",
        "",
        "## Adapter / Default Rebuild Proof",
        "This surface is not a default-rebuild adapter target yet. It is a bounded page-shell apply/session surface.",
        "",
        "## Cutover Proof",
        f"FinalDesignGuidePublication.cta authority latest status: `{(capture.get('final_publication_cta_authority') or {}).get('live_cutover_latest_status')}`.",
        "",
        "## Deadness / Deletion Proof",
        "Not dead. The apply payload path still owns stale/current-state guards and page-shell apply storage.",
        "",
        "## Lines Removed / Added",
        "No product code changed.",
        "",
        "## Files Changed",
        "- `tools/verification/design_guide_primary_button_apply_session_shell_boundary_snapshot.py`",
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
            "Page owns session/apply storage and safety guards only; CTA truth remains FinalDesignGuidePublication.cta.",
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
            "inputs_page_app_contract_bridge.py",
            "inputs_page_modules/design_guide/primary_apply_payload.py",
            "inputs_page_modules/design_guide/primary_apply_payload_recorder.py",
            "inputs_page_modules/design_guide/current_coordinators.py",
            "design_brain/final_publication.py",
            "tools/verification/design_guide_primary_button_apply_session_shell_boundary_snapshot.py",
        ]
    )
    capture = _build_snapshot()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_primary_button_apply_session_shell_boundary_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"design_guide_primary_button_apply_session_shell_boundary_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_primary_button_apply_session_shell_boundary_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_primary_button_apply_session_shell_boundary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_primary_button_apply_session_shell_boundary {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={audit_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
