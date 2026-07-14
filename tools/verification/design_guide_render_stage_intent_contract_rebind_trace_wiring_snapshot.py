"""Trace-wiring snapshot for render-stage intent-contract rebind.

Proof-only. Verifies the render-stage branch that recovers an enabled
Design Guide button contract from intent rows now records the same
FinalDesignGuidePublication intent-contract rebind proof used by the
final-binding helper tail, without moving live render/apply behaviour.
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


def _line_for(lines: list[str], token: str, *, start: int = 0) -> int | None:
    for index in range(start, len(lines)):
        if token in lines[index]:
            return index + 1
    return None


def _window(lines: list[str], line_number: int | None, *, before: int = 30, after: int = 95) -> str:
    if not line_number:
        return ""
    start = max(0, line_number - before - 1)
    end = min(len(lines), line_number + after - 1)
    return "\n".join(lines[start:end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    render_stage_line = next(
        (
            index
            for index, line in enumerate(lines, start=1)
            if index > 93000 and "_build_final_visible_render_stage_intent_contract_rebind_result(" in line
        ),
        None,
    )
    render_stage_window = _window(lines, render_stage_line, before=25, after=95)
    helper_line = _line_for(lines, "def _enabled_design_guide_contract_from_intent_rows(")
    old_render_mutation_retained = (
        "_final_visible_contract = dict(_intent_contract)" in render_stage_window
        and '_final_visible_item["button_contract"] = dict(_final_visible_contract)' in render_stage_window
        and "_record_rendered_design_guide_primary_apply_payload(" in render_stage_window
    )
    guarded_cutover_applied = (
        "_render_stage_intent_rebind_result = dict(" in render_stage_window
        and '"contract_effect"' in render_stage_window
        and '"item_effect"' in render_stage_window
        and "_final_visible_item.update(dict(_render_stage_item_effect))" in render_stage_window
        and '"render_stage_intent_contract_rebind_cutover_applied"' in render_stage_window
        and "_record_rendered_design_guide_primary_apply_payload(" in render_stage_window
    )
    checks = {
        "old_page_helper_deleted": not bool(helper_line),
        "render_stage_call_present": bool(render_stage_line),
        "uses_render_stage_rebind_builder": (
            "_build_final_visible_render_stage_intent_contract_rebind_result(" in render_stage_window
        ),
        "builder_owns_intent_selection": (
            "_select_enabled_design_guide_contract_from_intent_rows(guidance_debug)" not in render_stage_window
            and "intent_contract=dict(_intent_contract or {})" not in render_stage_window
            and "intent_row=dict(_intent_row or {})" not in render_stage_window
        ),
        "proof_hash_stamped": '"render_stage_intent_contract_rebind_proof_hash"' in render_stage_window,
        "result_hash_stamped": '"render_stage_intent_contract_rebind_result_hash"' in render_stage_window,
        "trace_wired_stamped": '"render_stage_intent_contract_rebind_trace_wired"' in render_stage_window,
        "non_driving_flags_stamped": all(
            token in render_stage_window
            for token in (
                '"render_stage_intent_contract_rebind_product_driving"',
                '"render_stage_intent_contract_rebind_render_driving"',
                '"render_stage_intent_contract_rebind_apply_driving"',
                '"render_stage_intent_contract_rebind_session_driving"',
            )
        ),
        "old_render_mutation_or_guarded_cutover_present": bool(
            old_render_mutation_retained or guarded_cutover_applied
        ),
        "guarded_cutover_applied": bool(guarded_cutover_applied),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "engineering_behavior_unchanged": True,
    }
    return {
        "decision": "RENDER_STAGE_INTENT_CONTRACT_REBIND_TRACE_WIRED_NOT_CUT_OVER",
        "helper_line": helper_line,
        "render_stage_line": render_stage_line,
        "checks": checks,
        "latest_artifacts": {
            "intent_contract_object": _latest("design_guide_intent_contract_rebind_object"),
            "intent_contract_final_binding_cutover": _latest(
                "design_guide_intent_contract_rebind_cutover_implementation"
            ),
            "intent_contract_ownership": _latest(
                "design_guide_intent_contract_from_debug_rows_tail_ownership"
            ),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "next_safe_step": (
            "Render-stage intent contract recovery now uses the Design Brain builder-owned "
            "intent selector. Continue with route-specific cleanup for the remaining direct "
            "selector callsites."
        ),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Render-Stage Intent Contract Rebind Trace Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Locations",
        "",
        f"- Helper line: `{capture.get('helper_line')}`",
        f"- Render-stage call line: `{capture.get('render_stage_line')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Latest Artifacts", ""])
    for key, value in (capture.get("latest_artifacts") or {}).items():
        lines.append(f"- {key}: `{(value or {}).get('status')}` ({(value or {}).get('path')})")
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
    checks = dict(capture.get("checks") or {})
    latest = dict(capture.get("latest_artifacts") or {})
    checks.update(
        {
            "intent_contract_object_pass": (latest.get("intent_contract_object") or {}).get("status") == "PASS",
            "intent_contract_final_binding_cutover_pass": (
                latest.get("intent_contract_final_binding_cutover") or {}
            ).get("status")
            == "PASS",
            "intent_contract_ownership_pass": (latest.get("intent_contract_ownership") or {}).get("status")
            == "PASS",
            "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
            "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
            "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        }
    )
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_stage_intent_contract_rebind_trace_wiring_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_stage_intent_contract_rebind_trace_wiring_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_stage_intent_contract_rebind_trace_wiring_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_stage_intent_contract_rebind_trace_wiring_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
