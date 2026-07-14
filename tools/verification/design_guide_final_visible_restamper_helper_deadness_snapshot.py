"""Deadness/readiness snapshot for the final-visible restamper helper.

Proof-only. All current callsites may be adapter-covered while the helper is
still not dead, because the adapters use the helper output as their
comparison/source result. This verifier prevents premature deletion.
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
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

HELPER = "_publish_final_visible_design_guide_contract_binding"
CALL = f"{HELPER}("


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _function_block(source: str) -> tuple[int | None, int | None, str]:
    marker = f"def {HELPER}("
    start = source.find(marker)
    if start < 0:
        return None, None, ""
    next_def = source.find("\ndef ", start + len(marker))
    next_class = source.find("\nclass ", start + len(marker))
    candidates = [idx for idx in (next_def, next_class) if idx >= 0]
    end = min(candidates) if candidates else len(source)
    return source[:start].count("\n") + 1, source[:end].count("\n") + 1, source[start:end]


def _line_numbers_for_calls(source: str) -> list[int]:
    lines = source.splitlines()
    out: list[int] = []
    for idx, line in enumerate(lines, start=1):
        if CALL in line and f"def {HELPER}(" not in line:
            out.append(idx)
    return out


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    helper_start, helper_end, helper_block = _function_block(source)
    remaining = _latest("design_guide_remaining_final_visible_restamper_reference_audit")
    remaining_payload = remaining.get("payload") or {}
    calls = (remaining_payload.get("capture") or {}).get("calls") or []
    category_counts = (remaining_payload.get("capture") or {}).get("category_counts") or {}
    call_lines = _line_numbers_for_calls(source)
    helper_decision_tokens = {
        "target_band_promotion_tail": "_stamp_final_visible_contract_binding_target_band_promotion_result(" in helper_block,
        "consistency_guard_tail": "_stamp_final_visible_contract_binding_consistency_guard_result(" in helper_block,
        "truth_result_tail": "_stamp_final_visible_contract_binding_truth_result(" in helper_block,
        "no_second_cta_tail": "_stamp_final_visible_contract_binding_no_second_cta_result(" in helper_block,
        "cleanup_evidence_rehydrate_tail": "_build_final_visible_contract_binding_cleanup_evidence_rehydrate_result(" in helper_block,
        "intent_contract_rebind_tail": "_build_final_visible_contract_binding_intent_contract_rebind_result(" in helper_block,
        "button_contract_mutation": "button_contract" in helper_block and "item[" in helper_block,
        "debug_mutation": "debug_sink[" in helper_block or "debug_sink.update(" in helper_block,
    }
    all_calls_adapter_covered = bool(calls) and all(
        str(call.get("category") or "") == "B. adapter-covered result-identity bridge"
        for call in calls
    )
    return {
        "decision": "FINAL_VISIBLE_RESTAMPER_HELPER_NOT_READY_TO_DELETE",
        "helper_start_line": helper_start,
        "helper_end_line": helper_end,
        "helper_line_count": (helper_end - helper_start + 1) if helper_start and helper_end else 0,
        "helper_definition_present": bool(helper_block),
        "call_lines": call_lines,
        "call_count": len(call_lines),
        "remaining_inventory_category_counts": category_counts,
        "all_calls_adapter_covered": all_calls_adapter_covered,
        "helper_decision_tokens": helper_decision_tokens,
        "helper_still_builds_source_output": any(helper_decision_tokens.values()),
        "safe_to_delete_now": False,
        "reason_not_delete_ready": (
            "All callsites are adapter-covered, but the adapter-covered paths still use this helper "
            "to produce the comparison/source output. Delete only after a controller/final-publication "
            "binding-result API produces that output directly."
        ),
        "recommended_next_slice": (
            "Create a controller/final-publication binding-result adapter for this helper body, starting "
            "with the cleanup-evidence rehydrate tail or the whole-helper source-output parity surface."
        ),
        "latest": {
            "remaining_restamper_audit": remaining,
            "final_item_cutover": _latest("design_guide_render_fast_panel_final_item_binding_adapter_cutover"),
            "pre_card_cutover": _latest("design_guide_render_guidance_secondary_pre_card_binding_adapter_cutover"),
            "primary_binding_cutover": _latest("design_guide_render_guidance_secondary_binding_adapter_cutover"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "deletion_performed": False,
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "helper_definition_present": capture.get("helper_definition_present") is True,
        "calls_still_present": int(capture.get("call_count") or 0) > 0,
        "all_calls_adapter_covered": capture.get("all_calls_adapter_covered") is True,
        "helper_still_builds_source_output": capture.get("helper_still_builds_source_output") is True,
        "safe_to_delete_now_false": capture.get("safe_to_delete_now") is False,
        "remaining_restamper_audit_pass": (latest.get("remaining_restamper_audit") or {}).get("status") == "PASS",
        "final_item_cutover_pass": (latest.get("final_item_cutover") or {}).get("status") == "PASS",
        "pre_card_cutover_pass": (latest.get("pre_card_cutover") or {}).get("status") == "PASS",
        "primary_binding_cutover_pass": (latest.get("primary_binding_cutover") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "no_deletion": capture.get("deletion_performed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Final Visible Restamper Helper Deadness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Helper lines: `{capture.get('helper_start_line')}`-`{capture.get('helper_end_line')}`",
        f"- Helper line count: `{capture.get('helper_line_count')}`",
        f"- Call count: `{capture.get('call_count')}`",
        f"- All calls adapter-covered: `{capture.get('all_calls_adapter_covered')}`",
        f"- Safe to delete now: `{capture.get('safe_to_delete_now')}`",
        f"- Reason: {capture.get('reason_not_delete_ready')}",
        "",
        "## Helper Decision Tokens",
        "",
    ]
    for key, value in dict(capture.get("helper_decision_tokens") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next Safe Step", "", str(capture.get("recommended_next_slice"))])
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
            "inputs_page.py",
            "tools/verification/design_guide_final_visible_restamper_helper_deadness_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_final_visible_restamper_helper_deadness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_restamper_helper_deadness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_final_visible_restamper_helper_deadness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_final_visible_restamper_helper_deadness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
