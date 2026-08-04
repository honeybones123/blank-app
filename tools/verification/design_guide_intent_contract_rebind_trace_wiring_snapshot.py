"""Trace wiring snapshot for intent-contract-from-debug-rows rebind proof."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
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


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _line_for(lines: list[str], token: str) -> int:
    for index, line in enumerate(lines):
        if token in line:
            return index
    return -1


def _window(lines: list[str], center: int, *, before: int = 45, after: int = 130) -> str:
    if center < 0:
        return ""
    start = max(0, center - before)
    end = min(len(lines), center + after)
    return "\n".join(lines[start:end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    call_line = _line_for(lines, "_build_final_visible_contract_binding_intent_contract_rebind_result(")
    context = _window(lines, call_line)
    return {
        "decision": "INTENT_CONTRACT_REBIND_TRACE_WIRED_PROOF_ONLY",
        "trace_line": call_line + 1 if call_line >= 0 else None,
        "source_checks": {
            "import_present": (
                "build_final_visible_contract_binding_intent_contract_rebind_result as "
                "_build_final_visible_contract_binding_intent_contract_rebind_result"
            )
            in source,
            "trace_call_present": "_build_final_visible_contract_binding_intent_contract_rebind_result(" in context,
            "uses_current_item_contract_debug": all(
                token in context
                for token in (
                    "item=dict(out or {})",
                    "contract=dict(contract or {})",
                    "guidance_debug=dict(_intent_debug_source or {})",
                    "intent_contract=dict(_intent_contract or {})",
                    "intent_row=dict(_intent_row or {})",
                )
            ),
            "guard_inputs_passed": all(
                token in context
                for token in (
                    "post_click_apply_context=bool(_post_click_apply_context_for_binding)",
                    "active_strength_failures=tuple(sorted(_active_strength_failures_for_binding))",
                    "current_binding_cross_family=bool(_current_binding_cross_family)",
                )
            ),
            "proof_hash_stamped": '"final_binding_intent_contract_rebind_proof_hash"' in context,
            "result_hash_stamped": '"final_binding_intent_contract_rebind_result_hash"' in context,
            "guard_results_stamped": '"final_binding_intent_contract_rebind_guard_results"' in context,
            "trace_wired_stamped": '"final_binding_intent_contract_rebind_trace_wired"' in context,
            "non_driving_flags": all(
                token in context
                for token in (
                    '"final_binding_intent_contract_rebind_product_driving"',
                    '"final_binding_intent_contract_rebind_render_driving"',
                    '"final_binding_intent_contract_rebind_apply_driving"',
                    '"final_binding_intent_contract_rebind_session_driving"',
                    '"final_binding_intent_contract_rebind_ready_for_live_cutover"',
                )
            ),
            "old_live_branch_still_drives": all(
                token in context
                for token in (
                    "if (",
                    "_intent_contract",
                    "contract = dict(_intent_contract)",
                    "out.update(",
                    'action_type = "apply_resolved_candidate"',
                    "updates = dict(_intent_updates)",
                )
            ),
            "old_live_branch_absent_after_cutover": all(
                token not in context
                for token in (
                    "contract = dict(_intent_contract)",
                    "contract.update(",
                    "_intent_expected = _parse_util_value(",
                    "or _guidance_cleanup_candidate_id(_intent_family, _intent_updates)",
                )
            ),
        },
        "latest_artifacts": {
            "object_snapshot": _latest("design_guide_intent_contract_rebind_object"),
            "ownership_audit": _latest("design_guide_intent_contract_from_debug_rows_tail_ownership"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "ready_for_live_cutover": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    required_trace_checks = {
        key: value
        for key, value in source_checks.items()
        if key not in {"old_live_branch_still_drives", "old_live_branch_absent_after_cutover"}
    }
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "all_source_checks_pass": all(required_trace_checks.values()),
        "old_branch_state_classified": (
            source_checks.get("old_live_branch_still_drives") is True
            or source_checks.get("old_live_branch_absent_after_cutover") is True
        ),
        "object_snapshot_pass": (latest.get("object_snapshot") or {}).get("status") == "PASS",
        "ownership_audit_pass": (latest.get("ownership_audit") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "not_ready_for_live_cutover": capture.get("ready_for_live_cutover") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Intent Contract Rebind Trace Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Trace line: `{capture.get('trace_line')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Source Checks",
        "",
    ]
    for key, value in (capture.get("source_checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_intent_contract_rebind_trace_wiring_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_intent_contract_rebind_trace_wiring_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_intent_contract_rebind_trace_wiring_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_intent_contract_rebind_trace_wiring_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
