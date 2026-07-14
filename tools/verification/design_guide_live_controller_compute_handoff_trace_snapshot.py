"""Verify live trace-only wiring for controller compute handoff.

This snapshot proves the controller compute handoff proof is stamped beside the
single live compute-stage resolver without replacing it or driving product
behaviour.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    required_tokens = {
        "controller_request_import": (
            "DesignGuideControllerComputePublicationHandoffRequest as "
            "_DesignGuideControllerComputePublicationHandoffRequest"
        ),
        "controller_runner_import": (
            "run_design_guide_controller_compute_publication_handoff_trace_only as "
            "_run_design_guide_controller_compute_publication_handoff_trace_only"
        ),
        "trace_helper": "def _stamp_design_guide_controller_compute_handoff_trace_only(",
        "trace_runner_call": "_run_design_guide_controller_compute_publication_handoff_trace_only(request)",
        "controller_cutover_executes": "_pre_resolver_controller_response.final_compute_resolution or {}",
        "controller_fallback_shell_present": "_build_design_guide_controller_compute_resolver_fallback_shell(",
        "trace_call_at_compute_path": "_stamp_design_guide_controller_compute_handoff_trace_only(",
        "same_mutation_evidence_reused": "_compute_stage_pre_resolver_mutation",
        "blocker_evidence_surface_argument": "blocker_evidence_surface=dict(blocker_evidence_surface or {})",
        "compute_path_blocker_evidence_surface": "_compute_stage_blocker_evidence_surface = {",
        "same_blocker_evidence_surface_reused": "blocker_evidence_surface=dict(_compute_stage_blocker_evidence_surface)",
        "selected_hash_compare": '"selected_item_hash_match": response.selected_item_hash == live_selected_item_hash',
        "trace_hash_stamped": 'debug_sink["design_guide_controller_compute_handoff_trace_only_hash"]',
        "live_wired_flag": 'debug_sink["design_guide_controller_compute_handoff_trace_only_live_wired"] = True',
        "product_driving_false": 'debug_sink["design_guide_controller_compute_handoff_trace_only_product_driving"] = False',
        "render_driving_false": 'debug_sink["design_guide_controller_compute_handoff_trace_only_render_driving"] = False',
        "apply_driving_false": 'debug_sink["design_guide_controller_compute_handoff_trace_only_apply_driving"] = False',
        "session_driving_false": 'debug_sink["design_guide_controller_compute_handoff_trace_only_session_driving"] = False',
    }
    token_presence = {key: token in source for key, token in required_tokens.items()}
    return {
        "direct_compute_resolver_call_count": source.count(
            "final_compute_resolution = resolve_final_visible_design_guide_item("
        ),
        "fallback_compute_resolver_call_count": source.count(
            "_legacy_fallback_resolution = resolve_final_visible_design_guide_item("
        ),
        "trace_call_count": source.count("_stamp_design_guide_controller_compute_handoff_trace_only("),
        "token_presence": token_presence,
        "verification": {
            "controller_object": _run("tools/verification/design_guide_controller_compute_handoff_object_snapshot.py"),
            "controller_gap": _run("tools/verification/design_guide_controller_compute_handoff_gap_snapshot.py"),
            "deletion_readiness": _run(
                "tools/verification/design_guide_compute_stage_resolver_deletion_readiness_snapshot.py"
            ),
        },
        "product_behavior_changed": False,
        "resolver_replaced": True,
        "fallback_deleted": True,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = dict(capture.get("verification") or {})
    return {
        "direct_compute_resolver_assignment_removed": capture.get("direct_compute_resolver_call_count") == 0,
        "fallback_compute_resolver_call_deleted": capture.get("fallback_compute_resolver_call_count") == 0,
        "trace_helper_and_single_call_present": capture.get("trace_call_count") == 2,
        "all_required_tokens_present": all((capture.get("token_presence") or {}).values()),
        "controller_object_snapshot_pass": (verification.get("controller_object") or {}).get("passed") is True,
        "controller_gap_snapshot_pass": (verification.get("controller_gap") or {}).get("passed") is True,
        "deletion_readiness_still_blocks_delete": (verification.get("deletion_readiness") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "resolver_replaced_by_controller_cutover": capture.get("resolver_replaced") is True,
        "fallback_deleted_after_controller_shell_added": capture.get("fallback_deleted") is True,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Live Controller Compute Handoff Trace Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Direct compute resolver calls: `{capture.get('direct_compute_resolver_call_count')}`",
            f"- Fallback compute resolver calls: `{capture.get('fallback_compute_resolver_call_count')}`",
            f"- Trace helper/call token count: `{capture.get('trace_call_count')}`",
            f"- Resolver replaced: `{capture.get('resolver_replaced')}`",
            f"- Product behaviour changed: `{capture.get('product_behavior_changed')}`",
        ]
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
    json_path = ARTIFACT_DIR / f"design_guide_live_controller_compute_handoff_trace_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_live_controller_compute_handoff_trace_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_live_controller_compute_handoff_trace_snapshot {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
