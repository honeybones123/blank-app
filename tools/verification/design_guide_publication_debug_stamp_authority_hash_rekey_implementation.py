"""Implementation proof for duplicate debug publication stamp authority-hash rekey."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
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


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "passed": False}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "path": str(path), "passed": False, "error": str(exc)}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    passed = "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper()
    return {"found": True, "path": str(path), "passed": passed}


def _body(source: str, marker: str, *, end_marker: str | None = None) -> str:
    start = source.find(marker)
    if start < 0:
        return ""
    if end_marker:
        end = source.find(end_marker, start + len(marker))
    else:
        end = source.find("\ndef ", start + len(marker))
    if end < 0:
        end = min(len(source), start + 5000)
    return source[start:end]


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Publication Debug Stamp Authority-Hash Rekey Implementation",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Guards",
        "",
        "```json",
        json.dumps(payload["guards"], indent=2, sort_keys=True),
        "```",
        "",
        "## Failures",
        "",
    ]
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    guard_body = _body(source, "def _final_publication_current_hash_from_debug")
    decision_body = _body(source, "def _final_publication_duplicate_stamp_bypass_decision")
    rebuild_body = _body(source, "def _record_final_publication_duplicate_stamp_rebuild")
    stamp_body = _body(source, "def _stamp_final_publication_same_object_verifier_payload")
    legacy_body = _body(source, "def _canonicalize_legacy_design_guide_publication_session_storage")

    guards = {
        "guard_helper_exists": bool(guard_body),
        "guard_prefers_controller_publication_hash_before_payload_fallback": (
            "design_guide_controller_trace_only_parity" in guard_body
            and "controller_publication_hash" in guard_body
            and "live_publication_hash" in guard_body
            and "final_visible_resolution_authority_hash" in guard_body
            and guard_body.find("controller_publication_hash")
            < guard_body.find("final_publication_verifier_payload")
        ),
        "decision_uses_guard_helper": "_final_publication_current_hash_from_debug" in decision_body,
        "decision_records_guard_hash_source": "publication_hash_source" in decision_body
        and "DesignGuideController.publication_hash" in decision_body,
        "debug_force_guard_retained": "debug_force_rebuild" in decision_body,
        "missing_hash_rebuild_retained": "missing_current_publication_hash" in decision_body
        and "missing_previous_publication_hash" in decision_body,
        "stale_hash_rebuild_retained": "stale_or_changed_publication_hash" in decision_body,
        "rebuild_record_prefers_guard_hash": "canonical_hash_text" in rebuild_body
        and "current_hash = canonical_hash_text" in rebuild_body,
        "verifier_stamp_uses_duplicate_bypass_decision": "_final_publication_duplicate_stamp_bypass_decision(" in stamp_body,
        "legacy_stamp_uses_duplicate_bypass_decision": "_final_publication_duplicate_stamp_bypass_decision(" in legacy_body,
        "non_authoritative_surface_flags_retained": all(
            token in decision_body
            for token in (
                '"affects_final_publication": False',
                '"affects_cta": False',
                '"affects_display": False',
                '"affects_apply_payload": False',
                '"affects_visible_wording": False',
            )
        ),
        "no_apply_routing_moved_into_guard": "_record_rendered_design_guide_primary_apply_payload" not in guard_body
        and "_record_rendered_design_guide_primary_apply_payload" not in decision_body,
        "no_rendering_moved_into_guard": "_design_guide_dashboard_card_html_from_render_model" not in guard_body
        and "_design_guide_dashboard_card_html_from_render_model" not in decision_body,
    }

    latest = {
        "rekey_readiness": _latest("design_guide_publication_debug_stamp_authority_hash_rekey_readiness"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "zero_authority_lock": _latest("design_brain_inputs_page_zero_authority_inventory_lock"),
    }
    failures = []
    for key, value in guards.items():
        if value is not True:
            failures.append(f"guard_failed::{key}")
    for name, row in latest.items():
        if row.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    stamp = _stamp()
    payload = {
        "schema": "design_guide_publication_debug_stamp_authority_hash_rekey_implementation.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "guards": guards,
        "latest": latest,
        "product_behavior_changed": False,
    }
    json_path = ARTIFACT_DIR / f"design_guide_publication_debug_stamp_authority_hash_rekey_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_publication_debug_stamp_authority_hash_rekey_implementation_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_publication_debug_stamp_authority_hash_rekey_implementation {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
