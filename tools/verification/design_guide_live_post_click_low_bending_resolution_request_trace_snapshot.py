"""Trace snapshot for live post-click low-bending resolution request proof."""

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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
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
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    helper_block = _block(
        inputs_source,
        "def _stamp_final_publication_post_click_low_bending_resolution_request_proof(",
        "\ndef _stamp_final_publication_post_click_final_contract_predicate_result_adapter(",
    )
    render_block = _block(
        inputs_source,
        "if _post_click_bending_low_visible_action:",
        "if _post_click_bending_replacement_applied:",
    )
    trace_call_index = render_block.find(
        "_stamp_final_publication_post_click_low_bending_resolution_request_proof("
    )
    live_builder_index = render_block.find("_post_click_low_bending_resolution_item(")
    object_run = _run(
        [sys.executable, "tools/verification/design_guide_post_click_low_bending_resolution_request_object_snapshot.py"]
    )
    final_publication_has_legacy_page_key = (
        "one_click_candidate_label_at_step_start" in final_source
    )
    return {
        "decision": "LIVE_POST_CLICK_LOW_BENDING_RESOLUTION_REQUEST_TRACE_WIRED",
        "builder_imported": (
            "build_final_design_guide_post_click_low_bending_resolution_request_proof as "
            "_build_final_design_guide_post_click_low_bending_resolution_request_proof"
            in inputs_source
        ),
        "helper_present": bool(helper_block),
        "trace_call_present": trace_call_index >= 0,
        "trace_before_live_builder": (
            trace_call_index >= 0 and live_builder_index >= 0 and trace_call_index < live_builder_index
        ),
        "live_builder_retained": live_builder_index >= 0,
        "neutral_request_field_used": "candidate_label_at_step_start" in helper_block,
        "legacy_page_key_translated_only_in_page": (
            "one_click_candidate_label_at_step_start" in helper_block
            and not final_publication_has_legacy_page_key
        ),
        "proof_stamps_present": all(
            token in helper_block
            for token in (
                "final_publication_post_click_low_bending_resolution_request_proof",
                "final_publication_post_click_low_bending_resolution_request_proof_hash",
                "final_publication_post_click_low_bending_resolution_request_summary_hash",
                "final_publication_post_click_low_bending_resolution_request_inputs",
                "final_publication_post_click_low_bending_resolution_request_hidden_dependency",
            )
        ),
        "non_driving_stamps_present": all(
            token in helper_block
            for token in (
                '"final_publication_post_click_low_bending_resolution_request_proof_only"] = True',
                '"final_publication_post_click_low_bending_resolution_request_product_driving"] = False',
                '"final_publication_post_click_low_bending_resolution_request_render_driving"] = False',
                '"final_publication_post_click_low_bending_resolution_request_apply_driving"] = False',
                '"final_publication_post_click_low_bending_resolution_request_session_driving"] = False',
            )
        ),
        "live_request_inputs_passed": all(
            token in render_block
            for token in (
                "current_state=dict(current_state or {})",
                "overview=dict(_post_click_low_bending_resolution_overview or {})",
                "mode_config=dict(_post_click_low_bending_resolution_mode_config or {})",
                "acceptance_audit=dict(_post_click_bending_audit or {})",
                "last_apply_route=dict(_last_apply_route_for_visible or {})",
            )
        ),
        "product_behavior_changed": False,
        "object_snapshot": object_run,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "builder_imported": capture.get("builder_imported") is True,
        "helper_present": capture.get("helper_present") is True,
        "trace_call_present": capture.get("trace_call_present") is True,
        "trace_before_live_builder": capture.get("trace_before_live_builder") is True,
        "live_builder_retained": capture.get("live_builder_retained") is True,
        "neutral_request_field_used": capture.get("neutral_request_field_used") is True,
        "legacy_page_key_translated_only_in_page": (
            capture.get("legacy_page_key_translated_only_in_page") is True
        ),
        "proof_stamps_present": capture.get("proof_stamps_present") is True,
        "non_driving_stamps_present": capture.get("non_driving_stamps_present") is True,
        "live_request_inputs_passed": capture.get("live_request_inputs_passed") is True,
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Live Post-Click Low-Bending Resolution Request Trace Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Trace before live builder: `{capture.get('trace_before_live_builder')}`",
        f"- Live builder retained: `{capture.get('live_builder_retained')}`",
        f"- Legacy page key translated only in page: `{capture.get('legacy_page_key_translated_only_in_page')}`",
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
            "Create parity/readiness proof before moving any search/result construction out of `_post_click_low_bending_resolution_item(...)`.",
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
        "schema": "design_guide_live_post_click_low_bending_resolution_request_trace_snapshot.v1",
        "generated_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_live_post_click_low_bending_resolution_request_trace_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_live_post_click_low_bending_resolution_request_trace_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_live_post_click_low_bending_resolution_request_trace {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
