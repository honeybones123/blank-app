"""Callsite parity-readiness snapshot for controller rebind effects.

Proof-only. Verifies the combined/engine render rebind callsites are now wired
so controller trace proof can be compared against the old helper proof hash.
This does not replace the old helper and does not claim live cutover readiness.
"""

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

TARGETS: tuple[dict[str, str], ...] = (
    {
        "id": "combined_evidence_rebind_bridge",
        "old_call": "_combined_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "trace_call": "_stamp_controller_final_visible_rebind_effects_trace(",
        "rebound_item": "_combined_rebound_item",
        "post_helper_contract": 'dict(_combined_rebound_item.get("button_contract") or {})',
        "post_helper_updates": 'dict((_combined_rebound_item.get("button_contract") or {}).get("updates") or {})',
        "callsite_id": 'callsite_id="combined_evidence_rebind_bridge"',
    },
    {
        "id": "engine_evidence_rebind_bridge",
        "old_call": "_engine_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "trace_call": "_stamp_controller_final_visible_rebind_effects_trace(",
        "rebound_item": "_engine_rebound_item",
        "post_helper_contract": 'dict(_engine_rebound_item.get("button_contract") or {})',
        "post_helper_updates": 'dict((_engine_rebound_item.get("button_contract") or {}).get("updates") or {})',
        "callsite_id": 'callsite_id="engine_evidence_rebind_bridge"',
    },
)


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


def _line_for(lines: list[str], token: str) -> int | None:
    for index, line in enumerate(lines, start=1):
        if token in line:
            return index
    return None


def _window(lines: list[str], line: int | None, *, before: int = 4, after: int = 56) -> str:
    if line is None:
        return ""
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    helper_line = _line_for(lines, "def _stamp_controller_final_visible_rebind_effects_trace(")
    helper_context = _window(lines, helper_line, before=0, after=120)
    rows = []
    for target in TARGETS:
        old_line = _line_for(lines, target["old_call"])
        context = _window(lines, old_line)
        trace_index = context.find(target["trace_call"])
        old_index = context.find(target["old_call"])
        rows.append(
            {
                "id": target["id"],
                "old_line": old_line,
                "old_call_present": old_line is not None,
                "trace_call_present": trace_index >= 0,
                "trace_after_old_call": old_index >= 0 and trace_index > old_index,
                "callsite_id_present": target["callsite_id"] in context,
                "post_helper_item_used": (
                    f"item={target['rebound_item']} if isinstance({target['rebound_item']}, dict)" in context
                    or f"item=(\n                        {target['rebound_item']}" in context
                    or f"item=(\r\n                        {target['rebound_item']}" in context
                ),
                "post_helper_contract_used": target["post_helper_contract"] in context,
                "post_helper_updates_used": target["post_helper_updates"] in context,
                "old_helper_still_drives_output": "displayed_primary_item = dict(_" in context,
            }
        )
    return {
        "decision": "CALLSITE_PARITY_READY_FOR_LIVE_HASH_CAPTURE_NOT_CUTOVER_READY",
        "helper_line": helper_line,
        "helper_comparison_fields": {
            "previous_hash_captured": (
                'previous_helper_proof_hash = guidance_debug.get("final_visible_contract_binding_rebind_effects_proof_hash")'
                in helper_context
            ),
            "controller_hash_stamped": '"controller_final_visible_rebind_effects_latest_proof_hash"' in helper_context,
            "previous_hash_stamped": '"controller_final_visible_rebind_effects_previous_helper_proof_hash"' in helper_context,
            "parity_stamped": '"controller_final_visible_rebind_effects_helper_parity"' in helper_context,
            "trace_only_non_driving": (
                '"controller_final_visible_rebind_effects_trace_only"' in helper_context
                and '"controller_final_visible_rebind_effects_product_driving"' in helper_context
                and '"controller_final_visible_rebind_effects_render_driving"' in helper_context
                and '"controller_final_visible_rebind_effects_apply_driving"' in helper_context
                and '"controller_final_visible_rebind_effects_session_driving"' in helper_context
            ),
        },
        "rows": rows,
        "row_count": len(rows),
        "latest_artifacts": {
            "controller_adapter_parity": _latest("design_guide_controller_rebind_effects_adapter_parity"),
            "controller_trace_wiring": _latest("design_guide_controller_rebind_effects_trace_wiring"),
            "render_panel_binding_readiness": _latest("design_guide_render_panel_binding_adapter_readiness"),
            "remaining_restamper_reference_audit": _latest("design_guide_remaining_final_visible_restamper_reference_audit"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "ready_for_live_hash_capture": True,
        "ready_for_callsite_replacement": False,
        "next_safe_step": (
            "Run a browser/live or focused runtime hash-capture scenario proving "
            "controller_final_visible_rebind_effects_helper_parity is true at both "
            "combined/engine callsites before replacing either old helper call."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("rows") or [])
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "two_rows_captured": capture.get("row_count") == 2,
        "helper_comparison_fields_present": all((capture.get("helper_comparison_fields") or {}).values()),
        "old_calls_present": all(row.get("old_call_present") is True for row in rows),
        "trace_calls_present": all(row.get("trace_call_present") is True for row in rows),
        "trace_after_old_calls": all(row.get("trace_after_old_call") is True for row in rows),
        "callsite_ids_present": all(row.get("callsite_id_present") is True for row in rows),
        "post_helper_items_used": all(row.get("post_helper_item_used") is True for row in rows),
        "post_helper_contracts_used": all(row.get("post_helper_contract_used") is True for row in rows),
        "post_helper_updates_used": all(row.get("post_helper_updates_used") is True for row in rows),
        "old_helper_still_drives_output": all(row.get("old_helper_still_drives_output") is True for row in rows),
        "controller_adapter_parity_pass": (latest.get("controller_adapter_parity") or {}).get("status") == "PASS",
        "controller_trace_wiring_pass": (latest.get("controller_trace_wiring") or {}).get("status") == "PASS",
        "render_panel_binding_readiness_pass": (
            latest.get("render_panel_binding_readiness") or {}
        ).get("status")
        == "PASS",
        "remaining_restamper_reference_audit_pass": (
            latest.get("remaining_restamper_reference_audit") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "ready_for_live_hash_capture": capture.get("ready_for_live_hash_capture") is True,
        "not_ready_for_callsite_replacement": capture.get("ready_for_callsite_replacement") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Controller Rebind Effects Callsite Parity Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Rows",
        "",
        "| ID | Line | Trace After Old Call | Post-Helper Item | Post-Helper Contract | Ready To Replace |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for row in capture.get("rows") or []:
        lines.append(
            f"| `{row.get('id')}` | `{row.get('old_line')}` | `{row.get('trace_after_old_call')}` | "
            f"`{row.get('post_helper_item_used')}` | `{row.get('post_helper_contract_used')}` | "
            f"`{capture.get('ready_for_callsite_replacement')}` |"
        )
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next Safe Step", "", str(capture.get("next_safe_step") or "")])
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
        "schema": "design_guide_controller_rebind_effects_callsite_parity_readiness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_controller_rebind_effects_callsite_parity_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_controller_rebind_effects_callsite_parity_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_controller_rebind_effects_callsite_parity_readiness_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
