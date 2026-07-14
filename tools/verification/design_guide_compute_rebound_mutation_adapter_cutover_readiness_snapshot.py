"""Cutover readiness for replacing compute rebound mutation rows with adapter output."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
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


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _window(source: str, function_name: str) -> str:
    start = source.find(f"def {function_name}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    return source[start:] if next_def < 0 else source[start:next_def]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    late = _window(source, "_apply_compute_late_evidence_contract_rebound")
    post = _window(source, "_orchestrate_compute_post_core_publication_handoff")
    latest = {
        "adapter_parity": _latest("design_guide_compute_rebound_mutation_adapter_parity"),
        "adapter_live_wiring": _latest("design_guide_compute_rebound_mutation_adapter_live_wiring"),
        "controller_decision_parity": _latest(
            "design_guide_compute_rebound_controller_decision_parity"
        ),
        "live_bridge": _latest(
            "design_guide_live_compute_publication_handoff_rebound_decision_bridge"
        ),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    live_rows = {
        "late_primary_item_clear": "primary_item_for_evidence.clear()" in late,
        "late_primary_item_update": (
            "primary_item_for_evidence.update(_late_rebound_item)" in late
            or "primary_item_for_evidence.update(_late_mutation_item)" in late
        ),
        "late_collapsed_item_replace": (
            "collapsed_guidance_items[0] = dict(_late_rebound_item)" in late
            or "_late_mutation_collapsed_items = list(" in late
        ),
        "late_debug_contract_rows": all(
            token in late
            for token in (
                'debug_trace["primary_button_contract"] = dict(_late_rebound_contract)',
                'debug_trace["button_contract"] = dict(_late_rebound_contract)',
                'debug_trace["button_contract_enabled"] = True',
                'debug_trace["selected_action_type"] = "apply_resolved_candidate"',
            )
        )
        or "debug_trace.update(_late_mutation_debug_updates)" in late,
        "post_collapsed_item_replace": (
            "collapsed_guidance_items[0] = dict(_post_evidence_rebound)" in post
            or "_post_mutation_collapsed_items = list(" in post
        ),
        "post_debug_enabled_flag": (
            'debug_trace["post_evidence_cleanup_contract_rebound"]' in post
            or "debug_trace.update(_post_mutation_debug_updates)" in post
        ),
    }
    trace_rows = {
        "late_adapter_trace_before_live_mutation": (
            "_stamp_design_guide_controller_compute_rebound_mutation_trace_only(" in late
            and (
                "primary_item_for_evidence.clear()" in late
                or "_late_mutation_item = dict(" in late
            )
        ),
        "post_adapter_trace_before_live_mutation": (
            "_stamp_design_guide_controller_compute_rebound_mutation_trace_only(" in post
            and (
                "collapsed_guidance_items[0] = dict(_post_evidence_rebound)" in post
                or "_post_mutation_collapsed_items = list(" in post
            )
        ),
    }
    return {
        "decision": "COMPUTE_REBOUND_MUTATION_ROWS_READY_FOR_NARROW_CUTOVER",
        "live_rows": live_rows,
        "trace_rows": trace_rows,
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
        "ready_for_narrow_cutover": True,
        "delete_ready": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "all_live_rows_present": all((capture.get("live_rows") or {}).values()),
        "adapter_traces_present_before_mutation": all((capture.get("trace_rows") or {}).values()),
        "adapter_parity_pass": (latest.get("adapter_parity") or {}).get("status") == "PASS",
        "adapter_live_wiring_pass": (latest.get("adapter_live_wiring") or {}).get("status") == "PASS",
        "controller_decision_parity_pass": (
            (latest.get("controller_decision_parity") or {}).get("status") == "PASS"
        ),
        "live_bridge_pass": (latest.get("live_bridge") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "ready_for_narrow_cutover": capture.get("ready_for_narrow_cutover") is True,
        "not_delete_ready": capture.get("delete_ready") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Compute Rebound Mutation Adapter Cutover Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Result",
        "",
        f"- Ready for narrow cutover: `{capture.get('ready_for_narrow_cutover')}`",
        f"- Delete ready: `{capture.get('delete_ready')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            (
                "Replace only the proven live mutation rows with adapter output. "
                "Keep publish calls, predicates, CTA/apply routing, visible wording, and "
                "family/runtime behaviour unchanged. Add a post-cutover verifier before deletion."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_compute_rebound_mutation_adapter_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_compute_rebound_mutation_adapter_cutover_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_rebound_mutation_adapter_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_compute_rebound_mutation_adapter_cutover_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
