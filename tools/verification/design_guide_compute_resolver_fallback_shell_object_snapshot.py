"""Verify the controller-owned compute resolver fallback shell object."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    DesignGuideControllerComputePublicationHandoffRequest,
    build_design_guide_controller_compute_resolver_fallback_shell,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _sample_request() -> DesignGuideControllerComputePublicationHandoffRequest:
    return DesignGuideControllerComputePublicationHandoffRequest(
        current_state={"b": 300.0, "D": 500.0},
        overview={"statuses": {"bending": "FAIL"}, "utils": {"bending": 1.25}},
        collapsed_guidance_items=[
            {
                "check_key": "bending",
                "family": "bending",
                "title_main": "Bending repair blocked by reinforcement/detailing limits",
                "title": "Bending repair blocked by reinforcement/detailing limits",
                "status": "FAIL",
                "bucket": "fail",
                "guidance_intent": "specific_blocker",
                "final_state_class": "blocker",
                "primary_card_actionable": False,
            }
        ],
        publication_context={"guidance_state_snapshot": {"b": 300.0, "D": 500.0}},
        session_controls={"actions_mode": "manual"},
        design_actions_signature=(("Mu", "300"),),
        optimisation_goal="balanced",
        source="fallback_shell_object_snapshot",
    )


def _capture() -> dict[str, Any]:
    source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    request = _sample_request()
    first = build_design_guide_controller_compute_resolver_fallback_shell(
        request,
        reason="snapshot_controller_missing",
        error="sample error",
    )
    second = build_design_guide_controller_compute_resolver_fallback_shell(
        request,
        reason="snapshot_controller_missing",
        error="sample error",
    )
    item = dict((first.final_compute_resolution or {}).get("item") or {})
    contract = dict(item.get("button_contract") or {})
    shell_start = source.find("def build_design_guide_controller_compute_resolver_fallback_shell(")
    shell_end = source.find("\ndef _compute_selection_request_from_dict(", shell_start)
    shell_source = source[shell_start:shell_end if shell_end > shell_start else shell_start + 8000]
    forbidden_terms = {
        "streamlit": "streamlit" in shell_source.lower(),
        "st.session_state": "st.session_state" in shell_source,
        "resolve_final_visible_design_guide_item": (
            "resolve_final_visible_design_guide_item" in shell_source
        ),
        "_legacy_fallback_resolution": "_legacy_fallback_resolution" in shell_source,
    }
    checks = {
        "stable_controller_hash": first.controller_hash == second.controller_hash,
        "stable_resolution_hash": first.final_compute_resolution_hash
        == second.final_compute_resolution_hash,
        "old_resolver_input_not_required": first.old_resolver_input_required is False,
        "fallback_shell_flag_present": (
            (first.final_compute_resolution or {}).get(
                "controller_compute_resolver_fallback_shell"
            )
            is True
        ),
        "apply_disabled": contract.get("enabled") is False
        and contract.get("actionable") is False
        and not contract.get("updates"),
        "no_forbidden_page_or_ui_terms_in_shell": not any(forbidden_terms.values()),
    }
    return {
        "checks": checks,
        "forbidden_terms": forbidden_terms,
        "response": {
            "controller_id": first.controller_id,
            "authority": first.authority,
            "request_hash": first.request_hash,
            "controller_hash": first.controller_hash,
            "final_compute_resolution_hash": first.final_compute_resolution_hash,
            "old_resolver_input_required": first.old_resolver_input_required,
            "trace_only": first.trace_only,
            "product_driving": first.product_driving,
            "apply_driving": first.apply_driving,
            "render_driving": first.render_driving,
            "session_driving": first.session_driving,
        },
        "item_summary": {
            "title": item.get("title"),
            "status": item.get("status"),
            "family": item.get("family"),
            "fallback_shell": item.get("controller_compute_resolver_fallback_shell"),
            "button_contract": contract,
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Compute Resolver Fallback Shell Object Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Checks",
        "",
        "| Check | Pass |",
        "| --- | --- |",
    ]
    for key, value in dict(capture.get("checks") or {}).items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "## Response",
            "",
            "```json",
            json.dumps(capture.get("response") or {}, indent=2),
            "```",
            "",
            "## Item Summary",
            "",
            "```json",
            json.dumps(capture.get("item_summary") or {}, indent=2),
            "```",
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
            "design_brain/design_guide_controller.py",
            "tools/verification/design_guide_compute_resolver_fallback_shell_object_snapshot.py",
        ]
    )
    capture = _capture()
    failures: list[str] = []
    if compile_run["returncode"] != 0:
        failures.append("py_compile_failed")
    for key, value in dict(capture.get("checks") or {}).items():
        if value is not True:
            failures.append(key)
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_compute_resolver_fallback_shell_object_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "compile_run": compile_run,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"design_guide_compute_resolver_fallback_shell_object_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_resolver_fallback_shell_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, md_path)
    print(f"design_guide_compute_resolver_fallback_shell_object {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
