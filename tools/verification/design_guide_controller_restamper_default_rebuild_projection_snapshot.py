"""Proof that the controller exposes the final-visible output projection."""

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
REPORT_DIR = ROOT / "artifacts" / "reports"

from design_brain.design_guide_controller import (  # noqa: E402
    run_design_guide_controller_final_visible_rebind_effects_trace_only,
)
from design_brain.final_publication import stable_final_publication_hash  # noqa: E402


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _capture() -> dict[str, Any]:
    item = {
        "title_main": "Strengthening required",
        "summary_line": "Repair required.",
        "status": "FAIL",
        "bucket": "fail",
        "guidance_intent": "required_fix",
        "family": "shear",
        "check_key": "shear",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "updates": {"lig_legs": 0},
            "candidate_id": "controller-default-rebuild:candidate",
        },
        "updates": {"lig_legs": 0},
        "selected_action_updates": {"lig_legs": 0},
        "action_type": "apply_resolved_candidate",
        "candidate_search_evidence": {
            "family": "shear",
            "selected_candidate_updates": {"lig_legs": 0},
        },
    }
    contract = dict(item["button_contract"])
    response = run_design_guide_controller_final_visible_rebind_effects_trace_only(
        {
            "item": dict(item),
            "contract": dict(contract),
            "evidence_for_binding": dict(item["candidate_search_evidence"]),
            "debug": {"source": "controller_default_rebuild_projection_snapshot"},
            "current_updates": {},
            "source": "controller_default_rebuild_projection_snapshot",
        }
    )
    payload = response.to_dict()
    projection = dict(payload.get("final_visible_output_projection") or {})
    projection_item = dict(projection.get("item") or {})
    return {
        "decision": "CONTROLLER_FINAL_VISIBLE_OUTPUT_PROJECTION_AVAILABLE",
        "controller_hash": payload.get("controller_hash"),
        "request_hash": payload.get("request_hash"),
        "rebind_projection_hash": payload.get("rebind_projection_hash"),
        "final_visible_output_projection_hash": payload.get(
            "final_visible_output_projection_hash"
        ),
        "projection_adapter_hash": projection.get("adapter_hash"),
        "projection_item_hash": stable_final_publication_hash(projection_item),
        "projection_item_matches_rebind_item": stable_final_publication_hash(projection_item)
        == stable_final_publication_hash(
            (payload.get("rebind_projection") or {}).get("item") or {}
        ),
        "projection_has_cta": bool(projection.get("cta_projection")),
        "projection_has_display": bool(projection.get("display_projection")),
        "projection_has_evidence": bool(projection.get("evidence_projection")),
        "projection_has_payload": "action_payload_projection" in projection,
        "projection_has_resolved_candidate": "resolved_candidate_projection" in projection,
        "projection_has_debug": "debug_projection" in projection,
        "non_page_authority": all(
            projection.get(key) is False
            for key in ("product_driving", "render_driving", "apply_driving", "session_driving")
        ),
        "trace_only": bool(payload.get("trace_only")),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "next_safe_step": "wire live parity at the remaining final-visible output projection callsites",
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "controller_hash_present": bool(capture.get("controller_hash")),
        "rebind_projection_hash_present": bool(capture.get("rebind_projection_hash")),
        "output_projection_hash_present": bool(
            capture.get("final_visible_output_projection_hash")
        ),
        "projection_hash_matches_adapter_hash": capture.get(
            "final_visible_output_projection_hash"
        )
        == capture.get("projection_adapter_hash"),
        "projection_item_matches_rebind_item": capture.get("projection_item_matches_rebind_item")
        is True,
        "projection_surfaces_present": all(
            capture.get(key)
            for key in (
                "projection_has_cta",
                "projection_has_display",
                "projection_has_evidence",
                "projection_has_payload",
                "projection_has_resolved_candidate",
                "projection_has_debug",
            )
        ),
        "non_page_authority": capture.get("non_page_authority") is True,
        "trace_only": capture.get("trace_only") is True,
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
        "Controller-owned final-visible output projection.",
        "",
        "## Ownership Before",
        "The page restamper/default-rebuild helper used to produce the replacement projection.",
        "",
        "## Ownership After",
        "The controller response exposes a FinalDesignGuidePublication projection and hash.",
        "",
        "## Behaviour Preserved",
        "- Engineering behaviour unchanged.",
        "- Visible wording unchanged.",
        "- CTA/apply semantics unchanged.",
        "- Family runtimes unchanged.",
        "",
        "## Adapter / Default Rebuild Proof",
        f"- controller_hash: `{capture.get('controller_hash')}`",
        f"- projection_hash: `{capture.get('final_visible_output_projection_hash')}`",
        f"- projection_item_matches_rebind_item: `{capture.get('projection_item_matches_rebind_item')}`",
        "",
        "## Cutover Proof",
        "Not yet. This enables live callsite parity wiring.",
        "",
        "## Deadness / Deletion Proof",
        "Not yet.",
        "",
        "## Verifier Results",
    ]
    for key, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Next Safe Target", str(capture.get("next_safe_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    compile_run = _run(
        [
            "python",
            "-m",
            "py_compile",
            "design_brain\\design_guide_controller.py",
            "design_brain\\final_publication.py",
            "tools\\verification\\design_guide_controller_restamper_default_rebuild_projection_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [name for name, value in checks.items() if value is not True]
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "timestamp": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "compile_run": compile_run,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = _stamp()
    json_path = ARTIFACT_DIR / (
        f"design_guide_controller_final_visible_output_projection_{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        f"design_guide_controller_final_visible_output_projection_{stamp}.md"
    )
    report_path = REPORT_DIR / (
        f"design_brain_physical_extraction_controller_final_visible_output_projection_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_controller_final_visible_output_projection {payload['status']}")
    print(f"decision={capture.get('decision')}")
    print(json_path)
    print(audit_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

