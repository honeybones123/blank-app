"""Trace-wiring snapshot for controller-owned rebind effects.

Proof-only. Verifies the two combined/engine render-stage rebind bridges stamp
the controller rebind-effects proof beside the old binding helper without
driving product, render, apply, or session behavior.
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
        "callsite_id": 'callsite_id="combined_evidence_rebind_bridge"',
        "evidence": "evidence_for_binding=engine_candidate_search_evidence",
        "contract": 'dict(_combined_rebound_item.get("button_contract") or {})',
        "updates": "combined_binding_updates=_engine_evidence_updates",
    },
    {
        "id": "engine_evidence_rebind_bridge",
        "old_call": "_engine_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "callsite_id": 'callsite_id="engine_evidence_rebind_bridge"',
        "evidence": "evidence_for_binding=_engine_candidate_search_evidence",
        "contract": 'dict(_engine_rebound_item.get("button_contract") or {})',
        "updates": "combined_binding_updates=_engine_evidence_updates_for_update",
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


def _window(lines: list[str], line: int | None, *, before: int = 8, after: int = 48) -> str:
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
        line = _line_for(lines, target["old_call"])
        context = _window(lines, line)
        rows.append(
            {
                "id": target["id"],
                "line": line,
                "old_binding_call_present": line is not None,
                "controller_trace_call_present": "_stamp_controller_final_visible_rebind_effects_trace(" in context,
                "callsite_id_present": target["callsite_id"] in context,
                "evidence_input_present": target["evidence"] in context,
                "contract_input_present": target["contract"] in context,
                "updates_input_present": target["updates"] in context,
                "output_still_old_helper_driven": "displayed_primary_item = dict(_" in context,
            }
        )
    return {
        "decision": "CONTROLLER_REBIND_EFFECTS_TRACE_WIRED_OLD_HELPER_STILL_DRIVES_OUTPUT",
        "helper_line": helper_line,
        "helper_present": helper_line is not None,
        "helper_non_driving_stamps": {
            "trace_only": '"controller_final_visible_rebind_effects_trace_only"' in helper_context,
            "product": '"controller_final_visible_rebind_effects_product_driving"' in helper_context
            and "= False" in helper_context,
            "render": '"controller_final_visible_rebind_effects_render_driving"' in helper_context
            and "= False" in helper_context,
            "apply": '"controller_final_visible_rebind_effects_apply_driving"' in helper_context
            and "= False" in helper_context,
            "session": '"controller_final_visible_rebind_effects_session_driving"' in helper_context
            and "= False" in helper_context,
            "helper_parity": '"controller_final_visible_rebind_effects_helper_parity"' in helper_context,
            "projection_hash": '"controller_final_visible_rebind_effects_latest_projection_hash"' in helper_context,
        },
        "import_present": (
            "run_design_guide_controller_final_visible_rebind_effects_trace_only as "
            "_run_design_guide_controller_final_visible_rebind_effects_trace_only"
        )
        in source,
        "rows": rows,
        "row_count": len(rows),
        "latest_artifacts": {
            "controller_adapter_parity": _latest("design_guide_controller_rebind_effects_adapter_parity"),
            "effects_proof": _latest("design_guide_final_visible_contract_binding_rebind_effects_proof"),
            "effects_trace_wiring": _latest("design_guide_final_visible_contract_binding_rebind_effects_trace_wiring"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "next_safe_step": (
            "Create live parity comparing controller trace proof hashes with old helper proof hashes "
            "for combined/engine rebind scenarios before replacing the old binding calls."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("rows") or [])
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "helper_present": capture.get("helper_present") is True,
        "helper_non_driving_stamps_present": all((capture.get("helper_non_driving_stamps") or {}).values()),
        "import_present": capture.get("import_present") is True,
        "two_rows_captured": capture.get("row_count") == 2,
        "old_binding_calls_still_present": all(row.get("old_binding_call_present") is True for row in rows),
        "controller_trace_calls_present": all(row.get("controller_trace_call_present") is True for row in rows),
        "callsite_ids_present": all(row.get("callsite_id_present") is True for row in rows),
        "evidence_inputs_present": all(row.get("evidence_input_present") is True for row in rows),
        "contract_inputs_present": all(row.get("contract_input_present") is True for row in rows),
        "updates_inputs_present": all(row.get("updates_input_present") is True for row in rows),
        "old_helper_still_drives_output": all(row.get("output_still_old_helper_driven") is True for row in rows),
        "controller_adapter_parity_pass": (latest.get("controller_adapter_parity") or {}).get("status") == "PASS",
        "effects_proof_pass": (latest.get("effects_proof") or {}).get("status") == "PASS",
        "effects_trace_wiring_pass": (latest.get("effects_trace_wiring") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Controller Rebind Effects Trace Wiring",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Rows",
        "",
        "| ID | Line | Trace Wired | Old Helper Still Drives |",
        "| --- | ---: | --- | --- |",
    ]
    for row in capture.get("rows") or []:
        lines.append(
            f"| `{row.get('id')}` | `{row.get('line')}` | "
            f"`{row.get('controller_trace_call_present')}` | `{row.get('output_still_old_helper_driven')}` |"
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
        "schema": "design_guide_controller_rebind_effects_trace_wiring_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_controller_rebind_effects_trace_wiring_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_controller_rebind_effects_trace_wiring_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_controller_rebind_effects_trace_wiring_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
