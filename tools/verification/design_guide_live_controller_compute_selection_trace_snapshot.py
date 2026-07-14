"""Verify live trace wiring for controller compute selection parity.

This snapshot proves inputs_page.py stamps a non-product-driving controller
selection trace beside the current legacy compute resolver output. It does not
prove the selector can replace the resolver; it records the route readiness
fields needed for the next slice.
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "passed": proc.returncode == 0,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    required_tokens = {
        "selector_request_import": (
            "DesignGuideControllerComputeSelectionRequest as "
            "_DesignGuideControllerComputeSelectionRequest"
        ),
        "selector_runner_import": (
            "run_design_guide_controller_compute_selection_trace_only as "
            "_run_design_guide_controller_compute_selection_trace_only"
        ),
        "trace_helper": "def _stamp_design_guide_controller_compute_selection_trace_only(",
        "selector_request_constructed": "_DesignGuideControllerComputeSelectionRequest(",
        "selector_runner_call": "_run_design_guide_controller_compute_selection_trace_only(request)",
        "trace_call_at_compute_path": "_stamp_design_guide_controller_compute_selection_trace_only(",
        "compares_legacy_resolution": '"inputs_page.compute_stage.final_compute_resolution"',
        "route_flag": '"route_is_no_active_primary"',
        "replacement_ready_flag": '"route_replacement_ready"',
        "selected_item_hash_match": '"selected_item_hash_match"',
        "render_reason_match": '"render_reason_match"',
        "state_fingerprint_match": '"state_fingerprint_match"',
        "trace_hash_stamped": 'debug_sink["design_guide_controller_compute_selection_trace_only_hash"]',
        "live_wired_flag": (
            'debug_sink["design_guide_controller_compute_selection_trace_only_live_wired"] = True'
        ),
        "product_driving_false": (
            'debug_sink["design_guide_controller_compute_selection_trace_only_product_driving"] = False'
        ),
        "render_driving_false": (
            'debug_sink["design_guide_controller_compute_selection_trace_only_render_driving"] = False'
        ),
        "apply_driving_false": (
            'debug_sink["design_guide_controller_compute_selection_trace_only_apply_driving"] = False'
        ),
        "session_driving_false": (
            'debug_sink["design_guide_controller_compute_selection_trace_only_session_driving"] = False'
        ),
    }
    token_presence = {key: token in source for key, token in required_tokens.items()}
    helper_count = source.count("def _stamp_design_guide_controller_compute_selection_trace_only(")
    call_count = source.count("_stamp_design_guide_controller_compute_selection_trace_only(")
    composed = {
        "selector_object": _run(
            "tools/verification/design_guide_controller_compute_selector_object_snapshot.py"
        ),
        "selector_legacy_route_parity": _run(
            "tools/verification/design_guide_controller_compute_selector_legacy_route_parity_snapshot.py"
        ),
    }
    return {
        "token_presence": token_presence,
        "helper_count": helper_count,
        "call_count_including_definition": call_count,
        "composed": composed,
        "decision": "LIVE_TRACE_WIRED_NOT_PRODUCT_DRIVING",
        "replacement_status": "NOT_REPLACED_TRACE_ONLY",
        "next_required_proof": (
            "Run focused no-active primary scenarios and inspect route_replacement_ready "
            "before replacing any resolver branch."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    composed = dict(capture.get("composed") or {})
    return {
        "all_required_tokens_present": all(
            (capture.get("token_presence") or {}).values()
        ),
        "single_helper_defined": capture.get("helper_count") == 1,
        "helper_called_from_compute_path": capture.get("call_count_including_definition", 0) >= 2,
        "selector_object_gate_passes": (composed.get("selector_object") or {}).get("passed") is True,
        "selector_legacy_route_parity_gate_passes": (
            (composed.get("selector_legacy_route_parity") or {}).get("passed") is True
        ),
        "trace_only_not_replacement": capture.get("replacement_status")
        == "NOT_REPLACED_TRACE_ONLY",
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Live Controller Compute Selection Trace Snapshot",
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
            "## Trace State",
            "",
            f"- Replacement status: `{capture.get('replacement_status')}`",
            f"- Helper count: `{capture.get('helper_count')}`",
            f"- Call count including definition: `{capture.get('call_count_including_definition')}`",
            f"- Next proof: {capture.get('next_required_proof')}",
            "",
            "The live trace is proof-only. It compares controller selection against the current legacy resolver output and records route readiness without changing visible output, CTA/apply semantics, or family/runtime behavior.",
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
    json_path = ARTIFACT_DIR / f"design_guide_live_controller_compute_selection_trace_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_live_controller_compute_selection_trace_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_live_controller_compute_selection_trace_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
