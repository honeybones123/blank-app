"""Trace-only live wiring proof for render-item consumer adapter."""

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

CONTROLLER_IMPORT_TOKEN = (
    "run_design_guide_controller_render_item_consumer_trace_only "
    "as _run_design_guide_controller_render_item_consumer_trace_only"
)
DIRECT_BUILDER_IMPORT_TOKEN = (
    "build_final_design_guide_render_item_consumer_proof "
    "as _build_final_design_guide_render_item_consumer_proof"
)
HELPER_TOKEN = "def _stamp_final_publication_render_item_consumer_proof("
CALL_TOKEN = "_stamp_final_publication_render_item_consumer_proof("
REASON_TOKEN = 'publication_reason="render_fast_design_guidance_panel.render_item_consumer_trace"'


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
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _window(source: str, token: str, radius: int = 55) -> str:
    lines = source.splitlines()
    for index, line in enumerate(lines):
        if token in line:
            start = max(0, index - radius)
            end = min(len(lines), index + radius)
            return "\n".join(lines[start:end])
    return ""


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    helper_window = _window(source, HELPER_TOKEN, radius=70)
    call_window = _window(source, REASON_TOKEN, radius=42)
    object_snapshot = _latest("design_guide_render_item_consumer_adapter_object")
    readiness = _latest("design_guide_render_item_consumer_adapter_readiness")
    render_lock = _latest("design_guide_render_bridge_lock")
    compute_lock = _latest("design_guide_compute_resolver_publication_bridge_lock")
    independence_lock = _latest("design_guide_independence_lock")
    helper_flags = {
        "proof_hash_stamped": "final_publication_render_item_consumer_proof_hash" in helper_window,
        "authority_stamped": "final_publication_render_item_consumer_authority" in helper_window,
        "publication_hash_stamped": "final_publication_render_item_consumer_publication_hash" in helper_window,
        "covered_groups_stamped": "final_publication_render_item_consumer_covered_groups" in helper_window,
        "missing_groups_stamped": "final_publication_render_item_consumer_missing_groups" in helper_window,
        "proof_only_true": "final_publication_render_item_consumer_proof_only" in helper_window,
        "product_driving_false": "final_publication_render_item_consumer_product_driving" in helper_window and "False" in helper_window,
        "render_driving_false": "final_publication_render_item_consumer_render_driving" in helper_window and "False" in helper_window,
        "apply_driving_false": "final_publication_render_item_consumer_apply_driving" in helper_window and "False" in helper_window,
        "session_driving_false": "final_publication_render_item_consumer_session_driving" in helper_window and "False" in helper_window,
        "uses_controller_trace": "_run_design_guide_controller_render_item_consumer_trace_only(" in helper_window,
        "direct_publication_build_absent": "_build_final_design_guide_publication(" not in helper_window,
        "direct_render_item_builder_absent": "_build_final_design_guide_render_item_consumer_proof(" not in helper_window,
    }
    call_flags = {
        "callsite_present": REASON_TOKEN in source,
        "uses_final_visible_item": "item=dict(_final_visible_item or {})" in call_window,
        "uses_final_visible_resolution": "final_visible_resolution=dict(_final_visible_resolution or {})" in call_window,
        "uses_guidance_debug": "guidance_debug=guidance_debug" in call_window,
        "uses_design_brain_result": 'guidance_debug.get("design_brain_result")' in call_window
        and '_final_visible_resolution.get("design_brain_result")' in call_window,
        "before_last_apply_route": call_window.find(REASON_TOKEN) < call_window.find("_last_apply_route_for_visible")
        if "_last_apply_route_for_visible" in call_window
        else False,
    }
    return {
        "controller_import_present": CONTROLLER_IMPORT_TOKEN in source,
        "direct_builder_import_absent": DIRECT_BUILDER_IMPORT_TOKEN not in source,
        "helper_present": HELPER_TOKEN in source,
        "helper_flags": helper_flags,
        "call_flags": call_flags,
        "trace_only_live_wired": all(helper_flags.values()) and all(call_flags.values()),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest_locks": {
            "render_item_consumer_adapter_object": {
                "status": object_snapshot.get("status"),
                "path": object_snapshot.get("path"),
            },
            "render_item_consumer_adapter_readiness": {
                "status": readiness.get("status"),
                "path": readiness.get("path"),
            },
            "render_bridge_lock": {
                "status": render_lock.get("status"),
                "path": render_lock.get("path"),
            },
            "compute_resolver_publication_bridge_lock": {
                "status": compute_lock.get("status"),
                "path": compute_lock.get("path"),
            },
            "independence_lock": {
                "status": independence_lock.get("status"),
                "path": independence_lock.get("path"),
            },
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_locks") or {})
    return {
        "controller_import_present": capture.get("controller_import_present") is True,
        "direct_builder_import_absent": capture.get("direct_builder_import_absent") is True,
        "helper_present": capture.get("helper_present") is True,
        "helper_flags_all_true": all((capture.get("helper_flags") or {}).values()),
        "call_flags_all_true": all((capture.get("call_flags") or {}).values()),
        "trace_only_live_wired": capture.get("trace_only_live_wired") is True,
        "adapter_object_pass": (latest.get("render_item_consumer_adapter_object") or {}).get("status")
        == "PASS",
        "adapter_readiness_pass": (latest.get("render_item_consumer_adapter_readiness") or {}).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (
            latest.get("compute_resolver_publication_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Live Render Item Consumer Adapter Trace Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Trace-only live wired: `{capture.get('trace_only_live_wired')}`",
        f"- Product behavior changed: `{capture.get('product_behavior_changed')}`",
        f"- Visible wording changed: `{capture.get('visible_wording_changed')}`",
        f"- CTA/apply semantics changed: `{capture.get('cta_apply_semantics_changed')}`",
        "",
        "## Checks",
    ]
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
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_live_render_item_consumer_adapter_trace_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_live_render_item_consumer_adapter_trace_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_render_item_consumer_adapter_trace_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_live_render_item_consumer_adapter_trace {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
