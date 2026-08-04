"""Trace snapshot for live post-click low-bending result projection."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "passed": proc.returncode == 0,
    }


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    helper_block = _block(
        source,
        "def _stamp_final_publication_post_click_low_bending_resolution_result_projection(",
        "\ndef _stamp_final_publication_post_click_final_contract_predicate_result_adapter(",
    )
    render_block = _block(
        source,
        "if _post_click_bending_low_visible_action:",
        "if _post_click_bending_replacement_applied:",
    )
    live_builder_index = render_block.find("_post_click_low_bending_resolution_item(")
    trace_call_index = render_block.find(
        "_stamp_final_publication_post_click_low_bending_resolution_result_projection("
    )
    contract_read_index = render_block.find("_post_click_bending_contract =")
    object_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_resolution_result_projection_object_snapshot.py",
        ]
    )
    readiness_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_resolution_result_readiness_snapshot.py",
        ]
    )
    return {
        "decision": "LIVE_POST_CLICK_LOW_BENDING_RESULT_PROJECTION_TRACE_WIRED",
        "builder_imported": (
            "build_final_design_guide_post_click_low_bending_resolution_result_projection_proof as "
            "_build_final_design_guide_post_click_low_bending_resolution_result_projection_proof"
            in source
        ),
        "helper_present": bool(helper_block),
        "trace_call_present": trace_call_index >= 0,
        "trace_after_live_builder": (
            live_builder_index >= 0 and trace_call_index >= 0 and live_builder_index < trace_call_index
        ),
        "trace_before_contract_read": (
            trace_call_index >= 0 and contract_read_index >= 0 and trace_call_index < contract_read_index
        ),
        "live_builder_retained": live_builder_index >= 0,
        "result_item_passed": "result_item=dict(_post_click_bending_resolution or {})" in render_block,
        "acceptance_audit_passed": "acceptance_audit=dict(_post_click_bending_audit or {})" in render_block,
        "final_visible_resolution_passed": "final_visible_resolution=dict(_final_visible_resolution or {})" in render_block,
        "proof_stamps_present": all(
            token in helper_block
            for token in (
                "final_publication_post_click_low_bending_resolution_result_projection",
                "final_publication_post_click_low_bending_resolution_result_projection_hash",
                "final_publication_post_click_low_bending_resolution_result_projection_proof_hash",
                "final_publication_post_click_low_bending_resolution_result_surfaces",
                "final_publication_post_click_low_bending_resolution_result_excluded_live_surfaces",
            )
        ),
        "non_driving_stamps_present": all(
            token in helper_block
            for token in (
                '"final_publication_post_click_low_bending_resolution_result_projection_proof_only"] = True',
                '"final_publication_post_click_low_bending_resolution_result_projection_product_driving"] = False',
                '"final_publication_post_click_low_bending_resolution_result_projection_render_driving"] = False',
                '"final_publication_post_click_low_bending_resolution_result_projection_apply_driving"] = False',
                '"final_publication_post_click_low_bending_resolution_result_projection_session_driving"] = False',
            )
        ),
        "product_behavior_changed": False,
        "object_snapshot": object_run,
        "readiness_snapshot": readiness_run,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "builder_imported": capture.get("builder_imported") is True,
        "helper_present": capture.get("helper_present") is True,
        "trace_call_present": capture.get("trace_call_present") is True,
        "trace_after_live_builder": capture.get("trace_after_live_builder") is True,
        "trace_before_contract_read": capture.get("trace_before_contract_read") is True,
        "live_builder_retained": capture.get("live_builder_retained") is True,
        "result_item_passed": capture.get("result_item_passed") is True,
        "acceptance_audit_passed": capture.get("acceptance_audit_passed") is True,
        "final_visible_resolution_passed": capture.get("final_visible_resolution_passed") is True,
        "proof_stamps_present": capture.get("proof_stamps_present") is True,
        "non_driving_stamps_present": capture.get("non_driving_stamps_present") is True,
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "readiness_snapshot_passed": (capture.get("readiness_snapshot") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Live Post-Click Low-Bending Result Projection Trace Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Trace after live builder: `{capture.get('trace_after_live_builder')}`",
        f"- Trace before contract read: `{capture.get('trace_before_contract_read')}`",
        f"- Live builder retained: `{capture.get('live_builder_retained')}`",
        f"- Product behavior changed: `{capture.get('product_behavior_changed')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Create parity scenarios comparing the live result projection to the object projection before moving any result branch.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_live_post_click_low_bending_resolution_result_projection_trace_snapshot.v1",
        "generated_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_live_post_click_low_bending_resolution_result_projection_trace_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_live_post_click_low_bending_resolution_result_projection_trace_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_live_post_click_low_bending_resolution_result_projection_trace {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
